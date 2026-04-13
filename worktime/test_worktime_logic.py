"""
worktime/tests/test_worktime_logic.py
Model logika i payroll testovi za worktime app.
Pokriva: TimeEntry.calculate_payroll, overtime, noćni rad, compliance,
ActiveTimer lifecycle, TimeLog ArbZG break, EmployeeProfile, Project budget.
"""
import datetime
from decimal import Decimal

from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone

from companies.models import Company
from worktime.models import (
    Project, TimeEntry, EmployeeProfile, ActiveTimer,
    WorkGroup, TimeLog, DailyNote, TimeEntryTemplate,
)


def _company(oib='11111111100', name='WT Test d.o.o.'):
    return Company.objects.create(name=name, oib=oib)


def _user(username, company=None):
    u = User.objects.create_user(username, password='pass')
    if company:
        try:
            from accounts.models import UserProfile
            UserProfile.objects.get_or_create(user=u, defaults={'company': company})
        except DatabaseError:
            pass
    return u


def _project(company, code, **kwargs):
    defaults = dict(name=f'Projekt {code}', status='ACTIVE', hourly_rate=Decimal('25.00'))
    defaults.update(kwargs)
    return Project.objects.create(company=company, code=code, **defaults)


def _entry(user, project, duration, date=None, **kwargs):
    defaults = dict(
        company=project.company,
        date=date or datetime.date.today(),
        duration=Decimal(str(duration)),
        status='PENDING',
    )
    defaults.update(kwargs)
    return TimeEntry.objects.create(user=user, project=project, **defaults)


# ─────────────────────────────────────────────────────────────
# Project model
# ─────────────────────────────────────────────────────────────
class TestProjectModel(TestCase):

    def setUp(self):
        self.company = _company()
        self.user = _user('proj_tester', self.company)

    def test_project_str(self):
        p = _project(self.company, 'P-001')
        self.assertIn('P-001', str(p))

    def test_hours_used_empty(self):
        p = _project(self.company, 'P-002')
        self.assertEqual(p.hours_used, Decimal('0'))

    def test_hours_used_sums_entries(self):
        p = _project(self.company, 'P-003')
        _entry(self.user, p, 4)
        _entry(self.user, p, 3.5)
        self.assertEqual(p.hours_used, Decimal('7.5'))

    def test_budget_percentage_zero_no_budget(self):
        p = _project(self.company, 'P-004', budget_hours=None)
        self.assertEqual(p.budget_percentage, 0)

    def test_budget_percentage_calculates(self):
        p = _project(self.company, 'P-005', budget_hours=Decimal('10'))
        _entry(self.user, p, 5)
        self.assertEqual(p.budget_percentage, 50.0)

    def test_budget_percentage_caps_at_100(self):
        p = _project(self.company, 'P-006', budget_hours=Decimal('4'))
        _entry(self.user, p, 8)
        self.assertEqual(p.budget_percentage, 100)

    def test_project_code_unique(self):
        from django.db import IntegrityError
        _project(self.company, 'UNIQUE-1')
        with self.assertRaises(IntegrityError):
            _project(self.company, 'UNIQUE-1')

    def test_default_billable(self):
        p = _project(self.company, 'P-BILL')
        self.assertTrue(p.is_billable)

    def test_non_billable_project(self):
        p = _project(self.company, 'P-FREE', is_billable=False)
        self.assertFalse(p.is_billable)


# ─────────────────────────────────────────────────────────────
# TimeEntry.calculate_payroll — regular vs overtime
# ─────────────────────────────────────────────────────────────
class TestTimeEntryPayroll(TestCase):

    def setUp(self):
        self.company = _company('22222222200')
        self.user = _user('payroll_user', self.company)
        self.project = _project(self.company, 'PAY-001')

    def test_8h_no_overtime(self):
        e = _entry(self.user, self.project, 8)
        self.assertEqual(e.regular_hours, Decimal('8'))
        self.assertEqual(e.overtime_hours, Decimal('0'))
        self.assertFalse(e.is_overtime)

    def test_10h_has_2h_overtime(self):
        e = _entry(self.user, self.project, 10)
        self.assertEqual(e.regular_hours, Decimal('8'))
        self.assertEqual(e.overtime_hours, Decimal('2'))
        self.assertTrue(e.is_overtime)

    def test_6h_no_overtime(self):
        e = _entry(self.user, self.project, 6)
        self.assertEqual(e.regular_hours, Decimal('6'))
        self.assertEqual(e.overtime_hours, Decimal('0'))

    def test_billing_amount_calculated(self):
        """8h × 25€ = 200€."""
        e = _entry(self.user, self.project, 8)
        self.assertGreater(e.billing_amount, Decimal('0'))

    def test_overtime_billing_higher(self):
        """10h ima veći billing od 8h zbog OT rate."""
        e8 = _entry(self.user, self.project, 8)
        e10 = _entry(self.user, self.project, 10)
        self.assertGreater(e10.billing_amount, e8.billing_amount)


