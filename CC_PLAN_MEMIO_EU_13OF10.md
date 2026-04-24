# MEMIO GROUP — EU 13/10 Plan
*Generirano: 2026-04-24 | CC Sonnet 4.6*

## Misija
Tri zasebna portala (memio.pet / memio.world / memio.farm) pretvoriti u EU-ready platforme
koje zadovoljavaju Creative Europe / PLAY.EU / Horizon standarde — i integrirati sve
Fenix inovacije koje povećavaju UI/UX, AI i sigurnost.

---

## TRENUTNA OCJENA

| Portal | Arch | UI/UX | AI | Security | EU | UKUPNO |
|--------|------|-------|-----|----------|----|--------|
| memio.pet   | 8 | 7 | 3 | 5 | 6 | **6.5/10** |
| memio.world | 8 | 5 | 4 | 4 | 8 | **6.0/10** |
| memio.farm  | 4 | 2 | 1 | 3 | 3 | **3.0/10** |

---

## CILJANA OCJENA: 13/10

Što znači 13/10 za EU portale:
- Tehničko savršenstvo + kvantna sigurnost (BPZ-9, TAJNA, Z2P)
- AI koji je objašnjiv (EU AI Act compliance)
- Europeana API kao kulturni sloj
- GDPR-first arhitektura (0 Google Fonts server-side, cookieless)
- PWA offline-first
- .dok standard za sve digitalne dokumente
- Trust score vidljiv i objašnjiv korisnicima
- ChainBlock POE za sve kritične podatke

---

## PRIORITETI PO BLOKOVIMA

### BLOK A — Sigurnost (sve tri platforme) [PRIORITY 1]

**A1 — TLS upgrade memio.pet (sad: TLS 1.2+1.3 → cilj: samo TLS 1.3)**
```nginx
# /etc/nginx/sites-enabled/memio-pet
ssl_protocols TLSv1.3;  # samo TLS 1.3
ssl_ciphers TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256;
add_header X-Quantum-Shield "NEXUS-1.0;app=kyber768;tls=1.3+chacha20" always;
```

**A2 — BPZ-9 honeypot za memio.pet i memio.world**
- Kopirati middleware_honeypot.py pattern
- memio_pet i memio_world specifični HONEYPOT_PATHS
- ZamkeCanary evidentiranje u memio_pets DB

**A3 — VIVUS EncryptedField upgrade na memio.pet**
- Zamijeniti MemioEncryptedField s VIVUS_DOK_V1 formatom
- Vet zapisi → vivus_blob (samo vlasnik s passphrase čita)
- OIB, email → AES-256-GCM (kao sad) + TAJNA chain za PetHealthRecord

**A4 — Z2P commit zaštita**
- Već primijenjeno na fina-connect (uključuje memio apps)
- CommitGuardian bilježi sve commitove koji diraju memio_* fajlove
- Status: DONE (inherira od fina-connect Z2P)

**A5 — GDPR-first font loading**
- Zamijeniti Google Fonts s self-hosted Fontsource
- memio.world index.html: Google Fonts → `/static/fonts/` lokalni
- Eliminira cross-border data transfer bez privole

---

### BLOK B — memio.pet [PRIORITY 2]

**B1 — Pretraga (PLAN-005) — IMPLEMENTIRATI**
```python
# memio_pet/views.py → pretraga()
def pretraga(request):
    q = request.GET.get("q", "").strip()
    vrsta = request.GET.get("vrsta", "")
    grad = request.GET.get("grad", "")
    
    qs = AnimalProfile.objects.filter(is_public=True)
    if q:
        qs = qs.filter(
            Q(name__icontains=q) | Q(breed__icontains=q) | 
            Q(chip_number__icontains=q)
        )
    if vrsta:
        qs = qs.filter(species=vrsta)
    if grad:
        qs = qs.filter(breeder__city__icontains=grad)
    
    return render(request, "memio_pet/pretraga.html", {"animals": qs[:50], "q": q})
```

**B2 — Prodaja (PLAN-006) — IMPLEMENTIRATI**
```python
# Koristiti RawFoodListing kao temelj za opću prodaju
# Proširiti: oglasi, cijena, kontakt, udomljavanje
class SaleAd(models.Model):
    animal = models.ForeignKey(AnimalProfile, ...)
    price = models.DecimalField(...)
    description = models.TextField()
    contact_method = ...  # WhatsApp / Email
    is_active, expires_at, views_count
```

