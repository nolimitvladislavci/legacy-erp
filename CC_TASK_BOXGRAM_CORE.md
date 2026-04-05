# CC_TASK_BOXGRAM_CORE.md
# Boxgram — Digitalni život ljubimca
# Prioritet: VISOK | Ekipa: CC Code
# Datum: 05.04.2026.

## KONTEKST
Boxgram je socijalna mreža za ljubimce unutar memio.pet platforme.
Filozofija: "Preslika vanjskog života u digitalni portal — od rođenja do zauvijek."
Nije Instagram. Nije vet bilježnica. Oboje zajedno + arhiva + identitet + takmičenje.

Jezik: Hrvatski (primarni), EN/DE/SLO poslije.
Infrastruktura: Django app unutar fina-connect projekta.

---

## B1 — Nova Django app: boxgram/

```bash
cd /var/www/fina-connect
source venv/bin/activate
python manage.py startapp boxgram
```

Dodaj u INSTALLED_APPS: 'boxgram'

---

## B2 — models.py

```python
import uuid, hashlib, json
from django.db import models
from django.contrib.auth import get_user_model
from tenants.models import Tenant

User = get_user_model()

SPECIES_CHOICES = [
    ('pas', 'Pas'),
    ('macka', 'Mačka'),
    ('konj', 'Konj'),
    ('zec', 'Zec'),
    ('ptica', 'Ptica'),
    ('riba', 'Riba'),
    ('pcela', 'Pčelinja zajednica'),
    ('govedo', 'Govedo'),
    ('svinja', 'Svinja'),
    ('ovca', 'Ovca'),
    ('koza', 'Koza'),
    ('ostalo', 'Ostalo'),
]

EVENT_TYPE_CHOICES = [
    ('rodenje', 'Rođenje'),
    ('vet', 'Vet posjet'),
    ('cijepljenje', 'Cijepljenje'),
    ('natjecanje', 'Natjecanje'),
    ('nagrada', 'Nagrada'),
    ('usvajanje', 'Usvajanje'),
    ('promjena_vlasnika', 'Promjena vlasnika'),
    ('preseljenje', 'Preseljenje'),
    ('parenje', 'Parenje'),
    ('leglo', 'Leglo/Rojenje'),
    ('social_import', 'Uvezeno s društvenih mreža'),
    ('milestone', 'Prekretnica'),
    ('smrt', 'Smrt'),
    ('memorijal', 'Memorijal'),
    ('ostalo', 'Ostalo'),
]

PLATFORM_CHOICES = [
    ('facebook', 'Facebook'),
    ('instagram', 'Instagram'),
    ('tiktok', 'TikTok'),
    ('youtube', 'YouTube'),
    ('manual', 'Ručni unos'),
]


class PetProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='pets')
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='pets')

    name = models.CharField(max_length=100)
    species = models.CharField(max_length=20, choices=SPECIES_CHOICES)
    breed = models.CharField(max_length=100, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    death_date = models.DateField(null=True, blank=True)

    bio = models.TextField(blank=True)
    avatar = models.ImageField(upload_to='boxgram/avatars/', null=True, blank=True)
    cover_photo = models.ImageField(upload_to='boxgram/covers/', null=True, blank=True)

    slug = models.SlugField(max_length=120, unique=True)
    is_public = models.BooleanField(default=True)
    is_memorial = models.BooleanField(default=False)  # auto True kad death_date postavljeno

    # Identitet i verifikacija
    qr_code = models.ImageField(upload_to='boxgram/qr/', null=True, blank=True)
    sha256_seal = models.CharField(max_length=64, blank=True)
    is_verified_breeder = models.BooleanField(default=False)
    is_vet_verified = models.BooleanField(default=False)

    # Statistike
    followers_count = models.PositiveIntegerField(default=0)
    hearts_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Profil ljubimca'
        verbose_name_plural = 'Profili ljubimaca'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.get_species_display()})"

    def save(self, *args, **kwargs):
        if self.death_date:
            self.is_memorial = True
        if not self.sha256_seal:
            self.sha256_seal = self._generate_seal()
        super().save(*args, **kwargs)

    def _generate_seal(self):
        data = f"{self.id}{self.name}{self.species}{self.birth_date}"
        return hashlib.sha256(data.encode()).hexdigest()


class LifeEvent(models.Model):
    """Srce Boxgrama — svaki događaj u životu ljubimca."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pet = models.ForeignKey(PetProfile, on_delete=models.CASCADE, related_name='events')

    event_type = models.CharField(max_length=30, choices=EVENT_TYPE_CHOICES)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    date = models.DateField()
    location = models.CharField(max_length=200, blank=True)
    location_city = models.CharField(max_length=100, blank=True)

    source = models.CharField(max_length=20, choices=PLATFORM_CHOICES, default='manual')
    source_url = models.URLField(blank=True)
    source_id = models.CharField(max_length=200, blank=True)

    is_public = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='verified_events')

    hearts_count = models.PositiveIntegerField(default=0)
    comments_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Životni događaj'
        verbose_name_plural = 'Životni događaji'
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.pet.name} — {self.get_event_type_display()} ({self.date})"


class EventMedia(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(LifeEvent, on_delete=models.CASCADE, related_name='media')

    file = models.FileField(upload_to='boxgram/media/', null=True, blank=True)
    file_type = models.CharField(max_length=10, choices=[('photo','Foto'),('video','Video'),('doc','Dokument')])
    source_url = models.URLField(blank=True)
    thumbnail_url = models.URLField(blank=True)
    sha256 = models.CharField(max_length=64, blank=True)

    order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order']


class SocialImport(models.Model):
    """Uvezene objave s FB/IG/TikTok čekaju odobrenje vlasnika."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pet = models.ForeignKey(PetProfile, on_delete=models.CASCADE, related_name='imports')

    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    source_url = models.URLField()
    source_id = models.CharField(max_length=200, blank=True)
    raw_data = models.JSONField(default=dict)

    thumbnail_url = models.URLField(blank=True)
    caption = models.TextField(blank=True)
    post_date = models.DateField(null=True, blank=True)

    STATUS_CHOICES = [('pending','Na čekanju'),('approved','Prihvaćeno'),('rejected','Odbijeno')]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    mapped_to = models.OneToOneField(LifeEvent, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Uvezena objava'
        verbose_name_plural = 'Uvezene objave'


class Competition(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='competitions')

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    species_filter = models.CharField(max_length=20, choices=SPECIES_CHOICES, blank=True)

    start_date = models.DateTimeField()
    end_date = models.DateTimeField()

    STATUS_CHOICES = [('draft','Priprema'),('active','Aktivno'),('finished','Završeno')]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    winner = models.ForeignKey(PetProfile, null=True, blank=True, on_delete=models.SET_NULL, related_name='won_competitions')
    cover_image = models.ImageField(upload_to='boxgram/competitions/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Takmičenje'
        verbose_name_plural = 'Takmičenja'

    def __str__(self):
        return self.title


class CompetitionEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    competition = models.ForeignKey(Competition, on_delete=models.CASCADE, related_name='entries')
    pet = models.ForeignKey(PetProfile, on_delete=models.CASCADE, related_name='competition_entries')
    media = models.ForeignKey(EventMedia, null=True, blank=True, on_delete=models.SET_NULL)

    votes = models.PositiveIntegerField(default=0)
    rank = models.PositiveSmallIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['competition', 'pet']
        ordering = ['-votes']


class CompetitionVote(models.Model):
    entry = models.ForeignKey(CompetitionEntry, on_delete=models.CASCADE, related_name='vote_records')
    voter_ip = models.GenericIPAddressField()
    voter_user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    voted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['entry__competition', 'voter_ip']


class PetFollower(models.Model):
    pet = models.ForeignKey(PetProfile, on_delete=models.CASCADE, related_name='followers')
    follower = models.ForeignKey(User, on_delete=models.CASCADE, related_name='following_pets')
    followed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['pet', 'follower']


class EventHeart(models.Model):
    event = models.ForeignKey(LifeEvent, on_delete=models.CASCADE, related_name='hearts')
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    ip = models.GenericIPAddressField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['event', 'ip']
```

