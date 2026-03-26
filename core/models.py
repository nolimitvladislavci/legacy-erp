from django.db import models
from core.managers import CompanyManager


class SystemAuditLog(models.Model):
    """Immutable audit trail for all financial data changes."""
    ACTION_CHOICES = [
        ('create', 'Kreiranje'),
        ('update', 'Ažuriranje'),
        ('delete', 'Brisanje'),
        ('read', 'Pristup'),
    ]

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    user = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)
    company = models.ForeignKey('companies.Company', on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=100, db_index=True)
    object_id = models.CharField(max_length=50)
    object_repr = models.CharField(max_length=300, blank=True)
    changes = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    objects = CompanyManager()

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['model_name', 'object_id']),
            models.Index(fields=['company', 'timestamp']),
            models.Index(fields=['user', 'timestamp']),
        ]
        verbose_name = 'Revizijski zapis'
        verbose_name_plural = 'Revizijski zapisi'

    def __str__(self):
        return f"{self.timestamp:%Y-%m-%d %H:%M} | {self.action} | {self.model_name} | {self.object_repr[:50]}"


class InspectionToken(models.Model):
    """
    Inspekcijski pristupni token — generira se iz Panic Buttona.
    Inspektor skenira QR → pristupa read-only dashboardu bez logina.
    """
    SCOPE_CHOICES = [
        ('porezna',  'Porezna inspekcija'),
        ('pos',      'POS / Fiskalizacija'),
        ('radna',    'Radna inspekcija'),
        ('sanitarna', 'Sanitarna inspekcija'),
        ('hapih',    'HAPIH — Knjiga lijekova'),
        ('jrdz',     'JRDZ — Registar životinja'),
        ('vetis',    'VetIS — Vet knjiga'),
        ('all',      'Potpuni pristup (sve)'),
    ]

    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                                related_name='inspection_tokens')
    token = models.CharField(max_length=64, unique=True, db_index=True)
    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES, default='all')
    label = models.CharField(max_length=200, blank=True,
                             verbose_name='Naziv (npr. "Porezna inspekcija 22.03.2026")')

    # Period koji inspektor može vidjeti
    date_from = models.DateField(null=True, blank=True, verbose_name='Od datuma')
    date_to = models.DateField(null=True, blank=True, verbose_name='Do datuma')

    # Sigurnost
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(verbose_name='Istječe')
    max_views = models.IntegerField(default=100, verbose_name='Max pregleda')
    view_count = models.IntegerField(default=0)

    # Audit
    created_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_accessed = models.DateTimeField(null=True, blank=True)
    access_ip = models.GenericIPAddressField(null=True, blank=True)
    objects = CompanyManager()

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Inspekcijski token'
        verbose_name_plural = 'Inspekcijski tokeni'

    def __str__(self):
        return f'{self.label or self.scope} — {self.company.name}'

    def save(self, *args, **kwargs):
        if not self.token:
            import secrets
            self.token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    @property
    def is_valid(self):
        from django.utils import timezone
        if not self.is_active:
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        if self.view_count >= self.max_views:
            return False
        return True

    def record_access(self, ip=None):
        from django.utils import timezone
        self.view_count += 1
        self.last_accessed = timezone.now()
        if ip:
            self.access_ip = ip
        self.save(update_fields=['view_count', 'last_accessed', 'access_ip'])
