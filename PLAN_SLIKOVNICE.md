# PLAY.EU — SLIKOVNICE (Picture Book Engine)
> Tri glave, jedan proizvod. Kvaliteta na prvom mjestu.
> Status: PLANIRANJE | Deadline: Creative Europe 2026-05-07

---

## VIZIJA

Svaka priča = prava digitalna slikovnica.
- Naslovnica: full-bleed slika, naslov, klikni za početak
- Stranica po stranica: ilustracija + tekst, listanje kao prava knjiga
- Zadnja stranica: pouka + "Čitaj na drugom jeziku"
- Audio: naracija na svakom jeziku (baka čita priču)
- Stil: topli watercolor na parchment papiru — PLAY.EU potpis

## BROJKE

```
10 priča × 9 stranica (naslovnica + 7 unutarnjih + zadnja) = 90 ilustracija
10 priča × 3 jezika × audio = 30 audio fajlova
10 priča × 3 jezika × tekst = podjela u stranice
```

## PRIČE (published)

| # | Slug | Naslov (HR) | Paragrafa | Stranica |
|---|------|-------------|-----------|----------|
| 1 | rapunzel | Rapunzel | 7 | 9 |
| 2 | cinderella | Pepeljuga | 6 | 8 |
| 3 | snow-white | Snjeguljica | 8 | 10 |
| 4 | sleeping-beauty | Trnoružica | 7 | 9 |
| 5 | hansel-and-gretel | Ivica i Marica | 7 | 9 |
| 6 | little-red-riding-hood | Crvenkapica | 7 | 9 |
| 7 | the-frog-prince | Kraljević Žabac | 8 | 10 |
| 8 | the-star-money | Zvjezdani taliri | 4 | 6 |
| 9 | the-town-musicians-of-bremen | Bremenski glazbenici | 8 | 10 |
| 10 | the-wolf-and-the-seven-young-goats | Vuk i sedam kozlića | 8 | 10 |

**Ukupno: 90 stranica = 90 ilustracija**

---

# GLAVA 1 — BACKEND & DATA MODEL
**Tko:** Opus CC (ili ekvivalent)
**Što:** Model, migracija, API, management commands

## 1.1 StoryPage model

```python
class StoryPage(models.Model):
    """Jedna stranica slikovnice — ilustracija + tekst + audio."""

    PAGE_TYPE_CHOICES = [
        ("cover", "Naslovnica"),          # samo slika + naslov
        ("inner", "Unutarnja stranica"),   # ilustracija + tekst
        ("back", "Zadnja stranica"),       # pouka + CTA
    ]

    LAYOUT_CHOICES = [
        ("full_bleed", "Slika preko cijele stranice"),
        ("top_image", "Slika gore, tekst dolje"),
        ("bottom_image", "Tekst gore, slika dolje"),
        ("left_image", "Slika lijevo, tekst desno"),
        ("split_50_50", "Pola slika, pola tekst"),
        ("text_overlay", "Tekst preko slike (proziran)"),
    ]

    id = UUIDField(primary_key=True)
    story = FK(ParallelStory, related_name="pages")
    page_number = PositiveSmallIntegerField()  # 0 = naslovnica
    page_type = CharField(choices=PAGE_TYPE_CHOICES)
    layout = CharField(choices=LAYOUT_CHOICES, default="top_image")

    # Ilustracija
    image = ImageField(upload_to="play_eu/pages/")
    image_thumbnail = ImageField(upload_to="play_eu/pages/thumbs/", blank=True)
    image_alt_text = CharField(max_length=500)
    image_prompt = TextField(help_text="AI prompt koji je generirao sliku")
    image_style = CharField(max_length=30, default="watercolor_parchment")
    image_source = CharField(choices=[
        ("ai_generated", "AI generirano"),
        ("europeana", "Europeana"),
        ("original", "Originalna ilustracija"),
        ("public_domain", "Javna domena"),
    ])
    image_approved = BooleanField(default=False)  # Ručna provjera kvalitete

    # Tekst po jezicima (jedan paragraf ili dva po stranici)
    text_hr = TextField(blank=True)
    text_de = TextField(blank=True)
    text_en = TextField(blank=True)

    # Audio naracija
    audio_hr = FileField(upload_to="play_eu/audio/pages/hr/", blank=True)
    audio_de = FileField(upload_to="play_eu/audio/pages/de/", blank=True)
    audio_en = FileField(upload_to="play_eu/audio/pages/en/", blank=True)

    # Vizualno
    background_color = CharField(max_length=7, default="#FDF6E3")
    text_color = CharField(max_length=7, default="#2D1B00")

    # Meta
    scene_description = TextField(help_text="Opis scene za AI/ilustratora")
    is_published = BooleanField(default=False)
    created_at = DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("story", "page_number")
        ordering = ["story", "page_number"]
```

