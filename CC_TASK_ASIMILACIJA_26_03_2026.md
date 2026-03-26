# CC TASK: Asimilacija 26.03.2026 — Tax Wizard Global + Worktime Mine + Zadruge + POS Sim
## Agent: CC Code | Prioritet: VISOK | Datum: 2026-03-26
## Naručuje: Sonnet (koordinator) — Ivanova odobrena sesija

---

## OBAVEZNO PROČITAJ PRVO (ne preskači)

```bash
cat FENIX_STATUS.md | head -50
git log --oneline -10
venv/bin/python manage.py check
```

---

## KONTEKST — ŠTO JE DOVRŠENO DANAS

### Udruge (CC Code, 9.5/10 — DONE, NE DIRAJ)
- StatusBranitelja, OdlikovanjeBranitelja modeli + views + templates
- Loviste, LovackaIskaznica, DopustenjeLova, ZapisnikLova, Trofej + views + templates
- 10 dashboardova: DVD, KUD, Ribolov, Pčelari, Rakija, Voćari, Branitelji, Lov
- 17 testova (15 pass, 2 SQLite teardown)

### Tax Wizard (Sonnet, DONE)
- 6 TaxFormTemplate: PO-SD, DOH, EÜR, AnlageV, UStVA, JOPPD
- 7 TaxDeadline za 2026 (HR + DE)
- PricingPlan: Porezni Godišnji 49 EUR/god
- 7 firmi aktivirano u CompanyModuleConfig

### Rental + Sati (Sonnet, DONE)
- Property.owner FK (razlika radnik/iznajmljivač)
- Ilija Šošić registriran (user pk=1326)

---

## TASK 1 — Tax Wizard Globalni Widget (VISOK)

### Što graditi
Jedan Django template tag / include koji se poziva iz SVAKE forme koja dirne novac.

### Implementacija

```python
# tax_wizard/templatetags/tax_wizard_tags.py

from django import template
from django.utils import timezone
from tax_wizard.models import TaxDeadline, TaxFormTemplate

register = template.Library()

@register.inclusion_tag('tax_wizard/_widget.html', takes_context=True)
def tax_wizard_widget(context, context_type='general', amount=None):
    """
    Globalni porezni widget — poziva se iz svake forme.

    context_type opcije:
      'invoice'  — faktura kreirana/plaćena
      'pos'      — POS Z-report
      'rental'   — booking potvrđen
      'worktime' — period zatvoren
      'general'  — dashboard

    Detekcija:
      - company.business_type + company.country → koji obrasci su relevantni
      - Provjeri nadolazeće deadline (≤30 dana)
      - Provjeri quarterly trigger (svaki put kad suma faktura prelazi prag)
    """
    request = context.get('request')
    if not request or not request.user.is_authenticated:
        return {'show': False}

    try:
        from accounts.models import UserProfile
        up = UserProfile.objects.select_related('company').get(user=request.user)
        company = up.company
    except Exception:
        return {'show': False}

    today = timezone.now().date()

    # Deadline upozorenja (≤30 dana)
    upcoming = TaxDeadline.objects.filter(
        company=company,
        deadline_date__gte=today,
        deadline_date__lte=today.replace(day=today.day) + timezone.timedelta(days=30),
        is_filed=False,
    ).select_related('template').order_by('deadline_date')[:3]

    # Relevantni obrasci za ovu firmu
    country = getattr(company, 'country', 'HR') or 'HR'
    btype = company.business_type or 'doo'

    relevant_templates = TaxFormTemplate.objects.filter(
        is_active=True,
        applicable_countries__contains=[country],
    ).exclude(
        applicable_business_types__len__gt=0
    )[:5]

    # Trigger: faktura/POS prijevazilazi kvartal?
    trigger_message = None
    if context_type == 'invoice' and amount and company.business_type in ['obrt','pausalni_obrt']:
        # PO-SD Q prag: 6.000 EUR kvartal (75k/god / 4)
        # Ako amount > 5000 EUR → upozori
        if float(amount or 0) > 5000:
            trigger_message = 'Dostigao si značajan promet — provjeri PO-SD obračun!'

    return {
        'show': bool(upcoming or trigger_message),
        'upcoming_deadlines': upcoming,
        'trigger_message': trigger_message,
        'wizard_url': '/porezni-savjetnik/',
        'context_type': context_type,
        'company': company,
    }
```

