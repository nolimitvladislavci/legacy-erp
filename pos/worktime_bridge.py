"""
pos/worktime_bridge.py
Auto-generiranje TimeEntry iz POS cashier PIN login/logout.
"""
import logging
from decimal import Decimal
from django.utils import timezone

logger = logging.getLogger('pos.worktime')


def _get_or_create_pos_project(company):
    """Lazy-create 'POS Rad' projekt za evidenciju sati."""
    from worktime.models import Project
    project, created = Project.objects.get_or_create(
        code=f'POS-{company.pk}'[:20],
        defaults={
            'name': f'POS Rad — {company.name}',
            'status': 'ACTIVE',
        }
    )
    if created:
        logger.info(f'Created POS project for {company.name}')
    return project


def cashier_clock_in(cashier):
    """Zabilježi prijavu blagajnika — poziva se iz PIN verify."""
    now = timezone.now()

    # Zatvori prethodni nepreklopljeni clock_in (ako postoji)
    if cashier.clock_in_at:
        cashier_clock_out(cashier, forced=True)

    cashier.clock_in_at = now
    cashier.save(update_fields=['clock_in_at'])
    logger.info(f'Cashier {cashier.name} clocked in at {now}')


def cashier_clock_out(cashier, forced=False):
    """Zatvori smjenu blagajnika i kreiraj TimeEntry."""
    if not cashier.clock_in_at:
        return None

    if not cashier.user:
        # Bez Django usera ne mozemo kreirati TimeEntry
        logger.warning(f'Cashier {cashier.name} has no linked user — skipping TimeEntry')
        cashier.clock_in_at = None
        cashier.save(update_fields=['clock_in_at'])
        return None

    now = timezone.now()
    start = cashier.clock_in_at
    delta = now - start

    # Min 1 minuta, max 16 sati (zastita od zaboravljenog clock-out)
    hours = Decimal(str(round(delta.total_seconds() / 3600, 2)))
    if hours < Decimal('0.02'):
        cashier.clock_in_at = None
        cashier.save(update_fields=['clock_in_at'])
        return None
    if hours > Decimal('16'):
        hours = Decimal('16')

    try:
        from worktime.models import TimeEntry
        company = cashier.company
        project = _get_or_create_pos_project(company)

        entry = TimeEntry.objects.create(
            company=company,
            user=cashier.user,
            project=project,
            date=start.date(),
            start_time=start.time(),
            end_time=now.time(),
            duration=hours,
            description=f'POS smjena — {cashier.name}' + (' [auto-close]' if forced else ''),
            task_type='OTHER',
            status='APPROVED',
            from_timer=True,
            break_minutes=0,
        )
        entry.calculate_payroll()
        entry.save()

        logger.info(f'TimeEntry created for {cashier.name}: {hours}h on {start.date()}')

        # Reset clock_in
        cashier.clock_in_at = None
        cashier.save(update_fields=['clock_in_at'])

        return entry

    except Exception as e:
        logger.error(f'Failed to create TimeEntry for {cashier.name}: {e}')
        cashier.clock_in_at = None
        cashier.save(update_fields=['clock_in_at'])
        return None


def session_close_all_cashiers(session):
    """Kad se POS smjena zatvara, zatvori sve aktivne blagajnike + konobarske smjene."""
    for cashier in session.active_cashiers.filter(clock_in_at__isnull=False):
        cashier_clock_out(cashier)

    # Zatvori aktivne WaiterShift za ovu kompaniju
    try:
        from pos.models import WaiterShift
        active_shifts = WaiterShift.objects.filter(
            company=session.terminal.company, is_active=True
        )
        now = timezone.now()
        for shift in active_shifts:
            shift.is_active = False
            shift.ended_at = now
            shift.save(update_fields=['is_active', 'ended_at'])
        if active_shifts.exists():
            logger.info('WaiterShifts closed for session #%s', session.session_number)
    except Exception as e:
        logger.warning('WaiterShift close failed: %s', e)

    logger.info(f'All cashiers clocked out for session #{session.session_number}')


