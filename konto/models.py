from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.managers import CompanyManager


# ─────────────────────────────────────────────
# 1. KONTNI PLAN (Chart of Accounts)
# ─────────────────────────────────────────────
class AccountType(models.TextChoices):
    ASSET = 'asset', _('Imovina')           # Klasa 0-3
    LIABILITY = 'liability', _('Obveze')     # Klasa 4
    EQUITY = 'equity', _('Kapital')          # Klasa 9
    INCOME = 'income', _('Prihodi')          # Klasa 7
    EXPENSE = 'expense', _('Rashodi')        # Klasa 4-6


class KontoAccount(models.Model):
    """Konto iz kontnog plana (npr. 1000 - Žiro račun, 1200 - Potraživanja od kupaca)"""
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                                related_name='konto_accounts')
    code = models.CharField(max_length=10, verbose_name=_('Šifra konta'),
        help_text='npr. 1000, 1200, 2200, 4000, 7000')
    name = models.CharField(max_length=200, verbose_name=_('Naziv konta'))
    account_type = models.CharField(max_length=20, choices=AccountType.choices,
                                     verbose_name=_('Vrsta konta'))
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='children', verbose_name=_('Nadređeni konto'))
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)
    objects = CompanyManager()

    class Meta:
        ordering = ['code']
        unique_together = ['company', 'code']
        verbose_name = _('Konto')
        verbose_name_plural = _('Kontni plan')

    def __str__(self):
        return f"{self.code} - {self.name}"

    @property
    def balance(self):
        """Trenutni saldo konta"""
        from django.db.models import Sum
        debits = self.ledgerline_entries.filter(side='debit').aggregate(
            t=Sum('amount'))['t'] or Decimal('0')
        credits = self.ledgerline_entries.filter(side='credit').aggregate(
            t=Sum('amount'))['t'] or Decimal('0')
        # Asset i Expense rastu s dugovne strane
        if self.account_type in ('asset', 'expense'):
            return debits - credits
        # Liability, Equity, Income rastu s potražne strane
        return credits - debits


# ─────────────────────────────────────────────
# 2. ŽIRO RAČUNI (Bank Accounts)
# ─────────────────────────────────────────────
class BankAccount(models.Model):
    """Žiro račun firme u banci"""
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                                related_name='bank_accounts')
    name = models.CharField(max_length=200, verbose_name=_('Naziv'),
        help_text='npr. Glavno Poslovanje - PBZ')
    iban = models.CharField(max_length=34, verbose_name='IBAN')
    bank_name = models.CharField(max_length=100, verbose_name=_('Banka'))
    swift = models.CharField(max_length=11, blank=True, verbose_name='SWIFT/BIC')
    currency = models.CharField(max_length=3, default='EUR', verbose_name=_('Valuta'))

    # Veza na kontni plan
    konto_account = models.ForeignKey(KontoAccount, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name=_('Konto'),
        help_text='npr. 1000 - Žiro račun u banci')

    opening_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0,
        verbose_name=_('Početni saldo'))
    current_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0,
        verbose_name=_('Trenutni saldo'))
    is_active = models.BooleanField(default=True)
    is_primary = models.BooleanField(default=False, verbose_name=_('Primarni račun'))

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = CompanyManager()

    class Meta:
        ordering = ['-is_primary', 'name']
        verbose_name = _('Žiro račun')
        verbose_name_plural = _('Žiro računi')

    def __str__(self):
        return f"{self.name} ({self.iban[-8:]})"

    def recalculate_balance(self):
        """Preračunaj saldo iz svih transakcija"""
        from django.db.models import Sum
        inflows = self.transactions.filter(
            transaction_type='inflow'
        ).aggregate(t=Sum('amount'))['t'] or Decimal('0')
        outflows = self.transactions.filter(
            transaction_type='outflow'
        ).aggregate(t=Sum('amount'))['t'] or Decimal('0')
        self.current_balance = self.opening_balance + inflows - outflows
        self.save(update_fields=['current_balance', 'updated_at'])


