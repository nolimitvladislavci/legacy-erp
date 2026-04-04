# CC_TASK_LICENSING_ENGINE.md
# Za: CC Code
# Datum: 2026-03-30
# Prioritet: VISOKO
# Procjena: 1-2 dana
#
# KONTEKST:
# LIMIT Connect se transformira iz "SaaS za krajnjeg korisnika"
# u "infrastruktura za digitalne posrednike".
#
# Posrednik (HR ili EU) nije korisnik softvera — on je KUPAC INFRASTRUKTURE.
# Ima vlastite klijente ispod sebe, vlasteni brand, vlastitu naplatu.
#
# Tehnički: Company model mora razumjeti razliku između:
#   role='client'    → plaća 22-189 EUR/mj, koristi software direktno
#   role='licensee'  → plaća 500-3.000 EUR/mj, ima vlastite klijente
#   role='platform'  → Konjik d.o.o., vlasnik svega

---

## KORAK 1 — WhiteLabelConfig model

Provjeri postoji li već:
```bash
grep -rn "WhiteLabelConfig\|white_label\|whiteLabelConfig" /var/www/fina-connect --include="*.py" | grep -v venv | grep -v test | grep -v ".pyc"
```

Ako ne postoji, kreiraj u `companies/models.py`:

```python
class WhiteLabelConfig(models.Model):
    """
    Konfiguracija za Licensee — firma koja kupuje pravo da preprodaje LIMIT Connect.
    Licensee ima vlasteni brand, vlastene klijente, vlastenu naplatu.
    """
    company = models.OneToOneField(
        'Company', on_delete=models.CASCADE,
        related_name='white_label'
    )

    # Branding
    brand_name = models.CharField(max_length=100)
    brand_logo = models.ImageField(upload_to='white_label/logos/', blank=True, null=True)
    primary_color = models.CharField(max_length=7, default='#1a3a6b')
    accent_color = models.CharField(max_length=7, default='#c9a84c')

    # Pristup (subdomena ili custom domena)
    subdomain = models.SlugField(
        max_length=50, blank=True, unique=True, null=True,
        help_text='npr. adriatik → adriatik.limit-connect.com'
    )
    custom_domain = models.CharField(
        max_length=200, blank=True,
        help_text='npr. erp-adriatik.hr'
    )

    # Naplata
    BILLING_MODE = [
        ('platform', 'Platforma naplaćuje klijente direktno'),
        ('licensee', 'Licensee naplaćuje vlastite klijente'),
    ]
    billing_mode = models.CharField(max_length=20, choices=BILLING_MODE, default='platform')
    commission_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=20,
        help_text='Postotak za Licensee od pretplata njegovih klijenata'
    )

    # Fiscal sistem (ključno za EU)
    FISCAL_SYSTEMS = [
        ('hr', 'Hrvatska — CIS/FINA'),
        ('de', 'Njemačka — KassenSichV/TSE'),
        ('at', 'Austrija — RKSV'),
        ('si', 'Slovenija — FURS'),
        ('eu', 'EU generički — PEPPOL/XRechnung'),
    ]
    fiscal_system = models.CharField(max_length=5, choices=FISCAL_SYSTEMS, default='hr')
    default_country = models.CharField(max_length=2, default='HR')
    default_language = models.CharField(max_length=5, default='hr')

    # Support
    support_email = models.EmailField(blank=True)
    from_name = models.CharField(max_length=100, blank=True)

    # Licensing fee (koliko plaća LIMIT Connect-u)
    monthly_license_fee = models.DecimalField(
        max_digits=10, decimal_places=2, default=500,
        help_text='Iznos koji Licensee plaća LIMIT Connect-u svaki mj'
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = 'White Label / Licensee konfiguracija'
        verbose_name_plural = 'White Label konfiguracije'

    def __str__(self):
        return f'{self.brand_name} — {self.fiscal_system.upper()}'

    @property
    def entry_url(self):
        if self.custom_domain:
            return f'https://{self.custom_domain}/pocni/'
        if self.subdomain:
            return f'https://{self.subdomain}.limit-connect.com/pocni/'
        return f'https://limit-connect.com/pocni/?brand={self.company_id}'

    @property
    def is_eu_licensee(self):
        return self.fiscal_system in ('de', 'at', 'si', 'eu')
```

