import os

def update_calculator():
    # --- MODELS.PY ---
    models_path = 'calculator/models.py'
    models_content = """from django.db import models
from django.utils.translation import gettext_lazy as _
from projects.models import Project

class Normative(models.Model):
    name = models.CharField(max_length=255, verbose_name=_('Naziv normativa'))
    unit = models.CharField(max_length=20, default='m2', verbose_name=_('Jedinica mjere'))
    base_price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name=_('Osnovna cijena materijala'))
    estimated_labor_hours = models.FloatField(verbose_name=_('Procjena sati rada po jedinici'))

    def __str__(self):
        return self.name

class Calculation(models.Model):
    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name='calculation')
    created_at = models.DateTimeField(auto_now_add=True)
    margin_percentage = models.FloatField(default=20.0, verbose_name=_('Dodatna marža (%)'))

    @property
    def total_value(self):
        return sum(item.total_price for item in self.items.all())

    def __str__(self):
        return f"Kalkulacija za: {self.project.name}"

class CalculationItem(models.Model):
    calculation = models.ForeignKey(Calculation, on_delete=models.CASCADE, related_name='items')
    description = models.CharField(max_length=255, verbose_name=_('Opis stavke'))
    quantity = models.FloatField(default=1.0, verbose_name=_('Količina'))
    unit_price_material = models.DecimalField(max_digits=12, decimal_places=2, verbose_name=_('Cijena materijala'))
    labor_hours = models.FloatField(verbose_name=_('Sati rada'))
    labor_rate = models.DecimalField(max_digits=12, decimal_places=2, verbose_name=_('Satnica rada (EUR)'))

    @property
    def total_price(self):
        material_cost = float(self.unit_price_material) * self.quantity
        labor_cost = self.labor_hours * float(self.labor_rate) * self.quantity
        return round(material_cost + labor_cost, 2)
"""
    with open(models_path, 'w') as f: f.write(models_content)

    # --- ADMIN.PY ---
    admin_path = 'calculator/admin.py'
    admin_content = """from django.contrib import admin
from .models import Calculation, CalculationItem, Normative

class CalculationItemInline(admin.TabularInline):
    model = CalculationItem
    extra = 1

@admin.register(Calculation)
class CalculationAdmin(admin.ModelAdmin):
    list_display = ('project', 'total_value', 'margin_percentage')
    inlines = [CalculationItemInline]

@admin.register(Normative)
class NormativeAdmin(admin.ModelAdmin):
    list_display = ('name', 'unit', 'base_price', 'estimated_labor_hours')
"""
    with open(admin_path, 'w') as f: f.write(admin_content)
    print("Calculator models and admin updated.")

if __name__ == "__main__":
    update_calculator()
