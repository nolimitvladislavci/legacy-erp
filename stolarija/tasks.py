"""
Celery tasks for Stolarija module.
- Service reminders (daily)
- Warranty checks (weekly)
- Risk profile recalculation (weekly)
- AI message processing (every 5 min)
"""
import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone
from django.db import IntegrityError, DatabaseError

logger = logging.getLogger('stolarija')


@shared_task(bind=True, max_retries=2, retry_backoff=True)
def check_service_reminders(self):
    """
    Daily: find upcoming ServiceVisits and send WhatsApp reminders.
    30 days before, 7 days before, on the day.
    """
    from stolarija.models import ServiceVisit
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
    Weekly: ensure annual service visits exist for active warranties.
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
            continue

        year_start = today.replace(month=1, day=1)
        year_end = today.replace(month=12, day=31)
        has_visit = w.service_visits.filter(
            scheduled__gte=year_start,
            scheduled__lte=year_end,
        ).exists()

        if not has_visit and w.handover_date:
            anniversary = w.handover_date.replace(year=today.year)
            if anniversary < today:
                anniversary = anniversary.replace(year=today.year + 1)

            ServiceVisit.objects.create(warranty=w, scheduled=anniversary)
            created += 1

    logger.info('check_expired_warranties: created %d service visits', created)
    return {'created': created}


@shared_task(bind=True, max_retries=1)
def recalculate_risk_profiles(self):
    """Weekly: recalculate risk scores for all warranties."""
    from stolarija.risk_engine import recalculate_all_risks
    count = recalculate_all_risks()
    return {'updated': count}


@shared_task(bind=True, max_retries=2, retry_backoff=True)
def process_pending_messages(self):
    """
    Every 5 min: process inbound ServiceMessages that haven't been analyzed.
    """
    from stolarija.models import ServiceMessage
    from stolarija.ai_service_agent import process_inbound_message

    pending = ServiceMessage.objects.filter(
        direction='inbound',
        status='received',
    ).order_by('created_at')[:10]  # Batch of 10

    processed = 0
    for msg in pending:
        try:
            process_inbound_message(msg)
            processed += 1
        except Exception as e:
            logger.error('Failed to process message %s: %s', msg.pk, e)

    if processed:
        logger.info('process_pending_messages: processed %d messages', processed)
    return {'processed': processed}


@shared_task(bind=True, max_retries=2, retry_backoff=True)
def send_approved_messages(self):
    """
    Every 5 min: send messages that have been approved by humans.
    """
    from stolarija.models import ServiceMessage
    from core.whatsapp_tasks import send_whatsapp_text_task
    from django.core.mail import send_mail

    approved = ServiceMessage.objects.filter(
        direction='outbound',
        status='approved',
    ).order_by('approved_at')[:10]

    sent = 0
    for msg in approved:
        body = msg.final_body
        if not body:
            continue

        try:
            if msg.channel == 'whatsapp' and msg.sender_email:
                # sender_email reused as phone for WhatsApp
                send_whatsapp_text_task.delay(msg.sender_email, body)
                msg.status = 'sent'
                msg.sent_at = timezone.now()
                msg.save(update_fields=['status', 'sent_at'])
                sent += 1

            elif msg.channel == 'email' and msg.sender_email:
                send_mail(
                    subject=msg.subject or 'Servis stolarije — LIMIT Connect',
                    message=body,
                    from_email=getattr(
                        settings, 'DEFAULT_FROM_EMAIL',
                        'service@limit-connect.com'
                    ),
                    recipient_list=[msg.sender_email],
                    fail_silently=False,
                )
                msg.status = 'sent'
                msg.sent_at = timezone.now()
                msg.save(update_fields=['status', 'sent_at'])
                sent += 1

            # Audit
            try:
                from core.models import BookingSignature
                BookingSignature.objects.create(
                    action='send',
                    target_type='ServiceMessage',
                    target_id=str(msg.pk),
                    target_repr=f'AI message sent to {msg.sender_email}',
                    user=msg.approved_by,
                    changes={'channel': msg.channel, 'sentiment': msg.ai_sentiment},
                )
            except (IntegrityError, DatabaseError):
                pass

        except (IntegrityError, DatabaseError) as e:
            logger.error('Failed to send message %s: %s', msg.pk, e)

    if sent:
        logger.info('send_approved_messages: sent %d messages', sent)
    return {'sent': sent}
