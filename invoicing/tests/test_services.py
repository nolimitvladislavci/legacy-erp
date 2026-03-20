"""
Tests for invoicing.services — business logic unit tests.
"""
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from invoicing.services import (
    VALID_TRANSITIONS,
    calculate_tax,
    can_transition,
    copy_invoice,
    generate_invoice_number,
)


class TestCalculateTax(TestCase):
    def test_basic_calculation(self):
        items = [{"quantity": 2, "unit_price": 100, "discount": 0, "tax_rate": 25}]
        result = calculate_tax(items)
        self.assertEqual(result["subtotal"], Decimal("200.00"))
        self.assertEqual(result["tax_rate"], Decimal("25"))
        self.assertEqual(result["tax_amount"], Decimal("50.00"))
        self.assertEqual(result["total"], Decimal("250.00"))

    def test_with_discount(self):
        items = [{"quantity": 1, "unit_price": 200, "discount": 10, "tax_rate": 25}]
        result = calculate_tax(items)
        self.assertEqual(result["subtotal"], Decimal("180.00"))
        self.assertEqual(result["total"], Decimal("225.00"))

    def test_multiple_items(self):
        items = [
            {"quantity": 3, "unit_price": 50, "discount": 0, "tax_rate": 25},
            {"quantity": 1, "unit_price": 100, "discount": 0, "tax_rate": 25},
        ]
        result = calculate_tax(items)
        self.assertEqual(result["subtotal"], Decimal("250.00"))

    def test_zero_items(self):
        result = calculate_tax([], tax_rate=Decimal("19"))
        self.assertEqual(result["subtotal"], Decimal("0.00"))
        self.assertEqual(result["total"], Decimal("0.00"))

    def test_german_tax_rate(self):
        items = [{"quantity": 1, "unit_price": 100, "discount": 0, "tax_rate": 19}]
        result = calculate_tax(items, tax_rate=Decimal("19"))
        self.assertEqual(result["tax_amount"], Decimal("19.00"))


class TestStatusTransitions(TestCase):
    def test_valid_transitions(self):
        self.assertTrue(can_transition("DRAFT", "SENT"))
        self.assertTrue(can_transition("SENT", "ACCEPTED"))
        self.assertTrue(can_transition("ACCEPTED", "PAID"))
        self.assertTrue(can_transition("PAID", "STORNO"))

    def test_invalid_transitions(self):
        self.assertFalse(can_transition("DRAFT", "PAID"))
        self.assertFalse(can_transition("STORNO", "DRAFT"))
        self.assertFalse(can_transition("PAID", "DRAFT"))

    def test_cancellation_from_most_states(self):
        for state in ["DRAFT", "SENT", "ACCEPTED"]:
            self.assertTrue(can_transition(state, "CANCELLED"), f"{state} -> CANCELLED should be valid")

    def test_reopen_from_rejected(self):
        self.assertTrue(can_transition("REJECTED", "DRAFT"))

    def test_all_states_have_transitions(self):
        for state in VALID_TRANSITIONS:
            self.assertIsInstance(VALID_TRANSITIONS[state], list)


class TestCopyInvoice(TestCase):
    def setUp(self):
        from companies.models import Company
        from invoicing.models import Invoice
        self.company = Company.objects.first()
        if not self.company:
            self.company = Company.objects.create(name="Test Co", oib="12345678901")
        self.source = Invoice.objects.create(
            doctype="P",
            number="P-2026-0001",
            company=self.company,
            client_name="Test Klijent",
            subtotal=Decimal("100.00"),
            tax_percent=Decimal("25"),
            tax_amount=Decimal("25.00"),
            total=Decimal("125.00"),
            status="ACCEPTED",
            country="HR",
            issuer_name="Test Firma",
            issuer_oib="12345678901",
            date_issued=timezone.now(),
        )

    def test_copy_creates_draft(self):
        new = copy_invoice(self.source, "R", "R-2026-0001")
        self.assertEqual(new.status, "DRAFT")
        self.assertEqual(new.doctype, "R")
        self.assertEqual(new.client_name, "Test Klijent")
        self.assertEqual(new.total, Decimal("125.00"))

    def test_copy_with_extra_fields(self):
        new = copy_invoice(self.source, "R", "R-2026-0002", {"note": "Iz ponude"})
        self.assertEqual(new.note, "Iz ponude")


class TestGenerateInvoiceNumber(TestCase):
    def setUp(self):
        from companies.models import Company
        self.company = Company.objects.first()
        if not self.company:
            self.company = Company.objects.create(name="Test Co", oib="99999999999")

    def test_generates_number(self):
        from invoicing.models import Invoice
        invoice = Invoice(company=self.company, doctype="R")
        number = generate_invoice_number(invoice, None, "R")
        self.assertIsInstance(number, str)
        self.assertTrue(len(number) > 0)
