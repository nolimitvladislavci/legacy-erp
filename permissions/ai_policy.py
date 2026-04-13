"""
AI Policy Layer — Scoped Token za Gemini, CC Code, Haiku.
FAL Faza 3.

AI agenti ne smiju imati blanko cek za bazu.
Svaki task generira AIAccessToken koji definira sto smije:
  - allowed_models: koje modele smije citati/pisati
  - allowed_actions: ['read', 'create', 'update'] — bez 'delete' po defaultu
  - company_scope: za koju firmu operira
  - expires_at: token istjece

AI_POLICY_VIOLATION se logira i moze triggerirati WhatsApp alarm.
"""

import logging
import uuid
from datetime import timedelta

from django.db import models
from django.utils import timezone

logger = logging.getLogger("fal.ai_policy")


class AIAgentType(models.TextChoices):
    GEMINI = "gemini", "Google Gemini"
    CLAUDE_CODE = "claude_code", "Claude Code (CC)"
    HAIKU = "haiku", "Claude Haiku"
    SONNET = "sonnet", "Claude Sonnet"
    MCP = "mcp", "MCP Tool Call"


class AIAccessToken(models.Model):
    """Token za AI agent operacije. Generira se na pocetku svakog taska."""

    token_id = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    agent_type = models.CharField(max_length=20, choices=AIAgentType.choices)
    task_ref = models.CharField(max_length=200, help_text="CC_TASK ili GEMINI_TASK naziv")

    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="null = platform-wide (samo za superadmin taskove)",
    )
    allowed_models = models.JSONField(
        default=list, help_text='["invoicing.Invoice", "partners.Partner"] ili ["*"] za sve'
    )
    allowed_actions = models.JSONField(
        default=list, help_text='["read", "create", "update"] — delete zahtijeva eksplicitno odobrenje'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoke_reason = models.CharField(max_length=500, blank=True)

    operations_count = models.PositiveIntegerField(default=0)
    violations_count = models.PositiveIntegerField(default=0)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "permissions"
        db_table = "ai_access_tokens"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.agent_type} | {self.task_ref} | active={self.is_active}"

    @property
    def is_valid(self) -> bool:
        return self.is_active and not self.revoked_at and timezone.now() < self.expires_at

    def can_access(self, model_label: str, action: str) -> bool:
        """Provjeri moze li AI pristupiti modelu s danom akcijom."""
        if not self.is_valid:
            self._log_violation(model_label, action, "Token nevazeci ili istekao")
            return False

        allowed = self.allowed_models
        if "*" not in allowed and model_label not in allowed:
            app_label = model_label.split(".")[0]
            if f"{app_label}.*" not in allowed:
                self._log_violation(model_label, action, f"Model {model_label} nije u scope")
                return False

        if action not in self.allowed_actions:
            self._log_violation(model_label, action, f"Akcija {action} nije dozvoljena")
            return False

        self.operations_count += 1
        self.last_used_at = timezone.now()
        self.save(update_fields=["operations_count", "last_used_at"])
        logger.info(f"AI_ACCESS | {self.agent_type} | {model_label}.{action} | {self.task_ref}")
        return True

    def _log_violation(self, model_label: str, action: str, reason: str):
        self.violations_count += 1
        self.save(update_fields=["violations_count"])
        logger.warning(
            f"AI_POLICY_VIOLATION | agent={self.agent_type} | "
            f"model={model_label} | action={action} | reason={reason} | "
            f"task={self.task_ref} | token={self.token_id}"
        )
        if self.violations_count >= 3:
            self._alert_violations()

    def _alert_violations(self):
        try:
            from core.whatsapp import send_text

            send_text(
                phone="+4915771998747",
                message=(
                    f"FAL ALERT: AI_POLICY_VIOLATION\n"
                    f"Agent: {self.agent_type}\n"
                    f"Task: {self.task_ref}\n"
                    f"Violations: {self.violations_count}\n"
                    f"Token: {str(self.token_id)[:8]}..."
                ),
            )
        except ImportError:
            pass

    def revoke(self, reason: str = "Manual revoke"):
        self.is_active = False
        self.revoked_at = timezone.now()
        self.revoke_reason = reason
        self.save(update_fields=["is_active", "revoked_at", "revoke_reason"])


# -- PREDDEFINIRANI PROFILI --------------------------------------------------
AI_PROFILES = {
    "compliance_watchdog": {
        "allowed_models": ["invoicing.Invoice", "documents.ArhivaEntry", "eracun.EInvoice"],
        "allowed_actions": ["read"],
        "duration_hours": 24,
    },
    "ai_inbox_processor": {
        "allowed_models": ["documents.ArhivaEntry"],
        "allowed_actions": ["read", "update"],
        "duration_hours": 2,
    },
    "daily_report": {
        "allowed_models": ["invoicing.*", "pos.*", "worktime.*"],
        "allowed_actions": ["read"],
        "duration_hours": 4,
    },
    "gemini_patrol": {
        "allowed_models": ["documents.ArhivaEntry", "invoicing.Invoice", "pos.Receipt"],
        "allowed_actions": ["read"],
        "duration_hours": 1,
    },
    "warehouse_w1": {
        "allowed_models": ["inventory.InventoryItem", "inventory.GoodsReceipt"],
        "allowed_actions": ["read", "create", "update"],
        "duration_hours": 2,
    },
    "livestock_vet": {
        "allowed_models": ["livestock.Livestock", "livestock.HealthRecord"],
        "allowed_actions": ["read", "create"],
        "duration_hours": 4,
    },
}


def create_ai_token(
    agent_type: str,
    task_ref: str,
    allowed_models: list,
    allowed_actions: list = None,
    company=None,
    duration_hours: int = 4,
) -> AIAccessToken:
    """Factory za kreiranje AI tokena na pocetku svakog taska."""
    if allowed_actions is None:
        allowed_actions = ["read"]

    if "delete" in allowed_actions:
        logger.warning(f"AI token s DELETE ovlastima kreiran za task: {task_ref}")

    token = AIAccessToken.objects.create(
        agent_type=agent_type,
        task_ref=task_ref,
        company=company,
        allowed_models=allowed_models,
        allowed_actions=allowed_actions,
        expires_at=timezone.now() + timedelta(hours=duration_hours),
    )
    logger.info(
        f"AI_TOKEN_CREATED | {agent_type} | {task_ref} | "
        f"models={allowed_models} | actions={allowed_actions} | "
        f"expires={token.expires_at:%H:%M}"
    )
    return token


def token_from_profile(
    agent_type: str,
    task_ref: str,
    profile_name: str,
    company=None,
) -> AIAccessToken:
    """Kreiraj token iz predefiniranog profila."""
    if profile_name not in AI_PROFILES:
        raise ValueError(f"Nepoznati profil: {profile_name}. Dostupno: {list(AI_PROFILES.keys())}")
    profile = AI_PROFILES[profile_name]
    return create_ai_token(
        agent_type=agent_type,
        task_ref=task_ref,
        allowed_models=profile["allowed_models"],
        allowed_actions=profile["allowed_actions"],
        company=company,
        duration_hours=profile["duration_hours"],
    )
