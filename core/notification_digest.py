"""
core/notification_digest.py — Tjedni digest notifikacija za udruge

Celery task: send_weekly_digest
- Ponedjeljak 08:00 — šalje agregirani tjedni izvještaj po firmi
- Samo za firme s business_type='udruga' (i zadruga, ustanova)
- Preskoči firme s notification_mode='off' ili bez upozorenja

Kategorije upozorenja:
  - Oprema čiji atesti ističu (DVD — vatrogasna oprema)
  - Ribolovne dozvole koje ističu
  - Košnice koje trebaju tretman
  - Članarine koje kasne
  - Dokumenti koji ističu (svi)

LIMIT Connect ERP — 2026-03-25
"""
import logging
from datetime import timedelta
from collections import defaultdict

from celery import shared_task
from django.conf import settings
from django.utils import timezone
from django.db import DatabaseError

logger = logging.getLogger(__name__)

# Koliko dana unaprijed upozoriti
WARN_DAYS_ATEST = 30       # Atesti opreme
WARN_DAYS_DOZVOLA = 30     # Ribolovne dozvole
WARN_DAYS_DOCUMENT = 14    # Dokumenti
WARN_DAYS_TRETMAN = 60     # Košnice bez tretmana


def _get_notification_mode(company):
    """Dohvati notification_mode iz CompanyModuleConfig."""
    try:
        config = company.module_config
        return getattr(config, 'notification_mode', 'digest')
    except (AttributeError, TypeError):
        return 'digest'


def _get_whatsapp_opt_in(company):
    """Provjeri ima li firma WhatsApp opt-in (kroz Clan model admin)."""
    try:
        from udruge.models import Clan
        admin_clan = Clan.objects.filter(
            company=company, whatsapp_opt_in=True
        ).first()
        return admin_clan.telefon if admin_clan else None
    except DatabaseError:
        return None


