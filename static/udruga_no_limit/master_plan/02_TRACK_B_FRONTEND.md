# TRAK B — FRONTEND / UI

**Vlasnik**: Frontend AI agent
**File područje**: `templates/cmd/` (NOVO), `templates/pos/cmd/` (NOVO), `static/cmd/` (NOVO)
**NE diraj**: Backend kod (`*/views.py`, `*/models.py`), QA Lab, no_limit app

---

## CILJ

Dvije komponente, **isti backend**, **različiti UI** za različite kontekste:

```
                    BACKEND (Trak A + C)
                    Resolver + Intent Compiler + Embeddings
                              |
                ┌─────────────┴─────────────┐
                │                           │
                ▼                           ▼
     ┌──────────────────┐        ┌──────────────────────┐
     │  MODUL B1:       │        │  MODUL B2:           │
     │  Universal       │        │  POS Command         │
     │  Command Surface │        │  Mode                │
     │  (UCS)           │        │  (PCM)               │
     │                  │        │                      │
     │  - puni ekran    │        │  - mali ekran        │
     │  - tipkovnica    │        │  - voice-first       │
     │  - voice         │        │  - multi-item kamera │
     │  - kamera        │        │  - predictive cart   │
     │  - file upload   │        │  - barcode primarno  │
     │  - svi moduli    │        │  - samo POS akcije   │
     └──────────────────┘        └──────────────────────┘
```

**Iste funkcije, različita UX:**
- Voice input → oba imaju
- Camera input → oba imaju (UCS = OCR, PCM = multi-item detekcija)
- Tekst input → oba imaju
- Intent resolution → isti backend
- Predictive AI → oba (UCS = "Today's actions", PCM = "Predictive cart")

---

## MODUL B1 — UNIVERSAL COMMAND SURFACE (UCS)

### URL
- Ulazna točka: `https://limit-connect.com/` (zamjenjuje trenutni dashboard)
- Klasični prikaz fallback: `https://limit-connect.com/classic/` (toggle)

### Layout (full screen, bilo koji uređaj > 1024px)

```
┌────────────────────────────────────────────────────────────────────┐
│  Fenix V3   [Logo]                        [User] [Settings] [↻]   │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│              👋 Dobro jutro, Ivan. Što ćeš danas?                 │
│                                                                    │
│   ┌──────────────────────────────────────────────────────────┐    │
│   │  🎤  ⌨️  📷  📎    [ Što želiš napraviti?           🔍 ]  │    │
│   └──────────────────────────────────────────────────────────┘    │
│                                                                    │
│   ⚡ AMBIENT AI — predloži akcije na osnovi konteksta:             │
│                                                                    │
│   ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐    │
│   │ 📋 PDV Q1 Nikolić│  │ 📧 3 nepročitana │  │ 📄 12 fakt.  │    │
│   │ rok za 4 dana    │  │ obavijesti       │  │ za arhivu    │    │
│   └──────────────────┘  └──────────────────┘  └──────────────┘    │
│                                                                    │
│   ─────────────────────────────────────────────────────────────    │
│                                                                    │
│   Brzi pristup modulima (ako ne znaš što pitati):                  │
│   [Fakture] [Računovodstvo] [Arhiva] [POS] [Zaposleni] [Više]     │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

### Komponente

#### B1.1 — Command Bar (`templates/cmd/command_bar.html`)
- Alpine.js komponenta `<x-command-bar>`
- 4 input modaliteta: voice, text, camera, file
- Auto-focus na load
- Ctrl+K shortcut bilo gdje na stranici otvara
- Submit → POST `/api/cmd/resolve/` → handler

#### B1.2 — Voice Input (`static/cmd/voice.js`)
- WebRTC MediaRecorder API
- Whisper.cpp lokalni endpoint na backend-u (ne OpenAI)
- Real-time feedback (volumen indicator)
- Push-to-talk + wake-word („Fenix")

#### B1.3 — Camera Input (`static/cmd/camera.js`)
- `getUserMedia({video: {facingMode: 'environment'}})`
- Capture JPEG, šalje na `/api/cmd/ocr/`
- Pre-processing (auto-crop, contrast)

#### B1.4 — Result Renderer (`templates/cmd/result.html`)
- HTMX swap-target
- Renderira jedan od 4 tipa odgovora:
  - **Action confirmed** — „PDV obrazac kreiran, otvori?"
  - **Disambiguation** — „Imam 3 firme Nikolić, koji?"
  - **Module embed** — otvara cijeli postojeći modul kao panel
  - **Error** — „Nisam siguran, želiš li ručno?"

#### B1.5 — Ambient AI Suggestions (`templates/cmd/ambient.html`)
- 3 kartice s preporučenim akcijama
- Server-side render iz `core/ambient/predictor.py` (Trak C)
- Refresh svakih 60 sec

### Sprint razred

| Sprint | Tjedan | Akcija |
|---|---|---|
| 1 | T3 | B1.1 Command Bar (text only) + B1.4 Result Renderer + intgracija s Resolver |
| 2 | T4 | B1.5 Ambient AI Suggestions + B1.2 Voice Input |
| 3 | T5 | B1.3 Camera Input (OCR) + B1.4 Module embed (otvara postojeće module kao iframe/HTMX) |
| 4 | T6 | Polish, prijevod HR/DE/EN, accessibility audit |

---

## MODUL B2 — POS COMMAND MODE (PCM)

### URL
- Ulazna točka: `https://limit-connect.com/hr/pos/cmd/`
- Klasični POS fallback: `https://limit-connect.com/hr/pos/` (toggle)

