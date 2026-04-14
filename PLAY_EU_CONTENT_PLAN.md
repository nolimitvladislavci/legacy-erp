# PLAY.EU — SADRŽAJNI PLAN I ARHITEKTURA
> Status: DAN 48 | Verificirano: 2026-04-14 | Autor: Sonnet/Ivan Brtan
> Deadline Creative Europe: **7. svibnja 2026** (animation track)

---

## FILOZOFIJA: GDJE ŽIVIM, GDJE SE POVEŽEM

```
SERVER (naš Hetzner, 85GB slobodno):
  → Sadržaj koji transformiramo, obogaćujemo, serviramo offline
  → Naš value-add: meta podaci, AI enrichment, parallelnost, DialectMap veze
  → Bez vanjskih ovisnosti = PWA offline radi

EMBED/LINK (vanjski portal):
  → Sadržaj koji je već savršen kakav jest
  → Video (YouTube), interaktivni alati (LearningApps), igre (lichess)
  → Ne dupliciramo ono što netko drugi savršeno radi
```

---

## TOP 3 — HOSTED NA NAŠEM SERVERU

### SERVER-1: Europeana CC0 Kurirani Seed
**Zašto server:** Srce EU funding priče. Offline PWA. AI enrichment. Naš DB.

```
Što preuzimamo:
  - 500 objekata (bestijariji, iluminirani rukopisi, folk-audio, abecedne knjige)
  - Filtar: reusability=open, type=IMAGE|SOUND, provider=bestijariji/folk/abeceda
  - API: api.europeana.eu/record/ + IIIF za slike

Što radimo s tim:
  - EuropeanaItem model → naš DB
  - Slike: thumbnail (200px) na serveru, full-res IIIF link (ne preuzimamo)
  - Audio: preuzimamo MP3 za offline (folk pesme, uspavanke)
  - AI enrichment: Haiku generira "priča za djecu" za svaki objekt na HR/DE/EN
  - Veza s DialectMap: Aberdeen Bestiary zmaj ↔ dialektna riječ "zmaj/dragon/Drache"
  - Veza s TraditionalGame: folk instrument ↔ igra iz te regije

Prioritetni objekti za seed:
  1. Aberdeen Bestiary (~1200 AD) — zmajevi, jednorozci, feniksi [Aberdeen Univ.]
  2. Latvijske folk pjesme 1930-ih [Latvian National Archives]
  3. Gallica abecedne knjige 17-18.st. [BnF]
  4. Hornbooks (drvene abecedne tablice, 15-17.st.) [British Museum via Europeana]
  5. Středovjekovni iluminirani rukopisi — životinje [različiti EU muzeji]

Model koji treba:
  EuropeanaItem(
    europeana_id, title, description_hr, description_de, description_en,
    item_type [bestiary/folk_song/alphabet/game],
    thumbnail_local_path, iiif_url, audio_local_path,
    country_of_origin, era, license,
    ai_story_hr, ai_story_de, ai_story_en,
    related_game FK(TraditionalGame), related_dialect FK(DialectMap),
    age_min, is_published, play_count
  )

Trošak pohrane:
  500 thumbnail-a × ~20KB = ~10MB
  100 audio × ~3MB = ~300MB
  UKUPNO: ~310MB (zanemarivo)

EU funding vrijednost: MAKSIMALNA
  → Direktna veza s Europeana Foundation (konzorcij partner potencijal)
  → "Mi KORISTIMO EU baštinu, ne samo govorimo o njoj"
```

---

### SERVER-2: Grimm Paralelni Korpus (13 EU jezika)
**Zašto server:** Flagship pedagoška funkcija. Offline radi. Naš UI, naša analitika.

