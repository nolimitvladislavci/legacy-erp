"""
sales/models.py — 3 kritične rupe zatvorene:

1. CustomerPriceList + RabatMatrix — posebni cjenici za kupce
2. SalesOrder — narudžbenica kupca → otpremnica → faktura (P1/P7 flow)
3. OpenItem + IOSReport — saldakonti, otvorene stavke, IOS obrazac

AI inovacije:
  - SmartPricing: AI preporuča optimalne rabate na osnovu historije kupca
  - OrderPredictor: AI predviđa što će kupac naručiti (basket analysis)
  - PaymentPredictor: AI predviđa kad će kupac platiti (aging risk score)
"""

import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

# ════════════════════════════════════════════════════════════════
# 1. POSEBNI CJENICI — CustomerPriceList + RabatMatrix
# ════════════════════════════════════════════════════════════════

class RabatGroup(models.Model):
    """Rabatna grupa artikala — npr. 'Mliječni proizvodi', 'Pića'."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                                 related_name='rabat_groups')
    name = models.CharField(max_length=100, verbose_name=_('Naziv grupe'))
    code = models.CharField(max_length=20, blank=True, verbose_name=_('Šifra'))
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['name']
        verbose_name = _('Rabatna grupa')
        verbose_name_plural = _('Rabatne grupe')
        unique_together = [('company', 'code')]

    def __str__(self):
        return self.name


class CustomerPriceList(models.Model):
    """
    Posebni cjenik za kupca — definira rabate i fiksne cijene.
    Može biti po partneru ili po grupi partnera.
    Hijerarhija: Partner specifičan > Grupa partnera > Rabatna grupa > Standardna cijena
    """
    DISCOUNT_TYPE_CHOICES = [
        ('percent', _('Postotak (%)')),
        ('fixed_price', _('Fiksna cijena')),
        ('fixed_amount', _('Fiksni iznos popusta')),
        ('cassa_sconto', _('Cassa sconto (prijevremeno plaćanje)')),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                                 related_name='customer_price_lists')
    name = models.CharField(max_length=200, verbose_name=_('Naziv cjenika'))
    partner = models.ForeignKey('partners.Partner', on_delete=models.CASCADE,
                                 null=True, blank=True, related_name='customer_price_lists',
                                 verbose_name=_('Partner (kupac)'))
    partner_group = models.CharField(max_length=50, blank=True,
                                      verbose_name=_('Grupa partnera'),
                                      help_text=_('Alternativa: primijeni na sve partnere u grupi'))
    is_active = models.BooleanField(default=True)
    valid_from = models.DateField(null=True, blank=True, verbose_name=_('Vrijedi od'))
    valid_until = models.DateField(null=True, blank=True, verbose_name=_('Vrijedi do'))
    priority = models.PositiveIntegerField(default=10, verbose_name=_('Prioritet'),
                                            help_text=_('Manji broj = viši prioritet'))
    notes = models.TextField(blank=True)
    # AI metadata
    ai_suggested = models.BooleanField(default=False, verbose_name=_('AI preporučeno'))
    ai_confidence = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['priority', 'name']
        verbose_name = _('Posebni cjenik')
        verbose_name_plural = _('Posebni cjenici')

    def __str__(self):
        target = self.partner.name if self.partner else self.partner_group or 'Svi'
        return f'{self.name} → {target}'

    def is_valid(self):
        today = timezone.now().date()
        if self.valid_from and today < self.valid_from:
            return False
        if self.valid_until and today > self.valid_until:
            return False
        return self.is_active


class PriceListLine(models.Model):
    """Stavka posebnog cjenika — cijena/rabat za specifičan artikl ili grupu."""
    DISCOUNT_TYPE_CHOICES = CustomerPriceList.DISCOUNT_TYPE_CHOICES

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    price_list = models.ForeignKey(CustomerPriceList, on_delete=models.CASCADE,
                                    related_name='lines')
    item = models.ForeignKey('inventory.InventoryItem', on_delete=models.CASCADE,
                              null=True, blank=True, related_name='price_list_lines',
                              verbose_name=_('Artikl'))
    rabat_group = models.ForeignKey(RabatGroup, on_delete=models.SET_NULL,
                                     null=True, blank=True, verbose_name=_('Rabatna grupa'))
    discount_type = models.CharField(max_length=15, choices=DISCOUNT_TYPE_CHOICES,
                                      default='percent', verbose_name=_('Tip popusta'))
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                          verbose_name=_('Vrijednost'))
    min_quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                        verbose_name=_('Min. količina'),
                                        help_text=_('Količinski prag za aktivaciju'))
    # Cassa sconto
    cassa_days = models.PositiveIntegerField(default=0, verbose_name=_('Cassa dani'),
                                              help_text=_('Rok za prijevremeno plaćanje'))

    class Meta:
        ordering = ['rabat_group', 'item']
        verbose_name = _('Stavka cjenika')
        verbose_name_plural = _('Stavke cjenika')

    def __str__(self):
        target = self.item.name if self.item else (self.rabat_group.name if self.rabat_group else '—')
        return f'{target}: {self.discount_value} ({self.get_discount_type_display()})'

    def calculate_price(self, base_price, quantity=1):
        """Izračunaj cijenu nakon primjene popusta."""
        if quantity < self.min_quantity:
            return base_price
        if self.discount_type == 'percent':
            return base_price * (1 - self.discount_value / 100)
        elif self.discount_type == 'fixed_price':
            return self.discount_value
        elif self.discount_type == 'fixed_amount':
            return max(Decimal('0'), base_price - self.discount_value)
        return base_price


# ════════════════════════════════════════════════════════════════
# 2. SALES ORDER — narudžbenica kupca
# ════════════════════════════════════════════════════════════════

class SalesOrder(models.Model):
    """
    Narudžbenica kupca — P1/P7 flow (Fiskalizacija 2.0).
    Lifecycle: draft → confirmed → processing → shipped → invoiced → closed
    """
    STATUS_CHOICES = [
        ('draft', _('Nacrt')),
        ('confirmed', _('Potvrđena')),
        ('processing', _('U obradi')),
        ('shipped', _('Isporučeno')),
        ('invoiced', _('Fakturirano')),
        ('closed', _('Zatvorena')),
        ('cancelled', _('Otkazana')),
    ]
    PRIORITY_CHOICES = [
        (1, _('Niska')), (2, _('Normalna')), (3, _('Visoka')), (4, _('Hitna')),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                                 related_name='sales_orders')
    order_number = models.CharField(max_length=50, verbose_name=_('Broj narudžbe'))
    partner = models.ForeignKey('partners.Partner', on_delete=models.PROTECT,
                                 related_name='sales_orders', verbose_name=_('Kupac'))
    # Dates
    order_date = models.DateField(default=timezone.now, verbose_name=_('Datum narudžbe'))
    delivery_date = models.DateField(null=True, blank=True, verbose_name=_('Željeni datum isporuke'))
    # Financials
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_total = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                          verbose_name=_('Ukupni popust'))
    tax_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default='EUR')
    # Status
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='draft')
    priority = models.PositiveSmallIntegerField(choices=PRIORITY_CHOICES, default=2)
    # Linked documents (P1/P7 flow)
    otpremnica = models.ForeignKey('propter.Otpremnica', on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name='sales_orders',
                                    verbose_name=_('Otpremnica'))
    invoice = models.ForeignKey('invoicing.Invoice', on_delete=models.SET_NULL,
                                 null=True, blank=True, related_name='sales_orders',
                                 verbose_name=_('Faktura'))
    # Price list
    price_list = models.ForeignKey(CustomerPriceList, on_delete=models.SET_NULL,
                                    null=True, blank=True, verbose_name=_('Posebni cjenik'))
    # Delivery
    delivery_address = models.TextField(blank=True, verbose_name=_('Adresa isporuke'))
    warehouse = models.ForeignKey('inventory.Warehouse', on_delete=models.SET_NULL,
                                   null=True, blank=True, verbose_name=_('Skladište'))
    # Notes
    notes = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True, verbose_name=_('Interne napomene'))
    # AI
    ai_predicted = models.BooleanField(default=False, verbose_name=_('AI predviđena'))
    ai_suggested_items = models.JSONField(default=list, blank=True,
                                           help_text=_('AI sugestije artikala za cross-sell'))
    # Meta
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-order_date', '-created_at']
        verbose_name = _('Narudžbenica kupca')
        verbose_name_plural = _('Narudžbenice kupaca')
        unique_together = [('company', 'order_number')]

    def __str__(self):
        return f'{self.order_number} — {self.partner.name}'

    def recalculate(self):
        """Preračunaj ukupne iznose iz stavki."""
        lines = self.lines.all()
        self.subtotal = sum(l.line_total for l in lines)
        self.discount_total = sum(l.discount_amount for l in lines)
        self.tax_total = sum(l.tax_amount for l in lines)
        self.total = self.subtotal - self.discount_total + self.tax_total
        self.save(update_fields=['subtotal', 'discount_total', 'tax_total', 'total'])

    @property
    def fulfillment_percent(self):
        """Postotak isporučenih stavki."""
        lines = self.lines.all()
        if not lines:
            return 0
        fulfilled = sum(1 for l in lines if l.delivered_quantity >= l.quantity)
        return round(fulfilled / lines.count() * 100)


class SalesOrderLine(models.Model):
    """Stavka narudžbenice kupca."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(SalesOrder, on_delete=models.CASCADE, related_name='lines')
    item = models.ForeignKey('inventory.InventoryItem', on_delete=models.PROTECT,
                              verbose_name=_('Artikl'))
    quantity = models.DecimalField(max_digits=12, decimal_places=4, verbose_name=_('Količina'))
    unit = models.CharField(max_length=20, default='kom')
    unit_price = models.DecimalField(max_digits=12, decimal_places=4, verbose_name=_('Jed. cijena'))
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0,
                                            verbose_name=_('Popust %'))
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=25,
                                    verbose_name=_('PDV stopa'))
    # Delivery tracking
    delivered_quantity = models.DecimalField(max_digits=12, decimal_places=4, default=0,
                                             verbose_name=_('Isporučeno'))
    # AI
    is_ai_suggested = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['sort_order']
        verbose_name = _('Stavka narudžbe')
        verbose_name_plural = _('Stavke narudžbe')

    def __str__(self):
        return f'{self.item.name} × {self.quantity}'

    @property
    def line_total(self):
        return (self.quantity * self.unit_price).quantize(Decimal('0.01'))

    @property
    def discount_amount(self):
        return (self.line_total * self.discount_percent / 100).quantize(Decimal('0.01'))

    @property
    def net_total(self):
        return self.line_total - self.discount_amount

    @property
    def tax_amount(self):
        return (self.net_total * self.tax_rate / 100).quantize(Decimal('0.01'))

    @property
    def gross_total(self):
        return self.net_total + self.tax_amount

    @property
    def is_fully_delivered(self):
        return self.delivered_quantity >= self.quantity


