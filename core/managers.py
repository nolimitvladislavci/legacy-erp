from django.core.exceptions import ObjectDoesNotExist
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

from django.db import models, DatabaseError, IntegrityError

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
            if 'company' in model_fields:
                qs = qs.filter(company=company)
            elif 'parent_company' in model_fields:
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
    return getattr(_branch_local, 'branch', None)


def set_current_branch(branch):
    _branch_local.branch = branch


def clear_current_branch():
    _branch_local.branch = None
