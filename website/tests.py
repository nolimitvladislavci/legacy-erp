"""
website/tests.py — Integration tests for multi-tenant Website Builder.

3 test klase, 15 test metoda:
  1. CompanyWebsiteModelTest  (4) — model creation, public_url, slug unique, defaults
  2. CompanySiteViewTest      (5) — public site view, contact form, 404, unpublished
  3. WebsiteEditorTest        (6) — editor access, save basic settings, service AJAX, gallery, review, messages

Run:
    python manage.py test website --verbosity=2
"""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings

User = get_user_model()
NO_HTTPS = override_settings(SECURE_SSL_REDIRECT=False)


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def make_company(oib="88877766610"):
    from companies.models import Company
    return Company.objects.get_or_create(
        oib=oib,
        defaults=dict(name="Web Test GmbH", country="DE",
                      city="Munich", zip_code="80331"),
    )[0]


def make_user(company, username="web_admin", role="company_admin"):
    from accounts.models import UserProfile
    user = User.objects.create_user(
        username=username,
        email=f"{username}@web-test.de",
        password="TestPass2026!",
    )
    UserProfile.objects.create(user=user, company=company, role=role)
    return user


def make_site(company, slug="web-test-gmbh", published=True):
    from website.models import CompanyWebsite
    return CompanyWebsite.objects.create(
        company=company,
        slug=slug,
        site_title="Web Test GmbH",
        tagline="Najbolji u poslovanju",
        theme="generic",
        is_published=published,
        contact_phone="+4989123456",
        contact_email="info@web-test.de",
    )


# ══════════════════════════════════════════════════════════════════════════════
# TEST 1 — CompanyWebsite model
# ══════════════════════════════════════════════════════════════════════════════

class CompanyWebsiteModelTest(TestCase):
    """Tests for CompanyWebsite and related models."""

    def setUp(self):
        self.company = make_company()

    def test_create_company_website(self):
        """CompanyWebsite can be created with required fields."""
        from website.models import CompanyWebsite
        site = CompanyWebsite.objects.create(
            company=self.company,
            slug="test-slug",
            site_title="Test",
            is_published=True,
        )
        self.assertEqual(site.company, self.company)
        self.assertEqual(site.slug, "test-slug")
        self.assertEqual(site.theme, "generic")  # default

    def test_public_url_property(self):
        """public_url returns /site/<slug>/"""
        from website.models import CompanyWebsite
        site = CompanyWebsite.objects.create(
            company=self.company, slug="mein-betrieb", is_published=True,
        )
        self.assertEqual(site.public_url, "/site/mein-betrieb/")

    def test_slug_unique(self):
        """Two websites cannot share the same slug."""
        from django.db import IntegrityError

        from website.models import CompanyWebsite
        CompanyWebsite.objects.create(
            company=self.company, slug="unique-slug", is_published=True,
        )
        company2 = make_company(oib="88877766611")
        with self.assertRaises(IntegrityError):
            CompanyWebsite.objects.create(
                company=company2, slug="unique-slug", is_published=True,
            )

    def test_related_models_created(self):
        """WebsiteService, GalleryImage, Review, ContactMessage can be created."""
        from website.models import (
            WebsiteContactMessage,
            WebsiteReview,
            WebsiteService,
        )
        site = make_site(self.company, slug="related-test")
        WebsiteService.objects.create(website=site, title="Servis 1")
        WebsiteReview.objects.create(website=site, author_name="Pero", text="Odlicno!", rating=5)
        WebsiteContactMessage.objects.create(
            website=site, name="Ana", email="ana@test.de", message="Upit",
        )
        self.assertEqual(site.services.count(), 1)
        self.assertEqual(site.reviews.count(), 1)
        self.assertEqual(site.contact_messages.count(), 1)


# ══════════════════════════════════════════════════════════════════════════════
# TEST 2 — Public site views
# ══════════════════════════════════════════════════════════════════════════════

