# CC TASK: Warehouse W1 — nastavak (W1C + W1D + W1E)
# Agent: CC Code | Prioritet: 🟠 VISOK | Datum: 2026-03-26
# KONTEKST: W1A i W1B su DONE (e9a7cccc, e06d6937). Nastavljaš od W1C.

## OBAVEZNO PROČITAJ PRVO
```bash
cat FENIX_STATUS.md | head -30
git log --oneline -5
cat inventory/stock_input.py | head -30
cat inventory/models.py | grep -n "item_class\|fiscal_treatment\|ownership" | head -10
```

## SPRINT W1C — Kamera/AI unos (NIJE NAPRAVLJENO)
Kreiraj `inventory/camera_input.py`:
```python
# parse_camera_input(image_b64: str) -> dict
# Koristi Haiku za OCR/analiza slike
# Izvlači: naziv, qty, price, barcode ako postoji
# Vraća: {'name': str, 'qty': float, 'price': float, 'barcode': str|None, 'confidence': float}
# Math check: ako price*qty > 50000 EUR → odbaci (sanity limit)
```
URL: POST /hr/inventory/camera-input/ (ajax, JSON)
Test: test_camera_input_haiku() + test_math_sanity_limit()
Commit: `feat(W1C): camera/AI inventory input via Haiku`

## SPRINT W1D — Price engine dopuna (DJELOMIČNO)
U `inventory/models.py` dopuni `get_price_for_buyer()`:
- B2B: retail_price * (1 - discount_percent/100)
- B2C: retail_price
- Wholesale: wholesale_price if qty >= wholesale_min_qty
- Provjeri `wholesale_price` polje postoji — ako ne, dodaj i migriraj
Test: test_price_engine_b2b_b2c_wholesale()
Commit: `feat(W1D): price engine — B2B/B2C/wholesale switching`

## SPRINT W1E — Amortizacija DRAFT (NIJE NAPRAVLJENO)
Kreiraj `inventory/depreciation.py`:
```python
class DepreciationCalculator:
    # calculate_annual(item) -> DepreciationDraft (NE SPREMA u bazu, samo vraća dict)
    # Metode: LINEAR_5Y, LINEAR_10Y, DECLINING_BALANCE
    # Za assets (item_class='asset') s purchase_price i purchase_date
```
NAPOMENA: DepreciationDraft model ide u W4 (ne kreiraj ga sad).
Celery task `check_depreciation_reminders` — svaki 1. u mjesecu 06:00
→ Nalazi assete starije od 1 god, šalje WhatsApp Mariji: "Nacrt amortizacije spreman"
Commit: `feat(W1E): depreciation calculator draft + Celery reminder`

## KRAJ
git commit svaki sprint zasebno.
Ažuriraj FENIX_STATUS.md — dodaj W1C/W1D/W1E u DONE.
