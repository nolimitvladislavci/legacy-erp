import uuid

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class TrackingStatus(models.Model):
    TRACKING_TYPES = [
        ('food_order', 'Narudzba hrane'),
        ('delivery', 'Dostava'),
        ('intervention', 'Hitna intervencija'),
        ('work_order', 'Radni nalog'),
        ('expiry', 'Istek roka'),
        ('shipment', 'Otpremnica / Isporuka'),
    ]
    tracking_type = models.CharField(max_length=50, choices=TRACKING_TYPES)
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100)
    order = models.PositiveIntegerField(default=0)
    icon = models.CharField(max_length=50, blank=True)
    color = models.CharField(max_length=20, default='#c9a84c')

    class Meta:
        ordering = ['tracking_type', 'order']
        unique_together = ['tracking_type', 'slug']
        verbose_name = 'Status pracenja'
        verbose_name_plural = 'Statusi pracenja'

    def __str__(self):
        return f'{self.get_tracking_type_display()} / {self.name}'


class TrackedItem(models.Model):
    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE,
    )
    object_id = models.CharField(max_length=64)
    content_object = GenericForeignKey('content_type', 'object_id')

    tracking_type = models.CharField(max_length=50, choices=TrackingStatus.TRACKING_TYPES)
    current_status = models.ForeignKey(
        TrackingStatus, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='tracked_items',
    )
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    public_token = models.CharField(max_length=32, unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Praceni objekt'
        verbose_name_plural = 'Praceni objekti'

    def __str__(self):
        return f'{self.get_tracking_type_display()} #{self.pk}'

    # Logistics fields (used for shipment tracking type)
    driver_name   = models.CharField('Vozač', max_length=100, blank=True)
    vehicle_plate = models.CharField('Registracija', max_length=20, blank=True)
    tracking_url  = models.URLField('Vanjski tracking link', blank=True)
    DELIVERY_METHOD_CHOICES = [
        ('internal', 'Vlastito vozilo'),
        ('bus', 'Autobusna linija'),
        ('taxi', 'Taxi / brza dostava'),
        ('crowd', 'Crowd-shipping'),
        ('courier', 'Kurirska sluzba'),
        ('pickup', 'Osobno preuzimanje'),
    ]
    delivery_method = models.CharField(
        'Nacin dostave', max_length=20,
        choices=DELIVERY_METHOD_CHOICES, blank=True,
    )

    dispatched_at = models.DateTimeField('Polazak', null=True, blank=True)
    delivered_at  = models.DateTimeField('Isporuka', null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.public_token:
            self.public_token = uuid.uuid4().hex[:32]
        super().save(*args, **kwargs)

    def update_status(self, new_status, user=None, note=''):
        self.current_status = new_status
        self.save(update_fields=['current_status', 'updated_at'])
        return TrackingEvent.objects.create(
            tracked_item=self,
            status=new_status,
            user=user,
            note=note,
        )


class TrackingEvent(models.Model):
    tracked_item = models.ForeignKey(
        TrackedItem, on_delete=models.CASCADE, related_name='events',
    )
    status = models.ForeignKey(TrackingStatus, on_delete=models.CASCADE)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
    )
    note = models.TextField(blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Dogadaj pracenja'
        verbose_name_plural = 'Dogadaji pracenja'

    def __str__(self):
        return f'{self.tracked_item} -> {self.status.name}'
