"""
Propter -- test suite
Testira: BillingPeriod, Otpremnica, aggregate pipeline, EkoStats, signal
"""
from decimal import Decimal
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


def make_company():
    from companies.models import Company
    import uuid
    oib = str(uuid.uuid4().int)[:11]
    return Company.objects.create(
        name="Propter Test d.o.o.",
        oib=oib,
        country="HR",
        email="test@propter.hr",
    )


def make_period(company, year=None, month=None):
    from propter.models import BillingPeriod
    now = timezone.now()
    return BillingPeriod.objects.create(
        company=company,
        year=year or now.year,
        month=month or now.month,
        status=BillingPeriod.Status.OPEN,
    )


def make_otpremnica(company, period=None, total="100.00"):
    from propter.models import Otpremnica, OtpremnicaItem
    t = Decimal(total)
    net = t / Decimal("1.25")
    tax = t - net
    otp = Otpremnica.objects.create(
        company=company,
        billing_period=period,
        issue_date=timezone.now().date(),
        recipient_name="Test primatelj d.o.o.",
        recipient_oib="12345678901",
        subtotal=net.quantize(Decimal("0.01")),
        tax_amount=tax.quantize(Decimal("0.01")),
        total=t,
        source=Otpremnica.Source.MANUAL,
        status=Otpremnica.Status.ISSUED,
    )
    OtpremnicaItem.objects.create(
        otpremnica=otp,
        line_number=1,
        description="Testna usluga",
        quantity=Decimal("1"),
        unit="EA",
        unit_price=net.quantize(Decimal("0.01")),
        tax_rate=Decimal("25"),
        line_total=net.quantize(Decimal("0.01")),
    )
    return otp


@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=["*"])
class TestBillingPeriod(TestCase):

    def setUp(self):
        self.company = make_company()

    def test_create_period(self):
        from propter.models import BillingPeriod
        p = make_period(self.company)
        self.assertEqual(p.status, BillingPeriod.Status.OPEN)
        self.assertEqual(p.otpremnica_count, 0)

    def test_get_or_create_current(self):
        from propter.models import BillingPeriod
        now = timezone.now()
        p1 = BillingPeriod.get_or_create_current(self.company)
        p2 = BillingPeriod.get_or_create_current(self.company)
        self.assertEqual(p1.pk, p2.pk)
        self.assertEqual(p1.year, now.year)
        self.assertEqual(p1.month, now.month)

    def test_unique_together(self):
        from django.db import IntegrityError
        now = timezone.now()
        make_period(self.company, now.year, now.month)
        with self.assertRaises(IntegrityError):
            make_period(self.company, now.year, now.month)

    def test_str(self):
        p = make_period(self.company)
        self.assertIn(self.company.name, str(p))


@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=["*"])
class TestOtpremnica(TestCase):

    def setUp(self):
        self.company = make_company()
        self.period = make_period(self.company)

    def test_create_otpremnica(self):
        from propter.models import Otpremnica
        otp = make_otpremnica(self.company, self.period, "125.00")
        self.assertEqual(otp.total, Decimal("125.00"))
        self.assertEqual(otp.status, Otpremnica.Status.ISSUED)
        self.assertTrue(otp.number)  # auto-generated

    def test_auto_billing_period(self):
        """Otpremnica bez eksplicitnog perioda treba dobiti trenutni."""
        otp = make_otpremnica(self.company, period=None)
        self.assertIsNotNone(otp.billing_period)
        self.assertEqual(otp.billing_period.company, self.company)

    def test_number_format(self):
        otp = make_otpremnica(self.company, self.period)
        now = timezone.now()
        self.assertTrue(otp.number.startswith(str(now.year)))

    def test_items(self):
        otp = make_otpremnica(self.company, self.period, "100.00")
        self.assertEqual(otp.items.count(), 1)
        item = otp.items.first()
        self.assertEqual(item.tax_rate, Decimal("25"))


