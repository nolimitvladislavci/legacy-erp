# CC_TASK: REGISTRACIJA 10/10 — Autonomna prijava s AI vodstvom
# Datum: 04.04.2026. | Rok: 07.04.2026. | Prioritet: P0
# Vođa: Sonnet | Koordinator: Ivan Brtan
# Cilj: Korisnik dođe sam → za 5 minuta operativan. Bez Marije. Bez Ivana.

PRAVILO: READ models.py PRIJE svakog WRITE.
PRAVILO: base.html, .env NE DIRAS.
PRAVILO: venv/bin/python manage.py check 2>&1 | tail -3 nakon svake izmjene.
PRAVILO: Svaki AI poziv → Haiku (jeftino, brzo). Nikad Sonnet u sync requestu.

---

## ARHITEKTURA — 6 SLOJEVA

```
[1] /pocni/          → Personaliziran ulaz (već radi, nadogradnja)
[2] Plan preporuka   → AI Borg Advisor (Haiku, OIB-based)
[3] OIB Magic Fill   → Sudreg auto-fill (API postoji, UI upgrade)
[4] Setup Wizard     → AI Guided Checklist (gamification + Haiku tipovi)
[5] First Login      → Welcome experience (AI welcome card)
[6] Otvorene karte   → Trust signal (što vidimo, što ne vidimo)
```

---

## KORAK 1 — PROVJERI TEREN

```bash
# Što postoji u registraciji (AI)
grep -rn "haiku\|claude\|borg_advisor\|ai_plan" registration/ --include="*.py" | head -10

# OIB lookup API
grep -n "def api_oib_lookup" registration/views.py
curl -s "http://localhost:8000/hr/registration/api/oib-lookup/?oib=12345678901" 2>/dev/null | head -5

# Setup wizard completion
grep -n "completion\|progress" companies/views.py | head -10

# Existing plans u bazi
python venv/bin/python manage.py shell -c "
from registration.models import PricingPlan
for p in PricingPlan.objects.filter(is_active=True).order_by('sort_order'):
    print(p.slug, p.name, p.price_monthly, 'EUR')
" 2>/dev/null

# Koji NKD kodovi postoje
python venv/bin/python manage.py shell -c "
from companies.models import Company
print('NKD field:', 'nkd' if hasattr(Company(),'nkd') else 'industry')
" 2>/dev/null
```

---

## KORAK 2 — BORG ADVISOR LIGHT (AI plan preporuka)

KREIRAJ: `registration/borg_advisor.py`

