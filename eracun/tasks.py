

from celery import shared_task
import logging

logger = logging.getLogger('eracun.tasks')


@shared_task(bind=True, soft_time_limit=120)
def fetch_posrednik_inbox(self):
    """Dohvati nove e-racune od posrednika za sve konfigurirane firme."""
    from companies.models import Company
    from eracun.services.posrednik_service import PosrednikService
    from eracun.models import ERacun
    from django.utils import timezone
    from datetime import timedelta

    fetched = 0
    errors = 0
    since = timezone.now() - timedelta(days=7)

    for company in Company.objects.all():
        if not PosrednikService.is_configured(company):
            continue

        try:
            result = PosrednikService.fetch_inbox(company, since=since)
            if result.get('ok') and result.get('invoices'):
                for inv_data in result['invoices']:
                    inv_id = inv_data.get('id', inv_data.get('invoiceId', ''))
                    if not ERacun.objects.filter(fina_uuid=inv_id).exists():
                        ERacun.objects.create(
                            company=company,
                            doc_type='380',
                            invoice_number=inv_data.get('invoiceNumber', inv_id),
                            issuer_name=inv_data.get('senderName', ''),
                            issuer_oib=inv_data.get('senderOib', ''),
                            recipient_name=company.name,
                            recipient_oib=company.oib,
                            total=inv_data.get('totalAmount', 0),
                            issue_date=timezone.now().date(),
                            status='accepted',
                            fina_uuid=inv_id,
                            note='Primljeno od posrednika',
                        )
                        fetched += 1
        except Exception as e:
            errors += 1
            logger.warning('Inbox fetch error za %s: %s', company.name, e)

    logger.info('fetch_posrednik_inbox: fetched=%d, errors=%d', fetched, errors)
    return {'fetched': fetched, 'errors': errors}


@shared_task(bind=True, soft_time_limit=60)
def retry_unsent_eracuni(self):
    """Retry slanja e-racuna koji su ostali u statusu error/draft."""
    from eracun.models import ERacun
    from eracun.services.posrednik_service import PosrednikService
    from django.utils import timezone
    from datetime import timedelta

    cutoff = timezone.now() - timedelta(hours=48)
    unsent = ERacun.objects.filter(
        status__in=['error', 'draft'],
        source_receipt__isnull=False,
        created_at__gte=cutoff,
    ).select_related('company')

    sent = 0
    for eracun in unsent[:20]:
        if PosrednikService.is_configured(eracun.company):
            result = PosrednikService.send(eracun)
            if result.get('ok'):
                sent += 1

    return {'retried': unsent.count(), 'sent': sent}
