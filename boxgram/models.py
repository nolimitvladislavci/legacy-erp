import hashlib
import uuid

from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import gettext_lazy as _

from companies.models import Company

SPECIES_CHOICES = [
    ("pas", _("Pas")),
    ("macka", _("Mačka")),
    ("konj", _("Konj")),
    ("zec", _("Zec")),
    ("ptica", _("Ptica")),
    ("riba", _("Riba")),
    ("pcela", _("Pčelinja zajednica")),
    ("govedo", _("Govedo")),
    ("svinja", _("Svinja")),
    ("ovca", _("Ovca")),
    ("koza", _("Koza")),
    ("ostalo", _("Ostalo")),
]

EVENT_TYPE_CHOICES = [
    ("rodenje", _("Rođenje")),
    ("vet", _("Veterinarski pregled")),
    ("cijepljenje", _("Cijepljenje")),
    ("natjecanje", _("Natjecanje")),
    ("nagrada", _("Nagrada")),
    ("usvajanje", _("Usvajanje")),
    ("promjena_vlasnika", _("Promjena vlasnika")),
    ("preseljenje", _("Preseljenje")),
    ("parenje", _("Parenje")),
    ("leglo", _("Leglo")),
    ("social_import", _("Uvoz sa društvenih mreža")),
    ("milestone", _("Važna osnovna doga đaja")),
    ("smrt", _("Smrt")),
    ("memorijal", _("Memorijal")),
    ("ostalo", _("Ostalo")),
]

PLATFORM_CHOICES = [
    ("facebook", _("Facebook")),
    ("instagram", _("Instagram")),
    ("tiktok", _("TikTok")),
    ("youtube", _("YouTube")),
    ("manual", _("Ručna dodela")),
]

SOURCE_CHOICES = [
    ("facebook", _("Facebook")),
    ("instagram", _("Instagram")),
    ("tiktok", _("TikTok")),
    ("youtube", _("YouTube")),
    ("manual", _("Ručna dodela")),
    ("api", _("API")),
]

SOCIAL_IMPORT_STATUS_CHOICES = [
    ("pending", _("Na čekanju")),
    ("approved", _("Odobreno")),
    ("rejected", _("Odbijeno")),
    ("mapped", _("Mapirano")),
]

COMPETITION_STATUS_CHOICES = [
    ("draft", _("Skica")),
    ("active", _("Aktivna")),
    ("closed", _("Zatvorena")),
]


class PetProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="boxgram_pets", verbose_name=_("Stanac"))
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="boxgram_pets", verbose_name=_("Vlasnik"))
    name = models.CharField(max_length=200, verbose_name=_("Ime"))
    species = models.CharField(max_length=50, choices=SPECIES_CHOICES, verbose_name=_("Vrsta"))
    breed = models.CharField(max_length=200, blank=True, verbose_name=_("Pasmina"))
    birth_date = models.DateField(null=True, blank=True, verbose_name=_("Datum rođenja"))
    death_date = models.DateField(null=True, blank=True, verbose_name=_("Datum smrti"))
    bio = models.TextField(blank=True, verbose_name=_("Biografija"))
    avatar = models.ImageField(upload_to="boxgram/avatars/", null=True, blank=True, verbose_name=_("Avatar"))
    cover_photo = models.ImageField(upload_to="boxgram/covers/", null=True, blank=True, verbose_name=_("Naslovnjica"))
    slug = models.SlugField(unique=True, verbose_name=_("URL slug"))
    is_public = models.BooleanField(default=True, verbose_name=_("Javna profil"))
    is_memorial = models.BooleanField(default=False, verbose_name=_("Memorijal"))
    qr_code = models.ImageField(upload_to="boxgram/qrcodes/", null=True, blank=True, verbose_name=_("QR kod"))
    sha256_seal = models.CharField(max_length=64, blank=True, verbose_name=_("SHA256 pečat"))
    is_verified_breeder = models.BooleanField(default=False, verbose_name=_("Verificirani uzgajivač"))
    is_vet_verified = models.BooleanField(default=False, verbose_name=_("Veterinarski verificiran"))
    followers_count = models.IntegerField(default=0, verbose_name=_("Broj pratitelja"))
    hearts_count = models.IntegerField(default=0, verbose_name=_("Broj srca"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Kreirano"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Ažurirano"))
    company = models.ForeignKey(
        Company,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="boxgram_pet_company",
        verbose_name=_("Kompanija"),
    )
    limit_connect_ref = models.CharField(max_length=100, blank=True, verbose_name=_("LIMIT Connect referenca"))

    class Meta:
        verbose_name = _("Pet profil")
        verbose_name_plural = _("Pet profili")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.get_species_display()})"

    def save(self, *args, **kwargs):
        if self.death_date and not self.is_memorial:
            self.is_memorial = True
        if not self.sha256_seal:
            content = f"{self.id}{self.name}{self.owner_id}{self.created_at}".encode()
            self.sha256_seal = hashlib.sha256(content).hexdigest()
        super().save(*args, **kwargs)


class LifeEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pet = models.ForeignKey(PetProfile, on_delete=models.CASCADE, related_name="life_events", verbose_name=_("Pet"))
    event_type = models.CharField(max_length=50, choices=EVENT_TYPE_CHOICES, verbose_name=_("Tip događaja"))
    title = models.CharField(max_length=300, verbose_name=_("Naslov"))
    description = models.TextField(blank=True, verbose_name=_("Opis"))
    date = models.DateField(verbose_name=_("Datum"))
    location = models.CharField(max_length=300, blank=True, verbose_name=_("Lokacija"))
    source = models.CharField(max_length=50, choices=SOURCE_CHOICES, default="manual", verbose_name=_("Izvor"))
    source_url = models.URLField(blank=True, verbose_name=_("URL izvora"))
    source_id = models.CharField(max_length=200, blank=True, verbose_name=_("ID izvora"))
    is_public = models.BooleanField(default=True, verbose_name=_("Javna"))
    is_verified = models.BooleanField(default=False, verbose_name=_("Verificirana"))
    hearts_count = models.IntegerField(default=0, verbose_name=_("Broj srca"))
    comments_count = models.IntegerField(default=0, verbose_name=_("Broj komentara"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Kreirano"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Ažurirano"))

    class Meta:
        verbose_name = _("Životni događaj")
        verbose_name_plural = _("Životni događaji")
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return f"{self.title} ({self.date})"


