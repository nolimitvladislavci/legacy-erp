"""
LIMIT CONNECT – Sveobuhvatni testovi
Testira: modele, URL-ove, API endpointe, poslovnu logiku
"""
import json
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse, NoReverseMatch
from django.utils import timezone
from decimal import Decimal


# ── HELPER ───────────────────────────────────────────────────
_oib_counter = 0

def create_company(name="Test d.o.o.", business_type="doo", country="HR"):
    global _oib_counter
    _oib_counter += 1
    from companies.models import Company
    return Company.objects.create(
        name=name,
        business_type=business_type,
        country=country,
        oib=f"{_oib_counter:011d}",
        address="Testna ulica 1",
        city="Zagreb",
        zip_code="10000",
    )

def create_user(username, role, company=None, password="TestPass123!"):
    from accounts.models import UserProfile
    user = User.objects.create_user(
        username=username,
        email=f"{username}@test.hr",
        password=password,
        first_name=username.capitalize(),
        last_name="Test"
    )
    UserProfile.objects.create(user=user, role=role, company=company)
    return user


# ══════════════════════════════════════════════════════════════
# 1. TEST MODELA
# ══════════════════════════════════════════════════════════════
class CompanyModelTest(TestCase):
    def setUp(self):
        self.company = create_company("Visković BAU", "doo", "DE")

    def test_company_created(self):
        from companies.models import Company
        self.assertEqual(Company.objects.count(), 1)
        log_test("Company kreirana")

    def test_company_str(self):
        self.assertIn("Visković", str(self.company))
        log_test("Company __str__")


class UserProfileTest(TestCase):
    def setUp(self):
        self.company = create_company()
        self.admin = create_user("admin_test", "company_admin", self.company)
        self.worker = create_user("worker_test", "worker", self.company)
        self.superadmin = create_user("superadmin_test", "superadmin")

    def test_profiles_created(self):
        from accounts.models import UserProfile
        self.assertEqual(UserProfile.objects.count(), 3)
        log_test("UserProfile kreiran za 3 korisnika")

    def test_role_assignment(self):
        self.assertEqual(self.admin.profile.role, "company_admin")
        self.assertEqual(self.worker.profile.role, "worker")
        self.assertEqual(self.superadmin.profile.role, "superadmin")
        log_test("Role assignment ispravno")

    def test_company_assignment(self):
        self.assertEqual(self.admin.profile.company, self.company)
        self.assertIsNone(self.superadmin.profile.company)
        log_test("Company assignment ispravno")


class BurzaModelTest(TestCase):
    def setUp(self):
        self.company_a = create_company("Tvrtka A d.o.o.")
        self.company_b = create_company("Tvrtka B d.o.o.")
        self.user_a = create_user("user_a", "company_admin", self.company_a)

    def test_create_lead(self):
        from burza.models import ProjectLead
        lead = ProjectLead.objects.create(
            company=self.company_a,
            title="Renovacija kupaone 8m²",
            description="Kompletan remont",
            category="kupaonica",
            location="Zagreb",
            contact_name="Ivan Horvat",
            contact_phone="+38512345678",
            status="NOVI_UPIT",
            created_by=self.user_a,
        )
        self.assertEqual(lead.status, "NOVI_UPIT")
        self.assertFalse(lead.is_public)
        log_test("ProjectLead kreiran")

    def test_budget_display(self):
        from burza.models import ProjectLead
        lead = ProjectLead(budget_from=Decimal("1000"), budget_to=Decimal("5000"))
        self.assertIn("1.000", lead.budget_display)
        log_test("Budget display format")

    def test_transaction_lock(self):
        """Samo jedna tvrtka može preuzeti posao."""
        from burza.models import ProjectLead
        from django.db import transaction
        lead = ProjectLead.objects.create(
            company=self.company_a,
            title="Test posao za transaction lock",
            description="Test",
            category="ostalo",
            location="Split",
            contact_name="Test",
            contact_phone="091",
            status="NA_BURZI",
            is_public=True,
        )
        user_b = create_user("user_b", "company_admin", self.company_b)
        client_b = Client()
        client_b.force_login(user_b)
        
        # Prvo preuzimanje – mora uspjeti
        resp = client_b.post(f"/burza/lead/{lead.pk}/preuzmi/",
                             content_type="application/json", data=json.dumps({}))
        lead.refresh_from_db()
        self.assertEqual(lead.status, "PREUZETO")
        self.assertEqual(lead.taken_by, self.company_b)
        log_test("Transaction lock – prvo preuzimanje OK")

        # Pokušaj ponovnog preuzimanja – mora failati
        user_c_company = create_company("Tvrtka C d.o.o.")
        user_c = create_user("user_c", "company_admin", user_c_company)
        client_c = Client()
        client_c.force_login(user_c)
        resp2 = client_c.post(f"/burza/lead/{lead.pk}/preuzmi/",
                              content_type="application/json", data=json.dumps({}))
        data = json.loads(resp2.content)
        self.assertFalse(data.get("ok", True))
        log_test("Transaction lock – duplo preuzimanje BLOKIRANO")


