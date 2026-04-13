"""
worktime/tests/test_anomaly_tracker.py
Tests for AnomalyReport model, UniversalTracker, and patrol task.
"""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

User = get_user_model()


class AnomalyReportModelTest(TestCase):
    """Test AnomalyReport model CRUD and constraints."""

    @classmethod
    def setUpTestData(cls):
        from companies.models import Company
        cls.company = Company.objects.create(name='Test Firma', oib='12345678901')
        cls.user = User.objects.create_user(
            username='testradnik', password='test1234',
            first_name='Test', last_name='Radnik'
        )

    def test_create_anomaly_report(self):
        from worktime.models import AnomalyReport
        report = AnomalyReport.objects.create(
            user=self.user,
            company=self.company,
            anomaly_type='GHOST_SHIFT',
            severity='high',
            description='Smjena otvorena 08:00 bez POS aktivnosti',
            ai_confidence=Decimal('85.50'),
        )
        self.assertEqual(report.anomaly_type, 'GHOST_SHIFT')
        self.assertEqual(report.severity, 'high')
        self.assertFalse(report.is_resolved)
        self.assertIsNotNone(report.detected_at)
        self.assertIn('GHOST_SHIFT', str(report))

    def test_resolve_anomaly(self):
        from worktime.models import AnomalyReport
        report = AnomalyReport.objects.create(
            user=self.user,
            company=self.company,
            anomaly_type='MISSING_BREAK',
            severity='medium',
            description='6.5h rada bez pauze',
            ai_confidence=Decimal('75.00'),
        )
        report.is_resolved = True
        report.resolved_by = self.user
        report.resolution_note = 'Radnik je imao pauzu ali nije evidentirao'
        report.save()
        report.refresh_from_db()
        self.assertTrue(report.is_resolved)
        self.assertEqual(report.resolved_by, self.user)

    def test_anomaly_without_timelog(self):
        from worktime.models import AnomalyReport
        report = AnomalyReport.objects.create(
            user=self.user,
            anomaly_type='OVERTIME',
            severity='low',
            description='Test bez TimeLog veze',
        )
        self.assertIsNone(report.time_log)

    def test_anomaly_with_timelog(self):
        from worktime.models import AnomalyReport, TimeLog
        tl = TimeLog.objects.create(
            user=self.user, company=self.company,
            start_time=timezone.now() - timedelta(hours=14),
            date=timezone.now().date(),
        )
        report = AnomalyReport.objects.create(
            user=self.user,
            company=self.company,
            time_log=tl,
            anomaly_type='GHOST_SHIFT',
            severity='high',
            description='Ghost shift test',
        )
        self.assertEqual(tl.anomalies.count(), 1)
        self.assertEqual(tl.anomalies.first(), report)

    def test_all_anomaly_types_valid(self):
        from worktime.models import AnomalyReport
        for atype, label in AnomalyReport.ANOMALY_TYPES:
            report = AnomalyReport(
                user=self.user,
                anomaly_type=atype,
                severity='low',
                description='test %s' % atype,
            )
            report.full_clean()

    def test_all_severity_levels_valid(self):
        from worktime.models import AnomalyReport
        for sev, label in AnomalyReport.SEVERITY_CHOICES:
            report = AnomalyReport(
                user=self.user,
                anomaly_type='GHOST_SHIFT',
                severity=sev,
                description='test %s' % sev,
            )
            report.full_clean()


class ActivityEventPOSChoicesTest(TestCase):
    """Test that POS and INV action choices are available."""

    def test_pos_choices_exist(self):
        from worktime.models import ActivityEvent
        choice_keys = [c[0] for c in ActivityEvent.ACTION_CHOICES]
        self.assertIn('POS_CHECKOUT', choice_keys)
        self.assertIn('POS_VOID', choice_keys)
        self.assertIn('POS_OPEN_SHIFT', choice_keys)
        self.assertIn('POS_CLOSE_SHIFT', choice_keys)

    def test_inv_choices_exist(self):
        from worktime.models import ActivityEvent
        choice_keys = [c[0] for c in ActivityEvent.ACTION_CHOICES]
        self.assertIn('GOODS_RECEIPT', choice_keys)
        self.assertIn('TRANSFER_OUT', choice_keys)
        self.assertIn('INVENTURA_COMPLETE', choice_keys)
        self.assertIn('ARCHIVE_UPLOAD', choice_keys)

    def test_create_pos_event(self):
        from companies.models import Company
        from worktime.models import ActivityEvent
        company = Company.objects.create(name='POS Test', oib='99999999901')
        user = User.objects.create_user(username='blagajnik', password='test')
        event = ActivityEvent.objects.create(
            company=company,
            user=user,
            timestamp=timezone.now(),
            action='POS_CHECKOUT',
            detail='Bon #42',
            metadata={'receipt_id': 123, 'total': '25.50'},
        )
        self.assertEqual(event.action, 'POS_CHECKOUT')
        self.assertEqual(event.metadata['total'], '25.50')


