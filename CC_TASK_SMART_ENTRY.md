# CC_TASK: SMART ENTRY — /pocni/ Jedina ulazna točka
# Datum: 04.04.2026. | Rok: 05.04.2026. | Prioritet: P0
# BLOKIRA: konverziju, Claim flow, distributer invite

PRAVILO: READ models.py PRIJE svakog WRITE.
PRAVILO: base.html, .env NE DIRAS.
PRAVILO: python manage.py check 2>&1 | tail -3 nakon svake migracije.

---

## CILJ

Svaka osoba koja dođe na limit-connect.com završi na /pocni/ ako nije logirana.
Email detect → pravi flow, nema dead enda.

## KORAK 1: Provjeri stanje

```bash
grep -n "pocni\|smart_entry\|SmartEntry" core/urls.py
grep -rn "def pocni\|def smart_entry" --include="*.py" | grep -v venv
cat registration/models.py | grep -n "class\|PromoCode\|UmbrellaInvite" | head -30
```

## KORAK 2: View — /pocni/

KREIRAJ: `registration/smart_entry.py`

```python
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt
import json

def pocni(request):
    """
    Jedina ulazna točka za sve posjetitelje.
    GET  → prikazuje stranicu s email poljem
    POST → detect_email AJAX
    
    Parametri:
      ?ref=REF-MARIJA-2026  → sprema u session, veže uz agenta
      ?pet=Vučko            → personalizirani pozdrav
      ?plan=professional    → predabere plan
    """
    # Ako je već prijavljen, idi na portal
    if request.user.is_authenticated:
        return redirect('/hr/portal/')
    
    # Spremi ref u session
    ref = request.GET.get('ref', '')
    if ref:
        request.session['agent_ref'] = ref
    
    # Pet personalizacija
    pet = request.GET.get('pet', '')
    plan = request.GET.get('plan', '')
    
    context = {
        'pet': pet,
        'plan': plan,
        'ref': ref,
        'page_title': 'Počnite s LIMIT Connect',
    }
    return render(request, 'registration/smart_entry.html', context)


@require_POST
def api_detect_email(request):
    """
    POST /pocni/provjeri/
    Body: {"email": "ivan@firma.hr"}
    
    Odgovor:
      {"status": "new"}         → novi korisnik, ide na registraciju
      {"status": "existing"}    → postoji, šalji magic link
      {"status": "claimed"}     → ima firmu po OIB-u, može preuzeti
      {"status": "rate_limit"}  → previše pokušaja
    """
    try:
        data = json.loads(request.body)
        email = data.get('email', '').strip().lower()
    except Exception:
        return JsonResponse({'status': 'error', 'msg': 'Neispravan zahtjev'}, status=400)
    
    if not email or '@' not in email:
        return JsonResponse({'status': 'error', 'msg': 'Unesite valjanu email adresu'})
    
    # Rate limit check (koristi cache)
    from django.core.cache import cache
    rate_key = f'smart_entry_rate:{request.META.get("REMOTE_ADDR", "")}'
    attempts = cache.get(rate_key, 0)
    if attempts > 10:
        return JsonResponse({
            'status': 'rate_limit',
            'msg': 'Previše pokušaja. Pričekajte 10 minuta.',
            'wait_seconds': 600
        })
    cache.set(rate_key, attempts + 1, timeout=600)
    
    # Provjeri postoji li user
    user = User.objects.filter(email=email).first()
    if user:
        # Pošalji magic link
        _send_magic_link(user, request)
        return JsonResponse({
            'status': 'existing',
            'msg': f'Poslali smo vam link na {email}. Provjerite inbox (i spam).',
            'redirect': None
        })
    
    # Novi korisnik
    ref = request.session.get('agent_ref', '')
    return JsonResponse({
        'status': 'new',
        'msg': 'Dobrodošli! Kreiramo vaš račun.',
        'redirect': f'/hr/register/?email={email}&ref={ref}'
    })


def _send_magic_link(user, request):
    """Šalje one-click login link na email."""
    from django.core.signing import dumps
    from django.core.mail import send_mail
    from django.conf import settings
    
    token = dumps({'user_id': user.pk}, key=settings.SECRET_KEY, salt='magic-login')
    link = request.build_absolute_uri(f'/pocni/magic/{token}/')
    
    send_mail(
        subject='Vaš pristup LIMIT Connect',
        message=f'Kliknite link za ulaz u portal:\n{link}\n\nLink je valjan 24 sata.',
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@limit-connect.com'),
        recipient_list=[user.email],
        fail_silently=True,
    )


def magic_login(request, token):
    """One-click login via signed token."""
    from django.core.signing import loads, BadSignature, SignatureExpired
    from django.contrib.auth import login
    from django.conf import settings
    
    try:
        data = loads(token, key=settings.SECRET_KEY, salt='magic-login', max_age=86400)
        user = User.objects.get(pk=data['user_id'])
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        return redirect('/hr/portal/')
    except (BadSignature, SignatureExpired, User.DoesNotExist):
        return render(request, 'registration/smart_entry.html', {
            'error': 'Link je istekao ili neispravan. Unesite email ponovo.',
        })
```

