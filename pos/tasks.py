"""
POS Celery Tasks — pozadinski procesi.
"""
import logging
from celery import shared_task
from django.db.models import Q
from django.db import IntegrityError, DatabaseError

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
        except ImportError:
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
            except KeyError as e:
                logger.warning('Z-report failed for %s: %s', company.name, e)

    return {'sent': sent, 'date': str(today)}



@shared_task(bind=True, soft_time_limit=30)
def ai_analyze_prigovor(self, prigovor_id):
    """
    AI analiza prigovora potrošača — kategorizacija, sentiment, prijedlog odgovora.
    Koristi Claude Haiku za brzu analizu na hrvatskom jeziku.
    """
    import os, json
    from pos.models import KnjigaPrigovora
    from django.utils import timezone

    try:
        p = KnjigaPrigovora.objects.get(pk=prigovor_id)
    except KnjigaPrigovora.DoesNotExist:
        return {'error': 'Not found'}

    if p.ai_analyzed_at:
        return {'status': 'already_analyzed'}

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY', ''))

        # Adapt prompt based on record type and language
        lang_label = {'hr': 'hrvatskom', 'de': 'Deutsch', 'en': 'English'}.get(p.language, 'hrvatskom')
        type_label = dict(p.RECORD_TYPES).get(p.record_type, p.record_type)

        if p.record_type in ('pohvala', 'utisak'):
            prompt = """Analiziraj %s potrošača i odgovori ISKLJUČIVO kao JSON:

%s:
Ime: %s
Ocjena: %s zvjezdica
Opis: %s

VRATI JSON:
{
  "category": "product_quality|service|pricing|hygiene|wait_time|delivery|warranty|safety|other",
  "sentiment": "positive|very_positive|neutral|constructive",
  "priority": 1 (pohvale nisu hitne),
  "suggested_response": "Kratka zahvala na %s jeziku, profesionalan i srdačan ton, max 100 riječi.",
  "key_positives": ["pozitivna stavka 1", "stavka 2"],
  "auto_respond": true
}""" % (type_label, type_label, p.ime_potrosaca, p.star_rating or '?', p.opis_prigovora[:500], lang_label)
        else:
            deadline = p.legal_deadline_days or 15
            prompt = """Analiziraj %s potrošača i odgovori ISKLJUČIVO kao JSON:

%s:
Ime: %s
Opis: %s

VRATI JSON:
{
  "category": "product_quality|service|pricing|hygiene|wait_time|delivery|warranty|safety|other",
  "sentiment": "critical|negative|neutral|constructive",
  "priority": 1-5 (5=najhitnije, npr. sigurnost/ozljeda),
  "suggested_response": "Prijedlog službenog odgovora na %s jeziku, profesionalan ton, max 200 riječi. Referencira zakonski rok od %d dana.",
  "key_issues": ["kratki opis problema 1", "problem 2"],
  "auto_respond": false,
  "escalate": false
}""" % (type_label, type_label, p.ime_potrosaca, p.opis_prigovora[:500], lang_label, deadline)

        response = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=500,
            messages=[{'role': 'user', 'content': prompt}],
        )

        text = response.content[0].text.strip()
        if text.startswith('```'):
            text = text.split('\n', 1)[1].rsplit('```', 1)[0]
        result = json.loads(text)

        p.ai_category = result.get('category', 'other')[:30]
        p.ai_sentiment = result.get('sentiment', 'neutral')[:15]
        p.ai_priority = min(5, max(1, int(result.get('priority', 3))))
        p.ai_suggested_response = result.get('suggested_response', '')[:2000]
        p.ai_analyzed_at = timezone.now()
        p.save(update_fields=[
            'ai_category', 'ai_sentiment', 'ai_priority',
            'ai_suggested_response', 'ai_analyzed_at',
        ])

        logger.info('AI prigovor #%d [%s]: category=%s sentiment=%s priority=%d',
                     p.redni_broj, p.record_type, p.ai_category, p.ai_sentiment, p.ai_priority)

        # Auto-escalate if critical priority
        if p.ai_priority >= 4 and p.record_type in ('prigovor', 'reklamacija'):
            p.is_escalated = True
            p.escalated_at = timezone.now()
            p.escalation_reason = f'AI prioritet {p.ai_priority}/5 — automatska eskalacija'
            p.save(update_fields=['is_escalated', 'escalated_at', 'escalation_reason'])
            logger.warning('ESKALACIJA: prigovor #%d prioritet %d', p.redni_broj, p.ai_priority)

        # Auto-respond for pohvale/utisci (if AI says auto_respond=true)
        if result.get('auto_respond') and p.record_type in ('pohvala', 'utisak') and not p.odgovor:
            p.odgovor = p.ai_suggested_response
            p.datum_odgovora = timezone.now().date()
            p.response_channel = 'email' if p.consumer_email else ('whatsapp' if p.consumer_phone else '')
            p.save(update_fields=['odgovor', 'datum_odgovora', 'response_channel'])

            # Send auto-response
            if p.consumer_email:
                try:
                    from pos.complaint_views import _send_response_email
                    _send_response_email(p)
                except ImportError:
                    pass
            if p.consumer_phone:
                try:
                    from pos.complaint_views import _send_response_wa
                    _send_response_wa(p)
                except ImportError:
                    pass
            logger.info('Auto-response sent for %s #%d', p.record_type, p.redni_broj)

        # Dron #2: Trigger content moderation for public widget candidates
        if p.record_type in ('pohvala', 'utisak', 'prijedlog'):
            try:
                moderate_prigovor_content.delay(p.pk)
            except Exception:
                pass

        return {
            'category': p.ai_category,
            'sentiment': p.ai_sentiment,
            'priority': p.ai_priority,
            'auto_responded': result.get('auto_respond', False),
            'escalated': p.is_escalated,
        }

    except (json.JSONDecodeError, ValueError) as e:
        logger.warning('AI prigovor #%d failed: %s', prigovor_id, e)
        return {'error': str(e)}


