# CC_TASK_PROD_4_INVENTORY_INTEGRATION.md
# PRODUCTION MODULE — TASK 4: Inventory Integration + Signals + BOM Cost Engine
# Agent: Gemini / CC Code #4
# ČEKA: Task 1 DONE
# Piše: production/signals.py + production/services.py

---

## CILJ
Automatska integracija s inventory modulom pri završetku proizvodnog naloga:
1. Sirovina → StockMovement OUT (smanjenje zaliha)
2. Gotov proizvod → StockMovement IN (povećanje zalihe)
3. Trošak materijala → kalkulacija iz inventory cijena
4. Provjera dostupnosti PRIJE pokretanja naloga

---

## TASK 4A — production/services.py (poslovni sloj)

```python
"""
production/services.py
Poslovni servis za MRP — centralizirana logika, ne u modelima ni views.
"""
from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.utils import timezone


class BOMCostEngine:
    """
    Kalkulira trošak BOM-a baziran na trenutnim inventory cijenama.
    Metode su pure (bez side-efekata) — samo čitaju, ne mijenjaju DB.
    """

    @staticmethod
    def calculate_bom_cost(bom, quantity=None):
        """
        Izračunaj ukupni trošak sirovina za BOM za zadanu količinu.
        quantity=None → koristi bom.yield_quantity (trošak jedne serije).
        
        Returns:
            {
                'lines': [{'material_name', 'planned_qty', 'unit_cost', 'total_cost'}, ...],
                'total_material_cost': Decimal,
                'cost_per_unit': Decimal,
                'shortages': [{'material_name', 'available', 'needed'}],  # ako nema dovoljno
            }
        """
        quantity = quantity or bom.yield_quantity
        total_cost = Decimal('0')
        lines = []
        shortages = []

        for line in bom.lines.select_related('material').all():
            needed = (line.quantity_with_scrap * quantity / bom.yield_quantity).quantize(
                Decimal('0.001'), rounding=ROUND_HALF_UP
            )
            # Nabavna cijena: inventory purchase_price ili 0
            unit_cost = getattr(line.material, 'purchase_price', Decimal('0')) or Decimal('0')
            line_cost = (needed * unit_cost).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            total_cost += line_cost
            lines.append({
                'material': line.material,
                'material_name': line.material.name,
                'planned_qty': needed,
                'unit': line.unit,
                'unit_cost': unit_cost,
                'total_cost': line_cost,
            })
            # Provjeri dostupnost
            available = getattr(line.material, 'quantity', Decimal('0')) or Decimal('0')
            if available < needed:
                shortages.append({
                    'material_name': line.material.name,
                    'available': available,
                    'needed': needed,
                    'deficit': needed - available,
                })

        cost_per_unit = (total_cost / quantity).quantize(
            Decimal('0.0001'), rounding=ROUND_HALF_UP
        ) if quantity else Decimal('0')

        return {
            'lines': lines,
            'total_material_cost': total_cost,
            'cost_per_unit': cost_per_unit,
            'shortages': shortages,
            'has_shortages': bool(shortages),
        }


class ProductionInventoryService:
    """
    Sve interakcije između production i inventory modula.
    JEDINO MJESTO gdje se diraju inventory zalihe iz production.
    """

    @staticmethod
    @transaction.atomic
    def deduct_materials(order):
        """
        Poziva se pri completion naloga.
        Za svaku ProductionOrderLine:
          - Provjeri stock_deducted flag
          - Kreiraj StockMovement OUT
          - Smanji inventory.quantity
          - Postavi line.stock_deducted = True
        
        Returns: {'success': bool, 'movements': [...], 'errors': [...]}
        """
        from inventory.models import InventoryItem, StockMovement

        movements = []
        errors = []

        for line in order.lines.select_for_update().filter(stock_deducted=False):
            material = line.material
            qty_to_deduct = line.actual_quantity or line.planned_quantity

            if material.quantity < qty_to_deduct:
                errors.append(
                    f"{material.name}: dostupno {material.quantity}, potrebno {qty_to_deduct}"
                )
                continue  # Ne stopaj — deduciraj što možeš, prijavi greške

            # StockMovement OUT
            movement = StockMovement.objects.create(
                company=order.company,
                item=material,
                movement_type='out',
                quantity=qty_to_deduct,
                reason='production',
                reference=order.order_number,
                notes=f'Potrošak za nalog {order.order_number}',
                performed_by=None,  # system
            )
            movements.append(movement)

            # Smanji zalihu
            material.quantity = material.quantity - qty_to_deduct
            material.save(update_fields=['quantity', 'updated_at'])

            # Označi kao razduženo
            line.actual_quantity = qty_to_deduct
            line.stock_deducted = True
            unit_cost = material.purchase_price or Decimal('0')
            line.unit_cost = unit_cost
            line.total_cost = (qty_to_deduct * unit_cost).quantize(Decimal('0.01'))
            line.save(update_fields=['actual_quantity','stock_deducted','unit_cost','total_cost'])

        return {
            'success': len(errors) == 0,
            'movements': movements,
            'errors': errors,
        }

    @staticmethod
    @transaction.atomic
    def add_finished_goods(order):
        """
        Poziva se pri completion naloga.
        Dodaj actual_quantity gotovog proizvoda u inventory.
        StockMovement IN za gotov proizvod.
        """
        from inventory.models import InventoryItem, StockMovement

        product = order.product
        qty = order.actual_quantity

        if not qty or qty <= 0:
            return {'success': False, 'error': 'actual_quantity nije postavljen'}

        # StockMovement IN
        movement = StockMovement.objects.create(
            company=order.company,
            item=product,
            movement_type='in',
            quantity=qty,
            reason='production',
            reference=order.order_number,
            notes=f'Gotov proizvod iz naloga {order.order_number}',
        )

        # Povećaj zalihu gotovog proizvoda
        product.quantity = (product.quantity or Decimal('0')) + qty
        product.save(update_fields=['quantity', 'updated_at'])

        return {'success': True, 'movement': movement}

    @staticmethod
    def check_material_availability(order):
        """
        Provjeri da li ima dovoljno materijala PRIJE pokretanja naloga.
        Poziva se u order_plan view-u.
        Returns: {'available': bool, 'shortages': [...]}
        """
        shortages = []
        for line in order.lines.select_related('material').all():
            needed = line.planned_quantity
            available = line.material.quantity or Decimal('0')
            if available < needed:
                shortages.append({
                    'material': line.material.name,
                    'available': available,
                    'needed': needed,
                    'deficit': needed - available,
                    'unit': line.unit,
                })
        return {'available': len(shortages) == 0, 'shortages': shortages}


class ProductionCostService:
    """
    Agregacija i kalkulacija troškova po nalogu.
    """

    @staticmethod
    @transaction.atomic
    def recalculate_order_costs(order):
        """
        Zbroji sve ProductionCost i ProductionOrderLine troškove.
        Postavi order.cost_materials, cost_labor, cost_overhead, cost_total, cost_per_unit.
        """
        from production.models import ProductionCost

        # Materijalni troškovi iz linija
        from django.db.models import Sum
        mat_cost = order.lines.aggregate(t=Sum('total_cost'))['t'] or Decimal('0')

        # Ručno dodani troškovi
        costs = order.costs.values('cost_type').annotate(t=Sum('total_cost'))
        cost_map = {c['cost_type']: c['t'] or Decimal('0') for c in costs}

        labor    = cost_map.get('labor',    Decimal('0'))
        overhead = cost_map.get('overhead', Decimal('0'))
        other    = cost_map.get('other',    Decimal('0'))

        total = (mat_cost + labor + overhead + other).quantize(Decimal('0.01'))
        per_unit = (total / order.actual_quantity).quantize(
            Decimal('0.0001')
        ) if order.actual_quantity else Decimal('0')

        order.cost_materials = mat_cost.quantize(Decimal('0.01'))
        order.cost_labor     = labor.quantize(Decimal('0.01'))
        order.cost_overhead  = (overhead + other).quantize(Decimal('0.01'))
        order.cost_total     = total
        order.cost_per_unit  = per_unit
        order.save(update_fields=[
            'cost_materials','cost_labor','cost_overhead','cost_total','cost_per_unit'
        ])
        return total


class MRPPlanner:
    """
    Jednostavni MRP kalkulator — simulira potrebe bez kreiranja naloga.
    Ulaz: lista (product, quantity). Izlaz: agregirana lista sirovina.
    """

    @staticmethod
    def calculate_requirements(requirements_list):
        """
        requirements_list = [{'product_id': 1, 'quantity': 100}, ...]
        Returns: {
            'material_requirements': [{'material', 'needed', 'available', 'to_order'}],
            'missing_boms': [product_id, ...],
        }
        """
        from production.models import BillOfMaterials
        from inventory.models import InventoryItem

        aggregated = {}  # material_id → needed qty
        missing_boms = []

        for req in requirements_list:
            try:
                bom = BillOfMaterials.objects.filter(
                    product_id=req['product_id'], is_active=True
                ).first()
                if not bom:
                    missing_boms.append(req['product_id'])
                    continue

                qty = Decimal(str(req['quantity']))
                for line in bom.lines.select_related('material').all():
                    needed = line.quantity_with_scrap * qty / bom.yield_quantity
                    mat_id = line.material_id
                    aggregated[mat_id] = aggregated.get(mat_id, Decimal('0')) + needed

            except Exception:
                missing_boms.append(req.get('product_id'))

        result = []
        for mat_id, needed in aggregated.items():
            try:
                mat = InventoryItem.objects.get(pk=mat_id)
                available = mat.quantity or Decimal('0')
                to_order = max(Decimal('0'), needed - available)
                result.append({
                    'material': mat.name,
                    'material_id': mat_id,
                    'needed': needed.quantize(Decimal('0.001')),
                    'available': available,
                    'to_order': to_order.quantize(Decimal('0.001')),
                    'unit': mat.unit,
                    'shortage': to_order > 0,
                })
            except InventoryItem.DoesNotExist:
                pass

        return {
            'material_requirements': sorted(result, key=lambda x: x['shortage'], reverse=True),
            'missing_boms': missing_boms,
        }
```