def collect_alerts_for_company(company):
    """
    Prikuplja sva upozorenja za jednu firmu.
    Vraća dict: {kategorija: [lista upozorenja]}
    """
    today = timezone.now().date()
    alerts = defaultdict(list)

    # ── 1. Vatrogasna oprema — atesti koji ističu ────────────────
    try:
        from udruge.models import VatrogasnaOprema
        warn_date = today + timedelta(days=WARN_DAYS_ATEST)
        oprema_qs = VatrogasnaOprema.objects.filter(
            company=company,
            status__in=['ispravno', 'servis'],
            atest_vrijedi_do__isnull=False,
            atest_vrijedi_do__lte=warn_date,
        ).order_by('atest_vrijedi_do')

        for op in oprema_qs:
            days_left = (op.atest_vrijedi_do - today).days
            if days_left < 0:
                urgency = 'ISTEKAO'
                urgency_class = 'danger'
            elif days_left <= 7:
                urgency = f'ističe za {days_left} dana'
                urgency_class = 'danger'
            else:
                urgency = f'ističe za {days_left} dana'
                urgency_class = 'warning'

            alerts['Oprema — atesti'].append({
                'naziv': f'{op.naziv} ({op.get_kategorija_display()})',
                'detalj': f'Atest: {op.atest_vrijedi_do:%d.%m.%Y} — {urgency}',
                'urgency': urgency_class,
                'datum': op.atest_vrijedi_do,
            })
    except DatabaseError as e:
        logger.debug('digest: skip oprema za %s: %s', company.name, e)

    # ── 2. Ribolovne dozvole koje ističu ─────────────────────────
    try:
        from udruge.models import RibolovnaDozvola
        warn_date = today + timedelta(days=WARN_DAYS_DOZVOLA)
        dozvole_qs = RibolovnaDozvola.objects.filter(
            company=company,
            valid_until__lte=warn_date,
            valid_until__gte=today - timedelta(days=7),  # i one koje su nedavno istekle
        ).select_related('clan').order_by('valid_until')

        for doz in dozvole_qs:
            days_left = (doz.valid_until - today).days
            if days_left < 0:
                urgency = 'ISTEKLA'
                urgency_class = 'danger'
            elif days_left <= 7:
                urgency = f'ističe za {days_left} dana'
                urgency_class = 'danger'
            else:
                urgency = f'ističe za {days_left} dana'
                urgency_class = 'warning'

            alerts['Ribolovne dozvole'].append({
                'naziv': f'{doz.clan} — {doz.get_kategorija_display()}',
                'detalj': f'Br. {doz.broj_dozvole}, do {doz.valid_until:%d.%m.%Y} — {urgency}',
                'urgency': urgency_class,
                'datum': doz.valid_until,
            })
    except DatabaseError as e:
        logger.debug('digest: skip dozvole za %s: %s', company.name, e)

    # ── 3. Košnice koje trebaju tretman ───────────────────────────
    try:
        from udruge.models import Kosnica, TretmanKosnice
        warn_date = today - timedelta(days=WARN_DAYS_TRETMAN)

        # Nađi sve aktivne košnice firme
        from udruge.models import Pcelinjak
        pcelinjaci = Pcelinjak.objects.filter(company=company)
        kosnice = Kosnica.objects.filter(
            pcelinjak__in=pcelinjaci,
            status__in=['aktivna', 'bolesna'],
        )

        for kosnica in kosnice:
            zadnji_tretman = TretmanKosnice.objects.filter(
                kosnica=kosnica
            ).order_by('-datum').first()

            needs_treatment = False
            reason = ''

            if kosnica.status == 'bolesna':
                needs_treatment = True
                reason = 'Status: BOLESNA'
                urgency_class = 'danger'
            elif not zadnji_tretman:
                needs_treatment = True
                reason = 'Nikad tretirana'
                urgency_class = 'warning'
            elif zadnji_tretman.datum < warn_date:
                days_since = (today - zadnji_tretman.datum).days
                needs_treatment = True
                reason = f'Zadnji tretman prije {days_since} dana ({zadnji_tretman.datum:%d.%m.%Y})'
                urgency_class = 'warning'

            # Karencija upozorenje
            if zadnji_tretman and zadnji_tretman.karencija_do and zadnji_tretman.karencija_do >= today:
                alerts['Košnice — karencija'].append({
                    'naziv': str(kosnica),
                    'detalj': f'Zabrana vrcanja do {zadnji_tretman.karencija_do:%d.%m.%Y} ({zadnji_tretman.get_tip_display()})',
                    'urgency': 'info',
                    'datum': zadnji_tretman.karencija_do,
                })

            if needs_treatment:
                alerts['Košnice — tretman'].append({
                    'naziv': str(kosnica),
                    'detalj': reason,
                    'urgency': urgency_class,
                    'datum': zadnji_tretman.datum if zadnji_tretman else None,
                })
    except DatabaseError as e:
        logger.debug('digest: skip košnice za %s: %s', company.name, e)

    # ── 4. Članarine koje kasne ──────────────────────────────────
    try:
        from udruge.models import Clanarina
        kasne_qs = Clanarina.objects.filter(
            company=company,
            status='kasni',
        ).select_related('clan').order_by('period_end')

        for cl in kasne_qs:
            days_overdue = (today - cl.period_end).days
            alerts['Članarine — kasne'].append({
                'naziv': f'{cl.clan} — {cl.amount} EUR',
                'detalj': f'Period: {cl.period_start:%d.%m.%Y} - {cl.period_end:%d.%m.%Y} (kasni {days_overdue} dana)',
                'urgency': 'danger' if days_overdue > 30 else 'warning',
                'datum': cl.period_end,
            })

        # Također provjeri "ceka" starije od 30 dana
        stale_date = today - timedelta(days=30)
        ceka_qs = Clanarina.objects.filter(
            company=company,
            status='ceka',
            period_end__lt=stale_date,
        ).select_related('clan').order_by('period_end')

        for cl in ceka_qs:
            alerts['Članarine — čekaju uplatu'].append({
                'naziv': f'{cl.clan} — {cl.amount} EUR',
                'detalj': f'Period: {cl.period_start:%d.%m.%Y} - {cl.period_end:%d.%m.%Y}',
                'urgency': 'warning',
                'datum': cl.period_end,
            })
    except DatabaseError as e:
        logger.debug('digest: skip članarine za %s: %s', company.name, e)

    # ── 5. Dokumenti koji ističu ─────────────────────────────────
    try:
        from documents.models import Document
        warn_date = today + timedelta(days=WARN_DAYS_DOCUMENT)
        doc_qs = Document.objects.filter(
            company=company,
            doc_type='contract',
            date_due__isnull=False,
            date_due__lte=warn_date,
            date_due__gte=today - timedelta(days=7),
        ).order_by('date_due')

        for doc in doc_qs:
            days_left = (doc.date_due - today).days
            if days_left < 0:
                urgency = 'ISTEKAO'
                urgency_class = 'danger'
            else:
                urgency = f'ističe za {days_left} dana'
                urgency_class = 'warning'

            alerts['Dokumenti'].append({
                'naziv': f'{doc.doc_number} — {doc.get_doc_type_display()}',
                'detalj': f'Rok: {doc.date_due:%d.%m.%Y} — {urgency}',
                'urgency': urgency_class,
                'datum': doc.date_due,
            })
    except DatabaseError as e:
        logger.debug('digest: skip dokumenti za %s: %s', company.name, e)

    return dict(alerts)


