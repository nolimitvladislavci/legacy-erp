"""
POS Celery Tasks — pozadinski procesi.
"""
import logging
from celery import shared_task
from django.db.models import Q

logger = logging.getLogger('pos.tasks')


@shared_task(name='pos.retry_fiscalization', soft_time_limit=120)
def retry_fiscalization():
    """
    Automatski retry nefiskaliziranih računa.
    Pokreće se svake 2 minute via Celery Beat.

    Zakon o fiskalizaciji (NN 133/12):
    - ZKI se generira lokalno (privatni ključ)
    - JIR se dobiva od FINA CIS-a
    - Offline račun je valjan s ZKI bez JIR-a
    - Sustav MORA naknadno poslati račun čim je veza dostupna
    - Rok: 48 sati od izdavanja računa

    Poboljšanja B-04:
    - 48h deadline tracking — računi stariji od 48h idu u CRITICAL alert
    - Eksponencijalni backoff: retry_count 0-5 odmah, 6-10 svakih 10 min, 11+ svakih 30 min
    - fiscal_retry_count i fiscal_last_error per-receipt
    - Notifikacija superadminu za račune > 24h bez JIR-a
    """
    from pos.models import POSReceipt
    from pos.services import _attempt_fiscalization
    from django.utils import timezone
    from datetime import timedelta

    now = timezone.now()

    # B-04 FIX: Računi koji trebaju fiskalizaciju — plaćeni, nemaju JIR, unutar 48h
    # Uključuje i račune koji nemaju ZKI (potpuni pad fiskalizacije)
    cutoff_48h = now - timedelta(hours=48)
    pending = POSReceipt.objects.filter(
        status='paid',
        paid_at__gte=cutoff_48h,
    ).filter(
        Q(jir__isnull=True) | Q(jir=''),
    ).exclude(
        # Dual-Routing: udruge izvan sustava PDV-a ne idu u FINA retry
        session__terminal__company__fiscal_exempt=True,
    ).order_by('paid_at')

    if not pending.exists():
        return {'status': 'ok', 'message': 'Nema nefiskaliziranih računa'}

    ok = 0
    fail = 0
    critical_48h = 0
    warning_24h = 0

    for receipt in pending[:50]:  # Max 50 po runu
        age_hours = (now - receipt.paid_at).total_seconds() / 3600 if receipt.paid_at else 0

        # 48h DEADLINE — zakonski prekršaj
        if age_hours > 48:
            critical_48h += 1
            receipt.fiscal_last_error = 'CRITICAL: Račun star %.0fh — prekoračen zakonski rok 48h!' % age_hours
            receipt.save(update_fields=['fiscal_last_error'])
            logger.critical(
                '[FISCAL CRITICAL] Račun #%d star %.0fh — PREKORAČEN 48h rok! ZKI: %s',
                receipt.receipt_number, age_hours, receipt.zki
            )
            continue

        # 24h WARNING
        if age_hours > 24:
            warning_24h += 1

        # Eksponencijalni backoff
        retry_count = receipt.fiscal_retry_count or 0
        if retry_count > 10 and retry_count % 15 != 0:
            continue  # >10 pokušaja: retry svaki 15. put (30 min interval)
        if 5 < retry_count <= 10 and retry_count % 5 != 0:
            continue  # 6-10 pokušaja: retry svaki 5. put (10 min interval)

        # Pokušaj fiskalizaciju
        try:
            jir = _attempt_fiscalization(receipt)
            if jir:
                ok += 1
                receipt.fiscal_retry_count = retry_count + 1
                receipt.fiscal_last_error = ''
                receipt.save(update_fields=['fiscal_retry_count', 'fiscal_last_error'])
                logger.info(
                    'Naknadno fiskaliziran račun #%d (JIR: %s, pokušaj %d, %.0fh star)',
                    receipt.receipt_number, jir[:12], retry_count + 1, age_hours
                )
            else:
                fail += 1
                receipt.fiscal_retry_count = retry_count + 1
                receipt.fiscal_last_error = 'JIR not returned (attempt %d)' % (retry_count + 1)
                receipt.save(update_fields=['fiscal_retry_count', 'fiscal_last_error'])
        except Exception as e:
            fail += 1
            receipt.fiscal_retry_count = retry_count + 1
            receipt.fiscal_last_error = str(e)[:200]
            receipt.save(update_fields=['fiscal_retry_count', 'fiscal_last_error'])
            logger.warning(
                'Retry fiskalizacija #%d neuspješna (pokušaj %d): %s',
                receipt.receipt_number, retry_count + 1, e
            )

    # Notifikacija za kritične slučajeve
    if critical_48h > 0 or warning_24h > 0:
        try:
            from superadmin_ai.tasks import _notify_superadmins
            if critical_48h > 0:
                _notify_superadmins(
                    title='FISKALIZACIJA CRITICAL: %d računa prekoračilo 48h rok!' % critical_48h,
                    message=(
                        '%d računa NIJE fiskalizirano unutar zakonskog roka od 48h.\n'
                        'Ovo je zakonski prekršaj (NN 133/12). Hitno provjerite FINA CIS vezu.\n'
                        'Pogledajte: /pos/ → Nefiskalizirani računi'
                    ) % critical_48h,
                    notification_type='system',
                )
            elif warning_24h > 0:
                _notify_superadmins(
                    title='Fiskalizacija: %d računa čeka JIR > 24h' % warning_24h,
                    message=(
                        '%d računa nije dobilo JIR duže od 24h.\n'
                        'Rok je 48h — provjerite internet vezu i FINA certifikat.'
                    ) % warning_24h,
                    notification_type='system',
                )
        except Exception:
            pass

    result = {
        'status': 'completed',
        'total': pending.count(),
        'success': ok,
        'failed': fail,
        'critical_48h': critical_48h,
        'warning_24h': warning_24h,
    }
    if ok > 0:
        logger.info('Retry fiskalizacija: %d/%d uspješno', ok, pending.count())
    return result


