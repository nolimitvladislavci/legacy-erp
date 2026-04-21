# CC_TASK: OPG Kruljac Slađana — Import + Web + EU Projekt + Burza

## STATUS: PENDING
## PRIORITET: P0

---

## PODACI IZ STARE BAZE (fina-connect)

```python
OPG_DATA = {
    'name':         'O.P.G. Kruljac Slađana',
    'entity_type':  'opg',
    'oib':          '41439993573',
    'vat_id':       'HR41439993573',
    'address':      'Kralja Tomislava 275',
    'city':         'Vladislavci',
    'postal_code':  '31404',
    'country':      'HR',
    'county':       'Osječko-baranjska',
    'iban':         'HR4224020061140216521',
    'email':        'opg.kruljac@limit-connect.com',
    'phone':        '0976091655',
    'nkd_code':     '01.50',
    'nkd_description': 'Mješovita poljoprivreda',
    'activity_description': 'Mliječno govedarstvo — robotizirana farma, Lely sustav',
    'vat_status':   'registered',
    'currency':     'EUR',
    'language':     'hr',
    'logo':         'company_logos/opg_kruljac.png',
    'notes':        'Lely robot_api_key: T04Frz7j9wwNItkGf9Yfyw378mkR8g0vtEvKXAzt0gg',
}
```

---

## BLOK 1 — Import korisnika u Fenix V3

### T-01 | STATUS: TODO
Pročitaj: /var/www/fenix-v3/companies/models.py (Company fields)
Pročitaj: /var/www/fenix-v3/accounts/models.py (User/Profile)

Kreiraj management command: /var/www/fenix-v3/companies/management/commands/import_opg_kruljac.py

```python
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from companies.models import Company

class Command(BaseCommand):
    help = 'Import OPG Kruljac Sladana from fina-connect'

    def handle(self, *args, **kwargs):
        User = get_user_model()

        # 1. Kreiraj usera (provjeri postoji li)
        user, created = User.objects.get_or_create(
            email='opg.kruljac@limit-connect.com',
            defaults={
                'username': 'opg_kruljac_sladana',
                'first_name': 'Slađana',
                'last_name': 'Kruljac',
                'is_active': True,
            }
        )
        if created:
            user.set_password('Kruljac2026!')  # temp, mora promijeniti
            user.save()

        # 2. Kreiraj Company — PROVJERI PRAVA POLJA PRIJE
        company, created = Company.objects.get_or_create(
            oib='41439993573',
            defaults={
                'name': 'O.P.G. Kruljac Slađana',
                'entity_type': 'opg',
                'address': 'Kralja Tomislava 275',
                'city': 'Vladislavci',
                'postal_code': '31404',
                'country': 'HR',
                'email': 'opg.kruljac@limit-connect.com',
                'phone': '0976091655',
                'nkd_code': '01.50',
                'nkd_description': 'Mješovita poljoprivreda',
                'vat_id': 'HR41439993573',
                'iban': 'HR4224020061140216521',
                'currency': 'EUR',
                'language': 'hr',
                'activity_description': 'Mliječno govedarstvo — robotizirana farma Lely',
                'website': 'https://limit-connect.com/opg/kruljac-sladana/',
            }
        )
        self.stdout.write(f'Company: {company.name} ({"kreirana" if created else "već postoji"})')
        self.stdout.write(f'User: {user.username} ({"kreiran" if created else "već postoji"})')
```

```bash
cd /var/www/fenix-v3
venv/bin/python manage.py import_opg_kruljac
```

---

## BLOK 2 — Generirana Web Stranica

### Arhitektura
URL: `/opg/<slug>/` → javno dostupno, bez logina
Template: `companies/templates/companies/opg_public.html`

Stranica ima 5 sekcija:
1. Hero — OPG info + logo + kontakt
2. Proizvodnja — svi segmenti farme
3. EU Projekt — sažetak + dokumenti
4. Web Shop — produkti na prodaju
5. Burza veza — aktivne ponude za druge OPG-ove

### T-02 | STATUS: TODO
Dodati URL u /var/www/fenix-v3/companies/urls.py:

```python
path('opg/<slug:slug>/', OPGPublicView.as_view(), name='opg_public'),
```

### T-03 | STATUS: TODO
Kreirati view u companies/views.py:

```python
class OPGPublicView(View):
    """Javna generirana stranica OPG-a — bez auth"""
    template_name = 'companies/opg_public.html'

    def get(self, request, slug):
        company = get_object_or_404(
            Company,
            entity_type='opg',
            website__icontains=slug
        )
        context = {
            'company': company,
            'production_segments': self._get_production(company),
            'eu_project': self._get_eu_project(company),
            'shop_products': self._get_products(company),
            'burza_offers': self._get_burza_offers(company),
        }
        return render(request, self.template_name, context)

    def _get_production(self, company):
        return company.production_segments.filter(is_active=True) \
               if hasattr(company, 'production_segments') else []

    def _get_eu_project(self, company):
        return company.eu_projects.first() \
               if hasattr(company, 'eu_projects') else None

    def _get_products(self, company):
        return company.shop_products.filter(available=True)[:12] \
               if hasattr(company, 'shop_products') else []

    def _get_burza_offers(self, company):
        return company.burza_offers.filter(status='active')[:5] \
               if hasattr(company, 'burza_offers') else []
```

