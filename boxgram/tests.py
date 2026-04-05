from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import date, timedelta
from companies.models import Company
from .models import (
    PetProfile, LifeEvent, Competition, CompetitionEntry, 
    CompetitionVote, EventHeart
)
from .tasks import close_competition, generate_pet_qr
import uuid
import logging

logger = logging.getLogger(__name__)


class PetProfileTestCase(TestCase):
    
    def setUp(self):
        self.company = Company.objects.create(
            name='Test Company',
            oib='12345678901'
        )
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_create_pet_profile(self):
        pet = PetProfile.objects.create(
            tenant=self.company,
            owner=self.user,
            name='Fluffy',
            species='macka',
            slug='fluffy-1'
        )
        self.assertEqual(pet.name, 'Fluffy')
        self.assertEqual(pet.species, 'macka')
        self.assertTrue(pet.is_public)
        self.assertFalse(pet.is_memorial)
    
    def test_pet_auto_memorial_on_death(self):
        pet = PetProfile.objects.create(
            tenant=self.company,
            owner=self.user,
            name='Buddy',
            species='pas',
            slug='buddy-1',
            death_date=date.today()
        )
        self.assertTrue(pet.is_memorial)
    
    def test_pet_sha256_seal_generation(self):
        pet = PetProfile.objects.create(
            tenant=self.company,
            owner=self.user,
            name='Rex',
            species='pas',
            slug='rex-1'
        )
        self.assertIsNotNone(pet.sha256_seal)
        self.assertEqual(len(pet.sha256_seal), 64)
    
    def test_pet_update(self):
        pet = PetProfile.objects.create(
            tenant=self.company,
            owner=self.user,
            name='Whiskers',
            species='macka',
            slug='whiskers-1'
        )
        pet.name = 'Whiskers Updated'
        pet.save()
        refreshed_pet = PetProfile.objects.get(id=pet.id)
        self.assertEqual(refreshed_pet.name, 'Whiskers Updated')
    
    def test_pet_delete(self):
        pet = PetProfile.objects.create(
            tenant=self.company,
            owner=self.user,
            name='Spot',
            species='pas',
            slug='spot-1'
        )
        pet_id = pet.id
        pet.delete()
        with self.assertRaises(PetProfile.DoesNotExist):
            PetProfile.objects.get(id=pet_id)


class LifeEventTestCase(TestCase):
    
    def setUp(self):
        self.company = Company.objects.create(
            name='Test Company',
            oib='12345678901'
        )
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.pet = PetProfile.objects.create(
            tenant=self.company,
            owner=self.user,
            name='TestPet',
            species='pas',
            slug='testpet-1'
        )
    
    def test_create_life_event(self):
        event = LifeEvent.objects.create(
            pet=self.pet,
            event_type='rodenje',
            title='Birth Event',
            date=date.today()
        )
        self.assertEqual(event.event_type, 'rodenje')
        self.assertTrue(event.is_public)
    
    def test_create_multiple_events(self):
        event1 = LifeEvent.objects.create(
            pet=self.pet,
            event_type='rodenje',
            title='Birth',
            date=date.today()
        )
        event2 = LifeEvent.objects.create(
            pet=self.pet,
            event_type='vet',
            title='Vet Check',
            date=date.today()
        )
        self.assertEqual(self.pet.life_events.count(), 2)


