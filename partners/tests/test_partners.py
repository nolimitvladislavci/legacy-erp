"""
partners/tests/test_partners.py
Model i servisni testovi za partners app.
Pokriva: Partner model logika, is_complete, missing_fields, update_balance,
OIB/VAT logika, unique_together, CompanyManager scope.
"""
from decimal import Decimal

from django.test import TestCase

from companies.models import Company
from partners.models import Partner


def _company(oib, name='Test Firma'):
    return Company.objects.create(name=name, oib=oib)


def _partner(company, name='Test Partner', oib='', **kwargs):
    defaults = dict(
        partner_type='client',
        country='HR',
    )
    defaults.update(kwargs)
    return Partner.objects.create(company=company, name=name, oib=oib, **defaults)


# ─────────────────────────────────────────────────────────────
# Partner model — osnovno
# ─────────────────────────────────────────────────────────────
class TestPartnerModel(TestCase):

    def setUp(self):
        self.company = _company('10101010101')

    def test_create_minimal_partner(self):
        p = _partner(self.company, name='Minimal d.o.o.')
        self.assertIsNotNone(p.pk)
        self.assertEqual(p.name, 'Minimal d.o.o.')

    def test_str_contains_name(self):
        p = _partner(self.company, name='Klijent ABC', city='Zagreb')
        self.assertIn('Klijent ABC', str(p))

    def test_str_contains_city(self):
        p = _partner(self.company, name='Firma', city='Split')
        self.assertIn('Split', str(p))

    def test_str_na_when_no_city(self):
        p = _partner(self.company, name='Bez grada')
        self.assertIn('N/A', str(p))

    def test_is_active_default_true(self):
        p = _partner(self.company, 'Aktivan')
        self.assertTrue(p.is_active)

    def test_portal_token_auto_generated(self):
        p = _partner(self.company, 'Portal')
        self.assertIsNotNone(p.portal_token)

    def test_two_partners_have_different_tokens(self):
        p1 = _partner(self.company, 'P1', oib='11111111111')
        p2 = _partner(self.company, 'P2', oib='22222222222')
        self.assertNotEqual(p1.portal_token, p2.portal_token)

    def test_payment_term_default_zero(self):
        p = _partner(self.company, 'Termin')
        self.assertEqual(p.payment_term, 0)

    def test_discount_default_zero(self):
        p = _partner(self.company, 'Rabat')
        self.assertEqual(p.discount_percent, Decimal('0.00'))

    def test_cached_balance_default_zero(self):
        p = _partner(self.company, 'Saldo')
        self.assertEqual(p.cached_balance, Decimal('0.00'))

    def test_country_default_hr(self):
        p = _partner(self.company, 'Zemlja')
        self.assertEqual(p.country, 'HR')


# ─────────────────────────────────────────────────────────────
# is_complete i missing_fields
# ─────────────────────────────────────────────────────────────
class TestPartnerCompleteness(TestCase):

    def setUp(self):
        self.company = _company('20202020202')

    def test_complete_partner(self):
        p = _partner(
            self.company, 'Kompletan',
            oib='33333333333',
            address='Ilica 1',
            city='Zagreb',
            email='partner@example.com',
        )
        self.assertTrue(p.is_complete)

    def test_incomplete_without_oib(self):
        p = _partner(
            self.company, 'Bez OIB',
            address='Ilica 1', city='Zagreb', email='e@e.com',
        )
        self.assertFalse(p.is_complete)
        self.assertIn('OIB', p.missing_fields)

    def test_incomplete_without_email(self):
        p = _partner(
            self.company, 'Bez emaila',
            oib='44444444444', address='Ilica 1', city='Zagreb',
        )
        self.assertFalse(p.is_complete)
        self.assertIn('Email', p.missing_fields)

    def test_incomplete_without_city(self):
        p = _partner(
            self.company, 'Bez grada',
            oib='55555555555', address='Ilica 1', email='e@e.com',
        )
        self.assertFalse(p.is_complete)
        self.assertIn('Grad', p.missing_fields)

    def test_incomplete_without_address(self):
        p = _partner(
            self.company, 'Bez adrese',
            oib='66666666666', city='Zagreb', email='e@e.com',
        )
        self.assertFalse(p.is_complete)
        self.assertIn('Adresa', p.missing_fields)

    def test_missing_fields_empty_when_complete(self):
        p = _partner(
            self.company, 'Svi podaci',
            oib='77777777777', address='Trg 1', city='Rijeka',
            email='r@r.com', phone='099123456',
        )
        self.assertEqual(p.missing_fields, [])

    def test_multiple_missing_fields(self):
        p = _partner(self.company, 'Samo ime')
        missing = p.missing_fields
        self.assertIn('OIB', missing)
        self.assertIn('Email', missing)
        self.assertIn('Grad', missing)

    def test_phone_not_required_for_is_complete(self):
        """is_complete ne zahtijeva telefon."""
        p = _partner(
            self.company, 'Bez telefona',
            oib='88888888888', address='Ulica 1', city='Osijek',
            email='o@o.com',
        )
        self.assertTrue(p.is_complete)