### Template

Napravi `tax_wizard/templates/tax_wizard/_widget.html`:

```html
{% if show %}
<div class="tax-wizard-widget alert alert-warning border-start border-warning border-3 p-2 mb-3"
     style="background:rgba(201,146,42,0.08);border-color:var(--gold) !important;">
  <div class="d-flex align-items-center gap-2">
    <span style="font-size:1.3rem;">📋</span>
    <div class="flex-grow-1">
      {% if trigger_message %}
        <strong>{{ trigger_message }}</strong>
      {% endif %}
      {% for d in upcoming_deadlines %}
        <div class="small">
          <strong>{{ d.template.form_type }}</strong>
          — rok: <strong>{{ d.deadline_date|date:"d.m.Y." }}</strong>
          ({{ d.deadline_date|timeuntil }} preostalo)
        </div>
      {% endfor %}
    </div>
    <a href="{{ wizard_url }}" class="btn btn-sm btn-warning">
      Otvori →
    </a>
  </div>
</div>
{% endif %}
```

### Gdje ga pozvati (dodaj `{% load tax_wizard_tags %}` i `{% tax_wizard_widget ... %}`)

| Template | Poziv |
|----------|-------|
| `invoicing/templates/invoicing/invoice_list.html` | `{% tax_wizard_widget 'invoice' %}` |
| `invoicing/templates/invoicing/create.html` | `{% tax_wizard_widget 'invoice' amount=invoice.total %}` |
| `pos/templates/pos/z_report.html` | `{% tax_wizard_widget 'pos' %}` |
| `rental/templates/rental/booking_confirm.html` | `{% tax_wizard_widget 'rental' %}` |
| `worktime/templates/worktime/manager_timesheet.html` | `{% tax_wizard_widget 'worktime' %}` |
| `templates/base.html` — sidebar section | `{% tax_wizard_widget 'general' %}` (samo ako has deadline)  |
| `udruge/templates/udruge/*/dashboard.html` — svi dashboardi | `{% tax_wizard_widget 'general' %}` |

### Done kriterij
```bash
venv/bin/python manage.py check
grep "tax_wizard_widget" invoicing/templates/invoicing/create.html
grep "tax_wizard_widget" templates/base.html
ls tax_wizard/templatetags/tax_wizard_tags.py
```

---

## TASK 2 — Worktime /mine/ Mobilna Stranica (VISOK)

### Zakonska obveza
HR: ZOR + NN 73/2017 — radnik ima pravo uvida u vlastitu evidenciju
DE: ArbZG §16 + BAG 2022 — elektronička evidencija + uvid obvezni

### Što graditi

Nova URL: `path('mine/', views.worker_mine, name='ts_mine')`

```python
# worktime/timesheet_views.py — dodaj na kraj

@login_required
def worker_mine(request):
    """
    /worktime/mine/ — mobilna stranica SAMO za radnika.
    Prikazuje: ovaj tjedan, ovaj mjesec, pregled po danima.
    Ne prikazuje: tuđe sate, satnice, financijske podatke.
    Zakon: ZOR + ArbZG §16 — pravo uvida u vlastite sate.
    """
    from worktime.models import TimeEntry, EmployeeProfile
    from django.utils import timezone
    from datetime import timedelta

    company = _user_company(request)
    today = timezone.now().date()

    # Ovaj tjedan (pon-ned)
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    # Ovaj mjesec
    month_start = today.replace(day=1)

    week_entries = TimeEntry.objects.filter(
        user=request.user,
        company=company,
        date__range=(week_start, week_end),
    ).order_by('-date', 'start_time')

    month_entries = TimeEntry.objects.filter(
        user=request.user,
        company=company,
        date__range=(month_start, today),
    ).order_by('-date')

    # Sume
    from decimal import Decimal
    week_hours = sum((e.duration or Decimal('0')) for e in week_entries)
    month_hours = sum((e.duration or Decimal('0')) for e in month_entries)

    # EmployeeProfile za ugovoreni fond
    try:
        ep = EmployeeProfile.objects.get(user=request.user, company=company)
        weekly_target = ep.weekly_hours
        monthly_target = weekly_target * 4
    except EmployeeProfile.DoesNotExist:
        weekly_target = Decimal('40')
        monthly_target = Decimal('160')

    return render(request, 'worktime/worker_mine.html', {
        'week_entries': week_entries,
        'month_entries': month_entries,
        'week_hours': week_hours,
        'month_hours': month_hours,
        'weekly_target': weekly_target,
        'monthly_target': monthly_target,
        'week_start': week_start,
        'week_end': week_end,
        'today': today,
    })
```

