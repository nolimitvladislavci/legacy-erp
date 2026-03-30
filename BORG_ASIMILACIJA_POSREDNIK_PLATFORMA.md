# BORG_ASIMILACIJA_POSREDNIK_PLATFORMA.md
# Status: STRATEŠKI PRIORITET
# Datum: 2026-03-30
# Autor: Sonnet (koordinator) — na temelju strateške analize Ivan Brtan
#
# KONTEKST:
# Tri scenarija koje Ivan Brtan identificira kao strateški put:
# S1: Regionalni HR posrednici (Split, Rijeka, Varaždin...)
# S2: EU white-label SaaS (DE, AT, SI — KassenSichV 2.0, XRechnung)
# S3: Hybrid (preporučeni put — oba paralelno)
#
#BREAK-EVEN s 2 radnika: ~55 plaćajućih klijenata ILI 5 Distributor planova
# Trenutno: 13 plaćajućih, MRR 2.380 EUR, gap -620 EUR/mj
#
# OVO NIJE TASK ZA CC CODE — ovo je poslovna transformacija platforme.
# Tri zasebna taska izlaze iz ovog dokumenta.

---

## ANALIZA SCENARIJA

### Scenarij 1 — Regionalni HR posrednici

Netko iz Splita ili Varaždina želi biti lokalni digitalni posrednik:
- Plati ISO 27001 (dijeli s LIMIT Connect ili sam), dobije licencu PU
- Radi pod vlastitim brendom, koristi LIMIT Connect infrastrukturu
- Servisira 30-100 lokalnih klijenata (pekarnice, OPG, vulkanizeri...)
- Plaća LIMIT Connect: 359 EUR/mj (Distributor plan)
- Zarađuje: 750-6.000 EUR/mj (ovisno o broju klijenata i planu)

BREAK-EVEN za posrednika: 35+ klijenata (35 × 55 EUR = 1.925 EUR - 359 = 1.566 EUR)
BREAK-EVEN za LIMIT Connect: 1. Distributor odmah → gap se zatvara

### Scenarij 2 — EU white-label SaaS

Firma u DE/AT/SI licencira LIMIT Connect:
- KassenSichV 2.0 (DE) — novi zahtjevi od 2026/2027
- Žele kupiti "koji radi" umjesto graditi od nule
- LIMIT Connect već ima: KassenSichV adapter, XRechnung, ZUGFeRD, DSFinV-K
- Viskovic-bau.de = proof of concept koji već postoji

Modeli naplate:
  Hosted SaaS:    500-2.000 EUR/mj (vlastita instanca, vlasteni brand)
  Source licenca: 25.000-50.000 EUR jednoratno
  Revenue share:  20% od njihovog MRR-a

BREAK-EVEN za LIMIT Connect: 1 EU partner @ 1.000 EUR/mj = sve pokriveno

### Scenarij 3 — Hybrid (preporučeni)

Korak 1 (Q2 2026): 2-3 HR Distributor → MRR +700-1.000 EUR, gap zatvoren
Korak 2 (Q3 2026): 1 EU SaaS licenca → MRR +1.000 EUR, prva dobit
Korak 3 (Q4 2026): 5 HR + 2 EU = MRR 5.000+ EUR, 2 radnika pokrivena

---

## TRI TASKA KOJI IZLAZE IZ OVE ANALIZE

---

### TASK A — GEMINI_TASK_POSREDNIK_STRATESKA_ANALIZA.md (Ivan čita, ne CC)

Gemini treba napraviti:
1. Analizu zakonskih zahtjeva po EU državama za digitalne posrednike 2026/2027
2. Competitive mapping: tko već nudi white-label fiscalization SaaS u EU
3. Pricing benchmark za SaaS licencu (DE, AT, SI, CZ, PL tržišta)
4. Risk matrica: što se dogodi ako LIMIT Connect postane "kritična infrastruktura" za strane posrednike
5. Preporuku ugovornog okvira (SLA, SaaS agreement, data processing za GDPR)

