import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone
from core.managers import CompanyManager


class AIAgentMission(models.Model):
    """What the AI agent does for a specific company."""

    MISSION_TYPES = [
        ('daily_report', 'Dnevni izvještaj'),
        ('fund_watch', 'Praćenje EU fondova'),
        ('compliance_watch', 'Praćenje zakonske usklađenosti'),
        ('campaign_planner', 'Planiranje kampanja'),
        ('stock_alert', 'Upozorenje na zalihe'),
        ('custom', 'Prilagođeno'),
    ]
    FREQUENCY_CHOICES = [
        ('hourly', 'Svaki sat'),
        ('daily', 'Dnevno'),
        ('weekly', 'Tjedno'),
        ('monthly', 'Mjesečno'),
        ('on_trigger', 'Na okidač'),
    ]
    NOTIFY_CHANNEL_CHOICES = [
        ('whatsapp', 'WhatsApp'),
        ('email', 'Email'),
        ('both', 'WhatsApp + Email'),
        ('chat', 'Chat'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='ai_missions', verbose_name='Tvrtka',
    )
    mission_type = models.CharField(max_length=30, choices=MISSION_TYPES, default='daily_report')
    title = models.CharField(max_length=200, verbose_name='Naziv misije')
    description = models.TextField(blank=True, verbose_name='Opis')
    is_active = models.BooleanField(default=True, verbose_name='Aktivna')
    frequency = models.CharField(max_length=15, choices=FREQUENCY_CHOICES, default='daily')
    next_run = models.DateTimeField(null=True, blank=True, verbose_name='Sljedeće pokretanje')
    last_run = models.DateTimeField(null=True, blank=True, verbose_name='Zadnje pokretanje')
    config = models.JSONField(default=dict, blank=True, verbose_name='Konfiguracija')
    notify_channel = models.CharField(max_length=10, choices=NOTIFY_CHANNEL_CHOICES, default='whatsapp')
    notify_target = models.CharField(
        max_length=200, blank=True,
        verbose_name='Primatelj (telefon/email)',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ai_missions_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = CompanyManager()

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'AI misija'
        verbose_name_plural = 'AI misije'

    def __str__(self):
        return f"{self.company.name} — {self.get_mission_type_display()}"


class AIReportLog(models.Model):
    """History of AI-generated reports sent to clients."""

    STATUS_CHOICES = [
        ('pending', 'Na čekanju'),
        ('sent', 'Poslano'),
        ('failed', 'Neuspjelo'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='ai_report_logs',
    )
    mission = models.ForeignKey(
        AIAgentMission, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='report_logs',
    )
    report_type = models.CharField(max_length=50, default='daily_report')
    content = models.TextField(verbose_name='Tekst izvještaja')
    sent_via = models.CharField(max_length=10, default='whatsapp')
    sent_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    ai_tokens_used = models.IntegerField(default=0)
    error_message = models.TextField(blank=True)
    objects = CompanyManager()

    class Meta:
        ordering = ['-sent_at']
        verbose_name = 'AI izvještaj log'
        verbose_name_plural = 'AI izvještaj logovi'

    def __str__(self):
        return f"{self.company.name} — {self.report_type} — {self.sent_at:%Y-%m-%d %H:%M}"


class FundApplicationDraft(models.Model):
    """Draft EU fund application for a company."""

    STATUS_CHOICES = [
        ('draft', 'Nacrt'),
        ('review_pending', 'Čeka pregled'),
        ('approved', 'Odobreno'),
        ('submitted', 'Predano'),
        ('rejected', 'Odbijeno'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='fund_drafts',
    )
    fund_opportunity = models.ForeignKey(
        'intelligence.FundOpportunity', on_delete=models.CASCADE,
        related_name='application_drafts',
        verbose_name='Fond / Natječaj',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    eligibility_score = models.IntegerField(default=0, verbose_name='Ocjena prihvatljivosti (0-100)')
    eligibility_notes = models.TextField(blank=True, verbose_name='Bilješke o prihvatljivosti')
    draft_content = models.JSONField(default=dict, blank=True, verbose_name='Sadržaj prijave')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='reviewed_fund_drafts',
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    objects = CompanyManager()

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Prijava na fond (nacrt)'
        verbose_name_plural = 'Prijave na fondove (nacrti)'

    def __str__(self):
        return f"{self.company.name} → {self.fund_opportunity.naziv} ({self.get_status_display()})"


class ComplianceWatchItem(models.Model):
    """Tracking legal/regulatory changes relevant to a company."""

    STATUS_CHOICES = [
        ('compliant', 'Usklađeno'),
        ('action_needed', 'Potrebna akcija'),
        ('in_progress', 'U tijeku'),
        ('waived', 'Odbačeno'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='compliance_items',
    )
    law_reference = models.CharField(
        max_length=300, verbose_name='Zakonska referenca',
        help_text='Npr. "Zakon o fiskalizaciji čl. 12"',
    )
    description = models.TextField(verbose_name='Opis')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='action_needed')
    deadline = models.DateField(null=True, blank=True, verbose_name='Rok')
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='compliance_assignments',
    )
    ai_notes = models.TextField(blank=True, verbose_name='AI bilješke')
    last_checked = models.DateTimeField(default=timezone.now, verbose_name='Zadnja provjera')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = CompanyManager()

    class Meta:
        ordering = ['deadline', '-created_at']
        verbose_name = 'Compliance stavka'
        verbose_name_plural = 'Compliance stavke'

    def __str__(self):
        return f"{self.company.name} — {self.law_reference} ({self.get_status_display()})"

    @property
    def is_overdue(self):
        if not self.deadline:
            return False
        return self.deadline < timezone.now().date() and self.status != 'compliant'

    @property
    def days_until_deadline(self):
        if not self.deadline:
            return None
        return (self.deadline - timezone.now().date()).days


class CampaignPlan(models.Model):
    """AI-generated or manual campaign plan for a company."""

    CAMPAIGN_TYPE_CHOICES = [
        ('promo', 'Promocija'),
        ('newsletter', 'Newsletter'),
        ('seasonal', 'Sezonska'),
        ('event', 'Događaj'),
        ('loyalty', 'Loyalty'),
        ('eu_fund', 'EU fond obavijest'),
    ]
    STATUS_CHOICES = [
        ('draft', 'Nacrt'),
        ('approved', 'Odobreno'),
        ('sent', 'Poslano'),
        ('cancelled', 'Otkazano'),
    ]
    CHANNEL_CHOICES = [
        ('whatsapp', 'WhatsApp'),
        ('email', 'Email'),
        ('both', 'WhatsApp + Email'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='campaign_plans',
    )
    title = models.CharField(max_length=200, verbose_name='Naziv kampanje')
    campaign_type = models.CharField(max_length=20, choices=CAMPAIGN_TYPE_CHOICES, default='promo')
    target_audience = models.CharField(max_length=300, blank=True, verbose_name='Ciljna publika')
    message_template = models.TextField(blank=True, verbose_name='Predložak poruke')
    channel = models.CharField(max_length=10, choices=CHANNEL_CHOICES, default='whatsapp')
    planned_date = models.DateTimeField(null=True, blank=True, verbose_name='Planirani datum slanja')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='draft')
    ai_suggestion = models.BooleanField(default=False, verbose_name='AI prijedlog')
    estimated_reach = models.IntegerField(default=0, verbose_name='Procijenjeni doseg')
    actual_reach = models.IntegerField(default=0, verbose_name='Stvarni doseg')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='campaign_plans_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = CompanyManager()

    class Meta:
        ordering = ['-planned_date', '-created_at']
        verbose_name = 'Plan kampanje'
        verbose_name_plural = 'Planovi kampanja'

    def __str__(self):
        return f"{self.company.name} — {self.title} ({self.get_status_display()})"


# ── BORG FENIX: Knowledge Graph modeli ──────────────────────────────────────
from limit_connect_ai.models_knowledge_graph import (  # noqa: E402, F401
    RegulatorySource,
    RegulatoryUpdate,
    ImpactDomain,
    AdaptationRule,
    LegalOpportunity,
    ClientOpportunityMatch,
)
from limit_connect_ai.models_ai_action import AIAction  # noqa: F401
