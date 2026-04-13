from decimal import Decimal, ROUND_HALF_UP
from django.conf import settings
from django.db import models, DatabaseError, IntegrityError
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ObjectDoesNotExist
from core.managers import CompanyManager


class HonorarContract(models.Model):
    """Ugovor o djelu / autorski honorar / studentski ugovor."""

    CONTRACT_TYPES = [
        ('ugovor_djelo', 'Ugovor o djelu'),
        ('autorski', 'Autorski honorar'),
        ('studentski', 'Studentski ugovor'),
        ('clanarina_uprave', 'Članarina uprave'),
    ]

    STATUS_CHOICES = [
        ('draft', _('Nacrt')),
        ('active', _('Aktivan')),
        ('completed', _('Završen')),
        ('cancelled', _('Poništen')),
    ]

    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='honorar_contracts', verbose_name=_('Tvrtka'))
    contractor = models.ForeignKey(
        'partners.Partner', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='honorar_contracts', verbose_name=_('Izvršitelj'))
    contract_type = models.CharField(
        max_length=20, choices=CONTRACT_TYPES,
        verbose_name=_('Vrsta ugovora'))
    contract_number = models.CharField(
        max_length=50, verbose_name=_('Broj ugovora'))
    description = models.TextField(
        blank=True, verbose_name=_('Opis'))
    gross_amount = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name=_('Bruto iznos'))
    start_date = models.DateField(verbose_name=_('Datum početka'))
    end_date = models.DateField(verbose_name=_('Datum završetka'))
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='draft',
        verbose_name=_('Status'))
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        verbose_name=_('Kreirao'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = CompanyManager()

    class Meta:
        ordering = ['-created_at']
        unique_together = ['company', 'contract_number']
        verbose_name = _('Ugovor o honoraru')
        verbose_name_plural = _('Ugovori o honorarima')

    def __str__(self):
        return f"{self.contract_number} — {self.get_contract_type_display()}"


class HonorarCalculation(models.Model):
    """Obračun honorara — porez, doprinosi, neto."""

    contract = models.ForeignKey(
        HonorarContract, on_delete=models.CASCADE,
        related_name='calculations', verbose_name=_('Ugovor'))
    calculation_date = models.DateField(verbose_name=_('Datum obračuna'))
    gross_amount = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name=_('Bruto iznos'))
    tax_base = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name=_('Porezna osnovica'))
    income_tax = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name=_('Porez na dohodak'))
    surtax_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        verbose_name=_('Stopa prireza (%)'))
    surtax_amount = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name=_('Prirez'))
    health_insurance = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name=_('Doprinos za ZO'))
    pension_mio1 = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name=_('MIO I. stup'))
    net_amount = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name=_('Neto za isplatu'))
    total_cost = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name=_('Ukupni trošak poslodavca'))
    is_posted = models.BooleanField(
        default=False, verbose_name=_('Proknjiženo'))
    journal_entry = models.ForeignKey(
        'konto.JournalEntry', on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name=_('Temeljnica'))
    objects = CompanyManager()

    class Meta:
        ordering = ['-calculation_date']
        verbose_name = _('Obračun honorara')
        verbose_name_plural = _('Obračuni honorara')

    def __str__(self):
        return f"Obračun {self.contract.contract_number} — {self.calculation_date}"

    @property
    def company(self):
        return self.contract.company

    @property
    def company_id(self):
        return self.contract.company_id

    def _r(self, val):
        """Zaokruži na 2 decimale."""
        return Decimal(val).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def calculate(self):
        """
        Automatski izračunaj sve iznose prema HR poreznim pravilima.

        Ugovor o djelu:
            - Normirani troškovi: 30%
            - Porez na dohodak: 20% od porezne osnovice
            - ZO doprinos: 16.5% od bruto
            - MIO I. stup: 10% od bruto

        Autorski honorar:
            - Normirani troškovi: 40%
            - Porez na dohodak: 20% od porezne osnovice
            - ZO doprinos: 16.5% od bruto
            - MIO I. stup: 0% (registrirani) — default

        Studentski ugovor:
            - SC provizija: ~12%, nema poreza ni doprinosa

        Članarina uprave:
            - Isto kao ugovor o djelu
        """
        gross = self._r(self.gross_amount)
        ct = self.contract.contract_type

        if ct == 'studentski':
            # Studentski: samo SC provizija (~12%), ostatak je neto
            sc_fee = self._r(gross * Decimal('0.12'))
            self.tax_base = Decimal('0')
            self.income_tax = Decimal('0')
            self.surtax_amount = Decimal('0')
            self.health_insurance = Decimal('0')
            self.pension_mio1 = Decimal('0')
            self.net_amount = self._r(gross - sc_fee)
            self.total_cost = gross
            return

        # Normirani troškovi
        if ct == 'autorski':
            norm_rate = Decimal('0.40')  # 40% normirani troškovi
            mio_rate = Decimal('0.00')   # registrirani obrtnik: 0%
        else:
            # ugovor_djelo ili clanarina_uprave
            norm_rate = Decimal('0.30')  # 30% normirani troškovi
            mio_rate = Decimal('0.10')   # 10% MIO I

        # Porezna osnovica = bruto * (1 - normirani troškovi)
        self.tax_base = self._r(gross * (Decimal('1') - norm_rate))

        # Porez na dohodak = 20%
        self.income_tax = self._r(self.tax_base * Decimal('0.20'))

        # Prirez
        surtax_r = self.surtax_rate or Decimal('0')
        self.surtax_amount = self._r(self.income_tax * surtax_r / Decimal('100'))

        # Doprinosi (od bruto iznosa)
        self.health_insurance = self._r(gross * Decimal('0.165'))
        self.pension_mio1 = self._r(gross * mio_rate)

        # Neto = bruto - porez - prirez - ZO - MIO
        self.net_amount = self._r(
            gross - self.income_tax - self.surtax_amount
            - self.health_insurance - self.pension_mio1
        )

        # Ukupni trošak poslodavca = bruto (doprinosi su uključeni u bruto za honorare)
        self.total_cost = gross


