# VAL 3 — DIO 3: I18N FINAL + API DOCS FIX (HAIKU)
> Najjednostavniji: popuni 95 stringova, fix 500 na /api/docs/

## CILJ A: i18n 95 → 0
## CILJ B: Fix /api/docs/ 500 error

## A. I18N
- EL: 64 praznih — prevedi HR→EL
- TR: 28 praznih — prevedi HR→TR
- HR: 3 prazna — copy msgid→msgstr
- compilemessages

## B. API DOCS
- Debug 500 na /api/docs/
- Vjerovatno auth required ili schema generation error
- Fix i testirati

## NE DIRATI:
- ORM (DIO 1)
- Ruff/CI (DIO 2)
