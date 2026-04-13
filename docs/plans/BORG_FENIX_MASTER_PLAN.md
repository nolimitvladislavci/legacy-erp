# BORG SYSTEM — FENIX MASTER PLAN
# Datum: 2026-03-23
# Autor: Sonnet (koordinator), odobrio: Ivan Brtan
# Status: AKTIVNO — svi agenti čitaju ovo

---

## Što je BORG FENIX?

Jedina ERP platforma koja:
1. Asimilira vanjsku "materiju" (zakone, račune, tržište, regulativu) u stvarnom vremenu
2. Prilagođava se automatski — bez intervencije korisnika
3. Pronalazi i iskorištava legalne prednosti (rupe u zakonima, izuzeća, fondove)
4. Uči iz svakog dokumenta koji prođe kroz sustav

Ovo NIJE naučna fantastika. Svaki komponent postoji. Arhitektura je pitanje 90 dana.

---

## 4 SLOJA SUSTAVA

### SLOJ 1 — ASIMILACIJA (ingestion)
Što ulazi u sustav:
- Računi (batch scan do 100, OCR, multi-page grouping)
- Zakoni i propisi (Bundesrat RSS, EUR-Lex API, Narodne novine, FINA objave)
- Tržišni signali (konkurencija, cijene, trendovi)
- Transakcije klijenata (POS real-time, invoicing, arhiva)

### SLOJ 2 — TROJSTVO (procesiranje)
| Agent | Uloga | Brzina | Trošak |
|-------|-------|--------|--------|
| HAIKU | Klasifikacija, OCR verifikacija, sortiranje | ms | minimal |
| GEMINI PRO 2.5 | Duboka analiza, compliance, rupe u zakonima | sekunde | srednji |
| SONNET | Koordinacija, strategija, Ivan → produkcija | sekunde | srednji |
| CC CODE | Implementacija, deploy, testiranje | minute-sati | 0 (interna) |

### SLOJ 3 — FENIX KNOWLEDGE CORE
Versionirana baza znanja:
- DE propisi: GoBD, KassenSichV, DSFinV-K, UStG, HGB, AO
- HR propisi: FINA, PDV zakon, ZOR, ZPD, GDPR-HR
- EU propisi: GDPR, eIDAS, PSD2, AI Act, ESG reporting
- Sudska praksa (BFH za DE, Visoki upravni sudovi za HR)
- Changelog: svaka promjena zakona = timestamped entry

### SLOJ 4 — AKCIJA
- Auto-knjiženje: račun → kontni plan → 0 klikova
- Compliance alert: zakon se promijenio → prilagodi workflow
- Legal exploit: pronađena rupa → notifikacija klijentu → implementacija
- EU Fondovi: klijent ispunjava uvjete → automatska prijava
- Adaptivni UI: pokaži samo ono što je legalno u trenutnoj jurisdikciji

---

## 90-DNEVNI PLAN

### Faza 1 — ASIMILACIJA RAČUNA (0-30 dana) ← OVDJE SMO
- CC_TASK_SCAN_BATCH_100.md — batch scan do 100, WebP kompresija
- CC_TASK_SCAN_MULTIPAGE_AI.md — Haiku grupira višestranične račune  
- CC_TASK_SCAN_UI_2TIPKE.md — minimalni UI, progresivno otkrivanje

### Faza 2 — COMPLIANCE WATCHDOG (30-60 dana)
- GEMINI_TASK_COMPLIANCE_WATCHDOG_V2.md — RSS ingestion + diff engine
- CC_TASK_KNOWLEDGE_CORE.md — baza znanja versioning
- CC_TASK_LEGAL_EXPLOIT_ENGINE.md — traženje rupa (popis izuzeća iz zakona)

### Faza 3 — AUTONOMIJA (60-90 dana)  
- GEMINI_TASK_AUTO_BOOKING.md — auto-knjiženje bez klikova
- CC_TASK_EU_FUNDS_AUTOPILOT.md — automatska prijava na fondove
- GEMINI_TASK_MARKET_INTEL.md — praćenje konkurencije

### Faza 4 — SYMBIOSIS (90+ dana)
- Sustav koji se sam prilagođava
- Klijent prima prijedloge: "Uštedjeli smo vam X EUR ovim izuzećem"
- BORG asimilira novog klijenta za <24h

---

## PRAVILA KOORDINACIJE

1. Sonnet piše sve TASK fajlove — nikad CC ili Gemini sami
2. FENIX_STATUS.md = jedina istina, ažurira se na kraju svake sesije
3. Haiku = reflexi (OCR, sort) — nikad za strategiju
4. Gemini = dubina (zakoni, fondovi, analiza) — autonoman ali prijavljuje Sonnetu
5. CC Code = executor — ne odlučuje, samo gradi
6. Ivan = enter tipka — odobrava smjer, mi izvršavamo

---

## ETIČKA GRANICA

"Rupe u zakonima" = legalne mogućnosti koje postoje u zakonu ali nisu dovoljno poznate.
Primjeri:
- PDV izuzeća za određene kategorije usluga
- Amortizacijski planovi koji su povoljniji za klijenta
- EU fondovi kojima klijent ne zna da ima pravo
- Rokovi plaćanja koji su zakonski ali korisni za likvidnost

NIŠ što je ilegalno ne ulazi u sustav.
Compliance watchdog ODMAH javlja ako nešto graniči.

---

## STATUS

Zadnje ažuriranje: 2026-03-23 (Sonnet)
Trenutno aktivna faza: FAZA 1
