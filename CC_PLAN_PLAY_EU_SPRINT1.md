# PLAY.EU — Sprint 1 Plan
## Deadline: 2026-05-07 (Creative Europe)
## Status: AKTIVAN

---

## CILJ
Demo-ready MVP za Creative Europe prijavu:
- 3 Django modela u memio_world bazi
- Europeana API integracija (IIIF + Search)
- Višejezične paralelne priče (min 5 jezika)
- Heritage kartice (digitalne rekonstrukcije)
- Kviz engine s ocjenjivanjem

---

## FAZA 1: Modeli + Migracije (15-20.04)

### Model 1: EuropeanaItem
```python
# memio_world/models.py
class EuropeanaItem(models.Model):
    """
    Cache/proxy za Europeana API objekte.
    Ne kopiramo sadržaj — čuvamo metadata + thumbnail URL + rights info.
    Refresh via Celery task (tjedni sync novih items).
    """
    europeana_id = models.CharField(max_length=200, unique=True, db_index=True)
    title = models.CharField(max_length=500)
    title_hr = models.CharField(max_length=500, blank=True)
    title_de = models.CharField(max_length=500, blank=True)
    title_en = models.CharField(max_length=500, blank=True)
    description = models.TextField(blank=True)
    
    # Europeana metadata
    provider = models.CharField(max_length=200)  # "Gallica", "Deutsche Digitale Bibliothek"
    country = models.CharField(max_length=100)    # ISO country code
    data_provider = models.CharField(max_length=200, blank=True)
    
    # Media
    thumbnail_url = models.URLField(max_length=500, blank=True)
    media_url = models.URLField(max_length=500, blank=True)
    iiif_manifest = models.URLField(max_length=500, blank=True)
    media_type = models.CharField(max_length=50, choices=[
        ("IMAGE", "Slika"),
        ("SOUND", "Zvuk"),
        ("TEXT", "Tekst"),
        ("VIDEO", "Video"),
        ("3D", "3D objekt"),
    ])
    
    # Rights — KRITIČNO za legalnost
    rights = models.CharField(max_length=200)  # CC0, CC-BY, CC-BY-SA, etc.
    is_commercially_usable = models.BooleanField(default=False, db_index=True)
    attribution_text = models.TextField(blank=True)
    
    # Kategorija za djecu
    CATEGORY_CHOICES = [
        ("alphabet", "Slovarica / Abeceda"),
        ("counting", "Brojalica"),
        ("story", "Priča / Bajka"),
        ("song", "Pjesma"),
        ("game", "Igra"),
        ("illustration", "Ilustracija"),
        ("map", "Karta"),
        ("manuscript", "Rukopis"),
        ("bestiary", "Bestijarij"),
    ]
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, db_index=True)
    age_min = models.PositiveSmallIntegerField(default=3)
    age_max = models.PositiveSmallIntegerField(default=12)
    
    # Metadata
    year_created = models.IntegerField(null=True, blank=True)  # Godina nastanka originala
    original_language = models.CharField(max_length=10, blank=True)
    tags = models.JSONField(default=list, blank=True)
    
    # Admin
    is_curated = models.BooleanField(default=False)  # Ručno odabran za PLAY.EU
    is_active = models.BooleanField(default=True)
    fetched_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "play_europeana_item"
        ordering = ["-is_curated", "-year_created"]
        indexes = [
            models.Index(fields=["category", "is_commercially_usable"]),
            models.Index(fields=["country", "category"]),
        ]
    
    def __str__(self):
        return f"[{self.category}] {self.title[:60]}"
```

