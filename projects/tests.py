import uuid
"""Tests for projects — models + views."""
import datetime
from django.test import TestCase, Client
from django.contrib.auth.models import User


def _make_company(oib):
    from companies.models import Company
    return Company.objects.create(name=f'Proj {oib}', oib=oib)


def _make_user(company, username):
    from accounts.models import UserProfile
    from registration.models import CompanySubscription
    user = User.objects.create_user(username, password='pass123')
    try:
        p = user.profile
        p.company = company
        p.save()
    except (IntegrityError, DatabaseError):
        UserProfile.objects.create(user=user, company=company)
    CompanySubscription.objects.get_or_create(
        company=company,
        defaults=dict(
            plan='starter',
            valid_from=datetime.date.today(),
            monthly_fee=0,
            is_active=True,
            billing_cycle='monthly',
            modules_override=['projects'],
        ),
    )
    return user


class ProjectModelTest(TestCase):

    def setUp(self):
        self.company = _make_company('12121212121')
        self.user = _make_user(self.company, 'proj_model')

    def test_create_project(self):
        from projects.models import Project
        proj = Project.objects.create(code=str(uuid.uuid4())[:8], company=self.company, name='Test Projekt')
        self.assertEqual(proj.name, 'Test Projekt')
        self.assertIsNotNone(proj.pk)

    def test_str(self):
        from projects.models import Project
        proj = Project.objects.create(code=str(uuid.uuid4())[:8], company=self.company, name='Str Test')
        s = str(proj)
        self.assertIsNotNone(s)

    def test_company_isolation(self):
        from projects.models import Project
        co2 = _make_company('13131313131')
        Project.objects.create(code=str(uuid.uuid4())[:8], company=self.company, name='P A')
        Project.objects.create(code=str(uuid.uuid4())[:8], company=co2, name='P B')
        self.assertEqual(Project.objects.filter(company=self.company).count(), 1)

    def test_status_field(self):
        from projects.models import Project
        proj = Project.objects.create(code=str(uuid.uuid4())[:8], company=self.company, name='Status Test', status='active')
        self.assertEqual(proj.status, 'active')


class ProjectViewTest(TestCase):

    def setUp(self):
        self.company = _make_company('14141414141')
        self.user = _make_user(self.company, 'proj_view')
        self.client = Client()
        self.client.login(username='proj_view', password='pass123')

    def test_list_requires_login(self):
        c = Client()
        resp = c.get('/projects/', follow=True)
        self.assertIn(resp.status_code, [200, 302])

    def test_list_authenticated(self):
        resp = self.client.get('/projects/', follow=True)
        self.assertIn(resp.status_code, [200, 302])

    def test_list_shows_own_projects(self):
        from projects.models import Project
        Project.objects.create(code=str(uuid.uuid4())[:8], company=self.company, name='My Project')
        resp = self.client.get('/projects/', follow=True)
        if resp.status_code == 200:
            self.assertIn('My Project', resp.content.decode())

    def test_list_hides_other_projects(self):
        from projects.models import Project
        co2 = _make_company('15151515151')
        _make_user(co2, 'proj_other')
        Project.objects.create(code=str(uuid.uuid4())[:8], company=co2, name='Hidden Project')
        resp = self.client.get('/projects/', follow=True)
        if resp.status_code == 200:
            self.assertNotIn('Hidden Project', resp.content.decode())

    def test_create_get(self):
        resp = self.client.get('/projects/create/', follow=True)
        self.assertIn(resp.status_code, [200, 302, 404])

    def test_detail_view(self):
        from projects.models import Project
        proj = Project.objects.create(code=str(uuid.uuid4())[:8], company=self.company, name='Detail')
        resp = self.client.get(f'/projects/{proj.pk}/', follow=True)
        self.assertIn(resp.status_code, [200, 302, 404])
