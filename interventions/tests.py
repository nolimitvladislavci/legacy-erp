"""
interventions/tests.py — Integration tests for Hitna Intervencija module.

5 test klase, 16 test metoda:
  1. HitnaIntervencijaModelTest   (6 methods) — model, properties, assign_worker
  2. InterventionStatusTest       (4 methods) — AJAX status update
  3. InterventionGPSTest          (3 methods) — GPS coordinate tracking
  4. InterventionTrackingTest     (3 methods) — public client tracking page
  5. PublicInterventionTest       (2 methods) — public form (no login)

Run:
    python manage.py test interventions --verbosity=2
"""

import json
import uuid

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.utils import timezone

User = get_user_model()

# Disable HTTPS redirect so test HTTP requests reach actual view logic
NO_HTTPS = override_settings(SECURE_SSL_REDIRECT=False)


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════


def make_company(oib="55544433321"):
    from companies.models import Company

    return Company.objects.get_or_create(
        oib=oib,
        defaults=dict(name="Krizna Ekipa d.o.o.", country="HR", city="Zagreb", zip_code="10000"),
    )[0]


def make_subscription(company):
    """Create an active CompanySubscription with interventions module enabled."""
    from registration.models import CompanySubscription

    return CompanySubscription.objects.create(
        company=company,
        plan="enterprise",
        valid_from=timezone.now().date(),
        monthly_fee=0,
        is_active=True,
        modules_override=["interventions"],
    )


def make_user_with_profile(company, username, role="worker", is_superuser=False):
    from accounts.models import UserProfile

    user = User.objects.create_user(
        username=username,
        email=f"{username}@test.hr",
        password="TestPass2026!",
        is_superuser=is_superuser,
        is_staff=is_superuser,
    )
    UserProfile.objects.create(user=user, company=company, role=role)
    return user


def make_interv(company, title="Poplava u podrumu", status="NOVO", assigned_to=None):
    from interventions.models import HitnaIntervencija

    return HitnaIntervencija.objects.create(
        company=company,
        title=title,
        category="voda",
        address="Ilica 1, Zagreb",
        client_name="Marko Marić",
        client_phone="0912345678",
        status=status,
        assigned_to=assigned_to,
    )


# ══════════════════════════════════════════════════════════════════════════════
# TEST 1 — Model, properties, assign_worker
# ══════════════════════════════════════════════════════════════════════════════


class HitnaIntervencijaModelTest(TestCase):
    """Model-level tests: choices, properties, assign_worker."""

    def setUp(self):
        self.company = make_company()
        self.worker = make_user_with_profile(self.company, "radnik_test")
        self.interv = make_interv(self.company)

    def test_status_choices(self):
        """All 7 status choices must exist."""
        from interventions.models import HitnaIntervencija

        expected = {"NOVO", "DODIJELJENO", "NA_PUTU", "NA_LOKACIJI", "RIJESENO", "ESKALIRANO", "FAKTURIRANO"}
        actual = set(HitnaIntervencija.Status.values)
        self.assertEqual(expected, actual)

    def test_category_choices(self):
        """All 5 category choices must exist."""
        from interventions.models import HitnaIntervencija

        expected = {"voda", "struja", "plin", "kljucar", "ostalo"}
        actual = set(HitnaIntervencija.Category.values)
        self.assertEqual(expected, actual)

    def test_tracking_url(self):
        """`tracking_url` must return the correct public path."""
        expected = f"/track/{self.interv.tracking_token}/"
        self.assertEqual(self.interv.tracking_url, expected)

    def test_status_color(self):
        """`status_color` returns a hex string for each status."""
        from interventions.models import HitnaIntervencija

        for status in HitnaIntervencija.Status.values:
            self.interv.status = status
            color = self.interv.status_color
            self.assertTrue(
                color.startswith("#") and len(color) in (4, 7),
                f"Bad color '{color}' for status {status}",
            )

    def test_assign_worker(self):
        """`assign_worker()` sets status, assigned_to, and TTL."""
        before = timezone.now()
        self.interv.assign_worker(self.worker, ttl_minutes=5)
        self.interv.refresh_from_db()

        self.assertEqual(self.interv.status, "DODIJELJENO")
        self.assertEqual(self.interv.assigned_to, self.worker)
        self.assertIsNotNone(self.interv.ttl_expires_at)
        # TTL should be ~5 minutes in the future
        diff = (self.interv.ttl_expires_at - before).total_seconds()
        self.assertGreater(diff, 290)  # at least 4m50s
        self.assertLess(diff, 310)  # at most 5m10s

    def test_elapsed_minutes(self):
        """`elapsed_minutes` returns a non-negative integer."""
        minutes = self.interv.elapsed_minutes
        self.assertIsInstance(minutes, int)
        self.assertGreaterEqual(minutes, 0)


