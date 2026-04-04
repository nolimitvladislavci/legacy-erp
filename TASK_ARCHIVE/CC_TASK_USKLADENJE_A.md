# CC_TASK_USKLADENJE_A — Synesis usklađenje + testovi
**Dodjeljeno:** CC Code Instance A
**Ne dira:** delivery/, gastro_menu/, infrastruktura (to je B)
**Deadline:** 10.04.2026 (Marija blagoslov 11.04.)
**Status:** TODO

---

## KONTEKST — što skripta pokazuje

Pokreni PRVO i analiziraj output:
```bash
cd /var/www/fina-connect
venv/bin/python synesis_compare.py --summary
venv/bin/python synesis_compare.py --csv
```

**Trenutno stanje (01.04.2026):**
```
Uspoređeno: 765 faktura
✓ OK:         67   (8.8%)
⚠ Upozorenje:  2
✗ Razlika:   696   (91% — KRITIČNO)
✗ Nema u LC: 245   (Synesis ima, LC nema)
? Extra u LC: 2482  (LC ima, Synesis nema — vjerojatno drugi Synesis moduli)

Totali:
  IRA: Synesis 231k€ vs LC 261k€ → diff -30k€
  URA: Synesis 122k€ vs LC 170k€ → diff -48k€
  Temeljnice: 0/7344 kreirane
```

**Zašto toliko razlika:**
1. XINVOICESB (357 redaka Journal.mdb) = izlazni računi Synesis
   LC ima prefix SYN-IRA-xxx — samo ovi se uspoređuju
2. 7344 LC faktura = ukupno uvezeno (IRA + URA + Prijenosu salda + ostalo)
3. "Extra u LC" = fakture iz Storage.mdb (ne Journal.mdb) — drugačiji mapping
4. Razlika u iznosima = vjerojatno PDV uključen vs isključen u različitim izvorima

---

## ZADATAK A1 — Dijagnoza razlika

### Korak 1 — razumjeti što je "XINVOICESB" u Synesisu:
```bash
# Pogledaj Storage.mdb — ima li INVOICES tamo
mdb-tables '/var/www/fina-connect/Korpa/KORPAŠ d.o.o. 2025/Storage.mdb' | tr ' ' '\n' | grep -iE "INVOICE|RACUN|IRA|URA"

# Exportiraj INVOICES iz Storage ako postoji
mdb-export '/var/www/fina-connect/Korpa/KORPAŠ d.o.o. 2025/Storage.mdb' INVOICES 2>/dev/null | head -5
```

### Korak 2 — provjeri što su "Extra u LC" (2482 faktura):
```python
cd /var/www/fina-connect && venv/bin/python manage.py shell -c "
from invoicing.models import Invoice
from companies.models import Company
konjik = Company.objects.get(oib='37590751921')

# Koji prefiksi postoje u LC?
import re
from collections import Counter
prefixes = Counter()
for inv in Invoice.objects.filter(company=konjik):
    m = re.match(r'^([A-Z]+-[A-Z]+-|[0-9]+)', inv.number)
    if m: prefixes[m.group(1)] += 1
    else: prefixes['OTHER'] += 1
for k,v in prefixes.most_common():
    print(f'{k}: {v}')
"
```

### Korak 3 — provjeri import_synesis_to_erp.py:
```bash
head -100 /var/www/fina-connect/import_synesis_to_erp.py
# Razumij kako se vrši mapping number-a pri importu
# Je li SYN-IRA prefix dodijeljen XINVOICESB ili nečem drugom?
```

### Korak 4 — ažuriraj synesis_compare.py ako je mapping pogrešan:
U `DOC_MAP` u skripti provjeri odgovaraju li prefiksi stvarnim brojevima u bazi.
Ako je mapping drugačiji — ispravi ga i pokreni ponovo.

---

## ZADATAK A2 — Popravljanje razlika u iznosima

Razlika IRA: -30.093 EUR između Synesis i LC.
Uzrok je vjerojatno jedan od:
a) DOCUMENT_AMMOUNT u Synesisu = neto (bez PDV), LC ima bruto (s PDV)
b) Tečajne razlike (EUR vs HRK konverzija)
c) Pogrešan mapping kod importa

### Provjeri:
```python
# Uzmi 5 faktura s razlikom i usporedi ručno
venv/bin/python manage.py shell -c "
from invoicing.models import Invoice
from companies.models import Company
konjik = Company.objects.get(oib='37590751921')

# Uzmi fakturu iz LC koja ima razliku
inv = Invoice.objects.filter(company=konjik, number__startswith='SYN-IRA-').first()
print(f'Broj: {inv.number}')
print(f'Subtotal (neto): {inv.subtotal}')
print(f'Tax: {inv.tax_amount}')
print(f'Total (bruto): {inv.total}')
print(f'Partner: {inv.client_name}')
print(f'Datum: {inv.date_issued}')
"

# Nađi isti zapis u Synesisu po DOCUMENT_ID
# DOCUMENT_ID iz broja npr. SYN-IRA-52 → DOCUMENT_ID=52 u XINVOICESB
```

