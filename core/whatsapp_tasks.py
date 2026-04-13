"""
Celery tasks for WhatsApp messaging via WAHA gateway.
All tasks are idempotent with graceful retry on gateway errors.
"""
import logging
from celery import shared_task
from django.conf import settings
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

logger = logging.getLogger('whatsapp')


@shared_task(bind=True, max_retries=3, retry_backoff=True)
def send_whatsapp_text_task(self, phone, message):
    """Generic WhatsApp text send with retry."""
    from core.whatsapp import send_text

    result = send_text(phone, message)
    if not result['success'] and result['error'] in ('Gateway unreachable', 'Gateway timeout'):
        raise self.retry(exc=Exception(result['error']))
    return result


@shared_task(bind=True, max_retries=3, retry_backoff=True)
def send_appointment_confirmation_whatsapp(self, appointment_id):
    """Send WhatsApp booking confirmation to client."""
    from appointments.models import Appointment
    from core.whatsapp import send_text

    try:
        appt = Appointment.objects.select_related('service').get(pk=appointment_id)
    except Appointment.DoesNotExist:
        logger.warning('Appointment %s not found for WhatsApp confirmation', appointment_id)
        return

    if not appt.whatsapp_number:
        return

    dt_fmt = appt.start_time.strftime('%d.%m.%Y u %H:%M')
    service_name = appt.service.name if appt.service else appt.title
    msg = (
        f"Potvr\u0111eno! \u2705\n\n"
        f"Usluga: {service_name}\n"
        f"Termin: {dt_fmt}\n"
    )
    if appt.total_price:
        msg += f"Cijena: {appt.total_price} EUR\n"
    msg += f"\nHvala na povjerenju!"

    result = send_text(appt.whatsapp_number, msg)
    if not result['success'] and result['error'] in ('Gateway unreachable', 'Gateway timeout'):
        raise self.retry(exc=Exception(result['error']))
    return result


@shared_task(bind=True, max_retries=3, retry_backoff=True)
def send_appointment_reminder_whatsapp(self, appointment_id):
    """Send WhatsApp reminder and mark whatsapp_reminder_sent=True on success."""
    from appointments.models import Appointment
    from core.whatsapp import send_text

    try:
        appt = Appointment.objects.select_related('service', 'client').get(pk=appointment_id)
    except Appointment.DoesNotExist:
        logger.warning('Appointment %s not found for WhatsApp reminder', appointment_id)
        return

    if not appt.whatsapp_number or appt.whatsapp_reminder_sent:
        return

    dt_fmt = appt.start_time.strftime('%d.%m.%Y u %H:%M')
    service_name = appt.service.name if appt.service else appt.title
    client_name = appt.client.name if appt.client else 'klijent'
    msg = (
        f"Podsjetnik \u23f0\n\n"
        f"Po\u0161tovani/a {client_name},\n"
        f"podsjje\u0107amo Vas na termin:\n\n"
        f"Usluga: {service_name}\n"
        f"Termin: {dt_fmt}\n"
    )
    if appt.location:
        msg += f"Lokacija: {appt.location}\n"
    msg += f"\nVidimo se!"

    result = send_text(appt.whatsapp_number, msg)
    if result['success']:
        appt.whatsapp_reminder_sent = True
        appt.save(update_fields=['whatsapp_reminder_sent'])
    elif result['error'] in ('Gateway unreachable', 'Gateway timeout'):
        raise self.retry(exc=Exception(result['error']))
    return result


@shared_task(bind=True, max_retries=3, retry_backoff=True)
def send_intervention_assignment_whatsapp(self, intervention_id, worker_user_id):
    """Send WhatsApp notification to assigned worker about new intervention."""
    from interventions.models import HitnaIntervencija
    from django.contrib.auth.models import User
    from core.whatsapp import send_text

    try:
        interv = HitnaIntervencija.objects.unscoped().get(pk=intervention_id)
    except HitnaIntervencija.DoesNotExist:
        logger.warning('Intervention %s not found for WhatsApp', intervention_id)
        return

    try:
        worker = User.objects.select_related('profile').get(pk=worker_user_id)
    except User.DoesNotExist:
        logger.warning('Worker user %s not found for WhatsApp', worker_user_id)
        return

    phone = getattr(worker, 'profile', None) and worker.profile.phone
    if not phone:
        logger.info('Worker %s has no phone number', worker.username)
        return

    category = interv.get_category_display()
    msg = (
        f"\u26a0\ufe0f Hitna intervencija!\n\n"
        f"{interv.title}\n"
        f"Kategorija: {category}\n"
        f"Adresa: {interv.address}\n"
        f"Klijent: {interv.client_name}\n"
        f"Tel: {interv.client_phone}\n"
    )
    if interv.description:
        msg += f"\nOpis: {interv.description[:200]}"

    result = send_text(phone, msg)

    # Mark notification sent on intervention
    if result['success']:
        try:
            interv.whatsapp_notification_sent = True
            interv.save(update_fields=['whatsapp_notification_sent'])
        except Exception:
            pass  # Field may not exist yet during migration

    if not result['success'] and result['error'] in ('Gateway unreachable', 'Gateway timeout'):
        raise self.retry(exc=Exception(result['error']))
    return result


@shared_task
def check_whatsapp_gateway_health():
    """Periodic health check — logs error if gateway is unhealthy."""
    from core.whatsapp import is_gateway_healthy

    if not getattr(settings, 'WAHA_ENABLED', False):
        return {'status': 'disabled'}

    healthy = is_gateway_healthy()
    if healthy:
        logger.info('WhatsApp gateway healthy')
        return {'status': 'healthy'}
    else:
        logger.error('WhatsApp gateway UNHEALTHY — messages will not be delivered')
        return {'status': 'unhealthy'}
