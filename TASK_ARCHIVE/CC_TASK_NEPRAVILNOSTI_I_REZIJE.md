# CC_TASK: DVIJE ZAKONSKE NEPRAVILNOSTI + REŽIJE MODUL
# Datum: 04.04.2026. | Rok: 07.04.2026. | Prioritet: P0
#
# Zakonska osnova:
#   Zakon o PDV-u NN 73/2013, čl. 79 — porezna obveza nastaje računom, ne ponudom
#   Zakon o radu NN 93/2014, čl. 94 st. 2 — prekovremeni rad min 50%
#   Zakon o računovodstvu NN 78/2015 — evidencija troškova
#   Zakon o energiji NN 120/2012 — evidencija potrošnje energenata

PRAVILO: READ models.py PRVO. select_for_update() za Konto operacije.
PRAVILO: Zakon o radu je prisilni propis — ne može se ugovorom smanjiti ispod minimuma.
PRAVILO: venv/bin/python manage.py check 2>&1 | tail -3 nakon svake izmjene.

---

## DIO 1 — ZAKONSKE NEPRAVILNOSTI

### 1A: PDV-S — ukloni ponude i predračune

READ: pdv_s/service.py (linija ~184)
READ: pdv_s/views.py (linija ~41)

Problem: `doctype__in=['R', 'PO', 'P', 'A', 'FA', 'RN', 'IRA']`
'PO' = Ponuda, 'P' = Predračun — nisu porezni dokumenti.

```bash
grep -n "doctype__in" pdv_s/service.py pdv_s/views.py | head -10
```

FIX — u OBJEMA datotekama zamijeni:
```python
# STARO:
doctype__in=['R', 'PO', 'P', 'A', 'FA', 'RN', 'IRA']

# NOVO (Zakon o PDV-u čl.79 — samo pravi računi):
doctype__in=['R', 'A', 'FA', 'RN']
# Objašnjenje:
# R   = Račun                    ✅ oporezivo
# A   = Avansni račun            ✅ oporezivo (PDV pri primitku predujma)
# FA  = Faktura B2B              ✅ oporezivo
# RN  = Račun gotovina           ✅ oporezivo
# PO  = Ponuda                   ❌ nije račun
# P   = Predračun/Predujam       ❌ nije račun (P ≠ A!)
# IRA = legacy oznaka            ❌ nekonzistentno s DOCTYPE_CHOICES
```

DODAJ komentar iznad svakog:
```python
# Zakon o PDV-u NN 73/2013, čl. 79: porezna obveza nastaje ispostavljanjem računa.
# Ponude (PO), predračuni (P) i narudžbenice (NAR) nisu porezni dokumenti.
```

Provjeri URA stranu:
```bash
grep -n "URA\|doctype.*URA\|invoice_in" pdv_s/ -r --include="*.py" | head -10
```
URA = ulazni računi → OK, oporezivo pretporezom.

### 1B: Overtime default — min 50% po ZOR

READ: worktime/models.py (overtime_rate field i calculate_payroll metoda)

```bash
grep -n "overtime_rate\|ot_rate\|Decimal.*30\|30.*posto" worktime/models.py | head -10
```

FIX — worktime/models.py:

```python
# STARO:
overtime_rate = models.DecimalField(
    max_digits=10, decimal_places=2, default=Decimal('30.00'))

# NOVO — ZOR čl. 94 st.2: min 50%
overtime_rate = models.DecimalField(
    max_digits=10, decimal_places=2, default=Decimal('50.00'),
    help_text=(
        'Postotak povećanja za prekovremeni rad. '
        'Minimum 50% po čl. 94 Zakona o radu (NN 93/2014). '
        'Kolektivni ugovor može odrediti veći postotak.'
    )
)
```

U calculate_payroll() i auto_split_hours() — ZAMIJENI hardkodirane fallback vrijednosti:
```python
# STARO:
ot_rate = Decimal('30')
# NOVO:
ot_rate = Decimal('50')  # ZOR čl. 94 minimum
```

Provjeri noćni rad:
```bash
grep -n "night.*bonus\|0\.25\|25.*nocni" worktime/models.py | head -5
```
Noćni rad 25% — ZOR čl. 91 minimum je 25% (OK za default, ali dodaj napomenu).

MIGRACIÓN za overtime_rate (samo default promjena, ne shema):
```bash
# Nema migracije — samo default u Pythonu, ne u bazi
# Ali postojeći EmployeeProfile zapisi s overtime_rate=30 ostaju
# Dodaj data migration za ažuriranje:
venv/bin/python manage.py shell -c "
from worktime.models import EmployeeProfile
updated = EmployeeProfile.objects.filter(overtime_rate=30).update(overtime_rate=50)
print(f'Ažurirano {updated} profila: 30% → 50%')
"
```

---

## DIO 2 — REŽIJE MODUL (utilities/)

### 2A: Novi Django app

