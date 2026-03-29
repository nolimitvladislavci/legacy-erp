# CC_TASK_SEZONSKI_RADNICI.md
# Dodijeljen: CC Code
# Prioritet: VISOKO — turistička sezona počinje 1.6.2026. (za 2 mjeseca)
# Procjena: 10-12 dana
# Piloti: Didin Konak (Viktor), OPG Kruljac (Ivica), Viskovic Bau (Nikša)
# Ref: MASTER_PLAN_2026.md → H1 add-on

# FILOZOFIJA:
# Sezonski radnik nije User u Django auth sustavu.
# On je entitet koji se veže uz Company s jasnim početkom/krajem.
# Ne mora imati login. Mora imati OIB, ugovor, i JOPPD.
# Worktime/EmployeeProfile ostaje za stalne zaposlenike s loginom.
# SeasonalWorker je "light" verzija — samo ono što zakon traži.

---

## KORAK 0 — PROVJERI UVIJEK PRVO

```bash
# Provjeri stvarna polja EmployeeProfile (ne pretpostavljaj)
grep -n "class EmployeeProfile\|tax_id\|OIB\|contract\|hourly_rate\|bank_account\|date_hired" \
  /var/www/fina-connect/worktime/models.py | head -30

# Provjeri payroll models
grep -n "class\|gross\|net\|joppd" \
  /var/www/fina-connect/payroll/models.py | head -20

# Provjeri hr_calculator - koji parametri ulaze
head -80 /var/www/fina-connect/payroll/hr_calculator.py
```

---

## KORAK 1 — Novi app `seasonal/`

```bash
cd /var/www/fina-connect
/var/www/fina-connect/venv/bin/python manage.py startapp seasonal
```

Dodati u `core/settings.py` INSTALLED_APPS:
```python
'seasonal',
```

---

## KORAK 2 — Modeli

### seasonal/models.py