Output: dokument koji Ivan može uzeti na sastanak s potencijalnim EU partnerom.

---

### TASK B — CC_TASK_WHITE_LABEL_ENGINE.md (tehnička implementacija)

#### B1. Tenant Model (multi-instanca iz jedne baze)

Trenutno: svaka Company je "jednaka". Nema koncepta "ovaj Distributor ima vlastiti brand".

Trebamo: WhiteLabelConfig model

```python
# companies/models.py ili novi whiteLabelApp

class WhiteLabelConfig(models.Model):
    """
    Konfiguracija za Distributor plan — vlasteni brand na LIMIT Connect infrastrukturi.
    """
    company = models.OneToOneField(Company, on_delete=models.CASCADE, related_name='white_label')
    
    # Branding
    brand_name = models.CharField(max_length=100, help_text='npr. "ERP Adriatik"')
    brand_logo = models.ImageField(upload_to='white_label/logos/', blank=True)
    primary_color = models.CharField(max_length=7, default='#1a3a6b')  # HEX
    accent_color = models.CharField(max_length=7, default='#c9a84c')
    
    # Domain
    custom_domain = models.CharField(
        max_length=200, blank=True,
        help_text='npr. erp-adriatik.hr — nginx konfig se generira automatski'
    )
    subdomain = models.CharField(
        max_length=50, blank=True,
        help_text='npr. adriatik → adriatik.limit-connect.com'
    )
    
    # Billing separacija
    billing_mode = models.CharField(max_length=20, choices=[
        ('platform', 'Platforma naplaćuje direktno'),      # LIMIT Connect → klijent
        ('distributor', 'Distributor naplaćuje sam'),       # Distributor → klijent
        ('hybrid', 'Mješovito'),
    ], default='platform')
    
    distributor_commission_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=20,
        help_text='Postotak koji Distributor dobiva od pretplata klijenata'
    )
    
    # Email branding
    from_email_name = models.CharField(max_length=100, blank=True, help_text='npr. "ERP Adriatik Tim"')
    support_email = models.EmailField(blank=True)
    
    # Jezik/lokalizacija
    default_language = models.CharField(max_length=5, default='hr')
    default_country = models.CharField(max_length=2, default='HR')
    fiscal_system = models.CharField(max_length=20, choices=[
        ('hr', 'Hrvatska (CIS/FINA)'),
        ('de', 'Njemačka (KassenSichV/TSE)'),
        ('at', 'Austrija (RKSV)'),
        ('si', 'Slovenija (FURS)'),
        ('eu', 'EU (XRechnung/PEPPOL)'),
    ], default='hr')
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'White Label konfiguracija'
        verbose_name_plural = 'White Label konfiguracije'

    def __str__(self):
        return f'{self.brand_name} ({self.company.name})'

    @property
    def entry_url(self):
        """URL za SmartEntry s ovim brendom."""
        if self.custom_domain:
            return f'https://{self.custom_domain}/pocni/'
        if self.subdomain:
            return f'https://{self.subdomain}.limit-connect.com/pocni/'
        return f'https://limit-connect.com/pocni/?brand={self.company.id}'
```

#### B2. Middleware: Brand Detection

```python
# core/middleware/__init__.py — dodati klasu

class WhiteLabelMiddleware:
    """
    Detektira white-label brand iz domene ili parametra.
    Postavlja request.white_label_config za template rendering.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from companies.models import WhiteLabelConfig
        host = request.get_host().split(':')[0].lower()
        
        config = None
        # Provjeri custom domenu
        if host not in ('limit-connect.com', 'www.limit-connect.com', '127.0.0.1', 'localhost'):
            try:
                config = WhiteLabelConfig.objects.select_related('company').get(
                    custom_domain=host, is_active=True
                )
            except WhiteLabelConfig.DoesNotExist:
                # Provjeri subdomain (adriatik.limit-connect.com)
                if host.endswith('.limit-connect.com'):
                    subdomain = host.replace('.limit-connect.com', '')
                    try:
                        config = WhiteLabelConfig.objects.select_related('company').get(
                            subdomain=subdomain, is_active=True
                        )
                    except WhiteLabelConfig.DoesNotExist:
                        pass
        
        # Provjeri ?brand= parametar (fallback)
        if not config:
            brand_id = request.GET.get('brand')
            if brand_id:
                try:
                    config = WhiteLabelConfig.objects.select_related('company').get(
                        company_id=brand_id, is_active=True
                    )
                except WhiteLabelConfig.DoesNotExist:
                    pass
        
        request.white_label = config
        return self.get_response(request)
```