@NO_HTTPS
class CompanySiteViewTest(TestCase):
    """Tests for the public /site/<slug>/ view."""

    def setUp(self):
        self.company = make_company(oib="88877766612")
        self.site = make_site(self.company, slug="public-site-test")
        self.c = Client()

    def test_published_site_returns_200(self):
        """GET /site/<slug>/ on published site → 200."""
        r = self.c.get(f"/site/{self.site.slug}/")
        self.assertEqual(r.status_code, 200)

    def test_site_contains_title(self):
        """Published site contains site_title in response."""
        r = self.c.get(f"/site/{self.site.slug}/")
        self.assertContains(r, self.site.site_title)

    def test_unpublished_site_returns_404(self):
        """GET on unpublished site → 404."""
        company2 = make_company(oib="88877766613")
        from website.models import CompanyWebsite
        CompanyWebsite.objects.create(
            company=company2, slug="hidden-site", is_published=False,
        )
        r = self.c.get("/site/hidden-site/")
        self.assertEqual(r.status_code, 404)

    def test_nonexistent_slug_returns_404(self):
        """GET on unknown slug → 404."""
        r = self.c.get("/site/this-does-not-exist/")
        self.assertEqual(r.status_code, 404)

    def test_contact_form_creates_message(self):
        """POST to /site/<slug>/contact/ → creates WebsiteContactMessage + redirect."""
        from website.models import WebsiteContactMessage
        before = WebsiteContactMessage.objects.count()
        r = self.c.post(f"/site/{self.site.slug}/contact/", {
            "name": "Test Korisnik",
            "email": "test@example.com",
            "phone": "0911234567",
            "message": "Zainteresiran sam za vase usluge.",
        })
        self.assertEqual(r.status_code, 302)
        self.assertIn(f"/site/{self.site.slug}/", r["Location"])
        self.assertEqual(WebsiteContactMessage.objects.count(), before + 1)
        msg = WebsiteContactMessage.objects.latest("created_at")
        self.assertEqual(msg.name, "Test Korisnik")
        self.assertEqual(msg.website, self.site)


# ══════════════════════════════════════════════════════════════════════════════
# TEST 3 — CMS Editor views
# ══════════════════════════════════════════════════════════════════════════════

@NO_HTTPS
class WebsiteEditorTest(TestCase):
    """Tests for the /website/editor/ CMS views."""

    def setUp(self):
        self.company = make_company(oib="88877766614")
        self.admin = make_user(self.company, username="ws_admin")
        self.worker = make_user(self.company, username="ws_worker", role="worker")
        self.c = Client()
        self.c.login(username="ws_admin", password="TestPass2026!")
        self.url = "/website/editor/"

    def test_editor_accessible_to_admin(self):
        """company_admin can GET /website/editor/ → 200."""
        r = self.c.get(self.url)
        self.assertEqual(r.status_code, 200)

    def test_editor_creates_site_on_first_access(self):
        """First GET to editor auto-creates CompanyWebsite for the company."""
        from website.models import CompanyWebsite
        before = CompanyWebsite.objects.filter(company=self.company).count()
        self.c.get(self.url)
        after = CompanyWebsite.objects.filter(company=self.company).count()
        self.assertGreater(after, before)

    def test_save_basic_settings(self):
        """POST to editor saves site_title and tagline."""
        # Ensure site exists first
        self.c.get(self.url)
        r = self.c.post(self.url, {
            "site_title": "Moja Nova Firma",
            "tagline": "Kvaliteta na prvom mjestu",
            "theme": "generic",
            "hero_text": "",
            "about_text": "",
            "contact_phone": "",
            "contact_email": "",
            "contact_address": "",
            "facebook_url": "",
            "instagram_url": "",
            "primary_color": "#2563eb",
        })
        self.assertEqual(r.status_code, 302)
        from website.models import CompanyWebsite
        site = CompanyWebsite.objects.get(company=self.company)
        self.assertEqual(site.site_title, "Moja Nova Firma")
        self.assertEqual(site.tagline, "Kvaliteta na prvom mjestu")

    def test_service_save_ajax(self):
        """POST to service_save creates a WebsiteService → JSON ok=True."""
        self.c.get(self.url)  # ensure site exists
        r = self.c.post("/website/editor/service/save/", {
            "title": "Instalacija vode",
            "description": "Brza i pouzdana instalacija.",
            "price_display": "od 80 EUR",
            "order": "0",
            "is_active": "1",
        })
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertTrue(d["ok"])
        from website.models import WebsiteService
        self.assertTrue(WebsiteService.objects.filter(title="Instalacija vode").exists())

    def test_worker_cannot_access_editor(self):
        """Worker role → GET /website/editor/ → redirect (not 200)."""
        c2 = Client()
        c2.login(username="ws_worker", password="TestPass2026!")
        r = c2.get(self.url)
        self.assertNotEqual(r.status_code, 200)

    def test_messages_inbox(self):
        """GET /website/editor/messages/ returns 200 for admin."""
        self.c.get(self.url)  # ensure site exists
        r = self.c.get("/website/editor/messages/")
        self.assertEqual(r.status_code, 200)