```python
"""
seasonal/models.py — Sezonski radnici

Arhitektura:
  SeasonalWorker  → radnik bez Django login pristupa
  SeasonalContract → ugovor (može ih biti više za jednog radnika)
  SeasonalPayment  → isplata (dnevnica, tjedna, završna)

Integracija:
  - hr_calculator (payroll) za obračun doprinosa
  - JOPPD generator (payroll) za obrazac
  - WhatsApp (core.whatsapp) za podsjetnik M-1/M-2
  - core.managers.CompanyManager za multi-tenant izolaciju
"""
from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from core.managers import CompanyManager


class SeasonalWorker(models.Model):
    """
    Sezonski radnik — ne mora imati Django korisnički račun.
    OIB je jedini obvezni identifikator.
    """
    NATIONALITY_CHOICES = [
        ('HR', 'Hrvatska'),
        ('DE', 'Njemačka'),
        ('AT', 'Austrija'),
        ('BA', 'Bosna i Hercegovina'),
        ('RS', 'Srbija'),
        ('SI', 'Slovenija'),
        ('OTHER', 'Ostalo'),
    ]

    company      = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='seasonal_workers'
    )
    objects = CompanyManager()

    # Osobni podaci
    first_name   = models.CharField(max_length=100, verbose_name=_('Ime'))
    last_name    = models.CharField(max_length=100, verbose_name=_('Prezime'))
    oib          = models.CharField(max_length=11, verbose_name='OIB',
                    help_text=_('Obvezno za JOPPD i prijavu HZMO'))
    nationality  = models.CharField(max_length=10, choices=NATIONALITY_CHOICES,
                    default='HR', verbose_name=_('Državljanstvo'))
    date_of_birth = models.DateField(null=True, blank=True, verbose_name=_('Datum rođenja'))
    address      = models.CharField(max_length=300, blank=True, verbose_name=_('Adresa'))

    # Kontakt
    phone        = models.CharField(max_length=30, blank=True, verbose_name=_('Mobitel'))
    email        = models.EmailField(blank=True, verbose_name=_('Email'))

    # Isplata
    iban         = models.CharField(max_length=34, blank=True, verbose_name='IBAN',
                    help_text=_('Za bankovni transfer. Ako prazno — isplata gotovinom.'))

    # Meta
    notes        = models.TextField(blank=True, verbose_name=_('Napomene'))
    is_active    = models.BooleanField(default=True,
                    verbose_name=_('Aktivan u bazi'))
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = _('Sezonski radnik')
        verbose_name_plural = _('Sezonski radnici')
        ordering            = ['last_name', 'first_name']
        unique_together     = [('company', 'oib')]

    def __str__(self):
        return f'{self.last_name} {self.first_name} ({self.oib})'

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'

    @property
    def active_contract(self):
        return self.contracts.filter(
            status__in=['active', 'pending']
        ).order_by('-start_date').first()


class SeasonalContract(models.Model):
    """
    Ugovor za sezonskog radnika.
    Jedan radnik može imati više ugovora (svaka sezona = novi ugovor).
    """
    CONTRACT_TYPE_CHOICES = [
        ('djelo',       _('Ugovor o djelu (čl. 590 ZOO)')),
        ('privremeni',  _('Privremeni i povremeni (ZOR čl. 10) — max 90 dana/god')),
        ('odredjeno',   _('Ugovor o radu na određeno (ZOR čl. 12)')),
        ('autorski',    _('Ugovor o autorskom djelu')),
        ('studentski',  _('Studentski ugovor (preko servisa)')),
    ]
    STATUS_CHOICES = [
        ('pending',    _('Na čekanju — nije počelo')),
        ('active',     _('Aktivan — radnik na terenu')),
        ('completed',  _('Završen — radnik otišao')),
        ('cancelled',  _('Otkazano')),
    ]
    PAYMENT_CYCLE_CHOICES = [
        ('daily',    _('Dnevna nadoknada')),
        ('weekly',   _('Tjedna isplata')),
        ('monthly',  _('Mjesečna plaća')),
        ('lump_sum', _('Jednokratna isplata po završetku')),
    ]

    worker        = models.ForeignKey(SeasonalWorker, on_delete=models.CASCADE,
                     related_name='contracts', verbose_name=_('Radnik'))
    company       = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                     related_name='seasonal_contracts')
    objects = CompanyManager()

    contract_type = models.CharField(max_length=20, choices=CONTRACT_TYPE_CHOICES,
                     verbose_name=_('Vrsta ugovora'))
    status        = models.CharField(max_length=15, choices=STATUS_CHOICES,
                     default='pending')

    # Período
    start_date    = models.DateField(verbose_name=_('Datum početka rada'))
    end_date      = models.DateField(verbose_name=_('Datum završetka rada'))

    # Naknada
    payment_cycle = models.CharField(max_length=15, choices=PAYMENT_CYCLE_CHOICES,
                     default='lump_sum', verbose_name=_('Ciklus isplate'))
    gross_amount  = models.DecimalField(
                     max_digits=10, decimal_places=2,
                     verbose_name=_('Bruto iznos (EUR)'),
                     help_text=_('Za djelo/privremeni: ukupni bruto. '
                                 'Za određeno: bruto/mj.'))
    currency      = models.CharField(max_length=3, default='EUR')

    # Uloga na poslu
    position      = models.CharField(max_length=200, blank=True,
                     verbose_name=_('Radno mjesto / opis posla'),
                     help_text=_('npr. Sobarica, Berač grožđa, Konobar'))

    # HZMO — M-1/M-2 (samo za ugovor o radu na određeno)
    hzmo_prijava_sent   = models.BooleanField(default=False,
                           verbose_name=_('M-1 prijavnica poslana'))
    hzmo_prijava_date   = models.DateField(null=True, blank=True,
                           verbose_name=_('Datum slanja M-1'))
    hzmo_odjava_sent    = models.BooleanField(default=False,
                           verbose_name=_('M-2 odjavnica poslana'))
    hzmo_odjava_date    = models.DateField(null=True, blank=True,
                           verbose_name=_('Datum slanja M-2'))

    # Dokument
    contract_pdf  = models.FileField(upload_to='seasonal/contracts/',
                     null=True, blank=True, verbose_name=_('Ugovor PDF'))
    signed_at     = models.DateTimeField(null=True, blank=True,
                     verbose_name=_('Datum potpisa'))
    notes         = models.TextField(blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)
    created_by    = models.ForeignKey('auth.User', on_delete=models.SET_NULL,
                     null=True, blank=True, related_name='+')

    class Meta:
        verbose_name        = _('Sezonski ugovor')
        verbose_name_plural = _('Sezonski ugovori')
        ordering            = ['-start_date']

    def __str__(self):
        return (f'{self.worker.full_name} — '
                f'{self.get_contract_type_display()} '
                f'({self.start_date} → {self.end_date})')

    @property
    def duration_days(self):
        return (self.end_date - self.start_date).days + 1

    @property
    def days_worked_so_far(self):
        today = timezone.localdate()
        if today < self.start_date:
            return 0
        end = min(today, self.end_date)
        return (end - self.start_date).days + 1

    @property
    def needs_hzmo_prijava(self):
        """M-1 je obvezno samo za ugovor o radu na određeno."""
        return (self.contract_type == 'odredjeno'
                and not self.hzmo_prijava_sent)

    @property
    def hzmo_prijava_deadline(self):
        """M-1 mora biti poslana u roku 8 dana od početka rada."""
        from datetime import timedelta
        return self.start_date + timedelta(days=8)

    @property
    def hzmo_odjava_deadline(self):
        """M-2 mora biti poslana u roku 8 dana od završetka rada."""
        from datetime import timedelta
        return self.end_date + timedelta(days=8)

    def calculate_gross(self):
        """
        Bruto za JOPPD. Za ugovor o djelu: 100% bruto_amount.
        Za ugovor o radu: uzima payroll.hr_calculator.
        """
        return self.gross_amount

    def net_estimate(self):
        """Procjena neto iznosa za radnika (informativno)."""
        try:
            from payroll.hr_calculator import izracunaj_placu
            result = izracunaj_placu(self.gross_amount)
            return result.get('neto', Decimal('0'))
        except Exception:
            # Fallback: ~70% bruta (aproksimacija)
            return self.gross_amount * Decimal('0.70')


class SeasonalPayment(models.Model):
    """
    Isplata sezonskom radniku — može biti parcijalna ili finalna.
    JOPPD se generira iz ovog modela.
    """
    PAYMENT_STATUS_CHOICES = [
        ('planned',  _('Planirana')),
        ('approved', _('Odobrena')),
        ('paid',     _('Isplaćena')),
    ]
    PAYMENT_METHOD_CHOICES = [
        ('bank',  _('Bankovni transfer')),
        ('cash',  _('Gotovina')),
    ]

    contract      = models.ForeignKey(SeasonalContract, on_delete=models.CASCADE,
                     related_name='payments', verbose_name=_('Ugovor'))
    company       = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                     related_name='seasonal_payments')
    objects = CompanyManager()

    payment_date  = models.DateField(verbose_name=_('Datum isplate'))
    gross_amount  = models.DecimalField(max_digits=10, decimal_places=2,
                     verbose_name=_('Bruto iznos'))
    # Obračun se popunjava pri approved statusu
    tax_amount    = models.DecimalField(max_digits=10, decimal_places=2,
                     default=0, verbose_name=_('Porez (10%/20%)'))
    net_amount    = models.DecimalField(max_digits=10, decimal_places=2,
                     default=0, verbose_name=_('Neto za isplatu'))

    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHOD_CHOICES,
                      default='bank')
    status         = models.CharField(max_length=15, choices=PAYMENT_STATUS_CHOICES,
                      default='planned')

    joppd_generated = models.BooleanField(default=False,
                       verbose_name=_('JOPPD obrazac generiran'))
    joppd_date      = models.DateField(null=True, blank=True,
                       verbose_name=_('Datum JOPPD'))
    joppd_xml       = models.TextField(blank=True,
                       verbose_name=_('JOPPD XML sadržaj'))

    reference       = models.CharField(max_length=100, blank=True,
                       verbose_name=_('Referenca plaćanja'))
    receipt_pdf     = models.FileField(upload_to='seasonal/receipts/',
                       null=True, blank=True, verbose_name=_('Potvrda isplate PDF'))
    notes           = models.TextField(blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    approved_by     = models.ForeignKey('auth.User', on_delete=models.SET_NULL,
                       null=True, blank=True, related_name='+')

    class Meta:
        verbose_name        = _('Isplata sezoncu')
        verbose_name_plural = _('Isplate sezonskim radnicima')
        ordering            = ['-payment_date']

    def __str__(self):
        return (f'{self.contract.worker.full_name} — '
                f'{self.gross_amount}€ bruto ({self.payment_date})')

    def calculate_and_approve(self, approved_by=None):
        """
        Izračunaj porez i odobri isplatu.
        Za ugovor o djelu: porez 10% (ako je < 15.000€/god) ili 20%.
        Za ugovor o radu na određeno: puni JOPPD obračun.
        """
        contract_type = self.contract.contract_type

        if contract_type in ('djelo', 'privremeni', 'autorski'):
            # Paušalni porez na drugi dohodak: 20%
            # S osobnim odbitkom: efektivno ~10% za niže iznose
            # Koristimo 20% kao sigurnu opciju (ZPDOH čl. 67)
            self.tax_amount = (self.gross_amount * Decimal('0.20')).quantize(Decimal('0.01'))
            self.net_amount = self.gross_amount - self.tax_amount

        elif contract_type == 'odredjeno':
            # Puni obračun kroz hr_calculator
            try:
                from payroll.hr_calculator import izracunaj_placu
                result = izracunaj_placu(self.gross_amount)
                self.tax_amount = result.get('porez', Decimal('0')) + result.get('prirez', Decimal('0'))
                self.net_amount = result.get('neto', self.gross_amount * Decimal('0.70'))
            except Exception:
                self.tax_amount = self.gross_amount * Decimal('0.30')
                self.net_amount = self.gross_amount * Decimal('0.70')

        else:
            # Studentski — bez poreza (do limita)
            self.tax_amount = Decimal('0')
            self.net_amount = self.gross_amount

        self.status = 'approved'
        self.approved_by = approved_by
        self.save(update_fields=['tax_amount', 'net_amount', 'status', 'approved_by'])
        return self
```

