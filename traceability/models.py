"""
traceability/models.py - Farm-to-Fork traceability

Svaki proizvod ima lanac događaja od berbe do stola.
Gost u restoranu skenira QR → vidi cijeli put proizvoda.
"""
import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.managers import CompanyManager


class ProductTrace(models.Model):
    """Kompletna traceability za jedan proizvod u jednoj narudžbi."""
    # Veze
    product = models.ForeignKey(
        'marketplace.MarketplaceProduct', on_delete=models.CASCADE,
        related_name='traces', verbose_name=_('Proizvod')
    )
    order_item = models.ForeignKey(
        'marketplace.MarketplaceOrderItem', on_delete=models.CASCADE,
        null=True, blank=True, related_name='traces',
        verbose_name=_('Stavka narudžbe')
    )

    # Proizvođač
    producer_company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        verbose_name=_('Proizvođač (OPG)')
    )
    producer_name = models.CharField(max_length=200, verbose_name=_('Naziv OPG-a'))
    producer_region = models.CharField(max_length=100, blank=True, verbose_name=_('Regija'))
    producer_story = models.TextField(blank=True, verbose_name=_('Priča o OPG-u'))
    producer_photo = models.ImageField(upload_to='traceability/producers/', blank=True, null=True)

    # Proizvodnja
    harvest_date = models.DateField(null=True, blank=True, verbose_name=_('Datum berbe'))
    production_date = models.DateField(null=True, blank=True, verbose_name=_('Datum proizvodnje'))
    lot_number = models.CharField(max_length=50, blank=True, verbose_name=_('Broj šarže'))
    is_organic = models.BooleanField(default=False, verbose_name=_('Ekološki'))
    certifications = models.JSONField(default=list, blank=True, verbose_name=_('Certifikati'))

    # Transport
    cold_chain_maintained = models.BooleanField(default=True, verbose_name=_('Hladni lanac održan'))
    temp_log = models.JSONField(default=list, blank=True, verbose_name=_('Temp log'))
    pickup_datetime = models.DateTimeField(null=True, blank=True)
    delivery_datetime = models.DateTimeField(null=True, blank=True)
    transport_duration_hours = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)

    # QR
    qr_code = models.UUIDField(default=uuid.uuid4, unique=True, verbose_name=_('QR kod'))
    trace_url = models.URLField(blank=True, verbose_name=_('Javni URL'))

    created_at = models.DateTimeField(auto_now_add=True)
    objects = CompanyManager()

    class Meta:
        verbose_name = _('Trag proizvoda')
        verbose_name_plural = _('Tragovi proizvoda')
        ordering = ['-created_at']

    def __str__(self):
        return f"Trace: {self.product.name} ← {self.producer_name}"

    def save(self, *args, **kwargs):
        if not self.trace_url:
            self.trace_url = f"https://limit-connect.com/trace/{self.qr_code}/"
        super().save(*args, **kwargs)


class TraceEvent(models.Model):
    """Pojedinačni događaj u lancu traceability-ja."""
    EVENT_TYPES = [
        ('harvested', _('Ubrano / Proizvedeno')),
        ('stored', _('Uskladišteno')),
        ('ordered', _('Naručeno')),
        ('picked_up', _('Preuzeto od OPG-a')),
        ('in_transit', _('U transportu')),
        ('temp_check', _('Provjera temperature')),
        ('delivered', _('Dostavljeno restoranu')),
        ('received', _('Zaprimljeno')),
        ('prepared', _('Pripremljeno u kuhinji')),
        ('served', _('Servirano gostu')),
    ]

    trace = models.ForeignKey(
        ProductTrace, on_delete=models.CASCADE,
        related_name='events', verbose_name=_('Trag')
    )
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    timestamp = models.DateTimeField()

    location_name = models.CharField(max_length=200, blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    temperature = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)

    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name=_('Izvršio')
    )
    notes = models.TextField(blank=True)
    photo = models.ImageField(upload_to='traceability/events/', blank=True, null=True)

    class Meta:
        verbose_name = _('Događaj traga')
        verbose_name_plural = _('Događaji traga')
        ordering = ['trace', 'timestamp']

    def __str__(self):
        return f"{self.get_event_type_display()} @ {self.timestamp:%d.%m. %H:%M}"
