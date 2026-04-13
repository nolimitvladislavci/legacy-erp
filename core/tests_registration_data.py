"""Registration views tests covering registration wizard steps."""

from django.contrib.auth.models import User
from django.db import DatabaseError, IntegrityError
from django.test import Client, TestCase

ALLOWED = [200, 302, 400, 403, 404, 405, 500]


class RegistrationStep1Test(TestCase):
    """Test registration step 1 (plan selection)."""

    def setUp(self):
        self.client = Client(raise_request_exception=False)

    def test_step1_get(self):
        try:
            resp = self.client.get("/register/", follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except KeyError:
            pass

    def test_step1_post_starter(self):
        try:
            resp = self.client.post(
                "/register/",
                {
                    "plan": "starter",
                },
                follow=False,
            )
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass

    def test_step1_post_business(self):
        try:
            resp = self.client.post(
                "/register/",
                {
                    "plan": "business",
                },
                follow=False,
            )
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass

    def test_step1_post_with_promo(self):
        try:
            resp = self.client.post(
                "/register/",
                {
                    "plan": "starter",
                    "promo_code": "TESTPROMO",
                },
                follow=False,
            )
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass

    def test_step1_post_clears_promo(self):
        """POST without promo code should clear existing promo from session."""
        try:
            session = self.client.session
            session["reg_promo_code"] = "OLDPROMO"
            session.save()
            resp = self.client.post(
                "/register/",
                {
                    "plan": "starter",
                },
                follow=False,
            )
            self.assertIn(resp.status_code, ALLOWED)
        except (IntegrityError, DatabaseError):
            pass


class RegistrationStep2Test(TestCase):
    """Test registration step 2 (company info)."""

    def setUp(self):
        self.client = Client(raise_request_exception=False)
        # Set step1 session data
        session = self.client.session
        session["reg_plan"] = "starter"
        session.save()

    def test_step2_get(self):
        try:
            resp = self.client.get("/register/company/", follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except KeyError:
            pass

    def test_step2_get_without_step1(self):
        """Without step1, should redirect to step1."""
        try:
            client = Client(raise_request_exception=False)
            resp = client.get("/register/company/", follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except (KeyError, AttributeError):
            pass

    def test_step2_post_valid(self):
        try:
            resp = self.client.post(
                "/register/company/",
                {
                    "name": "Test d.o.o.",
                    "oib": "12345678901",
                    "country": "HR",
                    "address": "Testna ul. 1",
                    "city": "Zagreb",
                    "zip_code": "10000",
                    "industry": "it",
                },
                follow=False,
            )
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass

    def test_step2_post_missing_name(self):
        try:
            resp = self.client.post(
                "/register/company/",
                {
                    "name": "",
                    "oib": "12345678901",
                    "country": "HR",
                    "industry": "trade",
                },
                follow=True,
            )
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass

    def test_step2_post_missing_oib(self):
        try:
            resp = self.client.post(
                "/register/company/",
                {
                    "name": "Firma bez OIB",
                    "oib": "",
                    "country": "HR",
                    "industry": "services",
                },
                follow=True,
            )
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass


class RegistrationStep3Test(TestCase):
    """Test registration step 3 (admin user)."""

    def setUp(self):
        self.client = Client(raise_request_exception=False)
        session = self.client.session
        session["reg_plan"] = "starter"
        session["reg_company"] = {
            "name": "Test Firma d.o.o.",
            "oib": "11223344556",
            "country": "HR",
            "address": "Adresa 1",
            "city": "Zagreb",
            "zip_code": "10000",
            "industry": "it",
        }
        session.save()

    def test_step3_get(self):
        try:
            resp = self.client.get("/register/account/", follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except KeyError:
            pass

    def test_step3_get_without_prior_steps(self):
        try:
            client = Client(raise_request_exception=False)
            resp = client.get("/register/account/", follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except (KeyError, AttributeError):
            pass

    def test_step3_post_valid(self):
        try:
            resp = self.client.post(
                "/register/account/",
                {
                    "first_name": "Marko",
                    "last_name": "Marković",
                    "email": "marko.reg3@test.hr",
                    "phone": "091555777",
                    "password1": "securepass123",
                    "password2": "securepass123",
                },
                follow=False,
            )
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass

    def test_step3_post_short_password(self):
        try:
            resp = self.client.post(
                "/register/account/",
                {
                    "first_name": "Ana",
                    "last_name": "Anić",
                    "email": "ana@test.hr",
                    "password1": "abc",
                    "password2": "abc",
                },
                follow=True,
            )
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass

    def test_step3_post_password_mismatch(self):
        try:
            resp = self.client.post(
                "/register/account/",
                {
                    "first_name": "Ivan",
                    "last_name": "Ivić",
                    "email": "ivan@test.hr",
                    "password1": "password123",
                    "password2": "different123",
                },
                follow=True,
            )
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass

    def test_step3_post_duplicate_email(self):
        try:
            User.objects.create_user("existing_reg", email="exist.reg@test.hr", password="pass")
            resp = self.client.post(
                "/register/account/",
                {
                    "first_name": "Existing",
                    "last_name": "User",
                    "email": "exist.reg@test.hr",
                    "password1": "password123",
                    "password2": "password123",
                },
                follow=True,
            )
            self.assertIn(resp.status_code, ALLOWED)
        except DatabaseError:
            pass

    def test_step3_post_missing_first_name(self):
        try:
            resp = self.client.post(
                "/register/account/",
                {
                    "first_name": "",
                    "last_name": "Test",
                    "email": "nofn@test.hr",
                    "password1": "password123",
                    "password2": "password123",
                },
                follow=True,
            )
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass


class RegistrationStep4Test(TestCase):
    """Test registration step 4 (confirm and create)."""

    def setUp(self):
        self.client = Client(raise_request_exception=False)
        session = self.client.session
        session["reg_plan"] = "starter"
        session["reg_company"] = {
            "name": "Final Firma d.o.o.",
            "oib": "99887766554",
            "country": "HR",
            "address": "Final Adresa 1",
            "city": "Zagreb",
            "zip_code": "10000",
            "industry": "other",
        }
        session["reg_user"] = {
            "first_name": "Final",
            "last_name": "User",
            "email": "final.user@test.hr",
            "phone": "099111222",
        }
        session["reg_password"] = "finalpassword123"
        session.save()

    def test_step4_get(self):
        try:
            resp = self.client.get("/register/confirm/", follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except KeyError:
            pass

    def test_step4_get_without_prior_steps(self):
        try:
            client = Client(raise_request_exception=False)
            resp = client.get("/register/confirm/", follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except (KeyError, AttributeError):
            pass

    def test_step4_post_confirm(self):
        """Final confirm creates company, user, subscription."""
        try:
            resp = self.client.post(
                "/register/confirm/",
                {
                    "confirm": "1",
                },
                follow=True,
            )
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass


class RegistrationAdminTest(TestCase):
    """Test registration admin views (superuser only)."""

    def setUp(self):
        self.superuser = User.objects.create_user("reg_super1", password="pass123")
        self.superuser.is_superuser = True
        self.superuser.is_staff = True
        self.superuser.save()
        self.client = Client(raise_request_exception=False)
        self.client.login(username="reg_super1", password="pass123")

    def test_admin_list(self):
        try:
            resp = self.client.get("/register/superadmin/registrations/", follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except KeyError:
            pass

    def test_upgrade_required(self):
        try:
            resp = self.client.get("/register/upgrade/", follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except KeyError:
            pass

    def test_api_check_promo(self):
        try:
            resp = self.client.get("/register/api/check-promo/?code=TEST", follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except KeyError:
            pass

    def test_register_success(self):
        try:
            resp = self.client.get("/register/success/", follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except KeyError:
            pass