```
Izvor: GrimmStories.com + Project Gutenberg (public domain, ≥70 god. od smrti)
Bajke: ~200 Grimmovih bajki × 13 jezika = ~2600 tekstualnih zapisa

Što radimo:
  - Scrapamo/preuzimamo jednom (public domain, smijemo)
  - StoryBook model → proširujemo s parallel_id grupiranjem
  - ParallelStory(story_id, language_code, title, content, source_url)
    → 13 zapisa po bajki, grupirani po slug-u ("sneewittchen")
  - Paralelni čitač: dijete vidi HR | DE | EN side-by-side
  - AI: Haiku generira pitanja za razumijevanje na svakom jeziku
  - Veza s TraditionalGame: Crvenkapica ↔ igre iz Schwarzwälda regije
  - Veza s DialectMap: "Großmutter" ↔ dialektna Schwäbisch verzija

Model koji treba:
  ParallelStory(
    group_slug, language_code, title, content_text,
    source StoryBook FK ili standalone,
    reading_level [1-5], word_count,
    ai_quiz_data JSONField,
    created_at
  )

Trošak pohrane:
  2600 tekstova × ~5KB = ~13MB (zanemarivo)

EU funding vrijednost: VISOKA
  → Višejezičnost = core EU vrijednost
  → "Ista Crvenkapica na 13 jezika" = novinarska priča
  → Učitelji to odmah razumiju
```

---

### SERVER-3: Le Quadrille des Enfans (1779) — Rekonstrukcija
**Zašto server:** Flagship VAU objekt. Nitko to nije napravio. Naše intelektualno vlasništvo nad rekonstrukcijom.

```
Izvor: Gallica BnF (gallica.bnf.fr) — originalni bakrorezni skenirani listovi
Status: Public domain (1779, >70 god.) — smijemo sve

Što je to: Karte za djecu iz 1779. — bakrorez sa životinjama, slovima, brojevima.
Henry Laurens (pariški nakladnik) ih je tiskao da djeca sjeckaju i igraju.
Digitalizirano u visokoj rezoluciji, dostupno na Gallica. Nikada rekonstruirano.

Što radimo:
  Faza 1 — Digitalna rekonstrukcija (statična):
    - Preuzimamo skenove s Gallice (IIIF, potpuno legalno)
    - Svaka karta = posebna slika na serveru
    - Abeceda A-Z + životinje + brojevi kao kolekcija
    - Prikaz djeci: "Vidiš ovu kartu? Ima 244 godine!"

  Faza 2 — Interaktivna igra (MVP):
    - Memory igra: uparivanje slova s ilustracijom
    - Abeceda igra: "Kojim slovom počinje ova životinja?"
    - Karta u originalnom stilu kao UI element (CSS/SVG)
    - Zvuk: klik na kartu → ime životinje na HR/DE/FR

  Faza 3 — Puna rekonstrukcija (post-funding):
    - Multiplayer kartaška igra s originalnim pravilima iz 1779.
    - Tiskanje: "Napravi svoju Quadrille!" PDF download
    - EU škole: set fizičkih karata kao merchandise

Model koji treba:
  HeritageCard(
    europeana_id ali i gallica_ark,
    card_type [letter/animal/number/scene],
    letter_depicted, animal_name_fr, animal_name_hr, animal_name_de,
    scan_local_path, thumbnail_path,
    year_created INT (1779),
    fun_fact_hr, fun_fact_de,
    game_engine_data JSONField
  )

Trošak pohrane:
  26 slova + ~50 scenskih karata = ~76 karata × ~2MB skena = ~150MB
  Thumbnails: ~76 × 50KB = ~4MB
  UKUPNO: ~154MB (prihvatljivo)

EU funding vrijednost: MAKSIMALNA — ovo je THE differenciator
  → BnF (Gallica) kao potencijalni partner/endorsement
  → "Prva digitalna rekonstrukcija Le Quadrille des Enfans od 1779."
  → Novinarski hook: "Napravi 244-godišnju igru s djecom"
```

---

## EMBED/LINK — VANJSKI PORTALI (ne manje važno!)

```
Strategija: Embed gdje je moguće. Link gdje nije. NIKAD ne dupliciramo.
```

### EMBED-1: LearningApps.org — Kvizovi
```
Tip: iframe embed (potpuno slobodan)
Što embedamo: Kvizovi na HR jeziku za djecu
Naša uloga: Kurator + kontekstualizator
  → "Ovaj kviz je uz bajku Crvenkapica"
  → Veza s ParallelStory i EuropeanaItem
Offline: NE — ali kvizovi su bonusi, ne core
```