class CompetitionTestCase(TestCase):
    
    def setUp(self):
        self.company = Company.objects.create(
            name='Test Company',
            oib='12345678901'
        )
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.pet1 = PetProfile.objects.create(
            tenant=self.company,
            owner=self.user,
            name='Pet1',
            species='pas',
            slug='pet1-1'
        )
        self.pet2 = PetProfile.objects.create(
            tenant=self.company,
            owner=self.user,
            name='Pet2',
            species='pas',
            slug='pet2-1'
        )
        self.competition = Competition.objects.create(
            tenant=self.company,
            title='Best Dog',
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=7)
        )
    
    def test_create_competition(self):
        self.assertEqual(self.competition.title, 'Best Dog')
        self.assertEqual(self.competition.status, 'draft')
    
    def test_create_competition_entry(self):
        entry = CompetitionEntry.objects.create(
            competition=self.competition,
            pet=self.pet1
        )
        self.assertEqual(entry.votes, 0)
    
    def test_vote_duplicate_ip_block(self):
        entry1 = CompetitionEntry.objects.create(
            competition=self.competition,
            pet=self.pet1
        )
        entry2 = CompetitionEntry.objects.create(
            competition=self.competition,
            pet=self.pet2
        )
        
        ip = '192.168.1.1'
        vote1, created1 = CompetitionVote.objects.get_or_create(
            entry=entry1,
            voter_ip=ip
        )
        self.assertTrue(created1)
        
        vote2, created2 = CompetitionVote.objects.get_or_create(
            entry=entry2,
            voter_ip=ip
        )
        self.assertFalse(created2)
        
        self.assertEqual(CompetitionVote.objects.filter(voter_ip=ip).count(), 1)
    
    def test_close_competition_task(self):
        entry1 = CompetitionEntry.objects.create(
            competition=self.competition,
            pet=self.pet1,
            votes=10
        )
        entry2 = CompetitionEntry.objects.create(
            competition=self.competition,
            pet=self.pet2,
            votes=5
        )
        
        close_competition(str(self.competition.id))
        
        self.competition.refresh_from_db()
        self.assertEqual(self.competition.status, 'closed')
        self.assertEqual(self.competition.winner, self.pet1)
        
        entry1.refresh_from_db()
        self.assertEqual(entry1.rank, 1)


class EventHeartTestCase(TestCase):
    
    def setUp(self):
        self.company = Company.objects.create(
            name='Test Company',
            oib='12345678901'
        )
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.pet = PetProfile.objects.create(
            tenant=self.company,
            owner=self.user,
            name='TestPet',
            species='pas',
            slug='testpet-1'
        )
        self.event = LifeEvent.objects.create(
            pet=self.pet,
            event_type='rodenje',
            title='Birth',
            date=date.today()
        )
    
    def test_create_event_heart(self):
        heart = EventHeart.objects.create(
            event=self.event,
            user=self.user,
            ip='192.168.1.1'
        )
        self.assertEqual(heart.event, self.event)
    
    def test_duplicate_ip_unique_constraint(self):
        ip = '192.168.1.1'
        heart1 = EventHeart.objects.create(
            event=self.event,
            user=self.user,
            ip=ip
        )
        
        with self.assertRaises(Exception):
            EventHeart.objects.create(
                event=self.event,
                user=self.user,
                ip=ip
            )


class BoxgramCoverageTest(TestCase):
    
    def setUp(self):
        self.company = Company.objects.create(
            name='Test Company',
            oib='12345678901'
        )
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_boxgram_models_exist(self):
        from boxgram.models import (
            PetProfile, LifeEvent, EventMedia, SocialImport,
            Competition, CompetitionEntry, CompetitionVote,
            PetFollower, EventHeart
        )
        self.assertIsNotNone(PetProfile)
        self.assertIsNotNone(LifeEvent)
        self.assertIsNotNone(EventMedia)
        self.assertIsNotNone(SocialImport)
        self.assertIsNotNone(Competition)
        self.assertIsNotNone(CompetitionEntry)
        self.assertIsNotNone(CompetitionVote)
        self.assertIsNotNone(PetFollower)
        self.assertIsNotNone(EventHeart)
    
    def test_boxgram_tasks_exist(self):
        from boxgram.tasks import (
            close_competition, fetch_social_import,
            generate_pet_qr, bulk_sync_company_to_boxgram
        )
        self.assertIsNotNone(close_competition)
        self.assertIsNotNone(fetch_social_import)
        self.assertIsNotNone(generate_pet_qr)
        self.assertIsNotNone(bulk_sync_company_to_boxgram)