# ══════════════════════════════════════════════════════════════
# OFFLINE POS — 48h Zakonski alarm (Zakon o fiskalizaciji čl.11)
# ══════════════════════════════════════════════════════════════

def _get_company_phone(company):
    """Pronađi telefon vlasnika/admina firme za WhatsApp alert."""
    # 1. Direktno s firme
    phone = getattr(company, 'phone', '') or getattr(company, 'mobile', '')
    if phone:
        return phone
    # 2. CompanyMembership owner/admin
    from accounts.models import CompanyMembership
    membership = (CompanyMembership.objects
        .filter(company=company, role__in=['owner', 'company_admin'], is_active=True)
        .select_related('user__profile')
        .first())
    if membership and hasattr(membership.user, 'profile'):
        phone = getattr(membership.user.profile, 'phone', '') or ''
        if phone:
            return phone
    # 3. Bilo koji aktivan user firme s telefonom
    membership = (CompanyMembership.objects
        .filter(company=company, is_active=True)
        .select_related('user__profile')
        .first())
    if membership and hasattr(membership.user, 'profile'):
        return getattr(membership.user.profile, 'phone', '') or ''
    return ''


def _get_operator_phone(receipt):
    """Pronađi telefon operatera koji je otvorio sesiju."""
    operator = receipt.session.operator
    if operator and hasattr(operator, 'profile'):
        return getattr(operator.profile, 'phone', '') or ''
    return ''


