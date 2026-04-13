import uuid

from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.managers import CompanyManager


class AIModulePermission(models.Model):
    """
    Definira razinu AI pristupa po modulu, po firmi.
    Granularne dozvole: can_read, can_write, can_create, can_modify.
    access_level se automatski izračunava iz booleana za gate kompatibilnost.
    """

    ACCESS_DISABLED = 0
    ACCESS_READ_ONLY = 1
    ACCESS_ASSISTED = 2
    ACCESS_AUTONOMOUS = 3
    ACCESS_COUNCIL = 4

    ACCESS_LEVELS = [
        (ACCESS_DISABLED, _("Isključeno")),
        (ACCESS_READ_ONLY, _("Samo čitanje")),
        (ACCESS_ASSISTED, _("Asistiran (odobrenje)")),
        (ACCESS_AUTONOMOUS, _("Autonoman")),
        (ACCESS_COUNCIL, _("AI Vijeće (2/3 glasova)")),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="ai_permissions",
        verbose_name=_("Tvrtka"),
        null=True,
        blank=True,
        help_text=_("Prazno = globalno (sve tvrtke)"),
    )
    module = models.CharField(max_length=50, verbose_name=_("Modul"))
    # Primarni naziv za prikaz u UI
    module_name = property(lambda self: self.module)

    # ── Granularne dozvole ──
    can_read = models.BooleanField(default=False, verbose_name=_("Čitanje"))
    can_write = models.BooleanField(default=False, verbose_name=_("Pisanje"))
    can_create = models.BooleanField(default=False, verbose_name=_("Kreiranje"))
    can_modify = models.BooleanField(default=False, verbose_name=_("Izmjene"))

    # ── Kompatibilnost s gate sustavom ──
    access_level = models.IntegerField(
        choices=ACCESS_LEVELS, default=ACCESS_DISABLED, verbose_name=_("Razina pristupa")
    )

    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Ažurirao"))
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True, verbose_name=_("Napomena"))
    objects = CompanyManager()

    class Meta:
        db_table = "ai_module_permission"
        unique_together = ("company", "module")
        verbose_name = _("AI dozvola modula")
        verbose_name_plural = _("AI dozvole modula")
        ordering = ["module"]

    def __str__(self):
        company_name = self.company.name if self.company else "GLOBALNO"
        perms = []
        if self.can_read:
            perms.append("R")
        if self.can_write:
            perms.append("W")
        if self.can_create:
            perms.append("C")
        if self.can_modify:
            perms.append("M")
        return f"{company_name} → {self.module} [{'/'.join(perms) or 'OFF'}]"

    def save(self, *args, **kwargs):
        """Auto-sync: compute access_level iz booleana za gate kompatibilnost."""
        # Compute access_level
        if self.can_modify or self.can_create:
            if self.can_write:
                self.access_level = self.ACCESS_AUTONOMOUS
            else:
                self.access_level = self.ACCESS_ASSISTED
        elif self.can_write:
            self.access_level = self.ACCESS_ASSISTED
        elif self.can_read:
            self.access_level = self.ACCESS_READ_ONLY
        else:
            self.access_level = self.ACCESS_DISABLED
        super().save(*args, **kwargs)

    @classmethod
    def get_level(cls, company, module):
        """Vrati razinu pristupa za modul. Provjeri firmu, pa globalno, pa DISABLED."""
        try:
            return cls.objects.get(company=company, module=module).access_level
        except cls.DoesNotExist:
            pass
        try:
            return cls.objects.get(company=None, module=module).access_level
        except cls.DoesNotExist:
            return cls.ACCESS_DISABLED

    @classmethod
    def get_perm(cls, company, module):
        """Vrati permission objekt ili None."""
        try:
            return cls.objects.get(company=company, module=module)
        except cls.DoesNotExist:
            try:
                return cls.objects.get(company=None, module=module)
            except cls.DoesNotExist:
                return None


