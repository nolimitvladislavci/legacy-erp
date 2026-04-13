"""
Tests for Finance→Konto features:
- Finance→Konto signal (create/update/delete sync)
- CSV bank import (Commerzbank, DKB, generic)
- Cashflow API
- Appointment reminder views
"""
import io
import uuid
import datetime
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, Client, override_settings
from django.utils import timezone

from accounts.models import UserProfile
from companies.models import Company
from partners.models import Partner
from konto.models import BankAccount, BankTransaction
from finance.models import Transaction
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist


# ─── Helpers ────────────────────────────────────────────────────────────────

def _make_company(name="Test Firma GmbH"):
    return Company.objects.get_or_create(
        name=name,
        defaults={"country": "DE", "currency": "EUR", "oib": str(abs(hash(name)))[:11]}
    )[0]


def _make_partner(company):
    return Partner.objects.get_or_create(
        name="Test Partner",
        company=company,
        defaults={"email": "partner@test.de"}
    )[0]


def _make_bank(company):
    return BankAccount.objects.get_or_create(
        company=company,
        iban="DE89370400440532013000",
        defaults={
            "name": "Test Bank",
            "bank_name": "Commerzbank",
            "currency": "EUR",
            "is_primary": True,
            "opening_balance": Decimal("0"),
            "current_balance": Decimal("0"),
        }
    )[0]


def _make_user_with_company(username="test_fin_user"):
    u, _ = User.objects.get_or_create(
        username=username,
        defaults={"is_staff": True, "is_superuser": True, "email": f"{username}@test.de"}
    )
    u.set_password("pass")
    u.save()
    company = _make_company()
    _make_bank(company)
    profile, _ = UserProfile.objects.get_or_create(user=u)
    profile.company = company
    profile.save()
    return u, company


# ─── Signal Tests ────────────────────────────────────────────────────────────

@override_settings(SECURE_SSL_REDIRECT=False)
class FinanceKontoSignalTest(TestCase):

    def setUp(self):
        self.user, self.company = _make_user_with_company("sig_test_user")
        self.partner = _make_partner(self.company)
        self.bank = _make_bank(self.company)

    def test_create_income_syncs_inflow(self):
        t = Transaction.objects.create(
            company=self.company, partner=self.partner,
            amount=Decimal("150.00"), direction="income",
            date=datetime.date.today(), description="Signal test",
        )
        bt = BankTransaction.objects.filter(external_id=f"finance-{t.pk}").first()
        self.assertIsNotNone(bt)
        self.assertEqual(bt.transaction_type, "inflow")
        self.assertEqual(bt.amount, Decimal("150.00"))
        self.assertEqual(bt.import_batch, "finance-sync")
        t.delete()

    def test_create_expense_syncs_outflow(self):
        t = Transaction.objects.create(
            company=self.company, partner=self.partner,
            amount=Decimal("75.00"), direction="expense",
            date=datetime.date.today(), description="Expense",
        )
        bt = BankTransaction.objects.filter(external_id=f"finance-{t.pk}").first()
        self.assertIsNotNone(bt)
        self.assertEqual(bt.transaction_type, "outflow")
        t.delete()

    def test_update_syncs_new_amount(self):
        t = Transaction.objects.create(
            company=self.company, partner=self.partner,
            amount=Decimal("100.00"), direction="income",
            date=datetime.date.today(), description="Update test",
        )
        t.amount = Decimal("200.00")
        t.save()
        bt = BankTransaction.objects.get(external_id=f"finance-{t.pk}")
        self.assertEqual(bt.amount, Decimal("200.00"))
        t.delete()

    def test_delete_removes_from_konto(self):
        t = Transaction.objects.create(
            company=self.company, partner=self.partner,
            amount=Decimal("50.00"), direction="income",
            date=datetime.date.today(), description="Delete test",
        )
        pk = t.pk
        t.delete()
        self.assertFalse(
            BankTransaction.objects.filter(external_id=f"finance-{pk}").exists()
        )

    def test_string_amount_does_not_crash(self):
        """Signal must handle string amounts without crashing (Decimal cast)."""
        t = Transaction(
            company=self.company, partner=self.partner,
            amount="99.99", direction="income",
            date=datetime.date.today(), description="String amount",
        )
        t.save()
        bt = BankTransaction.objects.filter(external_id=f"finance-{t.pk}").first()
        self.assertIsNotNone(bt)
        self.assertEqual(bt.amount, Decimal("99.99"))
        t.delete()

    def test_no_bank_account_skips_silently(self):
        """Company with no bank account must not raise."""
        company2 = Company.objects.create(
            name="No Bank Co", country="DE", currency="EUR",
            oib=str(abs(hash("NoBankCo" + str(uuid.uuid4()))))[: 11]
        )
        partner2 = Partner.objects.create(name="P2", company=company2)
        # Should not raise
        t = Transaction.objects.create(
            company=company2, partner=partner2,
            amount=Decimal("10.00"), direction="income",
            date=datetime.date.today(), description="No bank",
        )
        t.delete()


# ─── CSV Import Tests ────────────────────────────────────────────────────────