### Template `worktime/templates/worktime/worker_mine.html`

Mobilni dizajn — kopiraj stil iz `worker_dashboard.html`. Treba:
- Header: "Moji sati — {{ request.user.get_full_name }}"
- 2 kartice: OVAJ TJEDAN (X/Y h) | OVAJ MJESEC (X/Y h)
- Progress bar: week_hours / weekly_target
- Tablica dana: Datum | Projekt | Sati | Status badge
- Gumb: "Preuzmi PDF" → `/worktime/pdf/?user_only=1`
- **Nema satnice, nema iznosa, nema tuđih sati**
- Mobile-first: `<meta name="viewport">`, čist CSS, touch-friendly

### URL dodati u worktime/urls.py
```python
path('mine/', timesheet_views.worker_mine, name='ts_mine'),
```

### DeviceToken — link nakon logina
U `accounts/auth_views.py` nakon device_login_start_all():
```python
# Dodaj link koji se šalje korisniku
result['mine_url'] = '/worktime/mine/'
```

### Done kriterij
```bash
curl -sI https://limit-connect.com/hr/worktime/mine/ | head -3
grep "worker_mine" worktime/urls.py
ls worktime/templates/worktime/worker_mine.html
```

---

## TASK 3 — Zadruge Modul (SREDNJI)

### Zakon
Zakon o zadrugama HR (NN 76/14, izmjene 2018):
- Imenik zadrugara — Pravilnik NN 56/12 (obvezna knjiga!)
- Zadružna revizija svake 2 godine
- Zadrugar ≠ Clan udruge — ima uloge, udjele, prinos

### Kontekst
Zadruga je registrirana u SUDSKOM REGISTRU (ne registar udruga).
Ima poslovne karakteristike d.o.o.-a + zadružne principe.
NE koristiti Clan model iz udruga — kreirati zasebni Zadrugar model.

### Što graditi

```python
# Novi fajl: zadruge/models.py  (ZASEBNA APP, ne dio udruge)
# ili: dodati u udruge/models.py s jasnim separatorom

class Zadrugar(models.Model):
    """
    Zadrugar — član zadruge.
    Zakon o zadrugama NN 76/14 + Pravilnik o imeniku NN 56/12.
    NIJE isti kao Clan udruge — ima uloge + financijska prava.
    """
    ULOGA_CHOICES = [
        ('osnivac',        'Osnivač'),
        ('redovni',        'Redovni zadrugar'),
        ('pridruzeni',     'Pridruženi zadrugar'),
        ('pocasni',        'Počasni zadrugar'),
        ('pocasni_clan',   'Počasni član'),
    ]
    STATUS_CHOICES = [
        ('aktivan',        'Aktivan'),
        ('mirovanje',      'Mirovanje'),
        ('istupio',        'Istupio'),
        ('iskljucen',      'Isključen'),
    ]

    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                                related_name='zadrugari')
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    oib = models.CharField(max_length=11, blank=True)
    adresa = models.TextField(blank=True)
    datum_pristupanja = models.DateField()
    datum_istupanja = models.DateField(null=True, blank=True)
    uloga = models.CharField(max_length=20, choices=ULOGA_CHOICES, default='redovni')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='aktivan')

    # Financijska polja (Imenik zadrugara NN 56/12)
    clanski_ulog_eur = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                            verbose_name='Članski ulog (EUR)')
    udjeli_postotak = models.DecimalField(max_digits=6, decimal_places=4, default=0,
                                           verbose_name='Udjeli (%)')
    ukupni_prinos_eur = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                                             verbose_name='Ukupni prinos (EUR)')
    zadnji_prinos_godina = models.PositiveSmallIntegerField(null=True, blank=True)

    # Kontakt
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)

    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'udruge_zadrugar'
        verbose_name = 'Zadrugar'
        ordering = ['last_name', 'first_name']
        unique_together = [('company', 'oib')]

    def __str__(self):
        return f'{self.last_name} {self.first_name}'

    @property
    def puno_ime(self):
        return f'{self.first_name} {self.last_name}'


class ZadruznRevizija(models.Model):
    """
    Zadružna revizija — obveza svake 2 godine (Zakon o zadrugama).
    Obavlja je ovlašteni revizor iz Hrvatskog saveza zadruga.
    """
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                                related_name='zadruznrevizije')
    godina = models.PositiveSmallIntegerField(verbose_name='Godina revizije')
    revizor_ime = models.CharField(max_length=200, verbose_name='Ime revizora')
    revizor_firma = models.CharField(max_length=200, blank=True, verbose_name='Revizorska firma')
    datum_pocetak = models.DateField(verbose_name='Datum početka revizije')
    datum_zavrsetak = models.DateField(null=True, blank=True)
    nalaz = models.TextField(blank=True, verbose_name='Nalaz revizije')
    ocjena = models.CharField(max_length=20, choices=[
        ('uredna', 'Poslovanje uredno'),
        ('napomene', 'S napomenama'),
        ('neuredna', 'Neuredna'),
    ], blank=True)
    izvjestaj_pdf = models.FileField(upload_to='zadruge/revizija/%Y/', blank=True)
    sljedeca_revizija = models.DateField(null=True, blank=True,
                                          verbose_name='Sljedeća revizija do')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'udruge_zadruzna_revizija'
        verbose_name = 'Zadružna revizija'
        ordering = ['-godina']

    def save(self, *args, **kwargs):
        # Automatski izračunaj datum sljedeće revizije (2 godine)
        if self.datum_zavrsetak and not self.sljedeca_revizija:
            from dateutil.relativedelta import relativedelta
            self.sljedeca_revizija = self.datum_zavrsetak + relativedelta(years=2)
        super().save(*args, **kwargs)
```