## 1.2 StoryBookStyle model

```python
class StoryBookStyle(models.Model):
    """Vizualni stil za grupu slikovnica — konzistentnost."""

    name = CharField(max_length=100)  # "PLAY.EU Watercolor"
    slug = SlugField(unique=True)

    # AI prompt prefiks (dodaje se svakom promptu)
    prompt_prefix = TextField()
    # npr: "Children's storybook watercolor illustration,
    #       parchment paper texture, warm golden light,
    #       soft edges, European folk art style,
    #       safe for children, no text in image,"

    prompt_suffix = TextField(blank=True)
    # npr: "8K, detailed, Caldecott Medal quality"

    # Negativni prompt (što izbjegavati)
    negative_prompt = TextField(blank=True)
    # npr: "scary, violent, blood, weapons, nudity,
    #       realistic faces, photographic, text, watermark"

    # Vizualni parametri
    dominant_palette = JSONField(default=list)
    # npr: ["#FDF6E3", "#C9A84C", "#8B4513", "#2D5F2D", "#1B4F72"]

    font_family = CharField(max_length=100, default="Cormorant Garamond")
    page_texture = CharField(max_length=50, default="parchment")

    is_default = BooleanField(default=False)
```

## 1.3 Management commands

```
manage.py split_story_into_pages <slug>
  → Automatski dijeli paragraf teksta u stranice
  → Kreira StoryPage skeleton (bez slika)
  → Generira scene_description za svaku stranicu

manage.py split_all_stories
  → Pokreće split za svih 10 priča

manage.py generate_illustration <page_id> [--provider=dall-e|midjourney|sd]
  → Poziva AI API s prompt_prefix + scene_description + prompt_suffix
  → Sprema sliku u media/play_eu/pages/
  → Kreira thumbnail

manage.py generate_all_illustrations <story_slug> [--provider=dall-e]
  → Batch za sve stranice jedne priče

manage.py generate_audio <page_id> <lang> [--provider=google|elevenlabs]
  → TTS naracija za jednu stranicu
  → Sprema u media/play_eu/audio/pages/<lang>/

manage.py generate_all_audio <story_slug>
  → Batch za sve stranice × sve jezike
```

## 1.4 API / Views

```
GET /api/memio-world/play/book/<slug>/
  → Vraća JSON sa svim stranicama (za JS book reader)
  → { pages: [{page_number, image_url, text, audio_url, layout}, ...] }

GET /api/memio-world/play/book/<slug>/page/<n>/
  → Pojedinačna stranica (za lazy loading)
```

## 1.5 Zadaci (redom)

| # | Zadatak | Output | Procjena |
|---|---------|--------|----------|
| 1.1 | StoryPage + StoryBookStyle model | 2 modela, migracija | — |
| 1.2 | split_story_into_pages command | 10 priča × ~9 stranica = 90 skeletons | — |
| 1.3 | scene_description auto-generacija | AI opisuje scenu iz teksta za svaku str. | — |
| 1.4 | generate_illustration command | DALL-E / SD integracija | — |
| 1.5 | generate_audio command | Google TTS / ElevenLabs | — |
| 1.6 | Book reader API endpoint | JSON za frontend | — |
| 1.7 | Admin review view | Pregled + approve slike | — |
| 1.8 | Thumbnail generacija | Pillow resize 400px | — |

---

# GLAVA 2 — FRONTEND SLIKOVNICA READER
**Tko:** Frontend agent (CC ili čovjek)
**Što:** Book flip UI, cover, stranica, animacije, audio player

## 2.1 Book Reader komponenta

```
Iskustvo:
  1. Korisnik vidi NASLOVNICU — velika slika, naslov preko nje, "Otvori" gumb
  2. Klik → knjiga se "otvara" (CSS 3D animacija)
  3. Stranica po stranica — swipe lijevo/desno ili strelice
  4. Svaka stranica: ilustracija + tekst (layout ovisi o page.layout)
  5. Audio ikona na svakoj stranici — klik = baka čita
  6. Language switch — mijenja tekst + audio bez gubitka pozicije
  7. Zadnja stranica: pouka, "Čitaj na DE", "Čitaj drugu priču"
  8. Fullscreen gumb za imerzivni doživljaj
```

