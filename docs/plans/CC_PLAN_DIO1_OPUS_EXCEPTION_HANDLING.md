# DIO 1: EXCEPTION HANDLING REFACTORING (OPUS)
> Najzahtjevniji dio — zahtijeva semantičko razumijevanje svake try/except grane

## CILJ
Reducirati 3,598 broad `except Exception`/`except:` na < 200 (samo tamo gdje je zaista opravdano).
Svaki preostali broad catch mora imati `logger.exception()` i komentar zašto.

## SCOPE — SAMO OVI APPOVI (sortirano po broju broad catcheva):
```
core/                  784 broad catches (+ 111 u management/commands)
pos/                   246 + 46 u testovima
worktime/              166
invoicing/             87 + 31 u services
accounts/              86
konto/                 73
documents/             71
appointments/          63
limit_connect_ai/      62
ai_assistant/          53
partners/              52
synesis/               48
borg_ops/              47
registration/          45
assessment/            41
companies/             38
udruge/                33
smart_import/          30
eracun/                29 u services
memio_pet/             27
inventory/             23
simulation/            86
tmp/                   60
finance/               19
```

## PRAVILA REFACTORINGA

### 1. Identificiraj TIP operacije u try bloku:
```python
# DB operacija → except Model.DoesNotExist, IntegrityError, DatabaseError
# File I/O     → except FileNotFoundError, PermissionError, IOError
# HTTP/API     → except requests.RequestException, ConnectionError, Timeout
# JSON parse   → except json.JSONDecodeError, ValueError
# Validacija   → except ValidationError, ValueError
# Celery       → except celery.exceptions.*, kombu.exceptions.*
# Import       → except ImportError
# Math         → except ZeroDivisionError, decimal.InvalidOperation
# Crypto       → except cryptography.fernet.InvalidToken
```

### 2. Broad catch SMIJE ostati SAMO ako:
- Middleware/signal handler koji NE SMIJE crashati request (GracefulErrorMiddleware OK)
- Celery task top-level (ali MORA logirati: `logger.exception("Task X failed")`)
- Management command top-level
- UVIJEK dodaj `logger.exception()` — NIKAD silent catch

### 3. ANTI-PATTERN koji se MORA eliminirati:
```python
# LOŠE — silent swallow
try:
    something()
except:
    pass

# LOŠE — broad catch s return None
try:
    return calculate()
except Exception:
    return None

# DOBRO
try:
    return calculate()
except (ZeroDivisionError, decimal.InvalidOperation) as e:
    logger.warning("Calculation failed for %s: %s", context, e)
    return Decimal("0")
```

### 4. Red rada (po prioritetu):
1. **core/** — 784 catches, fundament svega
2. **pos/** — 246, kritičan za revenue
3. **worktime/** — 166, employee modul
4. **invoicing/** — 118, financijski modul
5. **accounts/** — 86, auth modul
6. **konto/** — 73, računovodstvo
7. Svi ostali po redu

### 5. Za SVAKI fajl:
1. Pročitaj cijeli fajl
2. Identificiraj svaki try/except blok
3. Analiziraj što se poziva unutar try
4. Zamijeni broad catch s najspecifičnijim exception tipom
5. Dodaj logger.exception() ili logger.warning() ako ne postoji
6. TESTIRAJ: `python -c "import <module>"` nakon promjene

## NE DIRATI (scope drugog tima):
- csrf_exempt (DIO 2)
- ORM optimizacije / select_related (DIO 3)
- Ghost appove (DIO 2)
- Frontend/template promjene

## METRIKA USPJEHA
- `grep -rn "except Exception\|except:" | grep -v venv | wc -l` < 200
- `grep -rn "except:" | grep -v venv | wc -l` = 0 (bare except potpuno eliminiran)
- Svi `except Exception` koji ostanu imaju `logger.exception()` u tijelu
- `python manage.py check` prolazi bez grešaka
- Gunicorn restart bez grešaka

## COMMIT PORUKA
```
refactor(exceptions): replace N broad catches with specific exceptions

- core: X → Y specific catches
- pos: X → Y
- [ostali appovi]
- All remaining broad catches have logger.exception()
- Zero bare `except:` remaining
```
