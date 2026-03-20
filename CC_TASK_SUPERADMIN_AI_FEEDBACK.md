# CC Task — Superadmin AI: feedback loop od testera

## Kontekst
Ponedjeljak dolaze pravi testeri: Marija (60+ komitenata), Korpaš, Šeki.
Kad nalete na problem — trebaju imati gumb "Prijavi problem" koji odmah
stiže u superadmin_ai dashboard. Trenutno taj gumb ne postoji.

## Što postoji (provjeri sve ovo PRVO)
```bash
cat /var/www/fina-connect/superadmin_ai/views.py | grep -A20 "def submit_request"
cat /var/www/fina-connect/superadmin_ai/urls.py
ls /var/www/fina-connect/templates/superadmin_ai/
cat /var/www/fina-connect/templates/superadmin_ai/dashboard.html | head -50
```

## Zadatak — 3 stvari

### 1. Floating feedback gumb u base.html
U `/var/www/fina-connect/templates/base.html`, prije `</body>`, dodaj:
```html
<!-- Feedback gumb — vidljiv svim prijavljenim korisnicima, ne superadminu -->
{% if user.is_authenticated and not user.is_superuser %}
<div id="feedback-btn" style="position:fixed;bottom:20px;right:20px;z-index:9999;">
  <button onclick="document.getElementById('feedback-modal').style.display='flex'"
          style="background:#c9a84c;color:#000;border:none;border-radius:50%;
                 width:48px;height:48px;font-size:22px;cursor:pointer;
                 box-shadow:0 2px 8px rgba(0,0,0,0.4);" title="Prijavi problem">
    ⚠️
  </button>
</div>
<div id="feedback-modal" style="display:none;position:fixed;inset:0;
     background:rgba(0,0,0,0.7);z-index:10000;align-items:center;justify-content:center;">
  <div style="background:#1a1a1a;border:1px solid #c9a84c;padding:24px;
              border-radius:8px;max-width:420px;width:90%;">
    <h3 style="color:#c9a84c;margin:0 0 12px;">Prijavi problem</h3>
    <textarea id="feedback-text" rows="4" placeholder="Opiši što ne radi..."
              style="width:100%;background:#111;color:#fff;border:1px solid #444;
                     padding:8px;border-radius:4px;resize:vertical;"></textarea>
    <div style="margin-top:12px;display:flex;gap:8px;justify-content:flex-end;">
      <button onclick="document.getElementById('feedback-modal').style.display='none'"
              style="background:#333;color:#fff;border:none;padding:8px 16px;
                     border-radius:4px;cursor:pointer;">Odustani</button>
      <button onclick="submitFeedback()"
              style="background:#c9a84c;color:#000;border:none;padding:8px 16px;
                     border-radius:4px;cursor:pointer;font-weight:bold;">Pošalji</button>
    </div>
    <div id="feedback-status" style="margin-top:8px;font-size:13px;color:#aaa;"></div>
  </div>
</div>
<script>
function submitFeedback() {
  const text = document.getElementById('feedback-text').value.trim();
  if (!text) return;
  document.getElementById('feedback-status').textContent = 'Šaljem...';
  fetch('/superadmin/ai/api/submit-request/', {
    method: 'POST',
    headers: {'Content-Type':'application/json','X-CSRFToken': '{{ csrf_token }}'},
    body: JSON.stringify({description: text, module: window.location.pathname, priority: 2})
  }).then(r => r.json()).then(d => {
    if (d.ok || d.id) {
      document.getElementById('feedback-status').textContent = '✅ Prijavljeno, hvala!';
      document.getElementById('feedback-text').value = '';
      setTimeout(() => { document.getElementById('feedback-modal').style.display='none'; }, 1500);
    } else {
      document.getElementById('feedback-status').textContent = '❌ Greška: ' + (d.error || 'pokušaj ponovo');
    }
  }).catch(() => {
    document.getElementById('feedback-status').textContent = '❌ Server nije odgovorio';
  });
}
</script>
{% endif %}
```

### 2. Provjeri submit_request view
U `superadmin_ai/views.py`, funkcija `submit_request` — provjeri prima li
`description`, `module`, `priority` iz JSON body-a. Ako ne prima JSON
(samo form POST) — dodaj JSON parsing:
```python
import json as json_lib
if request.content_type == 'application/json':
    data = json_lib.loads(request.body)
else:
    data = request.POST
```

### 3. Test
```bash
cd /var/www/fina-connect && venv/bin/python manage.py check 2>&1 | tail -2
systemctl reload gunicorn-fina || systemctl restart gunicorn-fina
curl -s -o /dev/null -w "%{http_code}" https://limit-connect.com/hr/accounts/login/
```

## PRAVILA
- Čitaj base.html CIJELI prije dodavanja (backup: base.html.bak)
- Ne diraj JS koji već postoji u base.html
- Ako submit_request ne postoji ili backa 404 — javi Ivanu, ne patch
