from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import get_user_model

User = get_user_model()


class CardActivity(models.Model):
    """
    Generički audit trail za sve kartice (WorkOrder, Lead, Intervencija...).
    Neizbrisiv — admin ne dozvoljava delete.
    """
    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE,
        related_name='card_activities'
    )
    object_id = models.CharField(max_length=50, db_index=True)
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+'
    )
    action = models.CharField(max_length=200)
    old_value = models.CharField(max_length=100, blank=True)
    new_value = models.CharField(max_length=100, blank=True)
    note = models.TextField(blank=True)
    is_public_facing = models.BooleanField(
        default=False,
        help_text='True = sigurno za prikaz klijentima (QR timeline, portal). False = samo interni.',
    )
    is_system_generated = models.BooleanField(
        default=False,
        help_text='True = generiran automatski (transition_to). False = human unos.',
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'card_activity'
        ordering = ['-created_at']
        indexes = [
            models.Index(
                fields=['content_type', 'object_id', '-created_at'],
                name='idx_cardact_ct_obj_date',
            ),
        ]
        verbose_name = 'Card Activity'
        verbose_name_plural = 'Card Activities'

    def __str__(self):
        return f'{self.action}: {self.old_value} \u2192 {self.new_value}'


class StatusTimestamp(models.Model):
    """SLA tracking — bilježi ulaz/izlaz iz svakog statusa."""
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.CharField(max_length=50, db_index=True)
    status = models.CharField(max_length=30)
    entered_at = models.DateTimeField(auto_now_add=True, db_index=True)
    exited_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    user = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+'
    )

    class Meta:
        db_table = 'sla_status_timestamp'
        ordering = ['-entered_at']
        indexes = [
            models.Index(
                fields=['content_type', 'object_id', 'status', 'exited_at'],
                name='idx_sla_ct_obj_status_exit',
            ),
        ]
        verbose_name = 'SLA Status Timestamp'
        verbose_name_plural = 'SLA Status Timestamps'

    def __str__(self):
        dur = f' ({self.duration_seconds}s)' if self.duration_seconds else ''
        return f'{self.status} @ {self.entered_at:%H:%M}{dur}'
