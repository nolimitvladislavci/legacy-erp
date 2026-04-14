"""
memio_world/models.py — Memio World digitalna baština
Baza: memio_world (potpuno odvojena od fina_erp i memio_pets)

Proizvod: memio.world — sjećanja, obitelji, TimeCapsule, MemoryVault
GDPR kontekst: osobni podaci obitelji, ne ljubimci — zasebna izolacija.
"""

import uuid

from django.db import models

from memio_world.encrypted_fields import WorldEncryptedField
from django.utils.translation import gettext_lazy as _


class WaitlistEntry(models.Model):
    """
    memio.world waitlist — migrirana iz memio_pets.WaitlistEntry
    (samo zapisi koji su source='memio.world').
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    email = models.EmailField(unique=True)
    source = models.CharField(max_length=50, default="memio.world")
    interest = models.CharField(
        max_length=30,
        blank=True,
        default="",
        choices=[
            ("timecapsule", "TimeCapsule"),
            ("familystory", "Obiteljska priča"),
            ("memoryvault", "Memory Vault"),
            ("general", "Općenito"),
        ],
        help_text="Koji dio Memio Worlda zanima korisnika",
    )
    ip = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    notified = models.BooleanField(default=False, help_text="Je li poslan launch email")

    class Meta:
        app_label = "memio_world"
        verbose_name = _("Waitlist prijava")
        verbose_name_plural = _("Waitlist prijave")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.email} ({self.source})"


class TimeCapsule(models.Model):
    """
    Digitalna vremenska kapsula — poruka, mediji, datum otvaranja.
    Korisnik kreira kapsulu koja se "otvara" na zadani datum.
    """

    STATUS_CHOICES = [
        ("draft", "Nacrt"),
        ("sealed", "Zapečaćena"),
        ("opened", "Otvorena"),
        ("expired", "Istekla"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner_email = models.EmailField(help_text="Kreator kapsule")
    title = models.CharField(max_length=200)
    message = WorldEncryptedField(blank=True, help_text="Tekstualna poruka (AES enkriptirano)")
    media_urls = models.JSONField(default=list, blank=True, help_text="Lista URL-ova na medije (slike, video, audio)")
    recipients = models.JSONField(default=list, blank=True, help_text="Email adrese primatelja")
    open_date = models.DateField(help_text="Datum kad se kapsula otvara")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")
    created_at = models.DateTimeField(auto_now_add=True)
    opened_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "memio_world"
        verbose_name = _("Vremenska kapsula")
        verbose_name_plural = _("Vremenske kapsule")
        ordering = ["open_date"]

    def __str__(self):
        return f"{self.title} → {self.open_date}"


class MemoryVault(models.Model):
    """
    Sigurni trezor sjećanja — enkriptirani dokumenti, fotografije,
    obiteljski recepti, važni datumi.
    """

    CATEGORY_CHOICES = [
        ("photo", "Fotografije"),
        ("document", "Dokumenti"),
        ("recipe", "Recepti"),
        ("story", "Priče"),
        ("video", "Video"),
        ("audio", "Audio"),
        ("other", "Ostalo"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner_email = models.EmailField()
    title = models.CharField(max_length=200)
    description = WorldEncryptedField(blank=True, help_text="AES enkriptirano")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="other")
    media_url = models.URLField(blank=True, help_text="URL na pohranjeni medij")
    file_size_bytes = models.BigIntegerField(default=0)
    is_encrypted = models.BooleanField(default=True)
    shared_with = models.JSONField(default=list, blank=True, help_text="Email adrese s kojima je podijeljeno")
    tags = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "memio_world"
        verbose_name = _("Memory Vault")
        verbose_name_plural = _("Memory Vault stavke")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} ({self.category})"


class FamilyStory(models.Model):
    """
    Obiteljske priče — tekst + mediji, generacijski lanac.
    Mogu se povezivati (roditelj → dijete priča).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    author_email = models.EmailField()
    title = models.CharField(max_length=200)
    content = WorldEncryptedField(help_text="Markdown format (AES enkriptirano)")
    media_urls = models.JSONField(default=list, blank=True)
    parent_story = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="child_stories",
        help_text="Roditelj priča (za generacijski lanac)",
    )
    location = models.CharField(max_length=200, blank=True, help_text="Gdje se priča dogodila")
    year_from = models.IntegerField(null=True, blank=True)
    year_to = models.IntegerField(null=True, blank=True)
    is_public = models.BooleanField(default=False, help_text="Vidljivo svima ili samo obitelji")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "memio_world"
        verbose_name = _("Obiteljska priča")
        verbose_name_plural = _("Obiteljske priče")
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


