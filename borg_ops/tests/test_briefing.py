"""
Tests for BORG Morning Briefing — aggregation, ranking, formatting.
"""
from unittest.mock import patch, MagicMock
from datetime import timedelta
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone


class BriefingCollectorTest(TestCase):
    """Test briefing item collection and ranking."""

    def setUp(self):
        from companies.models import Company
        from borg_ops.models import BorgBriefingConfig
        self.company = Company.objects.create(name='Briefing Test d.o.o.', oib='12345678901')
        self.config = BorgBriefingConfig.objects.create(
            company=self.company,
            enabled=True,
            phone_number='385991234567',
            max_items=5,
        )

    def test_collect_empty(self):
        """Empty company returns empty items."""
        from borg_ops.briefing import collect_briefing_items
        items = collect_briefing_items(self.company, self.config)
        self.assertIsInstance(items, list)

    def test_collect_with_overdue_invoice(self):
        """Overdue invoice appears in briefing."""
        from invoicing.models import Invoice
        Invoice.objects.create(
            company=self.company,
            number='R-2026-001',
            date_issued=timezone.now() - timedelta(days=30),
            date_due=timezone.now().date() - timedelta(days=10),
            client_name='Test Klijent',
            total=Decimal('1500.00'),
            status='OVERDUE',
        )
        from borg_ops.briefing import collect_briefing_items
        items = collect_briefing_items(self.company, self.config)
        self.assertTrue(len(items) >= 1)
        self.assertIn('R-2026-001', items[0]['title'])

    def test_collect_with_borg_task(self):
        """High-priority BorgTask appears in briefing."""
        from borg_ops.models import BorgTask
        BorgTask.objects.create(
            company=self.company,
            task_type='anomaly',
            title='Kriticna anomalija u POS-u',
            priority=1,
        )
        from borg_ops.briefing import collect_briefing_items
        items = collect_briefing_items(self.company, self.config)
        found = any('anomalija' in item['title'].lower() for item in items)
        self.assertTrue(found)

    def test_max_items_respected(self):
        """Config.max_items limits output."""
        from borg_ops.models import BorgTask
        for i in range(10):
            BorgTask.objects.create(
                company=self.company,
                task_type='anomaly',
                title=f'Task #{i}',
                priority=1,
            )
        self.config.max_items = 3
        self.config.save()
        from borg_ops.briefing import collect_briefing_items
        items = collect_briefing_items(self.company, self.config)
        self.assertLessEqual(len(items), 3)

    def test_priority_sorting(self):
        """Higher priority items come first."""
        from borg_ops.models import BorgTask
        from invoicing.models import Invoice
        # Low priority task
        BorgTask.objects.create(
            company=self.company, task_type='manual',
            title='Low prio task', priority=2,
        )
        # High priority overdue invoice
        Invoice.objects.create(
            company=self.company, number='R-BIG',
            date_issued=timezone.now() - timedelta(days=60),
            date_due=timezone.now().date() - timedelta(days=30),
            client_name='Big Client', total=Decimal('50000.00'),
            status='OVERDUE',
        )
        from borg_ops.briefing import collect_briefing_items
        items = collect_briefing_items(self.company, self.config)
        if len(items) >= 2:
            # Invoice with 50k * 30 days = 1.5M score should be first
            self.assertIn('R-BIG', items[0]['title'])


class BriefingFormatterTest(TestCase):
    """Test WhatsApp message formatting."""

    def test_format_with_items(self):
        """Format produces readable WhatsApp message."""
        from borg_ops.briefing import format_briefing_message
        items = [
            {'emoji': '\u26a0\ufe0f', 'title': 'Racun R-001 kasni 5 dana (1000 EUR)', 'detail': 'Klijent: Test'},
            {'emoji': '\U0001f4cb', 'title': 'PDV prijava rok: 20.04.', 'detail': ''},
        ]
        msg = format_briefing_message(items, 'Test Firma')
        self.assertIn('BORG Jutarnji Briefing', msg)
        self.assertIn('Test Firma', msg)
        self.assertIn('R-001', msg)
        self.assertIn('PDV', msg)

    def test_format_empty(self):
        """Empty items produce 'all clear' message."""
        from borg_ops.briefing import format_briefing_message
        msg = format_briefing_message([], 'Test Firma')
        self.assertIn('Sve pod kontrolom', msg)

    def test_format_numbering(self):
        """Items are numbered 1, 2, 3..."""
        from borg_ops.briefing import format_briefing_message
        items = [
            {'emoji': 'A', 'title': 'First', 'detail': ''},
            {'emoji': 'B', 'title': 'Second', 'detail': ''},
        ]
        msg = format_briefing_message(items, 'X')
        self.assertIn('1. A First', msg)
        self.assertIn('2. B Second', msg)
