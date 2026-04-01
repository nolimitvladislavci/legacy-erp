# CC_TASK_USKLADENJE_A — Synesis Mapping Fix

**Datum:** 2026-04-01/02
**Status:** COMPLETED
**Prioritet:** P0 — utječe na bilance i RDG svih 93 firmi

---

## 1. Dijagnoza

### Problem
Synesis `full_import.py` koristio je **pojednostavljenu klasa→tip mapu** koja ne pokriva:
- **Klasu 8** (Rezultat poslovanja) — mapirana kao `income` umjesto `equity/expense`
- **Klasu 7** — mapirana kao `income` umjesto `revenue`
- **Klasu 9** — dugoročne obveze (94x-96x) mapirane kao `equity` umjesto `liability`
- **DE SKR03** — potpuno ignoriran (3 firme s njemačkim kontnim planom)

### Utjecaj
- **2,514 pogrešno klasificiranih konto računa** (od 5,170 ukupno = 48.6%)
- Bilance su bile D=P (ispravno), ali **RDG i klasifikacija u izvještajima bila pogrešna**
- Klasa 800 "Dobit" prikazivana kao rashod umjesto rezultata
- Klasa 7 "Prihodi" prikazivana kao "income" umjesto "revenue"

### Firme zahvaćene
- 90 HR firmi (2,420 konto računa ispravljeno)
- 3 DE firmi (94 konto računa ispravljeno)

---

## 2. Fix

### A) Management command `fix_account_types`
**Lokacija:** `konto/management/commands/fix_account_types.py`

Podržava:
- HR RRF standard (klase 0-9 s refiniranom klasom 8 i 9)
- DE SKR03 standard (klase 1, 2, 8 s mixed tipovima)
- `--dry-run` za provjeru prije primjene
- `--company` filter za ciljanu firmu
- Idempotentnost — ponovljeno pokretanje ne mijenja ništa

### B) Import skripta fix
**Lokacija:** `synesis/full_import.py` — linija ~245
- `income` → `revenue` za klasu 7
- `income` → `equity` za klasu 8

### C) Primjena
```bash
# Dry run provjera
python manage.py fix_account_types --dry-run

# Primjena
python manage.py fix_account_types

# Rezultat: 2,514 ispravljeno (HR:2,420, DE:94)
```

---

## 3. Verifikacija

### Testni suite
**Lokacija:** `konto/tests/test_uskladenje_a.py`

| Test | Opis | Status |
|------|------|--------|
| test_class0_is_asset | Dugotrajna imovina | PASS |
| test_class1_is_asset | Kratkotrajna imovina | PASS |
| test_class2_is_liability | Kratkoročne obveze | PASS |
| test_class3_is_asset_not_equity | Zalihe = asset, NE kapital | PASS |
| test_class4_is_expense | Troškovi | PASS |
| test_class7_is_revenue | Prihodi = REVENUE | PASS |
| test_class8_dobit_is_equity | 800 Dobit = equity | PASS |
| test_class8_porez_is_expense | 803 Porez = expense | PASS |
| test_class9_kapital_is_equity | 900 Kapital = equity | PASS |
| test_class9_dugorocne_obveze | 95x = liability | PASS |
| test_de_class1_17xx_liability | DE: 17xx = liability | PASS |
| test_de_class2_20xx_equity | DE: 20xx = equity | PASS |
| test_de_class4_revenue | DE: 4xxx = revenue | PASS |
| test_balanced_entry | D=P provjera | PASS |
| test_no_negative_amounts | Nema negativnih | PASS |
| test_second_run_no_changes | Idempotentnost | PASS |
| test_unique_entry_numbers | Nema duplikata | PASS |

### Bilanca D=P provjera (post-fix)
Sve firme balansirane (diff < 1 EUR).

---

## 4. Commitovi

| Commit | Opis |
|--------|------|
| fix_account_types.py | Management command za HR+DE mapping |
| synesis/full_import.py | Ispravljen type_map za buduće importe |
| konto/tests/test_uskladenje_a.py | 17 testova za verifikaciju |

---

## 5. Potpis

Za potpis vidjeti: **MARIJA_BLAGOSLOV.md**
