import os

def fix_models_for_auto_migration():
    path = 'calculator/models.py'
    content = """from django.db import models
from django.utils.translation import gettext_lazy as _
from projects.models import Project

class Normative(models.Model):
    name = models.CharField(max_length=255, verbose_name=_('Naziv normativa'))
    unit = models.CharField(max_length=20, default='m2', verbose_name=_('Jedinica mjere'))
    base_material_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name=_('Cijena materijala'))
    estimated_hours_per_unit = models.FloatField(default=0, verbose_name=_('Sati rada po jedinici'))

    class Meta:
        verbose_name = _('Normativ')
        verbose_name_plural = _('Normativi')

    def __str__(self):
        return self.name

class Calculation(models.Model):
    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name='calculation')
    margin_percentage = models.FloatField(default=20.0, verbose_name=_('Marža (%)'))
    vat_percentage = models.FloatField(default=25.0, verbose_name=_('PDV (%)'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def calculate_totals(self):
        items = self.items.all()
        total_mat = sum(float(item.unit_price_material) * item.quantity for item in items)
        total_lab = sum(item.labor_hours_per_unit * float(item.labor_rate_applied) * item.quantity for item in items)
        net_total = total_mat + total_lab
        gross_total = net_total * (1 + (self.margin_percentage / 100))
        return {
            'material': round(total_mat, 2),
            'labor': round(total_lab, 2),
            'net_cost': round(net_total, 2),
            'offer_total_net': round(gross_total, 2),
            'offer_total_vat': round(gross_total * (1 + (self.vat_percentage / 100)), 2)
        }

class CalculationItem(models.Model):
    calculation = models.ForeignKey(Calculation, on_delete=models.CASCADE, related_name='items')
    normative = models.ForeignKey(Normative, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.CharField(max_length=255)
    quantity = models.FloatField(default=1.0)
    unit_price_material = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    labor_hours_per_unit = models.FloatField(default=0)
    labor_rate_applied = models.DecimalField(max_digits=12, decimal_places=2, default=0)
"""
    with open(path, 'w') as f:
        f.write(content)
    print("Models updated with defaults for automatic migration.")

if __name__ == "__main__":
    fix_models_for_auto_migration()