#### B3. Template Context Processor

```python
# permissions/context_processors.py — dodati:

def white_label_context(request):
    """Injecira white label branding u sve templateove."""
    wl = getattr(request, 'white_label', None)
    if not wl:
        return {
            'wl_brand_name': 'LIMIT Connect',
            'wl_primary_color': '#1a3a6b',
            'wl_accent_color': '#c9a84c',
            'wl_logo': None,
            'wl_support_email': 'support@limit-connect.com',
            'wl_active': False,
        }
    return {
        'wl_brand_name': wl.brand_name,
        'wl_primary_color': wl.primary_color,
        'wl_accent_color': wl.accent_color,
        'wl_logo': wl.brand_logo.url if wl.brand_logo else None,
        'wl_support_email': wl.support_email or 'support@limit-connect.com',
        'wl_active': True,
        'wl_config': wl,
    }
```

#### B4. base.html integracija

```html
<!-- U <head> u base.html: -->
{% if wl_active %}
<style>
  :root {
    --brand-primary: {{ wl_primary_color }};
    --brand-accent: {{ wl_accent_color }};
  }
</style>
{% endif %}

<!-- Logo u headeru: -->
{% if wl_logo %}
  <img src="{{ wl_logo }}" alt="{{ wl_brand_name }}" height="40">
{% else %}
  LIMIT Connect  {# Defaultni brand #}
{% endif %}
```

#### B5. Migracija i setup

```bash
# Migracija
venv/bin/python manage.py makemigrations companies --name white_label_config
venv/bin/python manage.py migrate

# Test setup: Marija kao Distributor s white-label
venv/bin/python manage.py shell << 'PYEOF'
from companies.models import Company, WhiteLabelConfig

konjik = Company.objects.get(name__icontains='Konjik')
wl, created = WhiteLabelConfig.objects.get_or_create(
    company=konjik,
    defaults={
        'brand_name': 'Konjik ERP',
        'subdomain': 'konjik',
        'primary_color': '#1a3a6b',
        'accent_color': '#c9a84c',
        'billing_mode': 'platform',
        'distributor_commission_pct': 20,
        'default_language': 'hr',
        'default_country': 'HR',
        'fiscal_system': 'hr',
    }
)
print(f'WhiteLabel {"kreiran" if created else "postoji"}: {wl.brand_name}')
print(f'Entry URL: {wl.entry_url}')
PYEOF
```

---

### TASK C — CC_TASK_EU_COMPLIANCE_PAKETI.md

Za svako EU tržište treba "compliance paket" koji se uključuje uz white-label.

#### C1. Postojeće DE komponente (provjeriti i dokumentirati)

```bash
grep -rn "KassenSichV\|TSE\|DSFinV\|XRechnung\|ZUGFeRD\|RKSV\|FURS" /var/www/fina-connect --include="*.py" | grep -v venv | grep -v test
```

Već postoji:
- `pos/services/checkout.py` — KassenSichV adapter, TSE Fiskaly Cloud
- `pos/tse_adapter.py` (pretpostavljeno) — TSE integracija
- `einvoice/` — XRechnung, ZUGFeRD (u razvoju)
- `fiscal/` — HR fiskalizacija (kompletna)

#### C2. Compliance paketi po državi

Model: CompliancePackage (Companies mogu biti u više paketa)

