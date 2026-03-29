# CC_TASK_SLA_ANOMALY_REPORT.md
# Dodijeljen: CC Code (s Gemini monitoring-om)
# Prioritet: SREDNJE — H2.4
# Procjena: 2-3 dana
# Ref: MASTER_PLAN_2026.md → H2.4
# Preduvjet: StatusTimestamp podaci postoje — model ured(an

## FILOZOFIJA

NE šaljemo svaki dan izvještaj.
Šaljemo SAMO kad se dogodi nešto vrijedno znanja.

Tišina = sve je normalno = to je poruka.
Anomalija = |Z-score| > 1.5 = WhatsApp alarm.
Rekord = novi minimum = WhatsApp slavlje.

Alert fatigue je stvaran. Riješavamo ga Z-scoreom, ne "AI pragom tolerancije".

## MATEMATIKA

Z-score = (danas - rolling_avg_7_dana) / rolling_std_7_dana

Primjer:
- Rolling avg (WO draft→completed): 4.1h
- Heute: 8.2h  
- Std: 1.5h
- Z = (8.2 - 4.1) / 1.5 = 2.73 → ALARM (> 1.5)

Rekord: danas < (rolling_min * 0.85) → SLAVLJE

## IMPLEMENTACIJA

### KORAK 1 — Provjeri StatusTimestamp podatke

```bash
cd /var/www/fina-connect && source venv/bin/activate
python manage.py shell -c "
from borg_ops.models import StatusTimestamp
total = StatusTimestamp.objects.count()
completed = StatusTimestamp.objects.filter(exited_at__isnull=False).count()
print(f'Ukupno SLA zapisa: {total}')
print(f'Završenih (s trajanjem): {completed}')
from borg_ops.models import StatusTimestamp
import django.db.models as m
avg = StatusTimestamp.objects.filter(
    duration_seconds__isnull=False
).aggregate(m.Avg('duration_seconds'))
print(f'Prosjek trajanja: {avg}')
"
```

### KORAK 2 — SLA Analytics Service

Kreirati: `borg_ops/sla_analytics.py`