**B3 — AI Breed Detection (PLAN-013)**
```python
# memio_pet/ai_views.py → detect_breed()
# Haiku vision: POST /api/breed-detect/ — slika → JSON breed + confidence
# Integrirati u add_animal wizard (korak 2: upload foto → AI predlaže breed)
```

**B4 — Vet Bridge (PLAN-014)**
```python
# memio_pet/bridge.py → sync_vet_records()
# Fenix V3 → memio.pet: API push zdravstvenih zapisa
# Endpoint: POST /api/vet-push/ (API key auth, rate limited)
# PetHealthRecord kriptiran VIVUS_DOK_V1
```

**B5 — PWA manifest + Service Worker**
```json
// static/memio_pet/manifest.json
{
  "name": "memio.pet",
  "short_name": "memio.pet",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#0a1628",
  "theme_color": "#6c8eff",
  "icons": [...]
}
```

**B6 — 3 inovacije iz budućnosti (memio.pet specifično)**
1. **AI Zdravstveni Prorok** — na temelju dobi/rase/zapisa predvidi zdravstvene rizike
2. **Besmrtni Karton** — `.dok` bundle s offline HTML čitačem = prava digitalna putovnica
3. **Folija Runtime Seal** — svaki pet profil ima live Folija badge koji dokazuje integritet

---

### BLOK C — memio.world / PLAY.EU [PRIORITY 2]

**C1 — Template kompletacija (kritično)**
Svaki game view mora imati pravi HTML template (ne inline):
- `/templates/memio_world/play_home.html` — dashboard igara
- `/templates/memio_world/story_detail.html` — čitanje s tipografijom
- `/templates/memio_world/memory_game.html` — interaktivni JS
- `/templates/memio_world/chess_home.html` — šah tutorijal
- `/templates/memio_world/parent_dashboard.html` — roditeljski kontrolni panel
- `/templates/memio_world/timecapsule.html` — kreiranje/otvaranje kapsule
- `/templates/memio_world/child_profile.html` — dječji profil

**C2 — GDPR font fix (KRITIČNO za EU projekte)**
```html
<!-- ZAMIJENITI: -->
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond..." rel="stylesheet">

<!-- S: -->
<link href="/static/fonts/cormorant-garamond.css" rel="stylesheet">
```
Sve 3 statične landing stranice (memio/index.html, memio-pet/index.html, memio-farm) trebaju self-hosted fontove.

**C3 — AI Asistent za djecu (Trojstvo integracija)**
```python
# memio_world/ai_views.py → storytelling_ai()
# Haiku: djeci prilagođen jezik
# Endpoint: POST /play/ai/story/
# Input: tema, dob, jezik
# Output: kratka priča na jeziku djeteta (HR/DE/EN)
# Rate limit: 10 priča/dan bez registracije, neograničeno za registrirane
```

**C4 — VoiceLegacy UI**
```python
# Model postoji: VoiceLegacy
# Dodati: MediaRecorder API (JS) → upload → transkript (Whisper/Haiku)
# Use case: baka/djed snima priče → djeca slušaju → AI transkribira
# EU projekt: "Digitalna baština govora" — Europeana submissija
```

**C5 — TimeCapsule UI**
```python
# Model postoji: TimeCapsule (draft/locked/opened status)
# Dodati: kreiranje kapsule, upload medija, datum otvaranja
# Inovacija: ChainBlock POE → kapsule su blockchain-verified
# 3 inovacije iz budućnosti: Capsule Time-Lock (TLP puzzle kao zamjenski sigurnosni sloj)
```

**C6 — Parent Dashboard s AI insights**
```python
# views_daily.py postoji, template treba
# Dashboard pokazuje:
# - Koje igre dijete igra (duration, score, emotional state)
# - AI preporuke (Haiku): "Marko puno igra šah, evo 3 izazova"  
# - Weekly report PDF (DATEV-style za edukativne institucije)
# - Europeana content koje dijete gleda
```

**C7 — Offline PWA (PLAY.EU zahtjev)**
```javascript
// Service Worker cache za sve igre
// Offline-first: igre rade bez interneta
// Sync na mrežu: results, milestones, time spent
// EU AI Act: svi AI pozivi moraju biti optional (ne blokirati offline igru)
```

**C8 — Europeana Deep Integration**
```python
# Trenutno: europeana_client.py postoji, gallery view
# Dodati:
# - Europeana slike kao puzzle/memory game kartice
# - Kulturno nasljeđe → learning path generator (AI)
# - Europeana items → StoryBook generacija (Haiku pišerava priče iz metapodataka)
# - Attribution badge na svakom Europeana itemu (CC license compliance)
```