Migracija:
```bash
venv/bin/python manage.py makemigrations companies --name white_label_config
venv/bin/python manage.py migrate
```

---

## KORAK 2 — WhiteLabelMiddleware

Dodati u `core/middleware/__init__.py` — PRIJE Force2FA i ForceTCMiddleware:

```python
class WhiteLabelMiddleware:
    """
    Detektira white-label brand iz domene → postavlja request.white_label.
    Radi za subdomain (adriatik.limit-connect.com) i custom domain (erp-adriatik.hr).
    """
    PLATFORM_HOSTS = {
        'limit-connect.com', 'www.limit-connect.com',
        '127.0.0.1', 'localhost', 'testserver'
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.white_label = self._detect(request)
        return self.get_response(request)

    def _detect(self, request):
        host = request.get_host().split(':')[0].lower()

        if host in self.PLATFORM_HOSTS:
            return None

        from companies.models import WhiteLabelConfig

        # Custom domain
        try:
            return WhiteLabelConfig.objects.select_related('company').get(
                custom_domain=host, is_active=True
            )
        except WhiteLabelConfig.DoesNotExist:
            pass

        # Subdomain: adriatik.limit-connect.com
        if '.limit-connect.com' in host:
            sub = host.split('.limit-connect.com')[0]
            try:
                return WhiteLabelConfig.objects.select_related('company').get(
                    subdomain=sub, is_active=True
                )
            except WhiteLabelConfig.DoesNotExist:
                pass

        return None
```

Dodati u MIDDLEWARE listu (u settings.py), ODMAH iza SessionMiddleware:
```python
"core.middleware.WhiteLabelMiddleware",
```

---

## KORAK 3 — Context Processor

Dodati u `permissions/context_processors.py`:

```python
def white_label(request):
    """Injecira white-label branding u sve templateove."""
    wl = getattr(request, 'white_label', None)
    if not wl:
        return {
            'WL_ACTIVE': False,
            'WL_NAME': 'LIMIT Connect',
            'WL_PRIMARY': '#1a3a6b',
            'WL_ACCENT': '#c9a84c',
            'WL_LOGO': None,
            'WL_SUPPORT': 'support@limit-connect.com',
        }
    return {
        'WL_ACTIVE': True,
        'WL_NAME': wl.brand_name,
        'WL_PRIMARY': wl.primary_color,
        'WL_ACCENT': wl.accent_color,
        'WL_LOGO': wl.brand_logo.url if wl.brand_logo else None,
        'WL_SUPPORT': wl.support_email or 'support@limit-connect.com',
        'WL_CONFIG': wl,
    }
```

Dodati u `settings.py` u `TEMPLATES['OPTIONS']['context_processors']`:
```python
'permissions.context_processors.white_label',
```

---

## KORAK 4 — base.html integracija

U `<head>` sekciji `templates/base.html` dodati CSS varijable:
```html
{% if WL_ACTIVE %}
<style>
:root {
  --brand-primary: {{ WL_PRIMARY }};
  --brand-accent: {{ WL_ACCENT }};
}
</style>
{% endif %}
```

U logo sekciji headera:
```html
{% if WL_LOGO %}
  <img src="{{ WL_LOGO }}" alt="{{ WL_NAME }}" style="height:40px;">
{% elif WL_ACTIVE %}
  <span style="font-weight:800;color:var(--brand-accent)">{{ WL_NAME }}</span>
{% else %}
  <span class="brand-logo">LIMIT Connect</span>
{% endif %}
```

---

## KORAK 5 — Compliance Packages model

Dodati u `companies/models.py` (ili novi fajl `companies/compliance.py`):

