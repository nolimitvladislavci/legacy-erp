# GEMINI TASK — PLATFORMA AUDIT + PLAN 10/10
> Agent: Gemini | Tip: Duboka analiza + strateški plan
> Pokretač: Sonnet | Datum: 2026-04-16
> max_steps: 40

---

## CILJ ZADATKA

Napravi **inženjerski audit cijele LIMIT Connect platforme** i generiraj
konkretni plan za dostizanje 10/10 po svim dimenzijama.

Ne želimo:  "moglo bi biti bolje" ili generičke preporuke
Želimo:     Konkretne datoteke, konkretne linije, konkretan redoslijed

---

## FAZA 1 — INVENTURA STANJA (čitaj redom)

### 1.1 Pročitaj ove datoteke:
```
FENIX_STATUS.md
CC_TASK_STOLARIJA_VOICE_V2.md
PLAN_BOOKKEEPER_WORKSPACE.md
PLAN_SLIKOVNICE.md
```

### 1.2 Za svaki CORE modul pročitaj models.py + views.py:
Moduli po prioritetu:
1. pos/         — POS blagajna (30k LoC, 310 testova)
2. invoicing/   — Računi/ponude (25k LoC, 351 testova)
3. documents/   — Arhiva (16k LoC, 258 testova)
4. konto/       — Kontiranje (14k LoC, 43 testova)
5. worktime/    — Radni sati (13k LoC, 63 testova)
6. stolarija/   — Stolarija modul (9k LoC, 0 testova!)
7. udruge/      — Udruge (15k LoC, 112 testova)
8. delivery/    — Dostava (8k LoC, 62 testova)
9. inventory/   — Skladište (6k LoC, 10 testova)
10. production/ — Proizvodnja (6k LoC, 53 testova)
11. appointments/ — Termini (6k LoC, 67 testova)
12. synesis/    — Legacy import (8k LoC, 15 testova)

Za svaki modul bilježi:
- Funkcionalnost: što radi, što nedostaje
- Kod kvaliteta: N+1, missing indeksi, testovi
- UI/UX razina: template stanje, mobile, responsivnost
- AI integracija: što postoji, što nedostaje
- Ocjena 1-10 po svakoj dimenziji

### 1.3 Provjeri u bazi produkcijsko stanje:
```python
# Pokreni za svaki modul:
from django.db import connection
# Broj zapisa po tablici
cursor = connection.cursor()
cursor.execute("""
    SELECT schemaname, tablename,
           pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
           (xpath('/row/cnt/text()', query_to_xml(format('SELECT COUNT(*) AS cnt FROM %I.%I', schemaname, tablename), false, true, '')))[1]::text::int AS row_count
    FROM pg_tables
    WHERE schemaname = 'public'
    ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
    LIMIT 50;
""")
```

---

## FAZA 2 — OCJENE PO MATRICI

Za svaki modul generiraj tablicu:

```
MODUL: pos
┌─────────────────────────────┬──────┬────────────────────────────────────┐
│ Dimenzija                   │ Razina│ Nedostaje za 10/10                 │
├─────────────────────────────┼──────┼────────────────────────────────────┤
│ Funkcionalnost              │  8/10│ Offline mode, multi-terminal sync  │
│ Inženjerski kod             │  7/10│ 34 N+1 querija, 8 missing indeksa  │
│ Testovi                     │  9/10│ 310 testova, coverage ~78%         │
│ UI/UX                       │  6/10│ Mobile-first nije završen          │
│ AI integracija              │  7/10│ Trojstvo radi, nema voice commands │
│ Sigurnost                   │  8/10│ Rate limiting OK, audit log nepot. │
│ Dokumentacija               │  4/10│ Nema inline docs                   │
│ UKUPNO                      │  7/10│                                    │
└─────────────────────────────┴──────┴────────────────────────────────────┘
```

Posebno markiraj:
- 🔴 KRITIČNO (ispod 5/10) — blokira klijente
- 🟡 POTREBNO (5-7/10) — utječe na zadovoljstvo
- 🟢 DOBRO (8-10/10) — može čekati

---

## FAZA 3 — ANALIZA OTVORENIH STAVKI

### Što je PLANIRANO ali nije IZVRŠENO:

```
ARHIVA (Operacija HR-DE):
- ARHIVA-3: Network Disk (rclone OneDrive)    → 0%
- ARHIVA-4: WhatsApp Share Link               → 0%
- ARHIVA-5: WhatsApp-IN (inbound)             → 0%
- ARHIVA-6: DE Steuerberater paket            → 0%
- ARHIVA-7: DATEV Export                      → 0%
- ARHIVA-8: Porezna Prijava DE                → 0%
- ARHIVA-9: Synesis Retroaktiv Import         → 0%
- ARHIVA-10: Billing                          → 0%

KORAK 11 Beta (Konjik):
- Marija kaže "ovo radi" → 10% gotovo
- Blokeri: stolarija bugovi, arhiva

STOLARIJA (Zdenko pilot):
- Voice V2 continuous                         → 0%
- GPS na mjerenju                             → 0%
- OCR šalabaktera                             → 0%
- BUG: ponuda se ne otvara                    → 0%
- BUG: stranica desno                         → 0%

MEMIO EKOSISTEM:
- memio.pet booking                           → 0%
- memio.world MVP (views+templates)           → 0%
- PLAY.EU Slikovnice Glava 1 backend          → 0% (plan postoji)
- POS free tier (Marija Čačić)               → 0%

DeepSeek Patrol nalazi:
- 221 missing DB indeksa                      → 0%
- Top 20 N+1 querija                          → 0%
- agent_gateway bez @login_required           → 0%
```