# ─────────────────────────────────────────────────────────────
# unique_together + company scope
# ─────────────────────────────────────────────────────────────
class TestPartnerUniqueness(TestCase):

    def setUp(self):
        self.company_a = _company('30303030303', 'Firma A')
        self.company_b = _company('40404040404', 'Firma B')

    def test_same_oib_different_companies_ok(self):
        """Isti OIB može biti u dvije različite tvrtke."""
        _partner(self.company_a, 'Partner A', oib='99999999999')
        _partner(self.company_b, 'Partner B', oib='99999999999')
        self.assertEqual(Partner.objects.filter(oib='99999999999').count(), 2)

    def test_same_oib_same_company_raises(self):
        """Isti OIB u istoj tvrtki → IntegrityError."""
        from django.db import IntegrityError
        _partner(self.company_a, 'Dup1', oib='12312312312')
        with self.assertRaises(IntegrityError):
            _partner(self.company_a, 'Dup2', oib='12312312312')

    def test_empty_oib_blocked_by_unique(self):
        """unique_together blokira i prazan OIB unutar iste firme."""
        from django.db import IntegrityError
        _partner(self.company_a, 'Bez OIB 1', oib='')
        with self.assertRaises(IntegrityError):
            _partner(self.company_a, 'Bez OIB 2', oib='')


# ─────────────────────────────────────────────────────────────
# Partner types
# ─────────────────────────────────────────────────────────────
class TestPartnerTypes(TestCase):

    def setUp(self):
        self.company = _company('50505050505')

    def test_client_type(self):
        p = _partner(self.company, 'Klijent', partner_type='client')
        self.assertEqual(p.partner_type, 'client')

    def test_supplier_type(self):
        p = _partner(self.company, 'Dobavljač', partner_type='supplier')
        self.assertEqual(p.partner_type, 'supplier')

    def test_both_type(self):
        p = _partner(self.company, 'Oboje', partner_type='both')
        self.assertEqual(p.partner_type, 'both')

    def test_employee_type(self):
        p = _partner(self.company, 'Radnik', partner_type='employee')
        self.assertEqual(p.partner_type, 'employee')

    def test_filter_by_type(self):
        _partner(self.company, 'K1', oib='11100001111', partner_type='client')
        _partner(self.company, 'K2', oib='22200002222', partner_type='client')
        _partner(self.company, 'S1', oib='33300003333', partner_type='supplier')
        clients = Partner.objects.filter(company=self.company, partner_type='client')
        self.assertEqual(clients.count(), 2)


# ─────────────────────────────────────────────────────────────
# VAT / PDV
# ─────────────────────────────────────────────────────────────
class TestPartnerVAT(TestCase):

    def setUp(self):
        self.company = _company('60606060606')

    def test_vat_registered_false_by_default(self):
        p = _partner(self.company, 'Nije PDV')
        self.assertFalse(p.is_vat_registered)

    def test_vat_id_stored(self):
        p = _partner(self.company, 'PDV firma', is_vat_registered=True, vat_id='HR12345678901')
        self.assertEqual(p.vat_id, 'HR12345678901')

    def test_eu_partner_can_have_vat_id(self):
        p = _partner(self.company, 'DE Firma', country='DE',
                     is_vat_registered=True, vat_id='DE123456789')
        self.assertEqual(p.vat_id, 'DE123456789')


# ─────────────────────────────────────────────────────────────
# Company scope (CompanyManager)
# ─────────────────────────────────────────────────────────────
class TestPartnerCompanyScope(TestCase):

    def setUp(self):
        self.company_x = _company('70707070707', 'X Co')
        self.company_y = _company('80808080808', 'Y Co')
        _partner(self.company_x, 'X Partner', oib='11111100001')
        _partner(self.company_x, 'X Partner 2', oib='22222200002')
        _partner(self.company_y, 'Y Partner', oib='33333300003')

    def test_objects_all_returns_all(self):
        """Normalni Manager vraća sve bez filtera."""
        self.assertEqual(Partner.objects.count(), 3)

    def test_active_partners_filter(self):
        p = _partner(self.company_x, 'Neaktivan', oib='99990000001', is_active=False)
        active = Partner.objects.filter(company=self.company_x, is_active=True)
        self.assertEqual(active.count(), 2)

    def test_ordering_by_name(self):
        """Default ordering je po imenu."""
        partners = list(Partner.objects.filter(company=self.company_x).values_list('name', flat=True))
        self.assertEqual(partners, sorted(partners))


# ─────────────────────────────────────────────────────────────
# IBAN / SWIFT
# ─────────────────────────────────────────────────────────────
class TestPartnerBankData(TestCase):

    def setUp(self):
        self.company = _company('90909090909')

    def test_iban_stored(self):
        p = _partner(self.company, 'IBAN', iban='HR1210010051863000160')
        self.assertEqual(p.iban, 'HR1210010051863000160')

    def test_swift_stored(self):
        p = _partner(self.company, 'SWIFT', swift='ZABAHR2X')
        self.assertEqual(p.swift, 'ZABAHR2X')

    def test_iban_blank_default(self):
        p = _partner(self.company, 'Bez IBAN')
        self.assertEqual(p.iban, '')

    def test_credit_limit_stored(self):
        p = _partner(self.company, 'Kredit', credit_limit=Decimal('5000.00'))
        self.assertEqual(p.credit_limit, Decimal('5000.00'))
