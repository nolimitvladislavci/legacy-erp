# CC_TASK: DRON #1 — Synesis Veto (Računovodstvena Mina)
# Datum: 02.04.2026 | Prioritet: 🔴 NULTI — Sve ostalo staje
# Odgovorni: CC Code
# Kontekst: Sonnet dijagnoza — synesis_compare.py živi output

---

## PRIJETNJA (ne ignorirati)

Ako LC izbaci fakturu ili XML export koji knjigovođin Synesis ne može progutati
jednim klikom → knjigovođa zove klijenta → "Miči mi ovaj program" → otkaz isti dan.
Nisu problem unutarnji brojevi. Problem je bookkeeper perception of reliability.

## DIJAGNOZA (iz synesis_compare.py — 02.04.2026)

```
OK (≤0.02€):   7  (0.9%)   ← KATASTROFA
Razlika >1€: 756            ← UZROK: mapping + iznos tip mismatch
Nema u LC:   238            ← Synesis ID "01","0001" → LC traži "SYN-IRA-01"
Extra u LC: 3182            ← Uredu, LC ima više podataka
Bez temeljnice: 7344        ← Čeka Mariju (zasebni task)
```

## UZROCI (redoslijed važnosti)

### Uzrok A — ID mapping propada (238 "Nema u LC")
Synesis radi `DOCUMENT_ID` = "01", "0002", "0000"
LC generira number = "SYN-IRA-01", "SYN-IRA-0002"
synesis_compare.py traži exact match → 0 hitova

**Fix A:** U synesis_compare.py, u lc_invs lookup dodaj:
```python
# Probaj i bez prefiksa — direct numeric match
bare_id = did.lstrip('0') or '0'  # "0001" → "1"
padded_variants = [did, did.lstrip('0'), did.zfill(4), did.zfill(6)]
for variant in padded_variants:
    lc = lc_invs.get(variant)
    if lc: break
# Pokušaj i sa SYN- prefiksom na sve varijante
if not lc:
    for variant in padded_variants:
        lc = lc_invs.get(f"SYN-IRA-{variant}") or lc_invs.get(f"SYN-URA-{variant}")
        if lc: break
```

### Uzrok B — DOCUMENT_AMMOUNT neto vs bruto (756 razlika)
Synesis DOCUMENT_AMMOUNT = **BRUTO** (s PDV-om)
LC `total` field = **NETO** (bez PDV-a) — confirmed iz modela

synesis_compare.py već ima kandidate za PDV faktore (1.25, 1.13, 1.05)
ALI: tolerancija je ±0.02 EUR, dok zaokruživanje na 2 decimale daje ±0.01

**Fix B:** Provjeri u synesis_compare.py:
```python
# Trenutno:
candidates = [
    abs(base['syn_amt'] - amt),
    abs(base['syn_amt'] - lc_bruto),  # amt + tax_amount
    ...
]
# Dodaj: round() na oba — Synesis i LC iznosi su zaokruženi na 2 decimale
def rounded_diff(a, b):
    return abs(round(a, 2) - round(b, 2))

candidates = [
    rounded_diff(base['syn_amt'], amt),
    rounded_diff(base['syn_amt'], lc_bruto),
    rounded_diff(base['syn_amt'], amt * Decimal('1.25')),
    rounded_diff(base['syn_amt'], amt * Decimal('1.13')),
    rounded_diff(base['syn_amt'], amt * Decimal('1.05')),
]
```

### Uzrok C — Datum mismatch kao sekundarni filtar
Ako synesis_compare.py filtrira po datumu, stari Synesis formati ('%m/%d/%y') 
mogu parseati godinu kao 2020 umjesto 1920 → kriva faktura se ne nađe.

**Fix C:** Provjeri parse_date() u synesis_compare.py — dodaj 2000+ fallback:
```python
def parse_date(s):
    s = clean(s)
    if not s: return ''
    for fmt in ('%m/%d/%y %H:%M:%S', '%m/%d/%Y %H:%M:%S', '%d.%m.%Y', '%Y-%m-%d'):
        try:
            d = datetime.strptime(s, fmt)
            # Fix dvocifrene godine: 25 → 2025, ne 1925
            if d.year < 2000: d = d.replace(year=d.year + 2000)
            return d.strftime('%Y-%m-%d')
        except: pass
    return s[:10]
```

---

## PRAVI BOOKKEEPER TEST (Dron #1 stvarni cilj)

Cilj nije samo synesis_compare na 95%. Cilj je da knjigovođa ne dobije dupli posao.

### Test 1 — PDF faktura (vizualni)
Stvori testnu fakturu u LC → preuzmi PDF → usporedi s Synesis PDF printoutom.
Moraju biti isti: broj fakture, OIB, IBAN, PDV razdvajanje, ukupni iznos.

### Test 2 — UBL 2.1 XML export
LC već generira eRačun XML (einvoice app). Pošalji jedan na Mariju.
Marija ga uvozi u Synesis. Ako Synesis kaže "OK" → Dron #1 neutraliziran.

Provjeri UBL export:
```bash
cd /var/www/fina-connect
venv/bin/python manage.py shell -c "
from einvoice.models import *
inv = EInvoice.objects.filter(status='issued').first()
if inv: print(inv.xml_content[:500] if hasattr(inv,'xml_content') else 'nema xml_content field')
"
```

### Test 3 — Konto/PDV razdvajanje
Ključno za knjigovođu: LC mora eksportirati razdvojen PDV po stopama (5%, 13%, 25%)
u formatu koji Synesis razumije (konto 2400, 2401, 2402 ili ekvivalent).

```bash
venv/bin/python manage.py shell -c "
from invoicing.models import Invoice
inv = Invoice.objects.filter(status='issued').first()
if inv:
    print('Neto:', inv.total)
    print('PDV:', inv.tax_amount)
    print('Bruto:', float(inv.total or 0) + float(inv.tax_amount or 0))
    print('PDV stopa:', inv.tax_rate if hasattr(inv,'tax_rate') else 'provjeri model')
"
```

---

## DELIVERABLE

1. synesis_compare.py s Fix A + Fix B + Fix C → pokreni → cilj OK% > 70% (korak 1)
2. Mariji poslati 1 testnu UBL XML fakturu za Synesis import test
3. Rezultat OK% i Marija feedback → dokumentiraj u FENIX_STATUS.md

Rok: **07.04.2026** (CC Code sprint dan 5)