## 2.2 Template struktura

```
templates/memio_world/
  book_cover.html          — naslovnica (standalone, klikabilna)
  book_reader.html         — full reader (page flip JS)
  _book_page_cover.html    — fragment: naslovnica layout
  _book_page_inner.html    — fragment: unutarnja stranica (6 layouta)
  _book_page_back.html     — fragment: zadnja stranica
  _book_audio_player.html  — fragment: mini audio player
```

## 2.3 CSS — Book Flip Engine

```css
/* Page flip — CSS 3D transforms */
.book-container {
  perspective: 1500px;
  /* Dimenzije: 4:3 landscape na desktopu, portrait na mobitelu */
}
.book-page {
  transform-style: preserve-3d;
  transition: transform 0.8s cubic-bezier(0.645, 0.045, 0.355, 1);
  /* Sjena koja se miče sa stranicom */
}
.book-page.turning {
  transform: rotateY(-180deg);
  /* Zvuk lista papira (Web Audio API) */
}
```

## 2.4 JavaScript — Swipe + Navigation

```
- Hammer.js ili vanilla touch events za swipe
- Keyboard: ← → za navigaciju, F za fullscreen, Space za audio
- Preload: učitaj sljedeću i prethodnu stranicu unaprijed
- Progress bar: tanki zlatni bar na dnu (koja si stranica od ukupno)
- Auto-play mode: audio + auto-flip kad završi naracija
```

## 2.5 Layout varijante (6 tipova)

```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│              │  │    IMAGE     │  │    TEXT       │
│    IMAGE     │  │              │  │              │
│  (full bleed)│  ├──────────────┤  ├──────────────┤
│              │  │    TEXT      │  │    IMAGE     │
│   + naslov   │  │              │  │              │
└──────────────┘  └──────────────┘  └──────────────┘
   cover             top_image         bottom_image

┌───────┬──────┐  ┌──────────────┐  ┌──────────────┐
│       │      │  │  IMG │ TEXT  │  │   IMAGE      │
│ IMAGE │ TEXT │  │      │      │  │  + overlay   │
│       │      │  │      │      │  │  text (semi- │
│       │      │  │      │      │  │  transparent)│
└───────┴──────┘  └──────────────┘  └──────────────┘
   left_image        split_50_50      text_overlay
```

## 2.6 Zadaci (redom)

| # | Zadatak | Output |
|---|---------|--------|
| 2.1 | book_reader.html — shell s flip engine | JS + CSS |
| 2.2 | 6 layout fragmenata | 6 template partials |
| 2.3 | Cover page UI (full-bleed + animirani naslov) | CSS animation |
| 2.4 | Swipe + keyboard navigation | JS |
| 2.5 | Audio player per page (mini, ne ometa čitanje) | HTML5 Audio |
| 2.6 | Language switcher (in-book, bez reload) | JS |
| 2.7 | Progress bar + page counter | CSS + JS |
| 2.8 | Fullscreen mode | Fullscreen API |
| 2.9 | Preload sljedeće stranice | JS Image preload |
| 2.10 | Auto-play mode (audio → flip → audio → flip) | JS |
| 2.11 | Back cover (pouka + links) | Template |
| 2.12 | Mobile optimizacija (portrait, veći font) | CSS media queries |
| 2.13 | Knjižica preglednih naslovnica (story_list update) | Thumbnail grid |

---

# GLAVA 3 — SADRŽAJ: ILUSTRACIJE + AUDIO
**Tko:** Sadržajni agent (CC ili čovjek)
**Što:** Promptovi, generacija, kvaliteta, audio

## 3.1 PLAY.EU Vizualni identitet

```
Stil: "Watercolor Parchment Storybook"

Ključne riječi za SVAKI prompt:
  "Children's storybook watercolor illustration on aged parchment paper,
   warm golden light, soft watercolor edges, European folk art inspired,
   Caldecott Medal quality, gentle and whimsical, safe for children,
   muted earth tones with gold accents, no text in image, no logos"

Negativni prompt:
  "scary, violent, blood, weapons, nudity, photorealistic faces,
   modern clothing, technology, text, watermark, signature,
   dark themes, horror, anime style, cartoon style"

Paleta:
  Parchment:  #FDF6E3 (pozadina)
  Gold:       #C9A84C (akcenti)
  Earth:      #8B4513 (drvo, kosa)
  Forest:     #2D5F2D (šuma, trava)
  Sky:        #87CEEB (nebo, voda)
  Stone:      #808080 (dvorac, kamenje)
  Rose:       #DDA0DD (princeze, cvijeće)
```