```bash
cd /var/www/fina-connect
mkdir -p utilities/migrations utilities/templates/utilities
touch utilities/__init__.py utilities/apps.py utilities/admin.py
touch utilities/models.py utilities/views.py utilities/urls.py
touch utilities/tasks.py utilities/services.py
```

### 2B: utilities/apps.py

```python
from django.apps import AppConfig

class UtilitiesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'utilities'
    verbose_name = 'Režije i komunalni troškovi'

    def ready(self):
        import utilities.signals  # noqa
```

### 2C: utilities/models.py — 3 ključna modela

```python
"""
Utilities — evidencija komunalnih troškova firme.
Struja, voda, plin, internet, najam, odvoz otpada, grijanje.
"""
from decimal import Decimal
from django.db import models
from django.utils.translation import gettext_lazy as _
from core.managers import CompanyManager


class UtilityContract(models.Model):
    """Ugovor s komunalnim poduzećem — HEP, Vodoopskrba, INA, HT, T-com..."""

    UTILITY_TYPES = [
        ('electricity', '⚡ Električna energija'),
        ('water',       '💧 Vodoopskrba'),
        ('gas',         '🔥 Plin'),
        ('internet',    '🌐 Internet / Telekomunikacije'),
        ('phone',       '📱 Telefon / Mobitel'),
        ('rent',        '🏢 Najam prostora'),
        ('waste',       '🗑️  Odvoz otpada'),
        ('heating',     '♨️  Daljinsko grijanje'),
        ('parking',     '🅿️  Parking'),
        ('cleaning',    '🧹 Čišćenje prostora'),
        ('security',    '🔒 Osiguranje / Zaštita'),
        ('other',       '📋 Ostalo'),
    ]

    BILLING_CYCLES = [
        ('monthly',    'Mjesečno'),
        ('bimonthly',  'Dvomjesečno'),
        ('quarterly',  'Kvartalno'),
        ('yearly',     'Godišnje'),
        ('irregular',  'Neredovito'),
    ]

    company          = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='utility_contracts', verbose_name=_('Tvrtka'))
    objects          = CompanyManager()

    utility_type     = models.CharField(
        max_length=20, choices=UTILITY_TYPES, verbose_name=_('Vrsta'))
    provider         = models.ForeignKey(
        'partners.Partner', on_delete=models.PROTECT,
        related_name='utility_contracts', verbose_name=_('Dobavljač'))

    # Identifikatori ugovora/mjernog mjesta
    contract_number  = models.CharField(max_length=100, verbose_name=_('Broj ugovora'))
    measuring_point  = models.CharField(
        max_length=100, blank=True, verbose_name=_('Oznaka mjernog mjesta'),
        help_text='Broj obračunskog mjesta / mjernog mjesta')
    ean_code         = models.CharField(
        max_length=20, blank=True, verbose_name=_('EAN kod'),
        help_text='EAN/GS1 identifikator (za struju i plin)')

    # Lokacija potrošnje
    address          = models.CharField(
        max_length=255, blank=True, verbose_name=_('Adresa potrošnje'),
        help_text='Može biti drugačija od sjedišta firme')

    # Financijski uvjeti
    billing_cycle    = models.CharField(
        max_length=15, choices=BILLING_CYCLES, default='monthly',
        verbose_name=_('Ciklus fakturiranja'))
    fixed_monthly_eur = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name=_('Fiksni dio (EUR/mj)'),
        help_text='Pretplata, naknada za priključak, osnovna naknada')
    estimated_monthly_eur = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name=_('Procijenjeni varijabilni dio (EUR/mj)'))
    pdv_rate         = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('25.00'),
        verbose_name=_('PDV stopa (%)'))

    # Konto za knjiženje
    konto_code       = models.CharField(
        max_length=10, default='4200',
        verbose_name=_('Konto troška'),
        help_text='4200=Energija, 4300=Usluge, 4400=Ostali mat. troškovi')

    # AI matching — prepoznaj račune iz Arhive
    archiva_keywords = models.CharField(
        max_length=500, blank=True,
        verbose_name=_('Ključne riječi za matching'),
        help_text='Npr. "HEP-ODS,HEP ELEKTRA" — za auto-linkovanje iz Arhive')

    # Trajanje ugovora
    start_date       = models.DateField(verbose_name=_('Datum početka'))
    end_date         = models.DateField(null=True, blank=True,
        verbose_name=_('Datum isteka'),
        help_text='Prazno = trajni ugovor')

    auto_renews      = models.BooleanField(
        default=True, verbose_name=_('Auto-obnavljanje'))
    notice_days      = models.PositiveIntegerField(
        default=30, verbose_name=_('Otkazni rok (dana)'))

    is_active        = models.BooleanField(default=True, verbose_name=_('Aktivan'))
    notes            = models.TextField(blank=True, verbose_name=_('Napomene'))
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Ugovor o komunalnoj usluzi')
        verbose_name_plural = _('Ugovori o komunalnim uslugama')
        ordering = ['utility_type', 'provider__name']

    def __str__(self):
        return (f'{self.get_utility_type_display()} — '
                f'{self.provider.name} ({self.contract_number})')

    @property
    def is_expiring_soon(self):
        """Ističe li ugovor u sljedećih 30 dana?"""
        if not self.end_date:
            return False
        from django.utils import timezone
        import datetime
        days_left = (self.end_date - timezone.now().date()).days
        return 0 < days_left <= self.notice_days

    @property
    def estimated_total_monthly(self):
        return self.fixed_monthly_eur + self.estimated_monthly_eur


class MeterReading(models.Model):
    """Jedno očitanje brojila — stanje u određenom trenutku."""

    METER_TYPES = [
        ('electricity_active',   '⚡ Struja — aktivna energija (kWh)'),
        ('electricity_reactive', '⚡ Struja — reaktivna (kVArh)'),
        ('electricity_peak',     '⚡ Struja — vršna snaga (kW)'),
        ('water_cold',           '💧 Voda hladna (m³)'),
        ('water_hot',            '💧 Voda topla (m³)'),
        ('gas_volume',           '🔥 Plin — volumen (m³)'),
        ('gas_energy',           '🔥 Plin — energija (kWh)'),
        ('heating',              '♨️  Toplinska energija (GJ)'),
        ('custom',               '📊 Prilagođeno'),
    ]

    SOURCE_CHOICES = [
        ('manual',   'Ručni unos'),
        ('photo',    'Foto (FenixCamera OCR)'),
        ('hes',      'Daljinsko očitanje (HES/AMR)'),
        ('invoice',  'Preuzeto s računa'),
        ('api',      'API integracija'),
    ]

    contract         = models.ForeignKey(
        UtilityContract, on_delete=models.CASCADE,
        related_name='readings', verbose_name=_('Ugovor'))
    reading_date     = models.DateField(verbose_name=_('Datum očitanja'))
    meter_id         = models.CharField(
        max_length=50, blank=True, verbose_name=_('Serijski broj brojila'))
    meter_type       = models.CharField(
        max_length=30, choices=METER_TYPES, default='electricity_active',
        verbose_name=_('Vrsta mjerenja'))

    # Stanje brojila
    value            = models.DecimalField(
        max_digits=12, decimal_places=3, verbose_name=_('Stanje brojila'))
    unit             = models.CharField(
        max_length=10, default='kWh', verbose_name=_('Jedinica'))

    # Konzumacija od zadnjeg očitanja (auto-computed)
    consumption      = models.DecimalField(
        max_digits=12, decimal_places=3, null=True, blank=True,
        verbose_name=_('Potrošnja od zadnjeg očitanja'))

    # Dokumentacija
    photo            = models.ImageField(
        upload_to='utility_readings/%Y/%m/', null=True, blank=True,
        verbose_name=_('Foto brojila (FenixCamera)'))
    photo_ai_value   = models.DecimalField(
        max_digits=12, decimal_places=3, null=True, blank=True,
        verbose_name=_('AI pročitano stanje s foto'))
    photo_ai_confidence = models.FloatField(
        null=True, blank=True, verbose_name=_('AI pouzdanost (0-1)'))

    source           = models.CharField(
        max_length=10, choices=SOURCE_CHOICES, default='manual',
        verbose_name=_('Izvor'))
    entered_by       = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True,
        verbose_name=_('Unio'))
    is_verified      = models.BooleanField(
        default=False, verbose_name=_('Verificirano'))
    notes            = models.CharField(max_length=500, blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Očitanje brojila')
        verbose_name_plural = _('Očitanja brojila')
        ordering = ['-reading_date', 'contract']

    def __str__(self):
        return (f'{self.contract.get_utility_type_display()} '
                f'{self.reading_date}: {self.value} {self.unit}')

    def save(self, *args, **kwargs):
        """Auto-izračunaj konzumaciju od zadnjeg očitanja."""
        if not self.consumption:
            prev = (MeterReading.objects
                    .filter(contract=self.contract, meter_type=self.meter_type,
                            reading_date__lt=self.reading_date)
                    .order_by('-reading_date').first())
            if prev and prev.value is not None:
                self.consumption = max(
                    Decimal('0'),
                    self.value - prev.value)
        super().save(*args, **kwargs)


class UtilityBill(models.Model):
    """Primljeni račun za komunalnu uslugu."""

    STATUS_CHOICES = [
        ('pending',   'Na čekanju (nije proknjižen)'),
        ('booked',    'Proknjižen u Konto'),
        ('paid',      'Plaćen'),
        ('disputed',  'U sporu'),
        ('cancelled', 'Storniran'),
    ]

    contract         = models.ForeignKey(
        UtilityContract, on_delete=models.PROTECT,
        related_name='bills', verbose_name=_('Ugovor'))
    arhiva_entry     = models.OneToOneField(
        'documents.ArhivaEntry', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='utility_bill',
        verbose_name=_('Arhiva dokument'))

    invoice_number   = models.CharField(max_length=100, verbose_name=_('Broj računa'))
    bill_date        = models.DateField(verbose_name=_('Datum računa'))
    due_date         = models.DateField(null=True, blank=True, verbose_name=_('Rok plaćanja'))
    period_from      = models.DateField(verbose_name=_('Period od'))
    period_to        = models.DateField(verbose_name=_('Period do'))

    # Potrošnja na računu
    consumption_value = models.DecimalField(
        max_digits=12, decimal_places=3, null=True, blank=True,
        verbose_name=_('Potrošnja (iz računa)'))
    consumption_unit  = models.CharField(max_length=10, default='kWh')

    # Iznosi
    amount_fixed     = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name=_('Fiksni dio (EUR bez PDV)'))
    amount_variable  = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name=_('Varijabilni dio (EUR bez PDV)'))
    amount_net       = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name=_('Neto (EUR)'))
    amount_tax       = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name=_('PDV (EUR)'))
    amount_total     = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name=_('Ukupno (EUR)'))

    status           = models.CharField(
        max_length=15, choices=STATUS_CHOICES, default='pending')
    payment_date     = models.DateField(null=True, blank=True)
    konto_entry      = models.ForeignKey(
        'konto.JournalEntry', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='utility_bills')

    # AI polja
    ai_extracted     = models.JSONField(
        default=dict, blank=True,
        verbose_name=_('AI ekstrakcija iz PDF-a'))
    is_anomaly       = models.BooleanField(
        default=False, verbose_name=_('AI: anomalna potrošnja'))
    anomaly_note     = models.TextField(
        blank=True, verbose_name=_('AI: opis anomalije'))
    anomaly_pct      = models.FloatField(
        null=True, blank=True,
        verbose_name=_('Odstupanje od prosjeka (%)'))

    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Račun za komunalnu uslugu')
        verbose_name_plural = _('Računi za komunalne usluge')
        ordering = ['-bill_date']

    def __str__(self):
        return f'{self.contract} — {self.bill_date} — {self.amount_total} EUR'

    @property
    def is_overdue(self):
        from django.utils import timezone
        return (self.due_date and
                self.due_date < timezone.now().date() and
                self.status not in ('paid', 'cancelled'))
```

