from django.test import RequestFactory, TestCase

from no_limit.models import AmbassadorApplication, CountryChapter, PartnershipLead


class AmbassadorApplicationTest(TestCase):
    def test_create_application(self):
        app = AmbassadorApplication.objects.create(
            full_name="Test User",
            email="test@example.com",
            country="HR",
            city="Zagreb",
            motivation="Test motivation",
            desired_role="national_coordinator",
        )
        self.assertEqual(app.status, "pending")
        self.assertEqual(app.get_country_display(), "Hrvatska")
        self.assertIn("Test User", str(app))

    def test_form_valid_post(self):
        response = self.client.post(
            "/no-limit/ambasadori/prijava/",
            {
                "full_name": "Marija Test",
                "email": "marija@test.hr",
                "country": "HR",
                "motivation": "Želim pomoći djeci",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(AmbassadorApplication.objects.count(), 1)
        app = AmbassadorApplication.objects.first()
        self.assertEqual(app.full_name, "Marija Test")

    def test_form_invalid_post(self):
        response = self.client.post(
            "/no-limit/ambasadori/prijava/",
            {"full_name": "Incomplete"},
        )
        # Missing required fields — stays on form
        self.assertEqual(response.status_code, 200)
        self.assertEqual(AmbassadorApplication.objects.count(), 0)

    def test_form_get(self):
        response = self.client.get("/no-limit/ambasadori/prijava/")
        self.assertEqual(response.status_code, 200)


class CountryChapterTest(TestCase):
    def test_create_chapter(self):
        ch = CountryChapter.objects.create(
            country="HR",
            country_name="Hrvatska",
            coordinator_name="Ivan Brtan",
            is_active=True,
        )
        self.assertTrue(ch.is_active)
        self.assertIn("Hrvatska", str(ch))


class PartnershipLeadTest(TestCase):
    def test_create_lead(self):
        lead = PartnershipLead.objects.create(
            name="Viskovic Bau",
            organization="Viskovic Bau GmbH",
            country="DE",
            partnership_type="sponsor",
        )
        self.assertEqual(lead.status, "new")
        self.assertIn("Sponzor", str(lead))


class PageLoadTest(TestCase):
    def test_landing(self):
        response = self.client.get("/no-limit/")
        self.assertEqual(response.status_code, 200)

    def test_statut(self):
        response = self.client.get("/no-limit/statut/")
        self.assertEqual(response.status_code, 200)

    def test_ambasadori(self):
        response = self.client.get("/no-limit/ambasadori/")
        self.assertEqual(response.status_code, 200)

    def test_partneri(self):
        response = self.client.get("/no-limit/partneri/")
        self.assertEqual(response.status_code, 200)

    def test_projekti(self):
        response = self.client.get("/no-limit/projekti/")
        self.assertEqual(response.status_code, 200)

    def test_hvala(self):
        response = self.client.get("/no-limit/ambasadori/hvala/")
        self.assertEqual(response.status_code, 200)
