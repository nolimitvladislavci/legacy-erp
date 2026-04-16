# CC TASK: evalidator.eu — Razina Senior Inženjera (10/10, #1 EU)

**Prioritet:** HIGH  
**Agent:** Claude Code (CC)  
**Datum:** 2026-04-16  
**Sonnet verdict:** Trenutno ~5/10 MVP. Cilj: senior engineer 10/10.

---

## TRENUTNI PROBLEMI (izmjereno)

| Problem | Lokacija | Težina |
|---------|----------|--------|
| 19 hardcoded hex boja u templateu | landing.html | ❌ Kritično |
| Nema dark/light toggle | landing.html | ❌ Kritično |
| Nema i18n (0 `{% trans %}` tagova) | cijeli app | ❌ Kritično |
| Nema `locale/` direktorija | evalidator/ | ❌ Kritično |
| Inline `<style>` blok ~80 linija | landing.html | ⚠️ Loše |
| Docs i Pricing su skeletonske stranice | docs.html, pricing.html | ⚠️ Loše |
| Nema meta OG tagova | landing.html | ⚠️ Loše |

---

## KORAK 1 — Čitaj PRIJE svega

```bash
# Design system koji POSTOJI i RADI u LIMIT Connect
cat /var/www/fina-connect/static/css/fenix-tokens.css | head -200
# Tema toggle koji POSTOJI
grep -A10 "theme-toggle\|toggleTheme\|data-theme" /var/www/fina-connect/templates/base.html
# i18n konfiguracija koja POSTOJI
grep "LANGUAGE\|LocaleMiddleware\|LANGUAGES" /var/www/fina-connect/core/settings.py
```

---

## KORAK 2 — Vanjski CSS fajl (ne inline `<style>`)

Kreiraj `/var/www/fina-connect/evalidator/static/evalidator/css/main.css`

**Pravila:**
- Koristi `var(--gold)`, `var(--surface)`, `var(--text)`, `var(--border)` itd.
- **NULA hardcoded boja** — sve iz fenix-tokens.css varijabli
- Dark/light automatski radi jer fenix-tokens.css mijenja varijable

```css
/* evalidator/static/evalidator/css/main.css */

/* Naslijeđuje fenix-tokens.css varijable */
.ev-hero { ... }
.ev-validator-card { background: var(--bg-card); border: 1px solid var(--border); ... }
.ev-tabs { background: var(--surface2); ... }
.ev-tab.active { background: var(--gold); color: var(--dark); ... }
.ev-input { background: var(--surface3); border: 1px solid var(--border); color: var(--text); ... }
.ev-result-valid { background: var(--green-dim); border: 1px solid var(--green); color: var(--green); }
.ev-result-invalid { background: var(--red-dim); border: 1px solid var(--red); color: var(--red); }
.ev-suggestion { color: var(--gold); }
.ev-badge { background: var(--surface2); border: 1px solid var(--border); color: var(--text-muted); }
.ev-badge.gold { border-color: var(--gold-border); color: var(--gold); }
.ev-api-block { background: var(--surface2); border: 1px solid var(--border); ... }
pre { background: var(--surface3); color: var(--green); ... }
```

---

## KORAK 3 — Dark/Light toggle

U `landing.html`:

```html
<!-- Na vrhu head-a: theme init (isti pattern kao LIMIT Connect base.html) -->
<script>
(function(){
  var t = localStorage.getItem('ev-theme') || 
          (window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark');
  document.documentElement.setAttribute('data-theme', t);
})();
</script>

<!-- Link na fenix-tokens.css (servirano iz /static/css/) -->
<link rel="stylesheet" href="/static/css/fenix-tokens.css">
<link rel="stylesheet" href="/static/evalidator/css/main.css">

<!-- Toggle button u headeru -->
<button id="ev-theme-toggle" onclick="evToggleTheme()" title="Tamna/Svijetla tema"
        aria-label="Toggle theme">
  <span id="ev-theme-icon">🌙</span>
</button>

<!-- Script na dnu -->
<script>
function evToggleTheme() {
  var html = document.documentElement;
  var current = html.getAttribute('data-theme');
  var next = current === 'dark' ? 'light' : 'dark';
  html.setAttribute('data-theme', next);
  localStorage.setItem('ev-theme', next);
  document.getElementById('ev-theme-icon').textContent = next === 'dark' ? '🌙' : '☀️';
}
// Init icon
(function(){
  var t = document.documentElement.getAttribute('data-theme');
  var icon = document.getElementById('ev-theme-icon');
  if(icon) icon.textContent = t === 'dark' ? '🌙' : '☀️';
})();
</script>
```

