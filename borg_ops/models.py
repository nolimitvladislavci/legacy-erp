from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import get_user_model

User = get_user_model()


class CardActivity(models.Model):
    """
    Genericki audit trail za sve kartice (WorkOrder, Lead, Intervencija...).
    Neizbrisiv - admin ne dozvoljava delete.
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
        default=False, db_index=True,
        verbose_name='Javno vidljivo',
        help_text='Ako True, ovaj zapis se prikazuje na javnom QR traceability linka.',
    )
    is_system_generated = models.BooleanField(
        default=True, db_index=True,
        verbose_name='Generirano od sustava',
        help_text='Ako False, zapis je rucno unio korisnik i ne smije biti javno vidljiv.',
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
    """SLA tracking - biljezi ulaz/izlaz iz svakog statusa."""
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


# ── BORG TaskBoard (F4 — 10/10) ────────────────────────────────────────────

class BorgTask(models.Model):
    """
    BORG Ops TaskBoard - actionable tasks auto-created from:
    - Overdue invoices -> followup
    - Open work orders -> work_order
    - Anomaly alerts -> anomaly
    - Patrol findings -> patrol
    - Signal triage -> signal
    - Regulatory adaptation -> adaptation
    - Opportunity match -> opportunity
    """
    TASK_TYPES = [
        ('followup', 'Naplata / Follow-up'),
        ('work_order', 'Radni nalog'),
        ('anomaly', 'Anomalija'),
        ('patrol', 'Patrol nalaz'),
        ('signal', 'Korisni signal'),
        ('adaptation', 'Regulatorna prilagodba'),
        ('opportunity', 'Prilika za ustedu'),
        ('manual', 'Rucno kreirano'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Ceka'),
        ('in_progress', 'U tijeku'),
        ('blocked', 'Blokirano'),
        ('completed', 'Zavrseno'),
        ('cancelled', 'Otkazano'),
    ]
    PRIORITY_CHOICES = [(1, 'Kriticno'), (2, 'Visoko'), (3, 'Normalno'), (4, 'Nisko')]

    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='borg_tasks', null=True, blank=True,
    )
    task_type = models.CharField(max_length=20, choices=TASK_TYPES, db_index=True)
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    priority = models.SmallIntegerField(choices=PRIORITY_CHOICES, default=3, db_index=True)
    assigned_to = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='borg_assigned_tasks',
    )
    created_by = models.CharField(max_length=50, default='borg')
    reference_type = models.CharField(max_length=50, blank=True)
    reference_id = models.CharField(max_length=100, blank=True, db_index=True)
    due_date = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    resolution_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'borg_task'
        ordering = ['priority', '-created_at']
        verbose_name = 'BORG Task'
        verbose_name_plural = 'BORG Tasks'

    def __str__(self):
        return f'[P{self.priority}] {self.title[:60]} ({self.get_status_display()})'

    def complete(self, note=''):
        from django.utils import timezone
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.resolution_note = note
        self.save(update_fields=['status', 'completed_at', 'resolution_note', 'updated_at'])
