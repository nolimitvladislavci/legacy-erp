"""Tests for appointments.services — booking logic unit tests."""
from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from appointments.services import (
    VALID_STATUS_TRANSITIONS,
    cancel_appointment,
    change_appointment_status,
    create_booking,
    get_available_slots,
    get_week_slots,
)
from core.exceptions import BookingConflictError
from core.exceptions import ValidationError as BizValidationError


class AppointmentTestBase(TestCase):
    def setUp(self):
        from appointments.models import BookingResource, BookingService, WorkingHours
        from companies.models import Company

        self.company = Company.objects.create(name="Test Salon", oib="77777777777")
        self.user = User.objects.create_user("appttest", password="test123")

        self.resource = BookingResource.objects.create(
            name="Frizer Ana",
            resource_type="frizer",
            is_active=True,
        )

        self.service = BookingService.objects.create(
            name="Šišanje",
            duration=timedelta(minutes=30),
            price=Decimal("15.00"),
            resource_type="frizer",
            slot_duration_minutes=30,
            is_active=True,
        )

        # Working hours: Mon-Fri 9:00-17:00
        for day in range(5):
            WorkingHours.objects.create(
                resource=self.resource,
                day_of_week=day,
                start_time=time(9, 0),
                end_time=time(17, 0),
                is_day_off=False,
            )


class TestSlotAvailability(AppointmentTestBase):

    def _next_weekday(self):
        """Find next Monday-Friday date."""
        d = date.today() + timedelta(days=1)
        while d.weekday() >= 5:
            d += timedelta(days=1)
        return d

    def test_available_slots_workday(self):
        target = self._next_weekday()
        result = get_available_slots(self.service, target)
        self.assertGreater(len(result["available"]), 0)
        self.assertIn("09:00", result["available"])

    def test_no_slots_past_date(self):
        past = date(2020, 1, 1)
        result = get_available_slots(self.service, past)
        self.assertEqual(len(result["available"]), 0)

    def test_no_slots_on_weekend(self):
        d = date.today() + timedelta(days=1)
        while d.weekday() != 5:  # Saturday
            d += timedelta(days=1)
        result = get_available_slots(self.service, d)
        self.assertEqual(len(result["available"]), 0)

    def test_week_slots(self):
        target = self._next_weekday()
        result = get_week_slots(self.service, target, 7)
        self.assertEqual(len(result), 7)
        self.assertTrue(any(day["count"] > 0 for day in result))


class TestBooking(AppointmentTestBase):

    def _next_weekday(self):
        d = date.today() + timedelta(days=1)
        while d.weekday() >= 5:
            d += timedelta(days=1)
        return d

    def test_create_booking(self):
        target = self._next_weekday()
        result = create_booking(
            service=self.service,
            target_date=target,
            time_str="09:00",
            client_name="Ivan Horvat",
            client_email="ivan@test.hr",
            company=self.company,
        )
        self.assertIn("appointment_id", result)
        self.assertEqual(result["service"], "Šišanje")

    def test_double_booking_fails(self):
        target = self._next_weekday()
        create_booking(self.service, target, "10:00", "Ana", "ana@test.hr", company=self.company)
        with self.assertRaises(BookingConflictError):
            create_booking(self.service, target, "10:00", "Marko", "marko@test.hr", company=self.company)

    def test_booking_unavailable_slot(self):
        target = self._next_weekday()
        with self.assertRaises(BookingConflictError):
            create_booking(self.service, target, "23:00", "Late", "late@test.hr", company=self.company)


class TestStatusTransitions(AppointmentTestBase):

    def _create_appointment(self):
        from appointments.models import Appointment
        target = date.today() + timedelta(days=1)
        while target.weekday() >= 5:
            target += timedelta(days=1)
        return Appointment.objects.create(
            service=self.service,
            resource=self.resource,
            start_time=timezone.make_aware(timezone.datetime(target.year, target.month, target.day, 10, 0)),
            end_time=timezone.make_aware(timezone.datetime(target.year, target.month, target.day, 10, 30)),
            status="scheduled",
            company=self.company,
        )

    def test_confirm_appointment(self):
        appt = self._create_appointment()
        result = change_appointment_status(appt, "confirmed", notify=False)
        self.assertTrue(result)
        appt.refresh_from_db()
        self.assertEqual(appt.status, "confirmed")

    def test_invalid_transition(self):
        appt = self._create_appointment()
        with self.assertRaises(BizValidationError):
            change_appointment_status(appt, "completed", notify=False)

    def test_cancel_appointment(self):
        appt = self._create_appointment()
        result = cancel_appointment(appt, reason="Klijent otkazao", notify=False)
        self.assertTrue(result)
        appt.refresh_from_db()
        self.assertEqual(appt.status, "cancelled")

    def test_all_states_defined(self):
        for state in VALID_STATUS_TRANSITIONS:
            self.assertIsInstance(VALID_STATUS_TRANSITIONS[state], list)
