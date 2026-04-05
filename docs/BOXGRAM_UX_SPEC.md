# BOXGRAM — UX Specifikacija

**Verzija:** 1.0  
**Datum:** 05.04.2026.  
**Jezik:** Hrvatski (primarni)

Detaljni UX flow-ovi za glavne feature-e Boxgrama.

---

## G2.1 Registracija ljubimca — 3 koraka

### Screen 1: OSNOVNO

**Naslov:** "Upoznaj nas sa tvojim ljubimcem"

**Input polja:**
```
┌─────────────────────────────────────────┐
│  📸  AVATAR (opciono)                   │
│  [Prosljeđi datoteku] ili [Snimka]      │
│                                         │
│  Ime ljubimca *                         │
│  [_________________________]             │
│                                         │
│  Vrsta *                                │
│  [Pas ▼]                               │
│  ├─ Pas                                 │
│  ├─ Mačka                               │
│  ├─ Konj                                │
│  ├─ Pčela (zajednica)                   │
│  └─ ... (12 vrsta)                      │
│                                         │
│  Rasa/Podvrsta (opciono)                │
│  [_________________________]             │
│                                         │
│  Datum rođenja (opciono)                │
│  [DD.MM.YYYY. ▼]                        │
│                                         │
│  [  DALJE →  ]                          │
└─────────────────────────────────────────┘
```

**Logika:**
- Ime: max 100 znakova, lowercase trim
- Vrsta: mandatory (backend će filtrirati event tipove po vrsti)
- Datum: DateField (birth_date), nullable
- Avatar: Optional ImageField, thumb 200x200px
- CTA: Gumb DALJE aktivira samo ako je Ime + Vrsta popunjeno

---

### Screen 2: PRIČA

**Naslov:** "Priča o {Ime}"

**Polja:**
```
┌─────────────────────────────────────────┐
│  Bio/Opis (opciono)                     │
│  ┌─────────────────────────────────────┐│
│  │ Sve što trebamo znati...            ││
│  │ (npr. Moj Rex je stariji pas, odličan││
│  │ lovac, puno voli partije utrčavanja) ││
│  │                                     ││
│  │ [max 500 znakova]                   ││
│  └─────────────────────────────────────┘│
│                                         │
│  Foto naslovnice (opciono)              │
│  [Prosljeđi datoteku]                   │
│                                         │
│  Rodovnica - Otac (opciono)             │
│  [_________________________]             │
│                                         │
│  Rodovnica - Majka (opciono)            │
│  [_________________________]             │
│                                         │
│  [ ← NAZAD ]     [DALJE → ]             │
└─────────────────────────────────────────┘
```

**Logika:**
- Bio: TextField, max 500 znakova, TinyMCE ili plain text
- Cover photo: ImageField (1200x400px idealno)
- Rodovnica: Tekstualna polja (father_name, mother_name) — ne FK za sada
- Backend generiraj SHA256 seal: `hash(uuid + name + species + birth_date)`

---

### Screen 3: VIDLJIVOST

**Naslov:** "Tvoj Boxgram profil"

**Opcije:**
```
┌─────────────────────────────────────────┐
│  Javnost profila                        │
│                                         │
│  ☑ Javna profila (svi vide)             │
│  ☐ Privatna profila (samo ja)           │
│                                         │
│  Javnost događaja (LifeEvent)           │
│  ☑ Svi događaji javni                   │
│  ☐ Samo odabrani događaji               │
│  ☐ Samo prijave prate                   │
│                                         │
│  Dozvoli import s društvenih mreža      │
│  ☑ Dozvoli                              │
│  (FB, IG, TikTok će biti prikazani      │
│   na čekanju za odobrenje)              │
│                                         │
│  ☐ Otkrij mog ljubimca na Boxgram       │
│     Feed-u ♥ (novog je lakše pronaći)  │
│                                         │
│  [KREIRAJ PROFIL ✓]                     │
└─────────────────────────────────────────┘
```

**Logika:**
- `is_public`: Boolean (default=True)
- Import settings: Sprema se u User preferences ili PetProfile
- QR kod: Generiraj async u Celery task nakon save()
- URL profila: `/memio.pet/ljubimac/{slug}/`

**Post-kreiranja:**
```
Prikaži success screen:
┌──────────────────────┐
│  ✓ Profil kreiran!   │
│                      │
│  URL: memio.pet/... │
│                      │
│  [Kopiraj link]      │
│  [Vidi profil]       │
│  [Dodaj prvi event]  │
└──────────────────────┘
```

