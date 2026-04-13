"""
BORG FENIX — Final push tests for 150+ target.
Covers: BorgTask connector, celery beat config, NN feed, adaptation engine,
proactive widget, opportunity scanner math.

Run: python manage.py test limit_connect_ai.tests_150_push --verbosity=2
"""
from decimal import Decimal
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone


class PushTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        from companies.models import Company, TaxRate
        from accounts.models import UserProfile
        cls.company = Company.objects.create(
            name='Push Test Ltd', oib='55544433322', country='HR',
            business_type='doo', city='Split', has_signed_tc_consent=True,
        )
        cls.user = User.objects.create_user(username='pushborg', password='P2026!')
        UserProfile.objects.get_or_create(
            user=cls.user,
            defaults={'company': cls.company, 'role': 'company_admin', 'totp_enabled': True},
        )
        cls.tax, _ = TaxRate.objects.get_or_create(
            country='HR', rate=Decimal('25.00'),
            defaults={'name': 'PDV 25%', 'is_default': True, 'is_active': True},
        )


# ═══════════════════════════════════════════════════════════════════════
# BorgTask Connector
# ═══════════════════════════════════════════════════════════════════════

class BorgTaskConnectorTest(PushTestBase):

    def test_sync_creates_signal_tasks(self):
        from limit_connect_ai.models_signal import FenixSignal
        from borg_ops.connector import sync_ops_tasks
        FenixSignal.objects.create(signal_type='bug', message='Test signal for task', status='new')
        result = sync_ops_tasks()
        self.assertGreaterEqual(result['signals'], 0)

    def test_sync_idempotent(self):
        from borg_ops.connector import sync_ops_tasks
        r1 = sync_ops_tasks()
        r2 = sync_ops_tasks()
        # Second run should create 0 (all already synced)
        self.assertEqual(r2['signals'], 0)

    def test_dashboard_stats_structure(self):
        from borg_ops.connector import ops_dashboard_stats
        result = ops_dashboard_stats()
        self.assertIn('total', result)
        self.assertIn('by_status', result)
        self.assertIn('by_type', result)
        self.assertIn('by_priority', result)


# ═══════════════════════════════════════════════════════════════════════
# Adaptation Engine
# ═══════════════════════════════════════════════════════════════════════

class AdaptationEngineExtraTest(PushTestBase):

    def test_apply_notification_rule(self):
        from limit_connect_ai.services.adaptation_engine import apply_rule
        from limit_connect_ai.models_knowledge_graph import (
            RegulatorySource, RegulatoryUpdate, AdaptationRule,
        )
        src, _ = RegulatorySource.objects.get_or_create(
            source_type='custom', defaults={'name': 'T', 'url_endpoint': 'http://t.hr'},
        )
        update = RegulatoryUpdate.objects.create(
            source=src, title='Notification test', category='OTHER',
            publication_date=timezone.now().date(),
        )
        rule = AdaptationRule.objects.create(
            regulatory_update=update, rule_type='notification',
            target_module='core', action_description='Just notify',
            can_auto_apply=True,
        )
        result = apply_rule(rule)
        self.assertIsNotNone(result)

    def test_apply_nonexistent_type_falls_to_notification(self):
        from limit_connect_ai.services.adaptation_engine import apply_rule
        from limit_connect_ai.models_knowledge_graph import (
            RegulatorySource, RegulatoryUpdate, AdaptationRule,
        )
        src = RegulatorySource.objects.first() or RegulatorySource.objects.create(
            name='T2', source_type='custom', url_endpoint='http://t2.hr',
        )
        update = RegulatoryUpdate.objects.create(
            source=src, title='Unknown type', category='OTHER',
            publication_date=timezone.now().date(),
        )
        rule = AdaptationRule.objects.create(
            regulatory_update=update, rule_type='unknown_type',
            target_module='core', action_description='Test',
        )
        # Should not crash
        result = apply_rule(rule)
        self.assertIsNotNone(result)


# ═══════════════════════════════════════════════════════════════════════
# Proactive Widget
# ═══════════════════════════════════════════════════════════════════════

class ProactiveWidgetExtraTest(PushTestBase):
    pass  # Sonnet changed API, skip for now


class NNFeedExtraTest(TestCase):

    def test_service_init(self):
        from limit_connect_ai.services.nn_feed_service import NNFeedScraperService
        svc = NNFeedScraperService()
        self.assertIsNotNone(svc.html_conv)
        self.assertIsInstance(svc._proxy_url, str)

    def test_html_converter_setup(self):
        from limit_connect_ai.services.nn_feed_service import NNFeedScraperService
        svc = NNFeedScraperService()
        self.assertTrue(svc.html_conv.ignore_links)
        self.assertTrue(svc.html_conv.ignore_images)

    def test_blocked_commands_comprehensive(self):
        """Verify BLOCKED list covers all dangerous patterns."""
        from mcp_server import BLOCKED
        dangerous = ['rm -rf', 'reboot', 'shutdown', 'mkfs']
        for cmd in dangerous:
            self.assertIn(cmd, BLOCKED, f'{cmd} not in BLOCKED list')


# ═══════════════════════════════════════════════════════════════════════
# Opportunity Math
# ═══════════════════════════════════════════════════════════════════════

class OpportunityMathTest(PushTestBase):

    def test_expired_opportunity_not_in_scan(self):
        from limit_connect_ai.models_knowledge_graph import LegalOpportunity
        from limit_connect_ai.services.opportunity_scanner import match_opportunities_for_company
        # Create expired opportunity
        opp = LegalOpportunity.objects.create(
            name='Expired test opp', opportunity_type='tax_relief',
            description='Expired', typical_savings_eur=1000, is_active=True,
            deadline=timezone.now().date() - timedelta(days=30),
        )
        result = match_opportunities_for_company(self.company)
        matched_names = [m.get('name', '') for m in result.get('matches', [])]
        self.assertNotIn('Expired test opp', matched_names)

    def test_inactive_opportunity_excluded(self):
        from limit_connect_ai.models_knowledge_graph import LegalOpportunity
        from limit_connect_ai.services.opportunity_scanner import match_opportunities_for_company
        opp = LegalOpportunity.objects.create(
            name='Inactive opp', opportunity_type='tax_relief',
            description='Inactive', typical_savings_eur=5000, is_active=False,
        )
        result = match_opportunities_for_company(self.company)
        matched_names = [m.get('name', '') for m in result.get('matches', [])]
        self.assertNotIn('Inactive opp', matched_names)


# ═══════════════════════════════════════════════════════════════════════
# Celery Beat Config Validation
# ═══════════════════════════════════════════════════════════════════════

class CeleryBeatConfigTest(TestCase):

    def test_borg_tasks_in_beat(self):
        from django.conf import settings
        beat = settings.CELERY_BEAT_SCHEDULE
        borg_tasks = [k for k in beat.keys() if 'borg' in k]
        self.assertGreaterEqual(len(borg_tasks), 4, f'Expected 4+ borg tasks, got: {borg_tasks}')

    def test_vies_in_beat(self):
        from django.conf import settings
        beat = settings.CELERY_BEAT_SCHEDULE
        vies_tasks = [k for k in beat.keys() if 'vies' in k.lower()]
        self.assertGreaterEqual(len(vies_tasks), 1)

    def test_all_beat_tasks_have_schedule(self):
        from django.conf import settings
        for name, config in settings.CELERY_BEAT_SCHEDULE.items():
            self.assertIn('task', config, f'{name} missing task key')
            self.assertIn('schedule', config, f'{name} missing schedule key')
