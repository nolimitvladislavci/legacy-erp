"""
Fenix V3 — POS Test Suite
Pokriva: modele, tier limit, fiskalizaciju, ghost receipt, smart price, tasks
"""
import json
import hashlib
import secrets
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone

from pos.models import (
    POSCompany, POSTerminal, POSCashier, POSSession,
    POSCategory, POSProduct, Table, POSReceipt,
    POSPricingRule, POSGhostReceipt, POSTierConfig,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_company(**kwargs):
    defaults = dict(name="Test Restoran", slug="test-restoran", industry="restaurant",
                    country="hr", fiscal_exempt=False)
    defaults.update(kwargs)
    return POSCompany.objects.create(**defaults)

def make_terminal(company, **kwargs):
    defaults = dict(name="Blagajna 1", poslovni_prostor="PP1", oznaka_blagajne="1")
    defaults.update(kwargs)
    return POSTerminal.objects.create(company=company, **defaults)

def make_cashier(terminal, pin="123456"):
    c = POSCashier(terminal=terminal, name="Test Blagajnik")
    c.set_pin(pin)
    c.save()
    return c

def make_session(terminal, cashier):
    return POSSession.objects.create(terminal=terminal, cashier=cashier, opening_cash=Decimal("100.00"))

def make_receipt(session, total=Decimal("10.00")):
    import uuid
    return POSReceipt.objects.create(
        receipt_id=str(uuid.uuid4())[:20],
        session=session,
        total=total,
        subtotal=total,
        is_paid=False,
    )


# ── 1. MODEL TESTOVI ──────────────────────────────────────────────────────────

class POSCompanyModelTest(TestCase):

    def test_create_company_defaults(self):
        c = make_company()
        self.assertEqual(c.country, "hr")
        self.assertFalse(c.fiscal_exempt)
        self.assertEqual(c.industry, "restaurant")

    def test_company_str(self):
        c = make_company()
        self.assertIn("Test Restoran", str(c))

    def test_fiscal_exempt_flag(self):
        c = make_company(fiscal_exempt=True)
        self.assertTrue(c.fiscal_exempt)

    def test_country_choices(self):
        c = make_company(country="de")
        self.assertEqual(c.country, "de")


class POSTerminalModelTest(TestCase):

    def test_terminal_create(self):
        company = make_company()
        t = make_terminal(company)
        self.assertTrue(t.is_active)
        self.assertTrue(str(t.terminal_id))  # UUID generated

    def test_terminal_str(self):
        company = make_company()
        t = make_terminal(company)
        self.assertIn("Test Restoran", str(t))
        self.assertIn("Blagajna 1", str(t))


class POSCashierPINTest(TestCase):

    def test_pin_hash_set_and_verify(self):
        company = make_company()
        terminal = make_terminal(company)
        cashier = make_cashier(terminal, pin="123456")
        self.assertTrue(cashier.verify_pin("123456"))
        self.assertFalse(cashier.verify_pin("wrong"))

    def test_pin_different_salts(self):
        company = make_company()
        terminal = make_terminal(company)
        c1 = make_cashier(terminal, pin="111111")
        c2 = make_cashier(terminal, pin="111111")
        # Isti PIN, različiti saltovi — hashevi moraju biti različiti
        self.assertNotEqual(c1.pin_hash, c2.pin_hash)

    def test_empty_pin_fails(self):
        company = make_company()
        terminal = make_terminal(company)
        cashier = make_cashier(terminal, pin="123456")
        cashier.pin_hash = ""
        cashier.save()
        self.assertFalse(cashier.verify_pin("123456"))


class POSReceiptFiskalTest(TestCase):

    def test_receipt_fiscal_fields_exist(self):
        company = make_company()
        terminal = make_terminal(company)
        cashier = make_cashier(terminal)
        session = make_session(terminal, cashier)
        receipt = make_receipt(session)

        # Sva nova fiscalna polja moraju biti dostupna
        self.assertEqual(receipt.jir, "")
        self.assertEqual(receipt.zki, "")
        self.assertIsNone(receipt.global_number)
        self.assertFalse(receipt.is_training)
        self.assertIsNone(receipt.fiscal_datetime)
        self.assertEqual(receipt.fiscal_retry_count, 0)
        self.assertEqual(receipt.fiscal_last_error, "")

    def test_receipt_is_cancelled_not_cancelled(self):
        """Provjera ispravnog naziva polja — bug je bio 'cancelled' umjesto 'is_cancelled'."""
        company = make_company()
        terminal = make_terminal(company)
        cashier = make_cashier(terminal)
        session = make_session(terminal, cashier)
        receipt = make_receipt(session)
        self.assertFalse(receipt.is_cancelled)
        # Provjeri da Django ne baca FieldError pri querysetu
        count = POSReceipt.objects.filter(is_cancelled=False).count()
        self.assertEqual(count, 1)

    def test_receipt_calculate_totals(self):
        company = make_company()
        terminal = make_terminal(company)
        cashier = make_cashier(terminal)
        session = make_session(terminal, cashier)
        import uuid
        receipt = POSReceipt.objects.create(
            receipt_id=str(uuid.uuid4())[:20],
            session=session,
            items=[
                {"name": "Kava", "price": "1.50", "quantity": 2, "tax_amount": "0.38"},
                {"name": "Voda", "price": "2.00", "quantity": 1, "tax_amount": "0.50"},
            ],
        )
        receipt.calculate_totals()
        self.assertEqual(receipt.subtotal, Decimal("5.00"))
        self.assertEqual(receipt.tax, Decimal("1.38"))
        self.assertEqual(receipt.total, Decimal("5.00") + Decimal("1.38"))


# ── 2. TIER LIMIT TESTOVI ─────────────────────────────────────────────────────

class POSTierConfigTest(TestCase):

    def setUp(self):
        self.company = make_company()
        self.terminal = make_terminal(self.company)
        self.cashier = make_cashier(self.terminal)
        self.session = make_session(self.terminal, self.cashier)

    def _make_paid_receipt(self):
        import uuid
        r = POSReceipt.objects.create(
            receipt_id=str(uuid.uuid4())[:20],
            session=self.session,
            total=Decimal("10.00"),
            is_paid=True,
            paid_at=timezone.now(),
        )
        return r

    def test_tier_for_company_creates_free(self):
        cfg = POSTierConfig.for_company(self.company)
        self.assertEqual(cfg.tier, POSTierConfig.TIER_FREE)
        self.assertEqual(cfg.monthly_limit, 50)

    def test_tier_ok_below_limit(self):
        cfg = POSTierConfig.for_company(self.company)
        # 0 transakcija — mora biti ok
        allowed, status, count, limit = cfg.check_tx_allowed()
        self.assertTrue(allowed)
        self.assertEqual(status, "ok")

    def test_tier_warning_zone(self):
        cfg = POSTierConfig.for_company(self.company)
        # Simuliramo 41 transakcija (warn_at=40)
        for _ in range(41):
            self._make_paid_receipt()
        allowed, status, count, limit = cfg.check_tx_allowed()
        self.assertTrue(allowed)
        self.assertEqual(status, "warning")

    def test_tier_limit_reached(self):
        cfg = POSTierConfig.for_company(self.company)
        # 50 transakcija = limit dostignut
        for _ in range(50):
            self._make_paid_receipt()
        allowed, status, count, limit = cfg.check_tx_allowed()
        self.assertFalse(allowed)
        self.assertEqual(status, "limit_reached")
        self.assertEqual(count, 50)

    def test_tier_pro_unlimited(self):
        cfg = POSTierConfig.for_company(self.company)
        cfg.tier = POSTierConfig.TIER_PRO
        cfg.save()
        self.assertIsNone(cfg.monthly_limit)
        allowed, status, count, limit = cfg.check_tx_allowed()
        self.assertTrue(allowed)
        self.assertIsNone(limit)

    def test_tier_count_excludes_cancelled(self):
        """is_cancelled=True ne smije se računati u limit."""
        cfg = POSTierConfig.for_company(self.company)
        import uuid
        # 1 plaćeni normalni
        POSReceipt.objects.create(
            receipt_id=str(uuid.uuid4())[:20], session=self.session,
            total=Decimal("5.00"), is_paid=True, paid_at=timezone.now(), is_cancelled=False
        )
        # 1 otkazani — ne smije se računati
        POSReceipt.objects.create(
            receipt_id=str(uuid.uuid4())[:20], session=self.session,
            total=Decimal("5.00"), is_paid=True, paid_at=timezone.now(), is_cancelled=True
        )
        count = cfg.get_monthly_tx_count()
        self.assertEqual(count, 1)


# ── 3. SMART PRICING TESTOVI ──────────────────────────────────────────────────

class POSPricingRuleTest(TestCase):

    def setUp(self):
        self.company = make_company()
        self.terminal = make_terminal(self.company)
        self.cat = POSCategory.objects.create(terminal=self.terminal, name="Pića")
        self.product = POSProduct.objects.create(
            terminal=self.terminal, category=self.cat,
            name="Kava", price=Decimal("2.00"), tax_rate="pdv25"
        )

    def test_percentage_discount(self):
        rule = POSPricingRule.objects.create(
            terminal=self.terminal, name="Popust 10%",
            rule_type="product_disc", discount_pct=Decimal("10.00"),
            product=self.product
        )
        new_price = rule.calculate_price(2.00)
        self.assertAlmostEqual(new_price, 1.80, places=2)

    def test_absolute_discount(self):
        rule = POSPricingRule.objects.create(
            terminal=self.terminal, name="Popust 0.50€",
            rule_type="product_disc", discount_abs=Decimal("0.50"),
            product=self.product
        )
        new_price = rule.calculate_price(2.00)
        self.assertAlmostEqual(new_price, 1.50, places=2)

    def test_bulk_min_quantity_not_met(self):
        rule = POSPricingRule.objects.create(
            terminal=self.terminal, name="Bulk 5+",
            rule_type="bulk", discount_pct=Decimal("15.00"),
            min_quantity=5, product=self.product
        )
        # Samo 3 komada — popust se ne primjenjuje
        new_price = rule.calculate_price(2.00, quantity=3)
        self.assertAlmostEqual(new_price, 2.00, places=2)

    def test_bulk_min_quantity_met(self):
        rule = POSPricingRule.objects.create(
            terminal=self.terminal, name="Bulk 5+",
            rule_type="bulk", discount_pct=Decimal("15.00"),
            min_quantity=5, product=self.product
        )
        new_price = rule.calculate_price(2.00, quantity=5)
        self.assertAlmostEqual(new_price, 1.70, places=2)


# ── 4. GHOST RECEIPT TESTOVI ──────────────────────────────────────────────────

class POSGhostReceiptTest(TestCase):

    def setUp(self):
        self.company = make_company()
        self.terminal = make_terminal(self.company)
        self.cashier = make_cashier(self.terminal)
        self.session = make_session(self.terminal, self.cashier)
        self.receipt = make_receipt(self.session, total=Decimal("25.00"))
        self.receipt.is_paid = True
        self.receipt.paid_at = timezone.now()
        self.receipt.save()

    def test_ghost_receipt_create(self):
        ghost = POSGhostReceipt.objects.create(
            receipt=self.receipt, channel="email",
            recipient="test@test.com", success=True
        )
        self.assertEqual(ghost.channel, "email")
        self.assertTrue(ghost.success)

    def test_ghost_receipt_whatsapp(self):
        ghost = POSGhostReceipt.objects.create(
            receipt=self.receipt, channel="whatsapp",
            recipient="+385912345678", success=False,
            error="WAHA timeout"
        )
        self.assertFalse(ghost.success)
        self.assertIn("WAHA", ghost.error)

    def test_ghost_receipt_str(self):
        ghost = POSGhostReceipt.objects.create(
            receipt=self.receipt, channel="email",
            recipient="x@x.com", success=True
        )
        self.assertIn("email", str(ghost))


# ── 5. SESSION CLOSE TESTOVI ──────────────────────────────────────────────────

class POSSessionCloseTest(TestCase):

    def test_session_close_updates_cashier(self):
        company = make_company()
        terminal = make_terminal(company)
        cashier = make_cashier(terminal)
        session = make_session(terminal, cashier)
        cashier.hourly_rate = Decimal("10.00")
        cashier.save()

        import time
        time.sleep(0.01)  # osiguraj delta > 0
        session.close_session(closing_cash=Decimal("150.00"))

        self.assertEqual(session.status, "closed")
        self.assertIsNotNone(session.closed_at)

        cashier.refresh_from_db()
        self.assertGreater(cashier.total_hours, 0)


# ── 6. FISCALIZATION TASK — UNIT ──────────────────────────────────────────────

class POSFiscalizeTaskTest(TestCase):

    def setUp(self):
        self.company = make_company(country="hr", fiscal_exempt=False)
        self.terminal = make_terminal(self.company)
        self.cashier = make_cashier(self.terminal)
        self.session = make_session(self.terminal, self.cashier)

    def test_skip_training_mode(self):
        """is_training=True → task ne šalje na FINU."""
        import uuid
        receipt = POSReceipt.objects.create(
            receipt_id=str(uuid.uuid4())[:20],
            session=self.session, total=Decimal("10.00"),
            is_paid=True, is_training=True
        )
        # Pozovi task direktno (ne async)
        from pos.tasks import fiscalize_receipt
        result = fiscalize_receipt(receipt.pk)
        self.assertEqual(result, {"skipped": "training_mode"})

    def test_skip_already_fiscalized(self):
        """Ako JIR već postoji — task preskače."""
        import uuid
        receipt = POSReceipt.objects.create(
            receipt_id=str(uuid.uuid4())[:20],
            session=self.session, total=Decimal("10.00"),
            is_paid=True, jir="JIR-123456"
        )
        from pos.tasks import fiscalize_receipt
        result = fiscalize_receipt(receipt.pk)
        self.assertEqual(result, {"skipped": "already_fiscalized"})

    def test_skip_fiscal_exempt_company(self):
        """fiscal_exempt=True → task preskače."""
        import uuid
        self.company.fiscal_exempt = True
        self.company.save()
        receipt = POSReceipt.objects.create(
            receipt_id=str(uuid.uuid4())[:20],
            session=self.session, total=Decimal("10.00"), is_paid=True
        )
        from pos.tasks import fiscalize_receipt
        result = fiscalize_receipt(receipt.pk)
        self.assertIn("skipped", result)