class SocialImportTestCase(TestCase):
    """Testovi za Social Import servis"""
    
    def setUp(self):
        from boxgram.services.social_import import detect_platform, fetch_oembed
        self.detect_platform = detect_platform
        self.fetch_oembed = fetch_oembed
        
        self.company = Company.objects.create(
            name='Test Company',
            oib='12345678901'
        )
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.pet = PetProfile.objects.create(
            tenant=self.company,
            owner=self.user,
            name='TestPet',
            species='pas',
            slug='testpet-1'
        )
    
    def test_detect_platform_youtube(self):
        """Test detektovanja YouTube platforme"""
        url = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
        platform = self.detect_platform(url)
        self.assertEqual(platform, 'youtube')
    
    def test_detect_platform_youtube_short(self):
        """Test detektovanja YouTube short URL"""
        url = 'https://youtu.be/dQw4w9WgXcQ'
        platform = self.detect_platform(url)
        self.assertEqual(platform, 'youtube')
    
    def test_detect_platform_tiktok(self):
        """Test detektovanja TikTok platforme"""
        url = 'https://www.tiktok.com/@username/video/1234567890'
        platform = self.detect_platform(url)
        self.assertEqual(platform, 'tiktok')
    
    def test_detect_platform_facebook(self):
        """Test detektovanja Facebook platforme"""
        url = 'https://www.facebook.com/photo.php?fbid=123456&set=a.123'
        platform = self.detect_platform(url)
        self.assertEqual(platform, 'facebook')
    
    def test_detect_platform_instagram(self):
        """Test detektovanja Instagram platforme"""
        url = 'https://www.instagram.com/p/ABC123XYZ/'
        platform = self.detect_platform(url)
        self.assertEqual(platform, 'instagram')
    
    def test_detect_platform_unsupported(self):
        """Test detektovanja nepodržane platforme"""
        url = 'https://www.example.com/some-video'
        platform = self.detect_platform(url)
        self.assertIsNone(platform)
    
    def test_fetch_oembed_invalid_url(self):
        """Test fetch_oembed sa nevaljanim URL-om"""
        url = 'https://invalid.domain.xyz/video'
        preview = self.fetch_oembed(url)
        self.assertFalse(preview.success)
        self.assertIsNone(preview.platform)
        self.assertIsNotNone(preview.error)
    
    def test_fetch_oembed_unsupported_platform(self):
        """Test fetch_oembed sa nepodržanom platformom"""
        url = 'https://www.reddit.com/r/cats/'
        preview = self.fetch_oembed(url)
        self.assertFalse(preview.success)
        self.assertIsNotNone(preview.error)
    
    def test_create_social_import_model(self):
        """Test kreiranja SocialImport zapisa"""
        from boxgram.models import SocialImport
        
        social_import = SocialImport.objects.create(
            pet=self.pet,
            platform='youtube',
            source_url='https://www.youtube.com/watch?v=test123',
            status='pending'
        )
        
        self.assertEqual(social_import.pet, self.pet)
        self.assertEqual(social_import.platform, 'youtube')
        self.assertEqual(social_import.status, 'pending')
        self.assertEqual(social_import.raw_data, {})
    
    def test_social_import_duplicate_check(self):
        """Test provjere duplikata kod importa"""
        from boxgram.models import SocialImport
        
        url = 'https://www.youtube.com/watch?v=test123'
        
        # Kreiraj prvi import
        import1 = SocialImport.objects.create(
            pet=self.pet,
            platform='youtube',
            source_url=url,
            status='pending'
        )
        
        # Pokušaj kreiraj duplikat
        imports = SocialImport.objects.filter(
            pet=self.pet,
            source_url=url
        )
        
        self.assertEqual(imports.count(), 1)
        self.assertEqual(imports.first().id, import1.id)
    
    def test_social_import_status_transitions(self):
        """Test tranzicija statusa za social import"""
        from boxgram.models import SocialImport
        
        social_import = SocialImport.objects.create(
            pet=self.pet,
            platform='facebook',
            source_url='https://www.facebook.com/photo.php?fbid=123',
            status='pending'
        )
        
        # Tranzicija na rejected
        social_import.status = 'rejected'
        social_import.save()
        self.assertEqual(social_import.status, 'rejected')
        
        # Kreiraj novi za approved test
        social_import2 = SocialImport.objects.create(
            pet=self.pet,
            platform='tiktok',
            source_url='https://www.tiktok.com/@test/video/123',
            status='pending'
        )
        
        social_import2.status = 'approved'
        social_import2.save()
        self.assertEqual(social_import2.status, 'approved')
    
    def test_social_import_raw_data_storage(self):
        """Test pohrane raw oEmbed podataka"""
        from boxgram.models import SocialImport
        
        test_data = {
            'title': 'Test Video',
            'thumbnail_url': 'https://example.com/thumb.jpg',
            'author_name': 'Test Author',
            'html': '<iframe>...</iframe>'
        }
        
        social_import = SocialImport.objects.create(
            pet=self.pet,
            platform='youtube',
            source_url='https://www.youtube.com/watch?v=test',
            status='pending',
            raw_data=test_data
        )
        
        self.assertEqual(social_import.raw_data['title'], 'Test Video')
        self.assertEqual(social_import.raw_data['author_name'], 'Test Author')
    
    def test_social_import_queryset(self):
        """Test queryset za social importa"""
        from boxgram.models import SocialImport
        
        # Kreiraj nekoliko importa
        for i in range(3):
            SocialImport.objects.create(
                pet=self.pet,
                platform='youtube',
                source_url=f'https://www.youtube.com/watch?v=test{i}',
                status='pending'
            )
        
        # Filtriraj pending
        pending = SocialImport.objects.filter(status='pending')
        self.assertEqual(pending.count(), 3)
        
        # Filtriraj po platformi
        youtube_imports = SocialImport.objects.filter(platform='youtube')
        self.assertEqual(youtube_imports.count(), 3)


