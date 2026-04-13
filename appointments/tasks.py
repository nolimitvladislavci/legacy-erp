"""
Celery tasks for appointment reminders and status notifications.
"""
import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name="appointments.tasks.send_appointment_reminders")
def send_appointment_reminders():
    """Send email + WhatsApp reminders for appointments tomorrow."""
    from appointments.models import Appointment

    tomorrow_start = timezone.now().replace(hour=0, minute=0, second=0) + timedelta(days=1)
    tomorrow_end = tomorrow_start + timedelta(days=1)

    upcoming = Appointment.objects.filter(
        start_time__gte=tomorrow_start,
        start_time__lt=tomorrow_end,
        status__in=["scheduled", "confirmed"],
    ).select_related("client", "service", "resource")

    sent_email = 0
    sent_wa = 0

    for appt in upcoming:
        # Email reminder
        if not appt.email_reminder_sent and appt.client and appt.client.email:
            try:
                _send_reminder_email(appt)
                appt.email_reminder_sent = True
                sent_email += 1
            except Exception as e:
                logger.warning(f"Email reminder failed for #{appt.id}: {e}")

        # WhatsApp reminder
        wa_number = appt.whatsapp_number or (appt.client.phone if appt.client else "")
        if not appt.whatsapp_reminder_sent and wa_number:
            try:
                _send_reminder_whatsapp(appt, wa_number)
                appt.whatsapp_reminder_sent = True
                sent_wa += 1
            except Exception as e:
                logger.warning(f"WhatsApp reminder failed for #{appt.id}: {e}")

        if appt.email_reminder_sent or appt.whatsapp_reminder_sent:
            appt.reminder_sent_at = timezone.now()
            appt.save(update_fields=[
                "email_reminder_sent", "whatsapp_reminder_sent", "reminder_sent_at"
            ])

    logger.info(f"Reminders: {sent_email} email, {sent_wa} WA (of {upcoming.count()} appts)")
    return {"email": sent_email, "whatsapp": sent_wa, "total": upcoming.count()}


def _send_reminder_email(appt):
    from django.conf import settings

    from core.email_tasks import send_email_task

    dt = appt.start_time.strftime("%d.%m.%Y u %H:%M")
    service_name = appt.service.name if appt.service else appt.title
    duration = int(appt.service.duration.total_seconds() // 60) if appt.service else ""

    subject = f"Podsjetnik: {service_name} sutra"
    body = (
        f"Posdtovani/a {appt.client.name},\n\n"
        f"Podsjecdamo Vas na Vas termin sutra:\n\n"
        f"  Usluga:  {service_name}\n"
        f"  Termin:  {dt}\n"
    )
    if duration:
        body += f"  Trajanje: {duration} min\n"
    if appt.total_price:
        body += f"  Cijena:  {appt.total_price} EUR\n"
    body += "\nAko trebate otkazati, kontaktirajte nas sto prije.\n\nHvala!\n"

    send_email_task.delay(
        subject, body,
        getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@fina-connect.hr"),
        [appt.client.email],
    )


def _send_reminder_whatsapp(appt, phone):
    from core.whatsapp_tasks import send_whatsapp_text_task

    dt = appt.start_time.strftime("%d.%m.%Y u %H:%M")
    service_name = appt.service.name if appt.service else appt.title

    msg = (
        f"Podsjetnik na termin sutra\n\n"
        f"*{service_name}*\n"
        f"{dt}\n"
    )
    if appt.total_price:
        msg += f"{appt.total_price} EUR\n"
    msg += "\nAko trebate otkazati, javite nam se."

    send_whatsapp_text_task.delay(phone, msg)


@shared_task(name="appointments.notify_status_change")
def notify_appointment_status_change(appointment_id, new_status):
    """Notify client when appointment status changes."""
    from appointments.models import Appointment

    try:
        appt = Appointment.objects.select_related("client", "service").get(id=appointment_id)
    except Appointment.DoesNotExist:
        return

    if not appt.client:
        return

    service_name = appt.service.name if appt.service else appt.title
    dt = appt.start_time.strftime("%d.%m.%Y u %H:%M")

    STATUS_HR = {
        "confirmed": "Potvrdjen",
        "cancelled": "Otkazan",
        "completed": "Zavrsen",
        "no_show":   "Nije se pojavio",
    }
    label = STATUS_HR.get(new_status, new_status)

    # Email
    if appt.client.email:
        from django.conf import settings

        from core.email_tasks import send_email_task

        subject = f"Termin {label.lower()}: {service_name}"
        body = (
            f"Postovani/a {appt.client.name},\n\n"
            f"Status Vaseg termina je promijenjen:\n\n"
            f"  Usluga: {service_name}\n"
            f"  Termin: {dt}\n"
            f"  Novi status: {label}\n\n"
        )
        if new_status == "confirmed":
            body += "Veselimo se Vasem dolasku!\n"
        elif new_status == "cancelled":
            body += "Ako zelite zakazati novi termin, kontaktirajte nas.\n"
        body += "\nS postovanjem,\nVas tim\n"

        try:
            send_email_task.delay(
                subject, body,
                getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@fina-connect.hr"),
                [appt.client.email],
            )
        except (AttributeError, TypeError) as e:
            logger.warning(f"Status email failed: {e}")

    # WhatsApp
    wa = appt.whatsapp_number or (appt.client.phone if appt.client else "")
    if wa:
        from core.whatsapp_tasks import send_whatsapp_text_task
        try:
            # Bakery-specific messages
            is_bakery = appt.service and getattr(appt.service, 'branch_type', '') == 'bakery'
            if is_bakery:
                bakery_msgs = {
                    'confirmed': 'Termin POTVRDEN! ' + service_name + ' — ' + dt + '. Donijeti namirnice na vrijeme!',
                    'completed': 'Vase pecenje je GOTOVO! ' + service_name + ' — Dodite pokupiti dok je toplo!',
                    'cancelled': 'Termin otkazan: ' + service_name + ' ' + dt + '. Za novi termin javite se.',
                }
                msg = bakery_msgs.get(new_status, 'Status: ' + label + ' — ' + service_name)
            else:
                msg = "Termin " + label.lower() + "\n" + service_name + "\n" + dt
            send_whatsapp_text_task.delay(wa, msg)
        except (AttributeError, TypeError) as e:
            logger.warning(f"Status WA failed: {e}")

    return {"appointment_id": appointment_id, "status": new_status}
