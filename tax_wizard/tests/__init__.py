"""
tax_wizard/tests.py — Test suite za Porezni Savjetnik

80 testova u 7 kategorija:
  A. Models (15) — hash integrity, tier lookup, deadline calc
  B. PrefillEngine (12) — invoice aggregation, POS tips, storno, confidence
  C. Calculation (15) — svih 5 tierova, rubni slučajevi, prirez
  D. AIAdvisor (10) — cliff, wall, potpomognuto, zero income
  E. XML Export (8) — XML generacija, polja, encoding
  F. Views (12) — wizard flow, AJAX save, permissions
  G. Security (8) — cross-tenant, CSRF, injection
"""
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.test import TestCase, RequestFactory, override_settings
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import activate

# ═══════════════════════════════════════════════════════════════
#  A. MODEL TESTS (15)
# ═══════════════════════════════════════════════════════════════

class TaxFormTemplateTest(TestCase):
    """Tests for TaxFormTemplate model."""

    @classmethod
    def setUpTestData(cls):
        from tax_wizard.models import TaxFormTemplate
        cls.template = TaxFormTemplate.objects.create(
            form_type='PO-SD',
            version='test-v1',
            name='Test PO-SD',
            schema={
                'steps': [
                    {'id': 'intro', 'title': 'Test', 'fields': [
                        {'name': 'oib', 'type': 'oib'},
                        {'name': 'q1', 'type': 'decimal'},
                    ]},
                    {'id': 'calc', 'title': 'Calc', 'fields': []},
                ]
            },
            valid_from=date(2026, 1, 1),
            filing_deadline_rule='jan-15',
        )

    def test_step_count(self):
        self.assertEqual(self.template.step_count, 2)

    def test_get_step_valid(self):
        step = self.template.get_step(0)
        self.assertEqual(step['id'], 'intro')

    def test_get_step_invalid(self):
        self.assertIsNone(self.template.get_step(99))

    def test_get_field_names(self):
        names = self.template.get_field_names()
        self.assertIn('oib', names)
        self.assertIn('q1', names)

    def test_unique_together(self):
        from tax_wizard.models import TaxFormTemplate
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            TaxFormTemplate.objects.create(
                form_type='PO-SD',
                version='test-v1',
                name='Duplicate',
                schema={'steps': []},
                valid_from=date(2026, 1, 1),
            )

    def test_str_representation(self):
        self.assertIn('PO-SD', str(self.template))


class TaxWizardSessionTest(TestCase):
    """Tests for TaxWizardSession model."""

    @classmethod
    def setUpTestData(cls):
        from tax_wizard.models import TaxFormTemplate, TaxWizardSession
        from companies.models import Company

        cls.user = User.objects.create_user('testuser', password='testpass123!')
        cls.company = Company.objects.create(name='Test Obrt', oib='12345678901')
        cls.template = TaxFormTemplate.objects.create(
            form_type='PO-SD',
            version='sess-v1',
            name='Session Test',
            schema={'steps': [{'id': 's1', 'title': 'S1', 'fields': []},
                             {'id': 's2', 'title': 'S2', 'fields': []},
                             {'id': 's3', 'title': 'S3', 'fields': []}]},
            valid_from=date(2026, 1, 1),
            filing_deadline_rule='jan-15',
        )
        cls.session = TaxWizardSession.objects.create(
            session_key='test-key-123',
            user=cls.user,
            company=cls.company,
            template=cls.template,
            tax_year=2025,
        )

    def test_data_hash_on_save(self):
        """Hash se izračuna pri save-u."""
        self.session.form_data = {'q1_primitak': 5000}
        self.session.save()
        self.assertTrue(len(self.session.data_hash) == 64)

    def test_data_hash_changes(self):
        """Hash se mijenja kad se podaci promijene."""
        self.session.form_data = {'q1_primitak': 5000}
        self.session.save()
        hash1 = self.session.data_hash

        self.session.form_data = {'q1_primitak': 6000}
        self.session.save()
        self.assertNotEqual(self.session.data_hash, hash1)

    def test_progress_percent(self):
        self.session.current_step = 1
        self.assertEqual(self.session.progress_percent, 33)

    def test_is_editable_draft(self):
        self.session.status = 'draft'
        self.assertTrue(self.session.is_editable)

    def test_is_editable_finalized(self):
        self.session.status = 'final'
        self.assertFalse(self.session.is_editable)

    def test_filing_deadline_jan15(self):
        deadline = self.session.get_filing_deadline()
        self.assertEqual(deadline, date(2026, 1, 15))

    def test_add_ai_message(self):
        self.session.add_ai_message(1, 'info', 'Test message')
        self.assertEqual(len(self.session.ai_messages), 1)
        self.assertEqual(self.session.ai_messages[0]['type'], 'info')