## KORAK 3: Template — templates/registration/smart_entry.html

BITNO: koristi `{% extends "base.html" %}` i global_themes.css varijable.
Design 10/10: čist, konverzijski, hero CTA.

```html
{% extends "base.html" %}
{% load i18n %}
{% block title %}Počnite — LIMIT Connect{% endblock %}

{% block content %}
<div class="smart-entry-hero">
  
  <!-- Pet personalizacija -->
  {% if pet %}
  <div class="pet-greeting">
    <span class="pet-icon">🐾</span>
    <p>Zdravo! Vaš {{ pet }} čeka na memio.pet 🐾</p>
  </div>
  {% endif %}

  <!-- Hero -->
  <div class="se-hero-text">
    <h1>ERP za male firme.<br><span class="gold">Bez komplikacija.</span></h1>
    <p class="se-subtitle">Fiskalizacija · Računi · Radni sati · POS · Arhiva</p>
    <p class="se-price">Od <strong>9 EUR/mj</strong> — prva 2 tjedna besplatno</p>
  </div>

  <!-- Email forma — GLAVNA CTA -->
  <div class="se-email-box" id="emailBox">
    <div class="se-input-row">
      <input type="email" id="seEmail" placeholder="vasa@firma.hr" 
             autocomplete="email" inputmode="email"
             class="se-input {% if error %}se-error{% endif %}" />
      <button id="seBtn" class="se-btn-gold" onclick="detectEmail()">
        Počnite →
      </button>
    </div>
    {% if error %}
    <p class="se-error-msg">{{ error }}</p>
    {% endif %}
    <p class="se-micro">Bez kreditne kartice. Bez ugovora.</p>
  </div>

  <!-- Status poruka (AJAX fill) -->
  <div id="seStatus" class="se-status" style="display:none;"></div>

  <!-- Social proof -->
  <div class="se-proof">
    <span>✓ 96 firmi</span>
    <span>✓ HR + DE fiskalizacija</span>
    <span>✓ AI u svakom modulu</span>
  </div>

</div>

<style>
.smart-entry-hero {
  min-height: 80vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2rem;
  padding: 2rem 1rem;
  text-align: center;
}
.pet-greeting {
  background: var(--surface-elevated);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: .75rem 1.5rem;
  font-size: .95rem;
}
.se-hero-text h1 {
  font-size: clamp(2rem, 5vw, 3.5rem);
  font-weight: 800;
  line-height: 1.15;
  color: var(--text-primary);
  margin-bottom: .5rem;
}
.gold { color: var(--gold); }
.se-subtitle { color: var(--text-secondary); font-size: 1.1rem; margin-bottom: .25rem; }
.se-price { color: var(--text-primary); font-size: 1rem; }
.se-email-box {
  width: 100%;
  max-width: 520px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 2rem;
  box-shadow: 0 4px 24px rgba(0,0,0,.15);
}
.se-input-row {
  display: flex;
  gap: .5rem;
  margin-bottom: .75rem;
}
.se-input {
  flex: 1;
  padding: .875rem 1rem;
  border: 1.5px solid var(--border);
  border-radius: 10px;
  background: var(--surface-elevated);
  color: var(--text-primary);
  font-size: 1rem;
  outline: none;
  transition: border-color .2s;
}
.se-input:focus { border-color: var(--gold); }
.se-input.se-error { border-color: var(--danger, #e74c3c); }
.se-btn-gold {
  padding: .875rem 1.5rem;
  background: var(--gold);
  color: #000;
  font-weight: 700;
  border: none;
  border-radius: 10px;
  cursor: pointer;
  font-size: 1rem;
  white-space: nowrap;
  transition: opacity .2s;
}
.se-btn-gold:hover { opacity: .88; }
.se-micro { color: var(--text-muted, #888); font-size: .8rem; margin: 0; }
.se-status {
  max-width: 520px;
  width: 100%;
  padding: 1rem 1.5rem;
  border-radius: 12px;
  font-size: .95rem;
  text-align: center;
}
.se-status.success { background: rgba(39,174,96,.15); color: #27ae60; border: 1px solid rgba(39,174,96,.3); }
.se-status.info { background: rgba(201,168,76,.1); color: var(--gold); border: 1px solid rgba(201,168,76,.3); }
.se-status.error { background: rgba(231,76,60,.1); color: #e74c3c; border: 1px solid rgba(231,76,60,.3); }
.se-proof {
  display: flex;
  gap: 1.5rem;
  flex-wrap: wrap;
  justify-content: center;
  color: var(--text-secondary);
  font-size: .85rem;
}
@media (max-width: 480px) {
  .se-input-row { flex-direction: column; }
  .se-btn-gold { width: 100%; }
}
</style>

<script>
async function detectEmail() {
  const email = document.getElementById('seEmail').value.trim();
  const btn = document.getElementById('seBtn');
  const status = document.getElementById('seStatus');
  
  if (!email || !email.includes('@')) {
    showStatus('Unesite valjanu email adresu.', 'error');
    return;
  }
  
  btn.disabled = true;
  btn.textContent = '⏳';
  
  try {
    const res = await fetch('/pocni/provjeri/', {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken')},
      body: JSON.stringify({email})
    });
    const data = await res.json();
    
    if (data.status === 'new') {
      showStatus('✅ ' + data.msg, 'success');
      setTimeout(() => { window.location.href = data.redirect; }, 800);
    } else if (data.status === 'existing') {
      showStatus('📧 ' + data.msg, 'info');
    } else if (data.status === 'rate_limit') {
      showStatus('⏳ ' + data.msg, 'error');
    } else {
      showStatus(data.msg || 'Greška. Pokušajte ponovo.', 'error');
    }
  } catch(e) {
    showStatus('Greška veze. Pokušajte ponovo.', 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Počnite →';
  }
}

function showStatus(msg, type) {
  const el = document.getElementById('seStatus');
  el.textContent = msg;
  el.className = 'se-status ' + type;
  el.style.display = 'block';
}

function getCookie(name) {
  return document.cookie.split(';').map(c => c.trim())
    .find(c => c.startsWith(name + '='))?.split('=')[1] || '';
}

document.getElementById('seEmail').addEventListener('keydown', e => {
  if (e.key === 'Enter') detectEmail();
});
</script>
{% endblock %}
```