### T-04 | STATUS: TODO
Kreirati template: companies/templates/companies/opg_public.html

Struktura (dark tema, gold akcenti, Fenix V3 stilovi):

```html
{% extends "base_public.html" %}
{% block content %}

<!-- SEKCIJA 1: HERO -->
<section class="opg-hero">
  <img src="{{ company.logo.url }}" alt="{{ company.name }}">
  <h1>{{ company.name }}</h1>
  <p>{{ company.activity_description }}</p>
  <div class="opg-meta">
    <span>OIB: {{ company.oib }}</span>
    <span>NKD: {{ company.nkd_code }} — {{ company.nkd_description }}</span>
    <span>{{ company.address }}, {{ company.city }}</span>
  </div>
</section>

<!-- SEKCIJA 2: PROIZVODNJA -->
<section class="opg-production" id="proizvodnja">
  <h2>Proizvodnja</h2>
  <div class="production-grid">
    <!-- Tvrdo kodirani segmenti + dinamički iz baze -->
    <div class="segment">🐄 Mliječno govedarstvo — 200 krava — 3× Lely robot</div>
    <div class="segment">🥩 Prerada mesa — mini klaonica</div>
    <div class="segment">🧀 Prerada mlijeka — sirarna</div>
    <div class="segment">⚡ Biogas 300kW + Solar 100kW</div>
    <div class="segment">🔬 Laboratorij embriotransfer</div>
    <div class="segment">🎓 Edukacijski centar — studenti EU</div>
  </div>
</section>

<!-- SEKCIJA 3: EU PROJEKT -->
<section class="opg-eu" id="eu-projekt">
  <h2>EU Projekt</h2>
  {% if eu_project %}
    {{ eu_project.description|safe }}
    <a href="{% url 'opg_eu_docs' company.slug %}">Dokumenti za apliciranje →</a>
  {% else %}
    <!-- Generirani sadržaj iz chata -->
    <div class="eu-summary">
      <h3>Modernizacija robotizirane farme — €6.89M</h3>
      <p>Projekt obuhvaća: 200 muznih krava, 3 Lely robota, biogas 300kW,
         preradu mesa i mlijeka, embriotransfer laboratorij, edukacijski centar.</p>
      <div class="funding-table">
        <div>73.10 bespovratno: €1,000,000</div>
        <div>73.11 bespovratno: €1,000,000</div>
        <div>HBOR 1726 (0% kamata): €2,000,000</div>
        <div>Kapitalni rabat (50%): -€1,000,000</div>
        <div>LEADER/Erasmus+: €400,000</div>
      </div>
    </div>
  {% endif %}
</section>

<!-- SEKCIJA 4: WEB SHOP -->
<section class="opg-shop" id="prodaja">
  <h2>Prodaja proizvoda</h2>
  <div class="shop-grid">
    {% for product in shop_products %}
    <div class="product-card">
      {% if product.image %}<img src="{{ product.image.url }}">{% endif %}
      <h3>{{ product.name }}</h3>
      <p>{{ product.description }}</p>
      <span class="price">€{{ product.price }}</span>
      <a href="{% url 'shop_order' product.id %}" class="btn-gold">Naruči</a>
    </div>
    {% empty %}
    <!-- Placeholder produkti -->
    <div class="product-card">🥛 Svježe mlijeko — €0.90/L</div>
    <div class="product-card">🧀 Sir — od €8/kg</div>
    <div class="product-card">🥩 Juneće meso — od €12/kg</div>
    {% endfor %}
  </div>
</section>

<!-- SEKCIJA 5: BURZA VEZA -->
<section class="opg-burza" id="burza">
  <h2>OPG Burza — Ponude</h2>
  <p>Slađana nudi višak kapaciteta i znanja ostalim OPG-ovima.</p>
  <div class="burza-offers">
    {% for offer in burza_offers %}
    <div class="offer-card">
      <h3>{{ offer.title }}</h3>
      <p>{{ offer.description }}</p>
      <a href="{% url 'burza_detail' offer.id %}">Kontaktiraj →</a>
    </div>
    {% empty %}
    <!-- Inicijalne ponude -->
    <div class="offer-card">
      🐄 Embriotransfer usluga — za uzgajivače u regiji
    </div>
    <div class="offer-card">
      🎓 Edukacijska posjeta — Lely robotika, 1 dan
    </div>
    <div class="offer-card">
      ⚡ Višak biogasa — za susjedne OPG-ove
    </div>
    {% endfor %}
  </div>
  <div class="burza-cta">
    <h3>Vi ste OPG? Spojite se s nama →</h3>
    <a href="/burza/upit/" class="btn-gold">Pošalji upit</a>
  </div>
</section>

{% endblock %}
```

---

## BLOK 3 — EU Projekt Model

### T-05 | STATUS: TODO
Kreirati model u companies/models.py (na kraj):