---

## G2.2 Timeline stranica

### Layout

```
┌─────────────────────────────────────────┐
│  ← | 📸 Rex | ♥ 234 | 👥 56             │  ← HEADER
│       (Pas, 5 god., Pas smeđi)          │
├─────────────────────────────────────────┤
│  [Svi] [Rođenja] [Vet] [Takmičenja] ... │  ← FILTRI (tab-ovi)
├─────────────────────────────────────────┤
│                                         │
│  🔵 Rođenje — 15.04.2019.              │  ← TIMELINE ITEM
│     "Rex je stigao kod nas!"            │
│     [Foto #1] [Foto #2]                 │
│     ♥ 12 | 💬 3 | 📤 Podijeli           │
│                                         │
│  📅 Vet posjet — 12.02.2025.            │
│     "Godišnja provjera OK"              │
│     Doktor: dr. Marko Horvat            │
│     ♥ 8 | 💬 1                          │
│                                         │
│  🏆 Natjecanje — 01.03.2025.            │
│     "Najbolje srednje uši u gradu!"     │
│     [Foto sa pobjedno]                  │
│     ♥ 45 | 💬 7 | 🎖 POBJEDNIK          │
│                                         │
│  📱 (Imported from Instagram)           │
│     "Ljetne igre na plaži 🏖️"          │
│     [3 Foto-a]                          │
│     ♥ 123 | 💬 12                       │
│                                         │
│  ⚫ Memorijal — 22.12.2024.             │  ← DARK MODE ako je memorial
│     "Ostatak zauvijek u našim srcima"  │     (temno pozadina, serif font)
│     [Collage od fotografija]            │
│     ♥ 567 | 💬 89                       │
│                                         │
└─────────────────────────────────────────┘
```

### Klikavanje na Event
- Otvori modal sa svim detaljima
- Mogućnost ♥ ako je `is_public=True`
- Mogućnost 💬 komentara (future feature)
- Mogućnost brisanja / editiranja ako je vlasnik

### Header — Informacije
```
┌─────────────────────────────────────────┐
│  [←] [📸 Avatar] [IME] | [🎂 5 god.] [♥] │
│      Pas, Smeđa boja                    │
│      "Moj najbolji prijatelj"           │
│      Vlasnik: @Ivan_Horvat              │
│      Verificiran uzgajivač ✓            │
│                                         │
│      [Slijedi] [Dijelovi] [...]         │
└─────────────────────────────────────────┘
```

**Logika:**
- Avatar: avatar iz PetProfile
- Ime + vrsta + bio
- Birth/death date kalkulacija: "5 god." ili "u 2019. — 2024."
- Hearts count: SUM od svih EventHeart za sve events ovog ljubimca
- Followers count: COUNT od PetFollower

### Filtriranje (Tab-ovi)
```
[Svi] [Rođenja] [Vet] [Čipljenja] [Takmičenja] [Nagrada] [Smrt] [Ostalo]
```

**Logika:**
- Klik na tab → Filter LifeEvent.event_type
- Backend: QuerySet.filter(pet=pet, event_type='rodenje', is_public=True)
- URL: `/memio.pet/ljubimac/{slug}/?filter=rodenje`

### Memorial Mode (Dark)
Kad je `pet.is_memorial=True`:
- Pozadina: #2a2a2a (dark gray)
- Font: serif (Georgia, Garamond)
- Boja teksta: #e0e0e0 (light gray)
- Dodaj "Вічна пам'ять" ili "Vječna uspomena" header
- Hearts i comments ostaju uključeni

---

## G2.3 Import wizard — 5 koraka

### Korak 1: URL paste

```
┌─────────────────────────────────────────┐
│  Uvezi objavu s društvenih mreža        │
│                                         │
│  Zalijepite URL objave (post-a):        │
│  [instagram.com/p/ABC123... or FB URL] │
│                                         │
│  Podržani platform-i:                   │
│  📱 Instagram | 👥 Facebook             │
│  🎵 TikTok    | 📺 YouTube              │
│  🔗 Ostalo (oEmbed)                     │
│                                         │
│  [DALJE]                                │
└─────────────────────────────────────────┘
```

**Validacija:**
- URLField validator (RFC 3986)
- Prepoznaj domenu: instagram.com, facebook.com, tiktok.com, youtube.com
- Ako nepoznata domena → pokušaj oEmbed fallback

