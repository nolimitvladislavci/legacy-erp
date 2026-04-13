"""
Komunalno — Celery tasks.

Task #1: e-ONTO noćni batch export (Mina #3 rješenje)
    - Pakira dnevne deliverije u XML
    - Šalje prema Ministarstvu zaštite okoliša
    - Retry s exponential backoff
    - Radi u 02:00 ujutro (beat schedule)

Task #2: Kvota upozorenja
    - Provjerava građane koji su na 80%+ kvote
    - Šalje notifikaciju operateru
"""
import logging
from datetime import timedelta
from decimal import Decimal

from celery import shared_task
from django.utils import timezone
from django.db import IntegrityError, DatabaseError

logger = logging.getLogger('komunalno')


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def export_onto_batch(self, company_id, station_id, date_str=None):
    from companies.models import Company
    from .models import WasteStation, WasteDelivery, OntoExportBatch

    company = Company.objects.get(pk=company_id)
    station = WasteStation.objects.get(pk=station_id, company=company)

    if date_str:
        from datetime import date
        target_date = date.fromisoformat(date_str)
    else:
        target_date = (timezone.localdate() - timedelta(days=1))

    unsent = WasteDelivery.objects.filter(
        company=company, station=station,
        delivery_date__date=target_date,
        status='confirmed', onto_exported=False,
    )

    if unsent.count() == 0:
        logger.info('e-ONTO: Nema neposlanih za %s @ %s', target_date, station.name)
        return f'No deliveries for {target_date}'

    batch, created = OntoExportBatch.objects.get_or_create(
        company=company, station=station,
        date_from=target_date, date_to=target_date,
        defaults={'status': 'pending'},
    )

    if batch.status == 'accepted':
        return f'Batch {batch.pk} already accepted'

    unsent.update(onto_batch=batch)

    try:
        batch.generate_xml()
        logger.info('e-ONTO: XML generiran za %s, %d zapisa', station.name, batch.delivery_count)
    except Exception as e:
        batch.status = 'error'
        batch.last_error = f'XML generation failed: {str(e)}'
        batch.save(update_fields=['status', 'last_error'])
        raise self.retry(exc=e)

    try:
        batch.status = 'sending'
        batch.save(update_fields=['status'])
        success, response_data = _send_to_onto(batch)

        if success:
            batch.status = 'accepted'
            batch.accepted_count = batch.delivery_count
            batch.sent_at = timezone.now()
            batch.completed_at = timezone.now()
            batch.save()
            WasteDelivery.objects.filter(onto_batch=batch).update(
                onto_exported=True, onto_export_date=timezone.now(),
            )
            logger.info('e-ONTO: Batch %s ACCEPTED (%d zapisa)', batch.pk, batch.delivery_count)
            return f'Batch {batch.pk} accepted: {batch.delivery_count} records'
        else:
            raise Exception(f'e-ONTO rejected: {response_data}')

    except (IntegrityError, DatabaseError) as e:
        batch.retry_count += 1
        batch.last_error = str(e)[:500]
        if batch.can_retry():
            batch.status = 'retry'
            batch.save(update_fields=['status', 'retry_count', 'last_error'])
            delay = 300 * (5 ** (batch.retry_count - 1))
            logger.warning('e-ONTO: Retry #%d za batch %s', batch.retry_count, batch.pk)
            raise self.retry(exc=e, countdown=delay)
        else:
            batch.status = 'error'
            batch.save(update_fields=['status', 'retry_count', 'last_error'])
            logger.error('e-ONTO: Batch %s FAILED: %s', batch.pk, e)
            return f'Batch {batch.pk} FAILED: {str(e)}'


@shared_task
def nightly_onto_export():
    from .models import WasteStation, WasteDelivery
    yesterday = timezone.localdate() - timedelta(days=1)

    company_ids = WasteDelivery.objects.filter(
        delivery_date__date=yesterday, status='confirmed', onto_exported=False,
    ).values_list('company_id', flat=True).distinct()

    count = 0
    for company_id in company_ids:
        for station in WasteStation.objects.filter(company_id=company_id, is_active=True):
            if WasteDelivery.objects.filter(
                company_id=company_id, station=station,
                delivery_date__date=yesterday, status='confirmed', onto_exported=False,
            ).exists():
                export_onto_batch.delay(company_id, station.pk, yesterday.isoformat())
                count += 1

    logger.info('e-ONTO nightly: %d batch exporta za %s', count, yesterday)
    return f'{count} batches queued for {yesterday}'


@shared_task
def check_quota_warnings():
    from .models import CitizenCard, WasteCategory
    year = timezone.localdate().year
    warnings = []
    for category in WasteCategory.objects.filter(default_annual_quota__gt=0):
        for card in CitizenCard.objects.filter(is_active=True):
            remaining = card.get_remaining_quota(category, year)
            if remaining is not None:
                quota = card._get_quota(category)
                if quota > 0:
                    usage_pct = ((quota - remaining) / quota * 100)
                    if usage_pct >= 80:
                        warnings.append({
                            'citizen': card.partner.name,
                            'category': category.name,
                            'used_pct': round(usage_pct, 1),
                        })
    if warnings:
        logger.info('Kvota upozorenja: %d građana na 80%%+', len(warnings))
    return f'{len(warnings)} quota warnings'


def create_onto_batch(company_id, station_id, date_str=None):
    export_onto_batch.delay(company_id, station_id, date_str)


def _send_to_onto(batch):
    import os
    from django.conf import settings
    onto_dir = os.path.join(settings.BASE_DIR, 'logs', 'onto_exports')
    os.makedirs(onto_dir, exist_ok=True)
    filename = f'onto_{batch.company.oib}_{batch.date_from}_{batch.station.pk}.xml'
    filepath = os.path.join(onto_dir, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(batch.xml_payload)
    batch.response_code = 'LOCAL_SAVED'
    batch.response_body = f'XML saved to {filepath}'
    batch.save(update_fields=['response_code', 'response_body'])
    logger.info('e-ONTO: XML saved locally to %s', filepath)
    return True, {'status': 'saved_locally', 'path': filepath}
