# CC_TASK_BORG_SIGNAL_FOUNDATION — FenixSignal + Kanali
## Agent: Claude Code | Prioritet: P0 — BORG 10/10
## Datum: 2026-03-24

**Čitaj prvo:** BORG_10_10_MASTER_PLAN.md, FENIX_STATUS.md

---

## KONTEKST

Cilj: korisnici (Šeki via WhatsApp, Marija via in-app gumb) šalju signale direktno
u FENIX bez Ivana kao posrednika. Sve se sprema u FenixSignal arhivu.

Što POSTOJI (ne graditi nanovo):
- WAHA gateway: `core/whatsapp.py` + `settings.WAHA_API_URL` (http://127.0.0.1:3000)
- Postojeći WhatsApp webhook: `api/whatsapp/webhook/` (provjeri što prima)
- `limit_connect_ai` app — tu ide FenixSignal model
- GracefulErrorMiddleware — tu dodati auto-signal hook

---

## ZADATAK 1: FenixSignal model

**Fajl:** `limit_connect_ai/models.py` — dodati na kraj

```python
class FenixSignal(models.Model):
    SOURCE_CHOICES = [
        ('whatsapp', 'WhatsApp'),
        ('inapp', 'In-App gumb'),
        ('auto', 'Auto (greška sustava)'),
        ('pos_pulse', 'POS Pulse'),
        ('celery', 'Celery Task'),
        ('email', 'Email'),
    ]
    SEVERITY_CHOICES = [
        ('critical', '🔴 Kritično'),
        ('high', '🟠 Visoko'),
        ('medium', '🟡 Srednje'),
        ('low', '🟢 Nisko'),
        ('info', '⚪ Info'),
    ]
    CATEGORY_CHOICES = [
        ('bug', 'Bug'),
        ('ux', 'UX problem'),
        ('data', 'Problem s podacima'),
        ('feature', 'Prijedlog'),
        ('question', 'Pitanje'),
        ('anomaly', 'Anomalija'),
        ('performance', 'Performanse'),
    ]
    STATUS_CHOICES = [
        ('new', 'Novo'),
        ('triaged', 'Triage done'),
        ('task_created', 'Task kreiran'),
        ('in_progress', 'U tijeku'),
        ('resolved', 'Riješeno'),
        ('ignored', 'Ignorirano'),
    ]

    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    company = models.ForeignKey('companies.Company', on_delete=models.SET_NULL,
                                 null=True, blank=True, related_name='fenix_signals')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                              null=True, blank=True)
    title = models.CharField(max_length=200)
    body = models.TextField()
    screenshot = models.ImageField(upload_to='fenix_signals/%Y/%m/', null=True, blank=True)
    metadata = models.JSONField(default=dict)
    raw_payload = models.TextField(blank=True)

    # Triage (Patrol popunjava)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, blank=True)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='medium')
    ai_summary = models.TextField(blank=True)
    ai_suggested_action = models.TextField(blank=True)

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    task_file = models.CharField(max_length=200, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_note = models.TextField(blank=True)

    # Feedback
    user_notified = models.BooleanField(default=False)
    notification_sent_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Fenix Signal'
        verbose_name_plural = 'Fenix Signali'

    def __str__(self):
        return f'[{self.get_severity_display()}] {self.title} ({self.source})'
```

Migracija: `venv/bin/python manage.py makemigrations limit_connect_ai && venv/bin/python manage.py migrate`

---

## ZADATAK 2: WhatsApp webhook za Šekija

**Provjeri prvi:** `cat` postojeći WhatsApp webhook u urls.py i views.py.
Ako već prima poruke — nadogradi, ne zamijeni.

**Novi endpoint:** `POST /fenix/signal/whatsapp/`

```python
# limit_connect_ai/views_signal.py — NOVI FAJL

@csrf_exempt
def whatsapp_signal(request):
    """
    WAHA webhook — prima poruke/slike od klijenata.
    WAHA šalje POST s JSON payload-om.
    """
    # WAHA payload format:
    # { "event": "message", "session": "default",
    #   "payload": { "from": "38591XXXXXX@c.us", "body": "tekst",
    #                "hasMedia": true, "mediaUrl": "..." } }

    payload = json.loads(request.body)
    event = payload.get('event', '')

    if event not in ('message', 'message.any'):
        return JsonResponse({'ok': True})  # ignoriraj status events

    msg = payload.get('payload', {})
    phone_raw = msg.get('from', '').replace('@c.us', '').replace('@g.us', '')
    body = msg.get('body', '') or msg.get('caption', '')
    has_media = msg.get('hasMedia', False)
    media_url = msg.get('mediaUrl', '')

    # Pronađi firmu po telefonu (UserProfile.phone ili Company.phone)
    company = _find_company_by_phone(phone_raw)

    # Kreiraj signal
    signal = FenixSignal.objects.create(
        source='whatsapp',
        company=company,
        title=f'WhatsApp: {body[:80]}' if body else 'WhatsApp slika/medij',
        body=body,
        metadata={
            'phone': phone_raw,
            'has_media': has_media,
            'media_url': media_url,
            'waha_payload': payload,
        },
        raw_payload=request.body.decode('utf-8', errors='replace'),
        severity='medium',
        status='new',
    )

    # Ako ima screenshot/sliku — preuzmi i spremi
    if has_media and media_url:
        _fetch_and_attach_media(signal, media_url)

    # Auto-odgovor Šekiju
    from core.whatsapp import send_text
    send_text(phone_raw, f'✅ Fenix primio signal #{signal.pk}. Gledamo.')

    return JsonResponse({'ok': True, 'signal_id': signal.pk})


def _find_company_by_phone(phone):
    """Traži Company po broju telefona kroz UserProfile."""
    from django.contrib.auth import get_user_model
    from accounts.models import UserProfile
    User = get_user_model()

    # Normaliziraj: ukloni +385, 00385 → lokalni format
    digits = re.sub(r'\D', '', phone)

    # Traži kroz profile
    profiles = UserProfile.objects.filter(
        phone__icontains=digits[-8:]  # zadnjih 8 znamenki
    ).select_related('user__userprofile__company')

    for profile in profiles:
        try:
            return profile.company
        except Exception:
            pass
    return None
```

**URL routing:**
```python
# limit_connect_ai/urls.py — dodati:
path('fenix/signal/whatsapp/', views_signal.whatsapp_signal, name='fenix_whatsapp_signal'),
path('fenix/signal/report/', views_signal.inapp_signal, name='fenix_inapp_signal'),
```

**WAHA konfiguracija** — provjeri je li WAHA već konfiguriran za webhook:
```bash
curl http://127.0.0.1:3000/api/sessions/default | python3 -m json.tool | grep -i webhook
```
Ako nije: `curl -X PUT http://127.0.0.1:3000/api/sessions/default -H "Content-Type: application/json" -d '{"webhooks":[{"url":"https://limit-connect.com/fenix/signal/whatsapp/","events":["message"]}]}'`

---

## ZADATAK 3: In-app gumb (Marija + svi logirani korisnici)

**Gdje:** `templates/base.html` — u navigaciji, vidljiv svima

```html
<!-- FENIX SIGNAL GUMB — uvijek dostupan -->
<button class="fenix-signal-btn" onclick="openFenixSignal()"
        title="Prijavi anomaliju Fenixu"
        style="position:fixed; bottom:20px; right:20px; z-index:9999;
               background:#dc3545; color:#fff; border:none; border-radius:50%;
               width:48px; height:48px; font-size:20px; cursor:pointer;
               box-shadow: 0 2px 8px rgba(0,0,0,0.3);">
  🔴
</button>

<div id="fenixSignalModal" style="display:none; position:fixed; inset:0;
     background:rgba(0,0,0,0.5); z-index:10000; align-items:center; justify-content:center;">
  <div style="background:#fff; border-radius:12px; padding:24px; max-width:480px; width:90%;">
    <h3>📡 Prijavi Fenixu</h3>
    <p style="color:#666; font-size:14px;">Anomalija, bug, prijedlog — sve je dobrodošlo.</p>
    <textarea id="fenixSignalBody" placeholder="Što si primijetio/la?" rows="4"
              style="width:100%; border:1px solid #ddd; border-radius:8px; padding:10px;
                     font-size:14px; resize:vertical;"></textarea>
    <div style="margin:10px 0;">
      <input type="file" id="fenixSignalFile" accept="image/*" style="font-size:13px;">
      <label style="font-size:12px; color:#888;">Screenshot (opcionalno)</label>
    </div>
    <div style="display:flex; gap:10px; margin-top:16px;">
      <button onclick="submitFenixSignal()"
              style="flex:1; background:#dc3545; color:#fff; border:none; border-radius:8px;
                     padding:10px; cursor:pointer; font-weight:600;">
        📡 Pošalji Fenixu
      </button>
      <button onclick="closeFenixSignal()"
              style="padding:10px 20px; border:1px solid #ddd; border-radius:8px; cursor:pointer;">
        Odustani
      </button>
    </div>
    <p id="fenixSignalStatus" style="margin-top:10px; font-size:13px; color:#28a745;"></p>
  </div>
</div>

<script>
function openFenixSignal() {
  document.getElementById('fenixSignalModal').style.display = 'flex';
}
function closeFenixSignal() {
  document.getElementById('fenixSignalModal').style.display = 'none';
  document.getElementById('fenixSignalBody').value = '';
  document.getElementById('fenixSignalStatus').textContent = '';
}
async function submitFenixSignal() {
  const body = document.getElementById('fenixSignalBody').value.trim();
  if (!body) { alert('Napiši što si primijetio.'); return; }

  const form = new FormData();
  form.append('body', body);
  form.append('url', window.location.href);
  form.append('csrfmiddlewaretoken', '{{ csrf_token }}');

  const file = document.getElementById('fenixSignalFile').files[0];
  if (file) form.append('screenshot', file);

  const btn = document.querySelector('#fenixSignalModal button');
  btn.textContent = '⏳ Šaljem...';

  const resp = await fetch('/fenix/signal/report/', { method: 'POST', body: form });
  const data = await resp.json();

  document.getElementById('fenixSignalStatus').textContent =
    data.ok ? `✅ Signal #${data.signal_id} primljen. Fenix gleda.` : '❌ Greška. Pokušaj ponovo.';
  btn.textContent = '📡 Pošalji Fenixu';
  setTimeout(closeFenixSignal, 2000);
}
</script>
```

**View za in-app signal:**
```python
@login_required
def inapp_signal(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)

    body = request.POST.get('body', '').strip()
    url = request.POST.get('url', '')
    screenshot = request.FILES.get('screenshot')

    company = getattr(request, 'current_company', None) or \
              getattr(getattr(request.user, 'userprofile', None), 'company', None)

    signal = FenixSignal.objects.create(
        source='inapp',
        company=company,
        user=request.user,
        title=f'{request.user.get_full_name() or request.user.username}: {body[:80]}',
        body=body,
        screenshot=screenshot,
        metadata={'url': url, 'user_agent': request.META.get('HTTP_USER_AGENT', '')},
        status='new',
        severity='medium',
    )

    return JsonResponse({'ok': True, 'signal_id': signal.pk})