### 2D: utilities/services.py — AI i konto integracija

```python
"""
Utilities Services — AI anomaly detection, konto booking, Arhiva matching.
"""
import logging
from decimal import Decimal
from django.db import transaction

logger = logging.getLogger('utilities')


def book_utility_bill(bill, user=None):
    """
    Proknjiži primljeni komunalni račun u Konto.
    URA logika: D:konto_troška + D:pretporez / P:obveze prema dobavljaču

    Struja 800€ neto + 200€ PDV = 1000€:
      D: 4200 Troškovi energije     800,00€
      D: 1400 Pretporez             200,00€
      P: 2200 Obveze prema dobavljaču 1000,00€
    """
    from konto.models import KontoAccount, JournalEntry, LedgerLine
    from konto.services_file import _next_entry_number

    if bill.status == 'booked' and bill.konto_entry_id:
        return bill.konto_entry  # Idempotentnost

    company = bill.contract.company
    net     = bill.amount_net
    tax     = bill.amount_tax
    total   = bill.amount_total
    konto   = bill.contract.konto_code or '4200'

    konto_names = {
        '4200': 'Troškovi energije',
        '4300': 'Troškovi komunalnih usluga',
        '4400': 'Ostali materijalni troškovi',
        '4060': 'Troškovi najma',
    }
    konto_name = konto_names.get(konto, 'Komunalni troškovi')

    with transaction.atomic():
        def acct(code, name, atype):
            a, _ = KontoAccount.objects.get_or_create(
                company=company, code=code,
                defaults={'name': name, 'account_type': atype})
            return a

        je = JournalEntry.objects.create(
            company=company,
            entry_number=_next_entry_number(company, 'KOM'),
            date=bill.bill_date,
            description=(
                f'{bill.contract.get_utility_type_display()} — '
                f'{bill.contract.provider.name} '
                f'{bill.period_from}→{bill.period_to} '
                f'({bill.invoice_number})'
            ),
            source_type='ura',
            is_posted=True,
            created_by=user,
        )

        # D: Trošak
        LedgerLine.objects.create(
            journal_entry=je,
            account=acct(konto, konto_name, 'expense'),
            side='debit', amount=float(net),
            description=f'{bill.contract.get_utility_type_display()} {bill.period_from}→{bill.period_to}')

        # D: Pretporez (ako postoji PDV)
        if tax > 0:
            LedgerLine.objects.create(
                journal_entry=je,
                account=acct('1400', 'Pretporez', 'asset'),
                side='debit', amount=float(tax),
                description=f'PDV {bill.contract.provider.name}')

        # P: Obveze prema dobavljaču
        LedgerLine.objects.create(
            journal_entry=je,
            account=acct('2200', 'Obveze prema dobavljačima', 'liability'),
            side='credit', amount=float(total),
            description=f'{bill.contract.provider.name} {bill.invoice_number}')

        bill.konto_entry = je
        bill.status = 'booked'
        bill.save(update_fields=['konto_entry', 'status', 'updated_at'])

    return je


def detect_anomaly(bill):
    """
    Haiku: usporedi potrošnju s prosjekom zadnjih 12 mj.
    Vrati: (is_anomaly: bool, pct: float, note: str)
    """
    from utilities.models import UtilityBill
    from django.db.models import Avg

    # Zadnjih 12 računa istog ugovora
    historical = (UtilityBill.objects
                  .filter(contract=bill.contract,
                          status__in=['booked', 'paid'])
                  .exclude(pk=bill.pk)
                  .order_by('-bill_date')[:12])

    if historical.count() < 3:
        return False, 0.0, ''  # Premalo podataka

    avg_consumption = historical.aggregate(
        a=Avg('consumption_value'))['a'] or Decimal('0')
    avg_amount      = historical.aggregate(
        a=Avg('amount_total'))['a'] or Decimal('0')

    current = bill.consumption_value or bill.amount_total

    if avg_consumption and avg_consumption > 0:
        pct = float((current - avg_consumption) / avg_consumption * 100)
        reference = float(avg_consumption)
        unit = bill.consumption_unit or ''
    elif avg_amount and avg_amount > 0:
        pct = float((bill.amount_total - avg_amount) / avg_amount * 100)
        reference = float(avg_amount)
        unit = 'EUR'
    else:
        return False, 0.0, ''

    threshold = 20.0  # 20% odstupanje
    is_anomaly = abs(pct) >= threshold

    note = ''
    if is_anomaly:
        direction = 'VIŠA' if pct > 0 else 'NIŽA'
        note = (f'{bill.contract.get_utility_type_display()}: '
                f'potrošnja {direction} za {abs(pct):.1f}% od prosjeka '
                f'({reference:.1f} {unit}). Molimo provjerite.')

        # AI dublja analiza (Haiku, async)
        try:
            from utilities.tasks import ai_anomaly_explain
            ai_anomaly_explain.delay(bill.pk, pct, reference, unit)
        except Exception:
            pass

    return is_anomaly, pct, note


def match_arhiva_to_contract(arhiva_entry):
    """
    Pokuša pronaći UtilityContract koji odgovara ovom ArhivaEntry.
    Koristi archiva_keywords matching.
    """
    from utilities.models import UtilityContract

    company = arhiva_entry.company
    partner_name = (arhiva_entry.partner_name or '').lower()

    # Pokušaj direktno po partneru
    contracts = UtilityContract.objects.filter(
        company=company, is_active=True
    ).select_related('provider')

    for contract in contracts:
        # Provjeri keywords
        keywords = [k.strip().lower()
                    for k in contract.archiva_keywords.split(',')
                    if k.strip()]
        for kw in keywords:
            if kw in partner_name or kw in (arhiva_entry.doc_number or '').lower():
                return contract

        # Provjeri ime partnera direktno
        if contract.provider.name.lower() in partner_name:
            return contract

    return None
```