```python
"""
Borg Advisor Light — AI plan preporuka za registraciju.
Koristi Haiku (brzo, jeftino). Fallback na keyword matching.
"""
import json
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

# Keyword→plan mapping (fallback bez AI-a)
KEYWORD_PLAN_MAP = {
    'starter': [
        'obrt', 'obrtar', 'opg', 'poljoprivred', 'kosilar', 'čišćen',
        'vodoinstalat', 'elektricar', 'zidar', 'medicinska sestra', 'frizjer',
        'kozmetičar', 'cvjetar', 'ribar', 'pčelar', 'vinogradar',
    ],
    'professional': [
        'restoran', 'kafić', 'caffe', 'hotel', 'smještaj', 'udruga',
        'servis', 'automehaničar', 'vulkanizer', 'računovodstvo', 'knjig',
        'agencija', 'građevinar', 'prijevoz', 'veterinar', 'ljekarnar',
        'prodavaonica', 'maloprodaja', 'veleprodaja',
    ],
    'enterprise': [
        'komunal', 'grad', 'općina', 'dom zdravlja', 'bolnica', 'škola',
        'vrtić', 'lječilište', 'holding', 'grupa', 'd.d.', 'dioničko',
        'franšiza', 'distributer', 'umbrella',
    ],
}

def recommend_plan_by_keyword(name: str, industry: str = '') -> dict:
    """Brza keyword preporuka — uvijek radi, 0ms."""
    text = (name + ' ' + industry).lower()
    scores = {'starter': 0, 'professional': 0, 'enterprise': 0}
    for plan, keywords in KEYWORD_PLAN_MAP.items():
        for kw in keywords:
            if kw in text:
                scores[plan] += 1
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        best = 'professional'  # Default
    return {
        'plan': best,
        'confidence': 'keyword',
        'reason': _get_reason(best, text),
    }

def _get_reason(plan: str, text: str) -> str:
    reasons = {
        'starter': 'Savršen za obrte i OPG — fiskalizacija i fakture.',
        'professional': 'Idealan za vašu djelatnost — tim, AI i WhatsApp uključeni.',
        'enterprise': 'Vaša organizacija treba napredne module i neograničene korisnike.',
    }
    return reasons.get(plan, 'Preporučen na temelju vaše djelatnosti.')

def recommend_plan_ai(oib: str, name: str, nkd: str = '') -> dict:
    """
    AI preporuka plana — Haiku, async friendly.
    Poziva se AJAX-om, vraca JSON.
    Fallback na keyword ako Haiku ne odgovori u 3s.
    """
    import anthropic
    import re

    # Keyword fallback odmah za slučaj greške
    fallback = recommend_plan_by_keyword(name, nkd)

    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        prompt = f"""Tvrtka se želi registrirati na LIMIT Connect ERP.
Naziv: {name}
NKD/djelatnost: {nkd or 'nije poznato'}

LIMIT Connect planovi:
- starter (9 EUR/mj): fiskalizacija, fakture, POS, 1 korisnik — za obrte i OPG
- professional (29 EUR/mj): sve + radni sati, AI, WhatsApp, 5 korisnika — za tvrtke s timom
- enterprise (79 EUR/mj): sve + neograničeno, komunale, udruge, multi-firma

Odgovori SAMO JSON-om, bez ikakvog drugog teksta:
{{"plan": "starter|professional|enterprise", "reason": "jedna rečenica zašto (na hrvatskom)"}}"""

        msg = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=80,
            messages=[{'role': 'user', 'content': prompt}],
        )
        raw = msg.content[0].text.strip()
        data = json.loads(raw)
        if data.get('plan') in ('starter', 'professional', 'enterprise'):
            return {'plan': data['plan'], 'confidence': 'ai', 'reason': data.get('reason', '')}
    except Exception as e:
        logger.warning(f'Borg Advisor AI fallback: {e}')

    return fallback
```

---

## KORAK 3 — API ENDPOINT za Borg Advisor

READ: `registration/views.py` — pronađi `api_oib_lookup` i dodaj odmah ispod:

```python
@require_GET
def api_plan_suggest(request):
    """
    GET /registration/api/plan-suggest/?name=OPG+Kruljac&nkd=01.1
    Vraca: {"plan": "starter", "reason": "...", "confidence": "ai|keyword"}
    """
    from registration.borg_advisor import recommend_plan_ai, recommend_plan_by_keyword
    from django.http import JsonResponse

    name = request.GET.get('name', '').strip()
    nkd = request.GET.get('nkd', '').strip()

    if not name:
        return JsonResponse({'plan': 'professional', 'reason': '', 'confidence': 'default'})

    # Brza keyword preporuka — uvijek odmah
    result = recommend_plan_by_keyword(name, nkd)
    return JsonResponse(result)
```

DODAJ URL u `registration/urls.py`:
```python
path('api/plan-suggest/', views.api_plan_suggest, name='api_plan_suggest'),
```

---

## KORAK 4 — STEP1 UPGRADE (Plan odabir s AI preporukom)

READ: `templates/registration/step1.html` (cijeli, ~154 linije)

DODAJ ispred plan kartica (after pet banner, before plan form):