```python
class CompliancePackage(models.Model):
    """
    Paket zakonskih zahtjeva po državi.
    Licensee odabire koji compliance paket koristi za svoje klijente.
    """
    COUNTRY = [
        ('hr', 'Hrvatska'),
        ('de', 'Njemačka'),
        ('at', 'Austrija'),
        ('si', 'Slovenija'),
        ('eu', 'EU generički'),
    ]

    country = models.CharField(max_length=5, choices=COUNTRY, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField()
    legal_basis = models.TextField(help_text='Zakon/propis koji uvodi obavezu')
    mandatory_from = models.DateField(null=True, blank=True, help_text='Datum obveze')

    # Što je uključeno
    has_fiscal = models.BooleanField(default=False)
    has_einvoice = models.BooleanField(default=False)
    has_tse = models.BooleanField(default=False)  # DE specifično
    has_xrechnung = models.BooleanField(default=False)  # DE/EU
    has_dsfinvk = models.BooleanField(default=False)  # DE export
    has_peppol = models.BooleanField(default=False)

    # Addon cijena na basic plan
    monthly_addon_eur = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Compliance paket'
        verbose_name_plural = 'Compliance paketi'

    def __str__(self):
        return f'{self.name} ({self.country.upper()})'
```

Seed podataka odmah:
```bash
venv/bin/python manage.py shell << 'PYEOF'
from companies.compliance import CompliancePackage

packages = [
    {
        'country': 'hr',
        'name': 'HR Fiskalizacija + eRačun',
        'description': 'Hrvatska fiskalizacija (CIS/FINA), eRačun od 2026.',
        'legal_basis': 'Zakon o fiskalizaciji NN 133/12, izmjene 2026.',
        'has_fiscal': True,
        'has_einvoice': True,
        'monthly_addon_eur': 0,  # Uključeno u basic plan
    },
    {
        'country': 'de',
        'name': 'DE KassenSichV 2.0 + XRechnung',
        'description': 'Kassengesetz, TSE obaveza, XRechnung B2G od 2025, B2B od 2028.',
        'legal_basis': 'KassenSichV (Kassensicherungsverordnung), E-Rechnungsgesetz',
        'has_fiscal': True,
        'has_tse': True,
        'has_xrechnung': True,
        'has_dsfinvk': True,
        'monthly_addon_eur': 50,
    },
    {
        'country': 'at',
        'name': 'AT RKSV + E-Rechnung',
        'description': 'Registrierkassensicherheitsverordnung, E-Rechnung B2G od 2024.',
        'legal_basis': 'RKSV (BGBl. II Nr. 410/2015)',
        'has_fiscal': True,
        'has_einvoice': True,
        'monthly_addon_eur': 40,
    },
    {
        'country': 'si',
        'name': 'SI FURS eDavki',
        'description': 'Slovenska fiskalizacija, eDavki portal, eRačun B2G.',
        'legal_basis': 'Zakon o davčnem potrjevanju računov (ZDavPR)',
        'has_fiscal': True,
        'has_einvoice': True,
        'monthly_addon_eur': 35,
    },
]

for p in packages:
    obj, created = CompliancePackage.objects.get_or_create(
        country=p['country'],
        defaults=p
    )
    print(f'{"Kreiran" if created else "Postoji"}: {obj.name}')
PYEOF
```

---

## KORAK 6 — Licensee Dashboard (minimalni)

Dodati view u `companies/views.py` ili `companies/licensee_views.py`:

```python
@login_required
def licensee_dashboard(request):
    """
    Dashboard za Licensee — vidi svoje klijente, MRR, prihode.
    Dostupno samo firmama s WhiteLabelConfig.
    """
    try:
        wl = request.user.profile.company.white_label
    except Exception:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden('Niste Licensee.')

    from companies.models import Company
    from registration.models import CompanySubscription

    # Klijenti koji su se registrirali kroz ovaj brand
    my_clients = Company.objects.filter(
        umbrella_parent=wl.company, is_active=True
    ).select_related('subscription')

    my_mrr = sum(
        c.subscription.monthly_fee
        for c in my_clients
        if hasattr(c, 'subscription') and c.subscription.is_active
    )
    my_commission = my_mrr * (wl.commission_pct / 100)

    return render(request, 'companies/licensee_dashboard.html', {
        'wl': wl,
        'clients': my_clients,
        'client_count': my_clients.count(),
        'my_mrr': my_mrr,
        'my_commission': my_commission,
        'entry_url': wl.entry_url,
    })
```