class UniversalTrackerTest(TransactionTestCase):
    """Test the worktime.tracker.track() function."""

    def setUp(self):
        from companies.models import Company
        self.company = Company.objects.create(name='Tracker Test', oib='11111111101')
        self.user = User.objects.create_user(username='tracker_user', password='test')

    def test_track_creates_event(self):
        from worktime.models import ActivityEvent
        from worktime.tracker import track
        track(self.user, 'POS', 'POS_CHECKOUT', ref='Bon #1',
              detail='Test naplata', company=self.company)
        self.assertEqual(ActivityEvent.objects.count(), 1)
        event = ActivityEvent.objects.first()
        self.assertEqual(event.action, 'POS_CHECKOUT')
        self.assertIn('POS', event.detail)
        self.assertEqual(event.metadata['module'], 'POS')
        self.assertEqual(event.metadata['ref'], 'Bon #1')

    def test_track_ignores_anonymous(self):
        from worktime.models import ActivityEvent
        from worktime.tracker import track
        anon = MagicMock()
        anon.is_authenticated = False
        track(anon, 'POS', 'POS_CHECKOUT')
        self.assertEqual(ActivityEvent.objects.count(), 0)

    def test_track_never_raises(self):
        from worktime.tracker import track
        track(None, 'POS', 'POS_CHECKOUT')
        track(self.user, 'POS', 'INVALID_ACTION_THAT_IS_WAY_TOO_LONG_FOR_DB')


class AnomalyPatrolTaskTest(TestCase):
    """Test the nightly anomaly patrol task."""

    @classmethod
    def setUpTestData(cls):
        from companies.models import Company
        cls.company = Company.objects.create(name='Patrol Test', oib='22222222201')
        cls.user = User.objects.create_user(username='patrol_user', password='test')
        cls.admin = User.objects.create_superuser(
            username='admin_patrol', password='admin1234', email='admin@test.com'
        )

    def test_patrol_no_alerts(self):
        from worktime.tasks import worktime_anomaly_patrol
        result = worktime_anomaly_patrol()
        self.assertEqual(result['alerts'], 0)

    def test_patrol_detects_ghost_shift(self):
        from worktime.models import AnomalyReport, TimeLog
        from worktime.tasks import worktime_anomaly_patrol
        TimeLog.objects.create(
            user=self.user, company=self.company,
            start_time=timezone.now() - timedelta(hours=14),
            date=timezone.now().date(),
            status='OPEN',
        )
        result = worktime_anomaly_patrol()
        self.assertGreaterEqual(result['alerts'], 1)
        self.assertGreaterEqual(result['created'], 1)
        report = AnomalyReport.objects.filter(anomaly_type='GHOST_SHIFT').first()
        self.assertIsNotNone(report)
        self.assertEqual(report.severity, 'high')
        self.assertEqual(report.user, self.user)

    def test_patrol_detects_missing_break(self):
        from worktime.models import AnomalyReport, TimeLog
        from worktime.tasks import worktime_anomaly_patrol
        yesterday = timezone.now() - timedelta(days=1)
        TimeLog.objects.create(
            user=self.user, company=self.company,
            start_time=yesterday,
            end_time=yesterday + timedelta(hours=8),
            date=yesterday.date(),
            status='CLOSED',
            gross_hours=Decimal('8.00'),
            break_minutes=0,
            payable_hours=Decimal('7.25'),
        )
        result = worktime_anomaly_patrol()
        self.assertGreaterEqual(result['alerts'], 1)
        report = AnomalyReport.objects.filter(anomaly_type='MISSING_BREAK').first()
        self.assertIsNotNone(report)
        self.assertEqual(report.severity, 'medium')

    def test_patrol_skips_shift_with_pos_activity(self):
        from worktime.models import ActivityEvent, AnomalyReport, TimeLog
        from worktime.tasks import worktime_anomaly_patrol
        TimeLog.objects.create(
            user=self.user, company=self.company,
            start_time=timezone.now() - timedelta(hours=14),
            date=timezone.now().date(),
            status='OPEN',
        )
        ActivityEvent.objects.create(
            user=self.user, company=self.company,
            timestamp=timezone.now() - timedelta(hours=2),
            action='POS_CHECKOUT',
            detail='Bon #99',
        )
        result = worktime_anomaly_patrol()
        ghost_reports = AnomalyReport.objects.filter(
            anomaly_type='GHOST_SHIFT', user=self.user
        ).count()
        self.assertEqual(ghost_reports, 0)

    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': ''})
    def test_patrol_ai_failure_graceful(self):
        from worktime.models import TimeLog
        from worktime.tasks import worktime_anomaly_patrol
        TimeLog.objects.create(
            user=self.user, company=self.company,
            start_time=timezone.now() - timedelta(hours=14),
            date=timezone.now().date(),
            status='OPEN',
        )
        result = worktime_anomaly_patrol()
        self.assertGreaterEqual(result['alerts'], 1)
