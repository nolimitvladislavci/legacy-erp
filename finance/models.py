from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from companies.models import Company
from core.managers import CompanyManager
from documents.models import Document
from partners.models import Partner


class TransactionCategory(models.Model):

    class CategoryType(models.TextChoices):
        INCOME = 'income', _('Prihod')
        EXPENSE = 'expense', _('Rashod')
        BOTH = 'both', _('Prihod i rashod')

    name = models.CharField(max_length=100, unique=True, verbose_name=_('Naziv kategorije'))
    category_type = models.CharField(
        max_length=10,
        choices=CategoryType.choices,
        default=CategoryType.BOTH,
        verbose_name=_('Tip'),
    )
    code = models.CharField(max_length=20, unique=True, verbose_name=_('Šifra'), help_text=_('Kratka oznaka (npr. SALES, RENT, SALARY)'))
    description = models.CharField(max_length=255, blank=True, verbose_name=_('Opis'))
    is_active = models.BooleanField(default=True, verbose_name=_('Aktivna'))
    sort_order = models.PositiveSmallIntegerField(default=0, verbose_name=_('Redoslijed'))

    class Meta:
        verbose_name = _('Kategorija transakcije')
        verbose_name_plural = _('Kategorije transakcija')
        ordering = ['sort_order', 'name']

    def __str__(self):
        return f"{self.code} – {self.name}"


class Transaction(models.Model):
    DIRECTION_CHOICES = [
        ('income', _('Uplata / Prihod')),
        ('expense', _('Isplata / Rashod')),
    ]

    company   = models.ForeignKey(Company, on_delete=models.CASCADE, verbose_name=_('Tvrtka'))
    objects   = CompanyManager()
    partner   = models.ForeignKey(Partner, on_delete=models.PROTECT, related_name='transactions', verbose_name=_('Partner'))
    document  = models.ForeignKey(Document, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='transactions', verbose_name=_('Vezani dokument'))

    # Nova veza na račun (za automatsku rekoncilaciju)
    invoice   = models.ForeignKey(
        'invoicing.Invoice', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='transactions',
        verbose_name=_('Vezani račun'),
    )

    # Kategorija
    category  = models.ForeignKey(
        TransactionCategory, on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name=_('Kategorija'),
    )

    amount    = models.DecimalField(max_digits=12, decimal_places=2, verbose_name=_('Iznos'))
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name=_('Iznos PDV-a'))
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES, verbose_name=_('Smjer'))

    date      = models.DateField(verbose_name=_('Datum transakcije'))
    value_date = models.DateField(null=True, blank=True, verbose_name=_('Datum valute'))
    description = models.CharField(max_length=255, verbose_name=_('Opis'))
    reference = models.CharField(max_length=100, blank=True, verbose_name=_('Referenca / Poziv na broj'))

    # Račun na koji je plaćeno / s kojeg je plaćeno
    payment_account = models.CharField(max_length=100, blank=True, verbose_name=_('Platni račun (IBAN/blagajna)'))

    # Rekoncilacija
    is_reconciled = models.BooleanField(default=False, verbose_name=_('Rekoncilirano'))

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Transakcija')
        verbose_name_plural = _('Transakcije')
        ordering = ['-date', '-created_at']

    def save(self, *args, **kwargs):
        if not self.partner_id:
            raise ValidationError('Svaka financijska transakcija mora biti vezana uz Partnera.')
        # Auto-reconcile if invoice is set and amount matches
        if self.invoice_id and not self.is_reconciled:
            try:
                if self.invoice.total == self.amount:
                    self.is_reconciled = True
            except Exception:
                pass
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.date} – {self.amount} ({self.get_direction_display()})"