### Model 2: ParallelStory
```python
class ParallelStory(models.Model):
    """
    Ista priča na N jezika paralelno.
    Izvor: GrimmStories, Project Gutenberg, StoryWeaver (CC BY 4.0), ili original.
    """
    slug = models.SlugField(max_length=200, unique=True)
    title_hr = models.CharField(max_length=300)
    title_de = models.CharField(max_length=300, blank=True)
    title_en = models.CharField(max_length=300, blank=True)
    title_fr = models.CharField(max_length=300, blank=True)
    title_it = models.CharField(max_length=300, blank=True)
    title_es = models.CharField(max_length=300, blank=True)
    title_tr = models.CharField(max_length=300, blank=True)
    
    # Kategorija
    STORY_TYPE_CHOICES = [
        ("fairy_tale", "Bajka"),
        ("folk_tale", "Narodna priča"),
        ("fable", "Basna"),
        ("counting_rhyme", "Brojalica"),
        ("nursery_rhyme", "Uspavanка"),
        ("legend", "Legenda"),
        ("alphabet_story", "Slovarica"),
    ]
    story_type = models.CharField(max_length=20, choices=STORY_TYPE_CHOICES)
    
    # Izvor i prava
    SOURCE_CHOICES = [
        ("grimm", "Brothers Grimm (public domain)"),
        ("andersen", "H.C. Andersen (public domain)"),
        ("perrault", "Charles Perrault (public domain)"),
        ("storyweaver", "StoryWeaver (CC BY 4.0)"),
        ("gutenberg", "Project Gutenberg (public domain)"),
        ("europeana", "Europeana (various)"),
        ("original", "PLAY.EU original"),
        ("folk", "Narodna predaja (public domain)"),
    ]
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    source_url = models.URLField(blank=True)
    license = models.CharField(max_length=50, default="public_domain")
    attribution = models.TextField(blank=True)
    
    # Sadržaj po jezicima (TextField za priču, JSONField za strukturirani sadržaj)
    text_hr = models.TextField(blank=True)
    text_de = models.TextField(blank=True)
    text_en = models.TextField(blank=True)
    text_fr = models.TextField(blank=True)
    text_it = models.TextField(blank=True)
    text_es = models.TextField(blank=True)
    text_tr = models.TextField(blank=True)
    
    # Audio naracija (URL-ovi ili file path-ovi)
    audio_hr = models.FileField(upload_to="play_eu/audio/hr/", blank=True)
    audio_de = models.FileField(upload_to="play_eu/audio/de/", blank=True)
    audio_en = models.FileField(upload_to="play_eu/audio/en/", blank=True)
    
    # Ilustracije (veza na EuropeanaItem ili vlastite)
    cover_image = models.ForeignKey(
        EuropeanaItem, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="stories_as_cover"
    )
    illustrations = models.ManyToManyField(
        EuropeanaItem, blank=True, related_name="stories_as_illustration"
    )
    
    # Metapodaci
    age_min = models.PositiveSmallIntegerField(default=3)
    age_max = models.PositiveSmallIntegerField(default=10)
    reading_time_minutes = models.PositiveSmallIntegerField(default=5)
    difficulty_level = models.PositiveSmallIntegerField(default=1)  # 1-5
    country_of_origin = models.CharField(max_length=100, blank=True)
    moral_lesson = models.TextField(blank=True)  # Za učitelje
    
    # Status
    is_published = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)
    view_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "play_parallel_story"
        ordering = ["-is_featured", "-view_count"]
        verbose_name_plural = "Parallel stories"
    
    def available_languages(self):
        """Vraća listu jezika za koje postoji tekst."""
        langs = []
        for code in ("hr", "de", "en", "fr", "it", "es", "tr"):
            if getattr(self, f"text_{code}", "").strip():
                langs.append(code)
        return langs
    
    def __str__(self):
        return f"{self.title_hr} ({len(self.available_languages())} jezika)"
```

### Model 3: HeritageCard
```python
class HeritageCard(models.Model):
    """
    Digitalna rekonstrukcija starih europskih igara, slovarica, kartica.
    Le Quadrille des Enfans (1779), Hornbooks, Bestiarij kartice, etc.
    Svaka kartica = jedan interaktivni element u heritage igri.
    """
    # Identifikacija
    slug = models.SlugField(max_length=200, unique=True)
    title = models.CharField(max_length=300)
    title_hr = models.CharField(max_length=300, blank=True)
    title_de = models.CharField(max_length=300, blank=True)
    title_en = models.CharField(max_length=300, blank=True)
    
    # Tip kartice
    CARD_TYPE_CHOICES = [
        ("alphabet", "Slovo (A-Ž)"),
        ("number", "Broj (0-100)"),
        ("animal", "Životinja (bestijarij)"),
        ("game_piece", "Igra (Le Quadrille, Mlin)"),
        ("map_region", "Regija na karti"),
        ("instrument", "Glazbalo"),
        ("folk_costume", "Narodna nošnja"),
        ("landmark", "Znamenitost"),
    ]
    card_type = models.CharField(max_length=20, choices=CARD_TYPE_CHOICES)
    
    # Sadržaj
    front_text = models.CharField(max_length=200)  # Tekst na prednjoj strani
    back_text = models.TextField(blank=True)        # Objašnjenje na stražnjoj strani
    fun_fact = models.TextField(blank=True)          # Zanimljivost za djecu
    
    # Vizualno
    original_image = models.ForeignKey(
        EuropeanaItem, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="heritage_cards"
    )
    modern_illustration = models.ImageField(
        upload_to="play_eu/cards/", blank=True
    )
    background_color = models.CharField(max_length=7, default="#F5E6CC")  # Parchment
    
    # Heritage kontekst
    historical_period = models.CharField(max_length=100, blank=True)
    country_of_origin = models.CharField(max_length=100, blank=True)
    source_collection = models.CharField(max_length=200, blank=True)  # "Aberdeen Bestiary"
    year_created = models.IntegerField(null=True, blank=True)
    
    # Igra mehanika
    GAME_CHOICES = [
        ("memory", "Memory (parovi)"),
        ("quiz", "Kviz"),
        ("sequence", "Slagalica (redoslijed)"),
        ("matching", "Spajanje"),
        ("collection", "Kolekcija (sakupljanje)"),
    ]
    game_type = models.CharField(max_length=20, choices=GAME_CHOICES, blank=True)
    difficulty = models.PositiveSmallIntegerField(default=1)  # 1-5
    points_value = models.PositiveSmallIntegerField(default=10)
    
    # Set/Grupa — kartice idu u setove
    card_set = models.CharField(max_length=100, db_index=True)  # "grimm_bestiary", "hr_alphabet"
    position_in_set = models.PositiveSmallIntegerField(default=0)
    
    # Status
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = "play_heritage_card"
        ordering = ["card_set", "position_in_set"]
        indexes = [
            models.Index(fields=["card_type", "is_published"]),
            models.Index(fields=["card_set", "position_in_set"]),
        ]
    
    def __str__(self):
        return f"[{self.card_set}] {self.front_text}"
```

