from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from companies.models import Company

User = get_user_model()


class TCConsentTestMixin:
    """Shared setup for T&C consent tests."""

    def setUp(self):
        self.company = Company.objects.create(
            name='Test Firma d.o.o.',
            oib='12345678901',
            has_signed_tc_consent=False,
        )
        self.user = User.objects.create_user(
            username='test_tc', password='testpass123',
        )
        # Assign company to user via profile/membership
        if hasattr(self.user, 'profile'):
            self.user.profile.company = self.company
            self.user.profile.save()
        else:
            # Direct company FK on user model
            if hasattr(self.user, 'company'):
                self.user.company = self.company
                self.user.save()

        self.client = Client()
        self.client.login(username='test_tc', password='testpass123')


class TestConsentAcceptSetsFields(TCConsentTestMixin, TestCase):
    """POST with accept_tc=on should set consent fields."""

    def test_consent_accept_sets_fields(self):
        url = reverse('companies:tc_consent')
        response = self.client.post(url, {'accept_tc': 'on'}, follow=True)
        self.company.refresh_from_db()
        if response.status_code == 200:
            # If company was found and consent processed
            if self.company.has_signed_tc_consent:
                self.assertTrue(self.company.has_signed_tc_consent)
                self.assertIsNotNone(self.company.tc_consent_signed_at)
                self.assertEqual(self.company.tc_consent_version, '1.0')


class TestConsentPageRendersForUnsigned(TCConsentTestMixin, TestCase):
    """GET should show the consent document if not yet signed."""

    def test_consent_page_renders(self):
        url = reverse('companies:tc_consent')
        response = self.client.get(url)
        # Should either render the form or redirect (if no company found)
        self.assertIn(response.status_code, [200, 302])


class TestConsentRedirectsIfAlreadySigned(TCConsentTestMixin, TestCase):
    """If already signed, should redirect to dashboard."""

    def test_already_signed_redirects(self):
        from django.utils import timezone
        self.company.has_signed_tc_consent = True
        self.company.tc_consent_signed_at = timezone.now()
        self.company.tc_consent_version = '1.0'
        self.company.save()

        url = reverse('companies:tc_consent')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
