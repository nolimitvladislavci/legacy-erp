from django.db import models, DatabaseError, IntegrityError
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from core.managers import CompanyManager


class Conversation(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="ai_conversations",
    )
    title = models.CharField(max_length=200, blank=True, default="")
    module_context = models.CharField(max_length=50, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"[{self.user.username}] {self.title or Razgovor}"


class Message(models.Model):
    ROLE_CHOICES = [
        ("user", "User"),
        ("assistant", "Assistant"),
        ("system", "System"),
    ]
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages",
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField(blank=True, default="")
    tool_calls = models.JSONField(default=list, blank=True)
    tool_results = models.JSONField(default=list, blank=True)
    tokens_used = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.role}: {self.content[:60]}"


class AIUsageLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="ai_usage_logs",
    )
    conversation = models.ForeignKey(
        Conversation, on_delete=models.SET_NULL, null=True, blank=True,
    )
    input_tokens = models.IntegerField(default=0)
    output_tokens = models.IntegerField(default=0)
    model = models.CharField(max_length=60, default="claude-sonnet-4-20250514")
    cost_estimate = models.DecimalField(max_digits=8, decimal_places=6, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} — {self.input_tokens}+{self.output_tokens} tokens"


class PatrolReport(models.Model):
    """Stores nightly AI patrol results for dashboard display."""
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    findings = models.JSONField(default=list)
    summary = models.TextField(blank=True)
    raw_data = models.JSONField(default=dict, blank=True)
    has_issues = models.BooleanField(default=False)
    finding_count = models.PositiveIntegerField(default=0)
    critical_count = models.PositiveIntegerField(default=0)
    objects = CompanyManager()

    class Meta:
        ordering = ['-created_at']
        get_latest_by = 'created_at'

    def __str__(self):
        return f'Patrol {self.created_at:%Y-%m-%d %H:%M} — {self.company.name}'


class KnowledgeArticle(models.Model):
    """
    RAG Knowledge Base — strukturirani članci koje AI koristi za odgovore.
    Umjesto haluciniranja, AI povlači točne podatke iz ove baze.
    """
    MODULE_CHOICES = [
        ('pos', 'POS (Blagajna)'),
        ('invoicing', 'Fakturiranje'),
        ('inventory', 'Skladište'),
        ('experiences', 'Iskustva / Agro-Turizam'),
        ('work_orders', 'Radni nalozi'),
        ('rental', 'Smještaj / Rental'),
        ('udruge', 'Udruge'),
        ('marketplace', 'OPG Tržnica'),
        ('compliance', 'Zakoni / Compliance'),
        ('borg', 'BORG operacije'),
        ('general', 'Opće'),
    ]

    module = models.CharField(max_length=30, choices=MODULE_CHOICES, db_index=True)
    title = models.CharField(max_length=200, verbose_name='Naslov')
    content = models.TextField(verbose_name='Sadržaj',
                                help_text='Markdown format. AI koristi ovo za RAG odgovore.')
    keywords = models.CharField(max_length=500, blank=True,
                                 help_text='Ključne riječi za pretragu, odvojene zarezom')
    is_active = models.BooleanField(default=True)
    priority = models.PositiveIntegerField(default=5,
                                            help_text='1=najvažnije, 10=najmanje')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Članak baze znanja'
        verbose_name_plural = 'Članci baze znanja'
        ordering = ['module', 'priority', 'title']

    def __str__(self):
        return f'[{self.module}] {self.title}'