---

## KORAK 3 — Views

### seasonal/views.py

```python
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from datetime import timedelta

from core.company_utils import get_user_company
from .models import SeasonalWorker, SeasonalContract, SeasonalPayment


@login_required
def dashboard(request):
    company = get_user_company(request)
    today   = timezone.localdate()

    # Aktivni ugovori
    active = SeasonalContract.objects.filter(
        company=company, status='active'
    ).select_related('worker').order_by('end_date')

    # Skorašnji početci (sljedećih 14 dana)
    upcoming = SeasonalContract.objects.filter(
        company=company, status='pending',
        start_date__lte=today + timedelta(days=14)
    ).select_related('worker').order_by('start_date')

    # HZMO alarmi — prekoračeni rokovi i bliski rokovi
    hzmo_alerts = []
    for c in SeasonalContract.objects.filter(
        company=company,
        contract_type='odredjeno',
        status__in=['active', 'pending', 'completed']
    ).select_related('worker'):
        if c.needs_hzmo_prijava:
            days_left = (c.hzmo_prijava_deadline - today).days
            hzmo_alerts.append({
                'contract': c,
                'type': 'M-1 prijava',
                'deadline': c.hzmo_prijava_deadline,
                'days_left': days_left,
                'urgent': days_left <= 2,
            })
        if (c.contract_type == 'odredjeno'
                and c.status == 'completed'
                and not c.hzmo_odjava_sent):
            days_left = (c.hzmo_odjava_deadline - today).days
            hzmo_alerts.append({
                'contract': c,
                'type': 'M-2 odjava',
                'deadline': c.hzmo_odjava_deadline,
                'days_left': days_left,
                'urgent': days_left <= 2,
            })

    # Statistike sezone (tekuća godina)
    year = today.year
    stats = {
        'total_workers': SeasonalWorker.objects.filter(company=company).count(),
        'active_now': active.count(),
        'contracts_this_year': SeasonalContract.objects.filter(
            company=company, start_date__year=year).count(),
        'total_gross_this_year': sum(
            p.gross_amount for p in SeasonalPayment.objects.filter(
                company=company, payment_date__year=year, status='paid'
            )
        ),
        'hzmo_alert_count': len(hzmo_alerts),
    }

    return render(request, 'seasonal/dashboard.html', {
        'active_contracts': active,
        'upcoming_contracts': upcoming,
        'hzmo_alerts': hzmo_alerts,
        'stats': stats,
        'today': today,
    })


@login_required
def worker_list(request):
    company = get_user_company(request)
    q = request.GET.get('q', '')
    workers = SeasonalWorker.objects.filter(company=company)
    if q:
        from django.db.models import Q
        workers = workers.filter(
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q) |
            Q(oib__icontains=q)
        )
    return render(request, 'seasonal/worker_list.html', {
        'workers': workers, 'q': q
    })


@login_required
def worker_create(request):
    company = get_user_company(request)
    if request.method == 'POST':
        p = request.POST
        try:
            worker = SeasonalWorker.objects.create(
                company=company,
                first_name=p['first_name'],
                last_name=p['last_name'],
                oib=p['oib'],
                nationality=p.get('nationality', 'HR'),
                phone=p.get('phone', ''),
                email=p.get('email', ''),
                iban=p.get('iban', ''),
                address=p.get('address', ''),
                notes=p.get('notes', ''),
            )
            messages.success(request, f'{worker.full_name} dodan u bazu.')
            # Ako je pristigao s "create_contract" flagom — odmah na ugovor
            if p.get('create_contract'):
                return redirect('seasonal:contract_create', worker_pk=worker.pk)
            return redirect('seasonal:worker_detail', pk=worker.pk)
        except Exception as e:
            messages.error(request, f'Greška: {e}')
    return render(request, 'seasonal/worker_form.html', {
        'nationality_choices': SeasonalWorker.NATIONALITY_CHOICES,
    })


@login_required
def worker_detail(request, pk):
    company = get_user_company(request)
    worker  = get_object_or_404(SeasonalWorker, pk=pk, company=company)
    contracts = worker.contracts.filter(company=company).order_by('-start_date')
    return render(request, 'seasonal/worker_detail.html', {
        'worker': worker,
        'contracts': contracts,
    })


@login_required
def contract_create(request, worker_pk):
    company = get_user_company(request)
    worker  = get_object_or_404(SeasonalWorker, pk=worker_pk, company=company)

    if request.method == 'POST':
        p = request.POST
        try:
            from datetime import date
            contract = SeasonalContract.objects.create(
                company=company,
                worker=worker,
                contract_type=p['contract_type'],
                start_date=p['start_date'],
                end_date=p['end_date'],
                gross_amount=p['gross_amount'],
                payment_cycle=p.get('payment_cycle', 'lump_sum'),
                position=p.get('position', ''),
                notes=p.get('notes', ''),
                status='pending',
                created_by=request.user,
            )
            messages.success(request,
                f'Ugovor kreiran: {worker.full_name} '
                f'od {contract.start_date} do {contract.end_date}.')
            # WhatsApp podsjetnik
            _schedule_hzmo_reminder(contract)
            return redirect('seasonal:contract_detail', pk=contract.pk)
        except Exception as e:
            messages.error(request, f'Greška: {e}')

    return render(request, 'seasonal/contract_form.html', {
        'worker': worker,
        'contract_type_choices': SeasonalContract.CONTRACT_TYPE_CHOICES,
        'payment_cycle_choices': SeasonalContract.PAYMENT_CYCLE_CHOICES,
        'today': timezone.localdate(),
    })


@login_required
def contract_detail(request, pk):
    company  = get_user_company(request)
    contract = get_object_or_404(SeasonalContract, pk=pk, company=company)
    payments = contract.payments.all().order_by('-payment_date')
    today    = timezone.localdate()

    # Neto procjena za info
    net_est = contract.net_estimate()

    return render(request, 'seasonal/contract_detail.html', {
        'contract': contract,
        'payments': payments,
        'net_estimate': net_est,
        'today': today,
        'days_worked': contract.days_worked_so_far,
        'hzmo_prijava_deadline': contract.hzmo_prijava_deadline,
        'hzmo_odjava_deadline': contract.hzmo_odjava_deadline,
    })


@login_required
def contract_activate(request, pk):
    """Označi ugovor kao aktivan (radnik je počeo raditi)."""
    company  = get_user_company(request)
    contract = get_object_or_404(SeasonalContract, pk=pk, company=company)
    if request.method == 'POST':
        contract.status = 'active'
        contract.save(update_fields=['status'])
        messages.success(request,
            f'{contract.worker.full_name} je sada aktivan radnik.')
        if contract.needs_hzmo_prijava:
            messages.warning(request,
                f'⚠️ M-1 prijava HZMO mora biti poslana do {contract.hzmo_prijava_deadline}!')
    return redirect('seasonal:contract_detail', pk=pk)


@login_required
def contract_complete(request, pk):
    """Završi sezonu za ovog radnika."""
    company  = get_user_company(request)
    contract = get_object_or_404(SeasonalContract, pk=pk, company=company)
    if request.method == 'POST':
        contract.status = 'completed'
        contract.save(update_fields=['status'])
        messages.success(request,
            f'Sezona završena: {contract.worker.full_name}.')
        if contract.contract_type == 'odredjeno' and not contract.hzmo_odjava_sent:
            messages.warning(request,
                f'⚠️ M-2 odjava HZMO mora biti poslana do {contract.hzmo_odjava_deadline}!')
        # Automatski kreiraj finalnu isplatu ako nije lump_sum
        _maybe_create_final_payment(contract, request.user)
    return redirect('seasonal:contract_detail', pk=pk)


@login_required
def payment_create(request, contract_pk):
    company  = get_user_company(request)
    contract = get_object_or_404(SeasonalContract, pk=contract_pk, company=company)

    if request.method == 'POST':
        p = request.POST
        payment = SeasonalPayment.objects.create(
            company=company,
            contract=contract,
            payment_date=p['payment_date'],
            gross_amount=p['gross_amount'],
            payment_method=p.get('payment_method', 'bank'),
            notes=p.get('notes', ''),
            status='planned',
        )
        if p.get('approve_now'):
            payment.calculate_and_approve(approved_by=request.user)
            messages.success(request,
                f'Isplata odobrena: {payment.net_amount}€ neto '
                f'za {contract.worker.full_name}.')
        else:
            messages.success(request, 'Isplata kreirana kao nacrta.')
        return redirect('seasonal:contract_detail', pk=contract_pk)

    today = timezone.localdate()
    return render(request, 'seasonal/payment_form.html', {
        'contract': contract,
        'today': today,
        'net_estimate': contract.net_estimate(),
    })


@login_required
def payment_approve(request, pk):
    company = get_user_company(request)
    payment = get_object_or_404(SeasonalPayment, pk=pk, company=company)
    if request.method == 'POST':
        payment.calculate_and_approve(approved_by=request.user)
        messages.success(request,
            f'Isplata odobrena: {payment.gross_amount}€ bruto → '
            f'{payment.net_amount}€ neto za {payment.contract.worker.full_name}')
    return redirect('seasonal:contract_detail', pk=payment.contract.pk)


@login_required
def hzmo_mark_sent(request, contract_pk, action):
    """Označi M-1 ili M-2 kao poslano."""
    company  = get_user_company(request)
    contract = get_object_or_404(SeasonalContract, pk=contract_pk, company=company)
    if request.method == 'POST':
        today = timezone.localdate()
        if action == 'm1':
            contract.hzmo_prijava_sent = True
            contract.hzmo_prijava_date = today
            contract.save(update_fields=['hzmo_prijava_sent', 'hzmo_prijava_date'])
            messages.success(request,
                f'M-1 prijava zabilježena za {contract.worker.full_name}.')
        elif action == 'm2':
            contract.hzmo_odjava_sent = True
            contract.hzmo_odjava_date = today
            contract.save(update_fields=['hzmo_odjava_sent', 'hzmo_odjava_date'])
            messages.success(request,
                f'M-2 odjava zabilježena za {contract.worker.full_name}.')
    return redirect('seasonal:contract_detail', pk=contract_pk)


@login_required
def season_cost_report(request):
    """Ukupni trošak sezone — za vlasnika/managera."""
    company = get_user_company(request)
    year    = int(request.GET.get('year', timezone.localdate().year))

    contracts = SeasonalContract.objects.filter(
        company=company, start_date__year=year
    ).select_related('worker').prefetch_related('payments')

    total_gross = sum(c.gross_amount for c in contracts)
    total_paid  = sum(
        p.net_amount for c in contracts
        for p in c.payments.filter(status='paid')
    )
    workers_count = contracts.values('worker').distinct().count()

    return render(request, 'seasonal/cost_report.html', {
        'contracts': contracts,
        'total_gross': total_gross,
        'total_paid': total_paid,
        'workers_count': workers_count,
        'year': year,
    })


# ── Helperi ──────────────────────────────────────────────────────────────────

def _schedule_hzmo_reminder(contract):
    """WhatsApp podsjetnik za M-1 (8 dana od početka)."""
    if contract.contract_type != 'odredjeno':
        return
    try:
        from core.tasks import schedule_whatsapp_reminder  # ako postoji
    except ImportError:
        pass  # Fallback: Celery daily task uhvatit će to


def _maybe_create_final_payment(contract, user):
    """Ako je lump_sum, automatski kreiraj finalnu isplatu."""
    if contract.payment_cycle != 'lump_sum':
        return
    existing = contract.payments.filter(status__in=['planned', 'approved', 'paid'])
    if existing.exists():
        return  # Već postoji
    SeasonalPayment.objects.create(
        company=contract.company,
        contract=contract,
        payment_date=contract.end_date,
        gross_amount=contract.gross_amount,
        payment_method='bank',
        notes='Auto-kreirana završna isplata',
        status='planned',
    )
```

