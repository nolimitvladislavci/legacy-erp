# VAL 2 — DIO 2: CSRF FINAL + EXCEPTION CLEANUP + LINTER (SONNET/HAIKU)
> Sistematičan završetak prethodnog vala + code quality tooling

## CILJ A: csrf_exempt 64 → <10
## CILJ B: Broad catches 734 → <300
## CILJ C: Ruff linter setup + first pass

---

## A. CSRF FINAL AUDIT (64 → <10)

### Preostali csrf_exempt po appu:
```
appointments/views.py  — 14 (NAJVIŠE — booking AJAX)
pos/views.py           — 18 (POS API + browser mix)
core/views.py          — 16 
eracun/                — 7 (webhookovi — LEGITIMNI)
synesis/               — 6
fenix_input/           — 4
ostali                 — ~10
```

### Za svaki preostali csrf_exempt:
1. Otvoriti view i provjeriti je li AJAX iz browsera (→ ukloni, HTMX šalje CSRF)
2. Je li DRF API endpoint (→ prebaci na TokenAuth)
3. Je li webhook od externog servisa (→ OSTAVI + dodaj HMAC)
4. Je li public booking (→ provjeri BookingSignature)

### appointments/ (14 csrf_exempt) — PRIORITET:
- Većina su booking AJAX handleri — trebaju CSRF token iz HTMX
- Public booking endpoint — treba BookingSignature

---

## B. EXCEPTION HANDLING FINAL (734 → <300)

### Preostali broad catches:
- Većina su u test fajlovima i middleware
- Fokus na NON-TEST fajlove samo
- Za svaki preostali `except Exception`:
  1. Ako je u middleware/signal → OK, ali dodaj logger.exception()
  2. Ako je u Celery task top-level → OK, ali dodaj logger.exception()
  3. Ako je u testu → OSTAVI (test namjerno testira error path)
  4. Sve ostalo → specificiraj

### Bare except: (9 preostalih) — SVE ELIMINIRATI:
```bash
grep -rn "except:" --include="*.py" | grep -v venv | grep -v "except Exception" | grep -v backups
```
Svaki bare `except:` zamijeni s `except Exception:` minimalno.

---

## C. RUFF LINTER SETUP

### Instalacija:
```bash
pip install ruff
```

### Konfiguracija (pyproject.toml):
```toml
[tool.ruff]
target-version = "py312"
line-length = 120
select = ["E", "W", "F", "I", "UP", "B", "SIM"]
ignore = ["E501"]  # line length — postupno

[tool.ruff.per-file-ignores]
"*/migrations/*" = ["ALL"]
"*/tests*" = ["B", "SIM"]
```

### Pokretanje:
```bash
ruff check . --fix  # auto-fix what's safe
ruff check . --statistics  # see what's left
```

## NE DIRATI:
- Modele (DIO 1 — Opus)
- ORM optimizacije (DIO 3)

## METRIKA USPJEHA
- csrf_exempt: 64 → <10
- Broad catches: 734 → <300
- Bare except: 9 → 0
- Ruff: 0 E/W/F errors (unused imports, undefined vars)