---

### Korak 2: oEmbed fetch (async)

**Backend:**
```python
@shared_task
def fetch_social_import(import_id):
    imp = SocialImport.objects.get(id=import_id)
    
    oembed_providers = {
        'instagram.com': 'https://graph.facebook.com/v18.0/instagram_oembed',
        'facebook.com': 'https://www.facebook.com/plugins/post/oembed.json',
        'tiktok.com': 'https://www.tiktok.com/oembed',
        'youtube.com': 'https://www.youtube.com/oembed',
    }
    
    for domain, endpoint in oembed_providers.items():
        if domain in imp.source_url:
            try:
                r = requests.get(endpoint, params={'url': imp.source_url}, timeout=10)
                data = r.json()
                imp.thumbnail_url = data.get('thumbnail_url')
                imp.caption = data.get('title', '')[:200]
                imp.raw_data = data
                imp.save()
            except Exception as e:
                logging.error(f"oEmbed failed for {imp.source_url}: {e}")
```

**UI Feedback:**
```
┌─────────────────────────────────────────┐
│  ⏳ Učitavam...                         │
│  Preuzimam podatke iz platforme...     │
└─────────────────────────────────────────┘
```

---

### Korak 3: Preview + Metadata

```
┌─────────────────────────────────────────┐
│  ✓ Učitano!                             │
│                                         │
│  Naslov:                                │
│  "Ljetne igre na plaži 🏖️"              │
│                                         │
│  Datum objave: 15.08.2024. u 14:30     │
│  Platform: Instagram                    │
│                                         │
│  Thumbnail:                             │
│  [======== SLIKA ========]              │
│  (3 media datoteke)                     │
│                                         │
│  Caption (prvi 200 znakova):            │
│  "Najljepši dan u godini! Rex je      │
│   prvi ušao u more..."                  │
│                                         │
│  [DALJE]                                │
└─────────────────────────────────────────┘
```

**Logika:**
- `thumbnail_url`: Prikaži iz oEmbed response-a
- `caption`: Tekst iz oEmbed title + description
- `post_date`: Parse iz oEmbed ili source_url

---

### Korak 4: Picker — Mapiraj na event tip

```
┌─────────────────────────────────────────┐
│  Koja vrsta događaja je ovo?            │
│                                         │
│  ☐ Novo događaja (kreiraj "Ljetni dan"│
│  ☑ Postojeći događaj — odaberi:        │
│    [Rođenje 15.04.2019. ▼]             │
│                                         │
│  ALI kreiraj novo:                      │
│  Tip: [Ostalo ▼]                        │
│  Naslov: ["Ljetne igre na plaži ▼]     │
│  Datum: [15.08.2024. ▼]                │
│  Lokacija (opciono): [Vodice]          │
│                                         │
│  [DALJE]                                │
└─────────────────────────────────────────┘
```

**Logika:**
- Ako korisnik odabere postojeći event → `SocialImport.mapped_to = existng_event`
- Ako kreiraj novo → backend kreira LifeEvent + mapira SocialImport.mapped_to na njega
- Medije iz oEmbed (thumbnails) spremi u EventMedia

---

### Korak 5: Approve + Finish

```
┌─────────────────────────────────────────┐
│  ✓ Gotovo!                              │
│                                         │
│  Objava je uspješno uvezena:            │
│  "Ljetne igre na plaži"                │
│  → Mapiran na događaj "Ostalo"          │
│  → 3 slike dodane                       │
│                                         │
│  Status: NA ČEKANJU (samo za tebe)     │
│                                         │
│  [Vidi na timeline-u]                   │
│  [Uvezi drugu] [Završi]                 │
└─────────────────────────────────────────┘
```

**Backend post-akcije:**
```python
SocialImport.status = 'pending'  # Čeka odobrenje vlasnika

# Ako korisnik klikne "Objavi"
SocialImport.status = 'approved'
mapped_event.is_public = True
mapped_event.save()
```

---

## G2.4 Takmičenje

### Stranica: Lista takmičenja