def render_digest_html(company, alerts):
    """
    Generiraj HTML email sa svim upozorenjima, grupiranim po kategoriji.
    Koristi inline stilove za email kompatibilnost.
    """
    total_count = sum(len(items) for items in alerts.values())
    danger_count = sum(
        1 for items in alerts.values()
        for item in items if item.get('urgency') == 'danger'
    )
    today = timezone.now()

    # Inline HTML — email klijenti ne podržavaju <style> block
    html = f"""<!DOCTYPE html>
<html lang="hr">
<head><meta charset="utf-8"></head>
<body style="font-family: 'Barlow', Arial, sans-serif; background: #1a1a2e; color: #e0e0e0; padding: 20px; margin: 0;">
<div style="max-width: 650px; margin: 0 auto; background: #16213e; border-radius: 12px; overflow: hidden; border: 1px solid #c9a84c33;">

<!-- Header -->
<div style="background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 24px 30px; border-bottom: 2px solid #c9a84c;">
    <h1 style="margin: 0; color: #c9a84c; font-family: 'Cormorant Garamond', Georgia, serif; font-size: 24px;">
        LIMIT Connect — Tjedni Digest
    </h1>
    <p style="margin: 4px 0 0; color: #aaa; font-size: 14px;">
        {company.name} &mdash; {today:%d.%m.%Y %H:%M}
    </p>
</div>

<!-- Summary bar -->
<div style="background: #0f3460; padding: 16px 30px; display: flex;">
    <span style="color: #c9a84c; font-weight: bold; font-size: 16px;">
        {total_count} upozorenje{'a' if total_count != 1 else ''}
    </span>
    {'&nbsp;&nbsp;|&nbsp;&nbsp;<span style="color: #ff4444; font-weight: bold;">%d kritično</span>' % danger_count if danger_count else ''}
</div>

<!-- Alerts by category -->
<div style="padding: 20px 30px;">
"""

    urgency_colors = {
        'danger': '#ff4444',
        'warning': '#ffaa00',
        'info': '#4488ff',
    }

    for category, items in alerts.items():
        html += f"""
    <h2 style="color: #c9a84c; font-size: 18px; margin: 24px 0 12px; padding-bottom: 8px; border-bottom: 1px solid #c9a84c33;">
        {category} ({len(items)})
    </h2>
    <table style="width: 100%; border-collapse: collapse; margin-bottom: 16px;">
        <tr style="background: #0f3460;">
            <th style="text-align: left; padding: 8px 12px; color: #c9a84c; font-size: 13px; border-bottom: 1px solid #c9a84c44;">Stavka</th>
            <th style="text-align: left; padding: 8px 12px; color: #c9a84c; font-size: 13px; border-bottom: 1px solid #c9a84c44;">Detalj</th>
        </tr>
"""
        for item in items:
            color = urgency_colors.get(item.get('urgency', 'info'), '#4488ff')
            html += f"""
        <tr style="border-bottom: 1px solid #ffffff0d;">
            <td style="padding: 10px 12px; font-size: 14px;">
                <span style="color: {color}; font-weight: bold;">&#9679;</span>&nbsp;
                {item['naziv']}
            </td>
            <td style="padding: 10px 12px; font-size: 13px; color: #aaa;">
                {item['detalj']}
            </td>
        </tr>
"""
        html += "    </table>\n"

    html += """
</div>

<!-- Footer -->
<div style="background: #0f3460; padding: 16px 30px; border-top: 1px solid #c9a84c33; text-align: center;">
    <p style="margin: 0; font-size: 12px; color: #666;">
        LIMIT Connect ERP &mdash; limit-connect.com<br>
        Automatski tjedni digest &mdash; postavke: /settings/notifications/
    </p>
</div>

</div>
</body>
</html>"""

    return html


def render_digest_plaintext(company, alerts):
    """Plaintext fallback za email klijente koji ne podržavaju HTML."""
    today = timezone.now()
    lines = [
        'LIMIT Connect — Tjedni Digest',
        f'{company.name} — {today:%d.%m.%Y %H:%M}',
        '=' * 50,
        '',
    ]

    total_count = sum(len(items) for items in alerts.values())
    lines.append(f'Ukupno upozorenja: {total_count}')
    lines.append('')

    for category, items in alerts.items():
        lines.append(f'--- {category} ({len(items)}) ---')
        for item in items:
            urgency_marker = '!!!' if item.get('urgency') == 'danger' else '!'
            lines.append(f'  {urgency_marker} {item["naziv"]}')
            lines.append(f'     {item["detalj"]}')
        lines.append('')

    lines.append('--')
    lines.append('LIMIT Connect ERP — limit-connect.com')
    return '\n'.join(lines)


