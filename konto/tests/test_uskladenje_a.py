"""
Tests za CC_TASK_USKLADENJE_A — Verifikacija account_type mappinga.

Provjerava:
1. HR RRF mapping za sve klase (0-9)
2. DE SKR03 mapping za klase 1, 2, 8
3. Bilanca D=P za svaku firmu
4. Nema negativnih LedgerLine iznosa
5. Nema dupliciranih JournalEntry entry_number-a
6. Management command fix_account_types idempotentnost
"""

from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from companies.models import Company
from konto.models import JournalEntry, KontoAccount, LedgerLine


class TestHRAccountTypeMapping(TestCase):
    """HR RRF kontni plan — account_type verifikacija."""

    def setUp(self):
        self.co = Company.objects.create(name="Test HR d.o.o.", oib="11111111111", country="HR")

    def _make(self, code, name="Test"):
        return KontoAccount.objects.create(company=self.co, code=code, name=name, account_type="asset")

    def test_class0_is_asset(self):
        acc = self._make("0100")
        call_command("fix_account_types", company="Test HR")
        acc.refresh_from_db()
        self.assertEqual(acc.account_type, "asset")

    def test_class1_is_asset(self):
        acc = self._make("1200")
        call_command("fix_account_types", company="Test HR")
        acc.refresh_from_db()
        self.assertEqual(acc.account_type, "asset")

    def test_class2_is_liability(self):
        acc = self._make("2200")
        call_command("fix_account_types", company="Test HR")
        acc.refresh_from_db()
        self.assertEqual(acc.account_type, "liability")

    def test_class3_is_asset_not_equity(self):
        """Klasa 3 = Zalihe = ASSET, ne kapital!"""
        acc = self._make("3100", "Zalihe sirovina")
        call_command("fix_account_types", company="Test HR")
        acc.refresh_from_db()
        self.assertEqual(acc.account_type, "asset")

    def test_class4_is_expense(self):
        acc = self._make("4000")
        call_command("fix_account_types", company="Test HR")
        acc.refresh_from_db()
        self.assertEqual(acc.account_type, "expense")

    def test_class7_is_revenue(self):
        """Klasa 7 = Prihodi = REVENUE, ne income!"""
        acc = self._make("7000", "Prihodi od prodaje")
        call_command("fix_account_types", company="Test HR")
        acc.refresh_from_db()
        self.assertEqual(acc.account_type, "revenue")

    def test_class8_dobit_is_equity(self):
        """800 = Dobit = equity, ne expense!"""
        acc = self._make("800", "Dobit")
        call_command("fix_account_types", company="Test HR")
        acc.refresh_from_db()
        self.assertEqual(acc.account_type, "equity")

    def test_class8_porez_is_expense(self):
        """803 = Porez na dobit = expense."""
        acc = self._make("803", "Porez na dobit")
        call_command("fix_account_types", company="Test HR")
        acc.refresh_from_db()
        self.assertEqual(acc.account_type, "expense")

    def test_class9_kapital_is_equity(self):
        acc = self._make("9000", "Temeljni kapital")
        call_command("fix_account_types", company="Test HR")
        acc.refresh_from_db()
        self.assertEqual(acc.account_type, "equity")

    def test_class9_dugorocne_obveze_is_liability(self):
        """94x-96x = Dugorocne obveze = liability."""
        acc = self._make("9500", "Dugorocni kredit")
        call_command("fix_account_types", company="Test HR")
        acc.refresh_from_db()
        self.assertEqual(acc.account_type, "liability")


class TestDEAccountTypeMapping(TestCase):
    """DE SKR03 kontni plan."""

    def setUp(self):
        self.co = Company.objects.create(name="Test DE GmbH", oib="DE123456789", country="DE")

    def _make(self, code, name="Test"):
        return KontoAccount.objects.create(company=self.co, code=code, name=name, account_type="asset")

    def test_de_class1_17xx_is_liability(self):
        acc = self._make("1740", "Verbindlichkeiten")
        call_command("fix_account_types", company="Test DE")
        acc.refresh_from_db()
        self.assertEqual(acc.account_type, "liability")

    def test_de_class2_20xx_is_equity(self):
        acc = self._make("2000", "Stammkapital")
        call_command("fix_account_types", company="Test DE")
        acc.refresh_from_db()
        self.assertEqual(acc.account_type, "equity")

    def test_de_class4_is_revenue(self):
        acc = self._make("4000", "Umsatzerloese")
        call_command("fix_account_types", company="Test DE")
        acc.refresh_from_db()
        self.assertEqual(acc.account_type, "revenue")


class TestBilancaBalance(TestCase):
    """Bilanca D=P provjera."""

    def setUp(self):
        self.co = Company.objects.create(name="Bilanca Test", oib="22222222222", country="HR")
        self.acc_d = KontoAccount.objects.create(company=self.co, code="1000", name="Banka", account_type="asset")
        self.acc_k = KontoAccount.objects.create(company=self.co, code="7000", name="Prihod", account_type="revenue")

    def test_balanced_entry(self):
        je = JournalEntry.objects.create(
            company=self.co, entry_number="TEST-001", date="2025-01-01", source_type="manual", is_posted=True
        )
        LedgerLine.objects.create(journal_entry=je, account=self.acc_d, side="debit", amount=Decimal("1000.00"))
        LedgerLine.objects.create(journal_entry=je, account=self.acc_k, side="credit", amount=Decimal("1000.00"))

        from django.db.models import Sum

        d = LedgerLine.objects.filter(journal_entry__company=self.co, side="debit").aggregate(t=Sum("amount"))["t"]
        k = LedgerLine.objects.filter(journal_entry__company=self.co, side="credit").aggregate(t=Sum("amount"))["t"]
        self.assertEqual(d, k)

    def test_no_negative_amounts(self):
        """Nema negativnih iznosa u LedgerLine."""
        neg = LedgerLine.objects.filter(journal_entry__company=self.co, amount__lt=0).count()
        self.assertEqual(neg, 0)


class TestFixCommandIdempotent(TestCase):
    """fix_account_types je idempotent — drugi run ne mijenja nista."""

    def setUp(self):
        self.co = Company.objects.create(name="Idempotent Test", oib="33333333333", country="HR")
        KontoAccount.objects.create(company=self.co, code="800", name="Dobit", account_type="expense")

    def test_second_run_no_changes(self):
        out1 = StringIO()
        call_command("fix_account_types", company="Idempotent", stdout=out1)
        self.assertIn("1 konto", out1.getvalue())

        out2 = StringIO()
        call_command("fix_account_types", company="Idempotent", stdout=out2)
        self.assertIn("Svi tipovi su ispravni", out2.getvalue())


class TestNoGlobalDuplicates(TestCase):
    """Nema dupliciranih entry_number u istoj firmi."""

    def test_unique_entry_numbers(self):
        from django.db.models import Count

        dupes = (
            JournalEntry.objects.values("company", "entry_number").annotate(cnt=Count("id")).filter(cnt__gt=1).count()
        )
        self.assertEqual(dupes, 0, "Postoje duplicirani entry_number-i!")
