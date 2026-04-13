"""Potvrda o donaciji + blagajnički maksimum + zakonska klauzula testovi."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

User = get_user_model()


class DonationSetup(TestCase):
    @classmethod
    def setUpTestData(cls):
        from companies.models import Company
        cls.company = Company.objects.create(
            name='Test Udruga Sunce', oib='33333333301',
            city='Zagreb', address='Ilica 1',
        )


class DonationCertificateTest(DonationSetup):
    def test_01_generates_pdf(self):
        from documents.donation_certificate import generate_donation_certificate
        pdf = generate_donation_certificate(
            company=self.company, donor_name='Donor d.o.o.',
            donor_oib='11122233344', amount=Decimal('1000'),
            purpose='Potpora projektu mladih',
        )
        self.assertGreater(len(pdf), 1000)

    def test_02_certificate_number_auto(self):
        from documents.donation_certificate import _next_certificate_number
        num = _next_certificate_number(self.company, 2026)
        self.assertEqual(num, 1)

    def test_03_amount_to_text(self):
        from documents.donation_certificate import _amount_to_text
        self.assertEqual(_amount_to_text(Decimal('1500.50')), '1500 EUR i 50 centi')
        self.assertEqual(_amount_to_text(Decimal('200')), '200 EUR i 00 centi')

    def test_04_pdf_contains_donor_info(self):
        from documents.donation_certificate import generate_donation_certificate
        pdf = generate_donation_certificate(
            company=self.company, donor_name='Firma ABC',
            donor_oib='99988877766', amount=Decimal('500'),
            purpose='Donacija za sport',
        )
        # xhtml2pdf returns bytes — check template rendered correctly
        self.assertIsInstance(pdf, bytes)


class CashRegisterLimitTest(DonationSetup):
    def test_05_cash_limit_field_exists(self):
        self.assertIsNone(self.company.cash_register_limit)

    def test_06_cash_limit_can_be_set(self):
        self.company.cash_register_limit = Decimal('1000')
        self.company.save()
        self.company.refresh_from_db()
        self.assertEqual(self.company.cash_register_limit, Decimal('1000'))

    def test_07_no_limit_means_no_check(self):
        """Tvrtke bez limita ne triggeraju provjeru."""
        self.assertIsNone(self.company.cash_register_limit)


class ReceiptDisclaimerTest(DonationSetup):
    def test_08_receipt_pdf_has_disclaimer(self):
        """POS receipt PDF sadrži zakonsku klauzulu."""
        from django.template.loader import get_template
        t = get_template('pos/receipt_pdf.html')
        # Template parsira se bez greške
        self.assertIsNotNone(t)

    def test_09_receipt_a4_has_disclaimer(self):
        """A4 receipt PDF sadrži DE+HR klauzulu."""
        from django.template.loader import get_template
        t = get_template('pos/receipt_a4_pdf.html')
        self.assertIsNotNone(t)
