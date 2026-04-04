# CC_TASK_BORG_REGISTRATION — BORG Prepoznaje Tko Se Registrira
## Agent: Claude Code | Prioritet: P0 | Revenue direktan
## Datum: 2026-03-24

**Čitaj prvo:** FENIX_STATUS.md, registration/constants.py, registration/models.py, registration/views.py

---

## STANJE DANAS (što je BROKEN)

```
BUSINESS_TYPES u CompanyRegistration:
  doo, jdoo, obrt, dd, sp, eu, other   ← nema: udruga, zadruga, opg, gmbh

PLAN_CHOICES u CompanyRegistration:
  micro(4€), starter(9€), professional(29€), enterprise(79€), distributor(149€)
  ← nema: paušalac(0), pos_free(0), rental(9.99), udruga(14.99),
           pos_arhiva(35), arhiva_ai(47)
  ← cijene WRONG: starter→22€, professional→69€, enterprise→189€, distributor→359€

AI Advisor: NE POSTOJI
BORG auto-detect na registraciji: NE POSTOJI

admin_approve_registration():
  fees = {'starter': 29, 'business': 59, 'enterprise': 99}  ← STARE CIJENE
```

---

## ZADATAK 1: registration/constants.py — novi paketi i cijene

**Zamijeni PLAN_FEATURES kompletno:**