```

---

## ZADATAK 4: Auto-signal iz GracefulErrorMiddleware

U `core/middleware/__init__.py`, u `GracefulErrorMiddleware.process_exception()`,
nakon logiranja, dodati:

```python
# Auto FenixSignal za svaku produkcijsku grešku
try:
    from limit_connect_ai.models import FenixSignal
    FenixSignal.objects.create(
        source='auto',
        company=getattr(getattr(request, 'current_company', None), None, None),
        user=request.user if request.user.is_authenticated else None,
        title=f'Auto: {type(exception).__name__} na {request.path}',
        body=traceback_str[:2000],
        metadata={
            'path': request.path,
            'method': request.method,
            'exception_type': type(exception).__name__,
        },
        severity='high',
        status='new',
    )
except Exception:
    pass  # nikad ne blokiraj error handler
```

---

## ZADATAK 5: Migrate + test

```bash
cd /var/www/fina-connect
venv/bin/python manage.py makemigrations limit_connect_ai
venv/bin/python manage.py migrate

# Test: kreiraj testni signal direktno
venv/bin/python -c "
import os; os.environ['DJANGO_SETTINGS_MODULE']='core.settings'
import django; django.setup()
from limit_connect_ai.models import FenixSignal
s = FenixSignal.objects.create(
    source='inapp', title='TEST signal', body='Ovo je test', severity='low', status='new'
)
print(f'Signal kreiran: #{s.pk} | {s}')
"
```

---

## COMMIT

```
git add limit_connect_ai/ templates/base.html core/middleware/__init__.py
git commit -m "feat(borg): FenixSignal foundation — WhatsApp + in-app + auto-signal channels"
```

---

## DEFINICIJA DONE

- [ ] FenixSignal model + migration
- [ ] WhatsApp webhook `/fenix/signal/whatsapp/` prima WAHA payload
- [ ] In-app 🔴 gumb u bazi (base.html) — vidljiv svim logiranim korisnicima
- [ ] GracefulErrorMiddleware kreira auto-signal za svaku 500 grešku
- [ ] Test: 3 signala kreirana (whatsapp, inapp, auto)
- [ ] WAHA webhook konfiguriran na limit-connect.com URL
