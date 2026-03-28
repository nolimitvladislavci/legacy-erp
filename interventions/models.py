import uuid
from datetime import timedelta

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.managers import CompanyManager
from borg_ops.mixins import FSMMixin
from django.contrib.contenttypes.fields import GenericRelation


class HitnaIntervencija(FSMMixin, models.Model):
    card_activities = GenericRelation('borg_ops.CardActivity', object_id_field='object_id', content_type_field='content_type')
    sla_timestamps  = GenericRelation('borg_ops.StatusTimestamp', object_id_field='object_id', content_type_field='content_type')

    STATUS_FIELD = 'status'
    TRANSITIONS = {
        'NOVO':        ['DODIJELJENO'],
        'DODIJELJENO': ['NA_PUTU', 'NOVO'],
        'NA_PUTU':     ['NA_LOKACIJI'],
        'NA_LOKACIJI': ['RIJESENO', 'ESKALIRANO'],
        'RIJESENO':    ['FAKTURIRANO'],
        'ESKALIRANO':  ['RIJESENO'],
        'FAKTURIRANO': [],  # terminal
    }

    class Status(models.TextChoices):
        NOVO        = 'NOVO',        'Novi poziv'
        DODIJELJENO = 'DODIJELJENO', 'Dodijeljeno ekipi'
        NA_PUTU     = 'NA_PUTU',     'Ekipa na putu'
        NA_LOKACIJI = 'NA_LOKACIJI', 'Ekipa na lokaciji'
        RIJESENO    = 'RIJESENO',    'Rijeseno'
        ESKALIRANO  = 'ESKALIRANO',  'Eskalirano u projekt'
        FAKTURIRANO = 'FAKTURIRANO', 'Fakturirano'

    class Category(models.TextChoices):
        VODA    = 'voda',    'Vodoinstalacije'
        STRUJA  = 'struja',  'Elektrika'
        PLIN    = 'plin',    'Plin'
        KLJUCAR = 'kljucar', 'Kljucar'
        OSTALO  = 'ostalo',  'Ostalo'

    STATUS_COLORS = {
        'NOVO':        '#3b82f6',
        'DODIJELJENO': '#c9a84c',
        'NA_PUTU':     '#f97316',
        'NA_LOKACIJI': '#8b5cf6',
        'RIJESENO':    '#4caf7d',
        'ESKALIRANO':  '#ec4899',
        'FAKTURIRANO': '#6b7280',
    }

    # Tenant
    company        = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                                       related_name='interventions', verbose_name=_('Tvrtka'))
    objects        = CompanyManager()

    # Core
    title          = models.CharField(max_length=200, verbose_name=_('Naslov'))
    category       = models.CharField(max_length=20, choices=Category.choices,
                                       default=Category.OSTALO, verbose_name=_('Kategorija'))
    address        = models.CharField(max_length=300, verbose_name=_('Adresa intervencije'))
    description    = models.TextField(blank=True, verbose_name=_('Opis'))

    # Klijent
    client_name    = models.CharField(max_length=100, verbose_name=_('Ime klijenta'))
    client_phone   = models.CharField(max_length=30, verbose_name=_('Telefon klijenta'))
    client_whatsapp = models.CharField(max_length=50, blank=True, verbose_name=_('WhatsApp klijenta'))
    whatsapp_notification_sent = models.BooleanField(default=False)

    # Dodjela i TTL
    assigned_to    = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                                        related_name='assigned_interventions',
                                        verbose_name=_('Dodijeljen'))
    assigned_at    = models.DateTimeField(null=True, blank=True)
    ttl_expires_at = models.DateTimeField(null=True, blank=True, verbose_name=_('TTL istjece'))

    # Tracking
    tracking_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    status         = models.CharField(max_length=20, choices=Status.choices,
                                       default=Status.NOVO, db_index=True,
                                       verbose_name=_('Status'))

    # Vremena
    created_at     = models.DateTimeField(auto_now_add=True)
    started_at     = models.DateTimeField(null=True, blank=True)
    arrived_at     = models.DateTimeField(null=True, blank=True)
    resolved_at    = models.DateTimeField(null=True, blank=True)

    # GPS praćenje
    last_lat        = models.FloatField(null=True, blank=True,
                                         verbose_name='Zadnja GPS širina')
    last_lng        = models.FloatField(null=True, blank=True,
                                         verbose_name='Zadnja GPS dužina')
    last_gps_update = models.DateTimeField(null=True, blank=True,
                                            verbose_name='Zadnje GPS ažuriranje')

    # Integracije
    pos_receipt    = models.ForeignKey('pos.POSReceipt', null=True, blank=True,
                                        on_delete=models.SET_NULL,
                                        related_name='interventions')
    project_lead   = models.ForeignKey('burza.ProjectLead', null=True, blank=True,
                                        on_delete=models.SET_NULL,
                                        related_name='interventions')

    class Meta:
        ordering            = ['-created_at']
        verbose_name        = 'Hitna intervencija'
        verbose_name_plural = 'Hitne intervencije'

    def __str__(self):
        return f'{self.title} – {self.get_status_display()}'

    @property
    def status_color(self):
        return self.STATUS_COLORS.get(self.status, '#888')

    @property
    def tracking_url(self):
        return f'/track/{self.tracking_token}/'

    @property
    def elapsed_minutes(self):
        delta = timezone.now() - self.created_at
        return int(delta.total_seconds() // 60)

    def assign_worker(self, user, ttl_minutes=3):
        self.assigned_to = user
        self.assigned_at = timezone.now()
        self.ttl_expires_at = timezone.now() + timedelta(minutes=ttl_minutes)
        self._fsm_transition_active = True
        self.status = self.Status.DODIJELJENO
        super().save()
        self._fsm_transition_active = False
