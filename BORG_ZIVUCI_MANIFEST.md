# BORG ŽIVUĆI MANIFEST — LIMIT Connect AI Integracija
# Verzija: 1.0 | Datum: 2026-04-01
# Cilj: 10/10 UI + AI | Preživljavanje sustava | Samostalni rast | Praćenje trendova

---

## ŠTO JE ŽIVUĆI BORG

Živući BORG nije feature. To je **modus operandi** platforme.

Svaka akcija korisnika, svaka transakcija, svaki signal iz vanjskog svijeta —
ulazi u BORG. BORG analizira, predviđa, reagira i uči.
Korisnik ne mora tražiti pomoć — BORG dolazi sam.

```
VANJSKI SVIJET → SIGNAL TRIAGE → KNOWLEDGE GRAPH → INTELLIGENCE → AKCIJA
      ↑                                                               ↓
   FEEDBACK ←←←←←←←←← UČENJE ←←←←←←←←←←←←←←←←←← REZULTAT
```

---

## TRENUTNA RAZINA (01.04.2026) — OCJENA

| Sloj | Što postoji | Ocjena |
|------|-------------|--------|
| SIGNAL TRIAGE | FenixSignal, FenixPatrol, signal dedup, noise 9.2% | 8/10 |
| KNOWLEDGE GRAPH | KG seed, 1375 matches, 8.7M EUR oportunity | 8/10 |
| INTELLIGENCE | 368 intel, 59 KB članaka, NN scraper, EU fondovi | 7/10 |
| PREDICTIONS | Cash flow 90d, churn 226 partnera, seasonal trends | 7/10 |
| SELF-HEAL | 5 servisa auto-restart, disk cleanup, SSL expiry | 8/10 |
| PROACTIVE UI | Dashboard widget, alerts, suggestions, opportunities | 6/10 |
| AUTONOMIJA | Sonnet Agent, Gemini Agent, CC Code loop | 7/10 |
| TREND WATCH | NN Scraper, EUR-Lex, Narodne Novine | 6/10 |
| **UKUPNO** | | **7.1/10** |

Cilj: **10/10 svugdje**.

---