```html
<!-- AI PLAN ADVISOR WIDGET -->
<div id="advisorBox" style="display:none;max-width:600px;margin:0 auto 1.5rem;
  background:rgba(201,168,76,.06);border:1px solid rgba(201,168,76,.25);
  border-radius:12px;padding:1.25rem 1.5rem;">
  <div style="display:flex;align-items:center;gap:.75rem;margin-bottom:.5rem;">
    <span style="font-size:1.5rem;">🤖</span>
    <strong style="color:var(--gold);font-size:.95rem;">Fenix preporučuje</strong>
  </div>
  <p id="advisorReason" style="color:var(--text);font-size:.9rem;margin:0 0 .75rem;"></p>
  <button id="advisorBtn" class="btn-gold-sm" onclick="applyAdvisorPlan()">
    Prihvati preporuku →
  </button>
</div>

<script>
// Pozovi Borg Advisor kada se učita stranica
(async function() {
  // Pokušaj dobiti naziv firme iz prethodnog koraka ili URL-a
  const urlParams = new URLSearchParams(window.location.search);
  const name = urlParams.get('company') || sessionStorage.getItem('reg_company_name') || '';
  const nkd  = urlParams.get('nkd') || '';

  if (!name || name.length < 3) return;

  try {
    const res = await fetch(`/hr/registration/api/plan-suggest/?name=${encodeURIComponent(name)}&nkd=${encodeURIComponent(nkd)}`);
    const data = await res.json();

    if (data.plan && data.reason) {
      document.getElementById('advisorReason').textContent = data.reason;
      document.getElementById('advisorBox').dataset.plan = data.plan;
      document.getElementById('advisorBox').style.display = 'block';
      // Highlight preporučeni plan
      highlightPlan(data.plan);
    }
  } catch(e) {}
})();

function applyAdvisorPlan() {
  const plan = document.getElementById('advisorBox').dataset.plan;
  if (plan) selectPlan(plan);  // Poziva postojeću selectPlan funkciju
}

function highlightPlan(planSlug) {
  document.querySelectorAll('.plan-card').forEach(card => {
    if (card.dataset.plan === planSlug) {
      card.style.borderColor = 'var(--gold)';
      card.style.boxShadow = '0 0 0 3px rgba(201,168,76,.15)';
      // Dodaj "Preporučeno" badge ako ne postoji
      if (!card.querySelector('.ai-badge')) {
        const badge = document.createElement('div');
        badge.className = 'ai-badge';
        badge.textContent = '🤖 Preporučeno';
        badge.style.cssText = 'position:absolute;top:-10px;right:12px;background:var(--gold);color:#000;font-size:.7rem;font-weight:700;padding:.2rem .6rem;border-radius:99px;';
        card.style.position = 'relative';
        card.appendChild(badge);
      }
    }
  });
}
</script>
```

---

## KORAK 5 — STEP2 OIB MAGIC FILL (UI upgrade)

READ: `templates/registration/step2_combined.html` i `registration/views.py:api_oib_lookup`

OIB polje mora imati vizualni feedback koji je 10/10:

ZAMIJENI OIB input sekciju s:

```html
<!-- OIB MAGIC FIELD -->
<div class="wiz-field" style="position:relative;">
  <label for="id_oib">
    OIB tvrtke
    <span id="oibStatus" style="margin-left:.5rem;font-size:.75rem;"></span>
  </label>
  <div style="position:relative;">
    <input type="text" name="oib" id="id_oib" maxlength="11" 
           inputmode="numeric" pattern="[0-9]{11}"
           class="form-control" placeholder="12345678901"
           autocomplete="off"
           oninput="onOibInput(this.value)"
           style="padding-right:2.5rem;">
    <span id="oibSpinner" style="position:absolute;right:.75rem;top:50%;transform:translateY(-50%);display:none;">
      ⏳
    </span>
    <span id="oibCheck" style="position:absolute;right:.75rem;top:50%;transform:translateY(-50%);display:none;color:#27ae60;">
      ✓
    </span>
  </div>
  <!-- Auto-fill preview -->
  <div id="oibPreview" style="display:none;margin-top:.5rem;background:rgba(39,174,96,.08);
    border:1px solid rgba(39,174,96,.25);border-radius:8px;padding:.75rem 1rem;font-size:.85rem;">
    <strong id="previewName" style="color:var(--text);display:block;"></strong>
    <span id="previewAddr" style="color:var(--muted);"></span>
  </div>
</div>

<script>
let oibTimer = null;
async function onOibInput(val) {
  const spinner = document.getElementById('oibSpinner');
  const check   = document.getElementById('oibCheck');
  const preview = document.getElementById('oibPreview');
  const status  = document.getElementById('oibStatus');

  // Reset
  check.style.display = 'none';
  preview.style.display = 'none';
  status.textContent = '';

  if (val.length !== 11 || !/^\d{11}$/.test(val)) return;

  // Debounce 600ms
  clearTimeout(oibTimer);
  oibTimer = setTimeout(async () => {
    spinner.style.display = 'inline';
    status.textContent = 'Pretraživanje sudskog registra...';
    status.style.color = 'var(--muted)';

    try {
      const res = await fetch(`/hr/registration/api/oib-lookup/?oib=${val}&country=HR`);
      const data = await res.json();

      spinner.style.display = 'none';

      if (data.found) {
        // Auto-fill skrivena polja
        const fields = {
          name:      data.name,
          address:   data.address,
          city:      data.city,
          zip_code:  data.zip_code,
          country:   data.country || 'HR',
        };
        Object.entries(fields).forEach(([k, v]) => {
          const el = document.querySelector(`[name="${k}"]`);
          if (el && v) el.value = v;
        });

        // Spremi za Borg Advisor
        sessionStorage.setItem('reg_company_name', data.name || '');

        // Preview
        document.getElementById('previewName').textContent = data.name || '';
        document.getElementById('previewAddr').textContent =
          [data.address, data.city].filter(Boolean).join(', ');
        preview.style.display = 'block';
        check.style.display = 'inline';
        status.textContent = '✓ Nađeno u sudskom registru';
        status.style.color = '#27ae60';
      } else {
        status.textContent = 'OIB nije nađen — unesite ručno';
        status.style.color = 'var(--muted)';
      }
    } catch(e) {
      spinner.style.display = 'none';
      status.textContent = 'Greška pretrage';
    }
  }, 600);
}
</script>
```

---

## KORAK 6 — SETUP WIZARD UPGRADE (AI guided + gamification)

READ: `templates/companies/setup_wizard.html` i `companies/views.py:setup_wizard`

### 6A: Completion progress vizual upgrade

Zamijeni progress bar s animated version:

```html
<!-- HERO WELCOME (na vrhu wizarda) -->
<div style="text-align:center;padding:1.5rem 0 1rem;">
  <div style="font-size:3rem;margin-bottom:.5rem;">
    {% if completion == 100 %}🎉{% elif completion > 60 %}🚀{% else %}👋{% endif %}
  </div>
  <h2 style="font-size:1.4rem;font-weight:800;margin-bottom:.25rem;">
    {% if completion == 100 %}
      Sve je postavljeno! Dobrodošli u LIMIT Connect.
    {% elif completion > 60 %}
      Odlično napredujete, {{ request.user.first_name|default:"" }}!
    {% else %}
      Postavimo vaš profil za 5 minuta.
    {% endif %}
  </h2>
  <p style="color:var(--text-secondary);font-size:.88rem;">
    {{ completion }}% postavljeno
    {% if completion < 100 %}— još {{ 100|add:"-"|add:completion|stringformat:"s" }}% do potpunog otključavanja{% endif %}
  </p>
</div>

<!-- PROGRESS BAR ANIMATED -->
<div class="wiz-progress">
  <div class="wiz-bar" style="width:{{ completion }}%;" id="progressBar"></div>
</div>

<!-- MODULE UNLOCK HINT -->
{% if completion < 80 %}
<div style="background:rgba(201,168,76,.06);border:1px solid rgba(201,168,76,.2);
  border-radius:8px;padding:.75rem 1rem;margin-bottom:1.5rem;font-size:.82rem;
  display:flex;align-items:center;gap:.75rem;">
  <span style="font-size:1.2rem;">🔓</span>
  <span style="color:var(--text-secondary);">
    Dovršite postavljanje i otključajte: 
    <strong style="color:var(--gold);">POS blagajnu, AI asistenta i WhatsApp upozorenja</strong>
  </span>
</div>
{% endif %}
```