def render_whatsapp_digest(company, alerts):
    """Kratka WhatsApp verzija digesta."""
    total = sum(len(items) for items in alerts.values())
    danger = sum(
        1 for items in alerts.values()
        for item in items if item.get('urgency') == 'danger'
    )

    msg = '📋 *LIMIT Connect — Tjedni Digest*\n'
    msg += f'*{company.name}*\n\n'
    msg += f'Ukupno: *{total}* upozorenja'
    if danger:
        msg += f' (🔴 {danger} kritičnih)'
    msg += '\n\n'

    for category, items in alerts.items():
        msg += f'*{category}* ({len(items)}):\n'
        for item in items[:5]:  # Max 5 po kategoriji za WhatsApp
            icon = '🔴' if item.get('urgency') == 'danger' else '🟡'
            msg += f'{icon} {item["naziv"]}\n'
        if len(items) > 5:
            msg += f'  ... i još {len(items) - 5}\n'
        msg += '\n'

    msg += '➡️ Detalji: limit-connect.com'
    return msg


# ═══════════════════════════════════════════════════════════════
#  CELERY TASK — send_weekly_digest
# ═══════════════════════════════════════════════════════════════

@shared_task(bind=True, max_retries=2, soft_time_limit=300)
def send_weekly_digest(self):
    """
    Ponedjeljak 08:00 — šalje agregirani tjedni izvještaj po firmi.
    
    Sadržaj:
    - Oprema čiji atesti ističu (DVD)
    - Ribolovne dozvole koje ističu (Ribari)
    - Košnice koje trebaju tretman (Pčelari)
    - Članarine koje kasne (svi)
    - Dokumenti koji ističu (svi)
    
    Preskoči firme bez upozorenja ili s notification_mode='off'.
    """
    from companies.models import Company

    # Sve nonprofit firme (udruga, zadruga, ustanova)
    nonprofit_types = ['udruga', 'zadruga', 'ustanova']
    companies = Company.objects.filter(
        business_type__in=nonprofit_types
    ).select_related('module_config')

    sent_count = 0
    skip_count = 0
    error_count = 0

    for company in companies:
        try:
            # Provjeri notification_mode
            mode = _get_notification_mode(company)
            if mode == 'off':
                skip_count += 1
                logger.debug('digest: skip %s (notification_mode=off)', company.name)
                continue

            # Prikupi upozorenja
            alerts = collect_alerts_for_company(company)

            if not alerts:
                skip_count += 1
                logger.debug('digest: skip %s (nema upozorenja)', company.name)
                continue

            # Email primatelja
            admin_email = company.email
            if not admin_email:
                logger.warning('digest: %s nema email adresu, preskačem', company.name)
                skip_count += 1
                continue

            # Generiraj email
            html_body = render_digest_html(company, alerts)
            text_body = render_digest_plaintext(company, alerts)
            total_alerts = sum(len(items) for items in alerts.values())
            subject = f'LIMIT Connect — Tjedni izvještaj: {total_alerts} upozorenja — {company.name}'

            # Pošalji async email
            from core.email_tasks import send_html_email_task
            send_html_email_task.delay(
                subject=subject,
                text_body=text_body,
                html_body=html_body,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@limit-connect.com'),
                recipient_list=[admin_email],
            )

            sent_count += 1
            logger.info('digest: email za %s (%d upozorenja) -> %s',
                        company.name, total_alerts, admin_email)

            # WhatsApp digest (opcija)
            wa_phone = _get_whatsapp_opt_in(company)
            if wa_phone:
                try:
                    from core.whatsapp_tasks import send_whatsapp_text_task
                    wa_msg = render_whatsapp_digest(company, alerts)
                    send_whatsapp_text_task.delay(wa_phone, wa_msg)
                    logger.info('digest: WhatsApp za %s -> %s', company.name, wa_phone)
                except ImportError as e:
                    logger.warning('digest: WhatsApp fail za %s: %s', company.name, e)

        except ImportError as e:
            error_count += 1
            logger.error('digest: greška za %s: %s', company.name, e, exc_info=True)

    result = (
        f'Weekly digest complete: sent={sent_count}, '
        f'skipped={skip_count}, errors={error_count}'
    )
    logger.info(result)
    return result