## 3.2 Scene Extraction — Rapunzel primjer

```
Stranica 0 (naslovnica):
  Scena: "A tall stone tower rising above a misty forest,
          golden-haired girl visible in the window,
          wildflowers growing at the base, morning light"
  Layout: full_bleed
  Naslov: "RAPUNZEL"

Stranica 1:
  Scena: "An evil sorceress carrying a baby away from
          a weeping couple, dark cloak flowing,
          cottage in background, moonlight"
  Tekst: "Čarobnica je ukrala dijete..."
  Layout: top_image

Stranica 2:
  Scena: "A young girl with extremely long golden braids
          sitting by a window in a round tower room,
          looking down at the forest below, birds nearby"
  Tekst: "Svaki dan čarobnica je dozivala..."
  Layout: split_50_50

Stranica 3:
  Scena: "A handsome prince on horseback in a forest,
          listening with wonder, the tower visible
          through the trees, golden sunset"
  Tekst: "Jednog dana princ je čuo..."
  Layout: top_image

Stranica 4:
  Scena: "The prince climbing the tower using the golden braid
          as a rope, the girl helping him from the window,
          stars in the night sky"
  Tekst: "Rapunzel spusti kosu..."
  Layout: left_image

Stranica 5:
  Scena: "The angry sorceress with scissors cutting the golden braid,
          the girl crying, loose hair falling,
          dramatic lightning in background"
  Tekst: "Ali čarobnica sazna!..."
  Layout: top_image

Stranica 6:
  Scena: "A blind prince wandering through a desert landscape,
          tears streaming, searching, wildflowers
          sprouting where his tears fall"
  Tekst: "Princ je godinama lutao..."
  Layout: split_50_50

Stranica 7 (zadnja):
  Scena: "The prince and Rapunzel reunited in a flower meadow,
          her tears healing his eyes, golden light radiating,
          the castle visible in the distance, happily ever after"
  Tekst: "Zajedno se vratiše..."
  Layout: top_image
```

## 3.3 Sve priče — scene plan

| # | Priča | Ključne scene | Str. |
|---|-------|---------------|------|
| 1 | Rapunzel | Toranj, kosa, princ, čarobnica, pustinja, reunion | 8 |
| 2 | Pepeljuga | Ognjište, vila, haljina, bal, cipela, vjenčanje | 8 |
| 3 | Snjeguljica | Šuma, kućica, 7 patuljaka, jabuka, lijes, princ | 10 |
| 4 | Trnoružica | Krštenje, vilina kletva, vreteno, san, princ, buđenje | 9 |
| 5 | Ivica i Marica | Šuma, kućica od slatkiša, vještica, peć, bijeg, blago | 9 |
| 6 | Crvenkapica | Put, šuma, vuk, baka, lovac | 9 |
| 7 | Kraljević Žabac | Zlatna lopta, bunar, žaba, obećanje, transformacija | 10 |
| 8 | Zvjezdani taliri | Sirota, hladnoća, darežljivost, zvijezde, zlato | 6 |
| 9 | Bremenski glazbenici | Magarac, pas, mačka, pijetao, razbojnici, kuća | 10 |
| 10 | Vuk i sedam kozlića | Mama koza, kozlići, vuk, kreda, škarice, kamenje | 10 |

**Ukupno: 89 scena = 89 ilustracija + 10 naslovnica = 99 slika**

## 3.4 AI Provider opcije

| Provider | Cijena | Kvaliteta | Konzistentnost | Preporuka |
|----------|--------|-----------|----------------|-----------|
| DALL-E 3 (OpenAI) | $0.04/slika | Odlična | Srednja | ✅ Za početak |
| Midjourney v6 | $0.02/slika | Izvrsna | Visoka | ✅ Za produkciju |
| Stable Diffusion XL | Besplatno (self-host) | Dobra | Visoka (ControlNet) | Za volume |
| Ideogram 2.0 | $0.02/slika | Dobra | Srednja | Alternativa |

**Preporuka:** DALL-E 3 za prototip (10 slika test), Midjourney za volume (90 slika).
**Budžet:** 99 slika × $0.04 = **$3.96** (DALL-E) ili **$1.98** (Midjourney)