## KORAK 4: URL routing

U `core/urls.py`, dodaj UNUTAR urlpatterns (BEZ i18n_patterns — ovo je global URL):

```python
# Smart Entry — globalna ulazna točka
path('pocni/', include([
    path('', __import__('registration.smart_entry', fromlist=['pocni']).pocni, name='smart_entry'),
    path('provjeri/', __import__('registration.smart_entry', fromlist=['api_detect_email']).api_detect_email, name='api_detect_email'),
    path('magic/<str:token>/', __import__('registration.smart_entry', fromlist=['magic_login']).magic_login, name='magic_login'),
])),
```

PROVJERI gdje su ostali globalni URLovi (homepage, /no-limit/, itd.) i stavi u isti blok.

## KORAK 5: Verifikacija

```bash
cd /var/www/fina-connect
python venv/bin/python manage.py check 2>&1 | tail -5
systemctl restart gunicorn-fina
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/pocni/
# Očekivano: 200
```

## DONE kriteriji:
- [ ] /pocni/ vraća 200
- [ ] POST /pocni/provjeri/ vraća JSON s "new" za nepoznati email
- [ ] POST /pocni/provjeri/ šalje magic link za postojeći email
- [ ] Rate limit radi (11+ pokušaja s iste IP → rate_limit)
- [ ] ?pet=Vučko prikazuje personalizirani pozdrav
- [ ] ?ref=REF-X sprema se u session
- [ ] Mobile 100% (flex kolona ispod 480px)
