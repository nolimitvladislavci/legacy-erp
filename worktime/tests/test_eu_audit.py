"""EU Audit Guard — testovi za 3 nagazne mine."""
import sys
from datetime import time
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone as tz

User = get_user_model()

# Temporarily add /tmp to path for eu_audit_guard until root deploys
sys.path.insert(0, '/tmp')


class EUAuditSetup(TestCase):
    @classmethod
    def setUpTestData(cls):
        from companies.models import Company
        from worktime.models import Project
        cls.company = Company.objects.create(name='EU Test Udruga', oib='44444444401')
        cls.user = User.objects.create_user('euvolonter', 'eu@t.com', 'T123!')
        cls.approver = User.objects.create_user('euvoditelj', 'vod@t.com', 'T123!')
        cls.project = Project.objects.create(
            company=cls.company, code='ESF-TEST-001',
            name='EU Test Projekt', hourly_rate=Decimal('8.00'),
        )

    def _entry(self, date, start, end, duration=None, approved=True, project=None):
        from worktime.models import TimeEntry
        d = duration or Decimal(str((tz.datetime.combine(date, end) - tz.datetime.combine(date, start)).total_seconds() / 3600))
        return TimeEntry.objects.create(
            company=self.company, user=self.user,
            project=project or self.project,
            date=date, start_time=start, end_time=end,
            duration=d, status='APPROVED' if approved else 'PENDING',
            approved_by=self.approver if approved else None,
            approved_at=tz.now() if approved else None,
            is_volunteer_work=True,
        )


class DoubleDippingTest(EUAuditSetup):
    """MINA 1: Preklapanje radnog vremena."""

    def test_01_no_overlap_ok(self):
        from eu_audit_guard import EUAuditGuard
        from datetime import date
        d = date(2026, 3, 10)
        self._entry(d, time(8, 0), time(12, 0))
        conflicts = EUAuditGuard.check_double_dipping(
            self.user, d, time(13, 0), time(17, 0)
        )
        self.assertEqual(len(conflicts), 0)

    def test_02_overlap_detected(self):
        from eu_audit_guard import EUAuditGuard
        from datetime import date
        d = date(2026, 3, 11)
        self._entry(d, time(8, 0), time(12, 0))
        conflicts = EUAuditGuard.check_double_dipping(
            self.user, d, time(11, 0), time(15, 0)
        )
        self.assertEqual(len(conflicts), 1)

    def test_03_validate_raises(self):
        from eu_audit_guard import EUAuditGuard, EUAuditError
        from worktime.models import TimeEntry
        from datetime import date
        d = date(2026, 3, 12)
        self._entry(d, time(8, 0), time(12, 0))
        new_entry = TimeEntry(
            company=self.company, user=self.user, project=self.project,
            date=d, start_time=time(10, 0), end_time=time(14, 0),
            duration=Decimal('4'), status='PENDING',
        )
        with self.assertRaises(EUAuditError) as ctx:
            EUAuditGuard.validate_no_overlap(new_entry)
        self.assertEqual(ctx.exception.code, 'DOUBLE_DIPPING')

    def test_04_same_entry_excluded(self):
        """Entry ne konflikira sam sa sobom."""
        from eu_audit_guard import EUAuditGuard
        from datetime import date
        d = date(2026, 3, 13)
        entry = self._entry(d, time(8, 0), time(12, 0))
        conflicts = EUAuditGuard.check_double_dipping(
            self.user, d, time(8, 0), time(12, 0), exclude_pk=entry.pk
        )
        self.assertEqual(len(conflicts), 0)


class MonthlyCapTest(EUAuditSetup):
    """MINA 2: Mjesečni fond sati."""

    def test_05_under_cap_ok(self):
        from eu_audit_guard import EUAuditGuard
        from datetime import date
        self._entry(date(2026, 3, 10), time(8, 0), time(12, 0), duration=Decimal('4'))
        result = EUAuditGuard.check_monthly_cap(self.user, 2026, 3)
        self.assertFalse(result['exceeded'])

    def test_06_over_cap_detected(self):
        from eu_audit_guard import EUAuditGuard
        result = EUAuditGuard.check_monthly_cap(self.user, 2026, 3, max_hours=Decimal('2'))
        # Mora imati barem neke sate od prethodnih testova
        # Testiram s eksplicitnim limitom
        from datetime import date
        self._entry(date(2026, 4, 1), time(8, 0), time(16, 0), duration=Decimal('100'))
        result = EUAuditGuard.check_monthly_cap(self.user, 2026, 4, max_hours=Decimal('50'))
        self.assertTrue(result['exceeded'])
        self.assertEqual(result['excess'], Decimal('50'))

    def test_07_validate_raises(self):
        from eu_audit_guard import EUAuditGuard, EUAuditError
        from datetime import date
        self._entry(date(2026, 5, 1), time(8, 0), time(16, 0), duration=Decimal('200'))
        with self.assertRaises(EUAuditError) as ctx:
            EUAuditGuard.validate_monthly_cap(self.user, 2026, 5, max_hours=Decimal('100'))
        self.assertEqual(ctx.exception.code, 'MONTHLY_CAP_EXCEEDED')


class SignatureTest(EUAuditSetup):
    """MINA 3: Potpisi."""

    def test_08_signed_entries_pass(self):
        from eu_audit_guard import EUAuditGuard
        from datetime import date
        e = self._entry(date(2026, 6, 1), time(8, 0), time(12, 0), approved=True)
        unsigned = EUAuditGuard.validate_signatures([e])
        self.assertEqual(len(unsigned), 0)

    def test_09_unsigned_entry_detected(self):
        from eu_audit_guard import EUAuditGuard
        from datetime import date
        e = self._entry(date(2026, 6, 2), time(8, 0), time(12, 0), approved=False)
        unsigned = EUAuditGuard.validate_signatures([e])
        self.assertEqual(len(unsigned), 1)

    def test_10_strict_raises(self):
        from eu_audit_guard import EUAuditGuard, EUAuditError
        from datetime import date
        e = self._entry(date(2026, 6, 3), time(8, 0), time(12, 0), approved=False)
        with self.assertRaises(EUAuditError) as ctx:
            EUAuditGuard.validate_signatures_strict([e])
        self.assertEqual(ctx.exception.code, 'UNSIGNED_ENTRIES')
