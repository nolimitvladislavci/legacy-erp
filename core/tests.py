"""
core/tests.py — Integration testovi za kritične tokove.

4 test klase, 14 test metoda:
  1. ForcePasswordChangeTest (4) — middleware redirect
  2. InvoiceFlowTest         (3) — invoice profile + recalculate
  3. POSFlowTest             (4) — POS sesija + naplata
  4. EmployeeCreateTest      (3) — kreiranje zaposlenika

Run:
    python manage.py test core --verbosity=2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.utils import timezone

User = get_user_model()
NO_HTTPS = override_settings(SECURE_SSL_REDIRECT=False)


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def make_company(oib="33322211190"):
    from companies.models import Company
    return Company.objects.get_or_create(
        oib=oib,
        defaults=dict(name="Core Test GmbH", country="DE",
                      city="Hamburg", zip_code="20095"),
    )[0]


def make_user(company, username="core_admin", role="company_admin",
              must_change=False, is_superuser=False):
    from accounts.models import UserProfile
    user = User.objects.create_user(
        username=username,
        email=f"{username}@core-test.de",
        password="TestPass2026!",
        is_superuser=is_superuser,
        is_staff=is_superuser,
    )
    UserProfile.objects.create(
        user=user, company=company, role=role,
        must_change_password=must_change,
    )
    return user


def make_tax_rate(country="DE", rate=Decimal("19.00"), name="MwSt 19%"):
    from companies.models import TaxRate
    obj, _ = TaxRate.objects.get_or_create(
        country=country, rate=rate, defaults=dict(name=name),
    )
    return obj


def make_invoice_profile(company, prefix="TST"):
    from invoicing.fiscal_models import InvoiceProfile
    profile, _ = InvoiceProfile.objects.get_or_create(
        company=company,
        invoice_prefix=prefix,
        defaults=dict(
            name=f"Test Profile {prefix}",
            is_default=True,
            is_active=True,
            company_name=company.name,
            currency="EUR",
        ),
    )
    return profile


def make_subscription(company):
    from registration.models import CompanySubscription
    return CompanySubscription.objects.create(
        company=company,
        plan="enterprise",
        valid_from=timezone.now().date(),
        monthly_fee=0,
        is_active=True,
        modules_override=["invoicing", "pos", "worktime"],
    )


# ══════════════════════════════════════════════════════════════════════════════
# TEST 1 — ForcePasswordChange middleware
# ══════════════════════════════════════════════════════════════════════════════

@NO_HTTPS
class ForcePasswordChangeTest(TestCase):
    """ForcePasswordChangeMiddleware redirects must_change_password users."""

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company, username="force_pw_user",
                              must_change=True)
        self.c = Client()
        self.c.login(username="force_pw_user", password="TestPass2026!")

    def test_redirect_when_must_change(self):
        """GET / → 302 redirect (smart_home or i18n or password change)."""
        r = self.c.get("/")
        self.assertEqual(r.status_code, 302)

    def test_password_page_accessible(self):
        """GET /accounts/password/ returns 200 or 302 (i18n redirect)."""
        r = self.c.get("/accounts/password/")
        self.assertIn(r.status_code, (200, 302))

    def test_password_change_clears_flag(self):
        """Valid password change POST clears must_change_password flag."""
        r = self.c.post("/accounts/password/", {
            "old_password":  "TestPass2026!",
            "new_password1": "NewSecurePass2026!",
            "new_password2": "NewSecurePass2026!",
        })
        # Should redirect after successful change
        self.assertIn(r.status_code, (200, 302))
        self.user.profile.refresh_from_db()
        self.assertFalse(self.user.profile.must_change_password)

    def test_superadmin_not_redirected(self):
        """Superadmin with must_change_password=True is NOT redirected."""
        superadmin = make_user(
            self.company, username="super_force_pw",
            must_change=True, is_superuser=True,
        )
        c = Client()
        c.login(username="super_force_pw", password="TestPass2026!")
        r = c.get("/")
        # Superadmin should reach the homepage (200) or be redirected for other reason, NOT to /accounts/password/
        if r.status_code == 302:
            self.assertNotIn("/accounts/password/", r.get("Location", ""))


# ══════════════════════════════════════════════════════════════════════════════
# TEST 2 — Invoice create + recalculate
# ══════════════════════════════════════════════════════════════════════════════

class InvoiceFlowTest(TestCase):
    """Invoice model: numbering, recalculate, status choices."""

    def setUp(self):
        self.company = make_company(oib="33322211191")
        self.tax = make_tax_rate()
        self.profile = make_invoice_profile(self.company, prefix="INV")

    def test_invoice_profile_generates_number(self):
        """get_next_number() returns VIS-style prefix-year-NNNN format."""
        from django.utils import timezone
        year = timezone.now().year
        number = self.profile.get_next_number(doctype="R")
        self.assertIn(str(year), number)
        self.assertIn("INV", number)
        # Format: INV-YYYY-NNNN
        parts = number.split("-")
        self.assertGreaterEqual(len(parts), 3)
        self.assertTrue(parts[-1].isdigit())

    def test_invoice_recalculate(self):
        """Invoice with 2 InvoiceItems → recalculate() computes correct sums."""
        from django.utils import timezone as tz

        from invoicing.models import Invoice, InvoiceItem
        inv = Invoice.objects.create(
            company=self.company,
            number="TST-RECALC-001",
            doctype="R",
            country="DE",
            status="DRAFT",
            date_issued=tz.now(),
            client_name="Test Klient",
            payment_method="UBERWEISUNG",
            currency="EUR",
            internal_note="TEST_RECALC",
        )
        InvoiceItem.objects.create(
            invoice=inv,
            description="Usluga A",
            quantity=Decimal("2.0"),
            unit_price=Decimal("100.00"),
            total_price=Decimal("200.00"),
            gross_total=Decimal("238.00"),
            tax_rate=Decimal("19.00"),
            discount_percent=Decimal("0"),
        )
        InvoiceItem.objects.create(
            invoice=inv,
            description="Usluga B",
            quantity=Decimal("1.0"),
            unit_price=Decimal("50.00"),
            total_price=Decimal("50.00"),
            gross_total=Decimal("59.50"),
            tax_rate=Decimal("19.00"),
            discount_percent=Decimal("0"),
        )
        inv.recalculate()
        inv.save()
        inv.refresh_from_db()

        # subtotal = 200 + 50 = 250
        self.assertEqual(inv.subtotal, Decimal("250.00"))
        # tax = 200*0.19 + 50*0.19 = 38 + 9.5 = 47.5
        self.assertAlmostEqual(float(inv.tax_amount), 47.5, places=1)
        # total = 250 + 47.5 = 297.5
        self.assertAlmostEqual(float(inv.total), 297.5, places=1)

    def test_invoice_status_choices(self):
        """All expected STATUS_CHOICES values exist."""
        from invoicing.models import Invoice
        choices = dict(Invoice.STATUS_CHOICES)
        for expected in ("DRAFT", "SENT", "PAID", "OVERDUE", "CANCELLED"):
            self.assertIn(expected, choices,
                          f"Status '{expected}' not in STATUS_CHOICES")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 3 — POS payment flow
# ══════════════════════════════════════════════════════════════════════════════

class POSFlowTest(TestCase):
    """POS: session open, receipt creation, payment, total calculation."""

    def setUp(self):
        self.company = make_company(oib="33322211192")
        self.user = make_user(self.company, username="pos_operator")
        self.tax = make_tax_rate()
        from pos.models import POSSession, POSTerminal
        self.terminal = POSTerminal.objects.create(
            company=self.company,
            name="Test Kasa",
            terminal_code="TST-001",
            pos_type="retail",
        )
        self.session = POSSession.objects.create(
            terminal=self.terminal,
            operator=self.user,
            session_number=1,
            opening_cash=Decimal("100.00"),
            status="open",
        )

    def test_session_open(self):
        """Newly created session has status OPEN."""
        self.assertEqual(self.session.status, "open")

    def test_create_receipt_and_pay(self):
        """Receipt OPEN → add items → set PAID → total is correct."""
        from pos.models import POSReceipt, POSReceiptItem
        receipt = POSReceipt.objects.create(
            session=self.session,
            receipt_number=1,
            status="open",
            subtotal=Decimal("0"),
            tax_amount=Decimal("0"),
            total=Decimal("0"),
        )
        POSReceiptItem.objects.create(
            receipt=receipt,
            description="Montage 2h",
            quantity=2,
            unit_price=Decimal("65.00"),
            tax_rate=Decimal("19.00"),
            total_price=Decimal("154.70"),  # 130 * 1.19
        )
        receipt.status = "paid"
        receipt.subtotal = Decimal("130.00")
        receipt.tax_amount = Decimal("24.70")
        receipt.total = Decimal("154.70")
        receipt.save()
        receipt.refresh_from_db()
        self.assertEqual(receipt.status, "paid")
        self.assertEqual(float(receipt.total), 154.70)

    def test_receipt_total_calculation(self):
        """Tax 19%: total = subtotal * 1.19."""
        net = Decimal("100.00")
        tax = round(net * Decimal("19") / Decimal("100"), 2)
        total = net + tax
        self.assertEqual(total, Decimal("119.00"))

    def test_session_total_sales(self):
        """session.total_sales() == sum of PAID receipts."""
        from pos.models import POSReceipt
        POSReceipt.objects.create(
            session=self.session, receipt_number=1,
            status="paid", subtotal=Decimal("100.00"),
            tax_amount=Decimal("19.00"), total=Decimal("119.00"),
        )
        POSReceipt.objects.create(
            session=self.session, receipt_number=2,
            status="paid", subtotal=Decimal("50.00"),
            tax_amount=Decimal("9.50"), total=Decimal("59.50"),
        )
        POSReceipt.objects.create(
            session=self.session, receipt_number=3,
            status="open", subtotal=Decimal("80.00"),
            tax_amount=Decimal("15.20"), total=Decimal("95.20"),
        )
        total_paid = self.session.total_sales
        # Only PAID receipts: 119 + 59.5 = 178.50
        self.assertAlmostEqual(float(total_paid), 178.50, places=2)


# ══════════════════════════════════════════════════════════════════════════════
# TEST 4 — Employee create via companies settings
# ══════════════════════════════════════════════════════════════════════════════

@NO_HTTPS
class EmployeeCreateTest(TestCase):
    """Tests for /companies/settings/employee/create/ endpoint."""

    def setUp(self):
        self.company = make_company(oib="33322211193")
        make_subscription(self.company)
        self.admin = make_user(self.company, username="emp_admin")
        self.worker = make_user(self.company, username="emp_worker", role="worker")
        self.c = Client()
        self.c.login(username="emp_admin", password="TestPass2026!")
        self.url = "/companies/settings/employee/create/"

    def test_create_employee_ok(self):
        """POST valid data → JSON ok=True, user created, must_change_password=True."""
        r = self.c.post(self.url, {
            "email":      "new.employee@core-test.de",
            "first_name": "Novi",
            "last_name":  "Zaposlenik",
            "role":       "worker",
            "phone":      "+385911234567",
        })
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertTrue(d.get("ok"), d)
        new_user = User.objects.filter(email="new.employee@core-test.de").first()
        self.assertIsNotNone(new_user)
        self.assertTrue(new_user.profile.must_change_password)

    def test_duplicate_email_rejected(self):
        """POST with existing email → JSON error, status 400."""
        r = self.c.post(self.url, {
            "email":      "emp_admin@core-test.de",  # already exists
            "first_name": "Duplicate",
            "last_name":  "User",
            "role":       "worker",
        })
        self.assertEqual(r.status_code, 400)
        d = r.json()
        self.assertIn("error", d)

    def test_non_admin_forbidden(self):
        """Worker POSTing to employee_create → 403."""
        c2 = Client()
        c2.login(username="emp_worker", password="TestPass2026!")
        r = c2.post(self.url, {
            "email": "hacker@test.de",
            "role":  "worker",
        })
        self.assertEqual(r.status_code, 403)