@shared_task(name='pos.check_fiscal_deadline')
def check_fiscal_deadline():
    """
    Svakih 30 min provjeri bonove koji prijete zakonskim rokom.
    Tri razine alarma — šalje WhatsApp operateru I vlasniku firme.

    Tier 1 (>24h): WARNING — operater + admin
    Tier 2 (>36h): SOS CRITICAL — operater + admin + superadmin
    Tier 3 (>48h): BREACH — samo log (retry_fiscalization već handla)

    Anti-spam: svaki tier se šalje samo jednom per receipt (prati se u fiscal_last_error).
    """
    from pos.models import POSReceipt
    from django.utils import timezone
    from datetime import timedelta

    now = timezone.now()

    # Svi plaćeni bez JIR-a, stariji od 12h, mlađi od 48h
    pending = POSReceipt.objects.filter(
        status='paid',
        paid_at__gte=now - timedelta(hours=48),
        paid_at__lt=now - timedelta(hours=12),
    ).filter(
        Q(jir__isnull=True) | Q(jir=''),
    ).exclude(
        session__terminal__company__fiscal_exempt=True,
    ).select_related(
        'session__terminal__company', 'session__operator__profile',
    ).order_by('paid_at')

    if not pending.exists():
        return {'status': 'ok', 'alerts': 0}

    # Grupiraj po kompaniji, pronađi najstariji bon
    from collections import defaultdict
    company_receipts = defaultdict(list)
    for r in pending[:100]:
        company_receipts[r.session.terminal.company].append(r)

    alerts_sent = 0
    tier1_companies = 0  # 24-36h
    tier2_companies = 0  # 36-48h

    for company, receipts in company_receipts.items():
        oldest = receipts[0]  # Sorted by paid_at ASC
        age_h = (now - oldest.paid_at).total_seconds() / 3600
        cnt = len(receipts)

        # Odredi tier
        if age_h >= 36:
            tier = 'SOS_36H'
            tier2_companies += 1
        elif age_h >= 24:
            tier = 'WARN_24H'
            tier1_companies += 1
        else:
            continue  # 12-24h: samo retry, bez alarma korisniku

        # Anti-spam: provjeri jesmo li već alertali ovaj tier za ovu firmu
        already_alerted = any(
            tier in (r.fiscal_last_error or '') for r in receipts
        )
        if already_alerted:
            continue

        # Označi receipte da smo alertali ovaj tier
        for r in receipts:
            existing_err = r.fiscal_last_error or ''
            if tier not in existing_err:
                r.fiscal_last_error = ('%s [%s]' % (existing_err, tier)).strip()
                r.save(update_fields=['fiscal_last_error'])

        # Poruke
        if tier == 'SOS_36H':
            emoji = '\u26a0\ufe0f\u26a0\ufe0f\u26a0\ufe0f'
            msg = (
                '%s HITNO — FISKALIZACIJA\n'
                '%s\n\n'
                '%d racun(a) bez JIR-a, najstariji %.0fh!\n'
                'Zakonski rok: 48h. Preostalo: ~%.0fh.\n'
                'Kazna: do 10.000 EUR.\n\n'
                'SPOJI UREDAJ NA INTERNET ODMAH!\n'
                'limit-connect.com'
            ) % (emoji, company.name, cnt, age_h, 48 - age_h)
        else:  # WARN_24H
            emoji = '\u26a0\ufe0f'
            msg = (
                '%s Fiskalizacija — upozorenje\n'
                '%s\n\n'
                '%d racun(a) ceka JIR vec %.0fh.\n'
                'Rok je 48h — preostalo ~%.0fh.\n'
                'Spoji POS uredaj na internet.\n'
                'limit-connect.com'
            ) % (emoji, company.name, cnt, age_h, 48 - age_h)

        # Šalji WhatsApp
        phones_sent = set()
        try:
            from core.whatsapp import send_text

            # 1. Operater (blagajnik koji je izdao bon)
            op_phone = _get_operator_phone(oldest)
            if op_phone:
                send_text(op_phone, msg)
                phones_sent.add(op_phone)
                alerts_sent += 1

            # 2. Admin/vlasnik firme
            admin_phone = _get_company_phone(company)
            if admin_phone and admin_phone not in phones_sent:
                send_text(admin_phone, msg)
                phones_sent.add(admin_phone)
                alerts_sent += 1

        except ImportError as e:
            logger.warning('check_fiscal_deadline WhatsApp failed (%s): %s', company.name, e)

        # 3. Za SOS tier: superadmin notifikacija + ImprovementSuggestion log
        if tier == 'SOS_36H':
            try:
                from superadmin_ai.tasks import _notify_superadmins
                _notify_superadmins(
                    title='SOS FISKALIZACIJA: %s — %d bonova, %.0fh!' % (company.name, cnt, age_h),
                    message=(
                        '%d racuna bez JIR-a, najstariji %.0fh.\n'
                        'Preostalo ~%.0fh do zakonskog roka.\n'
                        'Tvrtka: %s\n'
                        'WhatsApp poslan: %s'
                    ) % (cnt, age_h, 48 - age_h, company.name,
                         'DA (%d)' % len(phones_sent) if phones_sent else 'NE — nema broja!'),
                    notification_type='system',
                )
            except ImportError:
                pass

            # Log u ImprovementSuggestion (system)
            try:
                from pos.models import ImprovementSuggestion
                ImprovementSuggestion.objects.create(
                    company=company,
                    author=None,
                    source='system',
                    title='FISCAL SOS: %d bonova bez JIR-a (%.0fh)' % (cnt, age_h),
                    description=(
                        'Automatski alarm: %d racuna bez JIR-a, najstariji %.0fh.\n'
                        'Zakonski rok 48h (NN 133/12). WhatsApp poslan: %s.\n'
                        'Operater: %s'
                    ) % (cnt, age_h,
                         ', '.join(phones_sent) if phones_sent else 'NEMA BROJA',
                         oldest.session.operator.username if oldest.session.operator else 'N/A'),
                    category='fiscal',
                    priority=1,
                    status='new',
                )
            except (IntegrityError, DatabaseError):
                pass

        logger.warning(
            '[FISCAL %s] %s: %d bonova, najstariji %.0fh, WA sent: %d',
            tier, company.name, cnt, age_h, len(phones_sent)
        )

    return {
        'status': 'alerts_sent' if alerts_sent else 'no_alerts_needed',
        'tier1_24h': tier1_companies,
        'tier2_36h': tier2_companies,
        'whatsapp_sent': alerts_sent,
    }