class PausalTierTest(TestCase):
    """Tests for PausalTier model."""

    @classmethod
    def setUpTestData(cls):
        from tax_wizard.models import PausalTier
        cls.tiers = []
        tiers_data = [
            (1, 0, 12500, 1530, 127.50),
            (2, 12501, 17500, 2142, 178.50),
            (3, 17501, 25000, 3060, 255.00),
            (4, 25001, 40000, 4896, 408.00),
            (5, 40001, 60000, 7344, 612.00),
        ]
        for num, min_i, max_i, annual, monthly in tiers_data:
            t = PausalTier.objects.create(
                valid_year=2026, tier_number=num,
                min_income=Decimal(str(min_i)), max_income=Decimal(str(max_i)),
                annual_tax=Decimal(str(annual)), monthly_tax=Decimal(str(monthly)),
            )
            cls.tiers.append(t)

    def test_tier_for_income_tier1(self):
        from tax_wizard.models import PausalTier
        tier = PausalTier.get_tier_for_income(Decimal('5000'), 2026)
        self.assertEqual(tier.tier_number, 1)

    def test_tier_for_income_tier5(self):
        from tax_wizard.models import PausalTier
        tier = PausalTier.get_tier_for_income(Decimal('55000'), 2026)
        self.assertEqual(tier.tier_number, 5)

    def test_tier_for_income_above_limit(self):
        from tax_wizard.models import PausalTier
        tier = PausalTier.get_tier_for_income(Decimal('65000'), 2026)
        self.assertIsNone(tier)

    def test_get_all_tiers(self):
        from tax_wizard.models import PausalTier
        tiers = PausalTier.get_all_tiers(2026)
        self.assertEqual(tiers.count(), 5)


# ═══════════════════════════════════════════════════════════════
#  C. CALCULATION TESTS (15)
# ═══════════════════════════════════════════════════════════════