```python
class EUProject(BaseModel):
    """EU projekt vezan za kompaniju"""
    class Status(models.TextChoices):
        PRIPREMA   = 'priprema', 'Priprema dokumentacije'
        APLICIRANJE = 'apliciranje', 'Apliciranje'
        ODOBRENO   = 'odobreno', 'Odobreno'
        REALIZACIJA = 'realizacija', 'Realizacija'
        ZATVORENO  = 'zatvoreno', 'Zatvoreno'

    company        = models.ForeignKey(Company, on_delete=models.CASCADE,
                                       related_name='eu_projects')
    title          = models.CharField(max_length=300)
    program        = models.CharField(max_length=100)  # npr. "73.10 + 73.11 + HBOR 1726"
    total_value    = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    grant_amount   = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    own_contribution = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    status         = models.CharField(max_length=20, choices=Status.choices,
                                      default=Status.PRIPREMA)
    description    = models.TextField(blank=True)
    summary_html   = models.TextField(blank=True)  # AI generirani sažetak
    documents      = models.JSONField(default=list)  # lista dokumenata

    class Meta:
        verbose_name = 'EU Projekt'
        verbose_name_plural = 'EU Projekti'
```

### T-06 | STATUS: TODO
Seed podataka za OPG Kruljac:

```python
EUProject.objects.create(
    company=Company.objects.get(oib='41439993573'),
    title='Modernizacija robotizirane mliječne farme — Demo centar EU',
    program='73.10 + 73.11 + HBOR 1726 + LEADER',
    total_value=6890000,
    grant_amount=3400000,
    own_contribution=2490000,
    status='priprema',
    description="""
        Projekt obuhvaća proširenje s 1 na 3 Lely robota (200 krava),
        automatsku hranidbu, mini klaonicu, mljekaru/sirarnu,
        bioplinsko postrojenje 300kW, solar 100kW,
        laboratorij embriotransfer i edukacijski centar za EU farmere.
    """,
    documents=[
        {'naziv': 'Poslovni plan', 'status': 'priprema', 'rok': '30 dana'},
        {'naziv': 'Idejni projekt', 'status': 'priprema', 'rok': '30 dana'},
        {'naziv': 'Predračuni Lely', 'status': 'čeka', 'rok': '14 dana'},
        {'naziv': '73.10 zahtjev', 'status': 'čeka APPRRR konzultaciju'},
        {'naziv': '73.11 zahtjev', 'status': 'čeka APPRRR konzultaciju'},
        {'naziv': 'HBOR 1726 zahtjev', 'status': 'čeka odluku 73.10'},
        {'naziv': 'DNSH izjava', 'status': 'priprema'},
        {'naziv': 'BON-2 / SOL-2', 'status': 'pribaviti odmah'},
    ]
)
```

---

## BLOK 4 — Burza Veza (fina-connect → fenix-v3)

### T-07 | STATUS: TODO
Burza u fenix-v3 ne postoji. Opcije:
A) Port burza app iz fina-connect (preporučeno)
B) Koristiti fina-connect burza API iz fenix-v3

Implementiraj opciju B — API bridge:

```python
# fenix-v3/companies/burza_bridge.py
import requests

def get_opg_burza_offers(company_oib):
    """Dohvati burza ponude za OPG iz fina-connect"""
    try:
        r = requests.get(
            f'https://fina-connect.online/api/burza/opg/{company_oib}/',
            timeout=2
        )
        return r.json() if r.ok else []
    except Exception:
        return []
```

Ili direktno iz iste baze (share database):

```python
# fenix-v3/settings.py — dodati fina-connect bazu kao readonly
DATABASES['fina_connect'] = {
    'ENGINE': 'django.db.backends.postgresql',
    'NAME': 'fina_erp',
    'HOST': '127.0.0.1',
    'PORT': '6432',  # PgBouncer
    'OPTIONS': {'application_name': 'fenix_v3_readonly'},
}
```

---

## BLOK 5 — Migracija i Deploy

### T-08 | STATUS: TODO
```bash
cd /var/www/fenix-v3
venv/bin/python manage.py makemigrations companies
venv/bin/python manage.py migrate
venv/bin/python manage.py check
venv/bin/python manage.py import_opg_kruljac
systemctl reload gunicorn-fenix-v3.service
```

### T-09 | STATUS: TODO
Verifikacija:
```bash
curl https://limit-connect.com/opg/kruljac-sladana/
# Mora vratiti 200 OK s HTML sadržajem
```

### T-10 | STATUS: TODO
Commit:
```
feat(opg): OPG Kruljac Sladana — import + public page + EU project + burza bridge

- import_opg_kruljac management command
- OPGPublicView + opg_public.html template
- EUProject model + migration + seed data
- Burza bridge (fina-connect API)
- URL: /opg/kruljac-sladana/
```

---

## REDOSLJED

T-01 → T-02 → T-03 → T-04 → T-05 → T-06 → T-07 → T-08 → T-09 → T-10

PROČITAJ stvarna polja modela PRIJE svakog pisanja koda.
