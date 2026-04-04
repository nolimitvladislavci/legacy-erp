# CC_TASK_TAX_WIZARD_F1 — Infrastruktura
## Agent: Claude Code | Prioritet: P0 | Tjedan: 1-2

**Čitaj prvo:** TAX_WIZARD_MASTER_PLAN.md i FENIX_STATUS.md  
**Branch:** `feature/tax-wizard`  
**Ne diraj:** invoicing/, partners/, documents/ — samo čitaj iz njih

---

## MISIJA

Izgradi čvrstu infrastrukturu `tax_wizard` Django app-a.  
Sve ostalo (AI, UI, Stripe) stoji na ovome. Mora biti savršeno.

---

## KORAK 1 — Kreiraj app strukturu

```bash
cd /var/www/fina-connect
venv/bin/python manage.py startapp tax_wizard
```

Struktura koju moraš imati na kraju:
```
tax_wizard/
├── __init__.py
├── admin.py
├── apps.py
├── models.py          ← TaxWizardSession, PartnerTaxAccount
├── migrations/
├── prefill_engine.py  ← povlači podatke iz ERP-a
├── wizard_config.py   ← JSON config runner (kopira WizardDraft pattern)
├── deductions.py      ← PRAZNO, Gemini puni
├── ai_advisor.py      ← PRAZNO, Gemini puni  
├── views.py
├── urls.py
├── serializers.py
└── templates/
    └── tax_wizard/
        ├── wizard_base.html
        └── partner_dashboard.html
```

---

## KORAK 2 — Modeli (čitaj ovo pažljivo)

### TaxWizardSession

```python
class TaxWizardSession(models.Model):
    TAXPAYER_TYPES = [
        ('obrtnik_knjige', 'Obrtnik s poslovnim knjigama (DOH)'),
        ('zaposleni', 'Zaposlenik (ZPP-DOH)'),
        ('pausalist', 'Paušalni obrtnik (PO-SD)'),
        ('slobodna_zanimanja', 'Slobodna zanimanja'),
        ('mladi', 'Mladi do 30 godina (povrat)'),
        ('umirovljenik', 'Umirovljenik'),
    ]
    STATUS_CHOICES = [
        ('draft', 'U izradi'),
        ('confirmed', 'Potvrđeno'),
        ('submitted', 'Predano'),
        ('archived', 'Arhivirano'),
    ]
    
    id = UUIDField(primary_key=True, default=uuid4)
    company = FK('companies.Company', null=True, blank=True)  # ako je ERP korisnik
    partner_referral = FK('PartnerTaxAccount', null=True, blank=True)  # koja Marija je poslala
    
    # Identitet obveznika
    taxpayer_type = CharField(choices=TAXPAYER_TYPES)
    tax_year = IntegerField(default=2025)
    oib = CharField(max_length=11, blank=True)
    full_name = CharField(max_length=200, blank=True)
    jls_code = CharField(max_length=10, blank=True)  # šifra JLS za stopu poreza
    jls_rate = DecimalField(null=True, blank=True)    # lokalna porezna stopa
    
    # Wizard state
    current_step = IntegerField(default=0)
    step_data = JSONField(default=dict)      # odgovori korak po korak
    prefill_data = JSONField(default=dict)   # auto-povučeno iz ERP-a
    
    # Rezultati
    deductions_found = JSONField(default=list)   # lista pronađenih olakšica
    calculated_return = DecimalField(null=True)  # izračunati povrat/uplata
    tax_base = DecimalField(null=True)
    gross_income = DecimalField(null=True)
    
    # IntegrityHash chain (isti pattern kao ArhivaDocument)
    integrity_chain = CharField(max_length=64, blank=True)
    
    # Status i audit
    status = CharField(choices=STATUS_CHOICES, default='draft')
    ip_address = GenericIPAddressField(null=True)
    user_agent = CharField(max_length=500, blank=True)
    tc_accepted = BooleanField(default=False)
    tc_accepted_at = DateTimeField(null=True)
    
    # Output
    submitted_at = DateTimeField(null=True)
    submitted_xml = TextField(blank=True)    # ePorezna XML
    audit_pdf = FileField(null=True)         # potpisani PDF za arhivu
    
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
    
    def update_integrity_chain(self, new_data: dict):
        """
        Svaki save-step MORA proći kroz ovo.
        Kopiraj logiku iz documents/models.py compute_integrity_hash()
        ali kao chain: hash(prethodni_hash + json(novi_podaci) + timestamp)
        """
        import hashlib, json
        payload = f"{self.integrity_chain}|{json.dumps(new_data, sort_keys=True)}|{timezone.now().isoformat()}"
        self.integrity_chain = hashlib.sha256(payload.encode()).hexdigest()
        self.save(update_fields=['integrity_chain', 'updated_at'])
```