### Nakon dijagnoze:
- Ako je uzrok PDV → ažuriraj usporedbu u `synesis_compare.py` da koristi `subtotal` umjesto `total`
- Ako je uzrok mapping → popravi import u `import_synesis_to_erp.py` i re-importiraj

---

## ZADATAK A3 — Kreiranje JournalEntry temeljnica

**Problem:** 0/7344 PAID faktura ima temeljnicu u `konto.JournalEntry`.

### Provjeri model:
```bash
grep -n "class JournalEntry\|class JournalLine" /var/www/fina-connect/konto/models.py | head -5
grep -n "source_invoice\|source_type\|entry_number" /var/www/fina-connect/konto/models.py | head -10
```

### Postoji li auto-kreiranje temeljnica?
```bash
grep -rn "JournalEntry.objects.create\|create_journal\|auto_journal\|post_journal" \
  /var/www/fina-connect/invoicing/ \
  /var/www/fina-connect/konto/ 2>/dev/null | head -20
```

### Ako ne postoji — kreiraj management command:
```
konto/management/commands/create_journal_entries.py
```

Logika:
```python
# Za svaku PAID Invoice bez JournalEntry:
# 1. Kreiraj JournalEntry (entry_number, date, source_invoice, is_posted=True)
# 2. Kreiraj JournalLine zapise (debit/credit po računovodstvenom planu)
#    - IRA faktura: D 1200 (Potraživanja) / C 7500 (Prihodi) + C 2400 (PDV)
#    - URA faktura: D 4000 (Troškovi) + D 2400 (PDV prihod) / C 2200 (Obveze)

# Pokreni dry-run:
venv/bin/python manage.py create_journal_entries --dry-run --company=37590751921

# Pokreni pravo:
venv/bin/python manage.py create_journal_entries --company=37590751921
```

**NAPOMENA:** Ne kreirati temeljnice za Synesis podatke bez Marijinog odobrenja.
Ovaj task = priprema command-a, ne pokretanje.

---

## ZADATAK A4 — Testni suite za usklađenje

Kreirati `tests/test_synesis_compare.py`:

```python
class TestSynesisCompare(TestCase):
    """Automatski testovi koji se pokreću prije svake produkcije."""

    def test_invoice_count_matches(self):
        """Broj IRA/URA faktura u LC mora biti >= broju u Synesisu."""

    def test_ira_total_within_tolerance(self):
        """Ukupni IRA iznos smije odstupati max 0.5% od Synesis iznosa."""

    def test_all_paid_invoices_have_journal(self):
        """Svaka PAID faktura mora imati JournalEntry."""

    def test_no_duplicate_synesis_import(self):
        """Nema duplikata — isti synesis_id ne može biti na 2 fakture."""

    def test_partner_oib_consistency(self):
        """Partner OIB u LC mora matchirati Partner OIB u Synesisu."""
```

Pokretanje:
```bash
venv/bin/python manage.py test tests.test_synesis_compare -v 2
```

---

## ZADATAK A5 — GO/NO-GO checklistа za Mariju

Kreirati `/var/www/fina-connect/MARIJA_BLAGOSLOV.md`:

```markdown
# Marija Brtan — GO/NO-GO checklistа
# Datum pregleda: ___________

## Automatski testovi (pokreni: venv/bin/python synesis_compare.py --summary)
- [ ] OK% >= 95% (razlike ≤ 0.02€)
- [ ] Razlike >1€ = 0
- [ ] Nema u LC = 0
- [ ] IRA total diff < 100€
- [ ] URA total diff < 100€

## Ručna provjera (Marija)
- [ ] 10 random IRA faktura provjereno vizualno (broj, partner, iznos, datum)
- [ ] 10 random URA faktura provjereno vizualno
- [ ] 3 stornirane fakture ispravno evidentirane
- [ ] PDV prijava iznosi odgovaraju Synesisu

## Temeljnice
- [ ] JournalEntry kreiran za sve PAID fakture
- [ ] Konto plan 1200/7500/2400/4000/2200 ispravan

## POTPIS: ___________________  DATUM: ___________
## ODLUKA: [ ] GO  [ ] NO-GO — razlog: __________________
```

---

## PROVJERA NA KRAJU:
```bash
# Pokreni puni compare
venv/bin/python synesis_compare.py --csv

# Provjeri testove
venv/bin/python manage.py test tests.test_synesis_compare -v 2

# Provjeri OK% >= 95%
# Ako jest → kreiraj MARIJA_BLAGOSLOV.md popunjen s automatskim rezultatima
```

## GIT:
```bash
git add synesis_compare.py tests/test_synesis_compare.py konto/management/
git commit -m "feat(synesis): compare skripta, JournalEntry command, GO/NO-GO checklist"
git log --oneline -3
```
Update FENIX_STATUS.md — sve DONE stavke.