@shared_task(bind=True, soft_time_limit=60)
def archive_prigovor_pdf(self, prigovor_id):
    """Auto-archive prigovora u DocumentBlob kao PDF."""
    from pos.models import KnjigaPrigovora
    from pos.complaint_views import archive_prigovor_to_blob

    try:
        p = KnjigaPrigovora.objects.get(pk=prigovor_id)
    except KnjigaPrigovora.DoesNotExist:
        return {'error': 'Not found'}

    try:
        blob = archive_prigovor_to_blob(p)
        logger.info('Prigovor #%d archived as DocumentBlob %s', p.redni_broj, blob.pk)
        return {'status': 'archived', 'blob_id': str(blob.pk)}
    except (ValueError, TypeError) as e:
        logger.warning('Archive prigovor #%d failed: %s', prigovor_id, e)
        return {'error': str(e)}


@shared_task(name='pos.auto_escalate_complaints')
def auto_escalate_complaints():
    """
    Auto-eskalacija za prigovore koji su 3 dana do roka bez odgovora.
    Celery beat: svaki dan u 09:00.
    """
    from pos.models import KnjigaPrigovora
    from django.utils import timezone

    now = timezone.now().date()
    escalated = 0

    pending = KnjigaPrigovora.objects.filter(
        record_type__in=['prigovor', 'reklamacija'],
        datum_odgovora__isnull=True,
        is_escalated=False,
    )

    for p in pending:
        if p.dana_do_roka is not None and p.dana_do_roka <= 3:
            p.is_escalated = True
            p.escalated_at = timezone.now()
            p.escalation_reason = 'Auto-eskalacija: %d dana do zakonskog roka' % p.dana_do_roka
            p.save(update_fields=['is_escalated', 'escalated_at', 'escalation_reason'])
            escalated += 1

            # Notify admin
            try:
                from pos.complaint_views import _notify_admin_new_complaint
                _notify_admin_new_complaint(p)
            except (ValueError, TypeError):
                pass

            logger.warning('Auto-eskalacija prigovor #%d (%s) — %d dana do roka',
                          p.redni_broj, p.company.name, p.dana_do_roka)

    return {'escalated': escalated}


