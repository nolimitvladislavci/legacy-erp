# VAL 3 — DIO 2: RUFF CLEANUP + CI/CD (SONNET)
> Sistematičan: auto-fix remaining, GitHub Actions pipeline

## CILJ A: Ruff 3,893 → <500
## CILJ B: GitHub Actions CI pipeline

## A. RUFF CLEANUP
1. Import sorting (I001): 2,577 — `ruff check . --fix --select I001`
2. Remaining unused imports (F401): 645 — review, safe ones auto-fix
3. Unused variables (F841): 215 — `ruff check . --fix --select F841`
4. Ostali: F811 (22), E712 (3), F601 (7)

## B. CI/CD
Kreirati .github/workflows/ci.yml:
- python manage.py check
- ruff check .
- python manage.py test --parallel (smoke subset)

## NE DIRATI:
- ORM (DIO 1)
- i18n (DIO 3)
- Views logic
