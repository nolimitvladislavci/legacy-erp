"""
Celery tasks for Stolarija module — service reminders and warranty checks.
"""
import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger('stolarija')


@shared_task(bind=True, max_retries=2, retry_backoff=True)
def check_service_reminders(self):
    """
    Daily task: find upcoming ServiceVisits and send reminders.
    - 30 days before: first reminder
    - 7 days before: second reminder
    - On the day: final reminder
    """
    from stolarija.models import ServiceVisit, WindowWarranty
    from core.whatsapp_tasks import send_whatsapp_text_task

    today = timezone.now().date()
    reminder_days = [30, 7, 0]
    sent = 0

    for days_ahead in reminder_days:
        target_date = today + timedelta(days=days_ahead)
        visits = ServiceVisit.objects.filter(
            scheduled=target_date,
            completed__isnull=True,
            ai_reminder_sent=False,
        ).select_related('warranty__session__company')

        for visit in visits:
            warranty = visit.warranty
            company = warranty.session.company if warranty.session else None
            if not company:
                continue

            if days_ahead == 0:
                msg = (f"🔧 DANAS: Servisni pregled stolarije\n"
                       f"Garancija: {warranty.warranty_number}\n"
                       f"Adresa: {warranty.session.address if warranty.session else '—'}")
            elif days_ahead == 7:
                msg = (f"📅 Za 7 dana: servisni pregled stolarije\n"
                       f"Garancija: {warranty.warranty_number}\n"
                       f"Datum: {target_date.strftime('%d.%m.%Y')}")
            else:
                msg = (f"ℹ️ Za 30 dana: servisni pregled stolarije\n"
                       f"Garancija: {warranty.warranty_number}\n"
                       f"Datum: {target_date.strftime('%d.%m.%Y')}")

            # Send to company admin phone if available
            try:
                admin_phone = company.phone or ''
                if admin_phone:
                    send_whatsapp_text_task.delay(admin_phone, msg)
                    visit.ai_reminder_sent = True
                    visit.save(update_fields=['ai_reminder_sent'])
                    sent += 1
            except Exception as e:
                logger.warning('Service reminder failed for visit %s: %s', visit.pk, e)

    logger.info('check_service_reminders: sent %d reminders', sent)
    return {'sent': sent}


@shared_task(bind=True, max_retries=1)
def check_expired_warranties(self):
    """
    Weekly task: flag warranties past their validity period.
    Creates a final service visit if none exists for the last year.
    """
    from stolarija.models import WindowWarranty, ServiceVisit

    today = timezone.now().date()
    created = 0

    warranties = WindowWarranty.objects.filter(
        handover_date__isnull=False,
    ).select_related('session')

    for w in warranties:
        expiry = w.handover_date.replace(year=w.handover_date.year + w.valid_years)
        if expiry < today:
            continue  # Already expired

        # Check if annual service exists for current year
        year_start = today.replace(month=1, day=1)
        year_end = today.replace(month=12, day=31)
        has_visit = w.service_visits.filter(
            scheduled__gte=year_start,
            scheduled__lte=year_end,
        ).exists()

        if not has_visit and w.handover_date:
            # Schedule annual service on handover anniversary
            anniversary = w.handover_date.replace(year=today.year)
            if anniversary < today:
                anniversary = anniversary.replace(year=today.year + 1)

            ServiceVisit.objects.create(
                warranty=w,
                scheduled=anniversary,
            )
            created += 1

    logger.info('check_expired_warranties: created %d service visits', created)
    return {'created': created}
