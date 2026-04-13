"""
borg_ops/business_hours.py — Business Hours SLA kalkulator

BORG v2: Dinamički praznici via `holidays` package.
Podržava: HR + DE kalendar, konfigurabilan po kompaniji.
Nema hardkodiranih datuma — računa pomične praznike matematički zauvijek.
"""
from datetime import date, datetime, time, timedelta
from django.utils import timezone
import logging
from django.db import DatabaseError

logger = logging.getLogger('borg.sla')


def get_holidays(country='HR', year=None):
    """
    Vraća set datuma praznika za danu godinu i državu.
    Koristi `holidays` package koji matematički računa pomične praznike
    (Uskrs, Tijelovo) za bilo koju godinu.

    Fallback: ako package nije instaliran, vraća praznu listu
    (SLA se računa bez praznika — sigurnije nego hardkodirano).
    """
    if year is None:
        year = date.today().year

    try:
        import holidays as holidays_pkg
        country_map = {
            'HR': holidays_pkg.HR,
            'DE': holidays_pkg.DE,
            'AT': holidays_pkg.AT,
            'SI': holidays_pkg.SI,
            'BA': holidays_pkg.BA,
        }
        cls = country_map.get(country.upper(), holidays_pkg.HR)
        return set(cls(years=year).keys())
    except ImportError:
        logger.warning('holidays package not installed — SLA radi bez praznika')
        return set()
    except KeyError as e:
        logger.error('holidays error: %s', e)
        return set()


def get_company_holidays(company=None, year=None):
    """
    Praznici za specifičnu firmu = državni praznici + kolektivni godišnji.
    Ako firma ima country field, koristi taj; inače HR default.
    """
    if year is None:
        year = date.today().year

    country = 'HR'
    if company:
        country = getattr(company, 'country_code', 'HR') or 'HR'

    holidays_set = get_holidays(country, year)

    # Dodaj custom non-working days iz baze (ako model postoji)
    try:
        from borg_ops.models import NonWorkingDay
        custom = NonWorkingDay.objects.filter(
            date__year=year,
        )
        if company:
            custom = custom.filter(
                models.Q(company=company) | models.Q(company__isnull=True)
            )
        else:
            custom = custom.filter(company__isnull=True)
        holidays_set |= set(custom.values_list('date', flat=True))
    except DatabaseError:
        pass  # Model ne postoji još — to je OK

    return holidays_set


def is_business_hour(dt=None, work_start=8, work_end=16,
                     work_days=(0, 1, 2, 3, 4),
                     holidays=None, company=None):
    """
    Vraća True ako je dt unutar radnog vremena.

    Args:
        dt:         datetime (default: now)
        work_start: sat početka radnog vremena (default 8)
        work_end:   sat kraja (default 16)
        work_days:  tuple dana (0=pon, 6=ned), default pon-pet
        holidays:   set datuma praznika (auto ako None)
        company:    Company instanca za company-specific praznike
    """
    if dt is None:
        dt = timezone.localtime(timezone.now())
    elif timezone.is_aware(dt):
        dt = timezone.localtime(dt)

    d = dt.date()

    if holidays is None:
        holidays = get_company_holidays(company, d.year)

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
                              holidays=None, company=None):
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

    # Collect holidays za sve godine u rasponu
    if holidays is None:
        years = set(range(since.year, until.year + 1))
        holidays = set()
        for y in years:
            holidays |= get_company_holidays(company, y)

    minutes = 0
    current = since
    work_start_t = time(work_start, 0)
    work_end_t   = time(work_end, 0)

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
                 work_days=(0, 1, 2, 3, 4), company=None):
    """
    Vraća (breached: bool, elapsed_minutes: int).
    Koristi se u Celery SLA check tasku.
    """
    elapsed = business_minutes_elapsed(entered_at,
                                       work_start=work_start,
                                       work_end=work_end,
                                       work_days=work_days,
                                       company=company)
    return elapsed >= max_business_minutes, elapsed
