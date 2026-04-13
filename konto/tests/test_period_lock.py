"""Tests for accounting period lock - DB triggers + view."""
import datetime

from django.contrib.auth.models import User
from django.db.utils import InternalError
from django.test import TransactionTestCase, override_settings

from accounts.models import UserProfile
from companies.models import Company
from invoicing.models import Invoice
from konto.models import AccountingPeriod, JournalEntry


@override_settings(SECURE_SSL_REDIRECT=False)
class PeriodLockViewTests(TransactionTestCase):

    def setUp(self):
        self.company = Company.objects.create(name="Test Lock Co", oib="11111111111")
        self.user = User.objects.create_superuser(
            "locktest", email="lock@test.com", password="test123")
        UserProfile.objects.filter(user=self.user).delete()
        UserProfile.objects.create(
            user=self.user, company=self.company, role="company_admin"
        )
        self.client.login(username="locktest", password="test123")

    def test_period_management_page_loads(self):
        resp = self.client.get("/konto/periods/")
        self.assertIn(resp.status_code, [200, 302],
            f"Expected 200 or 302, got {resp.status_code}")
        if resp.status_code == 302:
            self.assertIn("periods", resp.url,
                f"Expected redirect to periods, got {resp.url}")

    def test_lock_period_via_post(self):
        resp = self.client.post("/konto/periods/", {
            "action": "lock", "year": "2026", "month": "1",
        })
        self.assertEqual(resp.status_code, 302)
        period = AccountingPeriod.objects.get(
            company=self.company, year=2026, month=1)
        self.assertTrue(period.is_locked)
        self.assertIsNotNone(period.locked_at)
        self.assertEqual(period.locked_by, self.user)

    def test_unlock_period_via_post(self):
        period = AccountingPeriod.objects.create(
            company=self.company, year=2026, month=1, is_locked=True)
        resp = self.client.post("/konto/periods/", {
            "action": "unlock", "year": "2026", "month": "1",
        })
        self.assertEqual(resp.status_code, 302)
        period.refresh_from_db()
        self.assertFalse(period.is_locked)


class PeriodLockTriggerTests(TransactionTestCase):

    def setUp(self):
        self.company = Company.objects.create(name="Trigger Co", oib="22222222222")
        self.user = User.objects.create_user("trigtest", password="test123")
        self.period = AccountingPeriod.objects.create(
            company=self.company, year=2026, month=1,
            is_locked=True)

    def test_journal_entry_in_locked_period_raises(self):
        with self.assertRaises(InternalError) as ctx:
            JournalEntry.objects.create(
                company=self.company,
                entry_number="TEST-LOCK-001",
                date=datetime.date(2026, 1, 15),
                description="Should fail - locked period",
            )
        self.assertIn("zaklju", str(ctx.exception).lower())

    def test_invoice_in_locked_period_raises(self):
        with self.assertRaises(InternalError) as ctx:
            Invoice.objects.create(
                company=self.company,
                number="INV-LOCK-001",
                date_issued=datetime.date(2026, 1, 15),
                client_name="Test Client",
            )
        self.assertIn("zaklju", str(ctx.exception).lower())

    def test_journal_entry_in_unlocked_period_succeeds(self):
        self.period.is_locked = False
        self.period.save(update_fields=["is_locked"])
        entry = JournalEntry.objects.create(
            company=self.company,
            entry_number="TEST-OPEN-001",
            date=datetime.date(2026, 1, 15),
            description="Should succeed - open period",
        )
        self.assertIsNotNone(entry.pk)
        self.assertEqual(entry.entry_number, "TEST-OPEN-001")