## 3.5 Audio naracija

```
Opcija A: Google Cloud TTS (Neural2)
  - Cijena: ~$0.000016/karakter → 10 priča × 3 jezika × ~800 char = $0.38
  - Glasovi: hr-HR-Wavenet-A (ženski), de-DE-Neural2-C, en-US-Neural2-H
  - Kvaliteta: dobra, ali "robotska"

Opcija B: ElevenLabs
  - Cijena: besplatno do 10K char/mj → dovoljno za 3-4 priče
  - Glasovi: moguće klonirati "bakin glas" (s pristankom)
  - Kvaliteta: izvrsna, prirodna

Opcija C: Vlastiti glas
  - Ivan/Marija snimi naraciju na HR
  - Besplatno, autentično, emocionalno
  - Problem: treba studio opremu + vrijeme

Preporuka: ElevenLabs za HR (bakin glas), Google TTS za DE/EN
```

## 3.6 Legal review

```
AI-generirane slike:
  - DALL-E 3: OpenAI daje prava korisniku (Terms of Use 2024)
  - Midjourney: komercijalna prava uz paid plan
  - Stable Diffusion: open source, puna sloboda
  
Tekst priča:
  - Grimm: public domain (autor umro 1863, >70 godina)
  - Andersen: public domain (autor umro 1875)
  - Perrault: public domain (autor umro 1703)
  
Audio:
  - TTS: prava na output su naša
  - Vlastiti glas: vlastito vlasništvo

STATUS: ✅ Zakonski čisto za sve opcije
```

## 3.7 Zadaci (redom)

| # | Zadatak | Output |
|---|---------|--------|
| 3.1 | Vizualni identitet dokument | Prompt template + paleta + primjeri |
| 3.2 | Scene extraction — svih 10 priča | 99 scene descriptions |
| 3.3 | Test batch: 10 naslovnica (DALL-E 3) | 10 cover slika |
| 3.4 | Review + korekcija promptova | Poboljšani promptovi |
| 3.5 | Full batch: 89 unutarnjih ilustracija | 89 slika |
| 3.6 | Thumbnail generacija (400px) | 99 thumbnailova |
| 3.7 | Quality review (ručna provjera svake slike) | Approve/regenerate |
| 3.8 | Audio HR: svih 10 priča | 10 × ~9 = 90 audio fajlova HR |
| 3.9 | Audio DE: svih 10 priča | 90 audio fajlova DE |
| 3.10 | Audio EN: svih 10 priča | 90 audio fajlova EN |
| 3.11 | Alt text za sve slike (accessibility) | 99 alt textova |
| 3.12 | Legal compliance zapisi | 10 LegalCompliance zapisa |

---

# REDOSLIJED IZVRŠENJA

```
Tjedan 1 (16-20.04):
  GLAVA 1: Model + migracija + split_story_into_pages
  GLAVA 3: Vizualni identitet + scene extraction za svih 10

Tjedan 2 (21-25.04):
  GLAVA 1: generate_illustration command + API endpoint
  GLAVA 2: Book reader shell + cover page + page flip CSS
  GLAVA 3: Test batch naslovnice → review → full batch start

Tjedan 3 (28.04-02.05):
  GLAVA 1: generate_audio command + admin review
  GLAVA 2: Audio player + swipe + language switch + fullscreen
  GLAVA 3: Audio generacija + quality review svih slika

Tjedan 4 (03-07.05):
  SVE GLAVE: Integracija + testiranje + polish
  GLAVA 2: Mobile optimizacija + auto-play
  GLAVA 3: Zadnje korekcije + legal review
  DEPLOY: Creative Europe demo ready
```

---

# CHECKPOINTS

```
CP1 (20.04): Model postoji, 90 stranica kreirano, scene description gotov
CP2 (25.04): 10 naslovnica generirano, book reader flip radi na mobitelu
CP3 (02.05): Svih 99 slika generirano + audio HR, reader kompletiran
CP4 (05.05): Svi jezici, fullscreen, auto-play, mobile testiran
CP5 (07.05): Creative Europe demo spreman — 10 slikovnica, 3 jezika, audio
```

---

# BUDŽET

```
Ilustracije:  99 × $0.04 = $3.96 (DALL-E) ili $1.98 (MJ)
Audio TTS:    ~$0.40 (Google) + ElevenLabs free tier
Regeneracije: ~20% = +$0.80
─────────────────────────────────────
UKUPNO:       ~$5.16 (konzervativno)
```
