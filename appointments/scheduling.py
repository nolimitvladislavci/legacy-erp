"""
appointments/scheduling.py
Polymorphic Resource Scheduling Engine - Double-Lock + Race Protection.
v2 - Koristi Appointment.actor_resource FK (mig 0009) za precizno pracenje aktora.
"""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from appointments.models import Appointment, BookingResource, WorkingHours


class SchedulingError(Exception):
    def __init__(self, message, code="CONFLICT", detail=""):
        self.message = message
        self.code = code
        self.detail = detail
        super().__init__(message)


def get_on_shift_actors(company, target_date, start_dt, end_dt):
    weekday = target_date.weekday()
    actors = BookingResource.objects.filter(
        company=company, resource_type="ljudstvo", is_active=True,
    )
    available = []
    for actor in actors:
        wh = WorkingHours.objects.filter(
            resource=actor, day_of_week=weekday, is_day_off=False,
        ).first()
        if not wh:
            continue
        if wh.start_time <= start_dt.time() and wh.end_time >= end_dt.time():
            available.append(actor)
    return available


def get_busy_actor_ids(company, start_dt, end_dt):
    """
    ID-evi zauzetih radnika via Appointment.actor_resource_id FK.
    Ovo je v2 fix - v1 koristio title prefix [A:123] workaround.
    """
    return set(
        Appointment.objects.filter(
            company=company,
            start_time__lt=end_dt,
            end_time__gt=start_dt,
            status__in=["scheduled", "confirmed"],
            actor_resource__isnull=False,
        ).values_list("actor_resource_id", flat=True)
    )


def get_busy_resource_ids(company, start_dt, end_dt):
    return set(
        Appointment.objects.filter(
            company=company,
            start_time__lt=end_dt,
            end_time__gt=start_dt,
            status__in=["scheduled", "confirmed"],
            resource__isnull=False,
        ).values_list("resource_id", flat=True)
    )


def _advisory_lock_slot(company_id, resource_id, slot_epoch):
    """
    PostgreSQL transakcijski advisory lock za booking slot.
    pg_try_advisory_xact_lock vraca False odmah ako je slot vec zakljucan
    u drugoj aktivnoj transakciji — sprecava race condition bez cekanja.
    Key je deterministicki hash (company, resource, slot_time).
    SQLite fallback: uvijek vraca True (nema advisory lock podrsku).
    """
    from django.db import connection
    if connection.vendor != 'postgresql':
        return True
    import ctypes
    raw = hash((company_id, resource_id, slot_epoch)) & 0x7FFFFFFFFFFFFFFF
    lock_key = ctypes.c_int64(raw).value
    with connection.cursor() as cur:
        cur.execute("SELECT pg_try_advisory_xact_lock(%s)", [lock_key])
        return cur.fetchone()[0]