### Layout — Adaptivni 3-tier

#### Tier 1: Mobile POS (< 768px)
```
┌──────────────────────┐
│ 🎤 ▼  📷  ⌨️  ←POS  │
├──────────────────────┤
│                      │
│  ⚡ Predictive Cart  │
│  ┌────────────────┐  │
│  │ ☕ Kava   2.50€│  │
│  │ 🥖 Kruh   1.50€│  │
│  └────────────────┘  │
│                      │
│  Trenutni račun:     │
│  (prazno)            │
│                      │
│  [+] [▲ swipe grid]  │
├──────────────────────┤
│  💰 UKUPNO    0.00€  │
└──────────────────────┘
```
- 80 % command-first, 20 % grid (swipe up za grid)

#### Tier 2: Tablet (768–1200px)
```
┌──────────────────────────────────┐
│ 🎤 ▼  📷  ⌨️           ←POS klas. │
├────────────────┬─────────────────┤
│ TRENUTNI RAČUN │ KATEGORIJE      │
│                │ ┌──┐ ┌──┐ ┌──┐  │
│ ☕ Kava    2.50│ │🥤│ │🥖│ │🍰│  │
│ 🥖 Kruh    1.50│ └──┘ └──┘ └──┘  │
│                │                 │
│                │ Predictive:     │
│                │ ☕ + 🥖 (jutro) │
├────────────────┼─────────────────┤
│ UKUPNO   4.00€ │ 💳 KARTICA      │
└────────────────┴─────────────────┘
```
- 50/50 split

#### Tier 3: Desktop POS (> 1200px)
```
┌──────────────────────────────────────────────────────┐
│ 🎤  Cmd+K otvara command bar           ←POS klasični │
├─────────────────────────┬────────────────────────────┤
│ TRENUTNI RAČUN          │ FULL GRID 6×8 ikona        │
│                         │                            │
│ ☕ Kava            2.50│ [grid kategorija + proiz.] │
│ 🥖 Kruh            1.50│                            │
│ ...                     │                            │
├─────────────────────────┼────────────────────────────┤
│ UKUPNO          4.00€  │ 💳 Plaćanje               │
└─────────────────────────┴────────────────────────────┘
```
- 30 % command, 70 % grid (klasično + command kao opcija)

### POS specifične funkcije (uz iste kao UCS)

#### B2.1 — Voice Queue (`static/pos/cmd/voice_queue.js`)
- Prodavač govori serijski: „Coca cola 3, kruh, dva piva, vrećica"
- Sustav dodaje sve u korpu, čeka „dosta" / „totale" za potvrdu
- Backend: ista jezgra kao UCS Voice, ali s POS intent set-om

#### B2.2 — Multi-item Camera (`static/pos/cmd/multi_item.js`)
- Jedna fotografija = cijeli pladanj
- Backend: Gemini Vision API call (Trak C handler)
- Confidence scoring, prodavač potvrđuje

#### B2.3 — Predictive Cart (`templates/pos/cmd/predictive.html`)
- Pri otvaranju POS-a, AI predloži vjerojatnu kupovinu (vrijeme + dan + povijest)
- Jedan klik za prihvaćanje
- Backend: `core/ambient/pos_predictor.py` (Trak C)

#### B2.4 — Mode toggle (`templates/pos/cmd/mode_switcher.html`)
- 3 opcije u settingsu: „Klasični / Command / Auto (po veličini ekrana)"
- Spremljeno u `UserProfile.pos_preferred_mode`

#### B2.5 — Barcode Scanner Integration (`static/pos/cmd/barcode.js`)
- HID scanner ulaz (USB barcode reader emulira tipkovnicu)
- + WebRTC kamera scan kao fallback
- Auto-add proizvod, čeka quantity (voice ili tipka)

### Sprint razred

| Sprint | Tjedan | Akcija |
|---|---|---|
| 1 | T7 | B2 osnovni adaptive layout (3 tier) + Mode switcher |
| 2 | T8 | B2.5 Barcode + B2.1 Voice Queue |
| 3 | T9 | B2.2 Multi-item Camera + B2.3 Predictive Cart |
| 4 | T10 | Pilot s 1 trgovinom (kafić ili pekara), iterirati na osnovu feedback-a |

---

## ZAJEDNIČKE KOMPONENTE (B1 + B2 dijele)