### Migracija
```bash
venv/bin/python manage.py makemigrations udruge --name="zadruge_zadrugar_revizija"
venv/bin/python manage.py migrate udruge
```

### Views i URL-ovi
```python
# udruge/views.py — dodaj na kraj

@login_required
def zadruge_dashboard(request):
    """Dashboard za zadrugu."""
    company = get_user_company(request)
    from .models import Zadrugar, ZadruznRevizija
    zadrugari = Zadrugar.objects.filter(company=company, status='aktivan')
    ukupni_ulozi = zadrugari.aggregate(sum=models.Sum('clanski_ulog_eur'))['sum'] or 0
    zadnja_revizija = ZadruznRevizija.objects.filter(company=company).first()

    return render(request, 'udruge/zadruge_dashboard.html', {
        'zadrugari': zadrugari.order_by('-udjeli_postotak'),
        'ukupni_ulozi': ukupni_ulozi,
        'zadnja_revizija': zadnja_revizija,
        'stats': {
            'ukupno': zadrugari.count(),
            'osnivaci': zadrugari.filter(uloga='osnivac').count(),
            'prosjecni_udjel': float(ukupni_ulozi / max(zadrugari.count(), 1)),
        }
    })

# + zadrugar_list, zadrugar_create, zadrugar_edit, revizija_list, revizija_create
```

URL-ovi:
```python
path('zadruge/', views.zadruge_dashboard, name='zadruge_dashboard'),
path('zadruge/zadrugari/', views.zadrugar_list, name='zadrugar_list'),
path('zadruge/zadrugari/create/', views.zadrugar_create, name='zadrugar_create'),
path('zadruge/revizije/', views.revizija_list, name='revizija_list'),
path('zadruge/revizije/create/', views.revizija_create, name='revizija_create'),
```

### Template zadruge_dashboard.html
Kopirati strukturu `ribolov_dashboard.html`. Stat kartice:
- Zadrugari ukupno | Osnivači | Ukupni ulozi (EUR) | Sljedeća revizija

---

## TASK 4 — POS Simulacija Popravak (VISOK)

### Problem
`scripts/pos_sim_all.py` pada zbog `receipt_number` koji je `PositiveIntegerField`, a skripta šalje string.

