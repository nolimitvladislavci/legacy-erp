from django.db import models
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


# ─── BOM / Bill of Materials ──────────────────────────────────────────────────

class BOM(models.Model):
    """Sastavnica materijala (normativ za InventoryItem)."""
    from django.contrib.auth.models import User as _User
    company         = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        null=True, blank=True, verbose_name=_('Tvrtka'),
    )
    article         = models.ForeignKey(
        'inventory.InventoryItem', on_delete=models.CASCADE,
        related_name='bom_set', verbose_name=_('Artikl (gotov proizvod)'),
    )
    name            = models.CharField(max_length=200, blank=True, verbose_name=_('Naziv BOM-a'))
    yield_quantity  = models.DecimalField(
        max_digits=10, decimal_places=3, default=1,
        verbose_name=_('Prinos (kom gotovog proizvoda)'),
    )
    is_active       = models.BooleanField(default=True, verbose_name=_('Aktivan'))
    notes           = models.TextField(blank=True, verbose_name=_('Napomene'))
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = _('Sastavnica (BOM)')
        verbose_name_plural = _('Sastavnice (BOM)')
        ordering            = ['article__name']

    def __str__(self):
        return self.name or f'BOM — {self.article.name}'

    def total_material_cost(self):
        """Sum of (material.purchase_price * quantity) for all items."""
        from decimal import Decimal
        total = Decimal('0')
        for item in self.items.select_related('material').all():
            price = item.material.purchase_price if item.material else Decimal('0')
            waste_factor = Decimal('1') + item.waste_percent / Decimal('100')
            total += price * item.quantity * waste_factor
        return total.quantize(Decimal('0.01'))


class BOMItem(models.Model):
    """Jedna komponenta sastavnice."""
    bom             = models.ForeignKey(
        BOM, on_delete=models.CASCADE,
        related_name='items', verbose_name=_('Sastavnica'),
    )
    material        = models.ForeignKey(
        'inventory.InventoryItem', on_delete=models.CASCADE,
        related_name='used_in_boms', verbose_name=_('Materijal/Komponenta'),
    )
    quantity        = models.DecimalField(
        max_digits=10, decimal_places=4, default=1,
        verbose_name=_('Količina'),
    )
    unit            = models.CharField(max_length=20, default='kom', verbose_name=_('JMJ'))
    waste_percent   = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        verbose_name=_('Otpad (%)'),
    )

    class Meta:
        verbose_name        = _('Stavka BOM-a')
        verbose_name_plural = _('Stavke BOM-a')
        ordering            = ['id']

    def __str__(self):
        return f'{self.material.name} × {self.quantity} {self.unit}'

    @property
    def net_quantity(self):
        """Quantity including waste."""
        from decimal import Decimal
        return self.quantity * (Decimal('1') + self.waste_percent / Decimal('100'))