---

## KORAK 4 — Django i18n (pravi, ne JS hack)

### 4.1 Settings (provjeri/dopuni)

```python
# Mora biti u settings.py:
USE_I18N = True
LANGUAGE_CODE = 'hr'
LANGUAGES = [
    ('hr', 'Hrvatski'),
    ('en', 'English'),
    ('de', 'Deutsch'),
    ('sl', 'Slovenščina'),
]
LOCALE_PATHS = [BASE_DIR / 'locale']

# U MIDDLEWARE — LocaleMiddleware MORA biti ISPRED SessionMiddleware:
# 'django.middleware.locale.LocaleMiddleware',
```

### 4.2 URL prefiks

U `core/urls.py` (ili gdje je evalidator include):
```python
from django.conf.urls.i18n import i18n_patterns
urlpatterns += i18n_patterns(
    path('', include('evalidator.urls', namespace='evalidator')),
    prefix_default_language=False,  # /evalidator/ = HR (bez prefiksa)
                                     # /en/evalidator/ = EN
                                     # /de/evalidator/ = DE
)
```

**PAZI:** Ovo mijenja URL strukturu. Provjeri postoji li `i18n_patterns` već u projektu.

### 4.3 Template tagovi

U `landing.html`:
```html
{% load i18n %}
...
<title>{% trans "eValidator — Infrastruktura Povjerenja" %}</title>
<h1>{% trans "Infrastruktura" %} <em>{% trans "Povjerenja" %}</em></h1>
<p>{% blocktrans %}Besplatna provjera OIB, IBAN i VAT ID za cijelu EU.{% endblocktrans %}</p>
...
```

Sve vidljive stringove označi s `{% trans %}` ili `{% blocktrans %}`.

### 4.4 Locale fajlovi

```bash
mkdir -p /var/www/fina-connect/evalidator/locale/{hr,en,de,sl}/LC_MESSAGES/
cd /var/www/fina-connect
. venv/bin/activate
python manage.py makemessages -l hr -l en -l de -l sl --ignore=venv -d django 2>/dev/null || \
python manage.py makemessages -l en -l de -l sl --ignore=venv
```

Popuni `evalidator/locale/en/LC_MESSAGES/django.po`:
```
msgid "eValidator — Infrastruktura Povjerenja"
msgstr "eValidator — Infrastructure of Trust"

msgid "Besplatna provjera OIB, IBAN i VAT ID za cijelu EU."
msgstr "Free verification of OIB, IBAN and VAT ID for the entire EU."

msgid "Unesite OIB (11 znamenki)"
msgstr "Enter OIB (11 digits)"

msgid "OIB je ispravan ✓"
msgstr "OIB is valid ✓"

msgid "Infrastruktura"
msgstr "Infrastructure"

msgid "Povjerenja"
msgstr "of Trust"

# ... sve ostale stringove
```

Popuni `.po` za DE (Deutsch) i SI (Slovenščina).

```bash
python manage.py compilemessages
```

### 4.5 Language switcher u headeru

```html
{% load i18n %}
<div class="ev-lang-switcher">
  {% get_available_languages as LANGUAGES %}
  {% get_current_language as LANGUAGE_CODE %}
  {% for lang_code, lang_name in LANGUAGES %}
    {% language lang_code %}
    <a href="{{ request.path }}" 
       class="ev-lang-btn {% if lang_code == LANGUAGE_CODE %}active{% endif %}"
       hreflang="{{ lang_code }}">
      {{ lang_code|upper }}
    </a>
    {% endlanguage %}
  {% endfor %}
</div>
```

