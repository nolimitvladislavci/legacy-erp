"""
fenix_input/models.py — Univerzalni ulazni kanal

Svaki podatak koji uđe u sustav — glasom, SMS-om, emailom,
Bluetoothom, ručnim unosom — postaje InputMessage.
AI ga parsira, korisnik potvrdi, podatak ide u ciljni modul.
"""
from django.conf import settings
from django.db import models


class InputMessage(models.Model):
    """Jedna ulazna poruka iz bilo kojeg kanala."""

    CHANNEL_CHOICES = [
        ('voice', 'Glas (mikrofon)'),
        ('sms', 'SMS (IoT / vaga / senzor)'),
        ('email', 'Email'),
        ('bluetooth', 'Bluetooth (čip čitač)'),
        ('manual', 'Ručni unos'),
        ('webhook', 'Webhook (API)'),
    ]

    STATUS_CHOICES = [
        ('raw', 'Primljeno — čeka AI'),
        ('parsed', 'AI parsirao — čeka potvrdu'),
        ('confirmed', 'Korisnik potvrdio'),
        ('applied', 'Primijenjeno u sustav'),
        ('rejected', 'Odbačeno'),
        ('error', 'Greška'),
    ]

    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='input_messages', null=True, blank=True,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='input_messages',
    )

    channel = models.CharField(max_length=15, choices=CHANNEL_CHOICES)
    raw_text = models.TextField(help_text='Sirovi tekst — transkripcija, SMS body, email body')
    sender = models.CharField(max_length=200, blank=True, help_text='Broj telefona, email, BT MAC...')

    # AI interpretacija
    ai_parsed = models.JSONField(
        default=dict, blank=True,
        help_text='AI output: {intent, target_module, fields, confidence}',
    )
    ai_confidence = models.FloatField(default=0, help_text='0.0 - 1.0')
    target_module = models.CharField(
        max_length=50, blank=True,
        help_text='Django app label: livestock, memio_pet, pos, inventory...',
    )
    target_action = models.CharField(
        max_length=50, blank=True,
        help_text='Akcija: create_record, update_status, log_weight...',
    )

    # Status i metapodaci
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='raw')
    applied_object_id = models.CharField(
        max_length=100, blank=True,
        help_text='PK kreiranog/ažuriranog objekta nakon primjene',
    )
    error_message = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True, help_text='Dodatni podaci po kanalu')

    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Ulazna poruka'
        verbose_name_plural = 'Ulazne poruke'

    def __str__(self):
        return f'[{self.channel}] {self.raw_text[:60]}...'


class SMSDevice(models.Model):
    """Registrirani SMS uređaj — vaga, senzor, GPS tracker."""

    DEVICE_TYPES = [
        ('bee_scale', 'Pčelarska vaga'),
        ('livestock_scale', 'Stočna vaga'),
        ('temperature', 'Temperaturni senzor'),
        ('gps_tracker', 'GPS tracker'),
        ('generic', 'Generički uređaj'),
    ]

    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='sms_devices',
    )
    phone_number = models.CharField(
        max_length=20, unique=True, db_index=True,
        help_text='Broj s kojeg uređaj šalje SMS (+385...)',
    )
    device_type = models.CharField(max_length=20, choices=DEVICE_TYPES, default='generic')
    name = models.CharField(max_length=100, help_text='Npr. "Vaga košnica 1-5"')
    parse_pattern = models.CharField(
        max_length=500, blank=True,
        help_text='Regex za parsiranje SMS-a. Grupe: weight, temp, hive_id...',
    )
    target_module = models.CharField(
        max_length=50, default='livestock',
        help_text='Modul u koji idu podaci',
    )
    is_active = models.BooleanField(default=True)
    last_message_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'SMS uređaj'
        verbose_name_plural = 'SMS uređaji'

    def __str__(self):
        return f'{self.name} ({self.phone_number})'
