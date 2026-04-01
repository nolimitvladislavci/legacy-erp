from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
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


# ── BORG Audit Entry (TIER 1A — Proactive Engine) ─────────────────────────

class BorgAuditEntry(models.Model):
    """
    Immutable compliance audit trail linking documents to legal sources.
    Pravni stit pred Poreznom — strukturirani zapis s referencom na NN.
    Nikad se ne brise, nikad se ne mijenja.
    """

    ENTRY_TYPES = [
        ('REGULATORY', 'Regulatorna promjena'),
        ('FISCAL', 'Fiskalizacija'),
        ('INVOICE', 'Fakturiranje'),
        ('ERACUN', 'e-Racun'),
        ('VIES_CHECK', 'VIES verifikacija'),
        ('OIB_CHECK', 'OIB provjera'),
        ('AML_ALERT', 'AML upozorenje'),
        ('GDPR_ACTION', 'GDPR radnja'),
        ('TRUST_CHECKPOINT', 'Kontrolna tocka povjerenja'),
        ('EXPORT', 'Izvoz podataka'),
        ('BRIEFING', 'Jutarnji briefing'),
    ]

    SEVERITY_CHOICES = [
        ('INFO', 'Informacija'),
        ('WARNING', 'Upozorenje'),
        ('ACTION_REQUIRED', 'Potrebna akcija'),
        ('CRITICAL', 'Kriticno'),
    ]

    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='borg_audit_entries',
    )
    entry_type = models.CharField(max_length=20, choices=ENTRY_TYPES, db_index=True)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='INFO')

    # Document link (generic FK — invoice, receipt, eracun, partner...)
    content_type = models.ForeignKey(
        ContentType, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='borg_audit_entries',
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    document = GenericForeignKey('content_type', 'object_id')

    # Legal source (NN reference)
    regulatory_update = models.ForeignKey(
        'limit_connect_ai.RegulatoryUpdate', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='borg_audit_entries',
    )
    legal_reference = models.CharField(
        max_length=200, blank=True,
        help_text='Npr. "NN 35/2026, cl.15"',
    )

    # Verification
    verification_type = models.CharField(
        max_length=50, blank=True,
        help_text='VIES, OIB, CIS, FINA',
    )
    verification_result = models.JSONField(default=dict, blank=True)

    # Context
    summary = models.TextField(verbose_name='Opis')
    metadata = models.JSONField(default=dict, blank=True)

    # Immutability
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
    )

    class Meta:
        db_table = 'borg_audit_entry'
        ordering = ['-created_at']
        indexes = [
            models.Index(
                fields=['company', 'entry_type', '-created_at'],
                name='idx_borgaudit_co_type_date',
            ),
            models.Index(
                fields=['company', 'severity', '-created_at'],
                name='idx_borgaudit_co_sev_date',
            ),
        ]
        verbose_name = 'BORG Audit Entry'
        verbose_name_plural = 'BORG Audit Entries'

    def __str__(self):
        return f'[{self.severity}] {self.get_entry_type_display()} — {self.summary[:80]}'

    def delete(self, *args, **kwargs):
        raise PermissionError("BorgAuditEntry je immutable — brisanje zabranjeno.")

    def save(self, *args, **kwargs):
        if self.pk:
            raise PermissionError("BorgAuditEntry je immutable — izmjena zabranjena.")
        super().save(*args, **kwargs)


class BorgBriefingConfig(models.Model):
    """Per-company configuration for morning WhatsApp briefing."""

    company = models.OneToOneField(
        'companies.Company', on_delete=models.CASCADE,
        related_name='borg_briefing_config',
    )
    enabled = models.BooleanField(default=False, verbose_name='Aktivirano')
    phone_number = models.CharField(max_length=20, verbose_name='WhatsApp broj')
    max_items = models.PositiveSmallIntegerField(default=5, verbose_name='Max stavki')
    include_financial = models.BooleanField(default=True, verbose_name='Ukljuci financije')
    include_compliance = models.BooleanField(default=True, verbose_name='Ukljuci compliance')
    include_operational = models.BooleanField(default=True, verbose_name='Ukljuci operativu')
    send_time = models.TimeField(default='08:00', verbose_name='Vrijeme slanja')
    last_sent = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'borg_briefing_config'
        verbose_name = 'BORG Briefing Config'
        verbose_name_plural = 'BORG Briefing Configs'

    def __str__(self):
        status = 'ON' if self.enabled else 'OFF'
        return f'{self.company.name} — Briefing {status} @ {self.send_time}'



# ── BORG Trust Decay + Graduated Autonomy (TIER 3) ────────────────────────

