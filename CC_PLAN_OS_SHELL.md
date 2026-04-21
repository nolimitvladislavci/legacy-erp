# CC_PLAN: Global OS Shell + Code Sync

## STATUS: PLAN — čeka odobrenje

---

## DIO 1 — ANALIZA USKLAĐENOSTI

### Snimak stanja (audit 2026-04-21)

| Metrika | Fenix V3 | Stari ERP |
|---------|----------|-----------|
| Apps | 20 | 20 |
| URL routes | 245 | 2.245 (~9×) |
| Middleware | Django standard | Custom: permissions + identity + WebSocket |
| Template arhitektura | Modularna, čista | 40+ subdirektorija, veća |
| Search infrastruktura | Ad-hoc (10 fajlova) | Sistemska (refactor_views_search.py) |

---

### Aplikacije koje POSTOJE u fina-connect, ali NE u Fenix V3
*(kandidati za migraciju — "povuci nazad")*

| App | Opis | Prioritet migracije |
|-----|------|---------------------|
| `permissions` | Role-based access control + identity | 🔴 VISOK — temelj sigurnosti |
| `payments` | Payment processing | 🔴 VISOK — novac |
| `payroll` | Obračun plaća | 🟡 SREDNJI — EU tržište |
| `appointments` | Booking / zakazivanje | 🟡 SREDNJI — prekriva se s booking |
| `vault` | Sigurna pohrana podataka | 🟡 SREDNJI — GDPR |
| `procurement` | Nabava | 🟠 NIZAK — B2B kanal |
| `aml` | Anti-money laundering | 🟠 NIZAK — compliance |
| `webshop` | E-commerce | 🟠 NIZAK — odvojena vertikala |
| `konto` | Kontni plan | 🔴 VISOK — računovodstvo |
| `livestock` | Stočarstvo | 🟠 NIZAK — memio.farm specifično |
| `memio_pet` | Azil za životinje | 🟠 NIZAK — memio.pet specifično |
| `eldercare` | Skrb za starije | 🟠 NIZAK — buduća vertikala |
| `knjiznica` | Knjižnica | 🟠 NIZAK — memio.world |
| `burza` | Burza / trading | 🟠 NIZAK — buduće |
| `work_orders` | Radni nalozi | 🟡 SREDNJI — stolarija/baustela |
| `seasonal` | Sezonsko poslovanje | 🟠 NIZAK |
| `propter` | Nekretnine | 🟠 NIZAK |

### Aplikacije koje POSTOJE u Fenix V3, ali NE u fina-connect
*(inovacije koje treba povući u stari ERP)*

| App | Opis | Akcija |
|-----|------|--------|
| `ai_cockpit` | AI kontrolni panel | Portirati u fina-connect |
| `evalidator` | E-validator servis | Portirati u fina-connect |
| `stolarija` | Stolarija vertikala | Već postoji u fina-connect (CC_PLAN_STOLARIJA) |
| `shelter` | Sklonište | Provjeri preklapanje s memio_pet |
| `country_plugins` | Lokalizacija po državi | Portirati — višejezičnost |
| `associations` | Upravljanje udrugama | Portirati — NO LIMIT kontekst |

### Iznuđena poboljšanja koja se MORAJU sinkronizirati (obostrano)

| Poboljšanje | Nastalo u | Treba u |
|-------------|-----------|---------|
| Small Doors 3-tier recovery | Fenix V3 | fina-connect |
| Shamir Secret Sharing (sslib) | Fenix V3 | fina-connect |
| pre-commit hook (memory sistem) | fina-connect | Fenix V3 |
| log-session CLI | fina-connect | Fenix V3 (done T-06) |
| WebSocket middleware | fina-connect | Fenix V3 — ako treba live obavijesti |
| Sistemska search infrastruktura | fina-connect | Fenix V3 — potrebno za OS Shell |
| ModuleGateMiddleware (domain split) | fina-connect | Fenix V3 (per-domain kontrola) |
| DATEV 2030 + DocumentSeal | fina-connect | Fenix V3 arhiva |

---

## DIO 2 — GLOBAL OS SHELL

### Vizija

"Windows radna površina kao wrapper cijelog sustava."
Aktivan od logina do odjave, na svakom ekranu, u svakom modulu.
Korisnik nikad ne vidi "praznu stranicu" — uvijek ima kontekst.

### Komponente

```
┌─────────────────────────────────────────────────────┐
│  TOPBAR: Logo | [🔍 Pretraži] | History×3 | Avatar  │
├─────────────────────────────────────────────────────┤
│                                                     │
│  RADNA POVRŠINA (samo na home / praznom stanju):    │
│                                                     │
│  [📁 Arhiva] [💳 POS]  [📊 Plaće] [🏗️ Radni nalozi] │
│  [🧾 Fakture][📋 Stolovi][🤖 AI Doktor][⚙️ Settings] │
│  ... (auto-popunjava se iz dostupnih modula)        │
│                                                     │
├─────────────────────────────────────────────────────┤
│  BOTTOMBAR (mobile only): Home | Search | History   │
└─────────────────────────────────────────────────────┘
```