### Provjeri trenutno stanje
```bash
venv/bin/python -c "
import django,os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','core.settings'); django.setup()
from pos.models import POSReceipt, POSSession
print('receipt_number type:', POSReceipt._meta.get_field('receipt_number').__class__.__name__)
# Provjeri next_receipt_num
import inspect
from pos.models import POSReceipt as R
if hasattr(R,'next_receipt_num'): print('next_receipt_num postoji')
"
head -100 scripts/pos_sim_all.py
```

### Fix
1. U svakom scenariju gdje se kreira `POSReceipt`, pozovi `next_receipt_num()` ili koristi auto-increment:
```python
# Umjesto:
receipt_number='SIM-001'

# Koristiti:
from pos.models import POSReceipt
last = POSReceipt.objects.filter(company=company).order_by('-receipt_number').first()
next_num = (last.receipt_number + 1) if last and last.receipt_number else 1

# Ili ako postoji metoda:
receipt_number = POSReceipt.get_next_number(company=company, terminal=terminal)
```

2. Provjeri `opening_cash` duplikat u POSSession create.
3. Pokreni sve 6 scenarija:
```bash
venv/bin/python scripts/pos_sim_all.py
```
4. Spremi output u `POS_SIM_REPORT_20260326.md`.

---

## TASK 5 — Worktime /mine/ PDF endpoint (SREDNJI)

Postojeći `/worktime/pdf/` treba podržati `?user_only=1` parametar:
- Ako `user_only=1` → prikazuje samo sate prijavljenog usera
- Bez satnica, bez financijskih podataka (zakonska zaštita osobnih podataka)
- Format: jednostavan A4, ime radnika, period, dan-po-dan pregled

---

## TASK 6 — Porezni Savjetnik Sidebar Link (NIZAK)

U `templates/base.html` sidebar — dodaj link na `/porezni-savjetnik/` za sve firme
koje imaju `tax_wizard` u `CompanyModuleConfig.enabled_modules`.

```html
{% if 'tax_wizard' in user_modules %}
<li class="nav-item">
  <a class="nav-link {% if request.path|startswith:'/porezni-savjetnik' %}active{% endif %}"
     href="{% url 'tax_wizard:dashboard' %}">
    <i class="fas fa-file-invoice-dollar me-2"></i>
    <span>Porezni Savjetnik</span>
    {% if tax_upcoming_count %}<span class="badge bg-warning text-dark ms-1">{{ tax_upcoming_count }}</span>{% endif %}
  </a>
</li>
{% endif %}
```

---

## DONE KRITERIJ — cijeli task

```bash
# 1. Tax wizard widget
grep "tax_wizard_widget" invoicing/templates/invoicing/create.html
ls tax_wizard/templatetags/tax_wizard_tags.py

# 2. Worktime mine
curl -sI https://limit-connect.com/hr/worktime/mine/ | head -3
ls worktime/templates/worktime/worker_mine.html

# 3. Zadruge
venv/bin/python manage.py migrate udruge --check
grep "class Zadrugar\|class ZadruznRevizija" udruge/models.py

# 4. POS sim
cat POS_SIM_REPORT_20260326.md | head -20

# 5. Testovi
venv/bin/python manage.py test udruge.tests --verbosity=1 --no-input 2>&1 | tail -3

# 6. FENIX_STATUS update
grep "tax_wizard_widget\|worker_mine\|Zadrugar" FENIX_STATUS.md
```

---

## NAPOMENE

1. **PROČITAJ models.py PRIJE pisanja koda** — ne pretpostavljaj nazive polja
2. Zadruge su u `udruge/models.py` (ista app, novi model) — ne krei novu app
3. Tax widget templatetags — napravi `tax_wizard/templatetags/__init__.py` ako ne postoji
4. worker_mine ne prikazuje NIŠTA financijsko — to je zakonska obveza
5. Commit svaki task zasebno s opisnim porukom
6. Ažuriraj `FENIX_STATUS.md` na kraju

---

## REDOSLIJED IZVRŠAVANJA

```
1. Tax Wizard Widget (templatetags + 6 mjesta pozivanja)  → commit
2. Worktime /mine/                                         → commit
3. Zadruge (Zadrugar + ZadruznRevizija + views + 3 tmpl)  → commit
4. POS Sim fix + run                                       → commit
5. Sidebar link                                            → commit
6. FENIX_STATUS.md ažurirati                              → commit
```