| Komponenta | Path | Korisnik |
|---|---|---|
| Voice recorder | `static/cmd/voice.js` | UCS + PCM |
| Camera capture | `static/cmd/camera.js` | UCS + PCM |
| Result renderer | `templates/cmd/result.html` | UCS + PCM |
| Confidence indicator | `templates/cmd/confidence.html` | UCS + PCM |
| Confirmation flow | `static/cmd/confirm.js` | UCS + PCM |
| API klijent | `static/cmd/api.js` | UCS + PCM |

**Pravilo**: ako bilo što treba i UCS i PCM, ide u `static/cmd/` ili `templates/cmd/`. Specifično za POS ide u `static/pos/cmd/` ili `templates/pos/cmd/`.

---

## SLJEDEĆA AKCIJA

→ **Sprint 1, B1.1 Command Bar (text only)**. Bez voice/camera prvo. Samo input polje koje šalje POST na `/api/cmd/resolve/` (čeka da Trak C postavi endpoint).

## ZADNJA IZMJENA

| Datum | Tko | Što | Sljedeći korak |
|---|---|---|---|
| 21.04.2026. | Opus design | Plan napisan | Pokreni Sprint 1 B1.1 nakon S1 (Trak A) |

---

## DEPENDENCIES

- **Čeka**: S1 (Trak A — Searchable mixin gotov), zatim S2 (Trak C — `/api/cmd/resolve/` endpoint)
- **Blokira**: Trak F pilot (memio.world Triple DNA UI ovisi o UCS)


---

## FALLBACK + OFFLINE STRATEGIJA (Načelo #11)

### Mode toggle u UI

```html
<!-- templates/cmd/mode_switcher.html -->
<select x-model="mode" @change="saveMode()">
  <option value="auto">⚡ Auto (AI + fallback)</option>
  <option value="classic">📋 Klasični (uvijek)</option>
  <option value="command">🎯 Samo Command (napredni)</option>
</select>
```

Spremljeno u `UserProfile.preferred_ui_mode`. Default: **classic** za postojećih 110 firmi (ne mijenjamo im UX bez da kliknu opt-in).

### Klasični UI rute zauvijek dostupne

Sve postojeće rute pod `/classic/` prefix:
- `https://limit-connect.com/classic/` — stari dashboard
- `https://limit-connect.com/classic/hr/invoicing/` — stari invoicing UI
- `https://limit-connect.com/classic/hr/pos/` — stari POS

**Garancija**: ove rute se NIKAD ne uklanjaju, ne mijenjaju, ne deprecated. Stare URL-ove uvijek poštujemo s 301 redirect na `/classic/...`.

### Service Worker za offline PWA

```javascript
// static/cmd/sw.js
const CRITICAL = [
  '/classic/hr/pos/', '/classic/hr/accounts/login/',
  '/classic/hr/companies/list/', '/classic/hr/invoicing/list/?recent=1'
];

self.addEventListener('install', e => {
  e.waitUntil(caches.open('fenix-v1').then(c => c.addAll(CRITICAL)));
});

self.addEventListener('fetch', e => {
  if (CRITICAL.some(r => e.request.url.includes(r))) {
    e.respondWith(caches.match(e.request).then(r => r || fetch(e.request)));
  }
});
```

### Network speed monitor (auto-fallback)

```javascript
// static/cmd/network_monitor.js
class AINetworkMonitor {
  constructor() { this.history = []; this.threshold = 1500; }
  recordLatency(ms) {
    this.history.push(ms);
    if (this.history.length > 10) this.history.shift();
    const avg = this.history.reduce((a,b)=>a+b, 0) / this.history.length;
    if (avg > this.threshold && this.mode !== 'classic') {
      this.switchMode('classic', "Mreža spora — privremeni klasični mod");
    } else if (avg < 500 && this.userPreference === 'auto') {
      this.switchMode('command', "Mreža OK — AI ponovno aktivan");
    }
  }
}
```

### POS Command Mode — offline-prvo

POS je najkritičniji case. Specifične mjere:
- **Cijeli POS UI** pre-cached u Service Worker (radi bez interneta)
- **Lokalni proizvod katalog** sinkroniziran 1× dnevno
- **Račun se sprema lokalno** (IndexedDB), syncia kad mreža dođe
- **Pri offline modu** pokazuje crveni indikator "OFFLINE — sync kad dođe mreža"
- Voice + multi-item kamera AUTOMATSKI off ako nema interneta (jer nema Whisper/Gemini)
- Vraća se na barcode + tipkanje (klasični POS workflow)

## ARHITEKTONSKE NAPOMENE

- **Iste API rute** za UCS i PCM (isti `/api/cmd/`) — različit kontekst u payload-u
- **Mode hint**: `{"context": "ucs"}` ili `{"context": "pos"}` u zahtjevu — backend zna koji set intent-a koristiti
- **Whisper lokalno** (privacy) — NE OpenAI Whisper API
