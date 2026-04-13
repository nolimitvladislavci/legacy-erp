"""
Appointments business logic — pure functions, no request/response.

Core functions: slot availability, booking creation, reminders.
"""
import logging
from datetime import date, datetime, timedelta

from django.db import transaction
from django.utils import timezone

from core.exceptions import BookingConflictError
from core.exceptions import ValidationError as BizValidationError

logger = logging.getLogger(__name__)


# ── Slot Availability ───────────────────────────────────────

def get_available_slots(service: "BookingService", target_date: date) -> dict[str, list[str]]:
    """
    Calculate available time slots for a service on a given date.
    Returns dict with 'available' and 'unavailable' slot lists.
    """
    from .models import Appointment, BookingResource, WorkingHours

    if target_date < datetime.now().date():
        return {"available": [], "unavailable": []}

    weekday = target_date.weekday()
    resources = BookingResource.objects.filter(
        resource_type=service.resource_type, is_active=True
    )
    service_duration = service.duration.total_seconds() / 60

    available_slots = set()
    unavailable_slots = set()

    for resource in resources:
        wh = WorkingHours.objects.filter(
            resource=resource, day_of_week=weekday, is_day_off=False
        ).first()
        if not wh:
            continue

        start_dt = datetime.combine(target_date, wh.start_time)
        end_dt = datetime.combine(target_date, wh.end_time)

        existing = list(Appointment.objects.filter(
            resource=resource,
            start_time__date=target_date,
            status__in=["scheduled", "confirmed"],
        ))

        current = start_dt
        while current + timedelta(minutes=service_duration) <= end_dt:
            slot_end = current + timedelta(minutes=service_duration)

            overlap = any(
                current < a.end_time.replace(tzinfo=None)
                and slot_end > a.start_time.replace(tzinfo=None)
                for a in existing
            )

            # Past slots today
            if target_date == datetime.now().date() and current.time() < datetime.now().time():
                overlap = True

            slot_str = current.strftime("%H:%M")
            if not overlap:
                available_slots.add(slot_str)
            else:
                unavailable_slots.add(slot_str)

            current += timedelta(minutes=service.slot_duration_minutes)

    avail = sorted(available_slots)
    unavail = sorted(unavailable_slots - available_slots)
    return {"available": avail, "unavailable": unavail}


def get_week_slots(service: "BookingService", start_date: date, days: int = 7) -> list[dict]:
    """Get available slots for a range of days."""
    result = []
    for i in range(days):
        d = start_date + timedelta(days=i)
        slots = get_available_slots(service, d)
        result.append({
            "date": d.isoformat(),
            "weekday": d.strftime("%A"),
            "available": slots["available"],
            "count": len(slots["available"]),
        })
    return result


# ── Booking Creation ────────────────────────────────────────

@transaction.atomic
def create_booking(service: "BookingService", target_date: date, time_str: str,
                   client_name: str, client_email: str,
                   client_phone: str = "", user: "User | None" = None,
                   company: "Company | None" = None, notes: str = "") -> dict:
    """
    Create a new appointment booking.
    Validates slot availability, creates/finds partner, creates appointment.
    Returns dict with booking details.
    """

    from .models import Appointment

    # Validate slot
    slots = get_available_slots(service, target_date)
    if time_str not in slots["available"]:
        raise BookingConflictError(f"Termin {time_str} nije dostupan za {target_date}.")

    # Parse times
    start_time = datetime.strptime(f"{target_date} {time_str}", "%Y-%m-%d %H:%M")
    duration_min = service.duration.total_seconds() / 60
    end_time = start_time + timedelta(minutes=duration_min)

    # Find available resource
    resource = _find_available_resource(service, target_date, start_time, end_time)
    if not resource:
        raise BookingConflictError("Nema dostupnog resursa za ovaj termin.")

    # Get or create partner
    partner = _get_or_create_partner(
        client_name, client_email, client_phone, company
    )

    # Create appointment
    appointment = Appointment.objects.create(
        service=service,
        resource=resource,
        client=partner,
        start_time=timezone.make_aware(start_time),
        end_time=timezone.make_aware(end_time),
        status="scheduled",
        description=notes,
        company=company,
        employee=user,
    )

    logger.info(
        "Booking created: appt=%d service=%s date=%s time=%s client=%s",
        appointment.pk, service.name, target_date, time_str, client_email,
    )

    return {
        "appointment_id": appointment.pk,
        "service": service.name,
        "date": target_date.isoformat(),
        "time": time_str,
        "duration": int(duration_min),
        "resource": resource.name,
        "client": client_name,
    }