@shared_task(name='pos.weekly_complaints_digest')
def weekly_complaints_digest():
    """
    Weekly digest email adminu — koliko novih prigovora, koliko čeka odgovor.
    Celery beat: ponedjeljak 08:00.
    """
    from pos.models import KnjigaPrigovora
    from companies.models import Company
    from django.utils import timezone
    from datetime import timedelta

    week_ago = timezone.now().date() - timedelta(days=7)
    sent = 0

    for company in Company.objects.filter(is_platform_owner=False):
        qs = KnjigaPrigovora.objects.filter(company=company)
        new_week = qs.filter(datum_primitka__gte=week_ago).count()
        pending = qs.filter(
            record_type__in=['prigovor', 'reklamacija'],
            datum_odgovora__isnull=True,
        ).count()
        overdue = sum(1 for p in qs.filter(
            record_type__in=['prigovor', 'reklamacija'],
            datum_odgovora__isnull=True,
        ) if p.rok_istekao)

        if new_week == 0 and pending == 0:
            continue

        # Find admin email
        from accounts.models import UserProfile
        admin = UserProfile.objects.filter(
            company=company,
            role__in=['tenant_admin', 'company_admin', 'owner'],
        ).select_related('user').first()

        if not admin or not admin.user.email:
            continue

        from django.core.mail import send_mail
        from django.conf import settings

        subject = 'Knjiga boljitaka — tjedni pregled (%s)' % company.name
        body = (
            'Tjedni pregled Knjige boljitaka\n'
            '==========================================\n\n'
            'Novi zapisi (zadnjih 7 dana): %d\n'
            'Cekaju odgovor: %d\n'
            'Prekoracen rok: %d\n\n'
            'Pogledajte na: https://limit-connect.com/pos/prigovori/dashboard/\n\n'
            'LIMIT Connect\n'
        ) % (new_week, pending, overdue)

        try:
            send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [admin.user.email], fail_silently=True)
            sent += 1
        except Exception:
            pass

    return {'sent': sent}


