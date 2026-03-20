"""Tests for Payments module."""
from decimal import Decimal
from django.test import TestCase
from companies.models import Company
from payments.models import PaymentConfig, Payment


class PaymentConfigTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Pay Co", oib="55555555555")

    def test_config_creation(self):
        config = PaymentConfig.objects.create(company=self.company)
        self.assertEqual(config.company, self.company)

    def test_config_str(self):
        config = PaymentConfig.objects.create(company=self.company)
        self.assertIn("Pay Co", str(config))


class PaymentTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Pay Test", oib="66666666666")

    def test_payment_creation(self):
        payment = Payment.objects.create(
            company=self.company,
            amount=Decimal("25.00"),
            method="cash",
            source="pos",
        )
        self.assertEqual(payment.amount, Decimal("25.00"))
        self.assertEqual(payment.method, "cash")
        self.assertIsNotNone(payment.id)

    def test_payment_uuid_pk(self):
        """Payment should use UUID primary key."""
        payment = Payment.objects.create(
            company=self.company,
            amount=Decimal("10.00"),
            method="stripe",
            source="webshop",
        )
        import uuid
        self.assertIsInstance(payment.pk, uuid.UUID)

    def test_payment_default_status(self):
        payment = Payment.objects.create(
            company=self.company,
            amount=Decimal("50.00"),
            method="card",
            source="pos",
        )
        self.assertEqual(payment.status, "pending")