```python
PLAN_FEATURES = {
    'pausalalac': {
        'name': 'Paušalac',
        'price': 0,
        'currency': '€',
        'modules': ['invoicing', 'documents', 'partners', 'worktime'],
        'features': [
            'Fakturiranje (do 40 računa/mj)',
            'Dokumenti',
            'Evidencija radnog vremena',
            '1 korisnik',
            'Besplatno dok si paušalac',
        ],
        'borg_detect': {
            'business_type': ['obrt'],
            'keywords': ['paušalac', 'pausalalac', 'sam', 'jedan zaposleni', 'slobodnjak', 'freelance'],
            'employee_max': 1,
        },
    },
    'pos_free': {
        'name': 'POS Besplatno',
        'price': 0,
        'currency': '€',
        'modules': ['pos'],
        'features': [
            'Samo POS blagajna',
            'Fiskalizacija',
            'Bez ERP modula',
            '1 terminal',
        ],
        'borg_detect': {
            'keywords': ['samo blagajna', 'pos', 'kasa', 'blagajna', 'cafe', 'kafić'],
            'no_invoicing': True,
        },
    },
    'rental': {
        'name': 'Rental',
        'price': Decimal('9.99'),
        'currency': '€',
        'modules': ['rental', 'documents', 'invoicing', 'partners'],
        'features': [
            'Najam opreme / prostora',
            'eVisitor integracija',
            'Fakturiranje',
            'Gosti i check-in',
            'Do 2 korisnika',
        ],
        'borg_detect': {
            'business_type': ['obrt', 'doo', 'opg'],
            'keywords': ['iznajmljujem', 'najam', 'apartman', 'soba', 'smještaj',
                         'rental', 'opg', 'seljačko domaćinstvo'],
            'industry': ['rental', 'opg'],
        },
    },
    'micro': {
        'name': 'Micro',
        'price': Decimal('10.00'),
        'currency': '€',
        'modules': ['invoicing', 'partners', 'documents'],
        'features': [
            'Fakturiranje',
            'Partneri',
            'Dokumenti',
            '1 korisnik',
            '50 računa/mj',
        ],
        'borg_detect': {
            'keywords': ['minimalno', 'samo fakture', 'malo firmu', 'mali obrt'],
        },
    },
    'udruga': {
        'name': 'Udruga',
        'price': Decimal('14.99'),
        'currency': '€',
        'modules': ['invoicing', 'documents', 'partners', 'worktime',
                    'udruge', 'pos', 'appointments'],
        'features': [
            'Modul za udruge i zadruge',
            'Članarine i donacije',
            'POS blagajna',
            'Termini i rezervacije',
            'Fakturiranje',
            'Do 5 korisnika',
        ],
        'borg_detect': {
            'business_type': ['udruga', 'zadruga', 'ustanova'],
            'keywords': ['udruga', 'zadruga', 'ustanova', 'neprofitno',
                         'klapa', 'klub', 'kulturno', 'sportski', 'KUD'],
        },
    },
    'starter': {
        'name': 'Starter',
        'price': Decimal('22.00'),
        'currency': '€',
        'modules': ['invoicing', 'partners', 'documents', 'calculator',
                    'worktime', 'projects', 'pos', 'appointments'],
        'features': [
            'Fakturiranje i naplata',
            'POS blagajna',
            'Radni nalozi',
            'Termini',
            'Do 3 korisnika',
        ],
        'borg_detect': {
            'business_type': ['doo', 'jdoo', 'obrt'],
            'keywords': ['mala firma', 'nekoliko zaposlenih', 'servis', 'usluge'],
            'employee_range': [2, 10],
        },
    },
    'pos_arhiva': {
        'name': 'POS + Arhiva',
        'price': Decimal('35.00'),
        'currency': '€',
        'modules': ['pos', 'invoicing', 'documents', 'partners',
                    'inventory', 'konto'],
        'features': [
            'POS + Fiskalizacija',
            'Arhiva dokumenata (AI OCR)',
            'Knjiženje',
            'Inventura',
            'Do 5 korisnika',
        ],
        'borg_detect': {
            'keywords': ['trgovina', 'prodavaonica', 'dućan', 'maloprodaja',
                         'supermarket', 'pekara'],
            'has_inventory': True,
        },
    },
    'arhiva_ai': {
        'name': 'Arhiva + AI',
        'price': Decimal('47.00'),
        'currency': '€',
        'modules': ['documents', 'invoicing', 'partners', 'konto',
                    'ai_assistant', 'smart_import', 'eracun', 'synesis'],
        'features': [
            'Arhiva + AI OCR (batch 100)',
            'e-Račun (FINA posrednik)',
            'Synesis uvoz',
            'AI Asistent',
            'Ideal za računovođu',
            'Do 10 korisnika',
        ],
        'borg_detect': {
            'business_type': ['doo', 'obrt'],
            'keywords': ['računovođa', 'računovodstvo', 'knjigovodstvo',
                         'steuerberater', 'buchhalter'],
            'industry': ['accounting'],
        },
    },
    'professional': {
        'name': 'Professional',
        'price': Decimal('69.00'),
        'currency': '€',
        'modules': ['invoicing', 'partners', 'documents', 'calculator',
                    'worktime', 'projects', 'pos', 'appointments',
                    'konto', 'reports', 'tracking', 'assessment',
                    'outreach', 'work_orders', 'marketplace', 'delivery',
                    'gastro_menu', 'payroll', 'ai_assistant'],
        'features': [
            'Sve iz Starter paketa',
            'Računovodstvo (RRiF/SKR03)',
            'AI Asistent',
            'Payroll',
            'CRM / Outreach',
            'Do 15 korisnika',
        ],
        'borg_detect': {
            'business_type': ['doo', 'dd', 'gmbh'],
            'keywords': ['rastuća firma', 'više zaposlenih', 'računovodstvo'],
            'employee_range': [10, 50],
        },
    },
    'enterprise': {
        'name': 'Enterprise',
        'price': Decimal('189.00'),
        'currency': '€',
        'modules': [
            'invoicing', 'partners', 'documents', 'calculator', 'worktime',
            'projects', 'pos', 'appointments', 'konto', 'reports', 'tracking',
            'assessment', 'outreach', 'work_orders', 'marketplace', 'delivery',
            'gastro_menu', 'payroll', 'finance', 'inventory', 'webshop', 'rental',
            'interventions', 'ai_assistant', 'eracun', 'propter', 'synesis',
            'smart_import', 'procurement', 'maintenance', 'helpdesk', 'udruge',
        ],
        'features': [
            'Svi moduli (46)',
            'e-Račun (FINA posrednik)',
            'AI Asistent',
            'Neograničen broj korisnika',
            'API pristup',
            'Dedicirani account manager',
        ],
        'borg_detect': {
            'business_type': ['doo', 'dd', 'gmbh', 'ag'],
            'keywords': ['enterprise', 'sve module', 'kompletan erp'],
            'employee_min': 50,
        },
    },
    'distributor': {
        'name': 'Distributor',
        'price': Decimal('359.00'),
        'currency': '€',
        'modules': [],  # Enterprise + multi-location
        'features': [
            'Sve iz Enterprise paketa',
            'Do 10 lokacija',
            'Do 50 korisnika',
            'White-label branding',
            'Invite kodovi za klijente',
        ],
        'borg_detect': {
            'keywords': ['više lokacija', 'franšiza', 'lanci', 'multi-location',
                         'filijale', 'poslovnice'],
            'multi_location': True,
        },
    },
}

PLAN_MODULES = {
    plan: set(data.get('modules', []))
    for plan, data in PLAN_FEATURES.items()
}
PLAN_MODULES['distributor'] = PLAN_MODULES['enterprise']
PLAN_MODULES['business'] = PLAN_MODULES['professional']  # legacy

PLAN_PRICES = {
    plan: str(data['price'])
    for plan, data in PLAN_FEATURES.items()
}
```

