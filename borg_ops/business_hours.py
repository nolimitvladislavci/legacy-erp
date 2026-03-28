"""
borg_ops/business_hours.py — Business Hours SLA kalkulator

Dron #2 fix: SLA ne smije zvati alarm vikendom/praznikom.
Podržava: HR + DE kalendar, konfigurabilan po kompaniji.
"""
from datetime import date, datetime, time, timedelta
from django.utils import timezone

# HR državni praznici 2026 (fiksni + varijabilni)
HR_HOLIDAYS_2026 = {
    date(2026, 1, 1),   # Nova godina
    date(2026, 1, 6),   # Bogojavljenje
    date(2026, 5, 1),   # Praznik rada
    date(2026, 5, 30),  # Dan državnosti
    date(2026, 6, 22),  # Dan antifašističke borbe
    date(2026, 8, 5),   # Dan domovinske zahvalnosti
    date(2026, 8, 15),  # Velika Gospa
    date(2026, 11, 1),  # Svi sveti
    date(2026, 11, 18), # Dan sjećanja i Vukovar
    date(2026, 12, 25), # Božić
    date(2026, 12, 26), # Sv. Stjepan
    # Varijabilni 2026 (Uskrs 5.4., Tijelovo 4.6.)
    date(2026, 4, 5),   # Uskrsni ponedjeljak
    date(2026, 6, 4),   # Tijelovo
}


def is_business_hour(dt=None, work_start=8, work_end=16,
                     work_days=(0, 1, 2, 3, 4),
                     holidays=HR_HOLIDAYS_2026):
    """
    Vraća True ako je dt unutar radnog vremena.
    
    Args:
        dt:         datetime (default: now)
        work_start: sat početka radnog vremena (default 8)
        work_end:   sat kraja (default 16)
        work_days:  tuple dana (0=pon, 6=ned), default pon-pet
        holidays:   set datuma praznika
    """
    if dt is None:
        dt = timezone.localtime(timezone.now())
    elif timezone.is_aware(dt):
        dt = timezone.localtime(dt)

    d = dt.date()
    if d in holidays:
        return False
    if dt.weekday() not in work_days:
        return False
    if not (work_start <= dt.hour < work_end):
        return False
    return True


def business_minutes_elapsed(since, until=None,
                              work_start=8, work_end=16,
                              work_days=(0, 1, 2, 3, 4),
                              holidays=HR_HOLIDAYS_2026):
    """
    Računa broj RADNIH minuta između dva trenutka.
    Preskače vikende, praznike i van-radne sate.
    
    Returns: int (radne minute)
    """
    if until is None:
        until = timezone.now()

    if timezone.is_aware(since):
        since = timezone.localtime(since).replace(tzinfo=None)
    if timezone.is_aware(until):
        until = timezone.localtime(until).replace(tzinfo=None)

    if since >= until:
        return 0

    minutes = 0
    current = since
    work_start_t = time(work_start, 0)
    work_end_t   = time(work_end, 0)
    day_minutes  = (work_end - work_start) * 60

    while current.date() <= until.date():
        d = current.date()
        is_holiday  = d in holidays
        is_workday  = current.weekday() in work_days and not is_holiday

        if is_workday:
            day_start = datetime.combine(d, work_start_t)
            day_end   = datetime.combine(d, work_end_t)
            seg_start = max(current, day_start)
            seg_end   = min(until, day_end)
            if seg_start < seg_end:
                minutes += int((seg_end - seg_start).total_seconds() / 60)

        # Skok na sljedeći dan
        current = datetime.combine(d + timedelta(days=1), work_start_t)

    return minutes


def sla_breached(entered_at, max_business_minutes,
                 work_start=8, work_end=16,
                 work_days=(0, 1, 2, 3, 4)):
    """
    Vraća (breached: bool, elapsed_minutes: int).
    Koristi se u Celery SLA check tasku.
    """
    elapsed = business_minutes_elapsed(entered_at,
                                       work_start=work_start,
                                       work_end=work_end,
                                       work_days=work_days)
    return elapsed >= max_business_minutes, elapsed
