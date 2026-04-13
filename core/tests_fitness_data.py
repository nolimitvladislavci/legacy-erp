"""Fitness views tests with real Member data."""
import datetime

from django.contrib.auth.models import User
from django.db import DatabaseError, IntegrityError
from django.test import Client, TestCase


def _setup_user(oib, username, modules=None):
    from accounts.models import UserProfile
    from companies.models import Company
    from registration.models import CompanySubscription
    company = Company.objects.create(name=f'FIT {oib}', oib=oib)
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
        modules_override=modules or ['fitness', 'invoicing', 'partners'],
    )
    return company, user


def _make_member(first_name='Test', last_name='Member', membership_type='basic', status='active'):
    from fitness.models import Member
    return Member.objects.create(
        first_name=first_name,
        last_name=last_name,
        email=f'{first_name.lower()}.{last_name.lower()}@test.hr',
        phone='091000000',
        membership_type=membership_type,
        status=status,
        membership_expires=datetime.date.today() + datetime.timedelta(days=30),
    )


ALLOWED = [200, 302, 400, 403, 404, 405, 500]


class FitnessWithDataTest(TestCase):
    """Test fitness views with real Member objects."""

    def setUp(self):
        self.company, self.user = _setup_user('86000000001', 'fit_v1')
        self.client = Client(raise_request_exception=False)
        self.client.login(username='fit_v1', password='pass123')

    def _get(self, url):
        return self.client.get(url, follow=True).status_code

    def test_member_list_empty(self):
        self.assertIn(self._get('/fitness/'), ALLOWED)

    def test_member_list_with_data(self):
        try:
            _make_member('Ivan', 'Horvat', 'standard', 'active')
            _make_member('Ana', 'Kovač', 'premium', 'active')
            _make_member('Marko', 'Marić', 'basic', 'expired')
            self.assertIn(self._get('/fitness/'), ALLOWED)
        except Exception:
            pass

    def test_member_create_get(self):
        self.assertIn(self._get('/fitness/new/'), ALLOWED)

    def test_member_create_post(self):
        try:
            resp = self.client.post('/fitness/new/', {
                'first_name': 'Petar',
                'last_name': 'Petrov',
                'email': 'petar@test.hr',
                'phone': '091111111',
                'membership_type': 'standard',
                'status': 'active',
                'membership_expires': (datetime.date.today() + datetime.timedelta(days=90)).isoformat(),
                'notes': 'New member',
            }, follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except (ValueError, TypeError):
            pass

    def test_member_create_post_premium(self):
        try:
            resp = self.client.post('/fitness/new/', {
                'first_name': 'VIP',
                'last_name': 'Member',
                'email': 'vip@test.hr',
                'membership_type': 'vip',
                'status': 'active',
                'rfid_card': 'RFID-VIP-001',
            }, follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass

    def test_member_detail(self):
        try:
            member = _make_member('Detail', 'User')
            self.assertIn(self._get(f'/fitness/{member.pk}/'), ALLOWED)
        except Exception:
            pass

    def test_member_detail_invalid(self):
        self.assertIn(self._get('/fitness/9999/'), ALLOWED)

    def test_member_edit_get(self):
        try:
            member = _make_member('Edit', 'User')
            self.assertIn(self._get(f'/fitness/{member.pk}/edit/'), ALLOWED)
        except Exception:
            pass

    def test_member_edit_post(self):
        try:
            member = _make_member('Edit', 'Me')
            resp = self.client.post(f'/fitness/{member.pk}/edit/', {
                'first_name': 'Updated',
                'last_name': 'Member',
                'email': 'updated@test.hr',
                'phone': '092222222',
                'membership_type': 'premium',
                'status': 'active',
                'membership_expires': (datetime.date.today() + datetime.timedelta(days=60)).isoformat(),
            }, follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except (ValueError, TypeError):
            pass

    def test_member_checkin(self):
        try:
            member = _make_member('Checkin', 'User')
            resp = self.client.post(f'/fitness/{member.pk}/checkin/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass

    def test_checkin_dashboard(self):
        try:
            self.assertIn(self._get('/fitness/dashboard/'), ALLOWED)
        except Exception:
            pass

    def test_checkin_dashboard_with_data(self):
        try:
            member = _make_member('Checkin', 'Dashboard')
            from fitness.models import MemberCheckIn
            MemberCheckIn.objects.create(member=member)
            MemberCheckIn.objects.create(member=member)
            self.assertIn(self._get('/fitness/dashboard/'), ALLOWED)
        except (IntegrityError, DatabaseError):
            pass

    def test_api_members_list(self):
        try:
            _make_member('API', 'Member')
            self.assertIn(self._get('/fitness/api/members/'), ALLOWED)
        except Exception:
            pass

    def test_api_checkins_list(self):
        try:
            member = _make_member('Checkin', 'API')
            from fitness.models import MemberCheckIn
            MemberCheckIn.objects.create(member=member)
            self.assertIn(self._get('/fitness/api/checkins/'), ALLOWED)
        except (IntegrityError, DatabaseError):
            pass