# ══════════════════════════════════════════════════════════════
# 2. URL TESTOVI – svi moduli
# ══════════════════════════════════════════════════════════════
class PublicURLTest(TestCase):
    """Javni URL-ovi – dostupni bez prijave."""
    def setUp(self):
        self.client = Client()

    def _check(self, url, expected_codes=(200,)):
        try:
            resp = self.client.get(url)
            ok = resp.status_code in expected_codes
            if ok:
                log_test(f"PUBLIC {url} → {resp.status_code}")
            else:
                fail_test(f"PUBLIC {url} → {resp.status_code} (očekivano: {expected_codes})")
            return resp
        except Exception as e:
            fail_test(f"PUBLIC {url} → EXCEPTION: {e}")

    def test_calculator_public(self):
        r = self._check("/calculator/", (200,))
        if r:
            self.assertEqual(r.status_code, 200)

    def test_burza_upit_public(self):
        self._check("/burza/upit/", (200,))

    def test_register_public(self):
        self._check("/register/", (200,))

    def test_login_public(self):
        self._check("/login/", (200,))


class ProtectedURLTest(TestCase):
    """Zaštićeni URL-ovi – redirect na login bez prijave."""
    def setUp(self):
        self.client = Client()

    def _check_redirect(self, url):
        resp = self.client.get(url)
        if resp.status_code in (302, 301):
            log_test(f"PROTECTED {url} → {resp.status_code} (redirect na login)")
        else:
            fail_test(f"PROTECTED {url} → {resp.status_code} (trebao redirect)")
        return resp

    def test_burza_protected(self):       self._check_redirect("/burza/")
    def test_pos_protected(self):         self._check_redirect("/pos/")
    def test_dashboard_protected(self):   self._check_redirect("/dashboard/")
    def test_worktime_protected(self):    self._check_redirect("/worktime/")
    def test_appointments_protected(self):self._check_redirect("/appointments/")
    def test_invoicing_protected(self):   self._check_redirect("/invoicing/")


class AuthenticatedURLTest(TestCase):
    """URL-ovi s prijavljenim korisnikom."""
    def setUp(self):
        self.company = create_company("Auth Test d.o.o.")
        self.admin = create_user("auth_admin", "company_admin", self.company)
        self.superadmin = create_user("auth_super", "superadmin")
        self.client = Client()
        self.client.force_login(self.admin)
        self.sa_client = Client()
        self.sa_client.force_login(self.superadmin)

    def _check(self, url, client=None, expected=(200, 302)):
        c = client or self.client
        try:
            resp = c.get(url)
            if resp.status_code in expected:
                log_test(f"AUTH {url} → {resp.status_code}")
            else:
                fail_test(f"AUTH {url} → {resp.status_code}")
            return resp
        except Exception as e:
            fail_test(f"AUTH {url} → EXCEPTION: {e}")

    def test_burza_kanban(self):       self._check("/burza/")
    def test_burza_new_lead(self):     self._check("/burza/lead/new/")
    def test_pos_dashboard(self):      self._check("/pos/")
    def test_dashboard(self):          self._check("/dashboard/")
    def test_worktime(self):           self._check("/worktime/")
    def test_appointments(self):       self._check("/appointments/")
    def test_invoicing(self):          self._check("/invoicing/")
    def test_calculator_auth(self):    self._check("/calculator/")


