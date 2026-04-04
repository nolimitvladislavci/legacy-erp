# CC_TASK: WHITELABEL ENGINE — Distributer branding
# Datum: 04.04.2026. | Rok: 06.04.2026. | Prioritet: P0
# BLOKIRA: distributer infrastrukturu, Marija/Kruljac subdomain

PRAVILO: READ models.py PRIJE svakog WRITE.
PRAVILO: base.html, .env NE DIRAS — WhiteLabel CSS override ide UNUTAR {% block extra_head %}
PRAVILO: python manage.py check + migrate 2>&1 | tail -5 nakon svake migracije.

---

## CILJ

Marija Brtan dobiva: konjik.limit-connect.com s Konjik logom
Kruljac Ivica dobiva: korpas.limit-connect.com s Korpaš brendom
Svaki novi distributer u HR/EU dobiva vlastiti subdomain

---

## KORAK 1: Provjeri teren

```bash
grep -rn "WhiteLabelConfig\|white_label\|WhiteLabel" --include="*.py" | grep -v venv | head -10
grep -n "class Company\b" companies/models.py | head -3
grep -n "subdomain\|brand\|logo" companies/models.py | head -10
cat core/middleware/__init__.py | head -50
grep -n "WhiteLabel\|white_label" core/context_processors.py | head -10
```

## KORAK 2: Model — WhiteLabelConfig

READ: companies/models.py (zadnjih 50 linija + importse)

DODAJ u `companies/models.py`:

```python
class WhiteLabelConfig(models.Model):
    """Konfig za distributer branding — jedan per agent/distributer."""
    
    FISCAL_CHOICES = [
        ('HR', 'Hrvatska (FINA)'),
        ('DE', 'Njemačka (KassenSichV)'),
        ('AT', 'Austrija (RKSV)'),
        ('SI', 'Slovenija (FURS)'),
    ]

    # Veza s korisnikom/agentom
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='white_label_config',
    )
    
    # Branding
    brand_name = models.CharField(max_length=80, help_text='Npr. Konjik d.o.o.')
    subdomain = models.SlugField(max_length=50, unique=True, help_text='Npr. konjik → konjik.limit-connect.com')
    logo_url = models.URLField(blank=True, help_text='URL logotipa (ili ostavi prazno za default)')
    primary_color = models.CharField(max_length=7, default='#c9a84c', help_text='Hex boja npr. #3b82f6')
    tagline = models.CharField(max_length=120, blank=True, help_text='Podnaslov ispod naziva')

    # Compliance
    fiscal_system = models.CharField(max_length=2, choices=FISCAL_CHOICES, default='HR')
    
    # Status
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'WhiteLabel konfiguracija'
        verbose_name_plural = 'WhiteLabel konfiguracije'
    
    def __str__(self):
        return f'{self.brand_name} ({self.subdomain})'
    
    @property
    def full_domain(self):
        return f'{self.subdomain}.limit-connect.com'
    
    @classmethod
    def get_for_request(cls, request):
        """Vrati WL config na temelju HTTP_HOST headera."""
        host = request.META.get('HTTP_HOST', '').split(':')[0].lower()
        # konjik.limit-connect.com → subdomain=konjik
        parts = host.split('.')
        if len(parts) >= 3:
            subdomain = parts[0]
            try:
                return cls.objects.select_related('owner').get(subdomain=subdomain, is_active=True)
            except cls.DoesNotExist:
                pass
        return None
```

MAKNI migraciju:
```bash
python venv/bin/python manage.py makemigrations companies --name="add_whitelabel_config"
python venv/bin/python manage.py migrate 2>&1 | tail -5
```

## KORAK 3: Middleware

READ: `core/middleware/__init__.py` ili `core/middleware.py` — gdje su ostali middlewarei

DODAJ `WhiteLabelMiddleware`:

```python
class WhiteLabelMiddleware:
    """
    Detektira WhiteLabel konfiguraciju iz HTTP_HOST.
    Sprema u request.white_label (None ako nije WL request).
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from companies.models import WhiteLabelConfig
        from django.core.cache import cache
        
        host = request.META.get('HTTP_HOST', '').split(':')[0].lower()
        cache_key = f'wl_config:{host}'
        
        # Cache 1 sat (WL config se rijetko mijenja)
        wl = cache.get(cache_key, '__NOT_SET__')
        if wl == '__NOT_SET__':
            wl = WhiteLabelConfig.get_for_request(request)
            cache.set(cache_key, wl, timeout=3600)
        
        request.white_label = wl
        response = self.get_response(request)
        return response
```

