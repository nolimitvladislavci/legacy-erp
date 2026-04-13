"""
Tests for Kindergarten vertical — forms, billing, attendance, portal, CSV import.
Target: 15 tests.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from kindergarten.models import (
    Attendance,
    Child,
    ChildGuardian,
    Guardian,
    KindergartenGroup,
    MonthlyBilling,
)

User = get_user_model()


class ChildFormTest(TestCase):
    """Test ChildForm validation — GDPR, OIB, age."""

    def setUp(self):
        from companies.models import Company
        self.company = Company.objects.create(name='Vrtic Test', oib='12345678901')
        self.group = KindergartenGroup.objects.create(
            company=self.company, name='Bubamare', capacity=20,
            monthly_price=Decimal('200'), meal_daily_price=Decimal('3.50'),
        )

    def test_gdpr_consent_required(self):
        """GDPR consent is mandatory for child enrollment."""
        from kindergarten.forms import ChildForm
        data = {
            'first_name': 'Marko',
            'last_name': 'Markic',
            'date_of_birth': date(2022, 5, 1),
            'group': self.group.pk,
            'gdpr_consent': False,
            'status': 'active',
        }
        form = ChildForm(data, company=self.company)
        self.assertFalse(form.is_valid())
        self.assertIn('gdpr_consent', form.errors)

    def test_valid_child_with_consent(self):
        """Child with GDPR consent passes validation."""
        from kindergarten.forms import ChildForm
        data = {
            'first_name': 'Ana',
            'last_name': 'Anic',
            'date_of_birth': date(2022, 3, 15),
            'group': self.group.pk,
            'gdpr_consent': True,
            'status': 'active',
        }
        form = ChildForm(data, company=self.company)
        self.assertTrue(form.is_valid())

    def test_age_over_16_rejected(self):
        """Child older than 16 is rejected."""
        from kindergarten.forms import ChildForm
        data = {
            'first_name': 'Stari',
            'last_name': 'Prestal',
            'date_of_birth': date(2005, 1, 1),
            'group': self.group.pk,
            'gdpr_consent': True,
            'status': 'active',
        }
        form = ChildForm(data, company=self.company)
        self.assertFalse(form.is_valid())

    def test_oib_validation(self):
        """OIB with invalid format rejected."""
        from kindergarten.forms import ChildForm
        data = {
            'first_name': 'Test',
            'last_name': 'OIB',
            'date_of_birth': date(2023, 1, 1),
            'oib': 'abc',
            'group': self.group.pk,
            'gdpr_consent': True,
            'status': 'active',
        }
        form = ChildForm(data, company=self.company)
        self.assertFalse(form.is_valid())


class BillingCalculationTest(TestCase):
    """Test MonthlyBilling calculation — absence deduction."""

    def setUp(self):
        from companies.models import Company
        self.company = Company.objects.create(name='Billing Test', oib='99988877766')
        self.group = KindergartenGroup.objects.create(
            company=self.company, name='Leptirici',
            monthly_price=Decimal('200'), meal_daily_price=Decimal('3.50'),
        )
        self.child = Child.objects.create(
            company=self.company, first_name='Ivica', last_name='Ivic',
            date_of_birth=date(2022, 6, 1), group=self.group,
            gdpr_consent=True, gdpr_consent_date=timezone.now(),
            status='active',
        )

    def test_billing_no_absences(self):
        """Full month, no absences = base price."""
        billing = MonthlyBilling(child=self.child, year=2026, month=3)
        billing.calculate()
        self.assertEqual(billing.base_amount, Decimal('200'))
        self.assertEqual(billing.days_absent, 0)
        self.assertEqual(billing.meal_deduction, Decimal('0'))
        self.assertEqual(billing.total_amount, Decimal('200'))

    def test_billing_with_absences(self):
        """5 sick days = 5 * 3.50 = 17.50 deduction."""
        for day in range(1, 6):
            Attendance.objects.create(
                child=self.child, date=date(2026, 3, day), status='sick',
            )
        billing = MonthlyBilling(child=self.child, year=2026, month=3)
        billing.calculate()
        self.assertEqual(billing.days_absent, 5)
        self.assertEqual(billing.meal_deduction, Decimal('17.50'))
        self.assertEqual(billing.total_amount, Decimal('182.50'))

    def test_billing_unexcused_not_deducted(self):
        """Unexcused absences are NOT deducted (only sick/excused)."""
        Attendance.objects.create(
            child=self.child, date=date(2026, 3, 1), status='unexcused',
        )
        billing = MonthlyBilling(child=self.child, year=2026, month=3)
        billing.calculate()
        self.assertEqual(billing.days_absent, 0)
        self.assertEqual(billing.total_amount, Decimal('200'))

    def test_payment_reference_format(self):
        """Payment reference = guardian OIB + YYYYMM."""
        guardian = Guardian.objects.create(
            company=self.company, first_name='Mama', last_name='Ivic',
            oib='11122233344', phone='0991234567',
        )
        ChildGuardian.objects.create(
            child=self.child, guardian=guardian, is_primary=True,
        )
        billing = MonthlyBilling(child=self.child, year=2026, month=3)
        billing.calculate()
        self.assertEqual(billing.payment_reference, '11122233344-202603')


class AttendanceTest(TestCase):
    """Test attendance tracking."""

    def setUp(self):
        from companies.models import Company
        self.company = Company.objects.create(name='Att Test', oib='55544433322')
        self.group = KindergartenGroup.objects.create(
            company=self.company, name='Medvjedici',
        )
        self.child = Child.objects.create(
            company=self.company, first_name='Petra', last_name='Petric',
            date_of_birth=date(2023, 1, 1), group=self.group,
            gdpr_consent=True, gdpr_consent_date=timezone.now(),
        )

    def test_attendance_unique_per_day(self):
        """Only one attendance record per child per day."""
        Attendance.objects.create(child=self.child, date=date(2026, 4, 1), status='present')
        with self.assertRaises(Exception):
            Attendance.objects.create(child=self.child, date=date(2026, 4, 1), status='sick')

    def test_is_absent_property(self):
        """is_absent returns True for non-present statuses."""
        att = Attendance(child=self.child, date=date(2026, 4, 1), status='sick')
        self.assertTrue(att.is_absent)
        att.status = 'present'
        self.assertFalse(att.is_absent)


class InvoiceIntegrationTest(TestCase):
    """Test MonthlyBilling → Invoice generation."""

    def setUp(self):
        from companies.models import Company
        self.company = Company.objects.create(name='Invoice Test', oib='77766655544')
        self.group = KindergartenGroup.objects.create(
            company=self.company, name='Zvjezdice',
            monthly_price=Decimal('250'), meal_daily_price=Decimal('4.00'),
        )
        self.child = Child.objects.create(
            company=self.company, first_name='Luka', last_name='Lukic',
            date_of_birth=date(2022, 8, 1), group=self.group,
            gdpr_consent=True, gdpr_consent_date=timezone.now(),
            status='active',
        )
        self.guardian = Guardian.objects.create(
            company=self.company, first_name='Mama', last_name='Lukic',
            oib='88877766655', phone='0991112233', email='mama@test.com',
        )
        ChildGuardian.objects.create(
            child=self.child, guardian=self.guardian,
            is_primary=True, is_billing_contact=True,
        )

    def test_invoice_created_from_billing(self):
        """Invoice is created when billing is generated."""
        from kindergarten.tasks import _create_invoice_from_billing
        billing = MonthlyBilling(child=self.child, year=2026, month=3)
        billing.calculate()
        billing.due_date = date(2026, 4, 15)
        billing.save()

        invoice = _create_invoice_from_billing(billing)
        self.assertIsNotNone(invoice)
        self.assertEqual(invoice.client_name, 'Mama Lukic')
        self.assertEqual(invoice.client_oib, '88877766655')
        self.assertIn('VRT-202603', invoice.number)

    def test_invoice_has_correct_amounts(self):
        """Invoice amounts match billing."""
        from kindergarten.tasks import _create_invoice_from_billing
        billing = MonthlyBilling(child=self.child, year=2026, month=3)
        billing.calculate()
        billing.due_date = date(2026, 4, 15)
        billing.save()

        invoice = _create_invoice_from_billing(billing)
        self.assertEqual(invoice.subtotal, Decimal('250'))
        self.assertEqual(invoice.tax_amount, Decimal('62.50'))
        self.assertEqual(invoice.total, Decimal('312.50'))


class GuardianFormTest(TestCase):
    """Test guardian form validation."""

    def test_valid_guardian(self):
        from kindergarten.forms import GuardianForm
        data = {
            'first_name': 'Ana',
            'last_name': 'Anic',
            'phone': '+385991234567',
            'email': 'ana@test.com',
        }
        form = GuardianForm(data)
        self.assertTrue(form.is_valid())

    def test_invalid_phone(self):
        from kindergarten.forms import GuardianForm
        data = {
            'first_name': 'Ana',
            'last_name': 'Anic',
            'phone': 'abc',
        }
        form = GuardianForm(data)
        self.assertFalse(form.is_valid())