### 2E: utilities/tasks.py — Celery taskovi

```python
"""Celery taskovi za Utilities modul."""
from celery import shared_task
import logging

logger = logging.getLogger('utilities')


@shared_task(name='utilities.ai_anomaly_explain')
def ai_anomaly_explain(bill_pk, pct, reference, unit):
    """Haiku dublja analiza anomalije — šalje WhatsApp."""
    from utilities.models import UtilityBill
    try:
        bill = UtilityBill.objects.select_related(
            'contract__company', 'contract__provider'
        ).get(pk=bill_pk)
    except UtilityBill.DoesNotExist:
        return

    direction = 'VIŠA' if pct > 0 else 'NIŽA'
    msg = (
        f'⚡ ANOMALIJA: {bill.contract.get_utility_type_display()}\n'
        f'Firma: {bill.contract.company.name}\n'
        f'Dobavljač: {bill.contract.provider.name}\n'
        f'Potrošnja {direction} {abs(pct):.1f}% od prosjeka\n'
        f'Račun: {bill.invoice_number} | {bill.amount_total:.2f} EUR\n'
        f'Period: {bill.period_from} → {bill.period_to}'
    )
    try:
        from notifications.whatsapp import send_whatsapp
        # Pošalji vlasniku firme
        from companies.models import Company
        company = bill.contract.company
        owner = company.users.filter(is_active=True).first()
        if owner and hasattr(owner, 'userprofile') and owner.userprofile.phone:
            send_whatsapp(owner.userprofile.phone, msg)
    except Exception as e:
        logger.warning(f'WhatsApp anomaly notify: {e}')


@shared_task(name='utilities.check_expiring_contracts')
def check_expiring_contracts():
    """
    Dnevna provjera: ugovori koji ističu u sljedećih N dana.
    Šalje WhatsApp upozorenje vlasniku firme.
    """
    from utilities.models import UtilityContract
    from django.utils import timezone
    import datetime

    today = timezone.now().date()
    expiring = UtilityContract.objects.filter(
        is_active=True,
        end_date__isnull=False,
        end_date__lte=today + datetime.timedelta(days=60),
        end_date__gte=today,
    ).select_related('company', 'provider')

    for contract in expiring:
        days_left = (contract.end_date - today).days
        msg = (
            f'⚠️ UGOVOR ISTIČE ZA {days_left} DANA\n'
            f'{contract.get_utility_type_display()}\n'
            f'Dobavljač: {contract.provider.name}\n'
            f'Br. ugovora: {contract.contract_number}\n'
            f'Datum isteka: {contract.end_date}\n'
            f'Otkazni rok: {contract.notice_days} dana\n'
            f'Akcija: limit-connect.com/hr/utilities/contracts/{contract.pk}/'
        )
        try:
            from notifications.whatsapp import send_whatsapp
            owner = contract.company.users.filter(is_active=True).first()
            if owner and hasattr(owner, 'userprofile') and owner.userprofile.phone:
                send_whatsapp(owner.userprofile.phone, msg)
        except Exception:
            pass


@shared_task(name='utilities.auto_book_pending_bills')
def auto_book_pending_bills():
    """
    Noćni task: proknjiži sve pending UtilityBill koji imaju arhiva_entry.
    """
    from utilities.models import UtilityBill
    from utilities.services import book_utility_bill

    pending = UtilityBill.objects.filter(
        status='pending',
        arhiva_entry__isnull=False,
        amount_total__gt=0,
    ).select_related('contract__company', 'contract__provider')[:50]

    booked = 0
    for bill in pending:
        try:
            book_utility_bill(bill)
            booked += 1
        except Exception as e:
            logger.warning(f'Auto-book utility bill {bill.pk}: {e}')

    logger.info(f'Utilities: proknjiženo {booked}/{len(pending)} računa')
    return {'booked': booked}
```