# ─────────────────────────────────────────────────────────────
# TimeEntry — EmployeeProfile rate override
# ─────────────────────────────────────────────────────────────
class TestTimeEntryEmployeeRate(TestCase):

    def setUp(self):
        self.company = _company('33333333300')
        self.user = _user('emp_rate_user', self.company)
        self.project = _project(self.company, 'EMP-001', hourly_rate=Decimal('25'))
        # Kreiraj EmployeeProfile s custom rate
        EmployeeProfile.objects.create(
            company=self.company,
            user=self.user,
            hourly_rate=Decimal('40.00'),
            overtime_rate=Decimal('60.00'),
            daily_hours=Decimal('8'),
        )

    def test_uses_employee_hourly_rate(self):
        """billing_amount koristi employee rate (40), ne project rate (25)."""
        e = _entry(self.user, self.project, 8)
        # 8h × 40€ = 320€
        self.assertEqual(e.billing_amount, Decimal('320.00'))

    def test_overtime_uses_employee_ot_rate(self):
        """10h: 8×40 + 2×60 = 440€."""
        e = _entry(self.user, self.project, 10)
        self.assertEqual(e.billing_amount, Decimal('440.00'))

    def test_daily_hours_from_profile(self):
        """Ako employee ima daily_hours=6, overtime počinje od 6h."""
        emp = self.user.employeeprofile
        emp.daily_hours = Decimal('6')
        emp.save()
        e = _entry(self.user, self.project, 8)
        e.refresh_from_db()
        self.assertEqual(e.regular_hours, Decimal('6'))
        self.assertEqual(e.overtime_hours, Decimal('2'))


# ─────────────────────────────────────────────────────────────
# TimeEntry — night hours
# ─────────────────────────────────────────────────────────────
class TestTimeEntryNightHours(TestCase):

    def setUp(self):
        self.company = _company('44444444400')
        self.user = _user('night_user', self.company)
        self.project = _project(self.company, 'NIGHT-001')

    def test_day_shift_no_night(self):
        """08:00-16:00 → noćnih sati = 0."""
        e = _entry(
            self.user, self.project, 8,
            start_time=datetime.time(8, 0),
            end_time=datetime.time(16, 0),
        )
        self.assertEqual(e.night_hours, Decimal('0'))
        self.assertFalse(e.is_night_work)

    def test_night_shift_22_to_06(self):
        """22:00-06:00 = 8h, sve noćno."""
        e = _entry(
            self.user, self.project, 8,
            start_time=datetime.time(22, 0),
            end_time=datetime.time(6, 0),
        )
        self.assertGreater(e.night_hours, Decimal('0'))
        self.assertTrue(e.is_night_work)

    def test_evening_shift_partial_night(self):
        """20:00-24:00 = 4h, zadnja 2h su noćna."""
        e = _entry(
            self.user, self.project, 4,
            start_time=datetime.time(20, 0),
            end_time=datetime.time(0, 0),
        )
        self.assertGreater(e.night_hours, Decimal('0'))
        self.assertLessEqual(e.night_hours, Decimal('4'))

    def test_no_times_no_night_hours(self):
        """Bez start_time/end_time → night_hours = 0."""
        e = _entry(self.user, self.project, 8)
        self.assertEqual(e.night_hours, Decimal('0'))


# ─────────────────────────────────────────────────────────────
# TimeEntry — compliance (ArbZG / ZOR)
# ─────────────────────────────────────────────────────────────
class TestTimeEntryCompliance(TestCase):

    def setUp(self):
        self.company = _company('55555555500')
        self.user = _user('compliance_user', self.company)
        self.project = _project(self.company, 'COMP-001')

    def test_8h_no_compliance_warning(self):
        """8h s dovoljnom pauzom → nema upozorenja."""
        e = _entry(self.user, self.project, 8, break_minutes=30)
        self.assertEqual(e.compliance_note, '')

    def test_11h_triggers_arbzg3(self):
        e = _entry(self.user, self.project, 11)
        self.assertIn('ArbZG §3', e.compliance_note)

    def test_13h_triggers_critical(self):
        e = _entry(self.user, self.project, 13)
        self.assertIn('KRITIČNO', e.compliance_note)

    def test_6h_no_break_triggers_warning(self):
        """6h rada bez pauze → upozorenje o pauzi."""
        e = _entry(self.user, self.project, 6, break_minutes=0)
        self.assertIn('ArbZG §4', e.compliance_note)

    def test_6h_with_30min_break_ok(self):
        e = _entry(self.user, self.project, 6, break_minutes=30)
        self.assertEqual(e.compliance_note, '')

    def test_9h_with_45min_break_ok(self):
        e = _entry(self.user, self.project, 9, break_minutes=45)
        # Samo ArbZG §3 (>10h) neće biti, ali 9h je ok za pauzu
        self.assertNotIn('ArbZG §4', e.compliance_note)

    def test_9h_with_30min_break_triggers(self):
        """9h ali samo 30min pauze → treba 45min."""
        e = _entry(self.user, self.project, 9, break_minutes=30)
        self.assertIn('ArbZG §4', e.compliance_note)

    def test_absence_type_skips_payroll(self):
        """Godišnji odmor → calculate_payroll se ne poziva."""
        e = _entry(self.user, self.project, 8, absence_type='ANNUAL')
        # Ne smije imati payroll izračun
        self.assertEqual(e.billing_amount, Decimal('0'))
        self.assertEqual(e.regular_hours, Decimal('0'))