# ════════════════════════════════════════════════════════════════
# 3. SALDAKONTI — Otvorene stavke + IOS
# ════════════════════════════════════════════════════════════════

class OpenItem(models.Model):
    """
    Otvorena stavka — neplaćeni ili djelomično plaćeni račun/dokument.
    Generira se automatski iz Invoice/konto, zatvara se kad se uplata poveže.
    """
    DIRECTION_CHOICES = [
        ('receivable', _('Potraživanje (kupac nam duguje)')),
        ('payable', _('Obveza (mi dugujemo dobavljaču)')),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                                 related_name='open_items')
    partner = models.ForeignKey('partners.Partner', on_delete=models.CASCADE,
                                 related_name='open_items', verbose_name=_('Partner'))
    direction = models.CharField(max_length=12, choices=DIRECTION_CHOICES)
    document_type = models.CharField(max_length=30, verbose_name=_('Vrsta dokumenta'),
                                      help_text=_('racun, avansni, odobrenje...'))
    document_number = models.CharField(max_length=50, verbose_name=_('Broj dokumenta'))
    document_date = models.DateField(verbose_name=_('Datum dokumenta'))
    due_date = models.DateField(verbose_name=_('Datum dospijeća'))
    # Amounts
    original_amount = models.DecimalField(max_digits=12, decimal_places=2,
                                           verbose_name=_('Izvorni iznos'))
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                       verbose_name=_('Plaćeni iznos'))
    currency = models.CharField(max_length=3, default='EUR')
    # Linked objects
    invoice = models.ForeignKey('invoicing.Invoice', on_delete=models.SET_NULL,
                                 null=True, blank=True, related_name='open_items')
    journal_entry = models.ForeignKey('konto.JournalEntry', on_delete=models.SET_NULL,
                                       null=True, blank=True)
    # Status
    is_closed = models.BooleanField(default=False, verbose_name=_('Zatvoreno'))
    closed_at = models.DateTimeField(null=True, blank=True)
    # AI
    ai_payment_prediction_days = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name=_('AI predviđanje (dana)'),
        help_text=_('Predviđeni broj dana do plaćanja'),
    )
    ai_risk_score = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        verbose_name=_('AI rizik score'),
        help_text=_('0=siguran, 100=visok rizik neplaćanja'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['due_date']
        verbose_name = _('Otvorena stavka')
        verbose_name_plural = _('Otvorene stavke')
        indexes = [
            models.Index(fields=['company', 'partner', 'is_closed']),
            models.Index(fields=['company', 'due_date']),
        ]

    def __str__(self):
        return f'{self.document_number} — {self.partner.name} ({self.remaining} {self.currency})'

    @property
    def remaining(self):
        return self.original_amount - self.paid_amount

    @property
    def days_overdue(self):
        if self.is_closed:
            return 0
        delta = (timezone.now().date() - self.due_date).days
        return max(0, delta)

    @property
    def aging_bucket(self):
        d = self.days_overdue
        if d == 0:
            return 'current'
        elif d <= 30:
            return '1-30'
        elif d <= 60:
            return '31-60'
        elif d <= 90:
            return '61-90'
        return '90+'

    def close(self):
        self.is_closed = True
        self.closed_at = timezone.now()
        self.save(update_fields=['is_closed', 'closed_at'])


class IOSReport(models.Model):
    """
    IOS obrazac — Izvod Otvorenih Stavki za partnera.
    Zakon o računovodstvu čl. 22: obvezno usklađivanje.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                                 related_name='ios_reports')
    partner = models.ForeignKey('partners.Partner', on_delete=models.CASCADE,
                                 related_name='ios_reports')
    report_date = models.DateField(verbose_name=_('Datum izvoda'))
    total_receivable = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                            verbose_name=_('Ukupna potraživanja'))
    total_payable = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                         verbose_name=_('Ukupne obveze'))
    net_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                       verbose_name=_('Neto saldo'))
    items_count = models.PositiveIntegerField(default=0)
    # Status
    sent_at = models.DateTimeField(null=True, blank=True, verbose_name=_('Poslano'))
    confirmed_at = models.DateTimeField(null=True, blank=True, verbose_name=_('Potvrđeno'))
    confirmed_by = models.CharField(max_length=200, blank=True, verbose_name=_('Potvrdio'))
    pdf_url = models.URLField(blank=True)
    # Meta
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-report_date']
        verbose_name = _('IOS izvod')
        verbose_name_plural = _('IOS izvodi')

    def __str__(self):
        return f'IOS {self.partner.name} — {self.report_date} ({self.net_balance} EUR)'