### 2F: Celery beat schedule — dodaj u settings.py

```python
# Pronađi zadnji CELERY_BEAT_SCHEDULE.update({}) i dodaj:
CELERY_BEAT_SCHEDULE.update({
    'utilities-check-contracts': {
        'task': 'utilities.check_expiring_contracts',
        'schedule': 86400,  # jednom dnevno u 08:00
    },
    'utilities-auto-book': {
        'task': 'utilities.auto_book_pending_bills',
        'schedule': 21600,  # svakih 6h
    },
})
```

### 2G: utilities/signals.py — Arhiva → UtilityBill auto-linkovanje

```python
"""Auto-link ArhivaEntry na UtilityBill pri kreiranju."""
from django.db.models.signals import post_save
from django.dispatch import receiver
import logging

logger = logging.getLogger('utilities')


@receiver(post_save, sender='documents.ArhivaEntry')
def auto_link_utility_bill(sender, instance, created, **kwargs):
    """
    Kad nova ArhivaEntry stigne — pokušaj linkati na UtilityContract.
    Ako se pronađe match → kreira UtilityBill u pending statusu.
    """
    if not created:
        return

    # Samo ulazni računi
    if instance.source_type not in ('invoice_in', 'eracun', 'email_in'):
        return

    # Mora imati iznos
    if not instance.amount or instance.amount <= 0:
        return

    try:
        from utilities.services import match_arhiva_to_contract
        from utilities.models import UtilityBill

        contract = match_arhiva_to_contract(instance)
        if not contract:
            return

        # Duplikat check
        if UtilityBill.objects.filter(arhiva_entry=instance).exists():
            return

        from django.utils import timezone
        today = timezone.now().date()

        # Pokušaj izvući period iz ArhivaEntry.ai_data
        ai_data = getattr(instance, 'ai_extracted', {}) or {}
        period_from = ai_data.get('period_from') or today.replace(day=1)
        period_to   = ai_data.get('period_to')   or today

        bill = UtilityBill.objects.create(
            contract=contract,
            arhiva_entry=instance,
            invoice_number=instance.doc_number or f'AUTO-{instance.pk}',
            bill_date=instance.doc_date or today,
            period_from=period_from,
            period_to=period_to,
            amount_net=instance.amount or 0,
            amount_tax=getattr(instance, 'vat_amount', 0) or 0,
            amount_total=(instance.amount or 0) + (getattr(instance, 'vat_amount', 0) or 0),
            ai_extracted=ai_data,
            status='pending',
        )

        # Anomaly check
        from utilities.services import detect_anomaly
        is_anom, pct, note = detect_anomaly(bill)
        if is_anom:
            bill.is_anomaly = True
            bill.anomaly_pct = pct
            bill.anomaly_note = note
            bill.save(update_fields=['is_anomaly', 'anomaly_pct', 'anomaly_note'])

        logger.info(f'UtilityBill kreiran iz ArhivaEntry {instance.pk} → {contract}')

    except Exception as e:
        logger.warning(f'auto_link_utility_bill fail za {instance.pk}: {e}')
```

