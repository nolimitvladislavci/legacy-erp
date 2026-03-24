# GEMINI_TASK_BORG_PATROL — Fenix Patrol + Haiku Triage + Auto-Task
## Agent: Gemini | Prioritet: P0 — BORG 10/10
## Datum: 2026-03-24
## Preduvjet: CC_TASK_BORG_SIGNAL_FOUNDATION.md mora biti DONE

**Čitaj prvo:** BORG_10_10_MASTER_PLAN.md, FENIX_STATUS.md
**Provjeri:** `FenixSignal.objects.filter(status='new').count()` — mora biti > 0

---

## ZADATAK: Fenix Patrol Celery task

**Fajl:** `limit_connect_ai/tasks.py` — dodati novi task

### Patrol logika

```python
@shared_task(name='limit_connect_ai.fenix_patrol')
def fenix_patrol():
    """
    Fenix Patrol — triage novih signala, kreacija taskova.
    Pokreće se svakih 15 minuta via Celery Beat.
    """
    from limit_connect_ai.models import FenixSignal
    import anthropic

    new_signals = FenixSignal.objects.filter(status='new').order_by('created_at')[:20]
    if not new_signals.exists():
        return 'No new signals'

    client = anthropic.Anthropic()
    resolved = []

    for signal in new_signals:
        # Haiku triage
        triage = _haiku_triage(client, signal)

        signal.category = triage['category']
        signal.severity = triage['severity']
        signal.ai_summary = triage['summary']
        signal.ai_suggested_action = triage['action']
        signal.status = 'triaged'
        signal.save(update_fields=[
            'category', 'severity', 'ai_summary',
            'ai_suggested_action', 'status', 'updated_at'
        ])

        # Automatska kreacija taska
        if triage['severity'] in ('critical', 'high'):
            task_file = _create_auto_task(signal, triage)
            signal.task_file = task_file
            signal.status = 'task_created'
            signal.save(update_fields=['task_file', 'status', 'updated_at'])

            # Ivan dobiva WhatsApp za critical
            if triage['severity'] == 'critical':
                _notify_ivan(signal, triage)

        resolved.append(f"#{signal.pk} [{triage['severity']}] {triage['summary'][:50]}")

    # Ažuriraj FENIX_STATUS.md
    _update_fenix_status(new_signals, resolved)

    return f'Patrol: {len(resolved)} signala obrađeno'


def _haiku_triage(client, signal):
    """Haiku klasificira signal — brzo i jeftino."""
    prompt = f"""Ti si FENIX AI Patrol. Analiziraj signal i vrati JSON.

SIGNAL:
Izvor: {signal.source}
Firma: {signal.company.name if signal.company else 'nepoznata'}
Naslov: {signal.title}
Poruka: {signal.body[:500]}
Metadata: {str(signal.metadata)[:200]}

Vrati SAMO JSON (bez markdown):
{{
  "severity": "critical|high|medium|low|info",
  "category": "bug|ux|data|feature|question|anomaly|performance",
  "summary": "jedna rečenica što je problem",
  "action": "što Trojstvo treba napraviti",
  "auto_task": true/false
}}

Pravila:
- critical: sustav ne radi za klijenta (produkcijski bug, POS down, login problem)
- high: funkcija ne radi ali postoji workaround
- medium: UX problem, sporo, nelogično
- low: prijedlog, pitanje, info
- auto_task: true samo za critical i high"""

    resp = client.messages.create(
        model='claude-haiku-4-5-20251001',
        max_tokens=300,
        messages=[{'role': 'user', 'content': prompt}]
    )

    import json
    try:
        return json.loads(resp.content[0].text)
    except Exception:
        return {
            'severity': 'medium', 'category': 'anomaly',
            'summary': signal.title[:100],
            'action': 'Manualni pregled potreban',
            'auto_task': False
        }


def _create_auto_task(signal, triage):
    """Kreira CC_TASK fajl automatski za high/critical signale."""
    from django.utils import timezone
    import os

    date_str = timezone.now().strftime('%Y%m%d')
    task_name = f'CC_TASK_SIGNAL_{date_str}_{signal.pk:04d}.md'
    task_path = os.path.join('/var/www/fina-connect', task_name)

    screenshot_note = ''
    if signal.screenshot:
        screenshot_note = f'Screenshot: {signal.screenshot.url}'

    content = f"""# AUTO-TASK od Fenix Patrol
## Agent: Claude Code | Severity: {triage['severity'].upper()} | Signal #{signal.pk}
## Datum: {timezone.now().strftime('%Y-%m-%d %H:%M')}

---

## IZVOR SIGNALA
- Kanal: {signal.source}
- Firma: {signal.company.name if signal.company else 'N/A'}
- Korisnik: {signal.user or 'anoniman'}

## PORUKA KORISNIKA
{signal.body}

{screenshot_note}

## FENIX AI ANALIZA
- Severity: {triage['severity']}
- Kategorija: {triage['category']}
- Sažetak: {triage['summary']}
- Predložena akcija: {triage['action']}

---

## OBAVEZNO PRIJE PISANJA KODA
1. Pročitaj FENIX_STATUS.md
2. Pročitaj relevantni models.py (ne pretpostavljaj polja)
3. git log --oneline -5 (provjeri zadnje promjene)

## DEFINICIJA DONE
- [ ] Problem analiziran i lociran
- [ ] Fix implementiran
- [ ] Test potvrđuje da je riješeno
- [ ] FenixSignal #{signal.pk} ažuriran: status='resolved'
- [ ] Commit s porukom: fix(signal-{signal.pk}): {{kratki opis}}
"""

    with open(task_path, 'w') as f:
        f.write(content)

    return task_name


def _notify_ivan(signal, triage):
    """Ivan dobiva WhatsApp notifikaciju za critical signale."""
    from core.whatsapp import send_text
    from django.conf import settings

    ivan_phone = getattr(settings, 'IVAN_WHATSAPP', '')
    if not ivan_phone:
        return

    msg = (f"🔴 FENIX CRITICAL\n"
           f"Signal #{signal.pk} | {signal.company.name if signal.company else 'N/A'}\n"
           f"{triage['summary']}\n"
           f"Akcija: {triage['action'][:100]}")
    send_text(ivan_phone, msg)


def _update_fenix_status(signals, resolved):
    """Dodaje sekciju novih signala u FENIX_STATUS.md."""
    from django.utils import timezone
    import os

    status_path = '/var/www/fina-connect/FENIX_STATUS.md'
    if not os.path.exists(status_path):
        return

    with open(status_path, 'r') as f:
        content = f.read()

    from django.utils import timezone
    ts = timezone.now().strftime('%Y-%m-%d %H:%M')
    section = f"\n## Fenix Patrol — {ts}\n"
    for line in resolved:
        section += f"- {line}\n"

    # Ubaci odmah nakon headera
    insert_after = '---\n'
    if insert_after in content:
        content = content.replace(insert_after, insert_after + section, 1)
    else:
        content = section + content

    with open(status_path, 'w') as f:
        f.write(content)
```

### Beat schedule

U `core/settings.py` ili `core/celery.py`, dodati u `beat_schedule`:
```python
'fenix-patrol': {
    'task': 'limit_connect_ai.fenix_patrol',
    'schedule': crontab(minute='*/15'),
},
```

---

## TEST

```bash
# Manualni pokretanje patrole
venv/bin/python -c "
import os; os.environ['DJANGO_SETTINGS_MODULE']='core.settings'
import django; django.setup()
from limit_connect_ai.tasks import fenix_patrol
result = fenix_patrol()
print(result)
"
```

---

## DEFINICIJA DONE

- [ ] `fenix_patrol` task postoji i radi
- [ ] Haiku triages signal za < 5 sekundi
- [ ] Critical signal → CC_TASK fajl kreiran automatski
- [ ] Beat schedule registriran (svakih 15 min)
- [ ] Test: manualni patrol obradi ≥ 1 signal
- [ ] FENIX_STATUS.md ažuriran s patrol sekcijom