@shared_task(bind=True, soft_time_limit=30)
def moderate_prigovor_content(self, prigovor_id):
    """
    DRON #2: AI Content Moderation za javni widget.
    Provjerava sadržaj za:
    - Vlastita imena (NER — može biti kleveta)
    - OIB-ove (11-znamenkasti, GDPR kršenje)
    - Psovke i uvrede
    - Osobne podatke (email, telefon u tekstu)

    Ako prođe → moderation_passed=True, is_public=True
    Ako ne prođe → moderation_passed=False, moderation_note s razlogom
    """
    import os
    import re
    from pos.models import KnjigaPrigovora

    try:
        p = KnjigaPrigovora.objects.get(pk=prigovor_id)
    except KnjigaPrigovora.DoesNotExist:
        return {'error': 'Not found'}

    # Only moderate pohvale/utisci/prijedlozi (prigovori never go public)
    if p.record_type in ('prigovor', 'reklamacija'):
        return {'status': 'skip', 'reason': 'prigovori never public'}

    text = (p.opis_prigovora or '').strip()
    issues = []

    # ── Rule 1: OIB detection (11-digit Croatian ID) ──
    oib_pattern = re.compile(r'\b\d{11}\b')
    if oib_pattern.search(text):
        issues.append('Sadrži OIB (osobni identifikacijski broj) — GDPR čl.87')

    # ── Rule 2: Email in text ──
    email_pattern = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
    if email_pattern.search(text):
        issues.append('Sadrži email adresu u tekstu — osobni podatak')

    # ── Rule 3: Phone number in text ──
    phone_pattern = re.compile(r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}')
    if phone_pattern.search(text):
        issues.append('Sadrži telefonski broj u tekstu — osobni podatak')

    # ── Rule 4: Common profanity (HR + DE basic list) ──
    profanity_hr = [
        'jeb', 'pičk', 'kurac', 'sranj', 'pizd', 'drolja', 'kurv',
        'debil', 'idiot', 'kreten', 'retard', 'šupak',
    ]
    profanity_de = [
        'scheiß', 'fick', 'arsch', 'hurensohn', 'wichser', 'fotze',
        'missgeburt', 'idiot', 'bastard',
    ]
    text_lower = text.lower()
    for word in profanity_hr + profanity_de:
        if word in text_lower:
            issues.append(f'Sadrži neprimjeren jezik: "{word}..."')
            break  # One is enough

    # ── Rule 5: AI NER check for proper names (Claude Haiku) ──
    if not issues:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY', ''))
            response = client.messages.create(
                model='claude-haiku-4-5-20251001',
                max_tokens=200,
                messages=[{'role': 'user', 'content': (
                    'Analiziraj ovaj tekst recenzije i odgovori SAMO kao JSON:\n\n'
                    f'"{text[:500]}"\n\n'
                    'Vrati JSON:\n'
                    '{"has_names": true/false, "names_found": ["ime1"], '
                    '"has_defamation": true/false, "safe_for_public": true/false, '
                    '"reason": "kratko obrazloženje"}'
                )}],
            )
            result_text = response.content[0].text.strip()
            if result_text.startswith('```'):
                result_text = result_text.split('\n', 1)[1].rsplit('```', 1)[0]
            import json
            result = json.loads(result_text)

            if result.get('has_names'):
                names = ', '.join(result.get('names_found', []))
                issues.append(f'AI detektirao vlastita imena: {names} — rizik klevete')

            if result.get('has_defamation'):
                issues.append(f'AI: potencijalna kleveta — {result.get("reason", "")}')

            if not result.get('safe_for_public', True):
                issues.append(f'AI: nije sigurno za javni prikaz — {result.get("reason", "")}')

        except (json.JSONDecodeError, ValueError) as e:
            logger.debug('AI moderation for #%d failed: %s', p.redni_broj, e)
            # If AI unavailable, don't auto-approve — leave for manual review
            issues.append('AI moderacija nedostupna — potrebna ručna provjera')

    # ── Decision ──
    if issues:
        p.moderation_passed = False
        p.moderation_note = '; '.join(issues)[:500]
        p.is_public = False
        p.save(update_fields=['moderation_passed', 'moderation_note', 'is_public'])
        logger.info('Moderation FAILED for #%d: %s', p.redni_broj, p.moderation_note)
        return {'status': 'rejected', 'issues': issues}
    else:
        p.moderation_passed = True
        p.moderation_note = 'AI + regex provjera prošla — sigurno za javni prikaz'
        # Auto-set public display name (GDPR: samo inicijali)
        if not p.public_display_name and p.ime_potrosaca:
            parts = p.ime_potrosaca.strip().split()
            if len(parts) >= 2:
                p.public_display_name = f'{parts[0]} {parts[-1][0]}.'
            else:
                p.public_display_name = parts[0] if parts else 'Anonim'
        p.is_public = True
        p.save(update_fields=['moderation_passed', 'moderation_note', 'is_public', 'public_display_name'])
        logger.info('Moderation PASSED for #%d', p.redni_broj)
        return {'status': 'approved'}
