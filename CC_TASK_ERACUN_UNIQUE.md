## PRVO PROCITAJ STATUS
```bash
cat /var/www/fina-connect/FENIX_STATUS.md
```

# CC Task — ERacun unique_together constraint

## Zadatak
Dodaj `unique_together = [('company', 'invoice_number')]` na ERacun model
i napravi migraciju.

## Korak 1 — Provjeri trenutni model
```
grep -n "invoice_number\|unique_together\|class Meta" /var/www/fina-connect/eracun/models.py
```

## Korak 2 — Dodaj constraint u Meta klasu
U `eracun/models.py`, klasa `ERacun`, unutar `class Meta:` dodaj:
```python
unique_together = [('company', 'invoice_number')]
```

## Korak 3 — Napravi migraciju
```bash
cd /var/www/fina-connect && venv/bin/python manage.py makemigrations eracun --name="eracun_unique_invoice_number"
venv/bin/python manage.py migrate eracun
```

## Korak 4 — Provjeri
```bash
venv/bin/python manage.py check 2>&1 | tail -2
```
Mora biti: 0 issues.

## Korak 5 — Javi Ivanu
- Broj nove migracije
- Output django check
- Potvrdu da je migrate prošao bez grešaka

## VAŽNO
Ne diraj ništa drugo u modelu. Samo Meta klasa, samo unique_together.
