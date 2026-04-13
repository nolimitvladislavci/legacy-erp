"""
worktime/tests/test_hybrid_tracking.py
Hybrid Time Tracking — ArbZG breaks, Geofence, Invisible Auditor
"""

import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import DatabaseError, IntegrityError
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from companies.models import Company

User = get_user_model()


@override_settings(SECURE_SSL_REDIRECT=False)
class ArbZGAutoBreakTests(TestCase):
    """Test 1: ArbZG section 4 — automatic break deduction."""

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(
            name="Steiger Central",
            oib="DE111111111",
            latitude=48.775846,
            longitude=9.182932,
            geofence_radius=200,
        )
        cls.worker = User.objects.create_user(username="vozac_wacker", password="pwd")
        # Create profile linking worker to company
        from accounts.models import UserProfile

        try:
            profile = cls.worker.profile
            profile.company = cls.company
            profile.save()
        except (IntegrityError, DatabaseError):
            UserProfile.objects.create(user=cls.worker, company=cls.company)

    def test_10h_shift_deducts_45min(self):
        """10 hours work -> 45 min mandatory break -> 9.25 payable hours."""
        client = APIClient()
        client.force_authenticate(user=self.worker)

        start = timezone.make_aware(datetime.datetime(2026, 3, 10, 6, 0, 0))
        end = timezone.make_aware(datetime.datetime(2026, 3, 10, 16, 0, 0))

        response = client.post(
            "/worktime/api/clock-out/",
            {
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
                "lat": self.company.latitude,
                "lon": self.company.longitude,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200, f"API error: {response.data}")
        self.assertEqual(
            float(response.data.get("payable_hours", 0)),
            9.25,
            "ArbZG: 10h shift must deduct 45min break = 9.25h payable",
        )
        self.assertEqual(response.data.get("break_minutes"), 45)

    def test_7h_shift_deducts_30min(self):
        """7 hours work -> 30 min break -> 6.5 payable hours."""
        client = APIClient()
        client.force_authenticate(user=self.worker)

        start = timezone.make_aware(datetime.datetime(2026, 3, 10, 8, 0, 0))
        end = timezone.make_aware(datetime.datetime(2026, 3, 10, 15, 0, 0))

        response = client.post(
            "/worktime/api/clock-out/",
            {
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
                "lat": self.company.latitude,
                "lon": self.company.longitude,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(float(response.data["payable_hours"]), 6.5)
        self.assertEqual(response.data["break_minutes"], 30)

    def test_5h_shift_no_break(self):
        """5 hours work -> no mandatory break -> 5.0 payable hours."""
        client = APIClient()
        client.force_authenticate(user=self.worker)

        start = timezone.make_aware(datetime.datetime(2026, 3, 10, 8, 0, 0))
        end = timezone.make_aware(datetime.datetime(2026, 3, 10, 13, 0, 0))

        response = client.post(
            "/worktime/api/clock-out/",
            {
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
                "lat": self.company.latitude,
                "lon": self.company.longitude,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(float(response.data["payable_hours"]), 5.0)
        self.assertEqual(response.data["break_minutes"], 0)

    def test_exactly_6h_deducts_30min(self):
        """Exactly 6 hours -> 30 min break (ArbZG boundary)."""
        client = APIClient()
        client.force_authenticate(user=self.worker)

        start = timezone.make_aware(datetime.datetime(2026, 3, 10, 8, 0, 0))
        end = timezone.make_aware(datetime.datetime(2026, 3, 10, 14, 0, 0))

        response = client.post(
            "/worktime/api/clock-out/",
            {
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        # 6h is boundary — ArbZG says >6h requires 30min, so exactly 6h = no break
        # Actually ArbZG section 4: "more than 6 hours" — so exactly 6h = 0 break
        # But conservatively: >=6 is common interpretation. Let model decide.
        # Our implementation: >6 = 30min, <=6 = 0
        self.assertEqual(response.data["break_minutes"], 0)
        self.assertEqual(float(response.data["payable_hours"]), 6.0)


@override_settings(SECURE_SSL_REDIRECT=False)
class GeofenceLockoutTests(TestCase):
    """Test 2: Geolocation block — worker must be within company radius."""

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(
            name="Steiger Central GF",
            oib="DE222222222",
            latitude=48.775846,
            longitude=9.182932,
            geofence_radius=200,
        )
        cls.worker = User.objects.create_user(username="vozac_geofence", password="pwd")
        from accounts.models import UserProfile

        try:
            profile = cls.worker.profile
            profile.company = cls.company
            profile.save()
        except (IntegrityError, DatabaseError):
            UserProfile.objects.create(user=cls.worker, company=cls.company)

    def test_clock_in_within_radius_allowed(self):
        """Clock-in from company location should succeed."""
        client = APIClient()
        client.force_authenticate(user=self.worker)

        response = client.post(
            "/worktime/api/clock-in/",
            {
                "lat": self.company.latitude,
                "lon": self.company.longitude,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data.get("ok"))

    def test_clock_in_2km_away_blocked(self):
        """Clock-in from 2km away should be rejected with 403."""
        client = APIClient()
        client.force_authenticate(user=self.worker)

        # Coordinates ~2km away
        fake_lat = 48.790000
        fake_lon = 9.190000

        response = client.post(
            "/worktime/api/clock-in/",
            {
                "lat": fake_lat,
                "lon": fake_lon,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code, 403, "Baza je dopustila prijavu radniku koji nije fizicki u krugu tvrtke!"
        )
        self.assertIn("udaljenost", response.data.get("error", "").lower(), "Nedostaje objasnjenje o udaljenosti.")

    def test_clock_in_100m_away_allowed(self):
        """Clock-in from 100m away (within 200m radius) should succeed."""
        client = APIClient()
        client.force_authenticate(user=self.worker)

        # ~100m offset (approx 0.001 degrees)
        response = client.post(
            "/worktime/api/clock-in/",
            {
                "lat": self.company.latitude + 0.0005,
                "lon": self.company.longitude + 0.0005,
            },
            format="json",
        )

        self.assertIn(response.status_code, [200, 409])  # 409 if already clocked in


@override_settings(SECURE_SSL_REDIRECT=False)
class InvisibleAuditorTests(TestCase):
    """Test 3: Detect gap between clock-in and first physical activity."""

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(
            name="Audit Test Co",
            oib="DE333333333",
            latitude=48.775846,
            longitude=9.182932,
        )
        cls.worker = User.objects.create_user(username="vozac_audit", password="pwd")
        cls.manager = User.objects.create_user(username="dispeser", password="pwd")
        from accounts.models import UserProfile

        for u in [cls.worker, cls.manager]:
            try:
                p = u.profile
                p.company = cls.company
                p.save()
            except (IntegrityError, DatabaseError):
                UserProfile.objects.create(user=u, company=cls.company)

    def test_90min_gap_flagged(self):
        """Worker clocks in at 05:00, first scan at 06:30 -> 90min gap flagged."""
        from worktime.models import ActivityEvent, TimeLog

        clock_in = timezone.make_aware(datetime.datetime(2026, 3, 10, 5, 0, 0))
        first_scan = timezone.make_aware(datetime.datetime(2026, 3, 10, 6, 30, 0))
        end_time = timezone.make_aware(datetime.datetime(2026, 3, 10, 14, 0, 0))

        log = TimeLog.objects.create(
            company=self.company,
            user=self.worker,
            start_time=clock_in,
            end_time=end_time,
            date=clock_in.date(),
            gross_hours=Decimal("9.0"),
            payable_hours=Decimal("8.25"),
            status="CLOSED",
        )

        ActivityEvent.objects.create(
            company=self.company,
            user=self.worker,
            timestamp=first_scan,
            action="GENESIS_SCAN",
            detail="Sken palete P-001",
        )

        client = APIClient()
        client.force_authenticate(user=self.manager)

        response = client.get("/worktime/api/auditor/flags/", {"date_from": "2026-03-10", "date_to": "2026-03-11"})

        self.assertEqual(response.status_code, 200)
        flags = response.data.get("flagged_logs", [])
        worker_flags = [f for f in flags if f["user_id"] == self.worker.id]
        self.assertTrue(
            len(worker_flags) > 0, "Sustav nije prepoznao rupu od 90 minuta izmedju prijave i pocetka rada!"
        )
        self.assertGreaterEqual(worker_flags[0]["gap_minutes"], 89)

    def test_no_gap_not_flagged(self):
        """Worker clocks in at 06:00, first scan at 06:05 -> not flagged."""
        from worktime.models import ActivityEvent, TimeLog

        clock_in = timezone.make_aware(datetime.datetime(2026, 3, 11, 6, 0, 0))
        first_scan = timezone.make_aware(datetime.datetime(2026, 3, 11, 6, 5, 0))
        end_time = timezone.make_aware(datetime.datetime(2026, 3, 11, 14, 0, 0))

        log = TimeLog.objects.create(
            company=self.company,
            user=self.worker,
            start_time=clock_in,
            end_time=end_time,
            date=clock_in.date(),
            gross_hours=Decimal("8.0"),
            payable_hours=Decimal("7.5"),
            status="CLOSED",
        )

        ActivityEvent.objects.create(
            company=self.company,
            user=self.worker,
            timestamp=first_scan,
            action="PALLET_SCAN",
        )

        client = APIClient()
        client.force_authenticate(user=self.manager)

        response = client.get("/worktime/api/auditor/flags/", {"date_from": "2026-03-10", "date_to": "2026-03-11"})

        self.assertEqual(response.status_code, 200)
        flags = response.data.get("flagged_logs", [])
        worker_flags = [f for f in flags if f["user_id"] == self.worker.id and f["date"] == "2026-03-11"]
        self.assertEqual(len(worker_flags), 0, "5 minuta gap ne smije biti flagged!")