class HonorarJOPPD(models.Model):
    """JOPPD stavka za honorar — prijava Poreznoj upravi."""

    calculation = models.ForeignKey(
        HonorarCalculation, on_delete=models.CASCADE,
        related_name='joppd_items', verbose_name=_('Obračun'))
    joppd_date = models.DateField(verbose_name=_('Datum JOPPD'))
    joppd_oznaka = models.CharField(
        max_length=10, verbose_name=_('Oznaka primitka'),
        help_text='4002 = ugovor o djelu, 4080 = autorski')
    oib_primatelja = models.CharField(
        max_length=11, verbose_name=_('OIB primatelja'))
    bruto = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name=_('Bruto'))
    porez = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name=_('Porez'))
    prirez = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name=_('Prirez'))
    mio1 = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name=_('MIO I. stup'))
    zo = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name=_('ZO doprinos'))
    neto = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name=_('Neto'))
    is_reported = models.BooleanField(
        default=False, verbose_name=_('Prijavljeno'))

    class Meta:
        ordering = ['-joppd_date']
        verbose_name = _('JOPPD stavka honorara')
        verbose_name_plural = _('JOPPD stavke honorara')

    def __str__(self):
        return f"JOPPD {self.joppd_oznaka} — {self.oib_primatelja} ({self.joppd_date})"


class HonorarPayment(models.Model):
    """Isplata honorara."""

    calculation = models.ForeignKey(
        HonorarCalculation, on_delete=models.CASCADE,
        related_name='payments', verbose_name=_('Obračun'))
    payment_date = models.DateField(verbose_name=_('Datum isplate'))
    amount = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name=_('Iznos'))
    bank_account = models.ForeignKey(
        'konto.BankAccount', on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name=_('Žiro račun'))
    reference = models.CharField(
        max_length=100, blank=True,
        verbose_name=_('Poziv na broj'))
    is_paid = models.BooleanField(
        default=False, verbose_name=_('Isplaćeno'))

    class Meta:
        ordering = ['-payment_date']
        verbose_name = _('Isplata honorara')
        verbose_name_plural = _('Isplate honorara')

    def __str__(self):
        status = 'isplaćeno' if self.is_paid else 'čeka'
        return f"Isplata {self.amount} EUR — {status}"