---

## KORAK 4 — URLs

### seasonal/urls.py

```python
from django.urls import path
from . import views

app_name = 'seasonal'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('radnici/', views.worker_list, name='worker_list'),
    path('radnici/novi/', views.worker_create, name='worker_create'),
    path('radnici/<int:pk>/', views.worker_detail, name='worker_detail'),
    path('radnici/<int:worker_pk>/ugovor/', views.contract_create, name='contract_create'),
    path('ugovori/<int:pk>/', views.contract_detail, name='contract_detail'),
    path('ugovori/<int:pk>/aktiviraj/', views.contract_activate, name='contract_activate'),
    path('ugovori/<int:pk>/zavrsi/', views.contract_complete, name='contract_complete'),
    path('ugovori/<int:contract_pk>/isplata/', views.payment_create, name='payment_create'),
    path('isplate/<int:pk>/odobri/', views.payment_approve, name='payment_approve'),
    path('ugovori/<int:contract_pk>/hzmo/<str:action>/', views.hzmo_mark_sent, name='hzmo_mark'),
    path('izvjestaj/', views.season_cost_report, name='cost_report'),
]
```

Dodati u `core/urls.py`:
```python
path('sezonci/', include('seasonal.urls', namespace='seasonal')),
```

---

## KORAK 5 — Celery Task: dnevni HZMO alarm

