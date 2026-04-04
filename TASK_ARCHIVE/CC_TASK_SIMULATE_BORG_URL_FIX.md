# CC_TASK_SIMULATE_BORG_URL_FIX.md
# Dodijeljen: CC Code
# Prioritet: VISOKO — blokira simulate_borg sidebar_urls (sada 25%)
# Procjena: 30 min
# Ref: MASTER_PLAN_2026.md → P0.3

## PROBLEM

simulate_borg sidebar_urls test koristi krive URL nazive.
Provjera je pokazala 3/12 (25%) umjesto 12/12.

## PROVJERI TOČNE URL NAZIVE (OBAVEZNO PRIJE PISANJA!)

```bash
grep -n "name=" /var/www/fina-connect/invoicing/urls.py | head -5
grep -n "name=" /var/www/fina-connect/partners/urls.py | head -5
grep -n "name=" /var/www/fina-connect/pos/urls.py | head -5
grep -n "name=" /var/www/fina-connect/worktime/urls.py | head -5
grep -n "name=" /var/www/fina-connect/burza/urls.py | head -5
grep -n "name=" /var/www/fina-connect/inventory/urls.py | head -5
```

## POZNATE ISPRAVKE (verificirano 2026-03-29)

U core/management/commands/simulate_borg.py, metoda _sim_sidebar_urls():

```python
# STARO → ISPRAVNO
sidebar_url_names = [
    ('dashboard', []),
    ('invoicing:index', []),          # BILO: invoicing:invoice_list
    ('partners:list', []),            # BILO: partners:partner_list
    ('pos:dashboard', []),            # BILO: pos:joker
    ('work_orders:list', []),         # OK
    ('worktime:ts_worker', []),       # BILO: worktime:list
    ('burza:kanban', []),             # BILO: burza:lead_list
    ('inventory:list', []),           # BILO: inventory:item_list
    ('experiences:experience_list', []),   # OK (ali namespace fix u P0.6)
    ('experiences:package_list', []),
    ('experiences:recall_list', []),
    ('borg_ops:operations_dashboard', []),
]
```

NAPOMENA: Provjeri svaki naziv gore s `grep -n "name="` prije nego staviš.
Ako je ijedan naziv drugačiji od onog u urls.py — koristi pravi naziv iz urls.py.

## VERIFIKACIJA

```bash
cd /var/www/fina-connect && source venv/bin/activate
python manage.py simulate_borg --modules sidebar_urls 2>&1

# Cilj: sidebar_urls ██████████ 100% (12/12)
```

## COMMIT

```bash
git add core/management/commands/simulate_borg.py
git commit -m "fix(simulate-borg): ispravni URL nazivi u sidebar_urls testu

Ispravka: invoice_list→index, partner_list→list, joker→dashboard,
worktime:list→ts_worker, lead_list→kanban, item_list→list"
git log --oneline -3
```

---
# STATUS: READY_FOR_CC_CODE
# Najbrži task u cijelom planu — 30 min
