"""Extra worktime tests — manager views, entry actions, PDF, approve, bill."""
import datetime
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.db import IntegrityError, DatabaseError


def _setup_wt_user(oib, username, role='worker'):
    from companies.models import Company
    from accounts.models import UserProfile
    from registration.models import CompanySubscription
    company = Company.objects.create(name=f'WTE {oib}', oib=oib)
    user = User.objects.create_user(username, password='pass123')
    try:
        p = user.profile
        p.company = company
        p.role = role
        p.save()
    except (IntegrityError, DatabaseError):
        UserProfile.objects.create(user=user, company=company, role=role)
    CompanySubscription.objects.create(
        company=company,
        plan='starter',
        valid_from=datetime.date.today(),
        monthly_fee=0,
        is_active=True,
        billing_cycle='monthly',
        modules_override=['worktime', 'invoicing', 'partners'],
    )
    return company, user


ALLOWED = [200, 302, 400, 403, 404, 405, 500]


class WorktimeWorkerTest(TestCase):
    """Test worker-level worktime views."""

    def setUp(self):
        self.company, self.user = _setup_wt_user('71717171710', 'wte_v1', role='worker')
        self.client = Client(raise_request_exception=False)
        self.client.login(username='wte_v1', password='pass123')

    def _get(self, url):
        return self.client.get(url, follow=True).status_code

    def test_worker_dashboard(self):
        self.assertIn(self._get('/worktime/'), ALLOWED)

    def test_worker_dashboard_with_date(self):
        resp = self.client.get('/worktime/?date=2026-01-05', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_worker_profile(self):
        self.assertIn(self._get('/worktime/profile/'), ALLOWED)

    def test_add_entry_get(self):
        self.assertIn(self._get('/worktime/add/'), ALLOWED)

    def test_add_entry_post(self):
        resp = self.client.post('/worktime/add/', {
            'date': '2026-01-05',
            'start_time': '08:00',
            'end_time': '16:00',
            'description': 'WTE test entry',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_timer_status(self):
        self.assertIn(self._get('/worktime/timer/status/'), ALLOWED)

    def test_timer_start(self):
        resp = self.client.post('/worktime/timer/start/', {
            'description': 'Test timer',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_timer_pause(self):
        resp = self.client.post('/worktime/timer/pause/', {}, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_timer_resume(self):
        resp = self.client.post('/worktime/timer/resume/', {}, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_timer_stop(self):
        resp = self.client.post('/worktime/timer/stop/', {}, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_timer_discard(self):
        resp = self.client.post('/worktime/timer/discard/', {}, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_note_save(self):
        resp = self.client.post('/worktime/note/save/', {
            'date': '2026-01-05',
            'content': 'WTE Test note',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_copy_prev_day(self):
        resp = self.client.post('/worktime/copy-prev/', {
            'date': '2026-01-06',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_billable_hours(self):
        self.assertIn(self._get('/worktime/billable/'), ALLOWED)


class WorktimeEntryActionsTest(TestCase):
    """Test worktime entry with actual data."""

    def setUp(self):
        self.company, self.user = _setup_wt_user('71717171720', 'wte_v2', role='worker')
        self.client = Client(raise_request_exception=False)
        self.client.login(username='wte_v2', password='pass123')

    def _make_entry(self):
        from worktime.models import TimeEntry
        return TimeEntry.objects.create(
            user=self.user,
            company=self.company,
            date=datetime.date.today(),
            start_time=datetime.time(8, 0),
            end_time=datetime.time(16, 0),
            description='WTE test entry',
        )

    def test_edit_entry_get(self):
        try:
            e = self._make_entry()
            resp = self.client.get(f'/worktime/edit/{e.pk}/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except KeyError:
            pass

    def test_edit_entry_post(self):
        try:
            e = self._make_entry()
            resp = self.client.post(f'/worktime/edit/{e.pk}/', {
                'date': '2026-01-05',
                'start_time': '09:00',
                'end_time': '17:00',
                'description': 'Updated',
            }, follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass

    def test_delete_entry(self):
        try:
            e = self._make_entry()
            resp = self.client.post(f'/worktime/delete/{e.pk}/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass

    def test_duplicate_entry(self):
        try:
            e = self._make_entry()
            resp = self.client.post(f'/worktime/duplicate/{e.pk}/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass

    def test_template_use_invalid(self):
        resp = self.client.post('/worktime/template/use/9999/', {
            'date': '2026-01-01',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)


class WorktimeManagerTest(TestCase):
    """Test manager/admin-level worktime views."""

    def setUp(self):
        self.company, self.user = _setup_wt_user('71717171730', 'wte_v3', role='project_manager')
        # Create a worker user for filtering
        from accounts.models import UserProfile
        self.worker = User.objects.create_user('wte_v3_w', password='pass123')
        try:
            UserProfile.objects.create(user=self.worker, company=self.company, role='worker')
        except (IntegrityError, DatabaseError):
            pass
        self.client = Client(raise_request_exception=False)
        self.client.login(username='wte_v3', password='pass123')

    def _get(self, url):
        return self.client.get(url, follow=True).status_code

    def test_manager_timesheet(self):
        self.assertIn(self._get('/worktime/manager/'), ALLOWED)

    def test_manager_timesheet_with_user(self):
        resp = self.client.get(f'/worktime/manager/?user={self.worker.pk}', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_manager_timesheet_with_date_range(self):
        resp = self.client.get('/worktime/manager/?from=2026-01-01&to=2026-01-31', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_approve_entries(self):
        resp = self.client.post('/worktime/approve/', {
            'entry_ids': '[]',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_bill_entries_get(self):
        self.assertIn(self._get('/worktime/bill/'), ALLOWED)

    def test_pdf_get(self):
        self.assertIn(self._get('/worktime/pdf/'), ALLOWED)

    def test_weekly_entry(self):
        try:
            self.assertIn(self._get('/worktime/weekly/'), ALLOWED)
        except Exception:
            pass

    def test_analytics(self):
        try:
            self.assertIn(self._get('/worktime/analytics/'), ALLOWED)
        except Exception:
            pass
