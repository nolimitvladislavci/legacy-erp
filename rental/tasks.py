"""
rental/tasks.py — Celery taskovi za Rental modul

1. daily_landlord_brief — svako jutro 08:00
2. check_evisitor_pending — svakih 6h, upozorenje za neregistrirane goste
3. annual_limit_check — tjedno, 40k prag provjera
4. gdpr_cleanup_guest_docs — dnevno, briši dokumente 24h nakon check-outa
"""
import logging
from celery import shared_task
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=1, soft_time_limit=120)
def daily_landlord_brief(self):
    """Svako jutro 08:00 — AI sažetak za sve iznajmljivače."""
    from rental.ai_assistant import generate_landlord_daily_brief
    from rental.models import Property
    from companies.models import Company

    company_ids = Property.objects.filter(
        is_active=True,
    ).values_list('company_id', flat=True).distinct()

    sent = 0
    for cid in company_ids:
        try:
            company = Company.objects.get(pk=cid)
            brief = generate_landlord_daily_brief(company)
            # WhatsApp
            try:
                from core.whatsapp import send_text
                phone = getattr(company, 'phone', '')
                if phone:
                    send_text(phone, brief)
                    sent += 1
            except Exception:
                pass
            logger.info('Landlord brief sent for %s', company.name)
        except ObjectDoesNotExist as e:
            logger.warning('Landlord brief failed for company %s: %s', cid, e)

    return {'companies': len(company_ids), 'sent': sent}


@shared_task(bind=True, soft_time_limit=60)
def check_evisitor_pending(self):
    """Svakih 6h — upozorenje za bookinge bez eVisitor prijave (24h rok)."""
    from rental.models import Booking
    from datetime import timedelta

    cutoff = timezone.now() - timedelta(hours=20)

    pending = Booking.objects.filter(
        status='checked_in',
        actual_check_in__lte=cutoff,
        guests__evisitor_synced=False,
    ).distinct().select_related('rental_property__company')

    count = 0
    for booking in pending:
        hours_since = (timezone.now() - booking.actual_check_in).total_seconds() / 3600
        logger.warning(
            'eVisitor PENDING: %s at %s — %.0fh since check-in',
            booking.guest_name, booking.rental_property.name, hours_since,
        )
        count += 1

    return {'pending': count}


@shared_task(bind=True, soft_time_limit=60)
def annual_limit_check(self):
    """Tjedno — provjeri blizinu 40k paušalnog praga."""
    from rental.ai_assistant import check_annual_limit_warning
    from rental.models import Property
    from companies.models import Company

    company_ids = Property.objects.filter(
        is_active=True,
    ).values_list('company_id', flat=True).distinct()

    alerts = 0
    for cid in company_ids:
        try:
            company = Company.objects.get(pk=cid)
            result = check_annual_limit_warning(company)
            if result.get('warning_level') in ('CRITICAL', 'HIGH'):
                logger.warning('40K LIMIT: %s — %s', company.name, result['message'])
                try:
                    from core.whatsapp import send_text
                    phone = getattr(company, 'phone', '')
                    if phone:
                        send_text(phone, result['message'])
                        alerts += 1
                except Exception:
                    pass
        except ObjectDoesNotExist as e:
            logger.warning('Limit check failed for %s: %s', cid, e)

    return {'checked': len(company_ids), 'alerts': alerts}


@shared_task(bind=True, soft_time_limit=120)
def gdpr_cleanup_guest_docs(self):
    """Dnevno 04:00 — briši slike dokumenata 24h nakon check-outa (GDPR)."""
    from rental.models import GuestDocument

    now = timezone.now()
    expired = GuestDocument.objects.filter(
        delete_after__isnull=False,
        delete_after__lte=now,
    )

    count = 0
    for doc in expired:
        try:
            if doc.image:
                doc.image.delete(save=False)
            doc.ocr_raw = {}
            doc.save(update_fields=['ocr_raw'])
            count += 1
        except Exception as e:
            logger.warning('GDPR cleanup failed for doc %s: %s', doc.pk, e)

    if count:
        logger.info('GDPR cleanup: %d guest documents purged', count)
    return {'purged': count}