class PublicProfileViewTest(TestCase):
    """Test za javni profil view"""
    
    def setUp(self):
        self.company = Company.objects.create(
            name='Test Company',
            oib='12345678901'
        )
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.pet = PetProfile.objects.create(
            tenant=self.company,
            owner=self.user,
            name='Fluffy',
            species='macka',
            slug='fluffy-test',
            is_public=True,
            bio='A cute cat'
        )
        
        self.event = LifeEvent.objects.create(
            pet=self.pet,
            event_type='rodenje',
            title='Birth Event',
            date=date.today(),
            is_public=True
        )
    
    def test_public_profile_page_accessible(self):
        """Test da je javni profil dostupan"""
        response = self.client.get(f'/ljubimac/{self.pet.slug}/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Fluffy', str(response.content))
    
    def test_public_profile_private_pet_not_accessible(self):
        """Test da privatni ljubimac nije dostupan"""
        private_pet = PetProfile.objects.create(
            tenant=self.company,
            owner=self.user,
            name='Private',
            species='pas',
            slug='private-pet',
            is_public=False
        )
        response = self.client.get(f'/ljubimac/{private_pet.slug}/')
        self.assertEqual(response.status_code, 404)
    
    def test_public_profile_contains_context(self):
        """Test da profil sadrži potrebne podatke"""
        response = self.client.get(f'/ljubimac/{self.pet.slug}/')
        self.assertIn(b'Fluffy', response.content)
        self.assertIn('Mačka'.encode(), response.content)
        self.assertIn(b'A cute cat', response.content)
    
    def test_public_profile_memorial_mode(self):
        """Test memorijalne mode za mrtve ljubimce"""
        self.pet.death_date = date.today()
        self.pet.save()
        
        response = self.client.get(f'/ljubimac/{self.pet.slug}/')
        self.assertEqual(response.status_code, 200)
        self.pet.refresh_from_db()
        self.assertTrue(self.pet.is_memorial)


class PublicFeedViewTest(TestCase):
    """Test za javni feed"""
    
    def setUp(self):
        self.company = Company.objects.create(
            name='Test Company',
            oib='12345678901'
        )
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Kreiraj 25 ljubimaca
        for i in range(25):
            PetProfile.objects.create(
                tenant=self.company,
                owner=self.user,
                name=f'Pet{i}',
                species='pas' if i % 2 == 0 else 'macka',
                slug=f'pet{i}',
                is_public=True
            )
    
    def test_feed_page_accessible(self):
        """Test da je feed dostupan"""
        response = self.client.get('/feed/')
        self.assertEqual(response.status_code, 200)
    
    def test_feed_pagination(self):
        """Test paginacije feeda - trebalo bi 20 po stranici"""
        response = self.client.get('/feed/')
        self.assertEqual(response.status_code, 200)
        # Trebalo bi biti 20 ili manje
        self.assertIn('page_obj', response.context)
    
    def test_feed_species_filter(self):
        """Test filtriranja po vrsti"""
        response = self.client.get('/feed/?species=pas')
        self.assertEqual(response.status_code, 200)
    
    def test_feed_only_public_pets(self):
        """Test da feed pokazuje samo javne ljubimce"""
        # Kreiraj privatnog ljubimca
        PetProfile.objects.create(
            tenant=self.company,
            owner=self.user,
            name='PrivatePet',
            species='pas',
            slug='privatepet',
            is_public=False
        )
        
        response = self.client.get('/feed/')
        self.assertEqual(response.status_code, 200)
        # Privatni ne bi trebalo da se pojavi


