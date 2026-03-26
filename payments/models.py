from core.fields import FernetEncryptedCharField
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
import uuid
from core.managers import CompanyManager


class PaymentConfig(models.Model):
    """Company-level payment gateway configuration."""
    company = models.OneToOneField(
        'companies.Company', on_delete=models.CASCADE,
        related_name='payment_config', verbose_name=_('Tvrtka'),
    )
    # Stripe
    stripe_enabled = models.BooleanField(default=False, verbose_name=_('Stripe aktivan'))
    stripe_public_key = FernetEncryptedCharField(blank=True, verbose_name=_('Stripe Publishable Key'))
    stripe_secret_key = FernetEncryptedCharField(blank=True, verbose_name=_('Stripe Secret Key'))
    stripe_webhook_secret = FernetEncryptedCharField(blank=True, verbose_name=_('Stripe Webhook Secret'))

    # BTCPay
    btcpay_enabled = models.BooleanField(default=False, verbose_name=_('BTCPay aktivan'))
    btcpay_url = models.URLField(blank=True, verbose_name=_('BTCPay Server URL'))
    btcpay_store_id = models.CharField(max_length=100, blank=True, verbose_name=_('BTCPay Store ID'))
    btcpay_api_key = FernetEncryptedCharField(blank=True, verbose_name=_('BTCPay API Key'))

    # PayPal
    paypal_enabled = models.BooleanField(default=False, verbose_name=_('PayPal aktivan'))
    paypal_client_id = FernetEncryptedCharField(blank=True, verbose_name=_('PayPal Client ID'))
    paypal_secret = FernetEncryptedCharField(blank=True, verbose_name=_('PayPal Secret'))
    paypal_mode = models.CharField(max_length=10, default='live', choices=[('sandbox','Sandbox'),('live','Live')], verbose_name=_('PayPal Mode'))

    # Revolut
    revolut_enabled = models.BooleanField(default=False, verbose_name=_('Revolut aktivan'))
    revolut_api_key = FernetEncryptedCharField(blank=True, verbose_name=_('Revolut API Key'))
    revolut_merchant_id = FernetEncryptedCharField(blank=True, verbose_name=_('Revolut Merchant ID'))
    revolut_webhook_secret = FernetEncryptedCharField(blank=True, verbose_name=_('Revolut Webhook Secret'))
    revolut_mode = models.CharField(max_length=10, default='sandbox', choices=[('sandbox','Sandbox'),('production','Production')], verbose_name=_('Revolut Mode'))

    # General
    default_currency = models.CharField(max_length=3, default='EUR', verbose_name=_('Valuta'))
    auto_capture = models.BooleanField(default=True, verbose_name=_('Automatski naplati'))

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Konfiguracija placanja')
        verbose_name_plural = _('Konfiguracije placanja')

    def __str__(self):
        methods = []
        if self.stripe_enabled:
            methods.append('Stripe')
        if self.btcpay_enabled:
            methods.append('BTCPay')
        if self.paypal_enabled:
            methods.append('PayPal')
        if self.revolut_enabled:
            methods.append('Revolut')
        return f'{self.company.name} - {", ".join(methods) or "Samo gotovina"}'


class Payment(models.Model):
    """Universal payment record - used by any module."""
    METHOD_CHOICES = [
        ('cash', _('Gotovina')),
        ('stripe', _('Kartica (Stripe)')),
        ('btcpay', _('Kriptovaluta (BTCPay)')),
        ('paypal', _('PayPal')),
        ('revolut', _('Revolut (Kartica/Tap to Pay)')),
    ]
    STATUS_CHOICES = [
        ('pending', _('Na cekanju')),
        ('processing', _('U obradi')),
        ('completed', _('Zavrseno')),
        ('failed', _('Neuspjesno')),
        ('refunded', _('Povrat')),
        ('cancelled', _('Otkazano')),
    ]
    SOURCE_CHOICES = [
        ('gastro_qr', _('Gastro QR Narudzba')),
        ('pos', _('POS Blagajna')),
        ('webshop', _('Webshop')),
        ('invoice', _('Faktura')),
        ('rental', _('Najam / Hostel')),
        ('booking', _('Rezervacija')),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='payments', verbose_name=_('Tvrtka'),
    )

    # What is being paid for
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, verbose_name=_('Izvor'))
    source_id = models.CharField(max_length=100, blank=True, verbose_name=_('ID izvora'),
                                  help_text=_('PK narudzbe, fakture, itd.'))

    # Payment details
    method = models.CharField(max_length=10, choices=METHOD_CHOICES, verbose_name=_('Nacin placanja'))
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending', verbose_name=_('Status'))
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_('Iznos'))
    currency = models.CharField(max_length=3, default='EUR')
    description = models.CharField(max_length=300, blank=True, verbose_name=_('Opis'))

    # External gateway references
    external_id = models.CharField(max_length=300, blank=True, verbose_name=_('Vanjski ID'),
                                    help_text=_('Stripe PaymentIntent ID ili BTCPay Invoice ID'))
    external_url = models.URLField(blank=True, verbose_name=_('Vanjski URL'),
                                    help_text=_('Stripe checkout URL ili BTCPay invoice URL'))
    gateway_data = models.JSONField(default=dict, blank=True, verbose_name=_('Gateway podaci'))

    # Customer info
    customer_email = models.EmailField(blank=True, verbose_name=_('Email kupca'))
    customer_name = models.CharField(max_length=100, blank=True, verbose_name=_('Ime kupca'))

    # Crypto-specific
    crypto_currency = models.CharField(max_length=10, blank=True, verbose_name=_('Kripto valuta'),
                                        help_text=_('BTC, ETH, LTC, itd.'))
    crypto_amount = models.CharField(max_length=30, blank=True, verbose_name=_('Kripto iznos'))
    crypto_address = models.CharField(max_length=200, blank=True, verbose_name=_('Crypto adresa'))

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    objects = CompanyManager()

    class Meta:
        verbose_name = _('Placanje')
        verbose_name_plural = _('Placanja')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'status']),
            models.Index(fields=['source', 'source_id']),
            models.Index(fields=['external_id']),
        ]

    def __str__(self):
        return f'{self.get_method_display()} {self.amount} {self.currency} - {self.get_status_display()}'

    @property
    def is_completed(self):
        return self.status == 'completed'

    @property
    def is_pending(self):
        return self.status in ('pending', 'processing')
