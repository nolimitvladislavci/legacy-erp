# CC_TASK: Partner buyer_type klasifikacija — batch reklasifikacija
## Agent: Claude Code | Prioritet: P1-VISOK | Datum: 2026-03-23

## Kontekst
- `Partner.buyer_type` polje postoji s 7 choices
- Trenutno: ~19.237 partnera ima `buyer_type='b2c'` (default)
- Invoice routing ovisi o buyer_type (NN 89/25 — eRačun zakon)
- Netočan buyer_type = kriva vrsta računa = zakonski problem

## Zadatak

### 1. Čitaj modele PRVO
```bash
grep -n "buyer_type\|is_budget_user\|oib\|vat_id" partners/models.py | head -30
```

### 2. Klasifikacijska logika (management command)
Kreiraj `partners/management/commands/classify_buyer_types.py`

Pravila klasifikacije (redoslijed):
```
1. oib počinje s '1' ili '2' + duljina = 11 → b2b (fizička osoba poduzetnik)
   NAPOMENA: ovo nije pouzdan signal — samo hint
2. vat_id počinje s 'HR' → b2b_vat (PDV obveznik)
3. vat_id počinje s 'DE'/'AT'/'SI'/'IT' itd. → b2b_eu (EU firma)
4. oib = NULL i vat_id = NULL i email sadržava '@' → b2c (građanin)
5. name sadržava 'grad'/'općin'/'ministarst'/'škol'/'bolnic'/'dom'
   (case-insensitive) → b2g (proračunski korisnik)
6. name sadržava 'udruga'/'klub'/'kud'/'udruge' → b2c_nonprofit
7. Sve ostalo što ima OIB → b2b (default za HR pravne subjekte)
```

Komanda:
```bash
python manage.py classify_buyer_types --dry-run  # Samo prikaži, ne mijenjaj
python manage.py classify_buyer_types --commit    # Primijeni promjene
python manage.py classify_buyer_types --company-id 123 --commit  # Samo za jednu firmu
```

### 3. Output dry-runa mora pokazati:
```
Klasifikacija partnera:
  b2b:          X (Y%)
  b2b_vat:      X (Y%)
  b2b_eu:       X (Y%)
  b2c:          X (Y%)
  b2g:          X (Y%)
  b2c_nonprofit: X (Y%)

Top 10 promjena:
  "Grad Zagreb" → b2g (bio: b2c)
  "Müller GmbH" → b2b_eu (bio: b2c)
  ...

Promjena bi utjecala na invoice routing za X partnera.
```

### 4. Celery task za background processing
```python
@shared_task(name='partners.classify_buyer_types_batch')
def classify_buyer_types_batch(company_id=None):
    # Batch klasifikacija za jednu ili sve firme
    # Logira promjene u SystemAuditLog
```

## Provjere
```bash
python manage.py classify_buyer_types --dry-run 2>&1 | tail -20
```
Mora pokazati razumnu distribuciju (ne 100% b2b ili 100% b2c).

## Commit poruka
`Partners: buyer_type batch klasifikacija — management command + Celery task`