### Arhitektura implementacije

#### Sloj 1 — Django context_processor (backend)

```python
# core/context_processors.py
def shell_context(request):
    if not request.user.is_authenticated:
        return {}
    return {
        'shell_modules': get_available_modules(request.user),
        'shell_history': get_recent_history(request.user, limit=3),
        'shell_search_enabled': True,
    }
```

`get_available_modules()` — čita iz ModuleGate / permissions, vrača ikone + URL-ove.
`get_recent_history()` — zadnja 3 posjeta (Redis, ključ po useru).

Registrirati u `settings.py → TEMPLATES → OPTIONS → context_processors`.

#### Sloj 2 — Alpine.js ShellComponent (frontend)

Jedna JS komponenta, ugrađena u `base.html`.
Nema build stepa — radi s postojećim Django templateima.

```html
<!-- base.html — jednom, za uvijek -->
<div x-data="ShellApp()" x-init="init()">
  <!-- topbar, search overlay, launcher overlay -->
</div>
<script>
function ShellApp() {
  return {
    searchOpen: false,
    launcherOpen: false,
    searchQuery: '',
    searchMode: 'text', // text | voice | camera
    results: [],
    // ...
  }
}
</script>
```

#### Sloj 3 — Service Worker cache (perzistencija)

Shell assets (ikone, topbar CSS/JS) keširani u browser-u.
Shell se učitava <50ms čak i na sporim vezama.
Zadnja 3 history stavke vidljive i offline.

---

### Search — 4 moda

| Mod | Okidač | Backend |
|-----|--------|---------|
| **Tipkovnica** | Klik na search box ili `/` shortcut | Django full-text (PostgreSQL tsvector) |
| **Mikrofon** | Klik na 🎤 | Web Speech API → isti backend |
| **Kamera / OCR** | Klik na 📷 | Capture → FenixScan OCR → search |
| **Kombinirani** | Automatski — ako sve dozvole | Paralelni pozivi, najbrži pobijedi |

Search je **globalan** — traži po svim modulima odjednom (dokument, firma, osoba, faktura, zadatak).
Rezultati grupirani po tipu: `Firme (3) | Fakture (12) | Dokumenti (5)`.

---

### Radna površina — auto-populacija

```
Pravilo: ikona se prikazuje ako:
  1. Modul je instaliran (ModuleGate)
  2. User ima permission za modul
  3. Modul nije u "hidden" listi (user može skrivati)

Raspored:
  - Sortirano po: last_used DESC (najčešće korišteni prvi)
  - Drag & drop reorder — sprema se u UserProfile.shell_layout (JSON)
  - "Pinned" ikone uvijek na vrhu
```

---

### Top 3 History

```python
# Redis key: shell:history:{user_id}
# Type: LPUSH + LTRIM 3
# Sadržaj: {url, title, icon, timestamp}

# Middleware (automatski bilježi svaki GET zahtjev):
class ShellHistoryMiddleware:
    def process_response(self, request, response):
        if request.method == 'GET' and response.status_code == 200:
            if request.user.is_authenticated:
                push_history(request.user.id, request.path, ...)
        return response
```

Prikazuje se u topbaru desno od search-a: zadnje 3 stranice s ikonama.

---

### Responzivnost — 3 veličine

| Breakpoint | Shell ponašanje |
|------------|-----------------|
| **Mobile** `< 768px` | Topbar: Logo + Search ikona + Avatar. Bottom nav: Home/Search/History. Launcher: full-screen drawer odozdo |
| **Tablet** `768–1280px` | Topbar: Logo + Search box (skraćen) + History×3 + Avatar. Launcher: side panel |
| **Desktop** `> 1280px` | Topbar: Logo + Search box (pun) + History×3 + Avatar + shortcuts. Launcher: floating grid overlay |

---

## DIO 3 — 3 INOVACIJE IZ BUDUĆNOSTI

### F-01: Adaptive Workspace Intelligence
**Koncept:** Shell uči navike korisnika i sam aranžira radnu površinu.

- Ponedjeljak 08:00 → Marija uvijek otvara Arhivu i Fakture: ikone su prve
- Petak poslijepodne → uvijek Plaće: pre-fetch u background
- "Nikad ne otvara Livestock" → ikona skrivena (ali dostupna u search-u)

**Implementacija:** Celery Beat jednom dnevno trenira `UserBehaviorProfile` (5 tablica, numpy). Shell koristi profil kao `shell_layout` override.

**Vrijednost:** Korisnik ima osjećaj "sustav me poznaje" — što je EU #1 ERP diferenciator.

---

