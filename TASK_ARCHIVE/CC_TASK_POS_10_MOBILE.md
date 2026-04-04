# CC_TASK_POS_10_MOBILE.md
# POS Modul — Mobile-First Redizajn | 10/10
# Kreirao: Opus | Datum: 2026-03-30

---

## DIJAGNOZA — Trenutno stanje

### Joker.html (1.247 linija) — centralni POS template
- Desktop: Grid 2-kolumna (proizvodi | košarica) — **7/10**
- Mobile (<900px): Vertikalni flex, basket dole — **4/10**
- Mobile (<500px): Stisnuto, teško za palac — **3/10**

### Ključni problemi na mobitelu:

1. **Brze tipke (Quick Keys)** — skrivene unutar scroll-a, ne izdvajaju se
2. **Košarica** — na dnu zauzima 50vh ali se ne vidi dok se scrollaju proizvodi
3. **Forme (plaćanje, količina)** — mali inputi, teški za touch
4. **Nema swipe geste** — sve je klik, nema native mobile UX
5. **Mod switching** — nema načina za brzo prebacivanje retail/gastro/service
6. **Proizvodi i košarica** — ne vide se istovremeno na malom ekranu

---

## ARHITEKTURA — Joker 2.0

### Principi:
- **Jedan ekran, sve kontrole** — nikad ne napuštaš POS
- **Palac-first** — sve dostupno jednim palcem iz donjeg dijela ekrana
- **Context-aware** — UI se prilagođava modu (retail/gastro/service/bakery)
- **Split-view** — košarica UVIJEK vidljiva (collapsible drawer)

### Layout (mobile):

```
┌─────────────────────────────────┐
│ STATUS BAR (kompaktan)          │  ← 36px: firma · sat · Z
├─────────────────────────────────┤
│                                 │
│     RADNA ZONA                  │  ← Flex-grow, scrollable
│     (proizvodi / stolovi /      │     Sadržaj ovisi o modu
│      brze tipke / pretraga)     │
│                                 │
├─────────────────────────────────┤
│ ┌─ KOŠARICA DRAWER ───────────┐ │  ← Swipe up/down
│ │ 3× Burek sir    15,00 €    │ │     Collapsed: samo total
│ │ 1× Kava          1,80 €    │ │     Expanded: full list
│ │ ─────────────────────────── │ │
│ │ UKUPNO:          16,80 €   │ │
│ └─────────────────────────────┘ │
├─────────────────────────────────┤
│ 🏪  🍽  ✂️  [  💰 POS  ]  🛒  ⚡│  ← 56px: Mode bar (fixed)
└─────────────────────────────────┘
```

### Mode Bar (donja traka):

```
┌──────────────────────────────────────────┐
│  🏪    🍽    ✂️    [ 💰 ]    🛒    ⚡   │
│ Retail Gastro Usluge  POS   Košar  Brze  │
└──────────────────────────────────────────┘
```

Centralna ikona: **💰 POS** (uvijek aktivna — otvara/zatvara POS)
Lijevo od centra:
- 🏪 Retail — product grid + barcode
- 🍽 Gastro — stolovi + narudžbe
- ✂️ Usluge — usluge + trajanje

Desno od centra:
- 🛒 Košarica — expand/collapse drawer
- ⚡ Brze tipke — overlay panel iznad svega

### Brze tipke — Floating Overlay:

```
┌─────────────────────────────────┐
│ ⚡ BRZE TIPKE              ✕   │  ← Fixed overlay
├─────────────────────────────────┤
│ ┌────┐ ┌────┐ ┌────┐ ┌────┐   │
│ │Bur │ │Kif │ │Kav │ │Čaj │   │  ← 4 kolone, veliki gumbi
│ │3€  │ │2€  │ │1.8€│ │1.5€│   │     min-height: 64px
│ └────┘ └────┘ └────┘ └────┘   │
│ ┌────┐ ┌────┐ ┌────┐ ┌────┐   │
│ │Sok │ │Pizza│ │XXX │ │YYY │   │
│ └────┘ └────┘ └────┘ └────┘   │
└─────────────────────────────────┘
│  (košarica preview ostaje       │
│   vidljiva ispod overl.)        │
└─────────────────────────────────┘
```

### Košarica Drawer — 3 stanja:

1. **Collapsed** (default): Samo total bar — "3 stavke · 16,80 €"
2. **Peek** (swipe up): Lista stavki + total — 40vh
3. **Full** (swipe up više): Cijeli ekran — editabilne stavke, korekcije, brisanje

### Forme u fokusu — Full-screen modal:

Kad korisnik tapne na input (količina, popust, komentar):
- Forma se podiže na **cijeli ekran** (z-index: 9000)
- Numerička tipkovnica za količinu (custom, veliki gumbi)
- "Gotovo" gumb vraća na POS

---

## IMPLEMENTACIJA — Faze

### Faza 1: Mode Bar + Layout refactor
- Nova donja traka s mod ikonama
- Layout presjek: status (36px) + radna zona (flex) + drawer + mode bar (56px)
- CSS custom properties za mod-specifične boje
- POSTerminal.pos_type kontrolira koje ikone su aktivne

### Faza 2: Košarica Drawer
- touch-action: pan-y na drawer handle
- JavaScript touch event handler (touchstart/move/end)
- 3 stanja: collapsed/peek/full
- Snap-to-state animacija (CSS transition)
- Inline edit: tap na qty → mini numpad
- Swipe-left na stavku → delete

### Faza 3: Brze tipke overlay
- Position: fixed, z-index: 8000
- Animacija: slide-up iz donje trake
- Grid 4×N (mobile) / 6×N (tablet)
- Tap → dodaj u košaricu + toast + haptic feedback
- Košarica total UVIJEK vidljiv ispod overlaya

### Faza 4: Full-screen fokus forme
- Quantity input → fullscreen numpad
- Payment input → fullscreen s cash quick buttons
- Partner/komentar → fullscreen s keyboard
- Backdrop blur na ostatak POS-a

### Faza 5: AI integracija
- AI barcode: kamera → prepoznavanje → auto-add
- AI voice: "dodaj 3 bureka" → NLP → add_item
- AI sugestije: "Kupci koji kupuju X obično uzmu Y"
- Smart pricing: automatski popust za količinu

---

## MODOVI — Što se mijenja

### 🏪 Retail (default)
- Product grid s kategorijama
- Barcode scanner (kamera)
- Brze tipke najčešćih artikala
- Pfand sustav (DE)

### 🍽 Gastro
- Table grid umjesto product grid
- Narudžba po stolu
- KDS (Kitchen Display) push
- Split bill, tip, service charge

### ✂️ Usluge
- Service picker (trajanje + cijena)
- Klijent odabir (Partner FK)
- Timer za uslugu u tijeku
- Booking integracija

### 🥐 Pekara (Quick)
- Samo brze tipke (nema grid)
- Veliki gumbi za najčešće proizvode
- Brzi checkout (1 tap → naplata)
- Dnevni specijal banner

---

## PRIORITET IMPLEMENTACIJE

| # | Zadatak | Utjecaj | Kompleksnost |
|---|---------|---------|-------------|
| 1 | Mode bar (donja traka) | Visok | Srednje |
| 2 | Košarica drawer (swipe) | Visok | Visoko |
| 3 | Brze tipke overlay | Visok | Nisko |
| 4 | Fullscreen fokus forme | Srednje | Srednje |
| 5 | AI voice/camera | WOW | Visoko |

---

*Plan kreiran: 2026-03-30 | Cilj: POS #1 HR + DE*