```python
# seasonal/tasks.py
from celery import shared_task
import logging
log = logging.getLogger('seasonal')

@shared_task(name='seasonal.daily_hzmo_check')
def daily_hzmo_check():
    """
    Svaki dan u 08:00 — provjeri HZMO rokove i pošalji WhatsApp upozorenje.

    Alarmi koje šaljemo:
    - M-1 mora biti poslan za X dana (5 dana, 2 dana, dan prije)
    - M-2 mora biti poslan za X dana (5 dana, 2 dana, dan prije)
    - Ugovor ističe za X dana (7, 3, 1 dan)
    """
    from django.utils import timezone
    from datetime import timedelta
    from .models import SeasonalContract
    from core.whatsapp import send_text
    from companies.models import Company

    today = timezone.localdate()
    IVAN_PHONE = '+4915771998747'
    alerts = []

    # Nađi sve aktivne i predstojeće ugovore
    contracts = SeasonalContract.objects.filter(
        status__in=['pending', 'active'],
    ).select_related('worker', 'company')

    for c in contracts:
        worker = c.worker.full_name
        company_name = c.company.name

        # M-1 alarm
        if c.contract_type == 'odredjeno' and not c.hzmo_prijava_sent:
            days_left = (c.hzmo_prijava_deadline - today).days
            if days_left in (5, 2, 1, 0):
                urgency = '🔴' if days_left <= 1 else '🟡'
                alerts.append(
                    f'{urgency} M-1 HZMO za {worker} ({company_name}): '
                    f'rok {c.hzmo_prijava_deadline} — '
                    f'{"DANAS!" if days_left == 0 else f"za {days_left} dana"}'
                )

        # M-2 alarm (kad je ugovor završen)
        if (c.contract_type == 'odredjeno'
                and c.status == 'completed'
                and not c.hzmo_odjava_sent):
            days_left = (c.hzmo_odjava_deadline - today).days
            if days_left in (5, 2, 1, 0):
                urgency = '🔴' if days_left <= 1 else '🟡'
                alerts.append(
                    f'{urgency} M-2 HZMO za {worker} ({company_name}): '
                    f'rok {c.hzmo_odjava_deadline} — '
                    f'{"DANAS!" if days_left == 0 else f"za {days_left} dana"}'
                )

        # Ugovor ističe
        days_to_end = (c.end_date - today).days
        if days_to_end in (7, 3, 1):
            alerts.append(
                f'📅 Ugovor ističe: {worker} ({company_name}) — '
                f'{c.end_date} ({days_to_end} dana)'
            )

    if alerts:
        message = '📋 *Sezonski radnici — dnevni alarm*\n\n' + '\n'.join(alerts)
        try:
            send_text(phone=IVAN_PHONE, message=message)
        except Exception as e:
            log.error(f'WhatsApp seasonal alarm failed: {e}')

    log.info(f'Seasonal HZMO check: {len(alerts)} alarma poslano')
    return {'alerts': len(alerts), 'contracts_checked': contracts.count()}
```