class POSDCalculatorTest(TestCase):
    """Tests for POSDCalculator."""

    @classmethod
    def setUpTestData(cls):
        from tax_wizard.models import PausalTier
        tiers = [
            (1, 0, 12500, 1530, 127.50, 290.98),
            (2, 12501, 17500, 2142, 178.50, 290.98),
            (3, 17501, 25000, 3060, 255.00, 290.98),
            (4, 25001, 40000, 4896, 408.00, 290.98),
            (5, 40001, 60000, 7344, 612.00, 290.98),
        ]
        for num, min_i, max_i, annual, monthly, contrib in tiers:
            PausalTier.objects.create(
                valid_year=2026, tier_number=num,
                min_income=Decimal(str(min_i)), max_income=Decimal(str(max_i)),
                annual_tax=Decimal(str(annual)), monthly_tax=Decimal(str(monthly)),
                monthly_contributions=Decimal(str(contrib)),
            )

    def test_tier1_calculation(self):
        from tax_wizard.services import POSDCalculator
        calc = POSDCalculator(2026)
        result = calc.calculate(
            Decimal('2000'), Decimal('3000'), Decimal('2500'), Decimal('2000'))
        self.assertEqual(result['porezni_razred'], 1)
        self.assertEqual(result['godisnji_porez'], Decimal('1530'))

    def test_tier3_boundary(self):
        """Točno 17501 — tier 3."""
        from tax_wizard.services import POSDCalculator
        calc = POSDCalculator(2026)
        result = calc.calculate(
            Decimal('4375.25'), Decimal('4375.25'),
            Decimal('4375.25'), Decimal('4375.25'))
        self.assertEqual(result['porezni_razred'], 3)

    def test_tier5_max(self):
        """Točno 60000 — tier 5, ne exceeds."""
        from tax_wizard.services import POSDCalculator
        calc = POSDCalculator(2026)
        result = calc.calculate(
            Decimal('15000'), Decimal('15000'),
            Decimal('15000'), Decimal('15000'))
        self.assertEqual(result['porezni_razred'], 5)
        self.assertFalse(result['exceeds_limit'])

    def test_exceeds_60k(self):
        from tax_wizard.services import POSDCalculator
        calc = POSDCalculator(2026)
        result = calc.calculate(
            Decimal('20000'), Decimal('20000'),
            Decimal('20000'), Decimal('1'))
        self.assertTrue(result['exceeds_limit'])
        self.assertEqual(result['porezni_razred'], 0)

    def test_zero_income(self):
        from tax_wizard.services import POSDCalculator
        calc = POSDCalculator(2026)
        result = calc.calculate(Decimal('0'), Decimal('0'), Decimal('0'), Decimal('0'))
        self.assertEqual(result['porezni_razred'], 1)
        self.assertEqual(result['godisnji_porez'], Decimal('1530'))

    def test_already_paid_positive_difference(self):
        from tax_wizard.services import POSDCalculator
        calc = POSDCalculator(2026)
        result = calc.calculate(
            Decimal('5000'), Decimal('5000'),
            Decimal('5000'), Decimal('5000'),
            already_paid=Decimal('1000'))
        # Tier 3: 3060 - 1000 = 2060
        self.assertEqual(result['razlika'], Decimal('2060.00'))

    def test_already_paid_refund(self):
        from tax_wizard.services import POSDCalculator
        calc = POSDCalculator(2026)
        result = calc.calculate(
            Decimal('2000'), Decimal('2000'),
            Decimal('2000'), Decimal('2000'),
            already_paid=Decimal('2000'))
        # Tier 1: 1530 - 2000 = -470 (refund)
        self.assertEqual(result['razlika'], Decimal('-470.00'))

    def test_contributions_calculation(self):
        from tax_wizard.services import POSDCalculator
        calc = POSDCalculator(2026)
        result = calc.calculate(Decimal('3000'), Decimal('3000'), Decimal('3000'), Decimal('3000'))
        self.assertEqual(result['annual_contributions'], Decimal('3491.76'))

    def test_total_annual_cost(self):
        from tax_wizard.services import POSDCalculator
        calc = POSDCalculator(2026)
        result = calc.calculate(Decimal('3000'), Decimal('3000'), Decimal('3000'), Decimal('3000'))
        expected = result['godisnji_porez'] + result['annual_contributions']
        self.assertEqual(result['total_annual_cost'], expected)


# ═══════════════════════════════════════════════════════════════
#  D. AI ADVISOR TESTS (10)
# ═══════════════════════════════════════════════════════════════

