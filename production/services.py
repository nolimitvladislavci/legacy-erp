"""
production/services.py — Inventory integration + cost accounting

Atomične operacije:
  consume_materials()  — oduzmi sirovine iz inventara (select_for_update)
  produce_output()     — dodaj gotov proizvod u inventar
  calculate_costs()    — izračunaj material + labor + overhead cost
  check_availability() — provjeri ima li dovoljno sirovina
"""

import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .models import ProductionOrder, ProductionLog

logger = logging.getLogger(__name__)


def check_availability(order):
    """
    Provjeri dostupnost svih materijala za radni nalog.
    Returns: list of dicts with item, required, available, sufficient
    """
    requirements = order.calculate_material_requirements()
    result = []
    all_ok = True
    for req in requirements:
        item = req['item']
        available = Decimal(str(getattr(item, 'quantity', 0)))
        required = req['required']
        sufficient = available >= required
        if not sufficient:
            all_ok = False
        result.append({
            'item': item,
            'item_name': item.name,
            'item_sku': getattr(item, 'sku', ''),
            'required': required,
            'available': available,
            'missing': max(Decimal('0'), required - available),
            'sufficient': sufficient,
            'unit': req['unit'],
        })
    return result, all_ok


@transaction.atomic
def consume_materials(order, user=None):
    """
    Oduzmi sirovine iz inventara za radni nalog.
    Koristi select_for_update za race condition zaštitu.
    """
    from inventory.models import InventoryItem

    if order.status not in ('confirmed', 'in_progress'):
        raise ValueError(f'Nalog {order.order_number} nije u statusu za utrošak materijala')

    multiplier = order.planned_quantity / order.bom.output_quantity
    consumed = []

    for line in order.bom.lines.select_related('item').all():
        qty_needed = line.effective_quantity * multiplier

        # Lock the item row
        item = InventoryItem.objects.select_for_update().get(pk=line.item_id)
        old_stock = item.quantity

        if item.quantity < qty_needed:
            raise ValueError(
                f'Nedovoljno {item.name}: potrebno {qty_needed}, dostupno {item.quantity}'
            )

        item.quantity -= qty_needed
        item.save(update_fields=['quantity'])

        # Create StockMovement transaction
        from inventory.models import StockMovement
        StockMovement.objects.create(
            company=order.company,
            item=item,
            movement_type='consumption',
            quantity=-qty_needed,
            unit=line.unit,
            stock_before=old_stock,
            stock_after=item.quantity,
            production_order=order,
            batch_number=order.batch_number,
            reference=f'Utrošak za RN {order.order_number}',
            performed_by=user,
        )

        consumed.append({
            'item_id': str(item.pk),
            'item_name': item.name,
            'quantity': float(qty_needed),
            'old_stock': float(old_stock),
            'new_stock': float(item.quantity),
        })

    # Log
    ProductionLog.objects.create(
        order=order,
        action='material_consumed',
        description=f'Utrošeno {len(consumed)} materijala za {order.planned_quantity} {order.bom.output_unit}',
        metadata={'consumed': consumed},
        user=user,
    )

    logger.info(f'Materials consumed for {order.order_number}: {len(consumed)} items')
    return consumed


@transaction.atomic
def produce_output(order, quantity, user=None):
    """
    Dodaj gotov proizvod u inventar.
    """
    from inventory.models import InventoryItem

    output_item = InventoryItem.objects.select_for_update().get(
        pk=order.bom.output_item_id
    )
    old_stock = output_item.quantity
    output_item.quantity += quantity
    output_item.save(update_fields=['quantity'])

    # Create StockMovement transaction
    from inventory.models import StockMovement
    StockMovement.objects.create(
        company=order.company,
        item=output_item,
        movement_type='production',
        quantity=quantity,
        unit=order.bom.output_unit,
        stock_before=old_stock,
        stock_after=output_item.quantity,
        production_order=order,
        batch_number=order.batch_number,
        reason=f'Proizvedeno iz RN {order.order_number}',
        performed_by=user,
    )

    order.produced_quantity += quantity
    if order.status == 'confirmed':
        order.status = 'in_progress'
        order.actual_start = order.actual_start or timezone.now()
    order.save(update_fields=['produced_quantity', 'status', 'actual_start'])

    ProductionLog.objects.create(
        order=order,
        action='produced',
        quantity=quantity,
        description=f'+{quantity} {order.bom.output_unit} {output_item.name} (stock: {old_stock}→{output_item.quantity})',
        metadata={
            'item_id': str(output_item.pk),
            'old_stock': float(old_stock),
            'new_stock': float(output_item.quantity),
        },
        user=user,
    )
    return output_item


def calculate_costs(order):
    """
    Izračunaj troškove radnog naloga.
    Material cost = BOM unit cost × planned quantity
    Labor cost = actual minutes × workstation hourly rate / 60
    Overhead = 15% material + labor (default, configurable)
    """
    # Material
    multiplier = order.planned_quantity / order.bom.output_quantity
    material_cost = order.bom.total_material_cost * multiplier

    # Labor — from steps
    labor_cost = Decimal('0')
    for step in order.steps.all():
        if step.actual_minutes and step.workstation:
            labor_cost += (Decimal(step.actual_minutes) / 60) * step.workstation.hourly_cost

    # If no steps but workstation on order
    if not labor_cost and order.workstation:
        total_minutes = sum(s.actual_minutes or s.estimated_minutes for s in order.steps.all())
        if not total_minutes:
            total_minutes = order.bom.estimated_duration_minutes
        if total_minutes:
            labor_cost = (Decimal(total_minutes) / 60) * order.workstation.hourly_cost

    # Overhead — 15% default
    overhead = (material_cost + labor_cost) * Decimal('0.15')

    order.material_cost = material_cost.quantize(Decimal('0.01'))
    order.labor_cost = labor_cost.quantize(Decimal('0.01'))
    order.overhead_cost = overhead.quantize(Decimal('0.01'))

    # Planned costs (za variance) — iz BOM-a
    if not order.planned_material_cost:
        bom_cost = order.bom.total_material_cost * (order.planned_quantity / order.bom.output_quantity)
        planned_labor = Decimal('0')
        if order.workstation and order.bom.estimated_duration_minutes:
            planned_labor = (Decimal(order.bom.estimated_duration_minutes) / 60) * order.workstation.hourly_cost
        planned_overhead = (bom_cost + planned_labor) * Decimal('0.15')
        order.planned_material_cost = bom_cost.quantize(Decimal('0.01'))
        order.planned_labor_cost = planned_labor.quantize(Decimal('0.01'))
        order.planned_total_cost = (bom_cost + planned_labor + planned_overhead).quantize(Decimal('0.01'))

    order.save(update_fields=[
        'material_cost', 'labor_cost', 'overhead_cost',
        'planned_material_cost', 'planned_labor_cost', 'planned_total_cost',
    ])

    ProductionLog.objects.create(
        order=order,
        action='cost_updated',
        description=f'Mat: {order.material_cost}€, Rad: {order.labor_cost}€, Režija: {order.overhead_cost}€ = {order.total_cost}€',
        metadata={
            'material': float(order.material_cost),
            'labor': float(order.labor_cost),
            'overhead': float(order.overhead_cost),
            'total': float(order.total_cost),
        },
    )
    return order
