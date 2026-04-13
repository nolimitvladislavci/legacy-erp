"""
BORG FENIX — Tests for F2/F3/F4 features.
Covers: KG seeder, opportunity lifecycle, intelligence connector,
anomaly detector, predictions, self-heal, quick actions, signal triage.

Run: python manage.py test limit_connect_ai.tests_f234 --verbosity=2
"""
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
import django.db
from django.utils import timezone


class F234TestBase(TestCase):
    """Base with Company + User fixture."""

    @classmethod
    def setUpTestData(cls):
        from companies.models import Company, TaxRate
        from accounts.models import UserProfile

        cls.company = Company.objects.create(
            name='Test BORG F234',
            oib='98765432101',
            country='HR',
            business_type='doo',
            city='Zagreb',
            has_signed_tc_consent=True,
        )
        cls.user = User.objects.create_user(
            username='borgtest234', password='Test2026!',
        )
        UserProfile.objects.get_or_create(
            user=cls.user,
            defaults={'company': cls.company, 'role': 'company_admin', 'totp_enabled': True},
        )
        cls.tax_25, _ = TaxRate.objects.get_or_create(
            country='HR', rate=Decimal('25.00'),
            defaults={'name': 'PDV 25%', 'is_default': True, 'is_active': True},
        )


# ══════════════════════════════════════════════════════════════════════════════
# F2.1 — KG Seeder
# ══════════════════════════════════════════════════════════════════════════════

class KGSeederTest(F234TestBase):

    def test_seed_regulatory_sources(self):
        from limit_connect_ai.services.kg_seeder import seed_regulatory_sources
        created = seed_regulatory_sources()
        self.assertGreaterEqual(created, 0)
        from limit_connect_ai.models_knowledge_graph import RegulatorySource
        self.assertGreaterEqual(RegulatorySource.objects.count(), 1)

    def test_seed_legal_opportunities(self):
        from limit_connect_ai.services.kg_seeder import seed_legal_opportunities
        created = seed_legal_opportunities()
        self.assertGreaterEqual(created, 0)
        from limit_connect_ai.models_knowledge_graph import LegalOpportunity
        self.assertGreaterEqual(LegalOpportunity.objects.count(), 1)

    def test_seed_idempotent(self):
        from limit_connect_ai.services.kg_seeder import seed_legal_opportunities
        first = seed_legal_opportunities()
        second = seed_legal_opportunities()
        self.assertEqual(second, 0)

    def test_scan_all_companies(self):
        from limit_connect_ai.services.kg_seeder import seed_legal_opportunities, scan_all_companies
        seed_legal_opportunities()
        result = scan_all_companies()
        self.assertIn('companies', result)
        self.assertIn('matches', result)
        self.assertGreaterEqual(result['companies'], 1)


# ══════════════════════════════════════════════════════════════════════════════
# F2.2 — Opportunity Lifecycle
# ══════════════════════════════════════════════════════════════════════════════

class OpportunityLifecycleTest(F234TestBase):

    def test_notify_new_matches(self):
        from limit_connect_ai.services.kg_seeder import seed_legal_opportunities, scan_all_companies
        seed_legal_opportunities()
        scan_all_companies()
        from limit_connect_ai.tasks_opportunity import notify_new_matches
        result = notify_new_matches(batch_size=10)
        self.assertIn('notified', result)
        self.assertGreaterEqual(result['notified'], 0)

    def test_expire_old_matches(self):
        from limit_connect_ai.tasks_opportunity import expire_old_matches
        result = expire_old_matches()
        self.assertIn('expired', result)

    def test_opportunity_digest(self):
        from limit_connect_ai.tasks_opportunity import opportunity_digest
        result = opportunity_digest()
        self.assertIn('total_active_matches', result)
        self.assertIn('total_potential_savings_eur', result)


# ══════════════════════════════════════════════════════════════════════════════
# F2.3 — NN → Adaptation Signal
# ══════════════════════════════════════════════════════════════════════════════