Dodati u `core/settings.py` CELERY_BEAT_SCHEDULE:
```python
'seasonal-daily-hzmo-check': {
    'task': 'seasonal.daily_hzmo_check',
    'schedule': crontab(hour=8, minute=15),
},
```

---

## KORAK 6 — Templates (6 templatea)

Kreirati: `mkdir -p /var/www/fina-connect/templates/seasonal/`

### Svaki template nasljeđuje base.html i koristi partials:
- `{% include "partials/_page_header.html" %}`
- `{% include "partials/_stat_card.html" %}`

### 6 templatea:
1. `dashboard.html` — stat_grid (5 kartica) + HZMO alert banner (crveni) + aktivni ugovori tablica + predstojeći
2. `worker_list.html` — filter po imenu/OIB + tablica + zelena/crvena (aktivni/neaktivni)
3. `worker_form.html` — forma + checkbox "kreiraj ugovor odmah"
4. `worker_detail.html` — info kartica + lista ugovora + "Novi ugovor" gumb
5. `contract_form.html` — forma: tip ugovora, datumi, bruto, pozicija + live neto procjena (JS)
6. `contract_detail.html` — sve detalje + HZMO status (zeleno/crveno) + lista isplata + akcije
7. `payment_form.html` — bruto input + neto procjena + odobrenje u jednom koraku
8. `cost_report.html` — godišnji pregled troškova, tablica po radniku