### PartnerTaxAccount

```python
class PartnerTaxAccount(models.Model):
    """Računovođa koji distribuira tax wizard kao white-label"""
    
    company = OneToOneField('companies.Company', on_delete=CASCADE)
    
    # White-label branding
    brand_name = CharField(max_length=200)  # "Konjik Tax Assistant"
    brand_logo = ImageField(null=True, blank=True)
    brand_color = CharField(max_length=7, default='#1e3a5f')  # hex
    
    # Distribucija
    referral_code = CharField(max_length=20, unique=True)  # auto-generiran
    referral_url = CharField(max_length=500, blank=True)   # /tax/ref/{code}/
    
    # Monetizacija
    commission_rate = DecimalField(default=Decimal('0.30'))  # 30%
    stripe_connect_id = CharField(max_length=100, blank=True)
    
    # Statistike
    clients_sent = IntegerField(default=0)
    clients_completed = IntegerField(default=0)
    total_earned = DecimalField(default=Decimal('0'))
    
    is_active = BooleanField(default=True)
    created_at = DateTimeField(auto_now_add=True)
    
    def generate_referral_code(self):
        """Generiraj jedinstveni kod iz naziva firme"""
        import secrets
        base = self.company.name[:6].upper().replace(' ', '')
        return f"{base}{secrets.token_hex(3).upper()}"
    
    def save(self, *args, **kwargs):
        if not self.referral_code:
            self.referral_code = self.generate_referral_code()
        super().save(*args, **kwargs)
```

---

## KORAK 3 — prefill_engine.py (NAJVAŽNIJI DIO)

Ovo je naš moat. Pažljivo.

