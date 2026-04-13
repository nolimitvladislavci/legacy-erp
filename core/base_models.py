"""
Fenix Abstract Base Models
==========================
Reusable abstract models that eliminate field duplication across 85+ apps.

Usage:
    from core.base_models import CompanyOwnedModel, AuditableModel

    class Invoice(AuditableModel):
        number = models.CharField(max_length=50)
        # company, created_at, updated_at, created_by, is_active — all inherited

Hierarchy:
    TimestampedModel          → created_at, updated_at
    CompanyOwnedModel         → + company FK
    UserTrackedModel          → + created_by FK
    SoftDeleteModel           → is_active, soft_delete()
    AuditableModel            → all of the above
    MoneyModel                → + currency, amount helpers
"""

from django.conf import settings
from django.db import models
from django.utils import timezone


class TimestampedModel(models.Model):
    """Base: auto timestamps on create/update."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]


class CompanyOwnedModel(TimestampedModel):
    """Timestamps + company FK with scoped manager."""

    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="%(app_label)s_%(class)s_set",
    )

    class Meta(TimestampedModel.Meta):
        abstract = True


class UserTrackedModel(CompanyOwnedModel):
    """Company-owned + who created it."""

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(app_label)s_%(class)s_created",
    )

    class Meta(CompanyOwnedModel.Meta):
        abstract = True


class SoftDeleteModel(models.Model):
    """Mixin: soft delete instead of hard delete."""

    is_active = models.BooleanField(default=True, db_index=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True

    def soft_delete(self):
        self.is_active = False
        self.deactivated_at = timezone.now()
        self.save(update_fields=["is_active", "deactivated_at"])

    def reactivate(self):
        self.is_active = True
        self.deactivated_at = None
        self.save(update_fields=["is_active", "deactivated_at"])


class AuditableModel(UserTrackedModel, SoftDeleteModel):
    """Full audit trail: company + user + timestamps + soft delete.

    Combines all base functionality:
    - created_at, updated_at (auto)
    - company FK (CASCADE)
    - created_by FK (SET_NULL)
    - is_active + soft_delete()
    """

    class Meta(UserTrackedModel.Meta):
        abstract = True


class NotesModel(models.Model):
    """Mixin: notes/description text field."""

    notes = models.TextField(blank=True, default="")

    class Meta:
        abstract = True


class StatusModel(models.Model):
    """Mixin: generic status field with choices.

    Subclass must define STATUS_CHOICES:
        class MyModel(StatusModel):
            STATUS_CHOICES = [('draft', 'Draft'), ('active', 'Active')]
    """

    status = models.CharField(max_length=30, db_index=True)

    class Meta:
        abstract = True