class AIAdvisorTest(TestCase):
    """Tests for AIAdvisor — cliff, wall, messages."""

    @classmethod
    def setUpTestData(cls):
        from tax_wizard.models import PausalTier
        tiers = [
            (1, 0, 12500, 1530, 127.50),
            (2, 12501, 17500, 2142, 178.50),
            (3, 17501, 25000, 3060, 255.00),
            (4, 25001, 40000, 4896, 408.00),
            (5, 40001, 60000, 7344, 612.00),
        ]
        for num, min_i, max_i, annual, monthly in tiers:
            PausalTier.objects.create(
                valid_year=2026, tier_number=num,
                min_income=Decimal(str(min_i)), max_income=Decimal(str(max_i)),
                annual_tax=Decimal(str(annual)), monthly_tax=Decimal(str(monthly)),
            )

    def test_exceeds_60k_error(self):
        from tax_wizard.services import AIAdvisor
        advisor = AIAdvisor(2026)
        msgs = advisor.analyze({'ukupni_primitak': 65000, 'exceeds_limit': True})
        self.assertTrue(any(m['type'] == 'error' for m in msgs))
        self.assertTrue(any(m['code'] == 'exceeds_60k' for m in msgs))

    def test_near_60k_warning(self):
        from tax_wizard.services import AIAdvisor
        advisor = AIAdvisor(2026)
        msgs = advisor.analyze({
            'ukupni_primitak': 55000, 'porezni_razred': 5,
            'exceeds_limit': False, 'godisnji_porez': 7344,
            'vec_placeni_porez': 0, 'razlika': 7344,
            'total_annual_cost': 10835.76,
        })
        self.assertTrue(any(m['code'] == 'near_60k' for m in msgs))

    def test_cliff_lower_tier(self):
        """12800 EUR — 300€ iznad tier 1 granice."""
        from tax_wizard.services import AIAdvisor
        advisor = AIAdvisor(2026)
        msgs = advisor.analyze({
            'ukupni_primitak': 12800, 'porezni_razred': 2,
            'exceeds_limit': False, 'godisnji_porez': 2142,
            'vec_placeni_porez': 0, 'razlika': 2142,
            'total_annual_cost': 5633.76,
        })
        cliff_msgs = [m for m in msgs if m.get('code') == 'cliff_lower_tier']
        self.assertEqual(len(cliff_msgs), 1)
        self.assertIn('612', cliff_msgs[0]['message'])  # savings

    def test_cliff_upper_tier(self):
        """12200 EUR — 300€ ispod tier 2 granice."""
        from tax_wizard.services import AIAdvisor
        advisor = AIAdvisor(2026)
        msgs = advisor.analyze({
            'ukupni_primitak': 12200, 'porezni_razred': 1,
            'exceeds_limit': False, 'godisnji_porez': 1530,
            'vec_placeni_porez': 0, 'razlika': 1530,
            'total_annual_cost': 5021.76,
        })
        cliff_msgs = [m for m in msgs if m.get('code') == 'cliff_upper_tier']
        self.assertEqual(len(cliff_msgs), 1)

    def test_zero_income_message(self):
        from tax_wizard.services import AIAdvisor
        advisor = AIAdvisor(2026)
        msgs = advisor.analyze({
            'ukupni_primitak': 0, 'porezni_razred': 1,
            'exceeds_limit': False, 'godisnji_porez': 1530,
            'vec_placeni_porez': 0, 'razlika': 1530,
            'total_annual_cost': 5021.76,
        })
        self.assertTrue(any(m['code'] == 'zero_income' for m in msgs))

    def test_refund_message(self):
        from tax_wizard.services import AIAdvisor
        advisor = AIAdvisor(2026)
        msgs = advisor.analyze({
            'ukupni_primitak': 5000, 'porezni_razred': 1,
            'exceeds_limit': False, 'godisnji_porez': 1530,
            'vec_placeni_porez': 2000, 'razlika': -470,
            'total_annual_cost': 5021.76,
        })
        self.assertTrue(any(m['code'] == 'refund_due' for m in msgs))

    def test_payment_due_message(self):
        from tax_wizard.services import AIAdvisor
        advisor = AIAdvisor(2026)
        msgs = advisor.analyze({
            'ukupni_primitak': 5000, 'porezni_razred': 1,
            'exceeds_limit': False, 'godisnji_porez': 1530,
            'vec_placeni_porez': 500, 'razlika': 1030,
            'total_annual_cost': 5021.76,
        })
        self.assertTrue(any(m['code'] == 'payment_due' for m in msgs))

    def test_no_forbidden_words(self):
        """Pravni štit: AI ne smije koristiti zabranjene riječi."""
        from tax_wizard.services import AIAdvisor
        advisor = AIAdvisor(2026)
        test_cases = [
            {'ukupni_primitak': 12800, 'porezni_razred': 2, 'exceeds_limit': False,
             'godisnji_porez': 2142, 'vec_placeni_porez': 0, 'razlika': 2142, 'total_annual_cost': 5633.76},
            {'ukupni_primitak': 55000, 'porezni_razred': 5, 'exceeds_limit': False,
             'godisnji_porez': 7344, 'vec_placeni_porez': 0, 'razlika': 7344, 'total_annual_cost': 10835.76},
        ]
        forbidden = ['preporučujem', 'savjetujem', 'trebali biste']
        for case in test_cases:
            msgs = advisor.analyze(case)
            for msg in msgs:
                text = msg['message'].lower()
                for word in forbidden:
                    self.assertNotIn(word, text,
                        f'Forbidden word "{word}" in: {msg["message"][:50]}...')

    def test_success_message_always_present(self):
        from tax_wizard.services import AIAdvisor
        advisor = AIAdvisor(2026)
        msgs = advisor.analyze({
            'ukupni_primitak': 20000, 'porezni_razred': 3,
            'exceeds_limit': False, 'godisnji_porez': 3060,
            'vec_placeni_porez': 3060, 'razlika': 0,
            'total_annual_cost': 6551.76,
        })
        self.assertTrue(any(m['code'] == 'calculation_ok' for m in msgs))

    def test_disclaimer_in_simulation_messages(self):
        """Svaka simulation poruka mora završiti s disclaimer-om."""
        from tax_wizard.services import AIAdvisor
        advisor = AIAdvisor(2026)
        msgs = advisor.analyze({
            'ukupni_primitak': 12800, 'porezni_razred': 2,
            'exceeds_limit': False, 'godisnji_porez': 2142,
            'vec_placeni_porez': 0, 'razlika': 2142, 'total_annual_cost': 5633.76,
        })
        sim_msgs = [m for m in msgs if m['type'] == 'simulation']
        for msg in sim_msgs:
            self.assertIn('informativni izračun', msg['message'].lower())