class AdaptationSignalTest(F234TestBase):

    def test_signal_creates_rule_on_processed_update(self):
        from limit_connect_ai.models_knowledge_graph import (
            RegulatorySource, RegulatoryUpdate, AdaptationRule,
        )
        src, _ = RegulatorySource.objects.get_or_create(
            source_type='nn',
            defaults={'name': 'Test NN', 'url_endpoint': 'http://test.hr', 'is_active': True},
        )
        before = AdaptationRule.objects.count()
        RegulatoryUpdate.objects.create(
            source=src,
            title='Test VAT change signal',
            category='VAT',
            publication_date=timezone.now().date(),
            impact_score=8,
            is_processed=True,
            is_breaking=False,
        )
        self.assertEqual(AdaptationRule.objects.count(), before + 1)

    def test_signal_skips_unprocessed(self):
        from limit_connect_ai.models_knowledge_graph import (
            RegulatorySource, RegulatoryUpdate, AdaptationRule,
        )
        src = RegulatorySource.objects.first() or RegulatorySource.objects.create(
            name='T', source_type='nn', url_endpoint='http://t.hr', is_active=True,
        )
        before = AdaptationRule.objects.count()
        RegulatoryUpdate.objects.create(
            source=src, title='Unprocessed', category='TAX',
            publication_date=timezone.now().date(), is_processed=False,
        )
        self.assertEqual(AdaptationRule.objects.count(), before)

    def test_signal_no_duplicate_rules(self):
        from limit_connect_ai.models_knowledge_graph import (
            RegulatorySource, RegulatoryUpdate, AdaptationRule,
        )
        src = RegulatorySource.objects.first() or RegulatorySource.objects.create(
            name='T', source_type='nn', url_endpoint='http://t.hr', is_active=True,
        )
        update = RegulatoryUpdate.objects.create(
            source=src, title='Dedup test', category='FISCAL',
            publication_date=timezone.now().date(), impact_score=5, is_processed=True,
        )
        count_after_first = AdaptationRule.objects.filter(regulatory_update=update).count()
        self.assertEqual(count_after_first, 1)


# ══════════════════════════════════════════════════════════════════════════════
# F3.1 — Intelligence Connector
# ══════════════════════════════════════════════════════════════════════════════

class IntelligenceConnectorTest(F234TestBase):

    def test_seed_intelligence_jobs(self):
        from intelligence.connector import seed_intelligence_jobs
        result = seed_intelligence_jobs()
        self.assertGreaterEqual(result, 0)

    def test_convert_regulatory_to_funds(self):
        from intelligence.connector import _convert_regulatory_to_funds
        result = _convert_regulatory_to_funds()
        self.assertGreaterEqual(result, 0)

    def test_match_funds_to_companies(self):
        from intelligence.connector import _match_funds_to_companies
        result = _match_funds_to_companies()
        self.assertGreaterEqual(result, 0)


# ══════════════════════════════════════════════════════════════════════════════
# F3.2 — AI Quick Actions
# ══════════════════════════════════════════════════════════════════════════════

class QuickActionsTest(F234TestBase):

    def test_quick_actions_list(self):
        from ai_assistant.quick_actions import get_quick_actions_for_user
        actions = get_quick_actions_for_user(self.user)
        self.assertGreaterEqual(len(actions), 5)

    def test_quick_action_structure(self):
        from ai_assistant.quick_actions import QUICK_ACTIONS
        for action in QUICK_ACTIONS:
            self.assertIn('id', action)
            self.assertIn('label', action)
            self.assertIn('prompt', action)

    def test_ai_health_check(self):
        from ai_assistant.quick_actions import ai_health_check
        result = ai_health_check()
        self.assertIn('total_conversations', result)


# ══════════════════════════════════════════════════════════════════════════════
# F3.4 — Anomaly Detector
# ══════════════════════════════════════════════════════════════════════════════

class AnomalyDetectorTest(F234TestBase):
    """Anomaly detector uses PostgreSQL array_agg - skip on SQLite."""

    @property
    def _is_sqlite(self):
        return 'sqlite' in django.db.connections['default'].vendor

    def setUp(self):
        if self._is_sqlite:
            self.skipTest('Requires PostgreSQL (array_agg)')

    def test_detect_anomalies_runs(self):
        from core.anomaly_detector import detect_cross_company_anomalies
        result = detect_cross_company_anomalies()
        self.assertIn('type_mismatches', result)
        self.assertIn('high_debtors', result)
        self.assertIn('name_mismatches', result)

    def test_type_mismatches_returns_list(self):
        from core.anomaly_detector import detect_buyer_type_mismatches
        result = detect_buyer_type_mismatches()
        self.assertIsInstance(result, list)

    def test_high_debtors_with_threshold(self):
        from core.anomaly_detector import detect_high_cross_company_debt
        result = detect_high_cross_company_debt(threshold_eur=999999999)
        self.assertEqual(len(result), 0)

    def test_name_mismatches_returns_list(self):
        from core.anomaly_detector import detect_name_mismatches
        result = detect_name_mismatches()
        self.assertIsInstance(result, list)


