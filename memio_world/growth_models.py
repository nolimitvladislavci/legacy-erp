"""
PLAY.EU Growth Engine — 5 inovacija koje dižu na 10/10
========================================================

1. TALENT RADAR — AI detekcija interesa → usmjeravanje u stvarne klubove
2. BUDDY SYSTEM — Spajanje djece po komplementarnim interesima (cross-EU)
3. FAMILY QUEST — Tjedni izazovi za CIJELU obitelj (most digital→fizički)
4. SPACED REPETITION — Leitner sustav za dugoročno pamćenje
5. PET BRIDGE — Veza s Memio.pet (ljubimci + odgovornost + Boxgram zona)

+ SAFE ZONE — Moderirana interakcija djece po interesima

Filozofija:
  Ekran je MOST, ne CILJ.
  Svaka aktivnost na platformi mora završiti u STVARNOM ŽIVOTU:
  - Kviz o prometnim znakovima → šetnja s roditeljima + prebrojavanje znakova
  - Lekcija o kuhanju → bakini recepti u kuhinji
  - Talent Radar kaže "glazba" → lista glazbenih škola u blizini
  - Pet Bridge → dijete brine o PRAVOM ljubimcu, ne virtualnom
"""

import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _

# ════════════════════════════════════════════════════════════════
# 1. TALENT RADAR — Detekcija interesa → stvarni svijet
# ════════════════════════════════════════════════════════════════