# ══════════════════════════════════════════════════════════════════════════════
# TEST 2 — AJAX status update
# ══════════════════════════════════════════════════════════════════════════════


@NO_HTTPS
class InterventionStatusTest(TestCase):
    """Tests for the update_status AJAX endpoint."""

    def setUp(self):
        self.company = make_company(oib="55544433322")
        make_subscription(self.company)
        self.dispatcher = make_user_with_profile(self.company, "dispatcher1", role="company_admin")
        self.interv = make_interv(self.company)
        self.client = Client()
        self.client.login(username="dispatcher1", password="TestPass2026!")
        self.url = f"/interventions/{self.interv.pk}/status/"

    def _post(self, data):
        return self.client.post(
            self.url,
            data=json.dumps(data),
            content_type="application/json",
        )

    def test_update_status_na_putu(self):
        """NOVO → NA_PUTU sets started_at and returns ok=True."""
        r = self._post({"status": "NA_PUTU"})
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertTrue(d["ok"])
        self.interv.refresh_from_db()
        self.assertEqual(self.interv.status, "NA_PUTU")
        self.assertIsNotNone(self.interv.started_at)

    def test_update_status_rijeseno(self):
        """NA_LOKACIJI → RIJESENO sets resolved_at."""
        self.interv.status = "NA_LOKACIJI"
        self.interv.save(update_fields=["status"])
        r = self._post({"status": "RIJESENO"})
        self.assertEqual(r.status_code, 200)
        self.interv.refresh_from_db()
        self.assertEqual(self.interv.status, "RIJESENO")
        self.assertIsNotNone(self.interv.resolved_at)

    def test_update_status_invalid(self):
        """Unknown status → 400."""
        r = self._post({"status": "NEPOSTOJECI_STATUS"})
        self.assertEqual(r.status_code, 400)
        d = r.json()
        self.assertIn("error", d)

    def test_update_status_requires_login(self):
        """Unauthenticated POST → redirect (302) to login."""
        anon = Client()
        r = anon.post(
            self.url,
            data=json.dumps({"status": "NA_PUTU"}),
            content_type="application/json",
        )
        self.assertIn(r.status_code, (302, 401))


# ══════════════════════════════════════════════════════════════════════════════
# TEST 3 — GPS coordinate tracking
# ══════════════════════════════════════════════════════════════════════════════


@NO_HTTPS
class InterventionGPSTest(TestCase):
    """Tests for the gps_update AJAX endpoint."""

    def setUp(self):
        self.company = make_company(oib="55544433323")
        make_subscription(self.company)
        self.worker = make_user_with_profile(self.company, "worker_gps", role="worker")
        self.other = make_user_with_profile(self.company, "worker_other", role="worker")
        self.interv = make_interv(self.company, assigned_to=self.worker)
        self.url = f"/interventions/{self.interv.pk}/gps/"

    def _post_gps(self, user, lat=45.815, lng=15.982):
        c = Client()
        c.login(username=user.username, password="TestPass2026!")
        return c.post(
            self.url,
            data=json.dumps({"lat": lat, "lng": lng}),
            content_type="application/json",
        )

    def test_gps_update_saves_coords(self):
        """Assigned worker can POST GPS → last_lat/lng saved."""
        r = self._post_gps(self.worker, lat=45.815, lng=15.982)
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertTrue(d["ok"])
        self.interv.refresh_from_db()
        self.assertAlmostEqual(self.interv.last_lat, 45.815, places=3)
        self.assertAlmostEqual(self.interv.last_lng, 15.982, places=3)
        self.assertIsNotNone(self.interv.last_gps_update)

    def test_gps_update_wrong_user(self):
        """Different (non-assigned, non-superadmin) user → 403."""
        r = self._post_gps(self.other)
        self.assertEqual(r.status_code, 403)

    def test_gps_update_superadmin_ok(self):
        """Superadmin can update GPS on any intervention."""
        superadmin = make_user_with_profile(self.company, "superadmin_gps", role="superadmin", is_superuser=True)
        r = self._post_gps(superadmin, lat=46.0, lng=16.0)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])


