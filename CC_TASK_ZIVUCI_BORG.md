# CC_TASK: ŽIVUĆI BORG — AI 10/10
# Dodijelio: Sonnet | Datum: 2026-04-01 | Prioritet: 🔴 STRATEŠKI
# Ref: BORG_ZIVUCI_MANIFEST.md

# PRAVILO: Čitaj models.py SVAKI PUT. Nikad ne pretpostavljaj field name.
# PRAVILO: Svaki task = poseban commit. Gunicorn restart na kraju.

---

## TASK A — BOOKING AI REMINDERI (Stup 8) ← POČNI OVDJE

### A1: 24h WhatsApp reminder
U `appointments/tasks.py` dodaj Celery task koji se pokreće svaki dan u 10:00:

```python
@shared_task
def send_booking_reminders():
    """Pošalji WA reminder za sve termine sutra."""
    from .models import Appointment
    from django.utils import timezone
    import datetime

    tomorrow = timezone.localdate() + datetime.timedelta(days=1)
    appts = Appointment.objects.filter(
        start_time__date=tomorrow,
        status__in=['scheduled', 'confirmed'],
        whatsapp_number__isnull=False
    ).exclude(whatsapp_number='')

    sent = 0
    for appt in appts:
        if appt.whatsapp_reminder_sent:
            continue
        msg = (
            f"⏰ Podsjetnik — termin sutra!\n\n"
            f"Usluga: {appt.service.name if appt.service else appt.title}\n"
            f"Termin: {appt.start_time.strftime('%d.%m.%Y u %H:%M')}\n"
            f"Trajanje: {int(appt.service.duration.total_seconds()//60) if appt.service else '?'} min\n\n"
            f"Ako trebate otkazati, odgovorite OTKAZI ili nazovite +385913912621.\n"
            f"Hvala! 🙏"
        )
        try:
            from core.whatsapp_tasks import send_whatsapp_text_task
            send_whatsapp_text_task.delay(appt.whatsapp_number, msg)
            appt.whatsapp_reminder_sent = True
            appt.save(update_fields=['whatsapp_reminder_sent'])
            sent += 1
        except Exception as e:
            logger.error('Reminder fail %s: %s', appt.id, e)

    logger.info('Booking reminders sent: %d/%d', sent, appts.count())
    return {'sent': sent, 'total': appts.count()}
```

### A2: Registriraj u django-celery-beat (settings.py CELERY_BEAT_SCHEDULE):
```python
'booking-reminders-daily': {
    'task': 'appointments.tasks.send_booking_reminders',
    'schedule': crontab(hour=10, minute=0),
},
```

### A3: Auto-confirm booking ako je korisnik već bio
U `api_submit_public_booking` — ako isti `phone` već ima prethodnih termina i svi su bili `completed` → status = 'confirmed' umjesto 'scheduled'.
Poruka WA: "Pozdrav {ime}! Vidjeli smo se već — termin je automatski potvrđen. 👋"

### A4: "Slobodan termin danas" notifikacija
Celery task u 09:00 — ako ima slobodnih termina DANAS (cancellations ili neispunjeni slotovi) →
WhatsApp vlasniku (BookingResource.whatsapp_number):
"📅 Slobodni termini danas: 11:00, 14:30, 16:00 — imaš li koga pozvati?"

---

## TASK B — FINANCIAL GUARDIAN (Stup 9)

### B1: Model FinancialAlert (ako ne postoji)
Provjeri postoji li — `grep -rn "FinancialAlert\|financial_alert" limit_connect_ai/models.py`
Ako ne → dodaj:
```python
class FinancialAlert(models.Model):
    TYPES = [
        ('pdv_deadline', 'PDV rok plaćanja'),
        ('joppd_deadline', 'JOPPD rok'),
        ('invoice_overdue_60', 'Faktura > 60 dana neplaćena'),
        ('unexpected_expense', 'Neočekivani trošak'),
        ('cash_flow_warning', 'Upozorenje cash flow'),
    ]
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE)
    alert_type = models.CharField(max_length=30, choices=TYPES)
    message = models.TextField()
    amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    is_sent = models.BooleanField(default=False)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
```

### B2: Celery task `financial_guardian_check` — svaki dan u 18:00
Provjere:
1. **PDV deadline**: 7. u mj → reminder 5 dana prije svim PDV obveznicima
2. **JOPPD**: 15. u mj → reminder 3 dana prije tvrtkama koje imaju aktivnih radnika
3. **Dospjele fakture > 60 dana**: pronađi → WA vlasniku tvrtke s listom
4. **Neočekivani trošak**: usporedi ovomjesečne troškove s prosjekom zadnja 3 mj. → ako > 30% → alert

Format WA poruke:
```
🔔 FINANCIAL GUARDIAN — {datum}

⚠️ PDV rok: 7.4.2026 (za 5 dana)
   Otvorene fakture: 3, ukupno 4.250 EUR

📄 Neplaćene > 60 dana: 2 fakture
   • Partner ABC — 1.200 EUR (72 dana)
   • Partner XYZ — 850 EUR (65 dana)

✅ Sve ostalo uredno.
```

### B3: Registriraj u CELERY_BEAT_SCHEDULE:
```python
'financial-guardian-daily': {
    'task': 'limit_connect_ai.tasks.financial_guardian_check',
    'schedule': crontab(hour=18, minute=0),
},
```