---

## TASK 4B — production/signals.py

```python
"""
production/signals.py
Signal: production_order_completed → deduciraj materijale, dodaj gotov proizvod
"""
from django.db.models.signals import post_save
from django.dispatch import receiver, Signal
from django.contrib import messages

# Custom signal (koristi se iz views.py)
production_order_completed = Signal()  # sending_args: order, request

@receiver(production_order_completed)
def handle_order_completion(sender, order, request=None, **kwargs):
    """
    Trigger pri order_complete view-u.
    Redoslijed: 1. deduct materials, 2. add finished goods, 3. recalculate costs
    """
    from production.services import (
        ProductionInventoryService as PIS,
        ProductionCostService as PCS,
    )
    import logging
    logger = logging.getLogger('production')

    # 1. Razduži sirovine
    result = PIS.deduct_materials(order)
    if result['errors']:
        logger.warning(f'Order {order.order_number} — inventory errors: {result["errors"]}')

    # 2. Dodaj gotov proizvod
    finished = PIS.add_finished_goods(order)
    if not finished['success']:
        logger.error(f'Order {order.order_number} — cannot add finished goods: {finished.get("error")}')

    # 3. Rekalkuliraj troškove
    PCS.recalculate_order_costs(order)

    logger.info(f'Order {order.order_number} completed. Inventory updated.')
```

U `views.py` order_complete view, nakon `transition_to('completed')`:
```python
from production.signals import production_order_completed
production_order_completed.send(sender=ProductionOrder, order=order, request=request)
```

---

## TASK 4C — production/inventory_utils.py

```python
def get_material_price(inventory_item):
    """
    Dohvati cijenu materijala za troškovnik.
    Prioritet: purchase_price → last_cost → 0
    """

def check_stock_before_start(order):
    """
    Vraća (can_start: bool, warnings: list).
    Warning (ne blocker) ako je dostupna količina < 110% potrebnog.
    """
```

---

## PROVJERA USPJEHA

```bash
cd /var/www/fina-connect && venv/bin/python -c "
import django; django.setup()
from production.services import BOMCostEngine, ProductionInventoryService, MRPPlanner
print('Services OK')
from production.signals import production_order_completed
print('Signals OK')
"
```

Kad završiš: `echo "TASK4_DONE" >> /var/www/fina-connect/PROD_BUILD_STATUS.txt`
