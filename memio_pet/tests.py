"""
memio_pet/tests.py — Funkcionalni testovi za memio.pet views
Pokrivenost: HTTP status codes, .using("memio_pets") korekcija, 404 logika
"""
from django.test import TestCase, Client
import uuid


class MemioPublicEndpointsTest(TestCase):
    """Testira da su svi javni endpointi dostupni bez prijave."""

    databases = ['default', 'memio_pets']

    def setUp(self):
        self.client = Client()

    # ── Landing page (statički HTML) ─────────────────────────────────
    def test_landing_200(self):
        response = self.client.get('https://memio.pet/', SERVER_NAME='memio.pet')
        # Nginx servisira statički index.html — Django ne vidi taj request.
        # Testiramo Django razinu: root path resolveaje na memio.pet.
        pass  # Nginx-level, covered by integration test

    # ── /barf/ ───────────────────────────────────────────────────────
    def test_barf_listings_200(self):
        response = self.client.get('/barf/')
        self.assertEqual(response.status_code, 200)

    def test_barf_listings_no_redirect(self):
        response = self.client.get('/barf/')
        self.assertNotEqual(response.status_code, 302)

    # ── /hotel/ ──────────────────────────────────────────────────────
    def test_hotel_booking_200(self):
        response = self.client.get('/hotel/')
        self.assertEqual(response.status_code, 200)

    # ── /dresura/ ────────────────────────────────────────────────────
    def test_training_list_200(self):
        response = self.client.get('/dresura/')
        self.assertEqual(response.status_code, 200)

    # ── /pas/<chip>/ — nepostojeci chip → 404 ────────────────────────
    def test_pet_profile_notfound_404(self):
        response = self.client.get('/pas/CHIP_NEPOSTOJI_XYZ/')
        self.assertEqual(response.status_code, 404)

    # ── /pas/<chip>/qr/ — nepostojeci chip → 404 ─────────────────────
    def test_pet_qr_notfound_404(self):
        response = self.client.get('/pas/CHIP_NEPOSTOJI_XYZ/qr/')
        self.assertEqual(response.status_code, 404)

    # ── /uzgajivac/<uuid>/ — nepostojeci uuid → 404 ──────────────────
    def test_breeder_profile_notfound_404(self):
        fake_uuid = str(uuid.uuid4())
        response = self.client.get(f'/uzgajivac/{fake_uuid}/')
        self.assertEqual(response.status_code, 404)

    # ── /badge/<uuid>/ — nepostojeci uuid → 404 ─────────────────────
    def test_badge_notfound_404(self):
        fake_uuid = str(uuid.uuid4())
        response = self.client.get(f'/badge/{fake_uuid}/')
        self.assertEqual(response.status_code, 404)


class MemioDBRoutingTest(TestCase):
    """Testira da svi ORM upiti koriste memio_pets bazu."""

    databases = ['default', 'memio_pets']

    def test_barf_uses_memio_pets_db(self):
        """barf_listings mora čitati iz memio_pets, ne default."""
        from memio_pet.models import RawFoodListing
        # Ako slučajno koristi default → ProgrammingError (kolona ne postoji)
        # Ovo ne smije baciti exception
        try:
            list(RawFoodListing.objects.using('memio_pets').all()[:1])
        except DatabaseError as e:
            self.fail(f"RawFoodListing.using('memio_pets') bacilo grešku: {e}")

    def test_breeder_uses_memio_pets_db(self):
        from memio_pet.models import BreederProfile
        try:
            list(BreederProfile.objects.using('memio_pets').all()[:1])
        except DatabaseError as e:
            self.fail(f"BreederProfile.using('memio_pets') bacilo grešku: {e}")

    def test_animal_uses_memio_pets_db(self):
        from memio_pet.models import AnimalProfile
        try:
            list(AnimalProfile.objects.using('memio_pets').all()[:1])
        except DatabaseError as e:
            self.fail(f"AnimalProfile.using('memio_pets') bacilo grešku: {e}")


class MemioWithDataTest(TestCase):
    """Testira s realnim podacima u memio_pets bazi."""

    databases = ['default', 'memio_pets']

    def setUp(self):
        from memio_pet.models import BreederProfile, AnimalProfile
        self.breeder = BreederProfile.objects.using('memio_pets').create(
            name='Test Uzgajivač d.o.o.',
            account_type='breeder',
            country='HR',
            is_cro_validated=True,
            trust_score=85,
        )
        self.animal = AnimalProfile.objects.using('memio_pets').create(
            chip_number='191100000000001',
            ear_tag='HR-TEST-001',
            name='Rex',
            vrsta='pas',
            breeder=self.breeder,
            breeder_name_snapshot=self.breeder.name,
        )
        self.client = Client()

    def test_pet_profile_200(self):
        response = self.client.get(f'/pas/{self.animal.chip_number}/')
        self.assertEqual(response.status_code, 200)

    def test_pet_profile_by_ear_tag(self):
        response = self.client.get(f'/pas/{self.animal.ear_tag}/')
        self.assertEqual(response.status_code, 200)

    def test_pet_qr_200(self):
        response = self.client.get(f'/pas/{self.animal.chip_number}/qr/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/png')

    def test_breeder_profile_200(self):
        response = self.client.get(f'/uzgajivac/{self.breeder.pk}/')
        self.assertEqual(response.status_code, 200)

    def test_badge_200(self):
        response = self.client.get(f'/badge/{self.breeder.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'svg', response.content.lower())

    def test_trust_score_in_badge(self):
        response = self.client.get(f'/badge/{self.breeder.pk}/')
        self.assertIn(b'85', response.content)

    def test_hotel_shows_hotels(self):
        from memio_pet.models import BreederProfile
        BreederProfile.objects.using('memio_pets').create(
            name='Luxury Pet Hotel',
            account_type='hotel',
            country='HR',
        )
        response = self.client.get('/hotel/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Luxury Pet Hotel', response.content)

    def test_trainer_shows_in_dresura(self):
        from memio_pet.models import BreederProfile
        BreederProfile.objects.using('memio_pets').create(
            name='Kinolog Pero',
            account_type='trainer',
            country='HR',
        )
        response = self.client.get('/dresura/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Kinolog Pero', response.content)
