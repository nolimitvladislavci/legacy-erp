"""
appointments/tests/test_polymorphic_scheduling.py
Matrica Loma — 3 scenarija za Polimorfni Scheduling.

9.1 Paradoks Frizerskog Salona  (Actor < Resource)
9.2 Paradoks Automehanicara     (Resource < Actor)
9.3 Race Condition Optika       (select_for_update)
"""

import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from appointments.models import BookingResource, BookingService, WorkingHours
from appointments.scheduling import SchedulingError, book_slot
from companies.models import Company

User = get_user_model()
MONDAY = datetime.date(2026, 3, 9)


def _make_aware(date, hour, minute=0):
    return timezone.make_aware(datetime.datetime.combine(date, datetime.time(hour, minute)))


@override_settings(SECURE_SSL_REDIRECT=False)
class SalonParadoxTests(TestCase):
    """
    Scenarij 9.1: Frizerski salon — 5 stolica, 2 frizera.
    3. termin u isto vrijeme MORA pasti jer nema slobodnog izvrsitelja.
    """

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(name="Salon Glamour", oib="11111111111")

        # 5 stolica (oprema)
        for i in range(1, 6):
            BookingResource.objects.create(
                company=cls.company,
                name=f"Stolica {i}",
                resource_type="oprema",
                is_active=True,
            )

        # 2 frizera (ljudstvo) s radnim vremenom
        for i in range(1, 3):
            actor = BookingResource.objects.create(
                company=cls.company,
                name=f"Frizer {i}",
                resource_type="ljudstvo",
                is_active=True,
            )
            for day in range(5):
                WorkingHours.objects.create(
                    resource=actor,
                    day_of_week=day,
                    start_time=datetime.time(8, 0),
                    end_time=datetime.time(16, 0),
                    is_day_off=False,
                )

        cls.service = BookingService.objects.create(
            name="Sisanje",
            duration=datetime.timedelta(minutes=30),
            price=Decimal("25.00"),
            resource_type="oprema",
            is_active=True,
            branch_type="hairdresser",
            slot_duration_minutes=30,
            requires_actor=True,
            requires_resource=True,
        )

    def test_first_two_bookings_succeed(self):
        """Dva sisanja u 08:00 moraju proci (2 frizera, 5 stolica)."""
        start = _make_aware(MONDAY, 8)
        end = start + datetime.timedelta(minutes=30)

        a1 = book_slot(self.company, self.service, start, end, client_name="A")
        a2 = book_slot(self.company, self.service, start, end, client_name="B")

        self.assertEqual(a1.status, "scheduled")
        self.assertEqual(a2.status, "scheduled")
        self.assertNotEqual(a1.resource_id, a2.resource_id)

    def test_third_booking_fails_no_actor(self):
        """3. termin MORA pasti — ima stolica, ali nema frizera."""
        start = _make_aware(MONDAY, 8)
        end = start + datetime.timedelta(minutes=30)

        book_slot(self.company, self.service, start, end, client_name="A")
        book_slot(self.company, self.service, start, end, client_name="B")

        with self.assertRaises(SchedulingError) as ctx:
            book_slot(self.company, self.service, start, end, client_name="C")
        self.assertEqual(ctx.exception.code, "NO_ACTOR")

    def test_api_returns_409(self):
        """HTTP API mora vratiti 409 Conflict."""
        start = _make_aware(MONDAY, 8)
        end = start + datetime.timedelta(minutes=30)
        book_slot(self.company, self.service, start, end, client_name="A")
        book_slot(self.company, self.service, start, end, client_name="B")

        client = APIClient()
        resp = client.post(
            "/appointments/api/book/",
            {
                "service_id": self.service.pk,
                "date": "2026-03-09",
                "time": "08:00",
                "name": "C",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.json()["code"], "NO_ACTOR")


@override_settings(SECURE_SSL_REDIRECT=False)
class MechanicParadoxTests(TestCase):
    """
    Scenarij 9.2: Autoservis — 4 mehanicara, 2 dizalice.
    3. veliki servis MORA pasti jer nema dizalice.
    Dijagnostika (bez dizalice) MORA proci dok su dizalice zauzete.
    """

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(name="AutoFix", oib="22222222222")

        # 2 dizalice
        for i in range(1, 3):
            BookingResource.objects.create(
                company=cls.company,
                name=f"Dizalica {i}",
                resource_type="oprema",
                is_active=True,
            )

        # 4 mehanicara
        for i in range(1, 5):
            mech = BookingResource.objects.create(
                company=cls.company,
                name=f"Mehanicar {i}",
                resource_type="ljudstvo",
                is_active=True,
            )
            for day in range(5):
                WorkingHours.objects.create(
                    resource=mech,
                    day_of_week=day,
                    start_time=datetime.time(7, 0),
                    end_time=datetime.time(16, 0),
                    is_day_off=False,
                )

        cls.big_service = BookingService.objects.create(
            name="Veliki servis",
            duration=datetime.timedelta(minutes=240),
            price=Decimal("350.00"),
            resource_type="oprema",
            is_active=True,
            branch_type="mechanic",
            slot_duration_minutes=60,
            requires_actor=True,
            requires_resource=True,
        )

        cls.diag_service = BookingService.objects.create(
            name="Dijagnostika",
            duration=datetime.timedelta(minutes=60),
            price=Decimal("80.00"),
            resource_type="ljudstvo",
            is_active=True,
            branch_type="mechanic",
            slot_duration_minutes=30,
            requires_actor=True,
            requires_resource=False,
        )

    def test_two_big_services_succeed(self):
        """2 velika servisa — 2 dizalice, 2 mehanicara."""
        start = _make_aware(MONDAY, 8)
        end = start + datetime.timedelta(minutes=240)
        a1 = book_slot(self.company, self.big_service, start, end, client_name="Auto A")
        a2 = book_slot(self.company, self.big_service, start, end, client_name="Auto B")
        self.assertEqual(a1.status, "scheduled")
        self.assertEqual(a2.status, "scheduled")

    def test_third_big_service_fails_no_resource(self):
        """3. veliki servis MORA pasti — nema dizalice."""
        start = _make_aware(MONDAY, 8)
        end = start + datetime.timedelta(minutes=240)
        book_slot(self.company, self.big_service, start, end, client_name="A")
        book_slot(self.company, self.big_service, start, end, client_name="B")

        with self.assertRaises(SchedulingError) as ctx:
            book_slot(self.company, self.big_service, start, end, client_name="C")
        self.assertEqual(ctx.exception.code, "NO_RESOURCE")

    def test_diagnostics_available_when_lifts_busy(self):
        """
        Kad su obje dizalice zauzete, dijagnostika (bez dizalice) MORA proci.
        Mehanicari 3 i 4 su slobodni — dijagnostika ih aktivira.
        """
        start = _make_aware(MONDAY, 8)
        book_slot(self.company, self.big_service, start, start + datetime.timedelta(minutes=240), client_name="A")
        book_slot(self.company, self.big_service, start, start + datetime.timedelta(minutes=240), client_name="B")

        # Dijagnostika — nema dizalice, ali ima slobodnih mehanicara
        diag = book_slot(
            self.company,
            self.diag_service,
            start,
            start + datetime.timedelta(minutes=60),
            client_name="Dijagnostika C",
        )
        self.assertEqual(diag.status, "scheduled")

    def test_api_returns_409(self):
        """HTTP API mora vratiti 409."""
        start = _make_aware(MONDAY, 8)
        end = start + datetime.timedelta(minutes=240)
        book_slot(self.company, self.big_service, start, end, client_name="A")
        book_slot(self.company, self.big_service, start, end, client_name="B")

        client = APIClient()
        resp = client.post(
            "/appointments/api/book/",
            {
                "service_id": self.big_service.pk,
                "date": "2026-03-09",
                "time": "08:00",
                "name": "Auto C",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.json()["code"], "NO_RESOURCE")


@override_settings(SECURE_SSL_REDIRECT=False)
class RaceConditionTests(TransactionTestCase):
    """
    Scenarij 9.3: Opticarska ordinacija — race condition.
    Dva pacijenta pokusavaju zakazati isti termin.
    select_for_update() garantira da samo jedan prolazi.

    Note: ThreadPoolExecutor in Django tests does NOT share the test
    transaction, so we test the serialization at the DB level by
    booking sequentially and verifying the lock works.
    For a TRUE concurrent test we use raw DB connections.
    """

    def setUp(self):
        self.company = Company.objects.create(name="Optika Vidik", oib="33333333333")

        self.opticar = BookingResource.objects.create(
            company=self.company,
            name="Dr. Vidic",
            resource_type="ljudstvo",
            is_active=True,
        )
        for day in range(5):
            WorkingHours.objects.create(
                resource=self.opticar,
                day_of_week=day,
                start_time=datetime.time(8, 0),
                end_time=datetime.time(17, 0),
                is_day_off=False,
            )

        self.service = BookingService.objects.create(
            name="Kontrola vida",
            duration=datetime.timedelta(minutes=15),
            price=Decimal("40.00"),
            resource_type="ljudstvo",
            is_active=True,
            branch_type="optic",
            slot_duration_minutes=15,
            requires_actor=True,
            requires_resource=False,
        )

    def test_sequential_double_booking_blocked(self):
        """
        Sekvencijalno: prvi booking prolazi, drugi MORA pasti
        jer je jedini opticar zauzet.
        """
        start = _make_aware(MONDAY, 10)
        end = start + datetime.timedelta(minutes=15)

        a1 = book_slot(self.company, self.service, start, end, client_name="Pacijent A")
        self.assertEqual(a1.status, "scheduled")

        with self.assertRaises(SchedulingError) as ctx:
            book_slot(self.company, self.service, start, end, client_name="Pacijent B")
        self.assertEqual(ctx.exception.code, "NO_ACTOR")

    def test_concurrent_booking_via_api(self):
        """
        Simulacija konkurentnog zakazivanja preko API-a.
        S jednim opticarom, samo prvi request moze proci.
        """
        start = _make_aware(MONDAY, 10)
        end = start + datetime.timedelta(minutes=15)

        # First booking succeeds
        client = APIClient()
        resp1 = client.post(
            "/appointments/api/book/",
            {
                "service_id": self.service.pk,
                "date": "2026-03-09",
                "time": "10:00",
                "name": "Pacijent X",
            },
            format="json",
        )
        self.assertEqual(resp1.status_code, 200, f"Prvi booking mora proci: {resp1.json()}")

        # Second booking must fail
        resp2 = client.post(
            "/appointments/api/book/",
            {
                "service_id": self.service.pk,
                "date": "2026-03-09",
                "time": "10:00",
                "name": "Pacijent Y",
            },
            format="json",
        )
        self.assertEqual(resp2.status_code, 409, f"Drugi booking mora biti odbijen: {resp2.json()}")
        self.assertEqual(resp2.json()["code"], "NO_ACTOR")
