"""Tests for pos.services — POS business logic unit tests."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from core.exceptions import PaymentError, SessionError
from pos.services import (
    add_receipt_item,
    close_session,
    create_receipt,
    generate_zreport,
    open_session,
    process_payment,
    quick_pay,
    remove_receipt_item,
)


class POSTestBase(TestCase):
    """Common setup for POS tests."""

    def setUp(self):
        from companies.models import Company
        from pos.models import POSTerminal

        self.company = Company.objects.create(name="Test POS Co", oib="55555555551")
        self.user = User.objects.create_user("postest", password="test123")
        self.terminal = POSTerminal.objects.create(name="Terminal 1", company=self.company)


class TestSessionManagement(POSTestBase):
    def test_open_session(self):
        session = open_session(self.terminal, self.user, Decimal("500"))
        self.assertEqual(session.session_number, 1)
        self.assertEqual(session.opening_cash, Decimal("500"))
        self.assertEqual(session.operator, self.user)

    def test_open_session_increments_number(self):
        s1 = open_session(self.terminal, self.user)
        close_session(s1, Decimal("0"))
        s2 = open_session(self.terminal, self.user)
        self.assertEqual(s2.session_number, 2)

    def test_cannot_open_duplicate(self):
        open_session(self.terminal, self.user)
        with self.assertRaises(SessionError):
            open_session(self.terminal, self.user)

    def test_close_session(self):
        session = open_session(self.terminal, self.user)
        result = close_session(session, Decimal("1000"))
        self.assertTrue(result)
        session.refresh_from_db()
        self.assertEqual(session.closing_cash, Decimal("1000"))
        self.assertIsNotNone(session.closed_at)

    def test_cannot_close_with_open_receipts(self):
        session = open_session(self.terminal, self.user)
        create_receipt(session)
        with self.assertRaises(SessionError):
            close_session(session)


class TestReceiptOperations(POSTestBase):
    def setUp(self):
        super().setUp()
        self.session = open_session(self.terminal, self.user)

    def test_create_receipt(self):
        r = create_receipt(self.session, note="Test")
        self.assertEqual(r.receipt_number, 1)
        self.assertEqual(r.note, "Test")

    def test_add_item(self):
        r = create_receipt(self.session)
        item = add_receipt_item(r, None, "Kava", Decimal("2"), Decimal("2.50"))
        self.assertEqual(item.description, "Kava")
        r.refresh_from_db()
        self.assertGreater(r.total, Decimal("0"))

    def test_remove_item(self):
        r = create_receipt(self.session)
        item = add_receipt_item(r, None, "Kava", Decimal("1"), Decimal("3.00"))
        result = remove_receipt_item(r, item.pk)
        self.assertTrue(result)
        r.refresh_from_db()
        self.assertEqual(r.total, Decimal("0"))

    def test_remove_nonexistent_item(self):
        r = create_receipt(self.session)
        result = remove_receipt_item(r, 99999)
        self.assertFalse(result)


class TestPayment(POSTestBase):
    def setUp(self):
        super().setUp()
        self.session = open_session(self.terminal, self.user)

    def test_process_payment(self):
        r = create_receipt(self.session)
        add_receipt_item(r, None, "Pivo", Decimal("1"), Decimal("4.00"))
        r.refresh_from_db()

        result = process_payment(r, "CASH", Decimal("10.00"), self.user)
        self.assertIn("receipt_id", result)
        self.assertGreater(result["change"], Decimal("0"))

        r.refresh_from_db()
        self.assertEqual(r.status, "paid")

    def test_cannot_pay_empty_receipt(self):
        r = create_receipt(self.session)
        with self.assertRaises(PaymentError):
            process_payment(r, "CASH", Decimal("10.00"))

    def test_cannot_pay_twice(self):
        r = create_receipt(self.session)
        add_receipt_item(r, None, "Sok", Decimal("1"), Decimal("2.00"))
        r.refresh_from_db()
        process_payment(r, "CASH", Decimal("5.00"))
        with self.assertRaises(PaymentError):
            process_payment(r, "CASH", Decimal("5.00"))

    def test_quick_pay(self):
        items = [
            {"name": "Espresso", "qty": 2, "price": "1.50", "tax": 25},
            {"name": "Voda", "qty": 1, "price": "1.00", "tax": 25},
        ]
        result = quick_pay(self.session, items, "CASH", Decimal("10"), user=self.user)
        self.assertTrue(result["receipt_id"])
        self.assertEqual(result["receipt_number"], 1)

    def test_quick_pay_empty_items(self):
        with self.assertRaises(PaymentError):
            quick_pay(self.session, [], "CASH")


class TestZReport(POSTestBase):
    def test_zreport_empty_session(self):
        session = open_session(self.terminal, self.user)
        report = generate_zreport(session)
        self.assertEqual(report["total_sales"], Decimal("0"))
        self.assertEqual(report["receipt_count"], 0)

    def test_zreport_with_sales(self):
        session = open_session(self.terminal, self.user)
        quick_pay(session, [{"name": "Item", "qty": 1, "price": "10"}], "CASH", Decimal("10"), user=self.user)
        report = generate_zreport(session)
        self.assertEqual(report["receipt_count"], 1)
        self.assertGreater(report["total_sales"], Decimal("0"))