---

## B3 — Celery taskovi (tasks.py)

```python
from celery import shared_task
from django.utils import timezone
from .models import Competition, CompetitionEntry, SocialImport, PetProfile
import requests

@shared_task(queue='default')
def close_competition(competition_id):
    """Zatvori takmičenje i proglasi pobjednika."""
    try:
        comp = Competition.objects.get(id=competition_id)
        winner_entry = comp.entries.order_by('-votes').first()
        if winner_entry:
            comp.winner = winner_entry.pet
            winner_entry.rank = 1
            winner_entry.save()
        comp.status = 'finished'
        comp.save()
    except Competition.DoesNotExist:
        pass

@shared_task(queue='default')
def fetch_social_import(import_id):
    """Povuci thumbnail i meta podatke za uvezenu objavu."""
    try:
        imp = SocialImport.objects.get(id=import_id)
        # oEmbed fallback za javne URL-ove
        oembed_providers = {
            'instagram.com': 'https://graph.facebook.com/v18.0/instagram_oembed',
            'tiktok.com': 'https://www.tiktok.com/oembed',
            'facebook.com': 'https://www.facebook.com/plugins/post/oembed.json',
        }
        for domain, endpoint in oembed_providers.items():
            if domain in imp.source_url:
                try:
                    r = requests.get(endpoint, params={'url': imp.source_url}, timeout=10)
                    if r.ok:
                        data = r.json()
                        imp.thumbnail_url = data.get('thumbnail_url', '')
                        imp.caption = data.get('title', '')
                        imp.raw_data = data
                        imp.save()
                except Exception:
                    pass
                break
    except SocialImport.DoesNotExist:
        pass

@shared_task(queue='default')
def generate_pet_qr(pet_id):
    """Generiraj QR kod za ljubimca."""
    import qrcode
    from io import BytesIO
    from django.core.files.base import ContentFile

    try:
        pet = PetProfile.objects.get(id=pet_id)
        url = f"https://memio.pet/ljubimac/{pet.slug}/"
        qr = qrcode.make(url)
        buffer = BytesIO()
        qr.save(buffer, format='PNG')
        pet.qr_code.save(f'qr_{pet.slug}.png', ContentFile(buffer.getvalue()), save=True)
    except PetProfile.DoesNotExist:
        pass
```