### EMBED-2: lichess.org — Šah
```
Tip: iframe embed (open source, MIT licenca)
Što embedamo: Šah za početnike, besplatne lekcije
Naša uloga: "Šah je europska igra od 6.st. — evo gdje početi"
Veza s TraditionalGame: "Petteia (Grčka, 600 pr.Kr.) → predak šaha"
```

### EMBED-3: YouTube — Alphablocks (BBC)
```
Tip: YouTube embed
Što embedamo: Abecedne animacije (EN) za djecu 3-6 god.
Naša uloga: Contextualizacija + "Uz ovu epizodu: naša interaktivna karta iz 1779."
GDPR: YouTube embed s privacy-enhanced mode (youtube-nocookie.com)
```

### EMBED-4: Gallicadabra (BnF) — Priče s naracijom
```
Tip: Deep link (ne iframe — ne podržava)
Što linkamo: 58 priča s glumačkom naracijom na FR
Naša uloga: "Za naše frankofonske korisnike — direktno na BnF"
Vrijednost: Pokazuje da radimo s institucijama, ne konkuriramo
```

### EMBED-5: StoryWeaver (Pratham) — 40K priča
```
Tip: API (CC BY 4.0) + deep link
Što koristimo: API za dohvat metapodataka + link na originale
NE preuzimamo: Slike i tekst — preveliko, CC BY 4.0 zahtijeva atribuciju
Naša uloga: Discovery layer — "Pronađi priče na svom jeziku"
```

### LINK-6: Mama Lisa's World — Brojalice
```
Tip: External link (ad-supported, ne može iframe)
Što linkamo: Brojalica na HR/DE + audio + note
Naša uloga: "Ova brojalica iz Dalmacije — slušaj original na Mama Lisa"
Vrijednost: 200+ zemalja = globalni kontekst naše lokalne baštine
```

### LINK-7: IMSLP — Notni zapisi
```
Tip: External link
Što linkamo: Notni zapisi dječjih pjesama (Schumann Album für die Jugend itd.)
Naša uloga: "Za učitelje glazbe — tiskaj note besplatno"
```

### LINK-8: eLektire (MZO) — HR Lektira
```
Tip: External link (državni portal)
Što linkamo: Schulska lektira HR
Naša uloga: "Pročitaj originalnu lektiru — mi nudimo kontekst i igru"
Partnerstvo: Moguć MZO endorsement za EU prijavu!
```

---

## NOVI MODELI POTREBNI (za implementaciju)