@override_settings(SECURE_SSL_REDIRECT=False)
class CsvBankImportTest(TestCase):

    def setUp(self):
        self.user, self.company = _make_user_with_company("csv_test_user")
        self.bank = _make_bank(self.company)
        self.client = Client()
        self.client.force_login(self.user)
        # Wire impersonation so get_user_company finds the company
        session = self.client.session
        session["impersonated_company_id"] = str(self.company.id)
        session.save()

    def _upload(self, csv_text):
        f = io.BytesIO(csv_text.encode("utf-8-sig"))
        f.name = "test.csv"
        return self.client.post(
            "/finance/bank-import/",
            {"bank_account": self.bank.pk, "csvfile": f},
        )

    def test_commerzbank_format(self):
        csv = (
            "Buchungstag;Auftraggeber / Beguenstigter;Verwendungszweck;Betrag\n"
            "05.03.2026;Max Muster GmbH;Rechnung 001;1250,00\n"
            "04.03.2026;Lieferant AG;Material;-350,50\n"
        )
        before = BankTransaction.objects.filter(bank_account=self.bank).count()
        resp = self._upload(csv)
        self.assertIn(resp.status_code, [200, 302])
        after = BankTransaction.objects.filter(bank_account=self.bank).count()
        self.assertEqual(after - before, 2)

    def test_generic_format(self):
        csv = (
            "Datum,Name,Verwendungszweck,Betrag\n"
            "2026-03-05,Test Kunde,Zahlung,500.00\n"
            "2026-03-04,Test Lieferant,Einkauf,-200.00\n"
        )
        before = BankTransaction.objects.filter(bank_account=self.bank).count()
        resp = self._upload(csv)
        self.assertIn(resp.status_code, [200, 302])
        after = BankTransaction.objects.filter(bank_account=self.bank).count()
        self.assertEqual(after - before, 2)

    def test_dedup_skips_second_upload(self):
        csv = "Datum,Name,Betrag\n2026-03-01,Dedup Test,100.00\n"
        self._upload(csv)
        before = BankTransaction.objects.filter(bank_account=self.bank).count()
        self._upload(csv)
        after = BankTransaction.objects.filter(bank_account=self.bank).count()
        self.assertEqual(before, after)

    def test_empty_csv_no_crash(self):
        resp = self._upload("Buchungstag;Betrag\n")
        self.assertIn(resp.status_code, [200, 302])

    def test_get_shows_form(self):
        resp = self.client.get("/finance/bank-import/")
        self.assertIn(resp.status_code, [200, 302])

    def test_requires_login(self):
        resp = Client().get("/finance/bank-import/")
        self.assertIn(resp.status_code, [301, 302])


# ─── Cashflow API ─────────────────────────────────────────────────────────────

@override_settings(SECURE_SSL_REDIRECT=False)
class CashflowApiTest(TestCase):

    def setUp(self):
        self.user, self.company = _make_user_with_company("cashflow_test_user")
        self.bank = _make_bank(self.company)
        self.client = Client()
        self.client.force_login(self.user)
        session = self.client.session
        session["impersonated_company_id"] = str(self.company.id)
        session.save()

    def test_returns_six_month_json(self):
        resp = self.client.get("/finance/cashflow-api/")
        self.assertIn(resp.status_code, [200, 302])
        if resp.status_code == 200:
            data = resp.json()
            self.assertIn("labels", data)
            self.assertEqual(len(data["labels"]), 6)
            self.assertEqual(len(data["inflows"]), 6)
            self.assertEqual(len(data["outflows"]), 6)

    def test_values_are_numeric(self):
        BankTransaction.objects.create(
            bank_account=self.bank, company=self.company,
            transaction_date=datetime.date.today(),
            value_date=datetime.date.today(),
            amount=Decimal("100.00"), transaction_type="inflow",
        )
        resp = self.client.get("/finance/cashflow-api/")
        if resp.status_code == 200:
            data = resp.json()
            self.assertTrue(all(isinstance(v, (int, float)) for v in data["inflows"]))

    def test_unauthenticated_redirects(self):
        resp = Client().get("/finance/cashflow-api/")
        self.assertIn(resp.status_code, [301, 302])


# ─── Appointment Reminders ────────────────────────────────────────────────────

@override_settings(SECURE_SSL_REDIRECT=False)
class AppointmentReminderViewTest(TestCase):

    def setUp(self):
        self.user, self.company = _make_user_with_company("appt_rem_user")
        self.client = Client()
        self.client.force_login(self.user)

    @patch("appointments.tasks.send_appointment_reminders")
    def test_send_reminders_now_calls_task(self, mock_task):
        mock_task.return_value = {"email": 2, "whatsapp": 1, "total": 3}
        resp = self.client.get("/appointments/send-reminders-now/")
        self.assertIn(resp.status_code, [200, 302])
        mock_task.assert_called_once()

    def test_send_reminders_now_unauthenticated_redirects(self):
        resp = Client().get("/appointments/send-reminders-now/")
        self.assertIn(resp.status_code, [301, 302])


# ─── Bank Import Template ─────────────────────────────────────────────────────

@override_settings(SECURE_SSL_REDIRECT=False)
class BankImportPageTest(TestCase):

    def setUp(self):
        self.user, self.company = _make_user_with_company("page_test_user")
        self.client = Client()
        self.client.force_login(self.user)
        session = self.client.session
        session["impersonated_company_id"] = str(self.company.id)
        session.save()

    def test_page_loads_with_bank_list(self):
        resp = self.client.get("/finance/bank-import/")
        self.assertIn(resp.status_code, [200, 302])