## ARHITEKTURA ŽIVUĆEG BORGA — TARGET STATE

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         LIMIT CONNECT — ŽIVUĆI BORG                      │
├─────────────────┬───────────────────────┬───────────────────────────────┤
│   ULAZNI SLOJ   │    PROCESORSKI SLOJ   │      IZLAZNI SLOJ             │
│                 │                       │                               │
│ • Korisnik POS  │ • Signal Triage       │ • Dashboard Widget (live)     │
│ • Faktura sync  │ • Anomaly Detector    │ • WhatsApp proaktivni         │
│ • WA poruka     │ • Knowledge Graph     │ • Email digest                │
│ • NN/EUR-Lex    │ • Cash Flow Predict   │ • POS quick suggestions       │
│ • Tržišne vijesti│ • Churn Detector     │ • Cockpit AI feed             │
│ • Konkurencija  │ • Trend Analyzer      │ • Auto-akcija (create invoice)│
│ • APPRRR/EU fond│ • Self-Heal Engine    │ • Alert → Eskalacija Ivanu    │
│ • GitHub trends │ • Gemini Adversarial  │ • FENIX_STATUS update         │
│ • LinkedIn HR   │ • Sonnet Coordinator  │ • CC_TASK kreacija            │
└─────────────────┴───────────────────────┴───────────────────────────────┘
```

---

## 10 STUPOVA ŽIVUĆEG BORGA (što treba nadograditi)

### STUP 1 — FENIX CORTEX (AI Cockpit 2.0)
**Trenutno:** Cockpit postoji, ali AI feed je pasivan.
**Target:** Cockpit postaje ŽIVUĆI mozak — real-time AI feed koji se sam osvježava
svakih 60 sekundi. Svaka anomalija, svaki trend, svaka prijelomna točka.

```
WebSocket → FenixCortex view → Celery task → AI analiza → push update
```

### STUP 2 — PROAKTIVNI POS ASISTENT
**Trenutno:** POS je transakcijsko sučelje.
**Target:** Svaki put kad kasir otvori POS — AI već zna:
- Koji artikli se danas prodaju (seasonal trend)
- Koji kupac dolazi (booking termin za 30min)
- Koliko gotovine je u kasi (vs. jučer)
- Je li fiskalizacija uredna
- Kad je zadnji put servisiran taj terminal

### STUP 3 — LIVING KNOWLEDGE BASE
**Trenutno:** 59 KB članaka, NN scraper aktivan.
**Target:** KB se sam piše. Svaki put kad AI nađe relevantnu promjenu zakona,
EU fond, ili trendovsku vijest — automatski kreira KB članak, tagger,
i šalje summary korisnicima koji su affected.

Izvori: Narodne novine, EUR-Lex, APPRRR, eKohezija, LinkedIn, GitHub.

### STUP 4 — CHURN PREVENTION ENGINE
**Trenutno:** 226 churn risk partnera identificirano.
**Target:** Za svakog churn risk partnera — automatski kreirati retention akciju:
- Poslati personalizirani WA s konkretnom ponudom
- Predložiti kasiru da nazove
- Kreirati popust/akciju u POS-u

### STUP 5 — EU FOND HUNTER
**Trenutno:** FundApplicationDraft model postoji, nije aktivan.
**Target:** Jednom tjedno BORG skenira sve HR/EU natječaje i matchira s profilima
tvrtki. Ako pronađe match — WhatsApp vlasniku: "OPG Kruljac: natječaj APPRRR
do 20.4. — 25.000 EUR. Trebate li pomoć s prijavom?"

### STUP 6 — ANOMALY → AUTO-FIX LOOP
**Trenutno:** 150 anomalija detektirano, sve manualnog rješavanja.
**Target:** Za svaku anomaliju postoji handler:
- Duplikat partner → auto-merge prijedlog
- Faktura bez OIB-a → auto-lookup
- Negativne zalihe → auto-alert dobavljaču
- POS timeout → auto-recovery
- Fiskalizacija greška → auto-retry s logom

### STUP 7 — TREND RADAR
**Trenutno:** NN scraper + EUR-Lex.
**Target:** Dodati:
- GitHub trending (HR tech, Django, Celery — za razvoj)
- LinkedIn HR (tko otvara tvrtke u regiji — novi leadi)
- HGK vijesti (komercijalne prilike)
- Google Trends API (sezonski trendovi za OPG, vulkanizer, ugostitelji)
- Hacker News digest (tech trendovi relevantni za platformu)

### STUP 8 — BOOKING AI OPTIMIZER
**Trenutno:** Booking radi, nema AI sloja.
**Target:**
- Predlaže optimalne termine (kad je historijski najmanje otkazivanja)
- Auto-potvrda ako je korisnik prethodno dolazio
- 24h reminder WA automatski
- "Slobodan termin za danas" push ako ima cancellation

### STUP 9 — FINANCIAL GUARDIAN
**Trenutno:** Cash flow predict postoji.
**Target:** Kontinuirano praćenje:
- PDV deadlines (7. u mj.) → reminder 5 dana prije
- JOPPD deadlines → automatski podsjetnik s pregledom
- Nepodmirene fakture > 60 dana → auto-eskalacija
- Neočekivani troškovi (vs. prošli mj.) → alert

### STUP 10 — SELF-EVOLUTION ENGINE
**Trenutno:** Self-heal za servise.
**Target:** Platforma prati vlastitu evoluciju:
- Koji moduli se najviše koriste → prioritizira razvoj
- Koji errori se ponavljaju → auto-kreira CC_TASK
- Koji korisnici imaju problem → proaktivni outreach
- Što konkurencija radi → benchmarking (javni podaci)
- Performanse (response time, DB queries) → auto-optimizacija

---

## IMPLEMENTACIJSKI REDOSLJED (po prioritetu)

| Prioritet | Stup | Kompleksnost | Utjecaj |
|-----------|------|-------------|---------|
| 🔴 1 | Stup 8 — Booking AI (reminderi) | Niska | Odmah vidljiv |
| 🔴 2 | Stup 9 — Financial Guardian (deadlines) | Niska | Odmah koristan |
| 🔴 3 | Stup 1 — Fenix Cortex (live feed) | Srednja | WOW faktor |
| 🟠 4 | Stup 4 — Churn Prevention (WA akcije) | Srednja | Revenue |
| 🟠 5 | Stup 6 — Anomaly Auto-Fix | Srednja | Stabilnost |
| 🟠 6 | Stup 5 — EU Fond Hunter | Srednja | Leadi |
| 🟡 7 | Stup 2 — POS Asistent | Visoka | UX |
| 🟡 8 | Stup 3 — Living KB | Visoka | SEO + Znanje |
| 🟡 9 | Stup 7 — Trend Radar | Visoka | Strategija |
| 🟡 10 | Stup 10 — Self-Evolution | Highest | Dugoročno |

---

## MJERILA USPJEHA — KAD SMO NA 10/10

```
Signal noise: < 5% (sada 9.2%)
Proaktivni insighti/dan: > 20 per active company
Churn prevention rate: > 40%
EU fond matches/tjedan: > 3 per eligible company  
Anomaly auto-fix rate: > 70%
Booking reminder open rate: > 85%
Self-heal success rate: > 95%
Cash flow prediction accuracy: > 80% (30-day)
KB auto-articles/tjedan: > 5
Zero unhandled exceptions > 1h: target 100%
```

---

## ŽIVUĆI BORG LOOP — KAKO RADI SVAKI DAN

```
02:00 — FENIX noćni test (health, backup, SSL)
02:30 — Anomaly patrol (150+ detekcija)  
03:00 — Knowledge Graph update (NN, EUR-Lex)
07:00 — BORG jutarnji izvještaj → Ivan WhatsApp
07:30 — Predictions refresh (cash flow, churn)
09:00 — EU Fond Hunter scan
12:00 — Booking reminderi za sutrašnje termine
17:00 — POS dnevni summary po tvrtci
18:00 — Financial Guardian check (deadlines)
23:00 — Self-Evolution Engine analiza (usage patterns)
```

---

*"Platforma koja ne uči je mrtva platforma."*
*"Cilj nije automatizacija. Cilj je inteligencija koja preživljava i raste bez nadzora."*