class PendingAIAction(models.Model):
    """
    Za ASSISTED razinu — AI kreira prijedlog, superadmin/company_admin odobrava.
    """

    STATUS_CHOICES = [
        ("pending", _("Čeka odobrenje")),
        ("approved", _("Odobreno")),
        ("rejected", _("Odbijeno")),
        ("executed", _("Izvršeno")),
        ("expired", _("Isteklo")),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="pending_ai_actions",
        verbose_name=_("Tvrtka"),
        null=True,
        blank=True,
    )
    module = models.CharField(max_length=50, verbose_name=_("Modul"))
    action_type = models.CharField(
        max_length=50, verbose_name=_("Tip akcije"), help_text=_("npr. create, update, delete, send")
    )
    description = models.TextField(verbose_name=_("Opis akcije"))
    proposed_code = models.TextField(blank=True, default="", verbose_name=_("Predloženi kod"))
    payload = models.JSONField(
        default=dict, verbose_name=_("Podaci"), help_text=_("JSON s detaljima akcije za izvršenje")
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending", verbose_name=_("Status"))
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_ai_actions",
        verbose_name=_("Pregledao"),
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True, verbose_name=_("Komentar"))
    result = models.JSONField(default=dict, blank=True, verbose_name=_("Rezultat izvršenja"))

    objects = CompanyManager()

    class Meta:
        db_table = "ai_pending_action"
        verbose_name = _("AI čekajuća akcija")
        verbose_name_plural = _("AI čekajuće akcije")
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.status}] {self.module}.{self.action_type}"


class AIActionLog(models.Model):
    """Audit trail svakog AI poziva — tko, što, kada, rezultat."""

    OUTCOME_CHOICES = [
        ("allowed", _("Dopušteno")),
        ("blocked", _("Blokirano")),
        ("queued", _("U redu čekanja")),
        ("executed", _("Izvršeno")),
        ("failed", _("Neuspješno")),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    timestamp = models.DateTimeField(auto_now_add=True)
    company = models.ForeignKey(
        "companies.Company", on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Tvrtka")
    )
    module = models.CharField(max_length=50, verbose_name=_("Modul"))
    action_type = models.CharField(max_length=50, verbose_name=_("Tip"))
    access_level = models.IntegerField(choices=AIModulePermission.ACCESS_LEVELS, verbose_name=_("Razina"))
    outcome = models.CharField(max_length=20, choices=OUTCOME_CHOICES, verbose_name=_("Ishod"))
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Korisnik"))
    details = models.JSONField(default=dict, blank=True, verbose_name=_("Detalji"))
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    objects = CompanyManager()

    class Meta:
        db_table = "ai_action_log"
        verbose_name = _("AI log")
        verbose_name_plural = _("AI logovi")
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.timestamp:%d.%m %H:%M} | {self.module}.{self.action_type} → {self.outcome}"


class AICouncilVote(models.Model):
    """
    Glasanje AI agenata za COUNCIL razinu (Razina 4).
    Akcija se izvršava kad 2/3 agenata glasaju ZA.
    """

    AGENT_CHOICES = [
        ("claude_haiku", "Claude Haiku (Analitika)"),
        ("claude_sonnet", "Claude Sonnet (Arhitektura)"),
        ("gemini_flash", "Gemini Flash (Validacija)"),
        ("system", "System (Auto)"),
    ]
    VOTE_CHOICES = [
        ("approve", "Odobri"),
        ("reject", "Odbij"),
        ("abstain", "Suzdržan"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pending_action = models.ForeignKey(PendingAIAction, on_delete=models.CASCADE, related_name="council_votes")
    agent = models.CharField(max_length=30, choices=AGENT_CHOICES)
    vote = models.CharField(max_length=10, choices=VOTE_CHOICES)
    reasoning = models.TextField(blank=True, help_text="Zašto ovaj glas")
    voted_at = models.DateTimeField(auto_now_add=True)
    confidence = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    class Meta:
        db_table = "ai_council_vote"
        unique_together = ("pending_action", "agent")
        ordering = ["voted_at"]

    def __str__(self):
        return f"{self.agent} → {self.vote} ({self.pending_action.action_type})"

    @classmethod
    def get_decision(cls, pending_action):
        """
        Vrati odluku vijeća:
        - 'approved' ako 2+ glasaju ZA
        - 'rejected' ako 2+ glasaju PROTIV
        - 'pending' inače
        """
        votes = cls.objects.filter(pending_action=pending_action)
        approve = votes.filter(vote="approve").count()
        reject = votes.filter(vote="reject").count()
        total = votes.count()

        if approve >= 2:
            return "approved"
        elif reject >= 2:
            return "rejected"
        elif total >= 3:
            return "rejected"  # Svi glasali, nema konsenzusa
        return "pending"