class EventMedia(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(LifeEvent, on_delete=models.CASCADE, related_name="media", verbose_name=_("Događaj"))
    file = models.FileField(upload_to="boxgram/media/", verbose_name=_("Datoteka"))
    file_type = models.CharField(
        max_length=50,
        choices=[("image", _("Slika")), ("video", _("Video")), ("audio", _("Zvuk"))],
        verbose_name=_("Tip datoteke"),
    )
    source_url = models.URLField(blank=True, verbose_name=_("URL izvora"))
    thumbnail_url = models.URLField(blank=True, verbose_name=_("URL minijature"))
    sha256 = models.CharField(max_length=64, blank=True, verbose_name=_("SHA256 heš"))
    order = models.IntegerField(default=0, verbose_name=_("Redosled"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Kreirano"))

    class Meta:
        verbose_name = _("Medija događaja")
        verbose_name_plural = _("Medije događaja")
        ordering = ["order"]

    def __str__(self):
        return f"{self.event.title} - {self.file_type}"


class SocialImport(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pet = models.ForeignKey(PetProfile, on_delete=models.CASCADE, related_name="social_imports", verbose_name=_("Pet"))
    platform = models.CharField(max_length=50, choices=PLATFORM_CHOICES, verbose_name=_("Platforma"))
    source_url = models.URLField(verbose_name=_("URL izvora"))
    raw_data = models.JSONField(default=dict, verbose_name=_("Sirovi podaci"))
    status = models.CharField(
        max_length=50, choices=SOCIAL_IMPORT_STATUS_CHOICES, default="pending", verbose_name=_("Status")
    )
    mapped_to = models.OneToOneField(
        LifeEvent,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="social_import",
        verbose_name=_("Mapiran na"),
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Kreirano"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Ažurirano"))

    class Meta:
        verbose_name = _("Uvoz sa društvenih mreža")
        verbose_name_plural = _("Uvozi sa društvenih mreža")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.platform} - {self.source_url}"


class Competition(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="boxgram_competitions", verbose_name=_("Stanac")
    )
    title = models.CharField(max_length=300, verbose_name=_("Naslov"))
    species_filter = models.CharField(
        max_length=50, choices=SPECIES_CHOICES, blank=True, verbose_name=_("Filter vrste")
    )
    start_date = models.DateTimeField(verbose_name=_("Datum početka"))
    end_date = models.DateTimeField(verbose_name=_("Datum kraja"))
    status = models.CharField(
        max_length=50, choices=COMPETITION_STATUS_CHOICES, default="draft", verbose_name=_("Status")
    )
    winner = models.ForeignKey(
        PetProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="competition_wins",
        verbose_name=_("Pobednik"),
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Kreirano"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Ažurirano"))

    class Meta:
        verbose_name = _("Natjecanje")
        verbose_name_plural = _("Natjecanja")
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class CompetitionEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    competition = models.ForeignKey(
        Competition, on_delete=models.CASCADE, related_name="entries", verbose_name=_("Natjecanje")
    )
    pet = models.ForeignKey(
        PetProfile, on_delete=models.CASCADE, related_name="competition_entries", verbose_name=_("Pet")
    )
    media = models.ForeignKey(EventMedia, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Medija"))
    votes = models.IntegerField(default=0, verbose_name=_("Broj glasova"))
    rank = models.IntegerField(null=True, blank=True, verbose_name=_("Rang"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Kreirano"))

    class Meta:
        verbose_name = _("Unos u natjecanju")
        verbose_name_plural = _("Unosi u natjecanju")
        unique_together = ("competition", "pet")
        ordering = ["-votes"]

    def __str__(self):
        return f"{self.competition.title} - {self.pet.name}"


class CompetitionVote(models.Model):
    entry = models.ForeignKey(
        CompetitionEntry, on_delete=models.CASCADE, related_name="vote_records", verbose_name=_("Unos")
    )
    voter_ip = models.GenericIPAddressField(verbose_name=_("IP glasača"))
    voter_user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Korisnik glasač")
    )
    voted_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Vreme glasa"))

    class Meta:
        verbose_name = _("Glas u natjecanju")
        verbose_name_plural = _("Glasovi u natjecanju")
        unique_together = ("entry", "voter_ip")

    def __str__(self):
        return f"Glas za {self.entry.pet.name}"


class PetFollower(models.Model):
    pet = models.ForeignKey(PetProfile, on_delete=models.CASCADE, related_name="pet_followers", verbose_name=_("Pet"))
    follower = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="following_pets", verbose_name=_("Pratitelj")
    )
    followed_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Vreme praćenja"))

    class Meta:
        verbose_name = _("Pet pratitelj")
        verbose_name_plural = _("Pet pratitelji")
        unique_together = ("pet", "follower")

    def __str__(self):
        return f"{self.follower.username} prati {self.pet.name}"


class EventHeart(models.Model):
    event = models.ForeignKey(
        LifeEvent, on_delete=models.CASCADE, related_name="heart_records", verbose_name=_("Događaj")
    )
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Korisnik"))
    ip = models.GenericIPAddressField(verbose_name=_("IP"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Vreme"))

    class Meta:
        verbose_name = _("Srce na događaju")
        verbose_name_plural = _("Srca na događajima")
        unique_together = ("event", "ip")

    def __str__(self):
        return f"Srce na {self.event.title}"
