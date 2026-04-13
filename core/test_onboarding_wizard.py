"""
Testovi za onboarding wizard — 8 testova pokrivaju:
- Wizard view logic (step detection, redirect)
- Profile update (step 1)
- Partner add (step 2)
- Item add (step 3)
- POS activate (step 5)
- Skip step
- Complete/dismiss
- Signal auto-completion (employee)
"""
from django.contrib.auth.models import User
from django.test import Client, TestCase

from companies.models import Company, OnboardingProgress


class OnboardingWizardTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(name='Test Wizard Firma', oib='12345678901')
        self.user = User.objects.create_user(username='wizard_user', password='test123')
        from accounts.models import UserProfile
        UserProfile.objects.create(user=self.user, company=self.company)
        self.client = Client()
        self.client.login(username='wizard_user', password='test123')

    def test_wizard_redirects_when_dismissed(self):
        ob, _ = OnboardingProgress.objects.get_or_create(company=self.company)
        ob.dismissed = True
        ob.save()
        resp = self.client.get('/onboarding/')
        self.assertEqual(resp.status_code, 302)
        self.assertIn('dashboard', resp.url)

    def test_wizard_shows_step_1_for_new_company(self):
        OnboardingProgress.objects.get_or_create(company=self.company)
        resp = self.client.get('/onboarding/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['step'], 1)

    def test_step1_update_profile(self):
        resp = self.client.post('/onboarding/update-profile/', {
            'name': 'Updated Firma', 'oib': '99988877766',
            'city': 'Zagreb', 'address': 'Ilica 1',
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['next_step'], 2)
        self.company.refresh_from_db()
        self.assertEqual(self.company.name, 'Updated Firma')
        ob = OnboardingProgress.objects.get(company=self.company)
        self.assertTrue(ob.profile_completed)

    def test_step2_add_partner(self):
        resp = self.client.post('/onboarding/add-partner/', {
            'name': 'Test Partner', 'oib': '11122233344',
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['next_step'], 3)

    def test_step3_add_item(self):
        resp = self.client.post('/onboarding/add-item/', {
            'name': 'Test Artikl', 'price': '99.99',
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        ob = OnboardingProgress.objects.get(company=self.company)
        self.assertTrue(ob.first_item_added)

    def test_step5_activate_pos(self):
        resp = self.client.post('/onboarding/activate-pos/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        ob = OnboardingProgress.objects.get(company=self.company)
        self.assertTrue(ob.pos_configured)

    def test_skip_step(self):
        resp = self.client.post('/onboarding/skip-step/', {'step': '3'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['next_step'], 4)
        ob = OnboardingProgress.objects.get(company=self.company)
        self.assertTrue(ob.first_item_added)

    def test_complete_dismiss(self):
        resp = self.client.post('/onboarding/complete/')
        self.assertEqual(resp.status_code, 200)
        ob = OnboardingProgress.objects.get(company=self.company)
        self.assertTrue(ob.dismissed)


class OnboardingSignalTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(name='Signal Test Firma', oib='55566677788')
        OnboardingProgress.objects.get_or_create(company=self.company)

    def test_employee_signal_marks_step(self):
        from worktime.models import EmployeeProfile
        user = User.objects.create_user(username='emp_signal', password='test123')
        EmployeeProfile.objects.create(
            company=self.company, user=user,
            first_name='Test', last_name='Emp',
        )
        ob = OnboardingProgress.objects.get(company=self.company)
        self.assertTrue(ob.first_employee_added)

    def test_percent_calculation(self):
        ob = OnboardingProgress.objects.get(company=self.company)
        self.assertEqual(ob.percent, 0)
        ob.profile_completed = True
        ob.first_partner_added = True
        ob.save()
        ob.refresh_from_db()
        self.assertEqual(ob.completed_steps, 2)
        self.assertEqual(ob.percent, 28)  # 2/7 * 100 = 28