# ─────────────────────────────────────────────
# 3. BANKOVNE TRANSAKCIJE (izvod)
# ─────────────────────────────────────────────
class BankTransaction(models.Model):
    """Jedna stavka bankovnog izvoda"""

    TRANSACTION_TYPES = [
        ('inflow', _('Uplata (priljev)')),
        ('outflow', _('Isplata (odljev)')),
    ]

    STATUS_CHOICES = [
        ('unmatched', _('Nepariran')),
        ('matched', _('Pariran')),
        ('ignored', _('Ignoriran')),
    ]

    bank_account = models.ForeignKey(BankAccount, on_delete=models.SET_NULL,
                                     null=True, blank=True, related_name='transactions')
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE)

    # Podaci iz izvoda
    transaction_date = models.DateField(verbose_name=_('Datum transakcije'))
    value_date = models.DateField(null=True, blank=True, verbose_name=_('Datum valute'))
    amount = models.DecimalField(max_digits=14, decimal_places=2, verbose_name=_('Iznos'))
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)

    # Detalji
    counterparty_name = models.CharField(max_length=300, blank=True,
        verbose_name=_('Platitelj/Primatelj'))
    counterparty_iban = models.CharField(max_length=34, blank=True,
        verbose_name=_('IBAN platitelja/primatelja'))
    description = models.TextField(blank=True, verbose_name=_('Opis plaćanja'))
    reference_number = models.CharField(max_length=100, blank=True,
        verbose_name=_('Poziv na broj'))

    # Pariranje
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='unmatched')
    matched_invoice = models.ForeignKey('invoicing.Invoice', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='bank_transactions',
        verbose_name=_('Pariran račun'))

    # Knjiženje
    is_booked = models.BooleanField(default=False, verbose_name=_('Proknjiženo'))

    # Import metadata
    import_batch = models.CharField(max_length=100, blank=True,
        help_text='ID importa za grupiranje')
    external_id = models.CharField(max_length=200, blank=True,
        help_text='ID iz banke za dedup')

    created_at = models.DateTimeField(auto_now_add=True)
    objects = CompanyManager()

    class Meta:
        ordering = ['-transaction_date', '-id']
        verbose_name = _('Bankovna transakcija')
        verbose_name_plural = _('Bankovne transakcije')
        indexes = [
            models.Index(fields=['company', '-transaction_date']),
            models.Index(fields=['status', 'company']),
            models.Index(fields=['reference_number']),
        ]

    def __str__(self):
        sign = '+' if self.transaction_type == 'inflow' else '-'
        return f"{self.transaction_date} {sign}{self.amount}\u20ac {self.counterparty_name[:30]}"


# ─────────────────────────────────────────────
# 4. KNJIŽENJE (Ledger Entries) - Dvostavno
# ─────────────────────────────────────────────
class JournalEntry(models.Model):
    """Temeljnica - grupa knjiženja koja mora biti u balansu (duguje = potražuje)"""
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                                related_name='journal_entries')
    entry_number = models.CharField(max_length=50, verbose_name=_('Broj temeljnice'))
    date = models.DateField(verbose_name=_('Datum knjiženja'))
    description = models.CharField(max_length=300, verbose_name=_('Opis'))

    # Izvor knjiženja
    SOURCE_TYPES = [
        ('invoice', _('Račun')),
        ('bank_statement', _('Bankovni izvod')),
        ('manual', _('Ručno knjiženje')),
        ('payroll', _('Obračun plaća')),
        ('pos', _('POS promet')),
        ('correction', _('Ispravak')),
        ('depreciation', _('Amortizacija')),
        ('membership', _('Članarina')),
        ('donation', _('Donacija')),
    ]
    source_type = models.CharField(max_length=30, blank=True, choices=SOURCE_TYPES)
    source_invoice = models.ForeignKey('invoicing.Invoice', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='journal_entries')
    source_transaction = models.ForeignKey(BankTransaction, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='journal_entries')

    is_posted = models.BooleanField(default=False, verbose_name=_('Proknjiženo'))
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    objects = CompanyManager()

    class Meta:
        ordering = ['-date', '-id']
        verbose_name = _('Temeljnica')
        verbose_name_plural = _('Temeljnice')
        unique_together = [['company', 'entry_number']]

    def __str__(self):
        return f"{self.entry_number} - {self.description}"

    def clean(self):
        from django.core.exceptions import ValidationError
        # Period lock check
        if self.date and self.company_id:
            if AccountingPeriod.is_period_locked(self.company, self.date.year, self.date.month):
                if not self.pk or JournalEntry.objects.filter(pk=self.pk, date=self.date).exists() is False:
                    raise ValidationError(
                        f"Razdoblje {self.date.month:02d}/{self.date.year} je zaključano. Knjiženje nije moguće."
                    )
        # Skip balance check for new entries (no lines yet)
        if self.pk and self.lines.exists():
            from django.db.models import Sum
            debits = self.lines.filter(side="debit").aggregate(t=Sum("amount"))["t"] or Decimal("0")
            credits = self.lines.filter(side="credit").aggregate(t=Sum("amount"))["t"] or Decimal("0")
            if debits != credits:
                raise ValidationError(
                    f"Temeljnica nije uravnotežena: duguje={debits}, potražuje={credits}, razlika={abs(debits - credits)}"
                )

    @property
    def is_balanced(self):
        """Provjera: duguje == potražuje"""
        from django.db.models import Sum
        debits = self.lines.filter(side='debit').aggregate(t=Sum('amount'))['t'] or Decimal('0')
        credits = self.lines.filter(side='credit').aggregate(t=Sum('amount'))['t'] or Decimal('0')
        return debits == credits

    @property
    def total_debit(self):
        from django.db.models import Sum
        return self.lines.filter(side='debit').aggregate(t=Sum('amount'))['t'] or Decimal('0')

    @property
    def total_credit(self):
        from django.db.models import Sum
        return self.lines.filter(side='credit').aggregate(t=Sum('amount'))['t'] or Decimal('0')