# ─────────────────────────────────────────────────────────────
# ActiveTimer lifecycle
# ─────────────────────────────────────────────────────────────
class TestActiveTimer(TestCase):

    def setUp(self):
        self.company = _company('66666666600')
        self.user = _user('timer_user', self.company)
        self.project = _project(self.company, 'TIMER-001')

    def _create_timer(self):
        return ActiveTimer.objects.create(
            company=self.company,
            user=self.user,
            project=self.project,
            description='Testni rad',
            started_at=timezone.now(),
        )

    def test_timer_created(self):
        t = self._create_timer()
        self.assertIsNotNone(t.pk)
        self.assertEqual(t.status, 'RUNNING')

    def test_elapsed_seconds_positive(self):
        t = self._create_timer()
        self.assertGreaterEqual(t.elapsed_seconds, 0)

    def test_elapsed_display_format(self):
        t = self._create_timer()
        display = t.elapsed_display
        parts = display.split(':')
        self.assertEqual(len(parts), 3)

    def test_pause_changes_status(self):
        t = self._create_timer()
        t.pause()
        t.refresh_from_db()
        self.assertEqual(t.status, 'PAUSED')

    def test_pause_accumulates_seconds(self):
        t = self._create_timer()
        t.pause()
        self.assertGreaterEqual(t.accumulated_seconds, 0)

    def test_resume_changes_status_to_running(self):
        t = self._create_timer()
        t.pause()
        t.resume()
        t.refresh_from_db()
        self.assertEqual(t.status, 'RUNNING')

    def test_paused_elapsed_equals_accumulated(self):
        t = self._create_timer()
        t.pause()
        self.assertEqual(t.elapsed_seconds, t.accumulated_seconds)

    def test_stop_creates_time_entry(self):
        t = self._create_timer()
        entry = t.stop_and_save()
        self.assertIsNotNone(entry.pk)
        self.assertEqual(entry.project, self.project)
        self.assertEqual(entry.user, self.user)

    def test_stop_deletes_timer(self):
        t = self._create_timer()
        pk = t.pk
        t.stop_and_save()
        self.assertFalse(ActiveTimer.objects.filter(pk=pk).exists())

    def test_stop_entry_from_timer_flag(self):
        t = self._create_timer()
        entry = t.stop_and_save()
        self.assertTrue(entry.from_timer)

    def test_discard_deletes_timer(self):
        t = self._create_timer()
        pk = t.pk
        t.discard()
        self.assertFalse(ActiveTimer.objects.filter(pk=pk).exists())

    def test_one_timer_per_user(self):
        """OneToOne — drugi timer za istog usera daje IntegrityError."""
        from django.db import IntegrityError
        self._create_timer()
        with self.assertRaises(IntegrityError):
            ActiveTimer.objects.create(
                company=self.company, user=self.user, project=self.project,
                started_at=timezone.now(),
            )


# ─────────────────────────────────────────────────────────────
# TimeLog — ArbZG break calculation
# ─────────────────────────────────────────────────────────────
class TestTimeLog(TestCase):

    def setUp(self):
        self.company = _company('77777777700')
        self.user = _user('timelog_user', self.company)

    def _log(self, start_h, end_h):
        now = timezone.now()
        start = now.replace(hour=start_h, minute=0, second=0, microsecond=0)
        end = now.replace(hour=end_h, minute=0, second=0, microsecond=0)
        return TimeLog.objects.create(
            company=self.company,
            user=self.user,
            start_time=start,
            end_time=end,
            date=now.date(),
        )

    def test_5h_no_mandatory_break(self):
        log = self._log(8, 13)
        log.close_shift()
        self.assertEqual(log.break_minutes, 0)

    def test_7h_mandatory_30min_break(self):
        log = self._log(8, 15)
        log.close_shift()
        self.assertEqual(log.break_minutes, 30)

    def test_10h_mandatory_45min_break(self):
        log = self._log(8, 18)
        log.close_shift()
        self.assertEqual(log.break_minutes, 45)

    def test_payable_hours_deducts_break(self):
        """9h rada - 30min pauza = 8.5h neto."""
        log = self._log(8, 17)
        log.close_shift()
        self.assertEqual(log.payable_hours, Decimal('8.5'))

    def test_close_shift_sets_status_closed(self):
        log = self._log(9, 17)
        log.close_shift()
        self.assertEqual(log.status, 'CLOSED')

    def test_gross_hours_calculated(self):
        log = self._log(8, 16)  # 8h
        log.close_shift()
        self.assertEqual(log.gross_hours, Decimal('8.00'))

    def test_str_contains_username(self):
        log = self._log(8, 16)
        self.assertIn(self.user.username, str(log))

    def test_payable_hours_never_negative(self):
        """Rubni slučaj: payable ne smije biti negativan."""
        log = self._log(8, 9)  # 1h
        log.close_shift()
        self.assertGreaterEqual(log.payable_hours, Decimal('0'))