### 2H: utilities/views.py — 10/10 UI

```python
"""
Utilities Views — 10/10 UI za upravljanje komunalnim troškovima.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Avg, Count, Q
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from decimal import Decimal
from datetime import date, timedelta
from core.company_utils import get_user_company


@login_required
def dashboard(request):
    """Główny dashboard — pregled svih komunalnih troškova."""
    company = get_user_company(request)
    from utilities.models import UtilityContract, UtilityBill, MeterReading

    today = date.today()
    month_start = today.replace(day=1)
    year_start = today.replace(month=1, day=1)

    # Aktivni ugovori po tipu
    contracts = UtilityContract.objects.filter(
        company=company, is_active=True
    ).select_related('provider').order_by('utility_type')

    # Troškovi ovaj mj po vrsti
    monthly_by_type = (UtilityBill.objects
        .filter(contract__company=company, bill_date__gte=month_start)
        .values('contract__utility_type')
        .annotate(total=Sum('amount_total'), count=Count('id'))
        .order_by('-total'))

    # Ukupno ove godine
    year_total = (UtilityBill.objects
        .filter(contract__company=company, bill_date__gte=year_start,
                status__in=['booked','paid'])
        .aggregate(t=Sum('amount_total'))['t'] or Decimal('0'))

    # Pending (neproknjiženi)
    pending = UtilityBill.objects.filter(
        contract__company=company, status='pending'
    ).select_related('contract').order_by('-bill_date')[:5]

    # Anomalije
    anomalies = UtilityBill.objects.filter(
        contract__company=company,
        is_anomaly=True,
        status__in=['pending','booked']
    ).select_related('contract__provider').order_by('-bill_date')[:5]

    # Ugovori koji ističu
    expiring = contracts.filter(
        end_date__isnull=False,
        end_date__lte=today + timedelta(days=60),
        end_date__gte=today,
    )

    # Zadnja očitanja po ugovoru
    latest_readings = {}
    for contract in contracts:
        r = (MeterReading.objects
             .filter(contract=contract)
             .order_by('-reading_date').first())
        if r:
            latest_readings[contract.pk] = r

    # Trend — zadnjih 12 mj
    import calendar
    trend_data = []
    for i in range(11, -1, -1):
        d = date(today.year, today.month, 1)
        # Izračun prethodnih mjeseci
        month = today.month - i
        year = today.year
        while month <= 0:
            month += 12
            year -= 1
        mstart = date(year, month, 1)
        mend = date(year, month, calendar.monthrange(year, month)[1])
        total = (UtilityBill.objects
                 .filter(contract__company=company,
                         bill_date__gte=mstart, bill_date__lte=mend)
                 .aggregate(t=Sum('amount_total'))['t'] or Decimal('0'))
        trend_data.append({
            'month': f'{month:02d}/{year}',
            'total': float(total),
        })

    return render(request, 'utilities/dashboard.html', {
        'contracts':      contracts,
        'monthly_by_type': monthly_by_type,
        'year_total':     year_total,
        'pending':        pending,
        'anomalies':      anomalies,
        'expiring':       expiring,
        'latest_readings': latest_readings,
        'trend_data':     trend_data,
        'page_title':     'Komunalni troškovi',
    })


@login_required
def contract_list(request):
    """Lista svih ugovora."""
    company = get_user_company(request)
    from utilities.models import UtilityContract
    contracts = (UtilityContract.objects.filter(company=company)
                 .select_related('provider')
                 .order_by('utility_type', 'provider__name'))
    return render(request, 'utilities/contract_list.html', {
        'contracts': contracts, 'page_title': 'Ugovori — Komunalne usluge'})


@login_required
def meter_reading_create(request, contract_pk):
    """Unos novog očitanja — s FenixCamera podrškom."""
    company = get_user_company(request)
    from utilities.models import UtilityContract, MeterReading
    contract = get_object_or_404(UtilityContract, pk=contract_pk, company=company)

    if request.method == 'POST':
        try:
            from decimal import Decimal
            reading = MeterReading.objects.create(
                contract=contract,
                reading_date=request.POST.get('reading_date', date.today()),
                meter_id=request.POST.get('meter_id', ''),
                meter_type=request.POST.get('meter_type', 'electricity_active'),
                value=Decimal(request.POST.get('value', '0')),
                unit=request.POST.get('unit', 'kWh'),
                source=request.POST.get('source', 'manual'),
                notes=request.POST.get('notes', ''),
                entered_by=request.user,
            )
            if 'photo' in request.FILES:
                reading.photo = request.FILES['photo']
                reading.save()
                # Pokušaj AI OCR čitanje s fotografije
                try:
                    from utilities.tasks import ocr_meter_photo
                    ocr_meter_photo.delay(reading.pk)
                except Exception:
                    pass

            from django.contrib import messages
            messages.success(request, f'Očitanje {reading.value} {reading.unit} uneseno.')
            if reading.consumption:
                messages.info(request,
                    f'Potrošnja od zadnjeg očitanja: {reading.consumption} {reading.unit}')
            return redirect('utilities:dashboard')
        except Exception as e:
            from django.contrib import messages
            messages.error(request, f'Greška: {e}')

    # Zadnje očitanje za prikaz
    from utilities.models import MeterReading as MR
    last = MR.objects.filter(contract=contract).order_by('-reading_date').first()
    return render(request, 'utilities/meter_reading_form.html', {
        'contract': contract,
        'last_reading': last,
        'page_title': f'Unos očitanja — {contract}',
    })


@login_required
@require_POST
def bill_book(request, bill_pk):
    """Proknjiži račun u Konto."""
    company = get_user_company(request)
    from utilities.models import UtilityBill
    from utilities.services import book_utility_bill
    bill = get_object_or_404(UtilityBill, pk=bill_pk, contract__company=company)
    try:
        je = book_utility_bill(bill, user=request.user)
        return JsonResponse({'ok': True, 'je': je.entry_number if je else None})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@login_required
def api_monthly_trend(request):
    """API: trend po tipu za chart."""
    company = get_user_company(request)
    from utilities.models import UtilityBill
    from django.db.models import Sum
    months = 12

    today = date.today()
    data = {}
    for i in range(months - 1, -1, -1):
        month = today.month - i
        year = today.year
        while month <= 0:
            month += 12
            year -= 1
        label = f'{month:02d}/{year}'
        import calendar
        mstart = date(year, month, 1)
        mend = date(year, month, calendar.monthrange(year, month)[1])
        bills = (UtilityBill.objects
                 .filter(contract__company=company,
                         bill_date__gte=mstart, bill_date__lte=mend)
                 .values('contract__utility_type')
                 .annotate(t=Sum('amount_total')))
        data[label] = {b['contract__utility_type']: float(b['t']) for b in bills}

    return JsonResponse({'trend': data, 'months': list(data.keys())})
```

