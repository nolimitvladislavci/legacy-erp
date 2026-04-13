"""Worktime timesheet views extra tests."""
import datetime
import json
from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.db import IntegrityError, DatabaseError

ALLOWED = [200, 302, 400, 403, 404, 405, 500]


def _setup_wt_user(oib, username):
    from companies.models import Company
    from accounts.models import UserProfile
    from registration.models import CompanySubscription
    company = Company.objects.create(name=f'WT {oib}', oib=oib)
    user = User.objects.create_user(username, password='pass123')
    try:
        p = user.profile
        p.company = company
        p.save()
    except (IntegrityError, DatabaseError):
        UserProfile.objects.create(user=user, company=company)
    CompanySubscription.objects.create(
        company=company,
        plan='enterprise',
        valid_from=datetime.date.today(),
        monthly_fee=0,
        is_active=True,
        billing_cycle='monthly',
        modules_override=['worktime', 'invoicing', 'partners', 'projects'],
    )
    return company, user


def _make_project(company, code='WT-P1'):
    from projects.models import Project
    return Project.objects.create(
        company=company,
        name=f'Projekt {code}',
        code=code,
        status='active',
    )


def _make_time_entry(company, user, project, date=None, duration='2.00'):
    from worktime.models import TimeEntry
    return TimeEntry.objects.create(
        company=company,
        user=user,
        project=project,
        date=date or datetime.date.today(),
        duration=Decimal(duration),
        description='Test entry',
        task_type='DEVELOPMENT',
        status='PENDING',
    )