Dodati URL u `core/urls.py` (i18n, treba login):
```python
path('moj-portal/', 
     __import__('companies.licensee_views', fromlist=['licensee_dashboard']).licensee_dashboard,
     name='licensee_dashboard'),
```

---

## KORAK 7 — Verifikacija

```bash
venv/bin/python manage.py shell << 'PYEOF'
from companies.models import Company, WhiteLabelConfig

# Test setup: Marija kao Licensee
konjik = Company.objects.get(name__icontains='Konjik')
wl, created = WhiteLabelConfig.objects.get_or_create(
    company=konjik,
    defaults={
        'brand_name': 'Konjik ERP',
        'subdomain': 'konjik',
        'fiscal_system': 'hr',
        'default_country': 'HR',
        'monthly_license_fee': 359,
        'billing_mode': 'platform',
        'commission_pct': 20,
    }
)
print(f'WhiteLabel {"kreiran" if created else "postoji"}: {wl.brand_name}')
print(f'Entry URL: {wl.entry_url}')
print(f'Fiscal: {wl.fiscal_system}')
print(f'Licenca: {wl.monthly_license_fee} EUR/mj')

# Provjeri compliance pakete
from companies.compliance import CompliancePackage
for p in CompliancePackage.objects.all():
    print(f'Paket: {p.country.upper()} — {p.name}')

print('Licensing engine: OK')
PYEOF
```

---

## COMMIT

```bash
git add companies/ templates/companies/ permissions/context_processors.py \
        core/middleware/__init__.py core/settings.py
git commit -m "feat(licensing): WhiteLabelConfig + Compliance paketi + Licensee dashboard

WhiteLabelConfig model:
  - brand_name, logo, colors, subdomain, custom_domain
  - billing_mode: platform/licensee
  - fiscal_system: HR/DE/AT/SI/EU
  - monthly_license_fee (što licensee plaća LIMIT Connect-u)
  - entry_url property (link za SmartEntry s ovim brendom)

WhiteLabelMiddleware:
  - Detektira brand iz custom domene ili subdomene
  - request.white_label → dostupno svuda

Context processor white_label:
  - WL_NAME, WL_PRIMARY, WL_ACCENT, WL_LOGO u svim templateovima
  - base.html CSS override za branding

CompliancePackage model + seed:
  - HR, DE (KassenSichV+XRechnung), AT (RKSV), SI (FURS)
  - Osnova za pricing EU addon

Licensee dashboard /moj-portal/:
  - Moji klijenti, MRR, moja provizija
  - Entry URL s copy-to-clipboard

Transformacija: LIMIT Connect = infrastruktura za posrednike, ne samo SaaS"
```

---

## NAPOMENE ZA CC

1. WhiteLabelConfig.subdomain mora biti UNIQUE — provjeri unique=True u modelu

2. WhiteLabelMiddleware ide u MIDDLEWARE LISTU u settings.py odmah iza:
   "django.contrib.sessions.middleware.SessionMiddleware"
   NE na kraj liste — treba biti dostupno svim ostalim middlewareima

3. Ako companies.compliance ne postoji kao zasebni fajl, stavi modele u companies/models.py

4. Migracije: makemigrations companies → migrate → seed compliance paketa

5. OBAVEZNO: Nakon implementacije javi Sonnet:
   - URL: https://limit-connect.com/konjik/ ili subdomena (treba nginx konfiguraciju)
   - Verificiraj da request.white_label radi za konjik.limit-connect.com
   - Verificiraj compliance pakete u adminu