---

## ZADATAK 2: registration/models.py — BUSINESS_TYPES + PLAN_CHOICES

```python
BUSINESS_TYPES = [
    ('doo', 'd.o.o.'),
    ('jdoo', 'j.d.o.o.'),
    ('obrt', 'Obrt'),
    ('dd', 'd.d.'),
    ('sp', 's.p.'),
    ('opg', 'O.P.G.'),
    ('udruga', 'Udruga'),
    ('zadruga', 'Zadruga'),
    ('ustanova', 'Ustanova / Zavod'),
    ('gmbh', 'GmbH'),
    ('ag', 'AG'),
    ('einzelunternehmen', 'Einzelunternehmen'),
    ('eu', 'EU company'),
    ('other', 'Other'),
]

PLAN_CHOICES = [
    ('pausalalac', 'Paušalac – BESPLATNO'),
    ('pos_free',  'POS Besplatno – BESPLATNO'),
    ('rental',    'Rental – €9.99/mj'),
    ('micro',     'Micro – €10/mj'),
    ('udruga',    'Udruga – €14.99/mj'),
    ('starter',   'Starter – €22/mj'),
    ('pos_arhiva','POS + Arhiva – €35/mj'),
    ('arhiva_ai', 'Arhiva + AI – €47/mj'),
    ('professional', 'Professional – €69/mj'),
    ('enterprise',   'Enterprise – €189/mj'),
    ('distributor',  'Distributor – €359/mj'),
]
```

Migracija: `venv/bin/python manage.py makemigrations registration`

---

## ZADATAK 3: BORG AI Advisor — novi fajl

**Fajl:** `registration/borg_advisor.py`

```python
"""
BORG AI Advisor — prepoznaje tko se registrira i predlaže pravi paket.
Radi bez API poziva za poznate obrasce. Haiku fallback za rubne slučajeve.
"""
from registration.constants import PLAN_FEATURES


KEYWORD_PLAN_MAP = {}
for plan_key, plan_data in PLAN_FEATURES.items():
    for kw in plan_data.get('borg_detect', {}).get('keywords', []):
        KEYWORD_PLAN_MAP[kw.lower()] = plan_key

BUSINESS_TYPE_PLAN_MAP = {
    'udruga':   'udruga',
    'zadruga':  'udruga',
    'ustanova': 'udruga',
    'opg':      'rental',
    'gmbh':     'professional',
    'ag':       'enterprise',
}


def borg_suggest_plan(business_type: str, description: str = '',
                      employee_count: int = 0, country: str = 'HR') -> dict:
    """
    Lokalni (bez API) plan advisor.
    Vraća: {'plan': str, 'reason': str, 'confidence': float}
    """
    desc_lower = description.lower()

    # 1. business_type direktan match
    if business_type in BUSINESS_TYPE_PLAN_MAP:
        plan = BUSINESS_TYPE_PLAN_MAP[business_type]
        return {
            'plan': plan,
            'reason': f'Tip poslovnog subjekta ({business_type}) → {plan}',
            'confidence': 0.95,
        }

    # 2. keyword match u opisu
    matched_plan = None
    matched_kw = None
    for kw, plan in KEYWORD_PLAN_MAP.items():
        if kw in desc_lower:
            matched_plan = plan
            matched_kw = kw
            break

    if matched_plan:
        return {
            'plan': matched_plan,
            'reason': f'Ključna riječ "{matched_kw}" → {matched_plan}',
            'confidence': 0.88,
        }

    # 3. employee count heuristika
    if employee_count == 0 or employee_count == 1:
        if business_type == 'obrt':
            return {'plan': 'pausalalac', 'reason': 'Obrt, 1 zaposleni → Paušalac', 'confidence': 0.85}

    if employee_count > 50:
        return {'plan': 'enterprise', 'reason': f'{employee_count} zaposlenih → Enterprise', 'confidence': 0.80}
    if employee_count > 10:
        return {'plan': 'professional', 'reason': f'{employee_count} zaposlenih → Professional', 'confidence': 0.75}

    # 4. Default po business_type
    defaults = {
        'doo': 'starter', 'jdoo': 'micro', 'obrt': 'starter',
        'dd': 'professional', 'sp': 'micro',
    }
    default_plan = defaults.get(business_type, 'starter')
    return {
        'plan': default_plan,
        'reason': f'Default za {business_type}',
        'confidence': 0.60,
    }


def borg_suggest_plan_ai(user_message: str) -> dict:
    """
    Haiku fallback za natural language input.
    "Ja sam udruga" → {'plan': 'udruga', 'reason': '...', 'confidence': 0.9}
    """
    import anthropic, json
    client = anthropic.Anthropic()

    plan_list = ', '.join(PLAN_FEATURES.keys())
    resp = client.messages.create(
        model='claude-haiku-4-5-20251001',
        max_tokens=200,
        messages=[{
            'role': 'user',
            'content': f"""Ti si BORG advisor za LIMIT Connect ERP.
Korisnik kaže: "{user_message}"
Dostupni paketi: {plan_list}

Vrati SAMO JSON (bez markdown):
{{"plan": "ime_paketa", "reason": "kratko objašnjenje", "confidence": 0.0-1.0}}"""
        }]
    )

    try:
        return json.loads(resp.content[0].text)
    except Exception:
        return {'plan': 'starter', 'reason': 'Haiku fallback', 'confidence': 0.5}
```