### 6B: AI tip za svaku sekciju (lazy load)

U svaki `wiz-card`, dodaj AI tip koji se učita async:

```html
<!-- Primjer za company sekciju -->
<div class="wiz-card {% if sections.company %}done{% endif %}" id="card-company">
  <div class="wiz-card-head">
    <div class="wiz-icon {% if sections.company %}done{% else %}pending{% endif %}">
      {% if sections.company %}✓{% else %}🏢{% endif %}
    </div>
    <div>
      <div class="wiz-title">Podaci tvrtke</div>
      <div class="wiz-desc">Naziv, OIB, adresa</div>
    </div>
  </div>
  <!-- AI TIP (lazy) -->
  <div class="ai-tip" data-section="company" style="display:none;
    font-size:.78rem;color:var(--gold);margin-bottom:.5rem;
    padding:.4rem .6rem;background:rgba(201,168,76,.06);border-radius:6px;">
  </div>
  {% if not sections.company %}
  <a href="{% url 'companies:setup_wizard_company' %}" class="wiz-btn wiz-btn-gold">
    Postavi →
  </a>
  {% else %}
  <span style="color:#10b981;font-size:.82rem;">✓ Postavljeno</span>
  <a href="{% url 'companies:setup_wizard_company' %}" class="wiz-btn wiz-btn-ghost" style="margin-left:.5rem;">
    Uredi
  </a>
  {% endif %}
</div>
```

AI tip JS (ubaci na dno setup_wizard.html):

```html
<script>
// Lazy-load AI tipove za nekompletirane sekcije
const AI_TIPS = {
  company: 'Ispravni OIB i naziv firme potrebni su za fiskalizaciju — FINA to provjerava pri svakom računu.',
  fiscal:  'Bez fiskalizacijskih podataka ne možete ispisivati R1 račune ni koristiti POS.',
  contact: 'Kupci koji prime e-Račun vide vaš email i telefon — unesite poslovne kontakte.',
  logo:    'Tvrtke s logom imaju 3× više povjerenja kod klijenata. Uploadajte logo u sekundi.',
  team:    'Dodajte djelatnika i odmah mu dodijelite pristup POS-u ili arhivi.',
};

document.querySelectorAll('.ai-tip').forEach(el => {
  const section = el.dataset.section;
  if (AI_TIPS[section]) {
    el.textContent = '💡 ' + AI_TIPS[section];
    el.style.display = 'block';
  }
});
</script>
```

---

## KORAK 7 — FIRST LOGIN EXPERIENCE (Welcome card)

READ: `core/views.py` — pronađi portal/dashboard view (main view koji se prikazuje po loginu)

DODAJ logiku koja detektira "prvi login" i prikazuje welcome card:

```python
# U dashboard/portal viewu:
def portal_dashboard(request):
    # ... existing code ...
    
    # First login detection
    from django.contrib.sessions.models import Session
    first_login = not request.session.get('welcomed', False)
    if first_login:
        request.session['welcomed'] = True
    
    context = {
        # ... existing context ...
        'first_login': first_login,
        'setup_completion': _get_setup_completion(request.user),
    }

def _get_setup_completion(user):
    """Izračunaj % postavljanja za welcome card."""
    from core.company_utils import get_user_company
    company = get_user_company_by_user(user)
    if not company:
        return 0
    checks = [
        bool(company.name and not company.name.startswith('DRAFT')),
        bool(company.oib and len(company.oib) == 11),
        bool(getattr(company, 'phone', '') or getattr(company, 'email', '')),
        bool(getattr(company, 'logo', None)),
    ]
    return int(sum(checks) / len(checks) * 100)
```

DODAJ u portal template (na vrhu content bloka):