```
┌─────────────────────────────────────────┐
│  🏆 Takmičenja                          │
│  [Aktivna] [Završena] [Moja]            │
├─────────────────────────────────────────┤
│                                         │
│  ┌─ AKTIVNO (3 dana još!) ─────────────┐│
│  │ "Najveći uši u gradu"               ││
│  │ [Cover image]                       ││
│  │ Polaznika: 12 | Glasova: 456        ││
│  │ Završava: 22. travnja                ││
│  │ [Glasaj za svojeg >]                 ││
│  └─────────────────────────────────────┘│
│                                         │
│  ┌─ AKTIVNO ────────────────────────────┐│
│  │ "Najbrži pas godine"                ││
│  │ [Cover]                             ││
│  │ Polaznika: 45 | Glasova: 2341       ││
│  │ Završava: 30. travnja                ││
│  │ [Glasaj >]                           ││
│  └─────────────────────────────────────┘│
│                                         │
│  ┌─ ZAVRŠENO ──────────────────────────┐│
│  │ "Najbolje ponašanje"                ││
│  │ POBJEDNIK: Zara (Mačka) | 890 glas. ││
│  │ [Vidi sve rezultate]                ││
│  └─────────────────────────────────────┘│
│                                         │
└─────────────────────────────────────────┘
```

---

### Stranica: Detalj takmičenja + Glasanje

```
┌─────────────────────────────────────────┐
│  "Najveći uši u gradu"                  │
│  [Cover image — 1200x400]               │
│  ⏱ Završava: 22. travnja 2026.          │
│  📊 12 polaznika | 456 glasova           │
├─────────────────────────────────────────┤
│                                         │
│  LEADERBOARD (Live):                    │
│  1. 🥇 Roki (Pas)      — 78 glasova     │
│  2. 🥈 Zara (Mačka)    — 62 glasova     │
│  3. 🥉 Šišo (Zec)      — 54 glasova     │
│  4. Dobi (Pas)         — 43 glasova     │
│  5. Maca (Mačka)       — 38 glasova     │
│  ... (još 7)                            │
│                                         │
│  ─────────────────────────────────────  │
│  GEO: Moj izbor je...                   │
│                                         │
│  [💙 GLASAJ ZA ROCKIJA]                │
│     (Pas, 3 god., vlasnik: @Marko_N)  │
│                                         │
│  Glasovi: 1 IP adresa = 1 glas po      │
│           takmičenju                    │
│  Ako si prijavio: glas = 1 po korisniku│
│                                         │
│  ⚠ Već si glasao za Rockija (15.04.)  │
│     Možeš promijeniti glas.             │
│     [Promijeni glas] [Obriši glas]      │
│                                         │
└─────────────────────────────────────────┘
```

**Logika glasanja:**
1. Korisnik je anoniman → `EventHeart` model sa IP check
   - Jedna IP = jedan glas po takmičenju
   - Ako pokušaš ponovno, error: "Već si glasao"
2. Korisnik je prijavljeni → `CompetitionVote` model
   - Jedan user = jedan glas po takmičenju
   - Može promijeniti glas (delete + new vote)

**Backend:**
```python
def vote_competition(request, competition_id, pet_id):
    comp = Competition.objects.get(id=competition_id)
    pet = PetProfile.objects.get(id=pet_id)
    entry = CompetitionEntry.objects.get(competition=comp, pet=pet)
    
    ip = get_client_ip(request)
    
    if request.user.is_authenticated:
        # User-based vote
        vote, created = CompetitionVote.objects.get_or_create(
            competition=comp,
            voter_user=request.user,
            defaults={'entry': entry, 'voter_ip': ip}
        )
        if not created:
            vote.entry = entry  # Update ako je user promijenio izbor
            vote.save()
    else:
        # IP-based vote
        vote, created = CompetitionVote.objects.get_or_create(
            competition=comp,
            voter_ip=ip,
            defaults={'entry': entry, 'voter_user': None}
        )
        if not created:
            return JsonResponse({'error': 'Već si glasao'}, status=400)
    
    # Recount
    entry.votes = entry.vote_records.count()
    entry.save(update_fields=['votes'])
    
    # Ažuriraj leaderboard
    all_entries = CompetitionEntry.objects.filter(
        competition=comp
    ).order_by('-votes')
    for idx, e in enumerate(all_entries, start=1):
        e.rank = idx
        e.save(update_fields=['rank'])
    
    return JsonResponse({'votes': entry.votes, 'rank': entry.rank})
```

---

### Završnica — Trofej

Kad je takmičenje završeno i pobjednika je proglašeno:

```
┌─────────────────────────────────────────┐
│  🏆 POBEDNIK ODREĐEN!                   │
│                                         │
│  "Najveći uši u gradu"                  │
│                                         │
│                    🏆                   │
│                   Roki                  │
│              Pas (3 god.)                │
│         890 glasova                      │
│                                         │
│  Vlasnik: @Marko_N                      │
│                                         │
│  [Preuzmi trofej 🎖️] (za print)         │
│  [Podijeli na društvenim mrežama]       │
│  [Vidi sve rezultate]                   │
│                                         │
└─────────────────────────────────────────┘
```

**Trofej design (SVG/PNG):**
- Zlatni trofej sa imenom pobjednika
- Mogućnost skidanja kao 1200x1200px PNG
- Integracija sa CompetitionEntry.rank=1

---

## G2.5 QR markica

### Prikaz QR-a na profilu

```
┌─────────────────────────────────────────┐
│ [← Rex]            ♥ 234 | 👥 56        │
│                                         │
│                      (Bottom section)   │
│ Identifikacija ljubimca:               │
│ ┌──────────────────────┐               │
│ │  █████████████████   │  ← PNG QR kod│
│ │  ████ memio.pet/ ████│               │
│ │  ████ ljubimac/  ████│               │
│ │  ████ rex-pas-   ████│               │
│ │  ████ a1b2c3d4   ████│               │
│ │  █████████████████   │               │
│ │                      │               │
│ │  Skaniraj za pristup │               │
│ └──────────────────────┘               │
│                                         │
│ SHA-256 pečat (verifikacija):          │
│ a2f9c4b1d8e7f5a3b6c9d2e8f1a4c7       │
│                                         │
│ [Preuzmi QR kod]                        │
│ [Naruči fizičku markicu (5 EUR)]       │
│                                         │
└─────────────────────────────────────────┘
```

**Data koja se enkriptira u QR:**
```
https://memio.pet/ljubimac/{slug}/
```

**QR svojstva:**
- Version: auto (1-40 ovisno o URL dužini)
- Error correction: H (30% recovery)
- Box size: 10px
- Border: 2
- Format: PNG sa transparentnim pozadinama ili white
- Rezolucija: 200x200px minimum (za print: 300dpi = 1000x1000px)

---

### Download QR kod

```
[Preuzmi QR kod]
 ↓
GET /api/boxgram/pets/{slug}/qr/
 ↓
Odgovara sa PNG slikom ili ZIP sa:
 - qr_kod.png (200x200)
 - qr_kod_300dpi.png (1000x1000)
 - qr_kod.svg (vektorski)
 - instrukcije.txt (kako ispisati)
```

---

### Fizička markica (5 EUR)

```
┌──────────────────────┐
│ [Naruči markicu]     │
└──────────────────────┘
 ↓
Otvori modal:
┌─────────────────────────────────────────┐
│  Naruči fizičku QR markicu             │
│                                         │
│  Cijena: 5 EUR (besplatna dostava)     │
│                                         │
│  Materijal:                            │
│  ☑ Plastična (PVC, vodootporna)        │
│  ☐ Metalna (keramička - premium)       │
│                                         │
│  Oblik:                                │
│  ☑ Kvadrat (50x50mm)                   │
│  ☐ Kružnica (Ø50mm)                    │
│  ☐ Kostim oblik (životinja)            │
│                                         │
│  Tekst na poleđini (opciono):          │
│  [Ime svojeg ljubimca]                 │
│  [Broj telefona]                       │
│                                         │
│  Dostava: [Hrvatska ▼]                │
│                                         │
│  [Naruči za 5 EUR]                     │
│                                         │
│  ℹ Markica stiže u 5-7 radnih dana.   │
│  Skenira se mobilnom kamerom.         │
│  Idealna za ogrlicu ili pričvršćivanje.│
│                                         │
└─────────────────────────────────────────┘
```

**Backend:**
- Integracija sa print-on-demand servisom (npr. Printful)
- Order submission → order_id sprema se na PetProfile
- Tracking link automatski u email
- Payment over Stripe/PayPal

---

## Zaključne UX smjernice

1. **Responsivnost:** Mobile first, SVG za ikone
2. **Prijevodi:** Django i18n za sve stringove
3. **Pristupačnost:** WCAG 2.1 AA (alt teksti, keyboard navigation)
4. **Brže Loading:** Lazy load slika, minify CSS/JS
5. **Dark mode:** Opcija u settingima korisnika
6. **Offline:** Progressive web app za offline čitanje timeline-a