**C9 — 3 inovacije iz budućnosti (memio.world)**
1. **Heritage Oracle AI** — Model postoji! Dati mu UI: djed/baka unose priče, AI ih strukturira u obiteljski kronikl
2. **NightProtocol UI** — Večernji rituali, priče za spavanje, EthicalSession monitoring
3. **DialectMap** — Interaktivna karta dijalekata → djeca snimaju lokalni govor → Europeana arhiva

---

### BLOK D — memio.farm [PRIORITY 3]

**D1 — Kompletna Django implementacija**
```python
# Modeli koji nedostaju (dodati u models.py):
class HealthRecord(models.Model):  # vet zapisi za stado
class EarTag(models.Model):        # EU eartag markice (HR-HR-12345)
class FeedLog(models.Model):       # prehrana i lijekovi
class ProductionRecord(models.Model):  # mlijeko/jaja/vuna
class HACCPDocument(models.Model):  # HACCP dokumentacija
class Slaughter(models.Model):     # klanje s certifikatom
class AgronetSync(models.Model):   # AGRONET API sync log

# EU traceability: svaka životinja = EU eartag = blockchain POE
```

**D2 — Kompletne Views + Templates**
```python
# Prioritet views:
# / → landing (iz Django, ne statički HTML)
# /stado/ → pregled stada s filterima
# /zivotinja/<ear_tag>/ → individualni profil (analogno /pas/<chip>/)
# /zdravlje/ → vet protokoli
# /dokumenti/ → HACCP + certifikati (.dok format)
# /agronet/ → AGRONET sync dashboard
```

**D3 — .dok format za HACCP i certifikate**
```python
# Svaki HACCP dokument → .dok bundle
# Satava: HACCP_payload.json + certifikat.pdf + proof.json
# Folija seal + ChainBlock POE
# EU zahtjev: traceability dokumenti moraju biti digitalno verificirani
```

**D4 — AGRONET API Bridge**
```python
# Analogno Vet Bridge za memio.pet
# AGRONET → automatski uvoz stada
# Svaka promjena u AGRONET → sync u memio.farm DB
# Webhook ili polling (AGRONET API dokumentacija)
```

**D5 — 3 inovacije iz budućnosti (memio.farm)**
1. **Farm AI Prorok** — na temelju dobi/rase/zapisa/sezone predvidi rizike + preporuči preventivne mjere
2. **Stado Loza** — digitalni rodovnik stada (analogno AnimalProfile heritage)
3. **HACCP .dok Chain** — svaki HACCP dokument = ChainBlock link, neizbrisivi lanac certifikacije

---

### BLOK E — Shared Innovations (sve 3 platforme)

**E1 — VIVUS .dok za sve digitalne dokumente**
| Portal | Dokument | .dok primjena |
|--------|----------|---------------|
| memio.pet | Zdravstveni karton | `PetHealthRecord → vivus_blob` |
| memio.pet | Putovnica | `.dok bundle (ZIP)` ← IMPLEMENTIRANO |
| memio.world | TimeCapsule | `.dok bundle s TLP puzzle` |
| memio.world | VoiceLegacy | `voice_payload.json + Folija seal` |
| memio.farm | HACCP | `.dok bundle + ChainBlock POE` |
| memio.farm | Vet zapisi | `vivus_blob (AGRONET verified)` |

**E2 — Trust Score vizualizacija (EU transparency zahtjev)**
```html
<!-- Svaki profil prikazuje Trust Score s objašnjenjem (EU AI Act Art. 13) -->
<div class="trust-score-badge" title="Izračunato na temelju: OIB verifikacije, vet zapisa, aktivnosti">
  <div class="score-bar" style="width: 78%"></div>
  <span>78/100 — Verificirani uzgajivač</span>
  <a href="/trust-metodologija/">Kako se računa?</a>  <!-- Transparentnost -->
</div>
```

**E3 — Folija Live Badge**
```html
<!-- Svaki pet/farm/world profil ima live seal provjeru -->
<div data-folija-seal="MEMIO-PET-{chip_number}" 
     data-folija-verify="/api/folija/verify/{seal_id}">
  ✓ Integritet verificiran
</div>
<!-- folija.js automatski provjerava seal i mijenja badge -->
```

