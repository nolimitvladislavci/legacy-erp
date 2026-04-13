from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile
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
        # Create UserProfile and link to company
        UserProfile.objects.create(
            user=self.user,
            company=self.company,
            role='company_admin',
        )

        self.client = Client()
        self.client.login(username='test_tc', password='testpass123')


@override_settings(LANGUAGE_CODE="hr", SECURE_SSL_REDIRECT=False)
class TestConsentAcceptSetsFields(TCConsentTestMixin, TestCase):
    """POST with accept_tc=on should set consent fields."""

    def test_consent_accept_sets_fields(self):
        url = reverse('companies:tc_consent')
        response = self.client.post(url, {'accept_tc': 'on'})
        self.assertIn(response.status_code, [302, 301])
        self.company.refresh_from_db()
        self.assertTrue(self.company.has_signed_tc_consent)
        self.assertIsNotNone(self.company.tc_consent_signed_at)
        self.assertEqual(self.company.tc_consent_version, '1.0')


@override_settings(LANGUAGE_CODE="hr", SECURE_SSL_REDIRECT=False)
class TestConsentPageRendersForUnsigned(TCConsentTestMixin, TestCase):
    """GET should show the consent document if not yet signed."""

    def test_consent_page_renders(self):
        url = reverse('companies:tc_consent')
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'accept_tc')


@override_settings(LANGUAGE_CODE="hr", SECURE_SSL_REDIRECT=False)
class TestConsentRedirectsIfAlreadySigned(TCConsentTestMixin, TestCase):
    """If already signed, should redirect to dashboard."""

    def test_already_signed_redirects(self):
        self.company.has_signed_tc_consent = True
        self.company.tc_consent_signed_at = timezone.now()
        self.company.tc_consent_version = '1.0'
        self.company.save()

        url = reverse('companies:tc_consent')
        response = self.client.get(url)
        self.assertIn(response.status_code, [301, 302])


@override_settings(LANGUAGE_CODE="hr", SECURE_SSL_REDIRECT=False)
class TestConsentBannerVisible(TCConsentTestMixin, TestCase):
    """Banner should be visible when company has not signed T&C."""

    def test_consent_banner_visible_without_consent(self):
        url = reverse('companies:tc_consent')
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Prihva')