### F-02: Cross-Module Universal Clipboard
**Koncept:** Kopiraj entitet u jednom modulu, zalijepi u drugom.

- U Arhivi kopiraš dokumenta → otvoriš Fakture → "Zalijepi dobavljača" → automatski popuni formu
- U Firmama kopiraš kontakt → u WhatsApp modulu: "Pošalji ovoj osobi"
- Clipboard je svjestan tipa: `{type: "company", id: 42, name: "Konjik d.o.o."}`

**Implementacija:** Alpine.js `$clipboard` store + Django session. Ikona "clipboard" u topbaru kada je nešto kopirano.

**Vrijednost:** Eliminira "otvori, kopiraj OIB, zalijepi u drugu karticu" workflow koji ubija produktivnost.

---

### F-03: Voice-First Navigation
**Koncept:** Cijeli sustav navigabilan glasom, bez dodirivanja ekrana.

```
Korisnik: "otvori arhivu za Konjik"
Sustav:   → /hr/documents/arhiva/?company=42

Korisnik: "pokaži fakture ovog tjedna"
Sustav:   → /hr/invoices/?period=this_week

Korisnik: "dodaj novi dokument"
Sustav:   → /hr/documents/arhiva/upload/
```

**Implementacija:** Web Speech API → intent parser (Haiku, 50ms latency) → URL resolver → redirect. Trening korpus iz RouteRegistry.

**Vrijednost:** Terenski radnici (baustela, stolarija, farm) imaju prljave ruke — glas je jedini input. Direktna EU accessibility compliance (EN 301 549).

---

## DIO 4 — 3 PRAKTIČNA RJEŠENJA (odmah primjenjiva)

### P-01: Django context_processor kao temelj
**Problem:** Svaki view bi morao ručno slati module/history u template.
**Rješenje:** Jedan context_processor registriran globalno — nula promjena u postojećim viewovima.
**Trošak:** T-01 u implementaciji, 2h CC.
**Pokrivenost:** 100% stranica automatski.

---

### P-02: Keyboard shortcut router
**Problem:** Power useri gube 3-5 sekundi na svaki modul switch.
**Rješenje:** Global keyboard shortcuts bez JavaScript frameworka.

```javascript
// base.html — 15 linija
document.addEventListener('keydown', (e) => {
  if (e.key === '/' && !isInputFocused()) openSearch()
  if (e.key === 'Escape')                closeOverlays()
  if (e.altKey && e.key === 'a')         go('/hr/documents/arhiva/')
  if (e.altKey && e.key === 'f')         go('/hr/invoices/')
  if (e.altKey && e.key === 'p')         go('/hr/pos/')
})
```

Shortcut cheatsheet u `?` helpu (modal).
**Trošak:** 45 min CC.
**Vrijednost:** Svaki power user štedi 30+ min/dan.

---

### P-03: Progressive Shell Load (PSL)
**Problem:** Shell se danas učitava kao dio svake stranice — blokira render.
**Rješenje:** Shell HTML inline (nula latency), data async (ne blokira render).

```html
<!-- Topbar se renderira odmah (inline HTML, nema AJAX) -->
<!-- Module ikone se učitavaju async nakon main content-a -->
<!-- History se učitava iz localStorage (0ms) dok API ne odgovori -->
```

**Trošak:** 3h CC — mijenja samo `base.html` i jedan API endpoint.
**Vrijednost:** Perceived performance +40% na mobilnim uređajima.

---

## SAŽETAK — REDOSLJED IMPLEMENTACIJE

```
FAZA 0 (1 tjedan):
  → Sync audit: portirati permissions + konto + konto u Fenix V3 (🔴 prioriteti)
  → Portirati ai_cockpit + evalidator u fina-connect

FAZA 1 (1 tjedan):
  → P-01: context_processor (temelj za sve ostalo)
  → P-03: PSL base.html refactor
  → Shell topbar: search box + history×3 + avatar (desktop + tablet)

FAZA 2 (1 tjedan):
  → Search backend: PostgreSQL tsvector globalni index
  → Mikrofon mod (Web Speech API)
  → Launcher / radna površina (grid overlay)
  → Mobile bottombar

FAZA 3 (1 tjedan):
  → P-02: Keyboard shortcuts
  → Kamera / OCR mod search
  → Drag & drop shell layout

FAZA 4 (2 tjedna):
  → F-02: Cross-module clipboard
  → F-03: Voice navigation (Haiku intent parser)

FAZA 5 (3 tjedna):
  → F-01: Adaptive Workspace Intelligence (Celery + UserBehaviorProfile)

UKUPNO: ~9 tjedana do kompletnog OS Shell-a s 3 future inovacije
```

---

## ADR REF
Kada implementacija krene → kreirati:
- `ADR-001-global-os-shell-architecture.md`
- `ADR-002-search-multimodal-approach.md`
- `ADR-003-sync-strategy-v3-vs-erp.md`
