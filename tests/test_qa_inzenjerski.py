"""
QA Inžinjerski testovi — 07.04.2026.
Blokovi A, B, C, D, E, F iz CC_TASK_QA_INZENJERSKI.md
"""

from django.test import Client, TestCase

# ════════════════════════════════════════════════════════════════
# BLOK A — memio.pet REGISTRACIJA
# ════════════════════════════════════════════════════════════════


class RegistracijaTest(TestCase):
    databases = ["default", "memio_pets"]

    def setUp(self):
        self.client = Client(SERVER_NAME="memio.pet")

    def test_a1_get_registracija(self):
        """A1: Forma se prikazuje."""
        r = self.client.get("/registracija/")
        self.assertEqual(r.status_code, 200)

    def test_a2_post_kreira_profil(self):
        """A2: POST kreira BreederProfile i redirecta."""
        from memio_pet.models import BreederProfile

        r = self.client.post(
            "/registracija/",
            {
                "ime": "Ljubeta Test",
                "email": "ljubeta_qa@test.hr",
                "grad": "Zagreb",
                "account_type": "breeder",
            },
        )
        self.assertEqual(r.status_code, 302)
        bp = BreederProfile.objects.using("memio_pets").filter(email="ljubeta_qa@test.hr").first()
        self.assertIsNotNone(bp)
        self.assertEqual(bp.name, "Ljubeta Test")

    def test_a3_duplicate_email_no_500(self):
        """A3: Dupli email ne izaziva 500."""
        from memio_pet.models import BreederProfile

        BreederProfile.objects.using("memio_pets").create(name="Stari", email="isti_qa@test.hr", account_type="owner")
        r = self.client.post(
            "/registracija/",
            {
                "ime": "Novi",
                "email": "isti_qa@test.hr",
                "grad": "Split",
                "account_type": "owner",
            },
        )
        self.assertEqual(r.status_code, 302)

    def test_a4_bez_emaila(self):
        """A4: Prazno email ne izaziva crash."""
        r = self.client.post("/registracija/", {"ime": "Test"})
        self.assertIn(r.status_code, [200, 302])


# ════════════════════════════════════════════════════════════════
# BLOK B — BOXGRAM + Profil edge cases
# ════════════════════════════════════════════════════════════════


class ProfilEdgeCaseTest(TestCase):
    databases = ["default", "memio_pets"]

    def setUp(self):
        self.client = Client(SERVER_NAME="memio.pet")

    def test_b1_profil_bez_cipa_koristi_ear_tag(self):
        """B1: Životinja bez chipa radi s ear_tag."""
        from memio_pet.models import AnimalProfile

        AnimalProfile.objects.using("memio_pets").create(
            name="Ovca QA", vrsta="ovca", ear_tag="HR-QA-2024", breeder_name_snapshot="OPG Test"
        )
        r = self.client.get("/pas/HR-QA-2024/")
        self.assertEqual(r.status_code, 200)

    def test_b2_nepostojeci_chip_404(self):
        """B2: Nepostojeći chip/tag vraća 404, ne 500."""
        r = self.client.get("/pas/NIKADNIJEPOSTOJAO_QA/")
        self.assertEqual(r.status_code, 404)


# ════════════════════════════════════════════════════════════════
# BLOK C — TRIKEY (sigurnosna logika)
# ════════════════════════════════════════════════════════════════


class TriKeyTest(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User

        from accounts.trikey import TriKeyProfile

        self.user = User.objects.create_user("qa_trikey", "tk_qa@test.hr", "old_pw")
        self.profile = TriKeyProfile.objects.create(user=self.user)

    def test_c1_pin_mora_6_znamenki(self):
        """C1: PIN kraći/duži od 6 → ValueError."""
        with self.assertRaises(ValueError):
            self.profile.set_pin("123")
        with self.assertRaises(ValueError):
            self.profile.set_pin("12345678")
        with self.assertRaises(ValueError):
            self.profile.set_pin("abcdef")

    def test_c2_ispravan_pin(self):
        """C2: Ispravan PIN radi, pogrešan ne radi."""
        self.profile.set_pin("847291")
        self.assertTrue(self.profile.verify_pin("847291"))
        self.assertFalse(self.profile.verify_pin("000000"))

    def test_c3_lockout_5_pokusaja(self):
        """C3: Nakon 5 krivih pokušaja → lockout."""
        self.profile.set_pin("847291")
        for _ in range(5):
            self.profile.verify_pin("000000")
        self.profile.refresh_from_db()
        self.assertIsNotNone(self.profile.pin_locked_until)
        with self.assertRaises(PermissionError):
            self.profile.verify_pin("847291")

    def test_c4_350_profila(self):
        """C4: Minimalno 350 TriKeyProfile u bazi."""
        from accounts.trikey import TriKeyProfile

        # +1 za ovaj test setUp
        self.assertGreaterEqual(TriKeyProfile.objects.count(), 350)


# ════════════════════════════════════════════════════════════════
# BLOK D — POS FISKALIZACIJA (integritet)
# ════════════════════════════════════════════════════════════════


class FiskalizacijaTest(TestCase):
    def test_d1_nema_jir_bez_zki(self):
        """D1: Nijedan bon nema JIR bez ZKI."""
        from pos.models import POSReceipt

        invalid = POSReceipt.objects.filter(jir__isnull=False).exclude(zki__isnull=False).exclude(zki="")
        self.assertEqual(invalid.count(), 0, f"{invalid.count()} bonova ima JIR bez ZKI!")


# ════════════════════════════════════════════════════════════════
# BLOK E — memio.world (integritet modela)
# ════════════════════════════════════════════════════════════════


class MemioWorldTest(TestCase):
    databases = ["default", "memio_world"]

    def test_e1_waitlist_api(self):
        """E1: POST na waitlist API sprema email."""
        import json

        r = self.client.post(
            "/api/memio-world/waitlist/",
            data=json.dumps({"email": "qa_test@memio.world", "name": "QA Test"}),
            content_type="application/json",
        )
        self.assertIn(r.status_code, [200, 201])

    def test_e2_waitlist_dupli_ne_500(self):
        """E2: Dupli email ne izaziva 500."""
        import json

        data = json.dumps({"email": "dupli_qa@memio.world"})
        self.client.post("/api/memio-world/waitlist/", data=data, content_type="application/json")
        r = self.client.post("/api/memio-world/waitlist/", data=data, content_type="application/json")
        self.assertNotEqual(r.status_code, 500)


# ════════════════════════════════════════════════════════════════
# BLOK F — NO LIMIT AZIL (end-to-end)
# ════════════════════════════════════════════════════════════════


class AzilTest(TestCase):
    def test_f1_azil_landing(self):
        """F1: Azil landing page radi."""
        r = self.client.get("/no-limit/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "azil", msg_prefix='Landing ne sadrži "azil"')