# ══════════════════════════════════════════════════════════════════════════════
# TEST 4 — Public client tracking page
# ══════════════════════════════════════════════════════════════════════════════


@NO_HTTPS
class InterventionTrackingTest(TestCase):
    """Tests for the public tracking_view (no login required)."""

    def setUp(self):
        self.company = make_company(oib="55544433324")
        self.interv = make_interv(self.company, status="NA_PUTU")
        self.url = f"/track/{self.interv.tracking_token}/"

    def test_tracking_view_public(self):
        """Tracking page is accessible without login."""
        c = Client()
        r = c.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, self.interv.title)

    def test_tracking_view_not_found(self):
        """Non-existent tracking token → 404."""
        c = Client()
        r = c.get(f"/track/{uuid.uuid4()}/")
        self.assertEqual(r.status_code, 404)

    def test_tracking_step_data_na_putu(self):
        """NA_PUTU → step 3 (index 2) is active, steps 0-1 are done."""
        c = Client()
        r = c.get(self.url)
        self.assertEqual(r.status_code, 200)
        step_data = r.context["step_data"]
        # NOVO (0) and DODIJELJENO (1) should be done
        self.assertEqual(step_data[0]["cls"], "done")
        self.assertEqual(step_data[1]["cls"], "done")
        # NA_PUTU (2) should be active
        self.assertIn("active", step_data[2]["cls"])
        # NA_LOKACIJI (3) and RIJESENO (4) should not be active/done
        self.assertEqual(step_data[3]["cls"], "")
        self.assertEqual(step_data[4]["cls"], "")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 5 — Public intervention form (SOS)
# ══════════════════════════════════════════════════════════════════════════════


@NO_HTTPS
class PublicInterventionTest(TestCase):
    """Tests for the public_intervention form (no login required)."""

    def setUp(self):
        self.company = make_company(oib="55544433325")
        self.c = Client()

    def test_public_form_get(self):
        """GET /interventions/public/ returns 200 without login."""
        r = self.c.get("/interventions/public/")
        self.assertEqual(r.status_code, 200)

    def test_public_form_post_creates_intervention(self):
        """Valid POST creates intervention and redirects to tracking page."""
        from interventions.models import HitnaIntervencija

        before_count = HitnaIntervencija.objects.unscoped().count()
        r = self.c.post(
            "/interventions/public/",
            {
                "client_name": "Iva Ivić",
                "client_phone": "0981234567",
                "address": "Gajeva 10, Zagreb",
                "category": "struja",
                "title": "Nestalo struje",
                "description": "Cijeli stan bez struje.",
            },
        )
        # Should redirect to tracking page (302 → /track/<uuid>/)
        self.assertEqual(r.status_code, 302)
        self.assertIn("/track/", r["Location"])
        # One new intervention must exist
        after_count = HitnaIntervencija.objects.unscoped().count()
        self.assertEqual(after_count, before_count + 1)
        # Check the intervention was created with correct data
        new_interv = HitnaIntervencija.objects.unscoped().order_by("-created_at").first()
        self.assertEqual(new_interv.client_name, "Iva Ivić")
        self.assertEqual(new_interv.status, "NOVO")
        self.assertIsNotNone(new_interv.tracking_token)