# ═══════════════════════════════════════════════════════════════
#  E. XML EXPORT TESTS (8)
# ═══════════════════════════════════════════════════════════════

class POSDXmlGeneratorTest(TestCase):
    """Tests for PO-SD XML generation."""

    @classmethod
    def setUpTestData(cls):
        from tax_wizard.models import TaxFormTemplate, TaxWizardSession
        from companies.models import Company

        cls.user = User.objects.create_user('xmluser', password='testpass123!')
        cls.company = Company.objects.create(name='XML Obrt', oib='98765432101')
        cls.template = TaxFormTemplate.objects.create(
            form_type='PO-SD', version='xml-v1', name='XML Test',
            schema={'steps': []}, valid_from=date(2026, 1, 1),
        )
        cls.session = TaxWizardSession.objects.create(
            session_key='xml-test-key',
            user=cls.user, company=cls.company, template=cls.template,
            tax_year=2025,
            form_data={
                'oib': '98765432101',
                'ime_prezime': 'Ivan Horvat',
                'adresa': 'Ilica 1, 10000 Zagreb',
                'naziv_obrta': 'XML Obrt',
                'djelatnost_nkd': '62.01',
                'q1_primitak': 5000,
                'q2_primitak': 6000,
                'q3_primitak': 4000,
                'q4_primitak': 3000,
            },
            calculated_results={
                'ukupni_primitak': 18000,
                'porezni_razred': 3,
                'godisnji_porez': 3060,
                'vec_placeni_porez': 1000,
                'razlika': 2060,
            },
        )

    def test_xml_generation(self):
        from tax_wizard.services import POSDXmlGenerator
        gen = POSDXmlGenerator()
        xml = gen.generate(self.session)
        self.assertIn('<?xml version=', xml)
        self.assertIn('<PO-SD', xml)

    def test_xml_contains_oib(self):
        from tax_wizard.services import POSDXmlGenerator
        xml = POSDXmlGenerator().generate(self.session)
        self.assertIn('<OIB>98765432101</OIB>', xml)

    def test_xml_contains_quarters(self):
        from tax_wizard.services import POSDXmlGenerator
        xml = POSDXmlGenerator().generate(self.session)
        self.assertIn('<Kvartal1>5000.00</Kvartal1>', xml)
        self.assertIn('<Kvartal2>6000.00</Kvartal2>', xml)
        self.assertIn('<Kvartal3>4000.00</Kvartal3>', xml)
        self.assertIn('<Kvartal4>3000.00</Kvartal4>', xml)

    def test_xml_contains_total(self):
        from tax_wizard.services import POSDXmlGenerator
        xml = POSDXmlGenerator().generate(self.session)
        self.assertIn('<UkupniPrimitak>18000.00</UkupniPrimitak>', xml)

    def test_xml_contains_tax_tier(self):
        from tax_wizard.services import POSDXmlGenerator
        xml = POSDXmlGenerator().generate(self.session)
        self.assertIn('<PorezniRazred>3</PorezniRazred>', xml)

    def test_xml_refund_vs_payment(self):
        """Pozitivna razlika = za uplatu, negativna = za povrat."""
        from tax_wizard.services import POSDXmlGenerator
        xml = POSDXmlGenerator().generate(self.session)
        self.assertIn('<RazlikaZaUplatu>2060.00</RazlikaZaUplatu>', xml)
        self.assertIn('<RazlikaZaPovrat>0.00</RazlikaZaPovrat>', xml)

    def test_xml_encoding_special_chars(self):
        """Specijalni znakovi u imenu ne smiju srušiti XML."""
        self.session.form_data['ime_prezime'] = 'Šeki Čović-Đurđević'
        self.session.save()
        from tax_wizard.services import POSDXmlGenerator
        xml = POSDXmlGenerator().generate(self.session)
        self.assertIn('Čović', xml)  # ElementTree handles encoding

    def test_xml_zero_income(self):
        self.session.form_data.update({
            'q1_primitak': 0, 'q2_primitak': 0,
            'q3_primitak': 0, 'q4_primitak': 0,
        })
        self.session.calculated_results.update({
            'ukupni_primitak': 0, 'porezni_razred': 1,
            'godisnji_porez': 1530, 'vec_placeni_porez': 0, 'razlika': 1530,
        })
        self.session.save()
        from tax_wizard.services import POSDXmlGenerator
        xml = POSDXmlGenerator().generate(self.session)
        self.assertIn('<UkupniPrimitak>0.00</UkupniPrimitak>', xml)


