# CC_TASK: Celery Queue Split — POS vs Heavy jobs
**Datum:** 02.04.2026. | **Prioritet:** 🔴 BLOKIRA GO-LIVE kvalitetu
**Procjena:** 2-3 sata | **Rok:** 05.04.2026.
**Vođa:** Sonnet — autonomno

---

## PROBLEM

Jedan Celery worker, jedna queue (`default`), concurrency=2.
Bulk import Synesis (33.270 partnera), SAF-T export, PDF generiranje —
sve dijeli isti worker s POS fiskalizacijom i emailovima.

Glasni susjed scenarij:
1. Admin pokrene bulk_import_synesis → zauzme oba workera
2. Konobar naplaćuje kavu → retry_fiscalization čeka u redu
3. POS loading ikona 8+ sekundi → korisnik misli da sustav puca

---

## RJEŠENJE — 2 workera, 2 queue

### Korak 1: Promijeni systemd konfiguracije

```bash
# /etc/systemd/system/celery-worker.service — ZAMIJENI ExecStart:
ExecStart=/var/www/fina-connect/venv/bin/celery -A core worker \
  --queues=default,critical \
  --loglevel=info \
  --concurrency=4 \
  --hostname=worker-fast@%h

# /etc/systemd/system/celery-worker-heavy.service — NOVI FILE:
[Unit]
Description=Celery Heavy Worker for fina-connect
After=network.target redis.service postgresql.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/var/www/fina-connect
Environment="LANG=en_US.UTF-8" "LC_ALL=en_US.UTF-8"
ExecStart=/var/www/fina-connect/venv/bin/celery -A core worker \
  --queues=heavy \
  --loglevel=info \
  --concurrency=2 \
  --hostname=worker-heavy@%h
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Korak 2: core/settings.py — CELERY_TASK_ROUTES

Dodati ISPOD postojećeg CELERY_BEAT_SCHEDULE:

```python
# ── Queue routing ─────────────────────────────────────────────────
CELERY_TASK_QUEUES_DEFAULT = 'default'

CELERY_TASK_ROUTES = {
    # CRITICAL — uvijek brzo, nikad u heavy queue
    'pos.*':                     {'queue': 'critical'},
    'einvoice.*':                {'queue': 'critical'},
    'core.ai_health_check':      {'queue': 'critical'},
    'core.sonnet_cycle':         {'queue': 'default'},

    # HEAVY — izolirano, ne blokira POS
    'synesis.*':                 {'queue': 'heavy'},
    'accounts.data_export.*':    {'queue': 'heavy'},
    'worktime.*report*':         {'queue': 'heavy'},
    'konto.*export*':            {'queue': 'heavy'},
    'invoicing.*export*':        {'queue': 'heavy'},
    'documents.*bulk*':          {'queue': 'heavy'},
    'udruge.*izvjestaj*':        {'queue': 'heavy'},
}
```

### Korak 3: Označi heavy taskove u kodu

Pretraži sve `@shared_task` koji rade bulk operacije:
```bash
grep -rn "@shared_task\|@app.task" --include="*.py" | grep -v venv | grep -v test | \
  xargs grep -l "bulk\|export\|import\|report\|pdf\|excel\|csv" 2>/dev/null | head -20
```

Za svaki pronađeni heavy task, dodaj `queue='heavy'`:
```python
# PRIJE:
@shared_task
def generate_saft_export(company_id):

# POSLIJE:
@shared_task(queue='heavy')
def generate_saft_export(company_id):
```

### Korak 4: View-ovi koji pozivaju heavy taskove

Za svaki view koji poziva heavy task, dodaj `.apply_async(queue='heavy')`:
```python
# PRIJE:
generate_report.delay(company_id)

# POSLIJE:
generate_report.apply_async(args=[company_id], queue='heavy')
```

I vrati korisniku odmah:
```python
return JsonResponse({
    'status': 'queued',
    'message': 'Izvještaj se generira. Dobit ćete obavijest kada bude spreman.',
    'task_id': task.id,
})
```

---

## PROVJERA MODELA PRIJE PISANJA

```bash
# Pronađi sve taskove koji rade bulk/export/report
grep -rn "@shared_task" --include="tasks.py" | grep -v venv | head -30

# Provjeri trenutnu queue konfiguraciju
grep -n "CELERY_TASK_ROUTES\|task_routes\|queue=" core/settings.py | head -10
```

---

## DEPLOY REDOSLIJED

```bash
# 1. Napravi novi systemd service
sudo nano /etc/systemd/system/celery-worker-heavy.service

# 2. Reload i start
sudo systemctl daemon-reload
sudo systemctl enable celery-worker-heavy
sudo systemctl start celery-worker-heavy
sudo systemctl restart celery-worker

# 3. Verify
sudo systemctl status celery-worker celery-worker-heavy
celery -A core inspect active_queues
```

---

## TESTOVI

```bash
# Test: heavy task ne blokira POS queue
celery -A core inspect reserved  # treba vidjeti heavy worker odvojen
celery -A core inspect active_queues  # critical/default + heavy odvojeno
```

## COMMIT FORMAT

```
feat(infra): celery queue split — POS/critical odvojen od heavy imports/exports

- celery-worker-heavy.service (novi, concurrency=2, queue=heavy)
- celery-worker.service: queues=default,critical, concurrency=4
- CELERY_TASK_ROUTES: pos.* → critical, synesis.* → heavy
- Sve bulk/export/report zadatke označiti @shared_task(queue='heavy')
- Views: heavy taskovi vraćaju odmah 'queued' response
```

---

## NAPOMENA: Dan 2 support (Dron #2) — odgođeno ali NE zanemari

ImprovementSuggestion zlatno dugme postoji ali nema:
- stack_trace capture u momentu prijave
- tenant ID + URL u payload-u
- Status tracking vidljiv korisniku ("vaš ticket #42 je u obradi")

CC_TASK_SUPPORT_WALL.md pisati ODMAH NAKON ovog taska.