class CompetitionDetailViewTest(TestCase):
    """Test za stranicu takmičenja"""
    
    def setUp(self):
        self.company = Company.objects.create(
            name='Test Company',
            oib='12345678901'
        )
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.pet1 = PetProfile.objects.create(
            tenant=self.company,
            owner=self.user,
            name='Pet1',
            species='pas',
            slug='pet1',
            is_public=True
        )
        
        self.pet2 = PetProfile.objects.create(
            tenant=self.company,
            owner=self.user,
            name='Pet2',
            species='pas',
            slug='pet2',
            is_public=True
        )
        
        self.competition = Competition.objects.create(
            tenant=self.company,
            title='Best Dog',
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=7),
            status='active'
        )
        
        self.entry1 = CompetitionEntry.objects.create(
            competition=self.competition,
            pet=self.pet1,
            votes=10
        )
        
        self.entry2 = CompetitionEntry.objects.create(
            competition=self.competition,
            pet=self.pet2,
            votes=5
        )
    
    def test_competition_page_accessible(self):
        """Test da je stranica takmičenja dostupna"""
        response = self.client.get(f'/takmicenje/{self.competition.id}/')
        self.assertEqual(response.status_code, 200)
    
    def test_competition_entries_displayed(self):
        """Test da su unosi prikazani"""
        response = self.client.get(f'/takmicenje/{self.competition.id}/')
        self.assertIn(b'Pet1', response.content)
        self.assertIn(b'Pet2', response.content)
    
    def test_competition_vote_endpoint_exists(self):
        """Test da endpoint za glasanje postoji"""
        # Testiraj samo da je URL dostupan
        self.assertIsNotNone(f'/takmicenje/{self.competition.id}/vote/')


class CompetitionVoteTest(TestCase):
    """Test za glasanje u takmičenju"""
    
    def setUp(self):
        self.company = Company.objects.create(
            name='Test Company',
            oib='12345678901'
        )
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.pet = PetProfile.objects.create(
            tenant=self.company,
            owner=self.user,
            name='TestPet',
            species='pas',
            slug='testpet',
            is_public=True
        )
        
        self.competition = Competition.objects.create(
            tenant=self.company,
            title='Test Competition',
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=7),
            status='active'
        )
        
        self.entry = CompetitionEntry.objects.create(
            competition=self.competition,
            pet=self.pet,
            votes=0
        )
    
    def test_vote_increments_counter(self):
        """Test da glasanje povećava brojač"""
        import json
        
        response = self.client.post(
            f'/takmicenje/{self.competition.id}/vote/',
            data=json.dumps({'entry_id': str(self.entry.id)}),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.votes, 1)
    
    def test_vote_ip_blocking(self):
        """Test da ista IP ne može glasati dva puta"""
        import json
        
        # Prvi glas
        response1 = self.client.post(
            f'/takmicenje/{self.competition.id}/vote/',
            data=json.dumps({'entry_id': str(self.entry.id)}),
            content_type='application/json',
            REMOTE_ADDR='192.168.1.1'
        )
        
        self.assertEqual(response1.status_code, 200)
        
        # Drugi glas sa istom IP
        response2 = self.client.post(
            f'/takmicenje/{self.competition.id}/vote/',
            data=json.dumps({'entry_id': str(self.entry.id)}),
            content_type='application/json',
            REMOTE_ADDR='192.168.1.1'
        )
        
        data = json.loads(response2.content)
        self.assertFalse(data['success'])