# ── Appointment Status ──────────────────────────────────────

VALID_STATUS_TRANSITIONS = {
    "scheduled": ["confirmed", "cancelled", "no_show"],
    "confirmed": ["completed", "cancelled", "no_show"],
    "completed": [],
    "cancelled": ["scheduled"],
    "no_show": [],
}


def change_appointment_status(appointment: "Appointment", new_status: str, notify: bool = True) -> bool:
    """
    Change appointment status with validation.
    Optionally sends notification to client.
    """
    old = appointment.status
    valid = VALID_STATUS_TRANSITIONS.get(old, [])

    if new_status not in valid:
        raise BizValidationError(f"Nije moguć prijelaz {old} → {new_status}.")

    appointment.status = new_status
    appointment.save(update_fields=["status"])

    if notify and new_status in ("confirmed", "cancelled"):
        _send_status_notification(appointment, new_status)

    logger.info("Appointment %d: %s → %s", appointment.pk, old, new_status)
    return True


# ── Cancellation ────────────────────────────────────────────

def cancel_appointment(appointment: "Appointment", reason: str = "", notify: bool = True) -> bool:
    """Cancel an appointment with optional reason and notification."""
    if appointment.status in ("completed", "no_show"):
        raise BizValidationError("Završeni termini se ne mogu otkazati.")

    appointment.status = "cancelled"
    if reason:
        appointment.description = f"{appointment.description}\nOtkazano: {reason}".strip()
    appointment.save()

    if notify:
        _send_status_notification(appointment, "cancelled")

    logger.info("Appointment %d cancelled: %s", appointment.pk, reason)
    return True


# ── Internal Helpers ────────────────────────────────────────

def _find_available_resource(service: "BookingService", target_date: date, start_time, end_time) -> "BookingResource | None":
    """Find first available resource for service at given time."""
    from .models import Appointment, BookingResource, WorkingHours

    resources = BookingResource.objects.filter(
        resource_type=service.resource_type, is_active=True
    )
    weekday = target_date.weekday()

    for resource in resources:
        wh = WorkingHours.objects.filter(
            resource=resource, day_of_week=weekday, is_day_off=False
        ).first()
        if not wh:
            continue

        # Check working hours
        if start_time.time() < wh.start_time or end_time.time() > wh.end_time:
            continue

        # Check overlaps
        overlap = Appointment.objects.filter(
            resource=resource,
            start_time__date=target_date,
            status__in=["scheduled", "confirmed"],
            start_time__lt=timezone.make_aware(end_time),
            end_time__gt=timezone.make_aware(start_time),
        ).exists()

        if not overlap:
            return resource

    return None


def _get_or_create_partner(name: str, email: str, phone: str = "", company: "Company | None" = None):
    """Get or create partner by email."""
    from partners.models import Partner

    if email:
        partner = Partner.objects.filter(email=email).first()
        if partner:
            return partner

    return Partner.objects.create(
        name=name,
        email=email,
        phone=phone or "",
        company=company,
        is_active=True,
    )


def _send_status_notification(appointment: "Appointment", new_status: str) -> None:
    """Send status change notification (email + WhatsApp) to client."""
    try:
        from .tasks import notify_appointment_status_change
        notify_appointment_status_change.delay(appointment.pk, new_status)
    except ImportError as e:
        logger.warning("Failed to send notification for appt %d: %s", appointment.pk, e)