class LedgerLine(models.Model):
    """Jedan red knjiženja - dugovna ili potražna strana"""
    journal_entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE,
                                      related_name='lines')
    account = models.ForeignKey(KontoAccount, on_delete=models.PROTECT,
                                related_name='ledgerline_entries')
    side = models.CharField(max_length=6, choices=[
        ('debit', _('Duguje')),
        ('credit', _('Potražuje')),
    ])
    amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    integrity_hash = models.CharField(max_length=64, blank=True, default='',
        verbose_name=_('Integrity Hash'), help_text='SHA-256 chain za GoBD audit')
    description = models.CharField(max_length=200, blank=True)
    cost_center = models.ForeignKey('CostCenter', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ledger_lines',
        verbose_name=_('Profitni centar'))

    class Meta:
        verbose_name = _('Stavka knjiženja')
        verbose_name_plural = _('Stavke knjiženja')

    def __str__(self):
        return f"{self.account.code} {'D' if self.side == 'debit' else 'P'} {self.amount}"

    def save(self, *args, **kwargs):
        import hashlib
        if not self.integrity_hash:
            data = f"{self.journal_entry_id}|{self.account_id}|{self.side}|{self.amount}"
            self.integrity_hash = hashlib.sha256(data.encode()).hexdigest()
        self.full_clean()
        super().save(*args, **kwargs)


# ─────────────────────────────────────────────
# 5. POREZNO RAZDOBLJE (Tax Period / USt-Voranmeldung)
# ─────────────────────────────────────────────

class TaxPeriod(models.Model):
    PERIOD_TYPES = [
        ('monthly', _('Miesięczny / Monatlich')),
        ('quarterly', _('Kvartalni / Quartal')),
        ('yearly', _('Godišnji / Jährlich')),
    ]

    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                                related_name='tax_periods')
    period_type = models.CharField(max_length=20, choices=PERIOD_TYPES, default='monthly')
    year = models.PositiveSmallIntegerField()
    month = models.PositiveSmallIntegerField(null=True, blank=True)   # 1-12
    quarter = models.PositiveSmallIntegerField(null=True, blank=True) # 1-4

    # Output VAT (izlazni PDV / Umsatzsteuer)
    total_output_vat = models.DecimalField(max_digits=14, decimal_places=2, default=0,
        verbose_name=_('Izlazni PDV'))
    # Input VAT (pretporez / Vorsteuer)
    total_input_vat = models.DecimalField(max_digits=14, decimal_places=2, default=0,
        verbose_name=_('Pretporez'))
    # Payable = output - input
    vat_payable = models.DecimalField(max_digits=14, decimal_places=2, default=0,
        verbose_name=_('PDV za uplatu'))
    # Revenue and expenses in period
    total_revenue = models.DecimalField(max_digits=14, decimal_places=2, default=0,
        verbose_name=_('Prihodi'))
    total_expenses = models.DecimalField(max_digits=14, decimal_places=2, default=0,
        verbose_name=_('Rashodi'))

    filing_deadline = models.DateField(null=True, blank=True,
        verbose_name=_('Rok prijave'))
    is_filed = models.BooleanField(default=False, verbose_name=_('Prijavljeno'))
    filed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = CompanyManager()

    class Meta:
        ordering = ['-year', '-month', '-quarter']
        unique_together = ['company', 'period_type', 'year', 'month', 'quarter']
        verbose_name = _('Porezno razdoblje')
        verbose_name_plural = _('Porezna razdoblja')

    def __str__(self):
        if self.period_type == 'monthly' and self.month:
            return f"{self.year}-{self.month:02d} ({self.company})"
        if self.period_type == 'quarterly' and self.quarter:
            return f"{self.year} Q{self.quarter} ({self.company})"
        return f"{self.year} ({self.company})"

    @property
    def period_label(self):
        if self.period_type == 'monthly' and self.month:
            import calendar
            return f"{calendar.month_name[self.month]} {self.year}"
        if self.period_type == 'quarterly' and self.quarter:
            return f"Q{self.quarter}/{self.year}"
        return str(self.year)


