"""
companies/tasks.py — Celery tasks za data quality.
"""
import logging
from celery import shared_task

logger = logging.getLogger('companies.tasks')


@shared_task(name='companies.async_fill_company_address', bind=True, max_retries=1, soft_time_limit=30)
def async_fill_company_address(self, company_pk):
    """Auto-fill prazne adrese iz partnera ili VIES-a."""
    from companies.models import Company
    from partners.models import Partner
    from django.db.models import Q

    try:
        company = Company.objects.get(pk=company_pk)
    except Company.DoesNotExist:
        return

    if company.address and company.city:
        return  # Već popunjeno

    oib = (company.oib or '').strip()
    if not oib or len(oib) != 11:
        return

    # 1. Iz partnera
    partner = Partner.objects.filter(oib=oib).exclude(
        Q(address__isnull=True) | Q(address='')
    ).order_by('-updated_at').first()

    if partner:
        updated = []
        if not company.address and partner.address:
            company.address = partner.address
            updated.append('address')
        if not company.city and partner.city:
            company.city = partner.city
            updated.append('city')
        if not company.zip_code and partner.zip_code:
            company.zip_code = partner.zip_code
            updated.append('zip_code')
        if updated:
            updated.append('updated_at')
            company.save(update_fields=updated)
            logger.info('Auto-fill %s from partner: %s', company.name, ', '.join(updated))
        return

    # 2. VIES lookup
    try:
        from core.business_lookup import lookup_business
        result = lookup_business(oib, 'HR')
        if result.found and result.address:
            updated = []
            if not company.address:
                company.address = result.address
                updated.append('address')
            if not company.city and result.city:
                company.city = result.city
                updated.append('city')
            if not company.zip_code and result.zip_code:
                company.zip_code = result.zip_code
                updated.append('zip_code')
            if updated:
                updated.append('updated_at')
                company.save(update_fields=updated)
                logger.info('Auto-fill %s from VIES: %s', company.name, ', '.join(updated))
    except Exception as e:
        logger.warning('VIES auto-fill failed for %s: %s', company.name, e)


@shared_task(name='companies.nightly_data_quality', bind=True, max_retries=0, soft_time_limit=120)
def nightly_data_quality(self):
    """Noćna provjera kvalitete podataka — popuni rupe + alertiraj."""
    from django.core.management import call_command
    from io import StringIO

    # 1. Pokušaj popuniti iz partnera
    out = StringIO()
    call_command('fill_company_addresses', stdout=out)
    fill_result = out.getvalue()

    # 2. Izračunaj score
    from companies.data_quality import check_data_quality_report
    report = check_data_quality_report()

    # 3. Alert ako ima rupa
    if report['no_address'] > 0:
        from core.notify import notify
        notify('INFO', (
            f"📊 *Data Quality Report*\n\n"
            f"Score: *{report['quality_score']}%*\n"
            f"Ukupno firmi: {report['total']}\n"
            f"Bez adrese: {report['no_address']}\n"
            f"Bez grada: {report['no_city']}\n"
            f"Bez ZIP: {report['no_zip']}\n"
            f"Bez emaila: {report['no_email']}\n\n"
            f"Auto-fill pokrenuo."
        ))

    return report