class TalentProfile(models.Model):
    """
    AI-generirani profil interesa djeteta.

    Ne mjerimo SPOSOBNOST (to je posao škole).
    Mjerimo INTERES — na što dijete troši vrijeme, što ga veseli,
    u čemu spontano traži više.

    Output: "Tvoje dijete pokazuje jak interes za glazbu i životinje.
    Evo glazbenih škola i udruga za zaštitu životinja u vašem gradu."
    """

    INTEREST_CHOICES = [
        ("music", _("Glazba")),
        ("art", _("Likovna umjetnost")),
        ("sports", _("Sport")),
        ("science", _("Znanost")),
        ("math_logic", _("Matematika i logika")),
        ("languages", _("Jezici")),
        ("nature_animals", _("Priroda i životinje")),
        ("technology", _("Tehnologija i robotika")),
        ("cooking", _("Kuhanje")),
        ("storytelling", _("Pripovijedanje")),
        ("history_culture", _("Povijest i kultura")),
        ("social_helping", _("Pomaganje drugima")),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    child = models.OneToOneField(
        "memio_world.ChildProfile",
        on_delete=models.CASCADE,
        related_name="talent_profile",
    )

    # Top 3 interesa (izračunato iz aktivnosti)
    primary_interest = models.CharField(max_length=30, choices=INTEREST_CHOICES, blank=True)
    secondary_interest = models.CharField(max_length=30, choices=INTEREST_CHOICES, blank=True)
    tertiary_interest = models.CharField(max_length=30, choices=INTEREST_CHOICES, blank=True)

    # Sirovi podaci (JSON: {interest: score, ...})
    interest_scores = models.JSONField(default=dict, blank=True)

    # Preporučene aktivnosti u stvarnom svijetu
    recommended_clubs = models.JSONField(
        default=list,
        blank=True,
        help_text="Lista: [{name, type, city, url, distance_km}]",
    )

    # Meta
    last_calculated = models.DateTimeField(null=True, blank=True)
    parent_notified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "memio_world"
        db_table = "play_talent_profile"
        verbose_name = _("Talent profil")
        verbose_name_plural = _("Talent profili")

    def __str__(self):
        return f"{self.child.name}: {self.primary_interest or '?'}"


class RealWorldVenue(models.Model):
    """
    Stvarni klubovi, radionice, sportske dvorane — MOST iz digitalnog u fizički.

    Ovo je KLJUČ monetizacije:
    - Besplatno za roditelje: sadržaj platforme
    - Premium za klubove: vidljivost na platformi (ali NIKAD kao reklama djeci)
    - Prikaz roditelju: "Vaše dijete voli robotiku. Evo Lego robotika radionica u Zagrebu."
    """

    VENUE_TYPE_CHOICES = [
        ("music_school", _("Glazbena škola")),
        ("sports_club", _("Sportski klub")),
        ("art_workshop", _("Likovna radionica")),
        ("robotics", _("Robotika / STEM")),
        ("dance", _("Ples")),
        ("swimming", _("Plivanje")),
        ("martial_arts", _("Borilački sportovi")),
        ("scouts", _("Izviđači")),
        ("animal_shelter", _("Sklonište za životinje")),
        ("library", _("Knjižnica")),
        ("museum", _("Muzej")),
        ("nature_club", _("Prirodoslovno društvo")),
        ("cooking_class", _("Kulinarska radionica")),
        ("theater", _("Kazalište / Drama")),
        ("language_school", _("Škola stranih jezika")),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=300)
    venue_type = models.CharField(max_length=30, choices=VENUE_TYPE_CHOICES)
    description = models.TextField(blank=True)

    # Lokacija
    city = models.CharField(max_length=100)
    country = models.CharField(max_length=5, default="HR")
    address = models.CharField(max_length=300, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    # Kontakt
    website = models.URLField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)

    # Interesi koje pokriva
    interests = models.JSONField(default=list, help_text="Lista interest kodova: ['music', 'art']")

    # Dob
    age_min = models.PositiveSmallIntegerField(default=4)
    age_max = models.PositiveSmallIntegerField(default=18)

    # Status
    is_verified = models.BooleanField(default=False, help_text="Verificiran od PLAY.EU tima")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "memio_world"
        db_table = "play_venue"
        ordering = ["country", "city", "name"]
        verbose_name = _("Stvarni klub/radionica")
        verbose_name_plural = _("Stvarni klubovi/radionice")

    def __str__(self):
        return f"{self.name} ({self.city})"


# ════════════════════════════════════════════════════════════════
# 2. BUDDY SYSTEM — Spajanje djece po komplementarnim interesima
# ════════════════════════════════════════════════════════════════


class BuddyPair(models.Model):
    """
    Spajanje djece po KOMPLEMENTARNIM interesima (ne istim!).

    Dijete koje voli matematiku → upareno s djetetom koje voli umjetnost.
    Uče jedno od drugog. Razmjenjuju perspektive.

    Cross-EU: hrvatsko dijete + njemačko dijete = učenje jezika kroz prijateljstvo.

    SVE komunikacije su:
    - Moderirane (AI + ljudski moderator)
    - Samo tekst (bez slika, bez videa, bez DM-ova)
    - Vidljive roditeljima UVIJEK
    """

    STATUS_CHOICES = [
        ("proposed", _("Predloženo")),
        ("parent_approved", _("Roditelj odobrio")),
        ("active", _("Aktivno")),
        ("paused", _("Pauzirano")),
        ("ended", _("Završeno")),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    child_a = models.ForeignKey(
        "memio_world.ChildProfile",
        on_delete=models.CASCADE,
        related_name="buddy_pairs_a",
    )
    child_b = models.ForeignKey(
        "memio_world.ChildProfile",
        on_delete=models.CASCADE,
        related_name="buddy_pairs_b",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="proposed")

    # Zašto su upareni
    match_reason = models.TextField(help_text="AI objašnjenje zašto su dobri partneri")
    shared_activity = models.CharField(max_length=200, blank=True, help_text="Zajednički zadatak/projekt")

    # Jezici za cross-EU
    language_a = models.CharField(max_length=5, default="hr")
    language_b = models.CharField(max_length=5, default="hr")

    # Roditeljski pristanak (GDPR!)
    parent_a_email = models.EmailField()
    parent_b_email = models.EmailField()
    parent_a_approved = models.BooleanField(default=False)
    parent_b_approved = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "memio_world"
        db_table = "play_buddy_pair"
        verbose_name = _("Buddy par")
        verbose_name_plural = _("Buddy parovi")

    def __str__(self):
        return f"{self.child_a.name} <-> {self.child_b.name}"


# ════════════════════════════════════════════════════════════════
# 3. FAMILY QUEST — Tjedni izazovi za cijelu obitelj
# ════════════════════════════════════════════════════════════════


class FamilyQuest(models.Model):
    """
    Tjedni obiteljski izazov — MOST iz digitalnog u stvarni život.

    Primjeri:
    - "Skuhajte zajedno bakin recept i fotografirajte jelo"
    - "Prošećite 3km i prebrojite prometne znakove"
    - "Intervjuirajte djeda o njegovom djetinjstvu"
    - "Posadite sjemenku i fotografirajte svaki dan 2 tjedna"
    - "Napravite ptičju kućicu od kutije za cipele"

    Bodovi idu OBITELJI, ne pojedincu.
    Roditelji MORAJU sudjelovati — to je poanta.
    """

    QUEST_TYPE_CHOICES = [
        ("cooking", _("Kuhanje")),
        ("outdoor", _("Aktivnost vani")),
        ("interview", _("Razgovor s bakama/djedovima")),
        ("craft", _("Rukotvorina")),
        ("nature", _("Priroda")),
        ("reading", _("Čitanje zajedno")),
        ("sport", _("Sport u obitelji")),
        ("culture", _("Kulturni izlet")),
        ("helping", _("Pomaganje u zajednici")),
        ("pet_care", _("Briga o ljubimcu")),
    ]

    SEASON_CHOICES = [
        ("any", _("Bilo kad")),
        ("spring", _("Proljeće")),
        ("summer", _("Ljeto")),
        ("autumn", _("Jesen")),
        ("winter", _("Zima")),
        ("advent", _("Advent")),
        ("easter", _("Uskrs")),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=300)
    title_de = models.CharField(max_length=300, blank=True)
    title_en = models.CharField(max_length=300, blank=True)
    quest_type = models.CharField(max_length=20, choices=QUEST_TYPE_CHOICES)
    season = models.CharField(max_length=10, choices=SEASON_CHOICES, default="any")

    # Opis zadatka
    description = models.TextField(help_text="Što treba napraviti — korak po korak")
    what_you_need = models.TextField(blank=True, help_text="Što vam treba (materijali, sastojci)")
    estimated_time = models.CharField(max_length=50, blank=True, help_text="30 min, 1 sat, 2 tjedna...")

    # Baka/Djed komentar
    grandma_tip = models.TextField(blank=True, help_text="Bakin savjet za ovaj quest")

    # Dokaz završetka
    requires_photo = models.BooleanField(default=True)
    requires_text = models.BooleanField(default=False)

    # Bodovi i veza
    family_points = models.PositiveSmallIntegerField(default=50)
    related_lesson = models.ForeignKey(
        "memio_world.LifeLesson",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="quests",
    )

    # Meta
    age_min = models.PositiveSmallIntegerField(default=3)
    age_max = models.PositiveSmallIntegerField(default=14)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "memio_world"
        db_table = "play_family_quest"
        ordering = ["quest_type", "title"]
        verbose_name = _("Obiteljski izazov")
        verbose_name_plural = _("Obiteljski izazovi")

    def __str__(self):
        return f"[{self.get_quest_type_display()}] {self.title}"


class FamilyQuestCompletion(models.Model):
    """Obitelj je završila quest — dokaz + bodovi."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quest = models.ForeignKey(FamilyQuest, on_delete=models.CASCADE, related_name="completions")
    child = models.ForeignKey(
        "memio_world.ChildProfile",
        on_delete=models.CASCADE,
        related_name="quest_completions",
    )
    completed_by_email = models.EmailField(help_text="Roditelj koji je potvrdio")
    photo = models.ImageField(upload_to="play_eu/quests/", blank=True)
    comment = models.TextField(blank=True, help_text="Komentar obitelji")
    points_awarded = models.PositiveSmallIntegerField(default=0)
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "memio_world"
        db_table = "play_family_quest_completion"
        ordering = ["-completed_at"]


# ════════════════════════════════════════════════════════════════
# 4. SPACED REPETITION — Leitner sustav
# ════════════════════════════════════════════════════════════════


class SpacedRepetitionCard(models.Model):
    """
    Leitner sustav — kartice se ponavljaju u rastućim intervalima.

    Kutija 1: svaki dan (novo/zaboravljeno)
    Kutija 2: svaka 2 dana
    Kutija 3: svaka 4 dana
    Kutija 4: svaki tjedan
    Kutija 5: svakih 2 tjedna (naučeno!)

    Točan odgovor → kartica ide kutiju gore.
    Krivi odgovor → kartica se vraća u Kutiju 1.

    Ovo je 3× efikasnije od klasičnog ponavljanja.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    child = models.ForeignKey(
        "memio_world.ChildProfile",
        on_delete=models.CASCADE,
        related_name="repetition_cards",
    )

    # Što se uči
    heritage_card = models.ForeignKey(
        "memio_world.HeritageCard",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="repetition_entries",
    )
    safety_topic = models.ForeignKey(
        "memio_world.SafetyTopic",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="repetition_entries",
    )
    custom_front = models.CharField(max_length=500, blank=True, help_text="Custom prednja strana")
    custom_back = models.TextField(blank=True, help_text="Custom stražnja strana")

    # Leitner kutija (1-5)
    box = models.PositiveSmallIntegerField(default=1, help_text="Leitner kutija 1-5")
    next_review = models.DateField(help_text="Kada se ponovo prikazuje")

    # Statistika
    times_correct = models.PositiveSmallIntegerField(default=0)
    times_wrong = models.PositiveSmallIntegerField(default=0)
    last_reviewed = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "memio_world"
        db_table = "play_spaced_card"
        ordering = ["next_review"]
        indexes = [
            models.Index(fields=["child", "next_review"]),
            models.Index(fields=["child", "box"]),
        ]

    def promote(self):
        """Točan odgovor → kutija gore, duži interval."""
        from datetime import timedelta

        from django.utils import timezone

        self.times_correct += 1
        self.box = min(5, self.box + 1)
        intervals = {1: 1, 2: 2, 3: 4, 4: 7, 5: 14}
        self.next_review = timezone.now().date() + timedelta(days=intervals[self.box])
        self.last_reviewed = timezone.now()

    def demote(self):
        """Krivi odgovor → natrag u Kutiju 1."""
        from datetime import timedelta

        from django.utils import timezone

        self.times_wrong += 1
        self.box = 1
        self.next_review = timezone.now().date() + timedelta(days=1)
        self.last_reviewed = timezone.now()


# ════════════════════════════════════════════════════════════════
# 5. PET BRIDGE — Veza s Memio.pet
# ════════════════════════════════════════════════════════════════


class PetBridgePost(models.Model):
    """
    Most između PLAY.EU i Memio.pet — sigurna zona za djecu i ljubimce.

    Dijete može:
    - Podijeliti fotografiju svog ljubimca (moderirana)
    - Napisati priču o ljubimcu
    - Odgovoriti na quest "Nauči svog psa novi trik" sa dokazom
    - Vidjeti ljubimce druge djece iz EU

    NEMA: lajkova, komentara od nepoznatih, DM-ova, followera.
    IMA: galeriju "Naši ljubimci", quest "Briga za ljubimca", edukaciju.

    Veza na Boxgram: samo preko moderiranog bridge-a, nikad direktno.
    Roditelj odobrava SVAKU objavu.
    """

    POST_TYPE_CHOICES = [
        ("photo", _("Fotografija ljubimca")),
        ("story", _("Priča o ljubimcu")),
        ("quest_proof", _("Dokaz quest-a")),
        ("tip", _("Savjet za brigu")),
        ("memorial", _("U sjećanje (preminuli ljubimac)")),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    child = models.ForeignKey(
        "memio_world.ChildProfile",
        on_delete=models.CASCADE,
        related_name="pet_posts",
    )
    post_type = models.CharField(max_length=20, choices=POST_TYPE_CHOICES)

    # Sadržaj
    title = models.CharField(max_length=200)
    text = models.TextField(blank=True)
    photo = models.ImageField(upload_to="play_eu/pets/", blank=True)

    # Ljubimac (ako je povezan s Memio.pet)
    pet_name = models.CharField(max_length=100)
    pet_species = models.CharField(max_length=50, blank=True, help_text="Pas, mačka, hrčak...")
    memio_pet_id = models.UUIDField(null=True, blank=True, help_text="FK na memio_pets bazu (cross-db)")

    # Moderacija
    parent_approved = models.BooleanField(default=False)
    ai_moderated = models.BooleanField(default=False)
    is_visible = models.BooleanField(default=False, help_text="Vidljivo tek kad parent + AI odobre")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "memio_world"
        db_table = "play_pet_bridge"
        ordering = ["-created_at"]
        verbose_name = _("Pet Bridge objava")
        verbose_name_plural = _("Pet Bridge objave")

    def __str__(self):
        return f"{self.child.name}: {self.pet_name} ({self.get_post_type_display()})"