### 2I: urls.py i settings.py

```python
# utilities/urls.py
from django.urls import path
from . import views
app_name = 'utilities'
urlpatterns = [
    path('',                           views.dashboard,             name='dashboard'),
    path('contracts/',                 views.contract_list,         name='contract_list'),
    path('contracts/<int:pk>/',        views.contract_detail,       name='contract_detail'),
    path('readings/<int:contract_pk>/new/', views.meter_reading_create, name='reading_create'),
    path('bills/<int:bill_pk>/book/',  views.bill_book,             name='bill_book'),
    path('api/trend/',                 views.api_monthly_trend,     name='api_trend'),
]
```

U `core/urls.py` dodaj:
```python
path('hr/utilities/', include('utilities.urls', namespace='utilities')),
```

U `core/settings.py` (INSTALLED_APPS):
```python
'utilities',
```

### 2J: Migracije i Verifikacija

```bash
venv/bin/python manage.py makemigrations utilities --name="initial"
venv/bin/python manage.py migrate 2>&1 | tail -5
venv/bin/python manage.py check 2>&1 | tail -3

# Test modela
venv/bin/python manage.py shell -c "
from utilities.models import UtilityContract, MeterReading, UtilityBill
print('UtilityContract:', UtilityContract.objects.count(), 'OK')
print('MeterReading:', MeterReading.objects.count(), 'OK')
print('UtilityBill:', UtilityBill.objects.count(), 'OK')
" 2>/dev/null

git add -A
git commit -m "feat(utilities): komunalni troškovi — ugovori, brojila, računi, AI anomaly, konto integracija"
```

---

## DONE KRITERIJI:

Zakonske nepravilnosti:
- [ ] PDV-S: PO i P uklonjeni iz doctype__in
- [ ] Overtime default: 30% → 50% (ZOR čl. 94)
- [ ] Postojeći EmployeeProfile: 30% → 50% (data migration)

Utilities modul:
- [ ] UtilityContract model + admin
- [ ] MeterReading model + auto-konzumacija
- [ ] UtilityBill model + anomaly detection
- [ ] book_utility_bill() → D:4200/1400 P:2200
- [ ] Signal: ArhivaEntry → auto UtilityBill (match keywords)
- [ ] Celery: check_expiring_contracts (dnevno)
- [ ] Celery: auto_book_pending_bills (6h)
- [ ] Dashboard: trend 12 mj, po tipu, anomalije, expiring
- [ ] Meter reading form: FenixCamera + manual
- [ ] manage.py check: 0 errora
- [ ] URL: /hr/utilities/ live