---

## KORAK 5 — Meta tagovi (SEO + OG)

```html
<meta name="description" content="{% trans 'Besplatna EU validacija OIB, IBAN i VAT ID.' %}">
<meta property="og:title" content="eValidator.eu">
<meta property="og:description" content="{% trans 'Infrastruktura Povjerenja — ISO 7064, MOD97, 27 EU zemalja' %}">
<meta property="og:url" content="https://evalidator.eu/">
<meta property="og:type" content="website">
<link rel="canonical" href="https://evalidator.eu/">
<link rel="alternate" hreflang="hr" href="https://evalidator.eu/">
<link rel="alternate" hreflang="en" href="https://evalidator.eu/en/">
<link rel="alternate" hreflang="de" href="https://evalidator.eu/de/">
```

---

## KORAK 6 — Docs i Pricing (prave stranice)

`docs.html` mora imati:
- Sve API endpointe s primjerima (OIB, IBAN, VAT, batch placeholder)
- Rate limit tablicu
- Auth (API key) opis
- Curl + Python + JS primjeri
- Isti dark/light toggle
- `{% trans %}` tagovi

`pricing.html`:
- Prava tablica planova (Free/Starter/Pro/Enterprise)
- FAQ sekcija
- Kontakt

---

## KORAK 7 — views.py poboljšanje

Dodaj u `landing` view:
```python
from django.utils.translation import get_language

def landing(request):
    lang = get_language()  # 'hr', 'en', 'de', 'sl'
    # Statistike s cache-om
    ...
    return render(request, 'evalidator/landing.html', {
        'stats': stats,
        'current_lang': lang,
    })
```

---

## KORAK 8 — collectstatic + migracije

```bash
python manage.py collectstatic --noinput
systemctl reload gunicorn-fina
```

---

## KORAK 9 — Testovi

`evalidator/tests.py` mora imati:
1. `test_landing_200_hr()` — landing u HR
2. `test_landing_200_en()` — landing u EN (URL prefiks)
3. `test_theme_css_variables_present()` — landing koristi var(--gold) ne #c9a84c
4. `test_validate_oib_htmx()` — POST vraća validan HTML partial
5. `test_validate_oib_api_json()` — GET vraća JSON
6. `test_rate_limit_enforced()` — 31. request dobiva 429
7. `test_validation_log_created()` — ValidationLog se kreira
8. `test_no_personal_data_in_log()` — log ne sadrži raw OIB

---

## KORAK 10 — Finalna verifikacija

```bash
# Sve mora proći:
curl -sk https://evalidator.eu/ | grep "var(--gold)" # Koristi CSS varijable
curl -sk https://evalidator.eu/validate/oib/ -X POST -d "oib=12345678903" | grep "ispravan"
curl -sk https://evalidator.eu/api/v1/oib/?oib=12345678903 | python3 -c "import sys,json;print(json.load(sys.stdin)['valid'])"
```

---

## ŠTO NE RADIŠ
- ❌ Ne uvodiš Vue.js, React, webpack
- ❌ Ne dupliciraš fenix-tokens.css — linkaj ga
- ❌ Ne pišeš inline `<style>` — sve u main.css
- ❌ Ne hardcodiš boje — samo CSS varijable
- ❌ Ne brišeš HTMX — radi, samo treba CSS popravak

## DEFINICIJA DONE
- [ ] Nula hardcoded boja u templateima
- [ ] Dark/light toggle radi (localStorage persistence)
- [ ] EN + DE prijevodi kompilirani i rade
- [ ] Language switcher vidljiv u headeru
- [ ] 8/8 testova prolazi
- [ ] `python manage.py check --deploy` bez kritičnih upozorenja
- [ ] CC_REPORT_EVALIDATOR_10_10.md s before/after metrikama