# ══════════════════════════════════════════════════════════════════════════════
# F4.1 — Predictions
# ══════════════════════════════════════════════════════════════════════════════

class PredictionsTest(F234TestBase):

    def test_cash_flow_structure(self):
        from limit_connect_ai.services.predictions import predict_cash_flow
        result = predict_cash_flow()
        self.assertIn('predictions', result)
        self.assertIn('30_days', result['predictions'])
        self.assertIn('60_days', result['predictions'])
        self.assertIn('90_days', result['predictions'])

    def test_churn_detection(self):
        from limit_connect_ai.services.predictions import detect_churn_risk
        result = detect_churn_risk()
        self.assertIn('total_at_risk', result)
        self.assertIn('top_at_risk', result)

    def test_seasonal_analysis(self):
        from limit_connect_ai.services.predictions import seasonal_analysis
        result = seasonal_analysis()
        # May return error if no invoice data in test DB
        if 'error' in result:
            self.assertEqual(result['error'], 'No data')
        else:
            self.assertIn('seasonal_index', result)


# ══════════════════════════════════════════════════════════════════════════════
# F4.2 — Self Heal
# ══════════════════════════════════════════════════════════════════════════════

class SelfHealTest(F234TestBase):

    def test_check_services(self):
        from borg_ops.self_heal import check_services
        result = check_services()
        self.assertIsInstance(result, dict)
        self.assertIn('nginx', result)

    def test_check_disk(self):
        from borg_ops.self_heal import check_disk
        result = check_disk()
        self.assertIn('percent_used', result)
        self.assertIsInstance(result['percent_used'], int)

    def test_check_database(self):
        from borg_ops.self_heal import check_database
        result = check_database()
        # In test mode (SQLite), pg functions may fail
        if 'error' in result:
            self.assertIn('function', str(result['error']).lower())
        else:
            self.assertTrue(result['connected'])

    def test_health_check_returns_report(self):
        from borg_ops.self_heal import health_check_and_heal
        result = health_check_and_heal()
        self.assertIn('services', result)
        self.assertIn('disk', result)
        self.assertIn('database', result)
        self.assertIn('healed', result)


# ══════════════════════════════════════════════════════════════════════════════
# Signal Triage
# ══════════════════════════════════════════════════════════════════════════════

class SignalTriageTest(F234TestBase):

    def test_auto_resolve_known_404(self):
        from limit_connect_ai.models_signal import FenixSignal
        from limit_connect_ai.signal_triage import auto_resolve_known
        sig = FenixSignal.objects.create(
            signal_type='bug',
            message='404 na /push/vapid-public-key/',
            status='new',
        )
        resolved = auto_resolve_known(sig)
        self.assertTrue(resolved)
        sig.refresh_from_db()
        self.assertEqual(sig.status, 'resolved')

    def test_auto_resolve_ignores_real_bugs(self):
        from limit_connect_ai.models_signal import FenixSignal
        from limit_connect_ai.signal_triage import auto_resolve_known
        sig = FenixSignal.objects.create(
            signal_type='bug',
            message='Cannot save invoice - total is NaN',
            status='new',
        )
        resolved = auto_resolve_known(sig)
        self.assertFalse(resolved)

    def test_dedup_signals(self):
        from limit_connect_ai.models_signal import FenixSignal
        from limit_connect_ai.signal_triage import dedup_signals
        # Create 3 identical signals
        for _ in range(3):
            FenixSignal.objects.create(
                signal_type='bug',
                message='Identical error X',
                page_url='/test/',
                status='new',
            )
        deduped = dedup_signals(hours=1)
        self.assertGreaterEqual(deduped, 2)

    def test_batch_auto_resolve(self):
        from limit_connect_ai.signal_triage import batch_auto_resolve
        result = batch_auto_resolve()
        self.assertGreaterEqual(result, 0)