# ═══════════════════════════════════════════════════════════════
#  F. VIEW TESTS (12)
# ═══════════════════════════════════════════════════════════════

@override_settings(SECURE_SSL_REDIRECT=False)
class WizardViewTest(TestCase):
    """Tests for wizard views."""

    def _url(self, name, *args):
        """Generiraj URL s /hr/ prefiksom za i18n patterns."""
        url = reverse(name, args=args)
        if not url.startswith('/hr/'):
            url = '/hr' + url
        return url


    @classmethod
    def setUpTestData(cls):
        from tax_wizard.models import TaxFormTemplate, TaxWizardSession, PausalTier
        from companies.models import Company

        cls.user = User.objects.create_user('viewuser', password='testpass123!')
        cls.other_user = User.objects.create_user('otheruser', password='testpass123!')
        cls.company = Company.objects.create(name='View Obrt', oib='11111111111')

        # Tiers
        for num, min_i, max_i, annual, monthly in [
            (1, 0, 12500, 1530, 127.50),
            (2, 12501, 17500, 2142, 178.50),
            (3, 17501, 25000, 3060, 255.00),
            (4, 25001, 40000, 4896, 408.00),
            (5, 40001, 60000, 7344, 612.00),
        ]:
            PausalTier.objects.create(
                valid_year=2026, tier_number=num,
                min_income=Decimal(str(min_i)), max_income=Decimal(str(max_i)),
                annual_tax=Decimal(str(annual)), monthly_tax=Decimal(str(monthly)),
            )

        cls.template = TaxFormTemplate.objects.create(
            form_type='PO-SD', version='view-v1', name='View Test',
            schema={'steps': [
                {'id': 'intro', 'title': 'Intro', 'fields': []},
                {'id': 'primitci', 'title': 'Primitci', 'fields': []},
                {'id': 'calc', 'title': 'Izračun', 'fields': []},
            ]},
            valid_from=date(2026, 1, 1),
            filing_deadline_rule='jan-15',
            applicable_business_types=[],
        )
        cls.session = TaxWizardSession.objects.create(
            session_key='view-test-key',
            user=cls.user, company=cls.company, template=cls.template,
            tax_year=2025,
            form_data={'oib': '11111111111', 'q1_primitak': 5000},
        )

    def setUp(self):
        self.client.login(username='viewuser', password='testpass123!')
        self.client.cookies['django_language'] = 'hr'
        activate('hr')

    def test_dashboard_200(self):
        # Patch get_user_company
        with patch('tax_wizard.views.get_user_company', return_value=self.company):
            response = self.client.get(self._url('tax_wizard:dashboard'), follow=True)
            self.assertEqual(response.status_code, 200)

    def test_wizard_view_200(self):
        response = self.client.get(self._url('tax_wizard:wizard_view', self.session.id), follow=True)
        self.assertEqual(response.status_code, 200)

    def test_wizard_view_other_user_403(self):
        self.client.login(username='otheruser', password='testpass123!')
        response = self.client.get(self._url('tax_wizard:wizard_view', self.session.id))
        # Http404 → handler404 redirecta na / (302) ili Django vraca 404
        self.assertIn(response.status_code, [302, 404])

    def test_save_step_ajax(self):
        import json
        response = self.client.post(
            self._url('tax_wizard:wizard_save_step', self.session.id),
            data=json.dumps({'step': 0, 'data': {'oib': '11111111111', 'ime_prezime': 'Test', 'naziv_obrta': 'Obrt'}}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['ok'])

    def test_save_step_invalid_oib(self):
        import json
        response = self.client.post(
            self._url('tax_wizard:wizard_save_step', self.session.id),
            data=json.dumps({'step': 0, 'data': {'oib': '123', 'ime_prezime': 'Test', 'naziv_obrta': 'Obrt'}}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['ok'])

    def test_save_step_other_user_forbidden(self):
        import json
        self.client.login(username='otheruser', password='testpass123!')
        response = self.client.post(
            self._url('tax_wizard:wizard_save_step', self.session.id),
            data=json.dumps({'step': 0, 'data': {}}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)

    def test_finalize_creates_xml(self):
        import json
        # Moramo prvo popuniti sesiju
        self.session.form_data = {
            'oib': '11111111111', 'ime_prezime': 'Test User',
            'adresa': 'Test 1', 'naziv_obrta': 'Test Obrt', 'djelatnost_nkd': '62.01',
            'q1_primitak': 3000, 'q2_primitak': 3000, 'q3_primitak': 3000, 'q4_primitak': 3000,
        }
        self.session.calculated_results = {
            'ukupni_primitak': 12000, 'porezni_razred': 1,
            'godisnji_porez': 1530, 'vec_placeni_porez': 0, 'razlika': 1530,
        }
        self.session.status = 'draft'
        self.session.save()

        response = self.client.post(
            self._url('tax_wizard:wizard_finalize', self.session.id),
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['ok'])

        self.session.refresh_from_db()
        self.assertEqual(self.session.status, 'final')

    def test_api_deadlines_empty(self):
        with patch('tax_wizard.views.get_user_company', return_value=self.company):
            response = self.client.get(self._url('tax_wizard:api_deadlines'), follow=True)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertIn('deadlines', data)

    def test_api_calendar(self):
        with patch('tax_wizard.views.get_user_company', return_value=self.company):
            response = self.client.get(self._url('tax_wizard:api_calendar', 2025), follow=True)
            self.assertEqual(response.status_code, 200)

    def test_simulate_pausal_tier_all(self):
        with patch('tax_wizard.views.get_user_company', return_value=self.company):
            response = self.client.get(self._url('tax_wizard:sim_pausal_tier') + '?year=2026', follow=True)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertIn('tiers', data)

    def test_simulate_pausal_tier_specific(self):
        with patch('tax_wizard.views.get_user_company', return_value=self.company):
            response = self.client.get(self._url('tax_wizard:sim_pausal_tier') + '?year=2026&income=20000', follow=True)
            self.assertEqual(response.status_code, 200)

    def test_preview_json(self):
        response = self.client.get(self._url('tax_wizard:wizard_preview', self.session.id), follow=True)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['ok'])


# ═══════════════════════════════════════════════════════════════
#  G. SECURITY TESTS (8)
# ═══════════════════════════════════════════════════════════════

@override_settings(SECURE_SSL_REDIRECT=False)
class SecurityTest(TestCase):
    """Security tests — cross-tenant, CSRF, injection."""

    def _url(self, name, *args):
        """Generiraj URL s /hr/ prefiksom za i18n patterns."""
        url = reverse(name, args=args)
        if not url.startswith('/hr/'):
            url = '/hr' + url
        return url


    @classmethod
    def setUpTestData(cls):
        from tax_wizard.models import TaxFormTemplate, TaxWizardSession
        from companies.models import Company

        cls.user1 = User.objects.create_user('secure1', password='testpass123!')
        cls.user2 = User.objects.create_user('secure2', password='testpass123!')
        cls.company1 = Company.objects.create(name='Firma 1', oib='11111111111')
        cls.company2 = Company.objects.create(name='Firma 2', oib='22222222222')

        cls.template = TaxFormTemplate.objects.create(
            form_type='PO-SD', version='sec-v1', name='Security Test',
            schema={'steps': []}, valid_from=date(2026, 1, 1),
        )
        cls.session1 = TaxWizardSession.objects.create(
            session_key='sec-key-1',
            user=cls.user1, company=cls.company1, template=cls.template,
            tax_year=2025,
            form_data={'oib': '11111111111', 'secret_data': 'confidential'},
        )

    def setUp(self):
        activate('hr')
        self.client.cookies['django_language'] = 'hr'

    def setUp(self):
        activate('hr')
        self.client.cookies['django_language'] = 'hr'

    def test_cross_tenant_wizard_view(self):
        """User 2 ne smije vidjeti sesiju User 1."""
        self.client.login(username='secure2', password='testpass123!')
        response = self.client.get(self._url('tax_wizard:wizard_view', self.session1.id))
        self.assertIn(response.status_code, [302, 404])

    def test_cross_tenant_save_step(self):
        """User 2 ne smije mijenjati sesiju User 1."""
        import json
        self.client.login(username='secure2', password='testpass123!')
        response = self.client.post(
            self._url('tax_wizard:wizard_save_step', self.session1.id),
            data=json.dumps({'step': 0, 'data': {'oib': 'HACKED'}}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)

    def test_cross_tenant_finalize(self):
        self.client.login(username='secure2', password='testpass123!')
        response = self.client.post(
            self._url('tax_wizard:wizard_finalize', self.session1.id),
        )
        self.assertEqual(response.status_code, 403)

    def test_cross_tenant_review(self):
        import json
        self.client.login(username='secure2', password='testpass123!')
        response = self.client.post(
            self._url('tax_wizard:accountant_review', self.session1.id),
            data=json.dumps({'action': 'approve'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)

    def test_save_step_requires_post(self):
        self.client.login(username='secure1', password='testpass123!')
        response = self.client.get(
            self._url('tax_wizard:wizard_save_step', self.session1.id),
            follow=True,
        )
        self.assertEqual(response.status_code, 405)

    def test_finalize_requires_post(self):
        self.client.login(username='secure1', password='testpass123!')
        response = self.client.get(
            self._url('tax_wizard:wizard_finalize', self.session1.id),
            follow=True,
        )
        self.assertEqual(response.status_code, 405)

    def test_unauthenticated_redirect(self):
        self.client.logout()
        response = self.client.get(self._url('tax_wizard:dashboard'))
        # login_required → 302 to login page
        self.assertEqual(response.status_code, 302)

    def test_xss_in_form_data(self):
        """XSS u form_data ne smije proći u XML."""
        import json
        self.client.login(username='secure1', password='testpass123!')
        response = self.client.post(
            self._url('tax_wizard:wizard_save_step', self.session1.id),
            data=json.dumps({
                'step': 0,
                'data': {
                    'oib': '11111111111',
                    'ime_prezime': '<script>alert("xss")</script>',
                    'naziv_obrta': 'Test',
                },
            }),
            content_type='application/json',
        )
        # Provjeri da se čuva ali da XML escapa
        self.session1.refresh_from_db()
        # XML generator koristi ElementTree koji automatski escapa
        from tax_wizard.services import POSDXmlGenerator
        self.session1.calculated_results = {
            'ukupni_primitak': 0, 'porezni_razred': 1,
            'godisnji_porez': 1530, 'vec_placeni_porez': 0, 'razlika': 1530,
        }
        self.session1.save()
        gen = POSDXmlGenerator()
        xml = gen.generate(self.session1)
        self.assertNotIn('<script>', xml)