DODAJ u settings.py MIDDLEWARE listu (odmah iza SecurityMiddleware):
```python
'core.middleware.WhiteLabelMiddleware',
```
... ali NE DIRАЈ settings.py direktno — samo napiši EXEC naredbu:
```bash
# Provjeri gdje su middlewarei u settings.py
grep -n "WhiteLabel\|MIDDLEWARE" config/settings.py | head -20
# Dodaj ako nedostaje:
sed -i "s/'django.middleware.security.SecurityMiddleware',/'django.middleware.security.SecurityMiddleware',\n    'core.middleware.WhiteLabelMiddleware',/" config/settings.py
python venv/bin/python manage.py check 2>&1 | tail -3
```

## KORAK 4: Context Processor

READ: `core/context_processors.py`

DODAJ ili AŽURIRAJ context processor koji servira WL varijable svim templateovima:

```python
def white_label_context(request):
    """Injektira WL varijable u sve templateove."""
    wl = getattr(request, 'white_label', None)
    if wl:
        return {
            'WL_ACTIVE': True,
            'WL_NAME': wl.brand_name,
            'WL_SUBDOMAIN': wl.subdomain,
            'WL_LOGO': wl.logo_url or '',
            'WL_COLOR': wl.primary_color,
            'WL_TAGLINE': wl.tagline,
            'WL_FISCAL': wl.fiscal_system,
        }
    return {
        'WL_ACTIVE': False,
        'WL_NAME': 'LIMIT Connect',
        'WL_LOGO': '',
        'WL_COLOR': '#c9a84c',
        'WL_TAGLINE': '',
        'WL_FISCAL': 'HR',
    }
```

DODAJ u settings.py TEMPLATES[0]['OPTIONS']['context_processors']:
```python
'core.context_processors.white_label_context',
```

## KORAK 5: base.html CSS inject

READ: `templates/base.html` — pronađi `{% block extra_head %}` ili `</head>` tag.

U `{% block extra_head %}` ili direktno ispred `</head>`, dodaj WL CSS override:

```html
{% if WL_ACTIVE %}
<style>
  :root {
    --gold: {{ WL_COLOR }};
    --gold-light: {{ WL_COLOR }};
  }
</style>
{% if WL_LOGO %}
<style>
  .navbar-brand img, .sidebar-logo img { content: url('{{ WL_LOGO }}'); }
  .sidebar-logo-text::before { content: '{{ WL_NAME }}'; }
</style>
{% endif %}
{% endif %}
```

PROVJERI kako se prikazuje logo u base.html, pa prilagodi selector!

## KORAK 6: Admin + Seed

```python
# companies/admin.py — dodaj
from .models import WhiteLabelConfig
@admin.register(WhiteLabelConfig)
class WhiteLabelConfigAdmin(admin.ModelAdmin):
    list_display = ('brand_name', 'subdomain', 'fiscal_system', 'is_active', 'created_at')
    list_filter = ('fiscal_system', 'is_active')
```

Seed za Mariju i Kruljac (run samo jednom):
```bash
python venv/bin/python manage.py shell -c "
from django.contrib.auth.models import User
from companies.models import WhiteLabelConfig

# Marija
u = User.objects.filter(username='marija').first()
if u:
    WhiteLabelConfig.objects.get_or_create(owner=u, defaults={
        'brand_name': 'Konjik d.o.o.',
        'subdomain': 'konjik',
        'primary_color': '#c9a84c',
        'fiscal_system': 'HR',
        'tagline': 'Vaš računovodstveni partner',
    })
    print('Konjik WL kreiran')

# Kruljac
u2 = User.objects.filter(username='kruljac').first() or User.objects.filter(username='ivica').first()
if u2:
    WhiteLabelConfig.objects.get_or_create(owner=u2, defaults={
        'brand_name': 'Korpaš d.o.o.',
        'subdomain': 'korpas',
        'primary_color': '#2563eb',
        'fiscal_system': 'HR',
        'tagline': 'Poslovanje bez granica',
    })
    print('Korpaš WL kreiran')
"
```

## KORAK 7: Nginx wildcard (INFORMACIJA — ne diraji, samo provjeri)

```bash
cat /etc/nginx/sites-available/limit-connect | grep -A 5 "server_name"
# Treba biti: server_name limit-connect.com *.limit-connect.com;
# Ako nije — napiši u DONE report, Ivan odobrava izmjenu
```

## DONE kriteriji:
- [ ] WhiteLabelConfig model postoji, migrate prošla
- [ ] WhiteLabelMiddleware aktivan (check prolazi)
- [ ] Context processor vraća WL_ACTIVE, WL_NAME, WL_COLOR
- [ ] konjik WL config postoji u bazi
- [ ] korpas WL config postoji u bazi
- [ ] Admin: WhiteLabelConfig vidljiv u /admin/
- [ ] base.html: WL_COLOR override radi (CSS var)
- [ ] Nginx: server_name pokriva *.limit-connect.com (provjeri i reportaj)