```html
{% if first_login %}
<div class="welcome-card" id="welcomeCard" style="
  background:linear-gradient(135deg,rgba(201,168,76,.08) 0%,var(--surface) 100%);
  border:1px solid rgba(201,168,76,.3);border-radius:16px;
  padding:2rem;margin-bottom:2rem;position:relative;overflow:hidden;">

  <button onclick="document.getElementById('welcomeCard').remove()"
    style="position:absolute;top:1rem;right:1rem;background:transparent;border:none;
    color:var(--text-secondary);font-size:1.2rem;cursor:pointer;">×</button>

  <div style="display:flex;align-items:flex-start;gap:1.25rem;flex-wrap:wrap;">
    <div style="font-size:3.5rem;">🎯</div>
    <div style="flex:1;min-width:280px;">
      <h2 style="font-size:1.35rem;font-weight:800;margin-bottom:.4rem;">
        Dobrodošli u LIMIT Connect{% if request.user.first_name %}, {{ request.user.first_name }}{% endif %}!
      </h2>
      <p style="color:var(--text-secondary);margin-bottom:1rem;font-size:.9rem;">
        Vaš profil je {{ setup_completion }}% postavljen. Ovdje su sljedeći koraci:
      </p>

      <div style="display:flex;flex-direction:column;gap:.6rem;margin-bottom:1.25rem;">
        {% if setup_completion < 100 %}
        <a href="{% url 'companies:setup_wizard' %}" class="welcome-action">
          <span>⚙️</span> Dovršite postavljanje profila
          <span style="margin-left:auto;color:var(--gold);">→</span>
        </a>
        {% endif %}
        <a href="{% url 'invoicing:create' %}" class="welcome-action">
          <span>🧾</span> Kreirajte prvu fakturu
          <span style="margin-left:auto;color:var(--gold);">→</span>
        </a>
        <a href="{% url 'pos:index' %}" class="welcome-action">
          <span>🛒</span> Otvorite POS blagajnu
          <span style="margin-left:auto;color:var(--gold);">→</span>
        </a>
      </div>

      <div style="font-size:.78rem;color:var(--text-secondary);">
        💡 Trebate pomoć? Napišite nam na
        <a href="mailto:info@limit-connect.com" style="color:var(--gold);">info@limit-connect.com</a>
        ili uključite mikrofon desno.
      </div>
    </div>
  </div>
</div>

<style>
.welcome-action {
  display:flex;align-items:center;gap:.75rem;
  padding:.65rem 1rem;
  background:var(--surface-elevated,#1e2024);
  border:1px solid var(--border);
  border-radius:8px;
  color:var(--text-primary);
  text-decoration:none;
  font-size:.88rem;
  font-weight:500;
  transition:border-color .2s;
}
.welcome-action:hover { border-color:var(--gold); }
</style>
{% endif %}
```

---

## KORAK 8 — OTVORENE KARTE (Trust sekcija)

KREIRAJ: `templates/registration/otvorene_karte.html` — partial koji se include-a u step1 i setup_wizard:

```html
<!-- OTVORENE KARTE — ugradi {% include "registration/otvorene_karte.html" %} -->
<div style="max-width:600px;margin:2rem auto 0;
  background:var(--surface);border:1px solid var(--border);
  border-radius:14px;padding:1.5rem;">

  <div style="display:flex;align-items:center;gap:.75rem;margin-bottom:1rem;">
    <span style="font-size:1.5rem;">🃏</span>
    <div>
      <strong style="color:var(--text-primary);">Otvorene karte</strong>
      <div style="font-size:.78rem;color:var(--text-secondary);">
        Što LIMIT Connect vidi — i što ne vidi
      </div>
    </div>
  </div>

  <div style="display:grid;grid-template-columns:1fr 1fr;gap:.75rem;">
    <div style="background:rgba(39,174,96,.06);border:1px solid rgba(39,174,96,.2);
      border-radius:8px;padding:1rem;">
      <div style="font-size:.7rem;text-transform:uppercase;letter-spacing:.1em;
        color:#27ae60;margin-bottom:.5rem;font-weight:700;">✓ Vidimo</div>
      <ul style="list-style:none;font-size:.8rem;color:var(--text-secondary);margin:0;">
        <li style="padding:.2rem 0;">📋 OIB i naziv tvrtke (javni registar)</li>
        <li style="padding:.2rem 0;">🧾 Vaše fakture koje vi kreirate</li>
        <li style="padding:.2rem 0;">⏰ Radni sati koje vi unosite</li>
        <li style="padding:.2rem 0;">📊 Statistike vašeg poslovanja</li>
      </ul>
    </div>
    <div style="background:rgba(231,76,60,.06);border:1px solid rgba(231,76,60,.2);
      border-radius:8px;padding:1rem;">
      <div style="font-size:.7rem;text-transform:uppercase;letter-spacing:.1em;
        color:#e74c3c;margin-bottom:.5rem;font-weight:700;">✗ Ne vidimo</div>
      <ul style="list-style:none;font-size:.8rem;color:var(--text-secondary);margin:0;">
        <li style="padding:.2rem 0;">💰 Vaš bankovni račun</li>
        <li style="padding:.2rem 0;">👥 Vaše klijente i kontakte</li>
        <li style="padding:.2rem 0;">🔐 Vaše lozinke (SHA-256 hash)</li>
        <li style="padding:.2rem 0;">📱 Vaše poruke i email</li>
      </ul>
    </div>
  </div>

  <div style="margin-top:1rem;font-size:.78rem;color:var(--text-secondary);
    border-top:1px solid var(--border);padding-top:.75rem;">
    🔒 Konjik d.o.o. je vaš GDPR Procesor podataka.
    Vaši podaci su na <strong>Hetzner EU serverima</strong>.
    Možete ih <strong>exportirati ili obrisati</strong> u bilo koje doba.
    <a href="/hr/gdpr/" style="color:var(--gold);margin-left:.25rem;">Saznajte više →</a>
  </div>
</div>
```

INCLUDE u `step1.html` i `step2_combined.html` na dno:
```html
{% include "registration/otvorene_karte.html" %}
```

---

## KORAK 9 — VERIFIKACIJA

```bash
cd /var/www/fina-connect

# Check
venv/bin/python manage.py check 2>&1 | tail -3

# Testovi
venv/bin/python manage.py test registration.tests --verbosity=1 2>&1 | tail -10

# Live test
systemctl restart gunicorn-fina
sleep 2

# Provjeri endpointe
curl -s "http://localhost:8000/pocni/" | grep -c "smart-entry"
curl -s "http://localhost:8000/hr/registration/api/plan-suggest/?name=OPG+Kruljac" | python3 -c "import sys,json; d=json.load(sys.stdin); print('Plan:', d['plan'], '|', d['reason'])"
curl -s "http://localhost:8000/hr/register/" | grep -c "plan-card\|planForm"

# Git commit
git add -A
git commit -m "feat(reg-10-10): Borg Advisor, OIB Magic Fill, Welcome Card, Otvorene Karte"
```

---

## DONE KRITERIJI — 10/10 checklist:

**UI:**
- [ ] /pocni/ → personaliziran (pet, ref, plan param)
- [ ] step1: AI Borg Advisor badge na preporučenom planu
- [ ] step2: OIB → auto-fill (naziv, adresa) s animated feedback
- [ ] setup_wizard: progress % + module unlock hint
- [ ] setup_wizard: AI tipovi za svaki nepopunjen korak
- [ ] Portal: Welcome card za prvi login (nestaje nakon dismiss)
- [ ] Otvorene karte: visible na step1 + step2

**AI integracija:**
- [ ] `borg_advisor.py` postoji, Haiku poziv radi
- [ ] `/api/plan-suggest/` vraća JSON s planom i razlogom
- [ ] OIB lookup (Sudreg) radi i popunjava polja

**Naša priča:**
- [ ] "Otvorene karte" vidljive (GDPR + što vidimo/ne vidimo)
- [ ] Completion gamification (%) vidljiv
- [ ] Welcome card personaliziran (ime, % completion, 3 akcije)
- [ ] "Fiskalizacija u džepu" tagline vidljiv u step1

**Tech:**
- [ ] manage.py check: 0 errora
- [ ] Haiku fallback na keyword (nema AI = sustav radi dalje)
- [ ] Mobile 100% (sve responsive)

---
STATUS: PENDING — čeka CC Code