# ─────────────────────────────────────────────────────────────
# DailyNote
# ─────────────────────────────────────────────────────────────
class TestDailyNote(TestCase):

    def setUp(self):
        self.company = _company('88888888800')
        self.user = _user('note_user', self.company)

    def test_create_note(self):
        note = DailyNote.objects.create(
            company=self.company,
            user=self.user,
            date=datetime.date.today(),
            note='Danas sam radio na projektu X.',
        )
        self.assertIsNotNone(note.pk)

    def test_unique_per_user_date(self):
        """Jedan korisnik može imati samo jednu bilješku po danu."""
        from django.db import IntegrityError
        today = datetime.date.today()
        DailyNote.objects.create(company=self.company, user=self.user, date=today, note='Prva')
        with self.assertRaises(IntegrityError):
            DailyNote.objects.create(company=self.company, user=self.user, date=today, note='Druga')

    def test_different_dates_ok(self):
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        today = datetime.date.today()
        DailyNote.objects.create(company=self.company, user=self.user, date=yesterday, note='Jučer')
        DailyNote.objects.create(company=self.company, user=self.user, date=today, note='Danas')
        self.assertEqual(DailyNote.objects.filter(user=self.user).count(), 2)


# ─────────────────────────────────────────────────────────────
# WorkGroup
# ─────────────────────────────────────────────────────────────
class TestWorkGroup(TestCase):

    def setUp(self):
        self.company = _company('99999999900')
        self.user = _user('wg_user', self.company)

    def test_create_work_group(self):
        wg = WorkGroup.objects.create(company=self.company, name='Backend Tim')
        self.assertEqual(str(wg), 'Backend Tim')

    def test_add_member(self):
        wg = WorkGroup.objects.create(company=self.company, name='Tim A')
        wg.members.add(self.user)
        self.assertIn(self.user, wg.members.all())

    def test_manager_assignment(self):
        wg = WorkGroup.objects.create(company=self.company, name='Tim B', manager=self.user)
        self.assertEqual(wg.manager, self.user)

    def test_project_in_workgroup(self):
        wg = WorkGroup.objects.create(company=self.company, name='Tim C')
        p = _project(self.company, 'WG-PROJ', work_group=wg)
        self.assertEqual(p.work_group, wg)
        self.assertIn(p, wg.projects.all())


# ─────────────────────────────────────────────────────────────
# TimeEntryTemplate
# ─────────────────────────────────────────────────────────────
class TestTimeEntryTemplate(TestCase):

    def setUp(self):
        self.company = _company('10010010010')
        self.user = _user('tmpl_user', self.company)
        self.project = _project(self.company, 'TMPL-001')

    def test_create_template(self):
        t = TimeEntryTemplate.objects.create(
            company=self.company,
            user=self.user,
            project=self.project,
            name='Standardni radni dan',
            default_duration=Decimal('8.00'),
        )
        self.assertIsNotNone(t.pk)
        self.assertEqual(str(t), f'Standardni radni dan ({self.project.code})')

    def test_use_count_default_zero(self):
        t = TimeEntryTemplate.objects.create(
            company=self.company, user=self.user, project=self.project,
            name='Predložak', default_duration=Decimal('4'),
        )
        self.assertEqual(t.use_count, 0)

    def test_ordering_by_use_count(self):
        t1 = TimeEntryTemplate.objects.create(
            company=self.company, user=self.user, project=self.project,
            name='Rijetko', default_duration=Decimal('1'), use_count=0,
        )
        t2 = TimeEntryTemplate.objects.create(
            company=self.company, user=self.user, project=self.project,
            name='Često', default_duration=Decimal('8'), use_count=50,
        )
        first = TimeEntryTemplate.objects.filter(user=self.user).first()
        self.assertEqual(first.pk, t2.pk)  # veći use_count dolazi prvi
