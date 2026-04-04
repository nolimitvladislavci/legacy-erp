"""
memio_world/models.py — Memio World digitalna baština
Baza: memio_world (potpuno odvojena od fina_erp i memio_pets)

Proizvod: memio.world — sjećanja, obitelji, TimeCapsule, MemoryVault
GDPR kontekst: osobni podaci obitelji, ne ljubimci — zasebna izolacija.
"""

import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _


class WaitlistEntry(models.Model):
    """
    memio.world waitlist — migrirana iz memio_pets.WaitlistEntry
    (samo zapisi koji su source='memio.world').
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    email = models.EmailField(unique=True)
    source = models.CharField(max_length=50, default='memio.world')
    interest = models.CharField(
        max_length=30, blank=True, default='',
        choices=[
            ('timecapsule', 'TimeCapsule'),
            ('familystory', 'Obiteljska priča'),
            ('memoryvault', 'Memory Vault'),
            ('general', 'Općenito'),
        ],
        help_text='Koji dio Memio Worlda zanima korisnika',
    )
    ip = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    notified = models.BooleanField(default=False, help_text='Je li poslan launch email')

    class Meta:
        app_label = 'memio_world'
        verbose_name = _('Waitlist prijava')
        verbose_name_plural = _('Waitlist prijave')
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.email} ({self.source})'


class TimeCapsule(models.Model):
    """
    Digitalna vremenska kapsula — poruka, mediji, datum otvaranja.
    Korisnik kreira kapsulu koja se "otvara" na zadani datum.
    """
    STATUS_CHOICES = [
        ('draft', 'Nacrt'),
        ('sealed', 'Zapečaćena'),
        ('opened', 'Otvorena'),
        ('expired', 'Istekla'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner_email = models.EmailField(help_text='Kreator kapsule')
    title = models.CharField(max_length=200)
    message = models.TextField(blank=True, help_text='Tekstualna poruka')
    media_urls = models.JSONField(default=list, blank=True,
                                   help_text='Lista URL-ova na medije (slike, video, audio)')
    recipients = models.JSONField(default=list, blank=True,
                                   help_text='Email adrese primatelja')
    open_date = models.DateField(help_text='Datum kad se kapsula otvara')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')
    created_at = models.DateTimeField(auto_now_add=True)
    opened_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'memio_world'
        verbose_name = _('Vremenska kapsula')
        verbose_name_plural = _('Vremenske kapsule')
        ordering = ['open_date']

    def __str__(self):
        return f'{self.title} → {self.open_date}'


class MemoryVault(models.Model):
    """
    Sigurni trezor sjećanja — enkriptirani dokumenti, fotografije,
    obiteljski recepti, važni datumi.
    """
    CATEGORY_CHOICES = [
        ('photo', 'Fotografije'),
        ('document', 'Dokumenti'),
        ('recipe', 'Recepti'),
        ('story', 'Priče'),
        ('video', 'Video'),
        ('audio', 'Audio'),
        ('other', 'Ostalo'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner_email = models.EmailField()
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')
    media_url = models.URLField(blank=True, help_text='URL na pohranjeni medij')
    file_size_bytes = models.BigIntegerField(default=0)
    is_encrypted = models.BooleanField(default=True)
    shared_with = models.JSONField(default=list, blank=True,
                                    help_text='Email adrese s kojima je podijeljeno')
    tags = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'memio_world'
        verbose_name = _('Memory Vault')
        verbose_name_plural = _('Memory Vault stavke')
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} ({self.category})'


class FamilyStory(models.Model):
    """
    Obiteljske priče — tekst + mediji, generacijski lanac.
    Mogu se povezivati (roditelj → dijete priča).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    author_email = models.EmailField()
    title = models.CharField(max_length=200)
    content = models.TextField(help_text='Markdown format')
    media_urls = models.JSONField(default=list, blank=True)
    parent_story = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='child_stories',
        help_text='Roditelj priča (za generacijski lanac)',
    )
    location = models.CharField(max_length=200, blank=True, help_text='Gdje se priča dogodila')
    year_from = models.IntegerField(null=True, blank=True)
    year_to = models.IntegerField(null=True, blank=True)
    is_public = models.BooleanField(default=False, help_text='Vidljivo svima ili samo obitelji')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'memio_world'
        verbose_name = _('Obiteljska priča')
        verbose_name_plural = _('Obiteljske priče')
        ordering = ['-created_at']

    def __str__(self):
        return self.title
