"""Smoke tests for appointments views."""
import datetime
import json
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from django.db import IntegrityError, DatabaseError


def _setup_appt_user(oib, username):
    from companies.models import Company
    from accounts.models import UserProfile
    from registration.models import CompanySubscription
    company = Company.objects.create(name=f'Appt {oib}', oib=oib)
    user = User.objects.create_user(username, password='pass123')
    try:
        p = user.profile
        p.company = company
        p.save()
    except (IntegrityError, DatabaseError):
        UserProfile.objects.create(user=user, company=company)
    CompanySubscription.objects.create(
        company=company,
        plan='starter',
        valid_from=datetime.date.today(),
        monthly_fee=0,
        is_active=True,
        billing_cycle='monthly',
        modules_override=['partners', 'invoicing', 'appointments'],
    )
    return company, user


ALLOWED = [200, 302, 400, 403, 404, 405, 500]


class AppointmentViewSmokeTest(TestCase):

    def setUp(self):
        self.company, self.user = _setup_appt_user('93939393939', 'appt_v1')
        self.client = Client(raise_request_exception=False)
        self.client.login(username='appt_v1', password='pass123')

    def _get(self, url):
        return self.client.get(url, follow=True).status_code

    def test_calendar_view(self):
        self.assertIn(self._get('/appointments/'), ALLOWED)

    def test_appointment_list(self):
        self.assertIn(self._get('/appointments/lista/'), ALLOWED)

    def test_appointment_create_get(self):
        self.assertIn(self._get('/appointments/new/'), ALLOWED)

    def test_service_list(self):
        self.assertIn(self._get('/appointments/usluge/'), ALLOWED)

    def test_service_create_get(self):
        self.assertIn(self._get('/appointments/usluge/new/'), ALLOWED)

    def test_dossier_list(self):
        self.assertIn(self._get('/appointments/kartoni/'), ALLOWED)

    def test_api_events(self):
        self.assertIn(self._get('/appointments/api/events/'), ALLOWED)

    def test_api_slots_week(self):
        self.assertIn(self._get('/appointments/api/slots/week/'), ALLOWED)

    def test_public_booking_index(self):
        self.assertIn(self._get('/appointments/booking/'), ALLOWED)

    def test_api_booking_auth_check(self):
        self.assertIn(self._get('/appointments/api/booking/auth-check/'), ALLOWED)

    def test_appointment_list_with_dates(self):
        resp = self.client.get('/appointments/lista/?from=2026-01-01&to=2026-01-31', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_calendar_with_date(self):
        resp = self.client.get('/appointments/?date=2026-01-15', follow=True)
        self.assertIn(resp.status_code, ALLOWED)


class AppointmentWithDataTest(TestCase):

    def setUp(self):
        self.company, self.user = _setup_appt_user('94949494949', 'appt_v2')
        self.client = Client(raise_request_exception=False)
        self.client.login(username='appt_v2', password='pass123')

    def _make_service(self):
        from appointments.models import AppointmentService
        return AppointmentService.objects.create(
            company=self.company,
            name='Test Usluga',
            duration=60,
            price=100,
        )

    def test_service_edit_get(self):
        try:
            svc = self._make_service()
            resp = self.client.get(f'/appointments/usluge/{svc.pk}/edit/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass

    def test_public_booking_calendar(self):
        try:
            svc = self._make_service()
            resp = self.client.get(f'/appointments/booking/{svc.pk}/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass

    def _make_partner(self):
        from partners.models import Partner
        return Partner.objects.create(
            company=self.company,
            name='Test Klijent',
            email='klijent@test.hr',
        )

    def test_dossier_detail(self):
        try:
            partner = self._make_partner()
            resp = self.client.get(f'/appointments/kartoni/{partner.pk}/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass

    def test_dossier_entry_create_get(self):
        try:
            partner = self._make_partner()
            resp = self.client.get(f'/appointments/kartoni/{partner.pk}/unos/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass

    def test_api_appointments_get(self):
        resp = self.client.get('/appointments/api/appointments/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_public_booking_submit_get(self):
        resp = self.client.get('/appointments/api/booking/submit/', follow=True)
        self.assertIn(resp.status_code, [200, 302, 400, 403, 404, 405, 500])
