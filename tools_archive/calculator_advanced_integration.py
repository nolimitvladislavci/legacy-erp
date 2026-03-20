import os

def deploy():
    # 1. MODIFIKACIJA MODELS.PY - Dodavanje poslovne logike za marže i troškove
    models_path = 'calculator/models.py'
    models_code = """from django.db import models
from django.db.models import Sum, F
from django.utils.translation import gettext_lazy as _
from projects.models import Project
from accounts.models import UserProfile

class Normative(models.Model):
    name = models.CharField(max_length=255, verbose_name=_('Naziv normativa'))
    unit = models.CharField(max_length=20, default='m2', verbose_name=_('Jedinica mjere'))
    base_material_cost = models.DecimalField(max_digits=12, decimal_places=2, verbose_name=_('Cijena materijala po jedinici'))
    estimated_hours_per_unit = models.FloatField(verbose_name=_('Sati rada po jedinici'))

    class Meta:
        verbose_name = _('Normativ')
        verbose_name_plural = _('Normativi')

    def __str__(self):
        return f"{self.name} ({self.unit})"

class Calculation(models.Model):
    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name='calculation')
    margin_percentage = models.FloatField(default=20.0, verbose_name=_('Marža (%)'))
    vat_percentage = models.FloatField(default=25.0, verbose_name=_('PDV (%)'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def calculate_totals(self):
        items = self.items.all()
        total_mat = sum(item.total_material_cost for item in items)
        total_lab = sum(item.total_labor_cost for item in items)
        net_total = total_mat + total_lab
        gross_total = net_total * (1 + (self.margin_percentage / 100))
        return {
            'material': round(total_mat, 2),
            'labor': round(total_lab, 2),
            'net_cost': round(net_total, 2),
            'offer_total_net': round(gross_total, 2),
            'offer_total_vat': round(gross_total * (1 + (self.vat_percentage / 100)), 2)
        }

    def __str__(self):
        return f"Kalkulacija - {self.project.code}"

class CalculationItem(models.Model):
    calculation = models.ForeignKey(Calculation, on_delete=models.CASCADE, related_name='items')
    normative = models.ForeignKey(Normative, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.CharField(max_length=255, verbose_name=_('Opis stavke'))
    quantity = models.FloatField(default=1.0)
    unit_price_material = models.DecimalField(max_digits=12, decimal_places=2)
    labor_hours_per_unit = models.FloatField()
    labor_rate_applied = models.DecimalField(max_digits=12, decimal_places=2, help_text=_('Cijena sata rada u trenutku kalkulacije'))

    @property
    def total_material_cost(self):
        return float(self.unit_price_material) * self.quantity

    @property
    def total_labor_cost(self):
        return self.labor_hours_per_unit * float(self.labor_rate_applied) * self.quantity

    @property
    def total_price(self):
        return self.total_material_cost + self.total_labor_cost
"""
    with open(models_path, 'w') as f: f.write(models_code)

    # 2. MODIFIKACIJA VIEWS.PY - Napredno procesiranje kalkulacije
    views_path = 'calculator/views.py'
    views_code = """from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from .models import Calculation, CalculationItem, Normative
from projects.models import Project

@login_required
def create_from_project(request, project_id):
    project = get_object_or_404(Project, pk=project_id)
    calculation, created = Calculation.objects.get_or_create(project=project)
    return redirect('calculation_detail', pk=calculation.pk)

@login_required
def calculation_detail(request, pk):
    calc = get_object_or_404(Calculation, pk=pk)
    totals = calc.calculate_totals()
    return render(request, 'calculator/detail.html', {
        'calculation': calc,
        'totals': totals,
        'items': calc.items.all()
    })
"""
    with open(views_path, 'w') as f: f.write(views_code)

    # 3. ADMIN.PY - Omogućavanje inline uređivanja troškovnika
    admin_path = 'calculator/admin.py'
    admin_code = """from django.contrib import admin
from .models import Calculation, CalculationItem, Normative

class CalculationItemInline(admin.TabularInline):
    model = CalculationItem
    extra = 1
    fields = ('description', 'quantity', 'unit_price_material', 'labor_hours_per_unit', 'labor_rate_applied')

@admin.register(Calculation)
class CalculationAdmin(admin.ModelAdmin):
    list_display = ('project', 'get_net_total', 'margin_percentage', 'updated_at')
    inlines = [CalculationItemInline]
    
    def get_net_total(self, obj):
        return obj.calculate_totals()['net_cost']
    get_net_total.short_description = 'Ukupni Trošak (Neto)'

@admin.register(Normative)
class NormativeAdmin(admin.ModelAdmin):
    list_display = ('name', 'unit', 'base_material_cost', 'estimated_hours_per_unit')
"""
    with open(admin_path, 'w') as f: f.write(admin_code)

if __name__ == "__main__":
    deploy()