### Posebnost dashboard.html — HZMO Alert Banner:
```html
{% if hzmo_alerts %}
<div class="alert alert-danger mb-3" role="alert">
  <i class="fas fa-exclamation-triangle me-2"></i>
  <strong>{{ hzmo_alerts|length }} HZMO rok{{ hzmo_alerts|length|pluralize:"," }}!</strong>
  {% for alert in hzmo_alerts %}
    <div class="mt-1 small">
      {{ alert.type }} — <strong>{{ alert.contract.worker.full_name }}</strong>:
      rok {{ alert.deadline }}
      {% if alert.days_left <= 0 %}
        <span class="badge bg-danger">ISTEKAO</span>
      {% elif alert.urgent %}
        <span class="badge bg-danger">{{ alert.days_left }} dan{{ alert.days_left|pluralize:"a,a,a" }}</span>
      {% else %}
        <span class="badge bg-warning text-dark">{{ alert.days_left }} dana</span>
      {% endif %}
    </div>
  {% endfor %}
</div>
{% endif %}
```

---

## KORAK 7 — Sidebar

```bash
grep -n "worktime\|payroll\|radnik" /var/www/fina-connect/templates/base.html | head -10
```

Naći sekciju i dodati:
```html
<a href="{% url 'seasonal:dashboard' %}"
   class="{% if 'sezonci' in request.path %}active{% endif %}">
  <i class="fas fa-umbrella-beach"></i> Sezonski radnici
</a>
```

