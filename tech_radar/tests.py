"""Tech Radar — 8+ testova za model, threshold, task."""
import json
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model

User = get_user_model()


class TechSignalModelTest(TestCase):
    def test_01_create_signal(self):
        from tech_radar.models import TechSignal
        s = TechSignal.objects.create(
            db_size_mb=Decimal('150.5'),
            disk_used_pct=Decimal('42.3'),
            memory_used_pct=Decimal('65.0'),
            cpu_load_1m=Decimal('1.25'),
        )
        self.assertIsNotNone(s.pk)
        self.assertEqual(s.severity, 'ok')

    def test_02_signal_str(self):
        from tech_radar.models import TechSignal
        s = TechSignal.objects.create(
            db_size_mb=Decimal('200'),
            disk_used_pct=Decimal('80'),
            memory_used_pct=Decimal('70'),
        )
        self.assertIn('200', str(s))
        self.assertIn('80', str(s))

    def test_03_signal_ordering(self):
        from tech_radar.models import TechSignal
        s1 = TechSignal.objects.create(db_size_mb=1)
        s2 = TechSignal.objects.create(db_size_mb=2)
        signals = list(TechSignal.objects.all())
        self.assertEqual(signals[0].db_size_mb, Decimal('2'))  # newest first

    def test_04_signal_alerts_json(self):
        from tech_radar.models import TechSignal
        s = TechSignal.objects.create(
            alerts=['disk_used_pct: warning', 'ram: critical'],
            severity='critical',
        )
        s.refresh_from_db()
        self.assertEqual(len(s.alerts), 2)
        self.assertEqual(s.severity, 'critical')


class CapacityThresholdTest(TestCase):
    def test_05_create_threshold(self):
        from tech_radar.models import CapacityThreshold
        t = CapacityThreshold.objects.create(
            metric='disk_used_pct',
            warning_value=Decimal('80'),
            critical_value=Decimal('90'),
        )
        self.assertTrue(t.is_active)

    def test_06_check_metric_ok(self):
        from tech_radar.models import CapacityThreshold
        CapacityThreshold.objects.create(
            metric='test_metric', warning_value=80, critical_value=90,
        )
        self.assertEqual(CapacityThreshold.check_metric('test_metric', Decimal('50')), 'ok')

    def test_07_check_metric_warning(self):
        from tech_radar.models import CapacityThreshold
        CapacityThreshold.objects.create(
            metric='test_warn', warning_value=80, critical_value=90,
        )
        self.assertEqual(CapacityThreshold.check_metric('test_warn', Decimal('85')), 'warning')

    def test_08_check_metric_critical(self):
        from tech_radar.models import CapacityThreshold
        CapacityThreshold.objects.create(
            metric='test_crit', warning_value=80, critical_value=90,
        )
        self.assertEqual(CapacityThreshold.check_metric('test_crit', Decimal('95')), 'critical')

    def test_09_check_unknown_metric(self):
        from tech_radar.models import CapacityThreshold
        self.assertEqual(CapacityThreshold.check_metric('nonexistent', Decimal('999')), 'ok')

    def test_10_inactive_threshold_ignored(self):
        from tech_radar.models import CapacityThreshold
        CapacityThreshold.objects.create(
            metric='test_inactive', warning_value=10, critical_value=20,
            is_active=False,
        )
        self.assertEqual(CapacityThreshold.check_metric('test_inactive', Decimal('999')), 'ok')


class TaskImportTest(TestCase):
    def test_11_tasks_importable(self):
        from tech_radar.tasks import tech_radar_scan, capacity_check, cleanup_signals
        self.assertEqual(tech_radar_scan.name, 'tech_radar.tasks.tech_radar_scan')
        self.assertEqual(capacity_check.name, 'tech_radar.tasks.capacity_check')
        self.assertEqual(cleanup_signals.name, 'tech_radar.tasks.cleanup_signals')
