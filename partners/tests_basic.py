"""
partners/tests.py - OIB validator + VIES + partner lookup tests.
"""
from django.test import TestCase
from django.db import IntegrityError, DatabaseError
from django.core.exceptions import ObjectDoesNotExist


class OIBFormatTests(TestCase):
    def test_format_hr(self):
        from core.oib_validator import format_oib_display
        self.assertEqual(format_oib_display('12345678903', 'HR'), 'OIB: 12345678903')

    def test_format_de(self):
        from core.oib_validator import format_oib_display
        self.assertEqual(format_oib_display('DE123456789', 'DE'), 'USt-IdNr: DE123456789')

    def test_strip_prefix_hr(self):
        from core.oib_validator import strip_vat_prefix
        self.assertEqual(strip_vat_prefix('12345678903', 'HR'), '12345678903')

    def test_strip_prefix_de(self):
        from core.oib_validator import strip_vat_prefix
        self.assertEqual(strip_vat_prefix('DE123456789', 'DE'), '123456789')

    def test_strip_prefix_at(self):
        from core.oib_validator import strip_vat_prefix
        self.assertEqual(strip_vat_prefix('ATU12345678', 'AT'), 'U12345678')


class PartnerOIBLookupViewTests(TestCase):
    def setUp(self):
        import datetime
        from django.contrib.auth.models import User
        from companies.models import Company
        from accounts.models import UserProfile
        from registration.models import CompanySubscription

        self.user = User.objects.create_superuser('testuser_oib', password='pass', email='')
        self.company = Company.objects.create(name='Lookup Test Co', oib='98765432109')

        try:
            profile = self.user.profile
            profile.company = self.company
            profile.save()
        except (IntegrityError, DatabaseError):
            UserProfile.objects.create(user=self.user, company=self.company)

        CompanySubscription.objects.create(
            company=self.company,
            plan='starter',
            valid_from=datetime.date.today(),
            monthly_fee=0,
            is_active=True,
            billing_cycle='monthly',
            modules_override=['partners'],
        )

        self.client.login(username='testuser_oib', password='pass')

    def test_invalid_oib_format(self):
        resp = self.client.get('/hr/partners/api/oib-lookup/', {'oib': '123', 'country': 'HR'}, secure=True)
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertTrue('error' in data or 'message' in data, f'Mora imati error/message key: {data}')

    def test_missing_oib(self):
        resp = self.client.get('/hr/partners/api/oib-lookup/', {'country': 'HR'}, secure=True)
        self.assertEqual(resp.status_code, 400)

    def test_existing_partner_returned(self):
        from partners.models import Partner
        Partner.objects.create(
            company=self.company, name='Postojeci Partner', oib='12345678903',
            email='test@test.hr', city='Zagreb',
        )
        resp = self.client.get('/hr/partners/api/oib-lookup/', {'oib': '12345678903', 'country': 'HR'}, secure=True)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['found'])
        self.assertEqual(data['source'], 'database')
        self.assertEqual(data['name'], 'Postojeci Partner')