```python
class CompliancePackage(models.Model):
    COUNTRY_CHOICES = [
        ('hr', 'Hrvatska'),
        ('de', 'Njemačka'),
        ('at', 'Austrija'),
        ('si', 'Slovenija'),
        ('eu', 'EU (generički)'),
    ]
    
    country = models.CharField(max_length=5, choices=COUNTRY_CHOICES)
    name = models.CharField(max_length=100)  # "KassenSichV 2.0 paket"
    description = models.TextField()
    
    # Što je uključeno
    includes_einvoice = models.BooleanField(default=False)
    includes_fiscal = models.BooleanField(default=False)
    includes_dsfin_export = models.BooleanField(default=False)
    includes_tse = models.BooleanField(default=False)
    includes_xrechnung = models.BooleanField(default=False)
    
    monthly_addon = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    
    class Meta:
        unique_together = [('country',)]
```

---

## FINANCIJSKA PROJEKCIJA — s posredničkim modelom

### Konzervativni scenarij (samo HR posrednici):
| Kvartal | Distributeri | Enterprise | Professional | MRR | Trošak | Dobit |
|---------|-------------|-----------|-------------|-----|--------|-------|
| Q1 2026 | 1 (359)     | 1 (189)   | 5 (345)     | 2.893 | 3.500 | -607 |
| Q2 2026 | 3 (1.077)   | 2 (378)   | 10 (690)    | 4.525 | 3.500 | +1.025 |
| Q3 2026 | 5 (1.795)   | 3 (567)   | 20 (1.380)  | 7.122 | 4.000 | +3.122 |
| Q4 2026 | 7 (2.513)   | 5 (945)   | 35 (2.415)  | 11.253 | 4.500 | +6.753 |

### Agresivni scenarij (HR + 1 EU partner Q3):
| Kvartal | HR MRR | EU licenca | Ukupno | Dobit |
|---------|--------|-----------|--------|-------|
| Q2 2026 | 4.525  | 0         | 4.525  | +1.025 |
| Q3 2026 | 7.122  | 1.000     | 8.122  | +4.122 |
| Q4 2026 | 11.253 | 2.000     | 13.253 | +8.753 |

---

## BORG ASIMILACIJA — Što BORG treba znati

Ovaj scenarij mijenja temeljni model platforme:

**PRIJE:** LIMIT Connect = ERP za krajnjeg korisnika
**POSLIJE:** LIMIT Connect = Platforma na kojoj drugi grade svoje ERP produkte

Arhitekturalne posljedice koje BORG mora pratiti:

1. **Multi-tenant branding** — ista baza, različiti brendovi, različiti UI
2. **Billing separacija** — Distributor mora vidjeti prihode od svojih klijenata
3. **Sub-umbrella model** — Distributor Zagreb ima pod sobom 50 firmi
4. **Compliance routing** — HR firma → HR fiscal, DE firma → KassenSichV
5. **SLA per tier** — EU partneri trebaju 99.9% uptime SLA (sad nemamo formalni)
6. **Data isolation** — EU GDPR zahtijeva podatke u EU (Hetzner Helsinki = OK)

---

## SLJEDEĆI KORACI (redoslijed)

### Odmah (ovaj tjedan):
1. [CC Code] WhiteLabelConfig model + middleware + context processor
2. [Gemini] Strateška analiza EU tržišta i competitive mapping
3. [Ivan] Kontaktirati 2-3 potencijalna HR Distributera (Split, Varaždin, Rijeka)

### Q2 2026:
4. Sub-billing modul (Distributor vidi prihode svojih klijenata)
5. Compliance paketi (DE, AT, SI)
6. Viskovic-bau.de → upgrade na EU white-label pilot klijent

### Q3 2026:
7. Formalni EU SaaS ugovor (NDA, SLA, DPA)
8. Prva EU white-label licenca
9. ISO 27001 gap analysis (priprema za formalni Informacijski posrednik)

---

## STATUS: BORG PRIMA — STRATEŠKA ANALIZA UGRAĐENA
## Implementacija: TaskA=Gemini, TaskB=CC Code, TaskC=CC Code (paralelno)