class TaxLineDetail(models.Model):
    """Per-rate VAT breakdown within a TaxPeriod."""
    period = models.ForeignKey(TaxPeriod, on_delete=models.CASCADE,
                               related_name='line_details')
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2,
        verbose_name=_('Stopa PDV-a (%)'))
    revenue_base = models.DecimalField(max_digits=14, decimal_places=2, default=0,
        verbose_name=_('Porezna osnovica'))
    output_vat = models.DecimalField(max_digits=14, decimal_places=2, default=0,
        verbose_name=_('Izlazni PDV'))

    class Meta:
        ordering = ['-tax_rate']
        unique_together = ['period', 'tax_rate']
        verbose_name = _('Stavka PDV-a')
        verbose_name_plural = _('Stavke PDV-a')

    def __str__(self):
        return f"{self.period} @ {self.tax_rate}%"


class AccountingPeriod(models.Model):
    """Accounting period lock - prevents posting to closed periods."""
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE)
    year = models.PositiveIntegerField()
    month = models.PositiveSmallIntegerField()
    is_locked = models.BooleanField(default=False)
    locked_at = models.DateTimeField(null=True, blank=True)
    locked_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='locked_periods')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    objects = CompanyManager()

    class Meta:
        unique_together = [['company', 'year', 'month']]
        ordering = ['-year', '-month']
        verbose_name = 'Obračunsko razdoblje'
        verbose_name_plural = 'Obračunska razdoblja'

    def __str__(self):
        return f"{self.month:02d}/{self.year} ({'zaključano' if self.is_locked else 'otvoreno'})"

    def lock(self, user=None):
        from django.utils import timezone
        self.is_locked = True
        self.locked_at = timezone.now()
        self.locked_by = user
        self.save(update_fields=['is_locked', 'locked_at', 'locked_by'])

    def unlock(self, user=None):
        self.is_locked = False
        self.locked_at = None
        self.locked_by = None
        self.save(update_fields=['is_locked', 'locked_at', 'locked_by'])

    @classmethod
    def is_period_locked(cls, company, year, month):
        try:
            period = cls.objects.get(company=company, year=year, month=month)
            return period.is_locked
        except cls.DoesNotExist:
            return False


# ───────────────���─────────────────────────────
# 6. PROFITNI CENTRI (Cost Centers)
# ─────────────────────────────────────────────
class CostCenter(models.Model):
    """Profitni centar / mjesto troška za analitiku po segmentima."""
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                                related_name='cost_centers')
    code = models.CharField(max_length=20, verbose_name=_('Šifra'))
    name = models.CharField(max_length=200, verbose_name=_('Naziv'))
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='children', verbose_name=_('Nadređeni centar'))
    manager = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True,
                                verbose_name=_('Odgovorna osoba'))
    budget_annual = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                                         verbose_name=_('Godišnji budžet'))
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    objects = CompanyManager()

    class Meta:
        ordering = ['code']
        unique_together = ['company', 'code']
        verbose_name = _('Profitni centar')
        verbose_name_plural = _('Profitni centri')

    def __str__(self):
        return f"{self.code} — {self.name}"

    @property
    def total_expenses(self):
        """Ukupni rashodi knjiženi na ovaj centar."""
        from django.db.models import Sum
        return self.ledger_lines.filter(side='debit').aggregate(
            t=Sum('amount'))['t'] or Decimal('0')

    @property
    def total_income(self):
        """Ukupni prihodi knjiženi na ovaj centar."""
        from django.db.models import Sum
        return self.ledger_lines.filter(side='credit').aggregate(
            t=Sum('amount'))['t'] or Decimal('0')

    @property
    def budget_remaining(self):
        return self.budget_annual - self.total_expenses