```python
"""
prefill_engine.py

Povlači podatke iz ERP modula i pre-popunjava TaxWizardSession.
Korisnik samo verificira — ne tipka ništa što već postoji u sustavu.
"""
from decimal import Decimal
from django.db.models import Sum, Q
from invoicing.models import Invoice
from konto.models import TaxPeriod
from payroll.models import Payslip


def prefill_for_obrtnik_knjige(session: 'TaxWizardSession') -> dict:
    """
    Za obrtnike s knjigama — DOH obrazac.
    Povlači: primitke, izdatke, plaće, amortizaciju
    """
    company = session.company
    year = session.tax_year
    
    if not company:
        return {}
    
    result = {}
    
    # 1. Ukupni primitci iz faktura (Invoicing modul)
    invoices = Invoice.objects.filter(
        company=company,
        date_issued__year=year,
        doctype__in=['R', 'FA'],  # računi i fakture
        status__in=['PAID', 'SENT', 'CONFIRMED'],
    )
    total_income = invoices.aggregate(s=Sum('subtotal'))['s'] or Decimal('0')
    result['ukupni_primici'] = total_income
    result['broj_faktura'] = invoices.count()
    
    # 2. PDV period za godinu — izdaci i prihodi
    tax_period = TaxPeriod.objects.filter(
        company=company,
        year=year,
        period_type='annual'
    ).first()
    
    if tax_period:
        result['ukupni_prihodi_konto'] = tax_period.total_revenue
        result['ukupni_rashodi_konto'] = tax_period.total_expenses
    
    # 3. Plaće (ako zapošljava radnike)
    payslips = Payslip.objects.filter(
        payroll_run__company=company,
        payroll_run__period_start__year=year,
    )
    total_gross = payslips.aggregate(s=Sum('gross_amount'))['s'] or Decimal('0')
    result['ukupne_place_bruto'] = total_gross
    result['broj_radnika'] = payslips.values('user').distinct().count()
    
    # 4. Označi izvor svakog podatka za UI
    result['_sources'] = {
        'ukupni_primici': f'Invoicing — {invoices.count()} faktura za {year}.',
        'ukupne_place_bruto': f'Payroll — {result["broj_radnika"]} radnika.',
    }
    
    return result


def prefill_for_zaposleni(session: 'TaxWizardSession') -> dict:
    """
    Za zaposlenike — ZPP-DOH.
    Samo olakšice koje PU ne zna: djeca, darovanja, invaliditet.
    Nema ERP podataka — ručni unos, ali sa pametnim pitanjima.
    """
    return {
        'tip': 'zaposleni',
        'napomena': 'Nema ERP podataka za zaposlenike. Wizard pita korak po korak.',
    }


def prefill_session(session: 'TaxWizardSession') -> None:
    """
    Glavni entry point. Poziva se odmah po kreiranju sesije.
    """
    dispatch = {
        'obrtnik_knjige': prefill_for_obrtnik_knjige,
        'slobodna_zanimanja': prefill_for_obrtnik_knjige,  # isti obrazac
        'zaposleni': prefill_for_zaposleni,
        'mladi': prefill_for_zaposleni,
        'pausalist': lambda s: {},  # PO-SD — posebna logika
        'umirovljenik': prefill_for_zaposleni,
    }
    
    fn = dispatch.get(session.taxpayer_type, lambda s: {})
    data = fn(session)
    
    session.prefill_data = data
    session.gross_income = data.get('ukupni_primici', None)
    session.save(update_fields=['prefill_data', 'gross_income', 'updated_at'])
```

---

## KORAK 4 — wizard_config.py (JSON engine)

```python
"""
wizard_config.py

JSON-driven wizard engine. Promjena zakona = promjena JSON, ne Python koda.
"""

WIZARD_STEPS = {
    'obrtnik_knjige': [
        {
            'id': 'tc_accept',
            'title': 'Uvjeti korištenja',
            'type': 'consent',
            'text': 'Ovaj alat je kalkulator. Odgovornost za točnost i zakonitost isključivo je na poreznom obvezniku.',
            'required': True,
        },
        {
            'id': 'osnovni_podaci',
            'title': 'Osnovni podaci',
            'fields': [
                {'id': 'oib', 'type': 'oib', 'label': 'OIB'},
                {'id': 'jls_code', 'type': 'jls_select', 'label': 'Grad/Općina'},
                {'id': 'tax_year', 'type': 'year_select', 'label': 'Porezna godina'},
            ],
        },
        {
            'id': 'primici_izdaci',
            'title': 'Primitci i izdaci',
            'prefill_from': 'ukupni_primici',
            'fields': [
                {'id': 'ukupni_primici', 'type': 'currency', 'label': 'Ukupni primitci (bez PDV-a)', 'editable': True},
                {'id': 'ukupni_izdaci', 'type': 'currency', 'label': 'Ukupni izdaci', 'editable': True},
                {'id': 'amortizacija', 'type': 'currency', 'label': 'Amortizacija dugotrajne imovine', 'editable': True},
            ],
            'ai_hint': 'Vidim {ukupni_primici}€ iz tvojih faktura u {tax_year}. Potvrdi ili ispravi.',
        },
        {
            'id': 'olaksice_scan',
            'title': 'Provjera olakšica',
            'type': 'ai_scan',
            'runs': 'deductions.scan_all',
            'message': 'Provjeravam {count} zakonskih olakšica...',
            'result_message': 'Pronašao sam {found} primjenjivih olakšica. Potencijalna ušteda: {savings}€',
        },
        {
            'id': 'pregled',
            'title': 'Pregled i potvrda',
            'type': 'review',
            'shows': ['izracun_poreza', 'povrat_uplata', 'olaksice_lista'],
        },
    ],
    
    'zaposleni': [
        # ZPP-DOH tijek — kraći, 3 koraka
        {'id': 'tc_accept', 'type': 'consent', 'title': 'Uvjeti korištenja'},
        {
            'id': 'osobne_olaksice',
            'title': 'Olakšice za koje PU nema podatke',
            'fields': [
                {'id': 'djeca_broj', 'type': 'integer', 'label': 'Broj uzdržavane djece'},
                {'id': 'invaliditet', 'type': 'boolean', 'label': 'Vlastiti invaliditet ili člana obitelji?'},
                {'id': 'darovanja', 'type': 'currency', 'label': 'Darovanja udrugama u 2025.'},
                {'id': 'bio_inozemstvo', 'type': 'boolean', 'label': 'Boravio 2+ god. u inozemstvu i vratio se?'},
                {'id': 'dob', 'type': 'integer', 'label': 'Godina rođenja (provjera mladenačke olakšice)'},
            ],
        },
        {'id': 'pregled', 'type': 'review', 'title': 'Pregled i potvrda'},
    ],
}
```