@transaction.atomic
def book_slot(company, service, start_dt, end_dt, client=None,
              client_name="", client_data=None, user_actor_id=None):
    """
    Atomicki zakazan termin s Double-Lock + Advisory Lock zastitom.

    Tri sloja zastite od race conditiona:
    1. @transaction.atomic — sve ili nista
    2. select_for_update() — zakljucava postojece overlapping retke
    3. pg_try_advisory_xact_lock — zakljucava SLOT KLJUC cak i kad nema
       postojecih appointmenta (prazan slot, prvi booking)
    """
    client_data = client_data or {}

    locked = list(
        Appointment.objects.select_for_update().filter(
            company=company,
            start_time__lt=end_dt,
            end_time__gt=start_dt,
            status__in=["scheduled", "confirmed"],
        )
    )

    # Izvuci zauzetosti iz zakljucanih redaka
    busy_actor_ids = {a.actor_resource_id for a in locked if a.actor_resource_id}
    busy_resource_ids = {a.resource_id for a in locked if a.resource_id}

    # Advisory lock: zakljucaj slot kljuc za ovaj company+time
    # Sprecava race condition kad je slot prazan (nema sto lockati s select_for_update)
    slot_key = int(start_dt.timestamp())
    if not _advisory_lock_slot(company.pk, 0, slot_key):
        raise SchedulingError(
            "Termin je upravo zauzet od drugog korisnika. Pokusajte ponovo.",
            code="RACE_CONFLICT",
            detail="pg_try_advisory_xact_lock: slot zauzet u konkurentnoj transakciji.",
        )

    assigned_actor = None
    if service.requires_actor:
        on_shift = get_on_shift_actors(company, start_dt.date(), start_dt, end_dt)
        if not on_shift:
            raise SchedulingError(
                "Nema dostupnih izvrsitelja u tom vremenu.",
                code="NO_ACTOR",
                detail="Nijedan radnik nema smjenu koja pokriva trazeni termin.",
            )
        free_actors = [a for a in on_shift if a.pk not in busy_actor_ids]
        if not free_actors:
            raise SchedulingError(
                "Svi izvrsitelji su zauzeti u tom terminu.",
                code="NO_ACTOR",
                detail="%d radnika u smjeni, svi zauzeti." % len(on_shift),
            )
        assigned_actor = free_actors[0]

    assigned_resource = None
    if service.requires_resource:
        res_type = service.resource_type
        if res_type == "ljudstvo":
            assigned_resource = assigned_actor
        else:
            all_resources = list(BookingResource.objects.filter(
                company=company, resource_type=res_type, is_active=True,
            ))
            if not all_resources:
                raise SchedulingError(
                    "Nema konfiguriranih resursa tipa '%s'." % res_type,
                    code="NO_RESOURCE",
                    detail="Administrator mora dodati resurse u sustav.",
                )
            free_resources = [r for r in all_resources if r.pk not in busy_resource_ids]
            if not free_resources:
                raise SchedulingError(
                    "Svi fizicki resursi su zauzeti u tom terminu.",
                    code="NO_RESOURCE",
                    detail="%d resursa ukupno, svi zauzeti." % len(all_resources),
                )
            assigned_resource = free_resources[0]

    display_title = service.name
    if client_name:
        display_title = "%s - %s" % (service.name, client_name)

    appointment = Appointment.objects.create(
        company=company,
        title=display_title,
        client=client,
        service=service,
        resource=assigned_resource,
        actor_resource=assigned_actor,
        start_time=start_dt,
        end_time=end_dt,
        appointment_type="service",
        status="scheduled",
        color=service.color or "#10b981",
        total_price=service.price or 0,
        payment_method=client_data.get("payment_method", "invoice"),
        whatsapp_number=client_data.get("whatsapp", ""),
    )
    return appointment


def check_availability(company, service, start_dt, end_dt):
    busy_actor_ids = get_busy_actor_ids(company, start_dt, end_dt)
    busy_resource_ids = get_busy_resource_ids(company, start_dt, end_dt)

    if service.requires_actor:
        on_shift = get_on_shift_actors(company, start_dt.date(), start_dt, end_dt)
        if not on_shift:
            return False, "NO_ACTOR"
        free = [a for a in on_shift if a.pk not in busy_actor_ids]
        if not free:
            return False, "NO_ACTOR"

    if service.requires_resource and service.resource_type != "ljudstvo":
        all_res = list(BookingResource.objects.filter(
            company=company, resource_type=service.resource_type, is_active=True,
        ))
        if not all_res:
            return False, "NO_RESOURCE"
        free = [r for r in all_res if r.pk not in busy_resource_ids]
        if not free:
            return False, "NO_RESOURCE"

    return True, "OK"


def process_no_show(company):
    tolerance = getattr(company, "no_show_tolerance_minutes", 15) or 15
    cutoff = timezone.now() - timedelta(minutes=tolerance)
    stale = Appointment.objects.filter(
        company=company, status="scheduled", start_time__lt=cutoff,
    )
    count = 0
    for appt in stale:
        appt.status = "no_show"
        appt.save(update_fields=["status", "updated_at"])
        count += 1
    return count