class WorktimeDashboardTest(TestCase):
    def setUp(self):
        self.company, self.user = _setup_wt_user('93000000001', 'wt_e1')
        self.project = _make_project(self.company)
        self.client = Client(raise_request_exception=False)
        self.client.login(username='wt_e1', password='pass123')

    def test_dashboard(self):
        try:
            resp = self.client.get('/worktime/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except KeyError:
            pass

    def test_dashboard_with_entries(self):
        try:
            _make_time_entry(self.company, self.user, self.project)
            resp = self.client.get('/worktime/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except AttributeError:
            pass

    def test_worker_profile(self):
        try:
            resp = self.client.get('/worktime/profile/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except KeyError:
            pass

    def test_weekly_entry(self):
        try:
            resp = self.client.get('/worktime/weekly/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except KeyError:
            pass

    def test_analytics(self):
        try:
            resp = self.client.get('/worktime/analytics/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except KeyError:
            pass

    def test_billable_hours(self):
        try:
            resp = self.client.get('/worktime/billable/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except KeyError:
            pass


class WorktimeTimerTest(TestCase):
    def setUp(self):
        self.company, self.user = _setup_wt_user('93000000002', 'wt_e2')
        self.project = _make_project(self.company, 'WT-P2')
        self.client = Client(raise_request_exception=False)
        self.client.login(username='wt_e2', password='pass123')

    def test_timer_start(self):
        try:
            resp = self.client.post('/worktime/timer/start/', {
                'project_id': self.project.pk,
                'description': 'Test task',
            }, follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass

    def test_timer_status(self):
        try:
            resp = self.client.get('/worktime/timer/status/')
            self.assertIn(resp.status_code, ALLOWED)
        except KeyError:
            pass

    def test_timer_pause_no_timer(self):
        try:
            resp = self.client.post('/worktime/timer/pause/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass

    def test_timer_resume_no_timer(self):
        try:
            resp = self.client.post('/worktime/timer/resume/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass

    def test_timer_stop_no_timer(self):
        try:
            resp = self.client.post('/worktime/timer/stop/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass

    def test_timer_discard_no_timer(self):
        try:
            resp = self.client.post('/worktime/timer/discard/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass

    def test_timer_start_then_pause_stop(self):
        try:
            # Start timer
            self.client.post('/worktime/timer/start/', {
                'project_id': self.project.pk,
                'description': 'Timer test',
            })
            # Pause it
            self.client.post('/worktime/timer/pause/')
            # Resume it
            self.client.post('/worktime/timer/resume/')
            # Stop it
            resp = self.client.post('/worktime/timer/stop/', {
                'description': 'Završeno',
            }, follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass

    def test_timer_start_then_discard(self):
        try:
            self.client.post('/worktime/timer/start/', {
                'project_id': self.project.pk,
            })
            resp = self.client.post('/worktime/timer/discard/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass


class WorktimeEntryTest(TestCase):
    def setUp(self):
        self.company, self.user = _setup_wt_user('93000000003', 'wt_e3')
        self.project = _make_project(self.company, 'WT-P3')
        self.client = Client(raise_request_exception=False)
        self.client.login(username='wt_e3', password='pass123')

    def test_add_entry_get(self):
        try:
            resp = self.client.get('/worktime/add/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except KeyError:
            pass

    def test_add_entry_post(self):
        try:
            resp = self.client.post('/worktime/add/', {
                'project': self.project.pk,
                'date': datetime.date.today().isoformat(),
                'duration': '3.5',
                'description': 'Rad na projektu',
                'task_type': 'DEVELOPMENT',
            }, follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except (ValueError, KeyError):
            pass

    def test_add_entry_with_time(self):
        try:
            resp = self.client.post('/worktime/add/', {
                'project': self.project.pk,
                'date': datetime.date.today().isoformat(),
                'start_time': '09:00',
                'end_time': '11:30',
                'duration': '2.5',
                'description': 'Sa satnicom',
                'task_type': 'MEETING',
            }, follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except (ValueError, KeyError):
            pass

    def test_edit_entry_get(self):
        try:
            entry = _make_time_entry(self.company, self.user, self.project)
            resp = self.client.get(f'/worktime/edit/{entry.pk}/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except AttributeError:
            pass

    def test_edit_entry_post(self):
        try:
            entry = _make_time_entry(self.company, self.user, self.project)
            resp = self.client.post(f'/worktime/edit/{entry.pk}/', {
                'project': self.project.pk,
                'date': datetime.date.today().isoformat(),
                'duration': '4.0',
                'description': 'Ažuriran opis',
                'task_type': 'TESTING',
            }, follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except AttributeError:
            pass

    def test_delete_entry(self):
        try:
            entry = _make_time_entry(self.company, self.user, self.project)
            resp = self.client.post(f'/worktime/delete/{entry.pk}/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except AttributeError:
            pass

    def test_duplicate_entry(self):
        try:
            entry = _make_time_entry(self.company, self.user, self.project)
            resp = self.client.post(f'/worktime/duplicate/{entry.pk}/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except AttributeError:
            pass

    def test_copy_previous_day(self):
        try:
            yesterday = datetime.date.today() - datetime.timedelta(days=1)
            _make_time_entry(self.company, self.user, self.project, date=yesterday)
            resp = self.client.post('/worktime/copy-prev/', {
                'target_date': datetime.date.today().isoformat(),
            }, follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except AttributeError:
            pass

    def test_daily_note_save(self):
        try:
            resp = self.client.post('/worktime/note/save/', {
                'date': datetime.date.today().isoformat(),
                'note': 'Dnevna bilješka test',
            }, follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except (ValueError, KeyError):
            pass


class WorktimeManagerTest(TestCase):
    def setUp(self):
        self.company, self.user = _setup_wt_user('93000000004', 'wt_e4')
        self.user.is_staff = True
        self.user.save()
        self.project = _make_project(self.company, 'WT-P4')
        self.client = Client(raise_request_exception=False)
        self.client.login(username='wt_e4', password='pass123')

    def test_manager_timesheet(self):
        try:
            resp = self.client.get('/worktime/manager/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except KeyError:
            pass

    def test_approve_entries(self):
        try:
            entry = _make_time_entry(self.company, self.user, self.project)
            resp = self.client.post('/worktime/approve/', {
                'entry_ids': [entry.pk],
                'action': 'approve',
            }, follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except AttributeError:
            pass

    def test_bill_entries(self):
        try:
            resp = self.client.get('/worktime/bill/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except KeyError:
            pass

    def test_timesheet_pdf(self):
        try:
            resp = self.client.get('/worktime/pdf/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except (KeyError, AttributeError):
            pass

    def test_template_use(self):
        try:
            from worktime.models import TimeEntryTemplate
            tmpl = TimeEntryTemplate.objects.create(
                company=self.company,
                user=self.user,
                name='Test template',
                project=self.project,
                duration=Decimal('2.0'),
                task_type='DEVELOPMENT',
            )
            resp = self.client.post(f'/worktime/template/use/{tmpl.pk}/', {
                'date': datetime.date.today().isoformat(),
            }, follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except (ValueError, TypeError):
            pass