---

## B4 — API (views.py + urls.py)

Endpointi:
```
GET  /api/boxgram/feed/                    → javni feed svih ljubimaca
GET  /api/boxgram/pets/                    → moji ljubimci
POST /api/boxgram/pets/                    → kreiraj profil
GET  /api/boxgram/pets/{slug}/             → javni profil
GET  /api/boxgram/pets/{slug}/timeline/    → svi eventi
POST /api/boxgram/pets/{slug}/events/      → dodaj event
POST /api/boxgram/import/url/             → uvoz po URL-u
POST /api/boxgram/import/{id}/approve/    → odobri uvoz
POST /api/boxgram/import/{id}/reject/     → odbij uvoz
GET  /api/boxgram/competitions/            → lista takmičenja
POST /api/boxgram/competitions/{id}/vote/ → glasaj
GET  /api/boxgram/pets/{slug}/qr/         → QR kod
```

---

## B5 — Migracija i registracija

```bash
python manage.py makemigrations boxgram
python manage.py migrate
```

Dodaj u main urls.py:
```python
path('api/boxgram/', include('boxgram.urls')),
path('boxgram/', include('boxgram.web_urls')),
```

---

## B6 — Tests (tests.py)
- Test kreiranja PetProfile
- Test LifeEvent CRUD
- Test glasanja (duplicate IP blokiran)
- Test close_competition task
- Test SocialImport URL parse
- Min 80% coverage

---

## NAPOMENE
- Jezik: sve verbose_name na hrvatskom
- Slug: auto-gen iz name + uuid suffix (unique)
- Memorial mode: automatski kad death_date nije null
- SHA256 seal: generira se jednom, nikad se ne mijenja
- qrcode library: pip install qrcode[pil]
- Pčelinja zajednica (pcela) je punopravna kategorija