---

## FAZA 2: Europeana API Integracija (20-25.04)

### Task 2.1: API Client
- `memio_world/europeana_client.py`
- Search API wrapper s rate limiting
- IIIF Manifest parser za slike
- Filter: `reusability=open` → samo CC0/CC-BY
- Cache rezultata u Redis (TTL 24h)

### Task 2.2: Sync Command
- `manage.py europeana_sync --category alphabet --limit 100`
- Povlači items iz Europeana, kreira EuropeanaItem zapise
- Dedup po europeana_id
- Auto-detect commercially_usable iz rights polja

### Task 2.3: Celery Beat
- `europeana_weekly_sync` @ nedjelja 04:00
- Sync novih items po svim kategorijama
- Max 500 items/tjedan (API fair use)

---

## FAZA 3: Sadržaj (25-30.04)

### Task 3.1: Grimm Priče (5 jezika)
- Scrape GrimmStories.com (13 jezika dostupno, public domain)
- Import u ParallelStory: HR, DE, EN, FR, IT
- Min 20 bajki za demo

### Task 3.2: Bestiarij Kartice
- Aberdeen Bestiary items via Europeana
- HeritageCard set: "aberdeen_bestiary"
- 30 kartica (životinje s ilustracijama)
- Memory game mehanika

### Task 3.3: HR Slovarica
- HeritageCard set: "hr_alphabet"
- 30 kartica (A-Ž + Č, Ć, Đ, Š, Ž)
- Ilustracije iz Europeana + Gallica abécédaires
- Quiz mehanika

---

## FAZA 4: Kviz Engine (30.04-05.05)

### Task 4.1: Quiz Model
- `memio_world/quiz_models.py`
- Quiz, QuizQuestion, QuizAnswer, QuizAttempt, QuizResult
- Podržava: multiple choice, matching, sequence, true/false
- Auto-grading
- Difficulty progression (adaptivna težina)

### Task 4.2: Teacher Dashboard
- Kreiranje kvizova iz HeritageCard setova
- Dodijeljivanje kao domaća zadaća
- Rezultati po učeniku / razredu
- CSV export ocjena

### Task 4.3: Parent Dashboard
- Pregled djetetovog napretka
- Područja za poboljšanje
- Preporučeni sadržaj

---

## FAZA 5: Demo UI (05-07.05)

### Task 5.1: PWA Shell
- Responsive, mobile-first
- Offline capable (Service Worker)
- Parchment/medieval vizualni stil

### Task 5.2: 3 Demo Scenarija
1. Dijete bira bajku → čita na HR → prebacuje na DE → sluša audio
2. Učitelj kreira kviz iz bestiarij kartica → učenici igraju memory
3. Roditelj pregledava napredak → vidi koje jezike dijete uči

---

## METRIKE ZA CREATIVE EUROPE PRIJAVU
- 20+ višejezičnih priča
- 60+ heritage kartica (bestiarij + slovarica)
- 3 igre mehanike (memory, kviz, slagalica)
- 5+ EU jezika
- GDPR-compliant (parent consent flow)
- Europeana API integracija s 100+ cultural items
- Offline PWA

---

## ROUTING NA HEAVY QUEUE
- Svi AI/Europeana taskovi idu na `heavy` queue
- Ne smiju blokirati POS fiskalizaciju ili WhatsApp

## DISK PROCJENA
- 3 modela, max 10K redova u prvoj fazi
- Slike: thumbnailovi, ne full-res (Europeana hostira originale)
- Audio: max 20 priča × 3 jezika × ~2MB = ~120MB
- Ukupno: <200MB od 85GB slobodnih

## TROŠKOVI
- Europeana API: besplatan
- DeepSeek za prijevode: ~$0.05/dan
- Ukupno Sprint 1: <$5