# ════════════════════════════════════════════════════════════════
# CHILD PROFILE + MEMORY ENTRY + MILESTONE (F3 task)
# ════════════════════════════════════════════════════════════════


class ChildProfile(models.Model):
    """Svako dijete = jedan digitalni pasoš."""

    VISIBILITY_CHOICES = [
        ("private", "Samo obitelj"),
        ("family", "Šira obitelj"),
        ("public", "Javno"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    date_of_birth = models.DateField()
    birth_city = models.CharField(max_length=100, blank=True)
    birth_country = models.CharField(max_length=2, default="HR")
    photo = models.ImageField(upload_to="children/", null=True, blank=True)
    guardian_emails_encrypted = WorldEncryptedField(
        blank=True,
        help_text="Email adrese roditelja/skrbnika (AES enkriptirano, JSON format)",
    )
    visibility = models.CharField(max_length=10, choices=VISIBILITY_CHOICES, default="private")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "memio_world"
        db_table = "mw_child_profile"
        verbose_name = _("Profil djeteta")
        verbose_name_plural = _("Profili djece")
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.date_of_birth})"

    @property
    def age(self):
        from datetime import date

        today = date.today()
        return (
            today.year
            - self.date_of_birth.year
            - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))
        )


class MemoryEntry(models.Model):
    """Jedan zapis u knjizi sjećanja."""

    ENTRY_TYPES = [
        ("photo", "Fotografija"),
        ("video", "Video"),
        ("text", "Priča/tekst"),
        ("milestone", "Postignuće"),
        ("document", "Dokument"),
        ("drawing", "Crtež"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    child = models.ForeignKey(ChildProfile, on_delete=models.CASCADE, related_name="memories")
    entry_type = models.CharField(max_length=20, choices=ENTRY_TYPES)
    title = models.CharField(max_length=200)
    content = WorldEncryptedField(blank=True, help_text="AES enkriptirano")
    media_file = models.FileField(upload_to="memories/", null=True, blank=True)
    entry_date = models.DateField(help_text="Datum sjećanja")
    age_at_entry = models.PositiveSmallIntegerField(null=True, blank=True)
    created_by_email = models.EmailField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_featured = models.BooleanField(default=False)
    tags = models.CharField(max_length=500, blank=True)

    class Meta:
        app_label = "memio_world"
        db_table = "mw_memory_entry"
        ordering = ["entry_date"]
        verbose_name = _("Sjećanje")
        verbose_name_plural = _("Sjećanja")

    def __str__(self):
        return f"{self.title} ({self.entry_date})"

    def save(self, *args, **kwargs):
        if self.child and self.entry_date and not self.age_at_entry:
            delta = self.entry_date - self.child.date_of_birth
            self.age_at_entry = delta.days // 365
        super().save(*args, **kwargs)


class Milestone(models.Model):
    """Prekretnice — 1. korak, 1. riječ, 1. dan škole..."""

    MILESTONE_TYPES = [
        ("first_word", "Prva riječ"),
        ("first_step", "Prvi korak"),
        ("first_tooth", "Prvi zubić"),
        ("school_start", "Polazak u školu"),
        ("graduation", "Završetak obrazovanja"),
        ("sport", "Sportski uspjeh"),
        ("art", "Umjetnički uspjeh"),
        ("other", "Ostalo"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    child = models.ForeignKey(ChildProfile, on_delete=models.CASCADE, related_name="milestones")
    milestone_type = models.CharField(max_length=30, choices=MILESTONE_TYPES)
    title = models.CharField(max_length=200)
    description = WorldEncryptedField(blank=True, help_text="AES enkriptirano")
    achieved_date = models.DateField()
    photo = models.ImageField(upload_to="milestones/", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "memio_world"
        db_table = "mw_milestone"
        ordering = ["achieved_date"]
        verbose_name = _("Prekretnica")
        verbose_name_plural = _("Prekretnice")

    def __str__(self):
        return f"{self.title} ({self.achieved_date})"


# ════════════════════════════════════════════════════════════════
# EDUKATIVNI SADRŽAJ — Učenje kroz igru
# ════════════════════════════════════════════════════════════════


class StoryBook(models.Model):
    """Bakine priče, bajke, priče za laku noć — audio + tekst."""

    CATEGORY_CHOICES = [
        ("laku_noc", "Za laku noć"),
        ("bajka", "Bajka"),
        ("narodna", "Narodna priča"),
        ("bakina", "Bakina priča"),
        ("zivotinje", "O životinjama"),
        ("priroda", "O prirodi"),
        ("avantura", "Avantura"),
    ]
    AGE_CHOICES = [
        ("3-4", "3-4 godine"),
        ("5-6", "5-6 godina"),
        ("7-8", "7-8 godina"),
        ("9+", "9+ godina"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    author = models.CharField(max_length=200, blank=True, help_text="Autor ili 'Narodna'")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="laku_noc")
    age_group = models.CharField(max_length=5, choices=AGE_CHOICES, default="3-4")
    content = WorldEncryptedField(help_text="Tekst priče (enkriptirano)")
    audio_url = models.URLField(blank=True, help_text="URL na audio snimku (S3/MinIO)")
    cover_image = models.ImageField(upload_to="world/stories/", null=True, blank=True)
    duration_minutes = models.PositiveSmallIntegerField(null=True, blank=True)
    language = models.CharField(
        max_length=5,
        default="hr",
        choices=[
            ("hr", "Hrvatski"),
            ("en", "English"),
            ("de", "Deutsch"),
            ("sl", "Slovenščina"),
            ("sr", "Srpski"),
        ],
    )
    is_published = models.BooleanField(default=False)
    read_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "memio_world"
        db_table = "mw_story_book"
        ordering = ["age_group", "title"]

    def __str__(self):
        return f"{self.title} ({self.get_age_group_display()})"


class TraditionalGame(models.Model):
    """Stare igre — Mlin, Čovječe ne ljuti se, Škola, Lastik, Klikeri...
    Digitalna konzervacija nematerijalne kulturne baštine EU.
    """

    GAME_TYPE_CHOICES = [
        ("board", "Igra na ploči"),
        ("outdoor", "Igra na otvorenom"),
        ("card", "Kartaška igra"),
        ("word", "Igra riječima"),
        ("math", "Matematička igra"),
        ("strategy", "Strateška igra"),
        ("physical", "Fizička igra"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    name_local = models.CharField(max_length=200, blank=True, help_text="Lokalni naziv (npr. Mlin, Tri u nizu)")
    game_type = models.CharField(max_length=15, choices=GAME_TYPE_CHOICES, default="board")
    origin_country = models.CharField(max_length=100, blank=True, help_text="Zemlja porijekla ili 'Europa'")
    origin_era = models.CharField(max_length=100, blank=True, help_text="Npr. 'Rimsko doba', 'Srednji vijek'")
    min_players = models.PositiveSmallIntegerField(default=2)
    max_players = models.PositiveSmallIntegerField(default=2)
    age_min = models.PositiveSmallIntegerField(default=5)
    rules_text = models.TextField(help_text="Pravila igre u Markdown formatu")
    history_text = models.TextField(blank=True, help_text="Povijest igre — odakle dolazi, kako se mijenjala")
    illustration = models.ImageField(upload_to="world/games/", null=True, blank=True)
    video_tutorial_url = models.URLField(blank=True, help_text="YouTube/Vimeo tutorial")
    is_playable_online = models.BooleanField(default=False, help_text="Može se igrati u browseru")
    game_engine_data = models.JSONField(
        default=dict, blank=True, help_text="Konfiguracija za web igru (board layout, rules engine)"
    )
    language = models.CharField(max_length=5, default="hr")
    is_published = models.BooleanField(default=False)
    play_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "memio_world"
        db_table = "mw_traditional_game"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.get_game_type_display()})"


class LearningModule(models.Model):
    """Interaktivni edukativni moduli — slova, brojevi, boje, oblici."""

    SUBJECT_CHOICES = [
        ("letters_hr", "Slova — Hrvatski"),
        ("letters_en", "Letters — English"),
        ("letters_de", "Buchstaben — Deutsch"),
        ("numbers", "Brojevi / Numbers"),
        ("colors", "Boje / Colors"),
        ("shapes", "Oblici / Shapes"),
        ("animals", "Životinje / Animals"),
        ("nature", "Priroda / Nature"),
        ("music", "Glazba / Music"),
        ("reading", "Čitanje / Reading"),
        ("writing", "Pisanje / Writing"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    subject = models.CharField(max_length=20, choices=SUBJECT_CHOICES)
    age_min = models.PositiveSmallIntegerField(default=3)
    age_max = models.PositiveSmallIntegerField(default=6)
    description = models.TextField(blank=True)
    content_data = models.JSONField(default=dict, help_text="Sadržaj lekcije (slike, zvukovi, kviz pitanja)")
    cover_image = models.ImageField(upload_to="world/learning/", null=True, blank=True)
    video_url = models.URLField(blank=True)
    order = models.PositiveSmallIntegerField(default=0)
    is_published = models.BooleanField(default=False)
    completion_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "memio_world"
        db_table = "mw_learning_module"
        ordering = ["subject", "order"]

    def __str__(self):
        return f"{self.title} ({self.get_subject_display()})"


class Spomenar(models.Model):
    """Digitalni spomenar — kao školski, ali zauvijek.
    Prijatelji, učiteljice, krsni kumovi ostavljaju poruke.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    child = models.ForeignKey(ChildProfile, on_delete=models.CASCADE, related_name="spomenari")
    title = models.CharField(max_length=200, default="Moj Spomenar")
    is_open = models.BooleanField(default=True, help_text="Prihvaća nove unose")
    share_token = models.UUIDField(default=uuid.uuid4, unique=True, help_text="Link za dijeljenje")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "memio_world"
        db_table = "mw_spomenar"

    def __str__(self):
        return f"{self.title} — {self.child.name}"

    @property
    def share_url(self):
        return f"https://memio.world/spomenar/{self.share_token}/"


class SpomenarEntry(models.Model):
    """Jedan unos u spomenar — poruka od prijatelja/obitelji."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    spomenar = models.ForeignKey(Spomenar, on_delete=models.CASCADE, related_name="entries")
    author_name = models.CharField(max_length=100)
    author_relation = models.CharField(max_length=50, blank=True, help_text="Npr. 'Prijateljica', 'Baka', 'Učiteljica'")
    message = WorldEncryptedField(help_text="Poruka (enkriptirano)")
    drawing = models.ImageField(upload_to="world/spomenar/", null=True, blank=True, help_text="Crtež ili slika")
    sticker = models.CharField(max_length=10, blank=True, help_text="Emoji sticker")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "memio_world"
        db_table = "mw_spomenar_entry"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.author_name}: {self.message[:30]}..."


class Event(models.Model):
    """Događaji u životu djeteta — rođendani, izleti, prvi dan škole."""

    EVENT_TYPES = [
        ("birthday", "Rođendan"),
        ("school_start", "Prvi dan škole"),
        ("school_end", "Kraj školske godine"),
        ("trip", "Izlet / Putovanje"),
        ("performance", "Priredba / Nastup"),
        ("sport", "Sportski događaj"),
        ("holiday", "Blagdan"),
        ("family", "Obiteljsko okupljanje"),
        ("other", "Ostalo"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    child = models.ForeignKey(ChildProfile, on_delete=models.CASCADE, related_name="events")
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    title = models.CharField(max_length=200)
    description = WorldEncryptedField(blank=True)
    event_date = models.DateField()
    location = models.CharField(max_length=200, blank=True)
    photos = models.JSONField(default=list, blank=True, help_text="Lista URL-ova fotografija")
    video_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "memio_world"
        db_table = "mw_event"
        ordering = ["-event_date"]

    def __str__(self):
        return f"{self.title} ({self.event_date})"


# ════════════════════════════════════════════════════════════════
# INOVACIJA I: "VOICE LEGACY" — Glas koji preživljava stoljeća
# ════════════════════════════════════════════════════════════════


class VoiceLegacy(models.Model):
    """Snimka glasa — baka, djed, roditelj — čuvana zauvijek.

    Ne samo MP3. Ekstrahiramo biometrijski potpis emocije:
    - Frekvencijski raspon (toplina glasa)
    - Tempo govora (mirnoća)
    - Pauze (dramatičnost)
    AI može rekonstruirati NOVU priču istim glasom.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    child = models.ForeignKey(ChildProfile, on_delete=models.CASCADE, related_name="voice_legacies")
    speaker_name = models.CharField(max_length=100, help_text="Tko govori (Baka Mara, Djed Ivo...)")
    speaker_relation = models.CharField(max_length=50, blank=True, help_text="Baka, Djed, Mama, Tata, Ujak...")
    audio_file = models.FileField(upload_to="world/voices/", help_text="Originalna snimka")
    duration_seconds = models.PositiveIntegerField(default=0)
    transcript = WorldEncryptedField(blank=True, help_text="Transkript (AES)")
    # Biometrijski potpis glasa
    voice_fingerprint = models.JSONField(default=dict, blank=True, help_text="Frekvencija, tempo, pauze, toplina")
    emotion_tags = models.JSONField(default=list, blank=True, help_text="['nježno', 'veselo', 'tužno', 'smirujuće']")
    # Metadata
    language = models.CharField(max_length=5, default="hr")
    dialect = models.CharField(max_length=50, blank=True, help_text="Npr. Slavonski, Kajkavski, Schwäbisch")
    recorded_at = models.DateTimeField(null=True, blank=True)
    integrity_hash = models.CharField(max_length=64, blank=True, help_text="SHA-256 originalne snimke")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "memio_world"
        db_table = "mw_voice_legacy"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.speaker_name}: {self.duration_seconds}s ({self.language})"

    def save(self, *args, **kwargs):
        # Auto-hash za integritet
        if self.audio_file and not self.integrity_hash:
            import hashlib

            try:
                h = hashlib.sha256()
                for chunk in self.audio_file.chunks():
                    h.update(chunk)
                self.integrity_hash = h.hexdigest()
            except Exception:
                pass
        super().save(*args, **kwargs)


# ════════════════════════════════════════════════════════════════
# INOVACIJA II: "ETHICAL ALGORITHM" — Anti-dopaminski motor
# ════════════════════════════════════════════════════════════════


class EthicalSession(models.Model):
    """Praćenje sesije djeteta — NE za engagement, nego za ZAŠTITU.

    Ethical Algorithm:
    - Ako dijete igra 15 min → predloži priču (promjena aktivnosti)
    - Ako čita 20 min → predloži igru na otvorenom (Školica, Kubb)
    - Nikad ne predlaže "još istog" — uvijek širi horizont
    - "Noćni protokol": nakon 20h → samo audio, ekran se gasi
    - Nema push notifikacija. NIKAD.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    child = models.ForeignKey(ChildProfile, on_delete=models.CASCADE, related_name="ethical_sessions")
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    # Što je dijete radilo
    activity_type = models.CharField(
        max_length=20,
        choices=[
            ("game", "Igra"),
            ("story", "Priča"),
            ("learning", "Učenje"),
            ("spomenar", "Spomenar"),
            ("voice", "Slušanje glasa"),
            ("capsule", "TimeCapsule"),
        ],
    )
    activity_id = models.UUIDField(null=True, blank=True, help_text="ID igre/priče/lekcije")
    duration_minutes = models.PositiveSmallIntegerField(default=0)
    # Ethical decisions
    was_night_mode = models.BooleanField(default=False, help_text="Je li bio noćni protokol (audio-only)")
    suggestion_given = models.CharField(
        max_length=200, blank=True, help_text="Što je sustav predložio umjesto 'još istog'"
    )
    child_accepted_suggestion = models.BooleanField(null=True, help_text="Je li dijete prihvatilo diversifikaciju")

    class Meta:
        app_label = "memio_world"
        db_table = "mw_ethical_session"
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.child.name}: {self.activity_type} ({self.duration_minutes}min)"


class NightProtocol(models.Model):
    """Konfiguracija Noćnog Protokola po djetetu.

    Nakon zadanog sata: ekran → audio only.
    Boje → topla žuta. Font → veći. Animacije → isključene.
    Push notifikacije → ne postoje (nikad ih nismo ni imali).
    """

    child = models.OneToOneField(ChildProfile, on_delete=models.CASCADE, related_name="night_protocol")
    is_enabled = models.BooleanField(default=True)
    night_start_hour = models.PositiveSmallIntegerField(default=20, help_text="Sat kad počinje noćni mod (0-23)")
    night_end_hour = models.PositiveSmallIntegerField(default=7, help_text="Sat kad završava")
    audio_only = models.BooleanField(default=True, help_text="Samo zvuk, ekran se gasi")
    max_stories_before_sleep = models.PositiveSmallIntegerField(default=2, help_text="Max priča prije 'Laku noć'")
    lullaby_enabled = models.BooleanField(default=True, help_text="Uspavanka nakon zadnje priče")
    parent_override_pin = models.CharField(max_length=4, blank=True, help_text="PIN za roditelja da produži")

    class Meta:
        app_label = "memio_world"
        db_table = "mw_night_protocol"

    def __str__(self):
        return f"Noćni protokol: {self.child.name} ({self.night_start_hour}:00-{self.night_end_hour}:00)"


# ════════════════════════════════════════════════════════════════
# INOVACIJA III: PRAVO NA ZABORAV + EMOCIONALNA SIGURNOST
# ════════════════════════════════════════════════════════════════


class MemoryGuard(models.Model):
    """Zaštita sjećanja — pravo na skrivanje, pravo na zaborav.

    Dijete (ili roditelj) može:
    - Sakriti bolno sjećanje (vidljivo samo s PIN-om)
    - Odgoditi otvaranje kapsule (nije spremno)
    - Potpuno obrisati — ali tek nakon 30 dana "cooling period"
    - Označiti sjećanje kao "samo za mene" (ni roditelj ne vidi)

    GDPR Article 17 (Right to erasure) + emocionalna dimenzija.
    """

    GUARD_ACTIONS = [
        ("hide", "Sakrij (vidljivo samo s PIN-om)"),
        ("delay", "Odgodi otvaranje"),
        ("private", "Samo za mene"),
        ("delete_request", "Zahtjev za brisanje (30 dana)"),
        ("deleted", "Obrisano"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    child = models.ForeignKey(ChildProfile, on_delete=models.CASCADE, related_name="memory_guards")
    # Što se čuva (generički — može biti bilo koji model)
    content_type = models.CharField(max_length=50, help_text="Model name: MemoryEntry, TimeCapsule, VoiceLegacy...")
    content_id = models.UUIDField(help_text="ID objekta koji se čuva")
    action = models.CharField(max_length=20, choices=GUARD_ACTIONS)
    reason = models.TextField(blank=True, help_text="Zašto (opcionalno, za dijete/roditelja)")
    # Timing
    requested_at = models.DateTimeField(auto_now_add=True)
    cooling_period_ends = models.DateTimeField(null=True, blank=True, help_text="Za delete: 30 dana od zahtjeva")
    executed_at = models.DateTimeField(null=True, blank=True)
    # Tko je zatražio
    requested_by = models.CharField(
        max_length=20,
        choices=[
            ("child", "Dijete"),
            ("parent", "Roditelj"),
            ("system", "Sustav (GDPR)"),
        ],
        default="parent",
    )

    class Meta:
        app_label = "memio_world"
        db_table = "mw_memory_guard"
        ordering = ["-requested_at"]

    def __str__(self):
        return f"{self.get_action_display()}: {self.content_type}#{self.content_id}"