# ═══════════════════════════════════════════════════════════════
# UNIFIED LOGIN — DeviceToken → radno vrijeme + waiter shift + cashier
# Jedan scan = sve počinje
# ═══════════════════════════════════════════════════════════════

def device_login_start_all(device_token, ip_address=None):
    """
    Kad se korisnik logira preko DeviceToken barkoda:
    1. TimeLog (radno vrijeme) — clock in
    2. WaiterShift — ako radi u gastro
    3. Cashier clock_in — ako ima cashier profil

    Vraća dict sa statusima.
    """
    user = device_token.user
    company = device_token.company
    now = timezone.now()
    result = {'user': user.get_full_name() or user.username, 'started': []}

    # 1. TimeLog — clock in (radno vrijeme)
    try:
        from worktime.models import TimeLog
        open_log = TimeLog.objects.filter(user=user, company=company, status='OPEN').first()
        if not open_log:
            timelog = TimeLog.objects.create(
                user=user,
                company=company,
                date=now.date(),
                start_time=now,
                status='OPEN',
            )
            if ip_address:
                timelog.notes = 'DeviceToken login (IP: %s)' % ip_address
                timelog.save(update_fields=['notes'])
            result['started'].append('radno_vrijeme')
            result['timelog_id'] = timelog.pk
            logger.info('TimeLog started for %s via DeviceToken', user.username)
        else:
            result['timelog_id'] = open_log.pk
            result['started'].append('radno_vrijeme_existing')
    except Exception as e:
        logger.warning('TimeLog creation failed for %s: %s', user.username, e)

    # 2. WaiterShift — ako postoji
    try:
        from pos.models import WaiterShift
        active_shift = WaiterShift.objects.filter(user=user, company=company, is_active=True).first()
        if not active_shift:
            shift = WaiterShift.objects.create(
                user=user,
                company=company,
            )
            result['started'].append('waiter_shift')
            result['shift_id'] = shift.pk
            logger.info('WaiterShift started for %s via DeviceToken', user.username)
        else:
            result['shift_id'] = active_shift.pk
            result['started'].append('waiter_shift_existing')
    except Exception as e:
        logger.warning('WaiterShift creation failed for %s: %s', user.username, e)

    # 3. Cashier clock_in — ako ima profil ili je na tokenu
    try:
        from pos.models import POSCashier
        cashier = device_token.cashier
        if not cashier:
            cashier = POSCashier.objects.filter(
                company=company, user=user, is_active=True
            ).first()
        if cashier:
            cashier_clock_in(cashier)
            result['started'].append('cashier')
            result['cashier_id'] = cashier.pk
            result['cashier_name'] = cashier.name
    except Exception as e:
        logger.warning('Cashier clock_in failed for %s: %s', user.username, e)

    return result


def device_logout_stop_all(user, company):
    """
    Kad se korisnik odlogira ili zatvori POS:
    1. Zatvori TimeLog
    2. Završi WaiterShift
    3. Clock out cashier
    """
    now = timezone.now()
    result = {'stopped': []}

    # 1. TimeLog close
    try:
        from worktime.models import TimeLog
        open_log = TimeLog.objects.filter(user=user, company=company, status='OPEN').first()
        if open_log:
            open_log.end_time = now
            open_log.close_shift()  # auto ArbZG breaks
            open_log.save()
            result['stopped'].append('radno_vrijeme')
            logger.info('TimeLog closed for %s', user.username)
    except Exception as e:
        logger.warning('TimeLog close failed: %s', e)

    # 2. WaiterShift end
    try:
        from pos.models import WaiterShift
        shift = WaiterShift.objects.filter(user=user, company=company, is_active=True).first()
        if shift:
            shift.is_active = False
            shift.ended_at = now
            shift.save()
            result['stopped'].append('waiter_shift')
            result['duration'] = shift.duration_display
    except Exception as e:
        logger.warning('WaiterShift close failed: %s', e)

    # 3. Cashier clock out
    try:
        from pos.models import POSCashier
        for cashier in POSCashier.objects.filter(company=company, user=user, clock_in_at__isnull=False):
            cashier_clock_out(cashier)
            result['stopped'].append('cashier')
    except Exception as e:
        logger.warning('Cashier clock_out failed: %s', e)

    return result