```python
"""
SLA Analytics — Z-score anomaly detection na StatusTimestamp podacima.
"""
from datetime import timedelta
from decimal import Decimal
import statistics
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType


def get_transition_durations(model_class, from_status, to_status, days=7):
    """
    Vraća listu trajanja (u sekundama) za određenu tranziciju u zadnjih N dana.
    """
    from borg_ops.models import StatusTimestamp
    
    ct = ContentType.objects.get_for_model(model_class)
    cutoff = timezone.now() - timedelta(days=days)
    
    # Nađi sve završene StatusTimestamp zapise za from_status u zadnjih N dana
    durations = list(
        StatusTimestamp.objects.filter(
            content_type=ct,
            status=from_status,
            exited_at__gte=cutoff,
            duration_seconds__isnull=False,
        ).values_list('duration_seconds', flat=True)
    )
    return durations


def compute_z_score(today_values, historical_values):
    """
    Izračunava Z-score za danas vs. historical.
    Returns: (today_avg, hist_avg, z_score) ili None ako nema dovoljno podataka.
    """
    if len(historical_values) < 3:
        return None  # Premalo podataka za statistiku
    
    today_avg = statistics.mean(today_values) if today_values else None
    if today_avg is None:
        return None
    
    hist_avg = statistics.mean(historical_values)
    try:
        hist_std = statistics.stdev(historical_values)
    except statistics.StatisticsError:
        return None
    
    if hist_std == 0:
        return None  # Nema varijabilnosti
    
    z = (today_avg - hist_avg) / hist_std
    return (today_avg, hist_avg, z)


def check_all_transitions():
    """
    Provjera svih ključnih tranzicija.
    Returns lista (model_name, transition_desc, today_avg_h, hist_avg_h, z_score, is_record)
    """
    # Definirati tranzicije koje pratimo
    # Format: (ModelClass, from_status, to_status, human_name)
    TRACKED_TRANSITIONS = []
    
    # Work Orders
    try:
        from work_orders.models import WorkOrder
        TRACKED_TRANSITIONS += [
            (WorkOrder, 'draft',       'in_progress', 'WO: Nacrt → U tijeku'),
            (WorkOrder, 'in_progress', 'completed',   'WO: U tijeku → Završen'),
            (WorkOrder, 'completed',   'invoiced',    'WO: Završen → Fakturiran'),
        ]
    except ImportError:
        pass
    
    # Burza
    try:
        from burza.models import ProjectLead
        TRACKED_TRANSITIONS += [
            (ProjectLead, 'NA_BURZI',  'PREUZETO',  'Burza: Objava → Preuzeto'),
            (ProjectLead, 'PREUZETO',  'RIJESENO',  'Burza: Preuzeto → Riješeno'),
        ]
    except ImportError:
        pass
    
    # Interventions
    try:
        from interventions.models import HitnaIntervencija
        TRACKED_TRANSITIONS += [
            (HitnaIntervencija, 'NOVO', 'DODIJELJENO', 'Intervencija: Novo → Dodijeljeno'),
            (HitnaIntervencija, 'DODIJELJENO', 'NA_PUTU', 'Intervencija: → Na putu'),
        ]
    except ImportError:
        pass
    
    results = []
    today = timezone.now().date()
    
    for ModelClass, from_st, to_st, name in TRACKED_TRANSITIONS:
        # Danas
        from borg_ops.models import StatusTimestamp
        ct = ContentType.objects.get_for_model(ModelClass)
        
        today_durations = list(
            StatusTimestamp.objects.filter(
                content_type=ct, status=from_st,
                exited_at__date=today,
                duration_seconds__isnull=False,
            ).values_list('duration_seconds', flat=True)
        )
        
        # Zadnjih 7 dana (bez danas)
        hist_durations = get_transition_durations(ModelClass, from_st, to_st, days=8)
        # Makni danas iz historije
        if today_durations:
            for d in today_durations:
                if d in hist_durations:
                    hist_durations.remove(d)
        
        if not today_durations:
            continue
        
        result = compute_z_score(today_durations, hist_durations)
        if result is None:
            continue
        
        today_avg_s, hist_avg_s, z = result
        today_avg_h = round(today_avg_s / 3600, 1)
        hist_avg_h  = round(hist_avg_s / 3600, 1)
        
        # Je li rekord?
        all_time_min = min(hist_durations) if hist_durations else None
        is_record = (all_time_min is not None and 
                     today_avg_s < all_time_min * 0.85)
        
        results.append({
            'name': name,
            'today_avg_h': today_avg_h,
            'hist_avg_h': hist_avg_h,
            'z_score': round(z, 2),
            'is_record': is_record,
            'sample_size': len(today_durations),
        })
    
    return results


def should_send_report(results):
    """
    Vraća (should_send, anomalies, records).
    Šalji SAMO ako ima anomalija ili rekorda.
    """
    anomalies = [r for r in results if abs(r['z_score']) > 1.5]
    records = [r for r in results if r['is_record']]
    return bool(anomalies or records), anomalies, records


def format_whatsapp_message(anomalies, records):
    """Formatira WhatsApp poruku."""
    lines = ['*BORG SLA Report*']
    
    if records:
        lines.append('\n🏆 *REKORD*')
        for r in records:
            lines.append(f"  {r['name']}: {r['today_avg_h']}h ← novi rekord! (prosjek bio {r['hist_avg_h']}h)")
    
    if anomalies:
        lines.append('\n⚠️ *ANOMALIJE*')
        for r in anomalies:
            direction = "sporije" if r['z_score'] > 0 else "brže"
            lines.append(
                f"  {r['name']}: {r['today_avg_h']}h "
                f"({direction} od prosjeka {r['hist_avg_h']}h, "
                f"Z={r['z_score']})"
            )
    
    lines.append(f"\n_Nema poruke = sve normalno_")
    return '\n'.join(lines)
```