---

## KORAK 5 — URL routing

Dodaj u `core/urls.py` (u `i18n_patterns`):
```python
path('tax/', include('tax_wizard.urls', namespace='tax_wizard')),
```

`tax_wizard/urls.py`:
```python
urlpatterns = [
    path('', views.wizard_home, name='home'),
    path('ref/<str:code>/', views.wizard_referral, name='referral'),
    path('session/<uuid:session_id>/', views.wizard_step, name='step'),
    path('session/<uuid:session_id>/save/', views.save_step, name='save_step'),
    path('session/<uuid:session_id>/pdf/', views.download_pdf, name='pdf'),
    path('partner/', views.partner_dashboard, name='partner_dashboard'),
    path('partner/setup/', views.partner_setup, name='partner_setup'),
    path('api/jls/', views.jls_list, name='jls_api'),  # 574 JLS za dropdown
]
```

---

## KORAK 6 — Admin

Registriraj oba modela u admin s:
- `list_display`: session_id, taxpayer_type, status, calculated_return, partner_referral
- `search_fields`: oib, full_name
- `list_filter`: taxpayer_type, status, tax_year

---

## KORAK 7 — Test

```bash
venv/bin/python manage.py test tax_wizard --verbosity=2
```

Testovi koje moraš napisati:
1. `test_integrity_chain_tamper_evident` — promijeni step_data direktno u bazi, provjeri da hash ne odgovara
2. `test_prefill_obrtnik` — kreiraj session za Konjik, provjeri da se primitci povuku iz Invoicing
3. `test_partner_referral_code_unique` — kreiraj 10 PartnerTaxAccount, provjeri da su svi kodovi jedinstveni

---

## ZABRANE

- NE mijenjaš invoicing/, documents/, partners/
- NE koristiš `manage.py migrate` bez da provjeriš da nema konflikta
- NE dodaješ Stripe logiku — to dolazi u F3
- NE dodaješ UI template iznad skeleton `wizard_base.html`

---

## DONE kriterij

```bash
venv/bin/python manage.py migrate tax_wizard && echo "MIGRATIONS OK"
venv/bin/python manage.py test tax_wizard && echo "TESTS OK"
curl https://limit-connect.com/hr/tax/ -sI | grep "200 OK"
```

Sva 3 zelena = F1 završena. Ažuriraj FENIX_STATUS.md.