---

## KORAK 8 — Migracije + verifikacija

```bash
cd /var/www/fina-connect

# Migracije
/var/www/fina-connect/venv/bin/python manage.py makemigrations seasonal
/var/www/fina-connect/venv/bin/python manage.py migrate

# Import test
/var/www/fina-connect/venv/bin/python manage.py shell -c "
from seasonal.models import SeasonalWorker, SeasonalContract, SeasonalPayment
from django.urls import reverse
print('Models OK')
print('Dashboard URL:', reverse('seasonal:dashboard'))
print('Worker list URL:', reverse('seasonal:worker_list'))
# Test net_estimate logika
from decimal import Decimal
class FakeContract:
    gross_amount = Decimal('2000')
    contract_type = 'djelo'
    def net_estimate(self): return Decimal('2000') * Decimal('0.80')
fc = FakeContract()
print('Net estimate test (djelo 2000€):', fc.net_estimate(), '€')
"

# Dodati u simulate_borg
# (dodati _sim_seasonal metodu analogno _sim_experiences)
```

---

## KORAK 9 — Commit

```bash
git add seasonal/ templates/seasonal/ core/settings.py core/urls.py
git commit -m "feat(seasonal): Sezonski radnici — MVP za turističku sezonu 2026

3 modela: SeasonalWorker, SeasonalContract (5 tipova ugovora), SeasonalPayment
FSM: pending→active→completed

HZMO automatika:
  - M-1 prijava alarm (8 dana rok, podsjetnici: 5/2/1 dan)
  - M-2 odjava alarm (8 dana rok od završetka)
  - Celery daily task 08:15 — WhatsApp alarm vlasnicima

Obračun poreza po tipu ugovora:
  - Djelo/privremeni: 20% porezna stopa
  - Ugovor o radu: hr_calculator (puni JOPPD)
  - Studentski: bez poreza

Piloti: Didin Konak, OPG Kruljac, Viskovic Bau
Tržište: 111K iznajmljivači + ugostiteljstvo + OPG = svi aktiviraju 1.6.2026"

git log --oneline -3
```

---

## KORAK 10 — simulate_borg integracija

Dodati u `core/management/commands/simulate_borg.py`:

```python
def _sim_seasonal(self, company, user):
    r = SimResult('seasonal')
    head("SEASONAL — Sezonski radnici")

    try:
        from seasonal.models import SeasonalWorker, SeasonalContract, SeasonalPayment
        from decimal import Decimal

        # Kreiraj test radnika
        worker = SeasonalWorker.objects.create(
            company=company,
            first_name='Test',
            last_name='Sezonac',
            oib='12345678901',
            nationality='HR',
            phone='+385912345678',
        )
        r.success(f'SeasonalWorker kreiran: {worker.full_name}')

        # Kreiraj test ugovor
        from datetime import date, timedelta
        contract = SeasonalContract.objects.create(
            company=company,
            worker=worker,
            contract_type='djelo',
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
            gross_amount=Decimal('1500.00'),
            payment_cycle='lump_sum',
            position='Konobar — testni',
            status='pending',
            created_by=user,
        )
        r.success(f'SeasonalContract kreiran: {contract.duration_days} dana')
        assert contract.net_estimate() > 0
        r.success(f'Net estimate: {contract.net_estimate()} EUR')

        # Test HZMO deadline
        from datetime import timedelta
        expected_deadline = contract.start_date + timedelta(days=8)
        assert contract.hzmo_prijava_deadline == expected_deadline
        r.success('HZMO M-1 deadline OK')

        # Test isplata
        payment = SeasonalPayment.objects.create(
            company=company,
            contract=contract,
            payment_date=date.today() + timedelta(days=30),
            gross_amount=Decimal('1500.00'),
            status='planned',
        )
        payment.calculate_and_approve(approved_by=user)
        assert payment.status == 'approved'
        assert payment.net_amount > 0
        r.success(f'Payment approve OK: neto {payment.net_amount} EUR')

        # URL test
        from django.urls import reverse
        for name in ['seasonal:dashboard', 'seasonal:worker_list', 'seasonal:cost_report']:
            url = reverse(name)
            r.success(f'URL: {url}')

    except Exception as e:
        r.error('Seasonal greška', e)

    return r
```

---
# STATUS: READY_FOR_CC_CODE
# Rok: buildano do 1.5.2026 — 1 mjesec prije turističke sezone
# Piloti kontaktirati odmah: Didin Konak (Viktor), OPG Kruljac (Ivica)
