import os

def rebuild_calculator():
    # 1. MODELS.PY
    with open('calculator/models.py', 'w') as f:
        f.write("""from django.db import models
from django.utils.translation import gettext_lazy as _
from projects.models import Project

class Normative(models.Model):
    name = models.CharField(max_length=255, verbose_name=_('Naziv normativa'))
    unit = models.CharField(max_length=20, default='m2', verbose_name=_('Jedinica mjere'))
    base_price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name=_('Cijena materijala'))
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
""")

    # 2. VIEWS.PY - Ispravljen import
    with open('calculator/views.py', 'w') as f:
        f.write("""from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from .models import Calculation, Normative

@login_required
def calculation_list(request):
    calculations = Calculation.objects.all()
    return render(request, 'calculator/list.html', {'calculations': calculations})

@login_required
def calculation_detail(request, pk):
    calc = get_object_or_404(Calculation, pk=pk)
    return render(request, 'calculator/detail.html', {'calculation': calc})
""")

    # 3. URLS.PY
    with open('calculator/urls.py', 'w') as f:
        f.write("""from django.urls import path
from . import views

urlpatterns = [
    path('', views.calculation_list, name='calculation_list'),
    path('<int:pk>/', views.calculation_detail, name='calculation_detail'),
]
""")

    print("Calculator app code has been fully rebuilt and corrected.")

if __name__ == "__main__":
    rebuild_calculator()