---

## ZADATAK 4: registration/views.py — 2 popravka

### A) admin_approve_registration — ispravi fees dict

Nađi liniju:
```python
fees = {'starter': Decimal('29.00'), 'business': Decimal('59.00'), 'enterprise': Decimal('99.00')}
```

Zamijeni:
```python
from registration.constants import PLAN_FEATURES
fees = {plan: Decimal(str(data['price'])) for plan, data in PLAN_FEATURES.items()}
```

### B) Dodaj BORG API endpoint — plan suggestion

```python
from django.views.decorators.http import require_GET
from django.http import JsonResponse

@require_GET
def borg_plan_suggest(request):
    """
    AJAX: BORG predlaže plan na osnovu korisnikovog opisa.
    GET /registration/borg-suggest/?q=ja+sam+udruga&business_type=udruga
    """
    query = request.GET.get('q', '')
    business_type = request.GET.get('business_type', '')
    employee_count = int(request.GET.get('employees', 0) or 0)

    from registration.borg_advisor import borg_suggest_plan, borg_suggest_plan_ai

    # Brzo lokalno
    result = borg_suggest_plan(business_type, query, employee_count)

    # Ako confidence < 0.7 → Haiku
    if result['confidence'] < 0.7 and query:
        result = borg_suggest_plan_ai(query)

    # Dodaj detalje paketa
    from registration.constants import PLAN_FEATURES
    plan_data = PLAN_FEATURES.get(result['plan'], {})
    result['price'] = str(plan_data.get('price', 0))
    result['features'] = plan_data.get('features', [])[:4]

    return JsonResponse(result)
```

URL u `registration/urls.py`:
```python
path('borg-suggest/', views.borg_plan_suggest, name='borg_plan_suggest'),
```

---

## ZADATAK 5: Registracijska forma — BORG live suggest

U registracijskoj formi (provjeri koji template, vjerojatno `registration/register.html`
ili `registration/step1.html`), dodaj uz plan dropdown:

```html
<!-- BORG AI Advisor box -->
<div id="borgAdvisorBox" style="background:#f8f9fa; border:1px solid #dee2e6;
     border-radius:8px; padding:16px; margin-top:12px; display:none;">
  <div style="display:flex; align-items:center; gap:8px; margin-bottom:8px;">
    <span style="font-size:20px;">🤖</span>
    <strong style="color:#2c3e50;">BORG Advisor</strong>
    <span style="font-size:12px; color:#888;">preporučuje</span>
  </div>
  <div id="borgSuggestedPlan" style="font-size:18px; font-weight:700; color:#dc3545;"></div>
  <div id="borgReason" style="font-size:13px; color:#666; margin-top:4px;"></div>
  <div id="borgFeatures" style="font-size:12px; color:#555; margin-top:8px;"></div>
  <button type="button" onclick="borgApplyPlan()"
          style="margin-top:10px; background:#dc3545; color:#fff; border:none;
                 border-radius:6px; padding:8px 16px; cursor:pointer; font-size:13px;">
    ✓ Primijeni ovaj paket
  </button>
</div>

<script>
let borgDebounce;

// Pozovi BORG kad se promijeni business_type ili upiše opis
document.querySelector('[name=business_type]')?.addEventListener('change', triggerBorg);
document.querySelector('[name=description], [name=activity], textarea[name=note]')
  ?.addEventListener('input', function() {
    clearTimeout(borgDebounce);
    borgDebounce = setTimeout(triggerBorg, 800);
  });

async function triggerBorg() {
  const bt = document.querySelector('[name=business_type]')?.value || '';
  const desc = document.querySelector('[name=description], [name=activity], textarea[name=note]')?.value || '';
  if (!bt && !desc) return;

  const resp = await fetch(`/registration/borg-suggest/?business_type=${bt}&q=${encodeURIComponent(desc)}`);
  const data = await resp.json();

  document.getElementById('borgSuggestedPlan').textContent =
    data.plan.toUpperCase() + (data.price === '0' ? ' — BESPLATNO' : ` — €${data.price}/mj`);
  document.getElementById('borgReason').textContent = data.reason;
  document.getElementById('borgFeatures').innerHTML =
    (data.features || []).map(f => `✓ ${f}`).join('<br>');
  document.getElementById('borgAdvisorBox').style.display = 'block';
  document.getElementById('borgAdvisorBox').dataset.plan = data.plan;
}

function borgApplyPlan() {
  const plan = document.getElementById('borgAdvisorBox').dataset.plan;
  const sel = document.querySelector('[name=selected_plan]');
  if (sel) { sel.value = plan; sel.dispatchEvent(new Event('change')); }
}
</script>
```

---

## ZADATAK 6: migrate + test

```bash
venv/bin/python manage.py makemigrations registration
venv/bin/python manage.py migrate

# Test BORG advisor lokalno
venv/bin/python -c "
import os; os.environ['DJANGO_SETTINGS_MODULE']='core.settings'
import django; django.setup()
from registration.borg_advisor import borg_suggest_plan, borg_suggest_plan_ai

tests = [
    ('udruga', '', 0),
    ('obrt', 'sam radim, paušalac', 1),
    ('obrt', 'iznajmljujem apartmane', 0),
    ('doo', 'računovodstvo i knjiženje', 5),
    ('doo', 'pekara i prodavaonica', 8),
]

for bt, desc, emp in tests:
    r = borg_suggest_plan(bt, desc, emp)
    print(f'{bt:15} | {desc:35} → {r[\"plan\"]:12} ({r[\"confidence\"]:.0%}) | {r[\"reason\"]}')

# AI test
print()
ai_tests = ['ja sam udruga', 'imam obrt, sam radim', 'iznajmljujem sobe']
for msg in ai_tests:
    r = borg_suggest_plan_ai(msg)
    print(f'{msg:35} → {r[\"plan\"]} ({r[\"confidence\"]:.0%})')
"
```

---

## COMMIT

```
git add registration/constants.py registration/models.py
git add registration/borg_advisor.py registration/views.py
git commit -m "feat(borg): BORG prepoznaje tko se registrira — 11 paketa, AI Advisor, live suggest"
```

---

## DEFINICIJA DONE

- [ ] 11 paketa u PLAN_FEATURES s ispravnim cijenama
- [ ] BUSINESS_TYPES prošireni (udruga, zadruga, opg, gmbh, ag...)
- [ ] `borg_advisor.py` — lokalni suggest + Haiku fallback
- [ ] `admin_approve_registration` koristi PLAN_FEATURES cijene (ne hardkodirane)
- [ ] `/registration/borg-suggest/` endpoint radi
- [ ] Registracijska forma ima BORG Advisor box (live suggest)
- [ ] Test: svih 5 test slučajeva točno prepoznato
- [ ] Migracija aplicirana