---

## TASK C — FENIX CORTEX LIVE FEED (Stup 1)

### C1: WebSocket endpoint za live AI feed
U `core/urls.py` (ili consumers.py ako postoji):
- Endpoint: `/ws/cortex/` ili fallback na SSE `/cortex/feed/`

Ako Django Channels nije instaliran → koristi SSE (Server-Sent Events):
```python
# core/cortex_views.py
import json, time
from django.http import StreamingHttpResponse

def cortex_feed(request):
    """SSE stream za Fenix Cortex live feed."""
    def event_stream():
        while True:
            data = get_cortex_snapshot(request.user)
            yield f"data: {json.dumps(data)}\n\n"
            time.sleep(60)
    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response

def get_cortex_snapshot(user):
    """Trenutna slika stanja platforme za live feed."""
    from limit_connect_ai.proactive_widget import get_dashboard_insights
    # ...agregira sve: signale, anomalije, predviđanja, financial alerts
```

### C2: Cortex widget na dashboard
U dashboard template (provjeri koji je — `grep -rn "cortex\|fenix.feed" templates/`) dodaj:

```html
<div id="fenixCortex" class="cortex-panel">
  <div class="cortex-header">
    <span class="cortex-dot live"></span>
    <span>FENIX CORTEX — Živi signal</span>
    <span id="cortexTime" class="cortex-time"></span>
  </div>
  <div id="cortexFeed" class="cortex-feed">
    <!-- Dinamički punjeno SSE streamom -->
  </div>
</div>

<script>
const evtSource = new EventSource('/cortex/feed/');
evtSource.onmessage = function(e) {
  const data = JSON.parse(e.data);
  renderCortexFeed(data);
  document.getElementById('cortexTime').textContent = new Date().toLocaleTimeString('hr');
};
</script>
```

### C3: CSS za Cortex panel (premium, dark, pulsing dot):
- Tamna pozadina s tankim zlatnim borderom
- Zelena pulsing točka ("LIVE")
- Feed stavke: ikona + tekst + timestamp + badge (INFO/WARN/ALERT)
- Smooth scroll kad dolaze novi eventi

---

## TASK D — CHURN PREVENTION AUTO-AKCIJA (Stup 4)

### D1: ChurnAction model (ako ne postoji)
```python
class ChurnAction(models.Model):
    partner = models.ForeignKey('partners.Partner', on_delete=models.CASCADE)
    action_type = models.CharField(max_length=30,
        choices=[('wa_sent','WA poslan'),('call_suggested','Poziv predložen'),('discount','Popust kreiran')])
    message = models.TextField()
    result = models.CharField(max_length=20, default='pending',
        choices=[('pending','Čeka'),('responded','Odgovorio'),('lost','Izgubljen'),('retained','Zadržan')])
    created_at = models.DateTimeField(auto_now_add=True)
```

### D2: Celery task `execute_churn_prevention` — jednom tjedno (pon 09:00)
Za top 10 churn risk partnera (iz predictions.py):
- Dohvati churn score
- Generiraj personaliziranu WA poruku (Haiku/Gemini)
- Pošalji s opt-out opcijom
- Kreira ChurnAction record

---

## TASK E — ANOMALY AUTO-FIX HANDLERS (Stup 6)

Lokacija: `core/anomaly_handlers.py` (novi fajl)

5 handlera:
```python
ANOMALY_HANDLERS = {
    'duplicate_partner': handle_duplicate_partner,      # auto-merge ako > 95% match
    'invoice_missing_oib': handle_invoice_missing_oib,  # auto-lookup + fill
    'negative_stock': handle_negative_stock,            # alert dobavljaču WA
    'pos_timeout': handle_pos_timeout,                  # auto-recovery sequence
    'fiskalizacija_error': handle_fiskalizacija_error,  # auto-retry s exponential backoff
}
```

Integriraj s `core/anomaly_detector.py` — kad detektor nađe anomaliju,
pozovi handler ako postoji. Logiraj rezultat u AnomalyReport.

---

## COMMIT PLAN

```
feat(booking): 24h WA reminder + auto-confirm returning clients
feat(booking): slobodni termini danas — notifikacija vlasniku
feat(ai): FinancialAlert model + financial_guardian_check task
feat(ai): Fenix Cortex SSE feed + dashboard widget
feat(ai): ChurnAction model + weekly churn prevention task
feat(ai): anomaly auto-fix handlers (5 tipova)
chore: CELERY_BEAT_SCHEDULE update (reminderi + guardian)
```

## TESTING

Za svaki task — mini test:
```bash
cd /var/www/fina-connect
venv/bin/python manage.py shell -c "
from appointments.tasks import send_booking_reminders
result = send_booking_reminders()
print('Reminders:', result)
"
```

## PO ZAVRŠETKU

1. `git log --oneline -10`
2. `systemctl restart gunicorn-fina celery-worker celery-beat`
3. `chown -R www-data:www-data logs/`
4. Ažuriraj FENIX_STATUS.md — ŽIVUĆI BORG Tasks → DONE
5. Ažuriraj BORG_ZIVUCI_MANIFEST.md — ocjene stupova