```python
# memio_world/models.py — proširenje

class EuropeanaItem(models.Model):
    """Europeana CC0 objekt preuzet na naš server."""
    europeana_id    = models.CharField(max_length=200, unique=True)
    title           = models.CharField(max_length=500)
    description_hr  = models.TextField(blank=True)
    description_de  = models.TextField(blank=True)
    description_en  = models.TextField(blank=True)
    item_type       = models.CharField(max_length=30,
                        choices=[('bestiary','Bestijarij'), ('folk_song','Folk Pjesma'),
                                 ('alphabet','Abeceda'), ('game','Igra'), ('manuscript','Rukopis')])
    thumbnail_path  = models.CharField(max_length=500, blank=True)  # lokalni path
    iiif_url        = models.URLField(blank=True)                   # full-res vanjski
    audio_path      = models.CharField(max_length=500, blank=True)  # lokalni MP3
    country_origin  = models.CharField(max_length=100, blank=True)
    era             = models.CharField(max_length=100, blank=True)
    license         = models.CharField(max_length=50, default='CC0')
    # AI enrichment
    ai_story_hr     = models.TextField(blank=True)
    ai_story_de     = models.TextField(blank=True)
    ai_story_en     = models.TextField(blank=True)
    # Veze s postojećim modelima
    related_game    = models.ForeignKey('TraditionalGame', null=True, blank=True,
                        on_delete=models.SET_NULL, related_name='europeana_items')
    related_dialect = models.ForeignKey('DialectMap', null=True, blank=True,
                        on_delete=models.SET_NULL, related_name='europeana_items')
    age_min         = models.PositiveSmallIntegerField(default=3)
    is_published    = models.BooleanField(default=False)
    play_count      = models.PositiveIntegerField(default=0)
    created_at      = models.DateTimeField(auto_now_add=True)


class ParallelStory(models.Model):
    """Ista bajka na više EU jezika."""
    group_slug      = models.SlugField(max_length=100, db_index=True)
    language_code   = models.CharField(max_length=5)    # hr, de, en, fr...
    title           = models.CharField(max_length=300)
    content_text    = models.TextField()
    source_url      = models.URLField(blank=True)        # Gutenberg/GrimmStories
    reading_level   = models.PositiveSmallIntegerField(default=3)  # 1-5
    word_count      = models.PositiveIntegerField(default=0)
    ai_quiz_data    = models.JSONField(default=dict, blank=True)
    related_game    = models.ForeignKey('TraditionalGame', null=True, blank=True,
                        on_delete=models.SET_NULL)
    is_published    = models.BooleanField(default=False)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('group_slug', 'language_code')]
        indexes = [models.Index(fields=['group_slug', 'language_code'])]


class HeritageCard(models.Model):
    """Le Quadrille des Enfans (1779) — rekonstruirane karte."""
    gallica_ark     = models.CharField(max_length=200, unique=True)
    card_type       = models.CharField(max_length=20,
                        choices=[('letter','Slovo'), ('animal','Životinja'),
                                 ('number','Broj'), ('scene','Scena')])
    letter_depicted = models.CharField(max_length=1, blank=True)  # A-Z
    animal_name_fr  = models.CharField(max_length=100, blank=True)
    animal_name_hr  = models.CharField(max_length=100, blank=True)
    animal_name_de  = models.CharField(max_length=100, blank=True)
    scan_path       = models.CharField(max_length=500, blank=True)   # lokalni path visoke rez.
    thumbnail_path  = models.CharField(max_length=500, blank=True)
    year_created    = models.IntegerField(default=1779)
    fun_fact_hr     = models.TextField(blank=True)
    fun_fact_de     = models.TextField(blank=True)
    game_engine_data = models.JSONField(default=dict, blank=True)   # za memory/abeceda igru
    order           = models.PositiveSmallIntegerField(default=0)
    is_published    = models.BooleanField(default=False)
    created_at      = models.DateTimeField(auto_now_add=True)
```

---

## CELERY TASKOVI ZA PREUZIMANJE

```python
# memio_world/tasks_content.py

@shared_task
def fetch_europeana_seed(query: str, item_type: str, max_items: int = 100):
    """Preuzmi Europeana CC0 objekte, spremi u EuropeanaItem."""
    # Europeana REST API → filter reusability=open
    # Download thumbnail → /var/www/fina-connect/media/europeana/{id}/thumb.jpg
    # Download audio (ako postoji) → /var/www/fina-connect/media/europeana/{id}/audio.mp3
    # Haiku AI enrichment → ai_story_hr/de/en
    pass

@shared_task
def fetch_parallel_stories(group_slug: str, languages: list):
    """Preuzmi Grimm bajku u svim jezicima s Gutenberga/GrimmStories."""
    # Project Gutenberg API za svaki jezik
    # Spremi kao ParallelStory
    # Haiku generira kviz pitanja → ai_quiz_data
    pass

@shared_task
def fetch_quadrille_cards():
    """Preuzmi Le Quadrille des Enfans s Gallice (IIIF)."""
    # Gallica IIIF manifest → lista karata
    # Download thumb za svaku kartu
    # AI: generiraj fun_fact na HR/DE
    pass
```

---

## REDOSLIJED IMPLEMENTACIJE

