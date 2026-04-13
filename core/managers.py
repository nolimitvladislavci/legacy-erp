"""
CompanyManager — automatski filtrira QuerySet po aktivnoj tvrtki.

Dodaj na svaki model koji ima 'company' FK:

    from core.managers import CompanyManager

    class MyModel(models.Model):
        company = models.ForeignKey('companies.Company', ...)
        objects = CompanyManager()

Za cross-company upite (Django admin, reports, seeding):
    MyModel.objects.unscoped().all()
    MyModel.objects.unscoped().filter(...)
"""

import threading

from django.db import models

from .tenant import get_current_company


class CompanyQuerySet(models.QuerySet):
    def unscoped(self):
        """Vraća QuerySet bez company filtera."""
        return self.all()


class CompanyManager(models.Manager):
    def get_queryset(self):
        qs = CompanyQuerySet(self.model, using=self._db)
        company = get_current_company()
        if company is not None:
            # Check which FK name this model uses for company
            model_fields = {f.name for f in self.model._meta.get_fields()}
            if "company" in model_fields:
                qs = qs.filter(company=company)
            elif "parent_company" in model_fields:
                qs = qs.filter(parent_company=company)
            # Models without company or parent_company FK → no auto-filter
        return qs

    def unscoped(self):
        """
        Bypass company filtera — za admin, migracije, seeding, reports.
        Uvijek vraća sve objekte bez obzira na thread-local company.

        Primjer:
            Invoice.objects.unscoped().filter(status='PAID')
        """
        return CompanyQuerySet(self.model, using=self._db)


# ── Branch (Podružnica) thread-local ─────────────────────────────────────────

_branch_local = threading.local()


def get_current_branch():
    """Return the active CompanyBranch for the current thread, or None."""
    return getattr(_branch_local, "branch", None)


def set_current_branch(branch):
    _branch_local.branch = branch


def clear_current_branch():
    _branch_local.branch = None


# ── Active (Soft-Delete) Manager ─────────────────────────────────────────────


class ActiveQuerySet(models.QuerySet):
    """QuerySet that filters to active records only."""

    def active(self):
        return self.filter(is_active=True)

    def inactive(self):
        return self.filter(is_active=False)

    def soft_delete(self):
        """Bulk soft-delete all records in queryset."""
        from django.utils import timezone

        return self.update(is_active=False, deactivated_at=timezone.now())

    def reactivate(self):
        """Bulk reactivate all records in queryset."""
        return self.update(is_active=True, deactivated_at=None)


class ActiveManager(models.Manager):
    """Manager that returns only active (is_active=True) records by default.

    Usage:
        class MyModel(models.Model):
            is_active = models.BooleanField(default=True)
            objects = ActiveManager()        # .all() returns active only
            all_objects = models.Manager()   # .all() returns everything

    Queryset methods:
        MyModel.objects.active()       # explicit active filter
        MyModel.objects.inactive()     # deactivated records
        MyModel.objects.soft_delete()  # bulk deactivate
    """

    def get_queryset(self):
        return ActiveQuerySet(self.model, using=self._db).filter(is_active=True)

    def include_inactive(self):
        """Return all records including deactivated ones."""
        return ActiveQuerySet(self.model, using=self._db)


# ── Company + Active combined Manager ────────────────────────────────────────


class CompanyActiveManager(CompanyManager):
    """Combines company-scoping with soft-delete filtering.

    Usage:
        class Invoice(models.Model):
            company = models.ForeignKey(Company, ...)
            is_active = models.BooleanField(default=True)
            objects = CompanyActiveManager()
    """

    def get_queryset(self):
        qs = super().get_queryset()
        model_fields = {f.name for f in self.model._meta.get_fields()}
        if "is_active" in model_fields:
            qs = qs.filter(is_active=True)
        return qs

    def include_inactive(self):
        """Return company-scoped records including deactivated ones."""
        return super().get_queryset()