### KORAK 3 — Celery Task

U `borg_ops/tasks.py` dodati:

```python
@shared_task(name='borg_ops.sla_daily_check', bind=True)
def sla_daily_check(self):
    """
    Svaki dan u 17:30 provjerava SLA anomalije.
    Šalje WhatsApp SAMO ako ima anomalije ili rekorda.
    """
    from borg_ops.sla_analytics import check_all_transitions, should_send_report, format_whatsapp_message
    import logging
    logger = logging.getLogger('borg.sla')
    
    results = check_all_transitions()
    
    if not results:
        logger.info('SLA check: nema dovoljno podataka za analizu.')
        return {'status': 'no_data', 'checked': 0}
    
    should_send, anomalies, records = should_send_report(results)
    
    if not should_send:
        logger.info('SLA check: sve normalno. Tišina.')
        return {'status': 'normal', 'checked': len(results)}
    
    message = format_whatsapp_message(anomalies, records)
    
    # Pošalji WhatsApp (WAHA)
    try:
        import requests
        from django.conf import settings
        WAHA_URL = getattr(settings, 'WAHA_URL', 'http://localhost:3000')
        IVAN_PHONE = '+4915771998747'  # Ivan WhatsApp
        
        resp = requests.post(f'{WAHA_URL}/api/sendText', json={
            'session': 'WORKING',
            'chatId': f'{IVAN_PHONE}@c.us',
            'text': message
        }, timeout=10)
        
        logger.info('SLA WhatsApp poslano: %s', resp.status_code)
        return {
            'status': 'sent',
            'anomalies': len(anomalies),
            'records': len(records),
            'checked': len(results)
        }
    except Exception as e:
        logger.error('SLA WhatsApp greška: %s', e)
        return {'status': 'error', 'error': str(e)}
```

### KORAK 4 — Celery Beat Schedule

U settings.py (ili gdje je definiran CELERY_BEAT_SCHEDULE), dodati:

```python
CELERY_BEAT_SCHEDULE = {
    # ... postojeći taskovi ...
    'sla-daily-check': {
        'task': 'borg_ops.sla_daily_check',
        'schedule': crontab(hour=17, minute=30),  # Svaki dan 17:30
    },
}
```

```bash
# Provjeri gdje je CELERY_BEAT_SCHEDULE definiran
grep -rn "CELERY_BEAT_SCHEDULE\|celery_beat" /var/www/fina-connect --include="*.py" | grep -v venv | head -10
```

## VERIFIKACIJA

```bash
cd /var/www/fina-connect && source venv/bin/activate

# Ručni test
python manage.py shell -c "
from borg_ops.sla_analytics import check_all_transitions, should_send_report
results = check_all_transitions()
print(f'Analizirane tranzicije: {len(results)}')
for r in results:
    print(f'  {r[\"name\"]}: Z={r[\"z_score\"]}, danas={r[\"today_avg_h\"]}h, hist={r[\"hist_avg_h\"]}h')
should_send, anomalies, records = should_send_report(results)
print(f'Šalje: {should_send} (anomalije: {len(anomalies)}, rekordi: {len(records)})')
"

# Ručno pokretanje taska
python manage.py shell -c "
from borg_ops.tasks import sla_daily_check
result = sla_daily_check.apply()
print('Rezultat:', result.result)
"
```

## COMMIT

```bash
git add borg_ops/sla_analytics.py borg_ops/tasks.py
git commit -m "feat(borg-ops): SLA anomaly detection — Z-score WhatsApp report

Celery beat task 17:30 svaki dan.
Šalje WhatsApp SAMO za anomalije (|Z|>1.5) ili rekorde.
Tišina = sve normalno. Nema alert fatigue.
Prati: WO, Burza, Intervencija tranzicije."
```

---
# STATUS: PLANIRA SE — Horizont 2 (Q4 2026)
# Preduvjet: StatusTimestamp ima dovoljno podataka (30+ dana produkcije)