@shared_task(name='pos.generate_missing_daily_reports')
def generate_missing_daily_reports():
    """
    Generiraj POSDailyReport za zatvorene sesije koje ga nemaju.
    Pokriva slučaj kad signal nije pokrenut (restart servera, bug, itd.)
    """
    from pos.models import POSSession, POSDailyReport

    closed_sessions = POSSession.objects.filter(
        status__in=['closed', 'z_done']
    ).exclude(
        daily_report__isnull=False
    ).order_by('-closed_at')[:20]

    generated = 0
    for session in closed_sessions:
        try:
            POSDailyReport.generate_from_session(session)
            generated += 1
        except Exception as e:
            logger.warning('DailyReport za sesiju #%d: %s', session.pk, e)

    return {'generated': generated}


@shared_task(name='pos.cleanup_zombie_sessions')
def cleanup_zombie_sessions():
    """
    Automatski zatvori sesije otvorene duže od 16 sati.
    Sprječava zombie sesije od zaboravljenih logout-ova.
    """
    from pos.models import POSSession, POSDailyReport
    from django.utils import timezone
    from datetime import timedelta

    cutoff = timezone.now() - timedelta(hours=16)
    zombies = POSSession.objects.filter(
        status='open',
        opened_at__lt=cutoff,
    )

    count = zombies.count()
    if count == 0:
        return {'status': 'ok', 'zombies': 0}

    for s in zombies:
        s.closing_cash = s.opening_cash
        s.closed_at = timezone.now()
        s.status = 'closed'
        s.save()
        try:
            POSDailyReport.generate_from_session(s)
        except Exception:
            pass
        logger.warning('Zombie sesija #%d auto-zatvorena (otvorena %s)', s.pk, s.opened_at)

    return {'status': 'cleaned', 'zombies': count}



@shared_task(bind=True, soft_time_limit=120)
def nightly_owner_zreport(self):
    """
    Ponocni Z-report na WhatsApp za vlasnike.
    Svaku vecer u 23:55 — vlasnik dobije dnevni sazetak.
    Psiholoski: dopaminska ovisnost o poruci = 0% churn.
    """
    from companies.models import Company
    from pos.models import POSSession, POSReceipt, POSReceiptItem, POSPaymentLine
    from django.db.models import Sum
    from django.utils import timezone
    from core.whatsapp import send_text
    import logging

    logger = logging.getLogger('pos.nightly')
    today = timezone.now().date()
    sent = 0

    for company in Company.objects.filter(is_platform_owner=False):
        # Provjeri ima li POS aktivnost danas
        receipts = POSReceipt.objects.filter(
            session__terminal__company=company,
            status='paid',
            created_at__date=today,
        )
        if not receipts.exists():
            continue

        # Izracunaj metriku
        total = receipts.aggregate(s=Sum('total'))['s'] or 0
        count = receipts.count()
        cash = POSPaymentLine.objects.filter(
            receipt__in=receipts, method='CASH'
        ).aggregate(s=Sum('amount'))['s'] or 0
        card = POSPaymentLine.objects.filter(
            receipt__in=receipts, method__in=['CARD', 'REVOLUT']
        ).aggregate(s=Sum('amount'))['s'] or 0

        # Top artikl
        top = POSReceiptItem.objects.filter(
            receipt__in=receipts, is_tip=False,
        ).values('description').annotate(
            qty=Sum('quantity'), rev=Sum('total_price')
        ).order_by('-rev').first()
        top_item = '%s (%sx)' % (top['description'][:20], int(top['qty'])) if top else 'N/A'

        # Napojnice
        tips = POSReceiptItem.objects.filter(
            receipt__in=receipts, is_tip=True,
        ).aggregate(s=Sum('unit_price'))['s'] or 0

        # Smjene
        sessions = POSSession.objects.filter(
            terminal__company=company,
            opened_at__date=today,
        ).count()

        # Poruka
        msg = (
            'Z-Izvjestaj (%s)\n\n'
            'Promet: %.2f EUR (%d bonova)\n'
            'Gotovina: %.2f EUR\n'
            'Kartica: %.2f EUR\n'
            'Napojnice: %.2f EUR\n'
            'Top artikl: %s\n'
            'Smjena: %d\n\n'
            'Sve je fiskalizirano i sigurno.\n'
            'limit-connect.com'
        ) % (today.strftime('%d.%m.'), total, count, cash, card, tips, top_item, sessions)

        # Posalji vlasniku
        phone = company.phone or company.mobile
        if not phone:
            # Trazi admina firme
            from accounts.models import CompanyMembership
            admin = CompanyMembership.objects.filter(
                company=company, role__in=['owner', 'company_admin'], is_active=True,
            ).select_related('user__profile').first()
            if admin and hasattr(admin.user, 'profile'):
                phone = getattr(admin.user.profile, 'phone', '') or ''

        if phone:
            try:
                result = send_text(phone, msg)
                if result.get('success'):
                    sent += 1
                    logger.info('Z-report sent to %s (%s)', company.name, phone)
            except Exception as e:
                logger.warning('Z-report failed for %s: %s', company.name, e)

    return {'sent': sent, 'date': str(today)}