**E4 — ChainBlock POE za kritične događaje**
| Event | ChainBlock |
|-------|-----------|
| Pet health record kreiran | ANIMAL-HEALTH-{id} |
| Vlasništvo promijenjeno | OWNERSHIP-{id} |
| HACCP dokument potpisan | HACCP-{farm_id}-{date} |
| TimeCapsule zapečaćena | CAPSULE-{id}-{open_date} |
| VoiceLegacy snimljena | VOICE-{id}-{hash} |

**E5 — Kyber/TAJNA za sensitivne podatke**
- OIB uzgajivača → TAJNA_KEY encrypted
- Vet zapisi → VIVUS_DOK_V1 (passphrase = chip broj)
- VoiceLegacy → VIVUS_DOK_V1 (passphrase = obiteljski kod)
- Sve zamke aktive na svim domenama (BPZ-9)

**E6 — AI Trojstvo integracija**
| AI | Uloga | Platform |
|----|-------|---------|
| Haiku | Djeci prilagođene priče, breed detekcija, trust score | svi |
| DeepSeek | Noćni audit koda, patron patrol | svi |
| Sonnet (CC) | Implementacija, koordinacija | svi |
| Gemini | Istraživanje EU zahtjeva | istraživanje |

---

## REDOSLJED IMPLEMENTACIJE

### Sprint 1 (sada → sljedeća sesija) [HITNO]
1. **A1** — TLS 1.3 only za memio.pet nginx ← 15 min
2. **A5** — GDPR font fix na svim 3 landing HTML ← 30 min
3. **B1** — Pretraga na memio.pet (real DB query) ← 2h
4. **C1** — 7 template-a za memio.world ← 3h
5. **C2** — Parent dashboard template ← 1h

### Sprint 2 (sljedeća sesija)
6. **B3** — AI Breed Detection (Haiku vision)
7. **B5** — PWA manifest za memio.pet
8. **C3** — AI Storytelling asistent
9. **C8** — Europeana deep: puzzle/memory kartice iz kulturne baštine
10. **D1** — memio.farm modeli (EarTag, HealthRecord, HACCP)

### Sprint 3 (EU projekt fokus)
11. **C5** — TimeCapsule UI + TLP seal
12. **C4** — VoiceLegacy snimač + Whisper transkript
13. **D2** — memio.farm kompletne views + templates
14. **D3** — HACCP .dok bundle
15. **E4** — ChainBlock POE za sve kritične evente

### Sprint 4 (13/10 finalizacija)
16. **B6** — AI Zdravstveni Prorok (pet)
17. **C9** — Heritage Oracle AI UI
18. **D5** — Farm AI Prorok
19. **E2** — Trust Score EU transparency badge
20. **E3** — Folija Live Badge na svim profilima

---

## EU PROJEKT CHECKLIST (Creative Europe / PLAY.EU / Horizon)

| Zahtjev | memio.pet | memio.world | memio.farm |
|---------|-----------|-------------|------------|
| GDPR-first (self-hosted fonts) | ❌ TODO | ❌ TODO | ❌ TODO |
| Cookie consent / cookieless | ⚠ partial | ⚠ partial | ❌ |
| Europeana API integration | ❌ | ✅ LIVE | ❌ |
| Offline PWA | ❌ | ❌ | ❌ |
| Multilingual (HR/DE/EN) | ⚠ partial | ⚠ partial | ❌ |
| AI Act transparency (explain AI) | ❌ | ❌ | ❌ |
| Digital heritage archiving | ✅ (putovnica) | ✅ (stories) | ❌ |
| ChainBlock POE | ✅ (.dok) | ❌ | ❌ |
| VIVUS encryption | ✅ (OIB/email) | ❌ | ❌ |
| Trust Score visible | ✅ | N/A | ❌ |
| Quantum security (BPZ-9) | ❌ | ❌ | ❌ |

---

## PROJEKCIJA OCJENA NAKON SPRINTOVA

| Sprint | memio.pet | memio.world | memio.farm |
|--------|-----------|-------------|------------|
| Sad | 6.5 | 6.0 | 3.0 |
| Sprint 1 | 7.5 | 7.0 | 3.5 |
| Sprint 2 | 9.0 | 8.5 | 5.0 |
| Sprint 3 | 10.5 | 10.0 | 8.0 |
| Sprint 4 | 13/10 | 13/10 | 13/10 |

13/10 znači: exceeds EU requirements + kvantna sigurnost + cultural heritage first class citizen.