```
SPRINT 1 (ova sesija → do 7.5.2026):
  [ ] 1. EuropeanaItem model + migracija (30 min)
  [ ] 2. ParallelStory model + migracija (20 min)
  [ ] 3. HeritageCard model + migracija (20 min)
  [ ] 4. fetch_europeana_seed task — Aberdeen Bestiary seed (2h)
       → Cilj: 50 objekata u bazi s AI enrichmentom
  [ ] 5. fetch_parallel_stories — 10 Grimm bajki × 3 jezika (HR/DE/EN) (2h)
  [ ] 6. fetch_quadrille_cards — svi listovi iz 1779. (1h)
  [ ] 7. Osnovne view-e + template za prezentaciju (4h)
       → /world/bestiarij/ — Aberdeen Bestiary interaktivno
       → /world/bajke/crvenkapica/ — paralelni čitač HR|DE|EN
       → /world/quadrille/ — karte iz 1779. s memory igrom
  [ ] 8. Demo URL za EU evaluatore (dangled from landing page)

SPRINT 2 (post-aplikacija):
  [ ] 9. Puni Europeana seed (500 objekata)
  [ ] 10. Svih 200 Grimm bajki × 13 jezika
  [ ] 11. Interaktivna Quadrille memory igra (JS)
  [ ] 12. LearningApps embed integracija uz bajke
  [ ] 13. lichess embed uz TraditionalGame "Šah"
  [ ] 14. Roditeljski dashboard + napredak djeteta

SPRINT 3 (nakon EU odobrenja):
  [ ] 15. Europeana Foundation partnerstvo (formalno)
  [ ] 16. MZO endorsement (eLektire)
  [ ] 17. Offline PWA build
  [ ] 18. Multiplayer Quadrille igra
```

---

## GDPR/PRAVNI CHECKPOINTS

```
Prije launcha OBAVEZNO:
  [ ] DPIA (procjena utjecaja) — jer obrađujemo dječje podatke
  [ ] DPO imenovanje (ili procjena da nije obavezno)
  [ ] Roditelj kreira account → dodaje dječji profil (ne dijete direktno)
  [ ] DSA čl. 28: NULA reklama usmjerenih na djecu
  [ ] DSA čl. 25: Bez dark patterns (nema "još samo 5 min!")
  [ ] NightProtocol: ekran se "zatvori" u 20:00 za djecu do 8 god. — GDPR + DE JuSchG
  [ ] Svaki Europeana objekt: provjeri license field u API odgovoru
  [ ] Mali Princ: NE koristiti (FR ratna iznimka do ~2045)
  [ ] Pre-1956 FR autori: provjeri svaki slučaj posebno

Dob digitalnog pristanka:
  → Roditelja treba za: HR (do 16), DE (do 16), FR (do 15)
  → Naš model: roditelj UVIJEK kreira — rješava sve jurisdikcije odjednom
```

---

## EU FUNDING — SADRŽAJNE POZICIJE (update)

```
NOVA POZICIJA 6 — Europeana kao okosnica:
  "Jedina platforma koja Europeana CC0 baštinu pretvara u 
   interaktivno obrazovno iskustvo za djecu na 13 EU jezika"

NOVA POZICIJA 7 — Le Quadrille des Enfans:
  "Prva digitalna rekonstrukcija europske dječje igre iz 1779. —
   od papirnih bakroreznih karata do interaktivne web igre"

NOVA POZICIJA 8 — Gallicadabra model × 27:
  "BnF je dokazala da model radi za Francusku.
   PLAY.EU je isti model za cijelu EU — 27 zemalja, 24 jezika"

NOVA POZICIJA 9 — Pravni okvir:
  "GDPR by design, DSA compliant, AI Act ethical layer —
   jedina dječja platforma koja ima sve tri regulatorne osi pokrivene od Dana 1"
```

---

## SERVERI I POHRANA

```
/var/www/fina-connect/media/
  europeana/
    {europeana_id}/
      thumb.jpg        (~20KB, naš server)
      audio.mp3        (~3MB, samo ako postoji, naš server)
      [full-res → IIIF URL, ne preuzimamo]
  quadrille_1779/
    {ark_id}/
      scan_hd.jpg      (~2MB, naš server)
      thumb.jpg        (~50KB, naš server)
  stories/
    [tekst u DB, ne fajlovi]

Ukupna procjena:
  Europeana seed (500): ~310MB
  Quadrille (76 karata): ~154MB
  Audio (100 folk): ~300MB
  UKUPNO: ~764MB — na 85GB slobodnih = 0.9% diska
```

---

## COMMIT PORUKA ZA OVAJ DOKUMENT

```
docs: PLAY.EU content architecture — server vs embed strategy
Definiran SERVER-3 vs EMBED-8 model
Nova pozicija: Le Quadrille des Enfans rekonstrukcija
Nova pozicija: Europeana CC0 okosnica
3 nova modela: EuropeanaItem + ParallelStory + HeritageCard
Sprint 1 plan: do 7.5.2026 (Creative Europe deadline)
```
