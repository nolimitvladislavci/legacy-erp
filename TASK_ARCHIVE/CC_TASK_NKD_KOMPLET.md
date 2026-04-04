# CC_TASK_NKD_KOMPLET — NKD Klasifikacija 100%
# Agent: CC Code
# Prioritet: VISOK — blokira porezne izvještaje, fiskalizaciju F20, TAX Wizard
# Datum: 2026-03-25

---

## Što imamo (ne dirati)

- ✅ Model `companies.NKDCode` — savršen, hijerarhija definirana (section/division/group/class)
- ✅ `nkd_search` endpoint — `/companies/nkd-search/` radi, filtrira po q i level
- ✅ FK `companies_company.nkd_code_id` — postoji
- ✅ Admin konfiguriran

## Što je pokvareno / nedostaje

| Problem | Detalji |
|---------|---------|
| **74 kodova u bazi** | HR NKD 2007 ima 615 podrazreda. Imamo 12% |
| **Nema hijerarhije** | Svih 74 zapisa ima `parent_id=NULL` i `level="4"` — nije 'class' |
| **Nema sekcija A-U** | Nema ni jednog section/division/group zapisa |
| **42/90 firmi bez NKD** | Ne mogu se auto-assignirati jer nema kodova |
| **Ključni segmenti nedostaju** | Ribari, lovci, pčelari, KUD-ovi — vidi tablicu dolje |
| **Nema management commande** | Nema bulk import, nema auto-detect |

### Kritično nedostajući kodovi za naše tržišne segmente

| Kod | Naziv | Segment |
|-----|-------|---------|
| 01.49 | Uzgoj ostalih životinja (uključuje pčelarstvo) | Pčelari |
| 01.70 | Lov, hvatanje divljači | Lovci |
| 03.11 | Morski ribolov | Ribari |
| 03.12 | Slatkovodni ribolov | Ribari |
| 03.21 | Morska akvakultura | Ribari |
| 03.22 | Slatkovodna akvakultura | Ribari |
| 85.51 | Sportsko i rekreacijsko obrazovanje | ŠRD/KUD |
| 90.01 | Izvedbene umjetnosti | KUD |
| 90.02 | Pomoćne djelatnosti u izv. umjetnosti | KUD |
| 90.03 | Kreativne i umjetničke djelatnosti | KUD |
| 91.01 | Knjižnice i arhivi | Udruge |
| 94.91 | Djelatnosti vjerskih organizacija | Udruge |
| 94.99 | Ostale djelatnosti organizacija | Udruge (KUD, LD, ŠRD) |
| 96.09 | Ostale osobne usluge | Razno |

---

## ZADATAK — 4 koraka

### KORAK 1: Bulk import kompletnog NKD 2007 šifarnika

Kreiraj management command: `companies/management/commands/import_nkd.py`

Logika:
1. Dohvati NKD šifarnik — koristiti embeddani JSON (dolje) ili API
2. Upsert po `code` — ne briši postojeće
3. Postavi ispravne `level` vrijednosti koristeći `NKDCode.Level` choices
4. Postavi hijerarhiju `parent_id` (section → division → group → class)

**Minimalni set koji MORA biti u bazi (kritični segmenti):**

```python
# Dodaj kao fallback ako API ne radi — hardkodirani minimalni set
CRITICAL_NKD = [
    # Pčelari
    {"code": "A", "level": "section", "name_hr": "Poljoprivreda, šumarstvo i ribarstvo", "section": "A"},
    {"code": "01", "level": "division", "name_hr": "Biljna i stočarska proizvodnja", "section": "A"},
    {"code": "01.4", "level": "group", "name_hr": "Stočarstvo", "section": "A"},
    {"code": "01.49", "level": "class", "name_hr": "Uzgoj ostalih životinja", "section": "A"},
    # Lov
    {"code": "01.70", "level": "class", "name_hr": "Lov, hvatanje divljači i usluge s time povezane", "section": "A"},
    # Ribolov
    {"code": "03", "level": "division", "name_hr": "Ribolov i akvakultura", "section": "A"},
    {"code": "03.1", "level": "group", "name_hr": "Ribolov", "section": "A"},
    {"code": "03.11", "level": "class", "name_hr": "Morski ribolov", "section": "A"},
    {"code": "03.12", "level": "class", "name_hr": "Slatkovodni ribolov", "section": "A"},
    {"code": "03.2", "level": "group", "name_hr": "Akvakultura", "section": "A"},
    {"code": "03.21", "level": "class", "name_hr": "Morska akvakultura", "section": "A"},
    {"code": "03.22", "level": "class", "name_hr": "Slatkovodna akvakultura", "section": "A"},
    # KUD, udruge, sport
    {"code": "R", "level": "section", "name_hr": "Umjetnost, zabava i rekreacija", "section": "R"},
    {"code": "90", "level": "division", "name_hr": "Kreativne, umjetničke i zabavne djelatnosti", "section": "R"},
    {"code": "90.0", "level": "group", "name_hr": "Kreativne, umjetničke i zabavne djelatnosti", "section": "R"},
    {"code": "90.01", "level": "class", "name_hr": "Izvedbene umjetničke djelatnosti", "section": "R"},
    {"code": "90.02", "level": "class", "name_hr": "Pomoćne djelatnosti u izvođačkim umjetnostima", "section": "R"},
    {"code": "90.03", "level": "class", "name_hr": "Kreativne i umjetničke djelatnosti", "section": "R"},
    # Ostale udruge
    {"code": "S", "level": "section", "name_hr": "Ostale uslužne djelatnosti", "section": "S"},
    {"code": "94", "level": "division", "name_hr": "Djelatnosti članskih organizacija", "section": "S"},
    {"code": "94.9", "level": "group", "name_hr": "Djelatnosti ostalih članskih organizacija", "section": "S"},
    {"code": "94.91", "level": "class", "name_hr": "Djelatnosti vjerskih organizacija", "section": "S"},
    {"code": "94.99", "level": "class", "name_hr": "Djelatnosti ostalih članskih organizacija", "section": "S"},
]
```

