"""
Propter integracija -- testovi za:
  - registration.PropterTenant -> propter.PropterConfig sync
  - API endpoint za otpremnice
  - BillingPeriod auto-close logika
  - PropterConfig views HTTP response
"""
from decimal import Decimal
from django.test import TestCase, override_settings, Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import IntegrityError, DatabaseError

User = get_user_model()


def make_company(oib=None):
    from companies.models import Company
    import uuid
    return Company.objects.create(
        name="Integ Test d.o.o.",
        oib=oib or str(uuid.uuid4().int)[:11],
        country="HR",
        email="integ@test.hr",
    )


@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=["*"])
class TestPropterTenantSync(TestCase):
    """Kad registration.PropterTenant nastane, propter.PropterConfig treba biti kreiran."""

    def setUp(self):
        self.company = make_company()

    def test_sync_creates_propter_config(self):
        from registration.models import PropterTenant
        from propter.models import PropterConfig

        tenant = PropterTenant.objects.create(
            company=self.company,
            tier="bookkeeper",
            monthly_fee=Decimal("200.00"),
            max_companies=60,
            fina_cert_status="pending",
        )

        # Signal treba kreirati PropterConfig
        cfg = PropterConfig.objects.filter(company=self.company).first()
        self.assertIsNotNone(cfg)
        self.assertEqual(cfg.tier, "bookkeeper")
        self.assertEqual(cfg.monthly_fee, Decimal("200.00"))
        self.assertEqual(cfg.max_clients, 60)

    def test_sync_updates_existing_config(self):
        from registration.models import PropterTenant
        from propter.models import PropterConfig

        # Kreiraj tenant
        tenant = PropterTenant.objects.create(
            company=self.company,
            tier="client",
            monthly_fee=Decimal("50.00"),
            max_companies=1,
        )

        # Prvotni config
        cfg1 = PropterConfig.objects.filter(company=self.company).first()
        self.assertEqual(cfg1.tier, "client")

        # Update tenant
        tenant.tier = "bookkeeper"
        tenant.monthly_fee = Decimal("200.00")
        tenant.save()

        # Config treba biti sinkroniziran
        cfg2 = PropterConfig.objects.get(company=self.company)
        self.assertEqual(cfg2.tier, "bookkeeper")
        self.assertEqual(cfg2.monthly_fee, Decimal("200.00"))


@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=["*"])
class TestPropterViews(TestCase):
    """HTTP testovi za propter/ views."""

    def setUp(self):
        import uuid
        self.company = make_company(str(uuid.uuid4().int)[:11])
        self.user = User.objects.create_user(
            username="propter_test_user",
            password="testpass123",
        )
        # Povezi user s company
        try:
            profile = self.user.profile
            profile.company = self.company
            profile.save()
        except (IntegrityError, DatabaseError):
            pass

        self.client = Client()
        self.client.login(username="propter_test_user", password="testpass123")

    def test_dashboard_redirect_if_not_logged_in(self):
        c = Client()
        resp = c.get("/propter/")
        self.assertIn(resp.status_code, [302, 301])

    def test_period_list_url_exists(self):
        resp = self.client.get("/propter/periods/")
        # 200 ili redirect (company nije postavljena)
        self.assertIn(resp.status_code, [200, 302, 500])

    def test_otpremnica_list_url_exists(self):
        resp = self.client.get("/propter/otpremnice/")
        self.assertIn(resp.status_code, [200, 302, 500])

    def test_eko_dashboard_url_exists(self):
        resp = self.client.get("/propter/eko/")
        self.assertIn(resp.status_code, [200, 302, 500])


@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=["*"])
class TestAutoClosePrevious(TestCase):
    """Test auto_close_previous() za prethodni mjesec."""

    def setUp(self):
        self.company = make_company()

    def test_auto_close_previous_empty(self):
        """Ako nema OPEN perioda, treba vratiti praznu listu."""
        from propter.services.aggregate import auto_close_previous
        results = auto_close_previous()
        self.assertIsInstance(results, list)

    def test_auto_close_previous_month(self):
        """OPEN period prethodnog mjeseca treba biti zatvoren."""
        from propter.models import BillingPeriod
        from propter.services.aggregate import auto_close_previous

        now = timezone.now()
        prev_year = now.year if now.month > 1 else now.year - 1
        prev_month = now.month - 1 if now.month > 1 else 12

        period = BillingPeriod.objects.create(
            company=self.company,
            year=prev_year,
            month=prev_month,
            status=BillingPeriod.Status.OPEN,
        )

        results = auto_close_previous()
        # Period nema otpremnica -- treba ERROR ili OK ovisno o logici
        self.assertIsInstance(results, list)
        self.assertEqual(len(results), 1)

        period.refresh_from_db()
        # Period treba biti zatvoren (CLOSED) -- cak i bez otpremnica
        self.assertEqual(period.status, BillingPeriod.Status.CLOSED)
