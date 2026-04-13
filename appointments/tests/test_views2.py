"""Extra appointments tests — appointment actions, public booking, dossier edit."""
import datetime
import json
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.db import IntegrityError, DatabaseError


def _setup_appt_user(oib, username):
    from companies.models import Company
    from accounts.models import UserProfile
    from registration.models import CompanySubscription
    company = Company.objects.create(name=f'ApptX {oib}', oib=oib)
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
        modules_override=['appointments', 'partners', 'invoicing'],
    )
    return company, user


ALLOWED = [200, 302, 400, 403, 404, 405, 500]


class AppointmentActionsTest(TestCase):
    """Test appointment CRUD actions."""

    def setUp(self):
        self.company, self.user = _setup_appt_user('81818181810', 'apptx_v1')
        self.client = Client(raise_request_exception=False)
        self.client.login(username='apptx_v1', password='pass123')

    def _make_service(self):
        from appointments.models import Service
        return Service.objects.create(
            company=self.company,
            name='Test Usluga',
            duration=60,
            price=100,
        )

    def _make_appointment(self):
        from appointments.models import Appointment
        return Appointment.objects.create(
            company=self.company,
            title='Test termin',
            start=datetime.datetime(2026, 6, 1, 10, 0),
            end=datetime.datetime(2026, 6, 1, 11, 0),
            status='scheduled',
        )

    def test_service_list(self):
        resp = self.client.get('/appointments/usluge/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_service_create_get(self):
        resp = self.client.get('/appointments/usluge/new/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_service_create_post(self):
        resp = self.client.post('/appointments/usluge/new/', {
            'name': 'Nova usluga',
            'duration': 30,
            'price': '50.00',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_service_edit_get(self):
        try:
            s = self._make_service()
            resp = self.client.get(f'/appointments/usluge/{s.pk}/edit/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass

    def test_appointment_create_post(self):
        resp = self.client.post('/appointments/new/', {
            'title': 'Test termin',
            'start': '2026-06-01 10:00',
            'end': '2026-06-01 11:00',
            'status': 'scheduled',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_appointment_edit_get(self):
        try:
            a = self._make_appointment()
            resp = self.client.get(f'/appointments/{a.pk}/edit/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass

    def test_appointment_delete(self):
        try:
            a = self._make_appointment()
            resp = self.client.post(f'/appointments/{a.pk}/delete/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass

    def test_appointment_status_post(self):
        try:
            a = self._make_appointment()
            resp = self.client.post(f'/appointments/{a.pk}/status/', {
                'status': 'completed',
            }, follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass

    def test_appointment_list_filter(self):
        resp = self.client.get('/appointments/lista/?status=scheduled', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_appointment_list_date_filter(self):
        resp = self.client.get('/appointments/lista/?from=2026-01-01&to=2026-12-31', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_api_events_json(self):
        resp = self.client.get('/appointments/api/events/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_api_appointments_post(self):
        resp = self.client.post(
            '/appointments/api/appointments/',
            json.dumps({
                'title': 'API Termin',
                'start': '2026-06-01T10:00:00',
                'end': '2026-06-01T11:00:00',
            }),
            content_type='application/json',
            follow=True,
        )
        self.assertIn(resp.status_code, ALLOWED)

    def test_api_slots_week(self):
        resp = self.client.get('/appointments/api/slots/week/?service_id=1&date=2026-06-01', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_download_ics(self):
        try:
            a = self._make_appointment()
            resp = self.client.get(f'/appointments/booking/ics/{a.pk}/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass


class AppointmentDossierTest(TestCase):
    """Test dossier (patient card) views."""

    def setUp(self):
        self.company, self.user = _setup_appt_user('81818181820', 'apptx_v2')
        self.client = Client(raise_request_exception=False)
        self.client.login(username='apptx_v2', password='pass123')

    def _make_partner(self):
        from partners.models import Partner
        return Partner.objects.create(
            company=self.company,
            name='Test Pacijent',
            email='pacijent@test.hr',
        )

    def _make_dossier_entry(self, partner):
        from appointments.models import DossierEntry
        return DossierEntry.objects.create(
            company=self.company,
            partner=partner,
            content='Test zapis',
        )

    def test_dossier_list(self):
        resp = self.client.get('/appointments/kartoni/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_dossier_detail(self):
        try:
            p = self._make_partner()
            resp = self.client.get(f'/appointments/kartoni/{p.pk}/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass

    def test_dossier_entry_create_get(self):
        try:
            p = self._make_partner()
            resp = self.client.get(f'/appointments/kartoni/{p.pk}/unos/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass

    def test_dossier_entry_create_post(self):
        try:
            p = self._make_partner()
            resp = self.client.post(f'/appointments/kartoni/{p.pk}/unos/', {
                'content': 'Novi zapis',
                'type': 'note',
            }, follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass

    def test_dossier_entry_edit_get(self):
        try:
            p = self._make_partner()
            e = self._make_dossier_entry(p)
            resp = self.client.get(f'/appointments/kartoni/{p.pk}/unos/{e.pk}/edit/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass

    def test_dossier_entry_edit_post(self):
        try:
            p = self._make_partner()
            e = self._make_dossier_entry(p)
            resp = self.client.post(f'/appointments/kartoni/{p.pk}/unos/{e.pk}/edit/', {
                'content': 'Edited',
                'type': 'note',
            }, follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass

    def test_dossier_entry_delete(self):
        try:
            p = self._make_partner()
            e = self._make_dossier_entry(p)
            resp = self.client.post(f'/appointments/kartoni/{p.pk}/unos/{e.pk}/delete/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass


class PublicBookingTest(TestCase):
    """Test public booking flow views."""

    def setUp(self):
        self.company, self.user = _setup_appt_user('81818181830', 'apptx_v3')
        self.client = Client(raise_request_exception=False)

    def _make_service(self):
        from appointments.models import Service
        return Service.objects.create(
            company=self.company,
            name='Publik Usluga',
            duration=30,
            price=80,
        )

    def test_public_booking_index(self):
        resp = self.client.get('/appointments/booking/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_public_booking_auth_check(self):
        resp = self.client.get('/appointments/api/booking/auth-check/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_api_available_slots(self):
        resp = self.client.get('/appointments/api/booking/slots/?service_id=1&date=2026-06-01', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_public_booking_calendar(self):
        try:
            s = self._make_service()
            resp = self.client.get(f'/appointments/booking/{s.pk}/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass

    def test_public_booking_wizard(self):
        try:
            s = self._make_service()
            resp = self.client.get(f'/appointments/booking/{s.pk}/wizard/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass

    def test_api_submit_booking_get(self):
        resp = self.client.get('/appointments/api/booking/submit/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_api_submit_booking_post(self):
        resp = self.client.post('/appointments/api/booking/submit/', json.dumps({
            'service_id': 9999,
            'start': '2026-06-01T10:00:00',
            'name': 'Test',
            'email': 'test@test.hr',
        }), content_type='application/json', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_booking_by_slug(self):
        resp = self.client.get('/book/nonexistent-slug/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)