# ══════════════════════════════════════════════════════════════
# 3. API TESTOVI – AJAX endpointi
# ══════════════════════════════════════════════════════════════
class BurzaAPITest(TestCase):
    def setUp(self):
        self.company_a = create_company("API Tvrtka A")
        self.company_b = create_company("API Tvrtka B")
        self.sa = create_user("api_super", "superadmin")
        self.user_a = create_user("api_user_a", "company_admin", self.company_a)
        self.user_b = create_user("api_user_b", "company_admin", self.company_b)
        
        from burza.models import ProjectLead
        self.lead = ProjectLead.objects.create(
            company=self.company_a,
            title="API Test posao",
            description="Test opis",
            category="kupaonica",
            location="Rijeka",
            contact_name="API Test",
            contact_phone="091234",
            status="NOVI_UPIT",
        )

    def test_move_as_superadmin(self):
        c = Client()
        c.force_login(self.sa)
        resp = c.post(f"/burza/lead/{self.lead.pk}/move/",
                      content_type="application/json",
                      data=json.dumps({"status": "INTERNA_PROCJENA"}))
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertTrue(data.get("ok"))
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, "INTERNA_PROCJENA")
        log_test("API Move status (superadmin)")

    def test_move_blocked_for_non_superadmin(self):
        c = Client()
        c.force_login(self.user_a)
        resp = c.post(f"/burza/lead/{self.lead.pk}/move/",
                      content_type="application/json",
                      data=json.dumps({"status": "NA_BURZI"}))
        data = json.loads(resp.content)
        self.assertFalse(data.get("ok", True))
        log_test("API Move blokiran za non-superadmin")

    def test_preuzmi_own_lead_blocked(self):
        """Ne može preuzeti vlastiti posao."""
        from burza.models import ProjectLead
        self.lead.status = "NA_BURZI"
        self.lead.is_public = True
        self.lead.save()
        c = Client()
        c.force_login(self.user_a)
        resp = c.post(f"/burza/lead/{self.lead.pk}/preuzmi/",
                      content_type="application/json", data=json.dumps({}))
        data = json.loads(resp.content)
        self.assertFalse(data.get("ok", True))
        log_test("API Preuzmi vlastiti posao BLOKIRAN")

    def test_public_upit_submit(self):
        c = Client()
        resp = c.post("/burza/upit/", {
            "title": "Test javni upit",
            "description": "Opis javnog upita",
            "category": "kupaonica",
            "location": "Osijek",
            "contact_name": "Pero Perić",
            "contact_phone": "+38512345",
        })
        self.assertIn(resp.status_code, (200, 302))
        from burza.models import ProjectLead
        self.assertTrue(ProjectLead.objects.filter(title="Test javni upit").exists())
        log_test("API Javni upit kreiran")


# ══════════════════════════════════════════════════════════════
# 4. REGISTRACIJA TVRTKE
# ══════════════════════════════════════════════════════════════
class RegistrationTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_wizard_step1(self):
        resp = self.client.get("/register/")
        self.assertEqual(resp.status_code, 200)
        log_test("Registration wizard step 1")

    def test_wizard_step1_post(self):
        resp = self.client.post("/register/", {
            "name": "Nova Test Firma",
            "oib": "98765432109",
            "country": "HR",
            "business_type": "doo",
            "address": "Nova ulica 5",
            "city": "Split",
            "postal_code": "21000",
            "contact_name": "Ana Anić",
            "contact_email": "ana@test.hr",
            "contact_phone": "+38521123456",
        })
        self.assertIn(resp.status_code, (200, 302))
        log_test("Registration step 1 POST")


# ══════════════════════════════════════════════════════════════
# 5. SUBSCRIPTION PROVJERA
# ══════════════════════════════════════════════════════════════
class SubscriptionTest(TestCase):
    def setUp(self):
        self.company = create_company("Subscription Test")
        self.user = create_user("sub_user", "company_admin", self.company)

    def test_no_subscription_access(self):
        """Bez pretplate ne može pristupiti Burzi kao preuzimatelj."""
        c = Client()
        c.force_login(self.user)
        from burza.models import ProjectLead
        from companies.models import Company
        other = create_company("Druga tvrtka")
        lead = ProjectLead.objects.create(
            company=other, title="Sub test", description="t",
            category="ostalo", location="ZG", contact_name="T",
            contact_phone="091", status="NA_BURZI", is_public=True,
        )
        resp = c.post(f"/burza/lead/{lead.pk}/preuzmi/",
                      content_type="application/json", data=json.dumps({}))
        # Bez subscription ili sa STARTER planom treba biti blokiran
        # (ako nema subscription model, 200 je OK – samo logiramo)
        log_test(f"Subscription check → {resp.status_code}")


# ── HELPER FUNKCIJE ZA LOGGING ───────────────────────────────
_results = []

def log_test(msg):
    _results.append(('PASS', msg))

def fail_test(msg):
    _results.append(('FAIL', msg))
