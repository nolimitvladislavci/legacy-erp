from celery import shared_task
import logging
log = logging.getLogger('seasonal')


@shared_task(name='seasonal.daily_hzmo_check')
def daily_hzmo_check():
    """
    Svaki dan 08:15 — HZMO rokovi + istek ugovora.
    Šalje WhatsApp samo kad treba (5/2/1/0 dana).
    """
    from django.utils import timezone
    from .models import SeasonalContract
    from core.whatsapp import send_text

    today  = timezone.localdate()
    alerts = []

    contracts = SeasonalContract.objects.filter(
        status__in=['pending', 'active', 'completed']
    ).select_related('worker', 'company')

    for c in contracts:
        name         = c.worker.full_name
        company_name = c.company.name

        # M-1 alarm
        if c.contract_type == 'odredjeno' and not c.hzmo_prijava_sent:
            dl = (c.hzmo_prijava_deadline - today).days
            if dl in (5, 2, 1, 0):
                ico = '🔴' if dl <= 1 else '🟡'
                alerts.append(
                    f'{ico} M-1 HZMO: {name} ({company_name})\n'
                    f'   Rok: {c.hzmo_prijava_deadline} — '
                    f'{"DANAS!" if dl == 0 else f"za {dl} dana"}'
                )

        # M-2 alarm
        if (c.contract_type == 'odredjeno'
                and c.status == 'completed'
                and not c.hzmo_odjava_sent):
            dl = (c.hzmo_odjava_deadline - today).days
            if dl in (5, 2, 1, 0):
                ico = '🔴' if dl <= 1 else '🟡'
                alerts.append(
                    f'{ico} M-2 HZMO: {name} ({company_name})\n'
                    f'   Rok: {c.hzmo_odjava_deadline} — '
                    f'{"DANAS!" if dl == 0 else f"za {dl} dana"}'
                )

        # Ugovor ističe
        if c.status == 'active':
            dl = (c.end_date - today).days
            if dl in (7, 3, 1):
                alerts.append(
                    f'📅 Ugovor ističe: {name} ({company_name})\n'
                    f'   Kraj: {c.end_date} — za {dl} dana'
                )

    if alerts:
        msg = '📋 *Sezonski radnici*\n\n' + '\n\n'.join(alerts)
        try:
            send_text(phone='+4915771998747', message=msg)
            log.info(f'Seasonal alarm: {len(alerts)} poruka poslano')
        except TypeError as e:
            log.error(f'WhatsApp seasonal failed: {e}')

    return {'alerts': len(alerts), 'checked': contracts.count()}