Za svaku stavku:
1. Procijeni kompleksnost (S/M/L/XL)
2. Procijeni trajanje (sati/dani)
3. Prijedlog: CC Code / Gemini / Sonnet / Ivan

---

## FAZA 4 — PLAN 10/10

### Sprint struktura (6 sprintova × 2 tjedna):

**SPRINT 1 — Baza kvalitete (ODMAH)**
Cilj: Kod koji ne pada, performanse koje se osjete

Zadaci za CC Code:
1. Svi missing DB indeksi → 1 migracija (M, 4h)
2. Top 20 N+1 querija → select_related (M, 6h)
3. agent_gateway @login_required (S, 30min)
4. Stolarija bugovi (M, 4h)
5. Stolarija testovi — 0 → 40+ (L, 8h)

Procijenjeni efekt: P95 latency -40%, 0 sigurnosnih rupa

**SPRINT 2 — Arhiva HR-DE (PRIORITET)**
Cilj: Marija kaže "ovo radi"

Zadaci:
1. ARHIVA-3 Network Disk/OneDrive (L, 2 dana)
2. ARHIVA-4 WhatsApp Share Link (M, 1 dan)
3. ARHIVA-5 WhatsApp-IN inbound (L, 2 dana)
4. Korak 11 Beta → Marija testira (S, pilot)

**SPRINT 3 — AI integracija (DIFERENCIATOR)**
Cilj: Svaki modul ima AI assist

Zadaci:
1. Stolarija Voice V2 continuous (L, 2 dana)
2. Stolarija OCR šalabaktera (M, 1 dan)
3. konto AI auto-kontiranje (L, 2 dana)
4. invoicing AI generator ponuda glasom (M, 1 dan)

**SPRINT 4 — Mobile-first UI (ZDENKO + TERENCI)**
Cilj: 10/10 UX na telefonu

Zadaci:
1. POS mobile PWA offline mode (XL, 3 dana)
2. Stolarija GPS + AR mjerenje priprema (L, 2 dana)
3. Worktime clock-in/out GPS (M, 1 dan)
4. Globalni dark/light theme audit (S, 4h)

**SPRINT 5 — DE Tržište**
Cilj: Viskovic Bau + Dragan pilot

Zadaci:
1. ARHIVA-6 DE Steuerberater (L, 2 dana)
2. ARHIVA-7 DATEV Export (XL, 3 dana)
3. DE fiscalization flow (L, 2 dana)

**SPRINT 6 — Rast i monetizacija**
Cilj: Korak 12 EU Kampanja

Zadaci:
1. ARHIVA-10 Billing (XL, 3 dana)
2. POS free tier (M, 1 dan)
3. PLAY.EU Slikovnice komplet (XL, 3 dana)
4. Korak 12 — EU prijava dokumenti (XL, 5 dana)

---

## FAZA 5 — OUTPUT FORMAT

Generiraj datoteku: `AUDIT_10_10_REZULTATI.md`

Struktura:
```markdown
# LIMIT CONNECT — AUDIT 10/10
> Datum: {datum}
> Agent: Gemini
> Commit: {git HEAD}

## EXECUTIVE SUMMARY
[3-4 rečenice — gdje smo, kamo idemo]

## OCJENE PO MODULIMA
[Tablica za svaki modul]

## KRITIČNI BLOKERI (moraju se riješiti prije beta)
[Lista s prioritetima]

## OTVORENE STAVKE — kompletna lista
[Sve ⏳ stavke iz FENIX_STATUS + analiza]

## PLAN 10/10 — 6 Sprintova
[Sprint 1-6 s konkretnim zadacima, trajectima, agentima]

## DEEPSEEK PATROL — TOP 10 NALAZA ZA ODMAH
[Konkretni fajlovi i linije]
```

---

## TEHNIČKI DETALJI ZA GEMINI

Server: 37.27.248.86
Projekt: /var/www/fina-connect
Baza: PostgreSQL, user=viskovic_user, db=fina_erp
Git: master branch

Alati koji su ti dostupni:
- read_file → čitaj bilo koji fajl
- exec_command → pokreni Python/shell
- query_db → SELECT upiti na bazu
- write_file → zapiši rezultate

Počni s FAZA 1, zatim FAZA 2, zatim generiraj output.
Ne preskači faze — svaka ovisi o prethodnoj.
Inženjeriraj, ne spekuliraj.