class BorgAutonomyTracker(models.Model):
    """
    Per-company tracking za Trust Decay mechanism.
    Sprjecava algoritamsku ljenost — meaningful human control.
    """
    AUTONOMY_LEVELS = [
        ('suggest_only', 'Samo prijedlozi'),
        ('semi_auto', 'Polu-automatski'),
        ('trusted', 'Provjereni'),
    ]

    company = models.OneToOneField(
        'companies.Company', on_delete=models.CASCADE,
        related_name='borg_autonomy',
    )
    autonomy_level = models.CharField(
        max_length=20, choices=AUTONOMY_LEVELS, default='suggest_only',
    )
    auto_approved_streak = models.PositiveIntegerField(default=0)
    last_rejection_date = models.DateField(null=True, blank=True)
    last_checkpoint_date = models.DateField(null=True, blank=True)
    category_approvals = models.JSONField(
        default=dict, blank=True,
        help_text='Counter per kategorija: {"invoice_reminder": 45, "stock_alert": 12}',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'borg_autonomy_tracker'
        verbose_name = 'BORG Autonomy Tracker'
        verbose_name_plural = 'BORG Autonomy Trackers'

    def __str__(self):
        return f'{self.company.name} — {self.get_autonomy_level_display()} (streak: {self.auto_approved_streak})'



# ── BORG Insight (TIER 2B — Prediktivni Compliance) ───────────────────────

class BorgInsight(models.Model):
    """
    Rezultat prediktivne analize — simulacija utjecaja regulatornih promjena.
    Virtualni CFO: 'Ova promjena ce vam povecati troskove za 4.2% u Q3.'
    """
    INSIGHT_TYPES = [
        ('vat_impact', 'Utjecaj PDV promjene'),
        ('regulation_impact', 'Utjecaj regulacije'),
        ('cost_trend', 'Trend troskova'),
        ('revenue_risk', 'Rizik prihoda'),
        ('compliance_gap', 'Compliance praznina'),
    ]

    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='borg_insights',
    )
    insight_type = models.CharField(max_length=30, choices=INSIGHT_TYPES)
    title = models.CharField(max_length=200)
    summary = models.TextField()
    data = models.JSONField(default=dict, blank=True,
        help_text='Strukturirani rezultati simulacije')
    regulatory_update = models.ForeignKey(
        'limit_connect_ai.RegulatoryUpdate', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='borg_insights',
    )
    confidence_score = models.FloatField(default=0.5,
        help_text='0.0=nisko, 1.0=visoko')
    is_acknowledged = models.BooleanField(default=False)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'borg_insight'
        ordering = ['-created_at']
        verbose_name = 'BORG Insight'
        verbose_name_plural = 'BORG Insights'

    def __str__(self):
        return f'[{self.get_insight_type_display()}] {self.title[:60]} (conf: {self.confidence_score:.0%})'



# ── BORG Collaborative Intelligence (TIER 4) ──────────────────────────────

class BorgSignal(models.Model):
    """
    Apstraktni, anonimizirani signal — NIKAD sirovi tenant podaci.
    BorgSignal NEMA company FK. Tenant izolacija ocuvana.
    Signal se ne moze traceback-ati do izvora.
    """
    CATEGORIES = [
        ('FOOD_SUPPLY', 'Prehrambene namirnice'),
        ('ENERGY', 'Energija'),
        ('LOGISTICS', 'Logistika'),
        ('REGULATION', 'Regulativa'),
        ('LABOR', 'Radna snaga'),
        ('MATERIAL', 'Sirovine'),
        ('SERVICE', 'Usluge'),
    ]
    DIRECTIONS = [
        ('UP', 'Rast'),
        ('DOWN', 'Pad'),
        ('STABLE', 'Stabilno'),
        ('VOLATILE', 'Volatilno'),
    ]

    category = models.CharField(max_length=30, choices=CATEGORIES, db_index=True)
    direction = models.CharField(max_length=10, choices=DIRECTIONS)
    magnitude_pct = models.FloatField(help_text='Raspon promjene u postocima (npr. 5.0 za 5%)')
    region = models.CharField(max_length=10, db_index=True,
        help_text='NUTS-3 kod: HR-01 do HR-21')
    period = models.CharField(max_length=10,
        help_text='Period: 2026-Q2')

    # Aggregation — NO company FK (anonymous by design)
    signal_count = models.PositiveIntegerField(default=1)
    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'borg_signal'
        unique_together = ['category', 'direction', 'region', 'period']
        verbose_name = 'BORG Signal'
        verbose_name_plural = 'BORG Signals'

    def __str__(self):
        return f'{self.get_category_display()} {self.direction} {self.magnitude_pct}% ({self.region}, {self.period}) x{self.signal_count}'


class BorgCollabConfig(models.Model):
    """Opt-in per company. Default OFF. GDPR cl.6(1)(a)."""
    company = models.OneToOneField(
        'companies.Company', on_delete=models.CASCADE,
        related_name='borg_collab_config',
    )
    enabled = models.BooleanField(default=False)
    opted_in_at = models.DateTimeField(null=True, blank=True)
    consent_text_version = models.CharField(max_length=20, default='v1.0')

    class Meta:
        db_table = 'borg_collab_config'
        verbose_name = 'BORG Collab Config'

    def __str__(self):
        return f'{self.company.name} — Collab {"ON" if self.enabled else "OFF"}'


class BorgInsightAlert(models.Model):
    """Generiran kad BorgSignal.signal_count prelazi prag."""
    signal = models.ForeignKey(BorgSignal, on_delete=models.CASCADE, related_name='alerts')
    threshold_reached = models.PositiveIntegerField()
    insight_text = models.TextField()
    companies_notified = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'borg_insight_alert'
        ordering = ['-created_at']
        verbose_name = 'BORG Insight Alert'

    def __str__(self):
        return f'Alert: {self.signal} (threshold={self.threshold_reached}, notified={self.companies_notified})'