@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=["*"])
class TestAggregatePipeline(TestCase):

    def setUp(self):
        self.company = make_company()
        self.period = make_period(self.company)
        # 3 otpremnice po 100 EUR (ukupno 300 EUR)
        for _ in range(3):
            make_otpremnica(self.company, self.period, "100.00")

    def test_close_period(self):
        from propter.services.aggregate import close_period
        from propter.models import BillingPeriod
        close_period(self.period)
        self.period.refresh_from_db()
        self.assertEqual(self.period.status, BillingPeriod.Status.CLOSED)
        self.assertEqual(self.period.otpremnica_count, 3)
        self.assertGreater(self.period.total_with_tax, Decimal("0"))

    def test_close_period_calculates_totals(self):
        from propter.services.aggregate import close_period
        close_period(self.period)
        self.period.refresh_from_db()
        # 3 x 100 EUR bruto
        self.assertEqual(self.period.total_with_tax, Decimal("300.00"))

    def test_cannot_close_already_closed(self):
        from propter.services.aggregate import close_period
        close_period(self.period)
        with self.assertRaises(ValueError):
            close_period(self.period)

    def test_aggregate_creates_eracun(self):
        from propter.services.aggregate import close_period, aggregate_to_eracun
        # Treba ERacunConfig za company
        from eracun.models import ERacunConfig
        ERacunConfig.objects.create(
            company=self.company, is_active=True, use_test_env=True
        )
        close_period(self.period)
        eracun = aggregate_to_eracun(self.period)
        self.assertIsNotNone(eracun)
        self.assertEqual(eracun.total, Decimal("300.00"))
        self.assertIn("ZBIRNI", eracun.invoice_number)

    def test_aggregate_marks_otpremnice(self):
        from propter.services.aggregate import close_period, aggregate_to_eracun
        from propter.models import Otpremnica
        from eracun.models import ERacunConfig
        ERacunConfig.objects.create(
            company=self.company, is_active=True, use_test_env=True
        )
        close_period(self.period)
        aggregate_to_eracun(self.period)
        # Sve otpremnice trebaju biti AGGREGATED
        still_issued = self.period.otpremnice.filter(
            status=Otpremnica.Status.ISSUED
        ).count()
        self.assertEqual(still_issued, 0)
        aggregated = self.period.otpremnice.filter(
            status=Otpremnica.Status.AGGREGATED
        ).count()
        self.assertEqual(aggregated, 3)

    def test_aggregate_idempotent(self):
        """Drugi poziv aggregate_to_eracun treba vratiti isti e-Racun."""
        from propter.services.aggregate import close_period, aggregate_to_eracun
        from eracun.models import ERacunConfig
        ERacunConfig.objects.create(
            company=self.company, is_active=True, use_test_env=True
        )
        close_period(self.period)
        e1 = aggregate_to_eracun(self.period)
        e2 = aggregate_to_eracun(self.period)
        self.assertEqual(e1.pk, e2.pk)


@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=["*"])
class TestEkoStats(TestCase):

    def setUp(self):
        self.company = make_company()
        self.period = make_period(self.company)
        # 60 otpremnica -- treba Bronze badge (50+)
        for _ in range(60):
            make_otpremnica(self.company, self.period, "10.00")

    def test_calculate_eko_stats(self):
        from propter.services.aggregate import close_period
        from propter.models import EkoStats
        close_period(self.period)
        eko = EkoStats.calculate(self.period)
        self.assertEqual(eko.otpremnice_count, 60)
        self.assertEqual(eko.paper_saved_sheets, 120)  # 60 x 2
        self.assertEqual(eko.co2_saved_grams, Decimal("600"))  # 120 x 5g
        self.assertEqual(eko.badge_level, EkoStats.Badge.BRONZE)

    def test_gold_badge(self):
        from propter.models import BillingPeriod, EkoStats
        period2 = make_period(self.company, 2024, 6)
        period2.otpremnica_count = 600
        period2.status = BillingPeriod.Status.CLOSED
        period2.save()
        eko = EkoStats.calculate(period2)
        self.assertEqual(eko.badge_level, EkoStats.Badge.GOLD)

    def test_no_badge_below_50(self):
        from propter.models import BillingPeriod, EkoStats
        period3 = make_period(self.company, 2024, 7)
        period3.otpremnica_count = 10
        period3.status = BillingPeriod.Status.CLOSED
        period3.save()
        eko = EkoStats.calculate(period3)
        self.assertEqual(eko.badge_level, "")


@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=["*"])
class TestPropterConfig(TestCase):

    def setUp(self):
        self.company = make_company()

    def test_create_config(self):
        from propter.models import PropterConfig
        cfg = PropterConfig.objects.create(
            company=self.company,
            tier=PropterConfig.Tier.BOOKKEEPER,
            monthly_fee=Decimal("200.00"),
            max_clients=60,
        )
        self.assertEqual(cfg.tier, PropterConfig.Tier.BOOKKEEPER)
        self.assertTrue(cfg.is_active)
        self.assertFalse(cfg.cert_is_valid)  # cert_status = NONE

    def test_is_trial(self):
        from propter.models import PropterConfig
        from datetime import timedelta
        cfg = PropterConfig.objects.create(
            company=self.company,
            tier=PropterConfig.Tier.CLIENT,
            monthly_fee=Decimal("50.00"),
            trial_until=timezone.now().date() + timedelta(days=14),
        )
        self.assertTrue(cfg.is_trial)


@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=["*"])
class TestCreateFromInvoice(TestCase):

    def setUp(self):
        self.company = make_company()

    def _make_invoice(self):
        from invoicing.models import Invoice
        import uuid
        inv = Invoice.objects.create(
            company=self.company,
            number="FC-{}-001".format(uuid.uuid4().hex[:6]),
            client_name="Test klijent d.o.o.",
            client_oib="98765432109",
            date_issued=timezone.now(),
            subtotal=Decimal("80.00"),
            tax_amount=Decimal("20.00"),
            total=Decimal("100.00"),
            status="SENT",
        )
        return inv

    def test_create_from_invoice(self):
        from propter.services.aggregate import create_from_invoice
        inv = self._make_invoice()
        otp = create_from_invoice(inv)
        self.assertEqual(otp.total, Decimal("100.00"))
        self.assertEqual(otp.invoice_id, str(inv.pk))

    def test_idempotent(self):
        from propter.services.aggregate import create_from_invoice
        inv = self._make_invoice()
        o1 = create_from_invoice(inv)
        o2 = create_from_invoice(inv)
        self.assertEqual(o1.pk, o2.pk)
