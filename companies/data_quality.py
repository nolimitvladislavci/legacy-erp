"""
companies/data_quality.py — Data Quality Guard

1. post_save signal: kad se Company spremi s praznom adresom, pokušaj auto-fill
2. Nightly patrol task: provjeri sve firme, popuni rupe, alertira
"""
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger('companies.data_quality')

CRITICAL_FIELDS = ['address', 'city', 'zip_code']


@receiver(post_save, sender='companies.Company')
def auto_fill_company_data(sender, instance, created, **kwargs):
    """
    Kad se Company spremi bez adrese — pokušaj auto-fill iz partnera ili VIES.
    Radi async (Celery) da ne blokira save.
    """
    if instance.is_vaulted:
        return

    missing = [f for f in CRITICAL_FIELDS if not getattr(instance, f, '')]
    if not missing:
        return

    oib = (instance.oib or '').strip()
    if not oib or len(oib) != 11 or not oib.isdigit():
        return

    # Async fill da ne blokira request
    try:
        from companies.tasks import async_fill_company_address
        async_fill_company_address.delay(str(instance.pk))
    except ImportError as e:
        logger.warning('auto_fill_company_data dispatch failed: %s', e)


def check_data_quality_report():
    """
    Nightly patrol — vraća dict s rupama u podacima.
    Poziva se iz Celery beat taska.
    """
    from companies.models import Company
    from django.db.models import Q

    active = Company.objects.filter(is_vaulted=False).exclude(
        Q(oib='') | Q(oib__isnull=True) |
        Q(oib__startswith='SYN') | Q(oib__startswith='999') |
        Q(oib__startswith='888')
    )

    total = active.count()
    no_address = active.filter(Q(address__isnull=True) | Q(address='')).count()
    no_city = active.filter(Q(city__isnull=True) | Q(city='')).count()
    no_zip = active.filter(Q(zip_code__isnull=True) | Q(zip_code='')).count()
    no_email = active.filter(Q(email__isnull=True) | Q(email='')).count()

    score = round((1 - (no_address + no_city + no_zip) / (total * 3)) * 100, 1) if total else 0

    return {
        'total': total,
        'no_address': no_address,
        'no_city': no_city,
        'no_zip': no_zip,
        'no_email': no_email,
        'quality_score': score,
    }
