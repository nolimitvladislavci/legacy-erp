from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.managers import CompanyManager


class Project(models.Model):
    name = models.CharField(max_length=200, verbose_name=_("Naziv projekta"))
    code = models.CharField(max_length=30, unique=True, verbose_name=_("Šifra"))
    description = models.TextField(blank=True, verbose_name=_("Opis"))
    location = models.CharField(max_length=255, blank=True, verbose_name=_("Lokacija"))
    status = models.CharField(max_length=20, default="planning")
    client = models.ForeignKey("partners.Partner", on_delete=models.SET_NULL, null=True, blank=True)
    company = models.ForeignKey("companies.Company", on_delete=models.SET_NULL, null=True, blank=True)
    objects = CompanyManager()
    manager = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="managed_projects")
    team = models.ManyToManyField(User, related_name="team_projects", blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    budget = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    is_public = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def actual_cost(self):
        """Stvarni trošak = suma (sati × satnica) iz TimeEntry-ja."""
        from decimal import Decimal

        from django.db.models import DecimalField, F, Sum
        from django.db.models.functions import Coalesce

        total = self.time_entries.aggregate(
            cost=Coalesce(
                Sum(F("hours") * F("user__employeeprofile__hourly_rate"), output_field=DecimalField()), Decimal("0")
            )
        )["cost"]
        return total

    @property
    def budget_usage_percentage(self):
        if not self.budget or self.budget == 0:
            return 0
        return round(float(self.actual_cost) / float(self.budget) * 100, 1)

    class Meta:
        verbose_name = _("Projekt")
        verbose_name_plural = _("Projekti")


class ProjectUpdate(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="updates")
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    title = models.CharField(max_length=200)
    content = models.TextField()
    is_public = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


class ProjectPhoto(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="photos")
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)  # OVO JE FALILO
    image = models.ImageField(upload_to="projects/photos/")
    caption = models.CharField(max_length=255, blank=True)
    is_public = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)