Command:
```bash
venv/bin/python manage.py import_nkd --minimal   # samo kritični set
venv/bin/python manage.py import_nkd --full      # puni šifarnik (web scrape ili JSON)
```

---

### KORAK 2: Popravi postojećih 74 zapisa

Problem: svi imaju `level="4"` umjesto `level="class"`.

```python
# U management commandu ili kao standalone migracija:
from companies.models import NKDCode
NKDCode.objects.filter(level="4").update(level=NKDCode.Level.CLASS)
# Postavi section na temelju koda (npr. 10.71 → 'C', 47.11 → 'G', itd.)
```

Mapiranje section po kodu:
```python
SECTION_MAP = {
    "01": "A", "03": "A",
    "10": "C", "33": "C",
    "41": "F", "43": "F",
    "45": "G", "46": "G", "47": "G",
    "49": "H", "52": "H",
    "55": "I", "56": "I",
    "59": "J", "60": "J", "62": "J", "63": "J",
    "64": "K", "66": "K",
    "68": "L",
    "69": "M", "70": "M", "73": "M", "74": "M",
    "77": "N", "79": "N", "82": "N",
    "85": "P",
    "86": "Q",
    "90": "R",
    "94": "S", "95": "S", "96": "S",
}
```

---

### KORAK 3: Auto-assign NKD za 42 firme bez koda

Strategija — 3 izvora po prioritetu:

**A) OIB → FINA e-Regos API** (ako dostupno):
```python
# core/business_lookup.py već postoji — provjeri postoji li nkd_code u responsu
from core.business_lookup import lookup_company_by_oib
result = lookup_company_by_oib(company.oib)
if result.get('nkd_code'):
    nkd = NKDCode.objects.filter(code=result['nkd_code']).first()
    if nkd:
        company.nkd_code = nkd
        company.save(update_fields=['nkd_code'])
```

**B) business_type → NKD default mapping**:
```python
BUSINESS_TYPE_NKD_DEFAULT = {
    'udruga': '94.99',    # Ostale članskih organizacija
    'obrt': '96.09',      # Ostale osobne usluge — placeholder
    'doo': '70.22',       # Savjetovanje — placeholder
    'jdoo': '70.22',
    'opg': '01.50',       # Mješovita poljoprivreda
}
```

**C) Naziv firme → AI hint** (Haiku, 0.001 EUR/firma):
- Samo za firme gdje A i B nisu dali rezultat
- "Uvijek Friško" → 10.71 (Pekare)
- "KUD Dukat" → 90.01 (Izvedbene umjetnosti)
- "O.P.G. Kruljac" → 01.50 (Mješovita poljoprivreda)

Kreiraj management command: `companies/management/commands/assign_nkd.py`
```bash
venv/bin/python manage.py assign_nkd --dry-run   # prikaži što bi dodijelilo
venv/bin/python manage.py assign_nkd --apply     # primijeni
```

---

### KORAK 4: UI poboljšanje — NKD u registraciji

U registration wizard (step 2 ili company settings):
- Dodaj NKD autocomplete polje (endpoint već postoji: `/companies/nkd-search/`)
- Obavezno za: `business_type in ['doo', 'jdoo', 'obrt']`
- Neobavezno za: `udruga`, `opg`
- Placeholder tekst: "Upišite djelatnost ili NKD šifru..."
- Prikaži: `{code} — {name_hr}` u dropdownu

---

## Verifikacija — Definition of Done

```sql
-- Ovo mora biti TRUE nakon taska:
SELECT COUNT(*) FROM companies_nkdcode;
-- Mora biti > 200 (idealno 615)

SELECT COUNT(*) FROM companies_nkdcode WHERE level = 'class';
-- Mora biti > 500

SELECT COUNT(*) FROM companies_company WHERE nkd_code_id IS NULL;
-- Mora biti < 10 (samo debug/test firme)

SELECT code FROM companies_nkdcode WHERE code IN ('03.11','03.12','01.70','01.49','90.01','94.99');
-- Mora vratiti 6 redaka
```

```bash
# Sintaksa OK:
venv/bin/python manage.py check
# Nema grešaka, nema warningova vezanih za NKD
```

Commit: `feat: NKD šifarnik komplet — 615 kodova, auto-assign, ribari/lovci/KUD ready`

---

## Napomena za GEMINI

Nakon što CC Code napravi import_nkd, Gemini treba:
1. Verificirati da su NKD kodovi za pčelare/lovce/ribari usklađeni s HR NKD 2007 službenim dokumentom
2. Provjeriti koji NKD kodovi daju pravo na PDV oslobođenje
3. Provjeriti koji NKD kodovi su relevantni za EU fondove (CAP, LEADER)

Task: GEMINI_TASK_NKD_COMPLIANCE.md (piše Sonnet sljedeća sesija ako treba)
