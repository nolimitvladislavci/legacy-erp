# CC TASK — DeepSeek Kompletna Analiza Kodebase
**Datum: 14.04.2026. | Prioritet: VISOK**
**Executor: DeepSeek-V3.2 + CC Code | Reviewer: Gemini | Koordinator: Sonnet**

## ⚠️ NAPOMENE
1. Python: `/var/www/fina-connect/venv/bin/python` — NIKAD `python`
2. systemctl: NEMOJ — napiši "POTREBAN RESTART" na kraju
3. DeepSeek se poziva kroz: `from core.deepseek_client import deepseek_direct`
4. WhatsApp pattern — kopirati doslovno, ne mijenjati

---

## Cilj
DeepSeek analizira kompletnu arhitekturu i identificira:
1. Arhitekturalne probleme (ne samo bugove)
2. N+1 querije koje automatski test ne hvata
3. Sigurnosne ranjivosti u poslovnoj logici
4. Nedostajuće validacije (OIB, IBAN, PDV)
5. Dead code koji usporava startup
6. Prijedloge za refaktor koji daju 10/10

---

## FAZA 1 — Inventura arhitekture (DeepSeek analiza)

```bash
cd /var/www/fina-connect

# Koliko app-ova, modela, viewova ima projekt
/var/www/fina-connect/venv/bin/python manage.py shell -c "
from django.apps import apps
models = list(apps.get_models())
print(f'Apps: {len(apps.get_app_configs())}')
print(f'Modeli: {len(models)}')
print()
# Top 10 modela po broju polja
from django.db.models import fields as f
for m in sorted(models, key=lambda x: len(x._meta.get_fields()), reverse=True)[:10]:
    print(f'{m.__name__}: {len(m._meta.get_fields())} polja')
" 2>/dev/null

# Statistika kodebase
find . -name '*.py' | grep -v venv | grep -v migration | grep -v backup | \
  xargs wc -l 2>/dev/null | sort -rn | head -20
```

---

## FAZA 2 — DeepSeek analiza po modulima

Za svaki kritični modul, pokreni DeepSeek analizu:

```python
# Skriptu snimi kao /tmp/deepseek_analyze.py i pokreni
import os, sys, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'core.settings'
sys.path.insert(0, '/var/www/fina-connect')
django.setup()

from core.deepseek_client import deepseek_direct

MODULI = [
    ('core/company_utils.py', 'multi-tenant izolacija'),
    ('pos/views.py', 'POS logika i fiskalizacija'),
    ('invoicing/models.py', 'Invoice model i poslovne validacije'),
    ('accounts/views.py', 'auth, PIN, company switch'),
    ('permissions/route_registry.py', 'pristupna kontrola'),
    ('core/middleware/', 'middleware stack'),
    ('limit_connect_ai/tasks.py', 'AI task logika'),
]

report = []
for filepath, kontekst in MODULI:
    full_path = f'/var/www/fina-connect/{filepath}'
    if os.path.isfile(full_path):
        kod = open(full_path).read()[:3000]  # max 3000 znakova
    elif os.path.isdir(full_path):
        kod = ''
        for f in os.listdir(full_path):
            if f.endswith('.py'):
                kod += open(f'{full_path}/{f}').read()[:1000]
        kod = kod[:3000]
    else:
        continue

    analiza = deepseek_direct(
        prompt=f"Analiziraj ovaj Django kod ({kontekst}). Pronađi: N+1 querije, sigurnosne rupe, manjkave validacije, dead code. Odgovori kao lista max 5 konkretnih problema s prijedlogom fixa.",
        system="Ti si senior Django security i performance inženjer. Budi konkretan, ne generičan.",
        max_tokens=600,
        temperature=0.2,
    )
    report.append(f"\n## {filepath} ({kontekst})\n{analiza}")
    print(f"✅ Analizirano: {filepath}")

# Spremi report
with open('/var/www/fina-connect/DEEPSEEK_CODE_ANALYSIS.md', 'w') as f:
    f.write("# DeepSeek Analiza Kodebase\n**Datum: " + __import__('datetime').date.today().isoformat() + "**\n")
    f.write("\n".join(report))

print("\n✅ Report: /var/www/fina-connect/DEEPSEEK_CODE_ANALYSIS.md")
```

Pokreni:
```bash
/var/www/fina-connect/venv/bin/python /tmp/deepseek_analyze.py
```

---

## FAZA 3 — N+1 Query detekcija

```bash
/var/www/fina-connect/venv/bin/python manage.py shell -c "
# Simuliraj request i broji querije
from django.test.utils import override_settings
from django.db import connection, reset_queries

# Testiraj kritični invoice list view
reset_queries()
from invoicing.models import Invoice
company_id = 1  # zamijeni s pravim ID-om
invoices = list(Invoice.objects.filter(company_id=company_id)[:20])
for inv in invoices:
    _ = inv.client  # svaki dohvat = novi query (N+1!)

print(f'Queriji za 20 faktura: {len(connection.queries)}')
print('Treba biti: 1-3 (s select_related)')
" 2>/dev/null
```

---

## FAZA 4 — Sigurnosni scan

```bash
# Instaliraj bandit za Python security scan
/var/www/fina-connect/venv/bin/pip install bandit --break-system-packages -q

# Pokreni na kritičnim modulima
/var/www/fina-connect/venv/bin/bandit -r \
  /var/www/fina-connect/core/ \
  /var/www/fina-connect/invoicing/ \
  /var/www/fina-connect/pos/ \
  /var/www/fina-connect/accounts/ \
  -ll -f txt 2>/dev/null | head -50
```

---

## FAZA 5 — Dead code detekcija

```bash
/var/www/fina-connect/venv/bin/pip install vulture --break-system-packages -q

/var/www/fina-connect/venv/bin/vulture \
  /var/www/fina-connect/core/ \
  /var/www/fina-connect/invoicing/ \
  /var/www/fina-connect/pos/ \
  --min-confidence 80 2>/dev/null | head -30
```

---

## Po završetku

```bash
cd /var/www/fina-connect

git add DEEPSEEK_CODE_ANALYSIS.md
git commit -m "analysis: DeepSeek kompletna analiza kodebase — arhitektura, N+1, sigurnost"

/var/www/fina-connect/venv/bin/python -c "
import os,sys,django
os.environ['DJANGO_SETTINGS_MODULE']='core.settings'
sys.path.insert(0,'/var/www/fina-connect')
django.setup()
from core.whatsapp import send_text

# Pročitaj summary iz reporta
report = open('DEEPSEEK_CODE_ANALYSIS.md').read()
problemi = report.count('##') - 1
send_text('4915771998747',
    f'DEEPSEEK ANALIZA GOTOVA\n{problemi} modula analizirano\nReport: DEEPSEEK_CODE_ANALYSIS.md\nSonnet pregledava i prioritizira.')
" 2>/dev/null

echo "POTREBAN GUNICORN RELOAD"
```
