"""
production/mrp.py — Material Requirements Planning algoritam

MRP Run:
  1. Uzmi sve confirmed/in_progress ProductionOrder-e
  2. Za svaki, eksplodiraj BOM (recursive multi-level)
  3. Izračunaj gross requirements (ukupna potreba)
  4. Oduzmi on-hand stock → net requirements
  5. Ako net > 0:
     - Ako item ima BOM → MRPPlannedOrder type=produce
     - Ako nema BOM → MRPPlannedOrder type=purchase
  6. Za produce planove: backward scheduling (needed_by - lead_time = order_date)

Rezultat: Lista MRPPlannedOrder-a za pregled/potvrdu.
"""

import logging
from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

DEFAULT_LEAD_TIME_DAYS = 7  # Ako item nema lead_time


@transaction.atomic
def mrp_run(company, horizon_days=30, user=None):
    """
    Pokreni MRP za firmu.
    horizon_days: koliko dana unaprijed gledati
    Returns: dict with results summary + list of planned orders
    """
    from inventory.models import InventoryItem
    from production.models import (
        BillOfMaterials,
        MRPPlannedOrder,
        ProductionOrder,
    )

    run_id = f"MRP-{timezone.now().strftime('%Y%m%d-%H%M%S')}"
    date.today() + timedelta(days=horizon_days)

    # 1. Dohvati aktivne naloge koji trebaju materijal
    active_orders = ProductionOrder.objects.filter(
        company=company,
        status__in=("confirmed", "in_progress"),
    ).select_related("bom")

    if not active_orders.exists():
        return {"run_id": run_id, "planned_orders": [], "message": "Nema aktivnih naloga."}

    # 2. Izračunaj gross requirements (recursive BOM explosion)
    gross_requirements = {}  # item_id → total quantity needed

    for order in active_orders:
        multiplier = order.planned_quantity / order.bom.output_quantity
        exploded = order.bom.explode(multiplier)
        for line in exploded:
            if not line["is_subassembly"]:
                item_id = line["item"].pk
                gross_requirements[item_id] = gross_requirements.get(item_id, Decimal("0")) + line["quantity"]

    # 3. Dohvati on-hand stock
    item_ids = list(gross_requirements.keys())
    items = {i.pk: i for i in InventoryItem.objects.filter(pk__in=item_ids, company=company)}

    # 4. Net requirements = gross - on_hand
    net_requirements = {}
    for item_id, gross in gross_requirements.items():
        item = items.get(item_id)
        if not item:
            continue
        on_hand = getattr(item, "quantity", Decimal("0"))
        # Oduzmi i već planirane (nepotvrđene) naloge
        already_planned = MRPPlannedOrder.objects.filter(
            company=company,
            item=item,
            status="planned",
        ).aggregate(total=models.Sum("quantity"))["total"] or Decimal("0")

        net = gross - on_hand - already_planned
        if net > Decimal("0"):
            net_requirements[item_id] = {
                "item": item,
                "gross": gross,
                "on_hand": on_hand,
                "already_planned": already_planned,
                "net": net,
            }

    # 5. Generiraj MRPPlannedOrder za svaki net requirement
    # Obriši stare planned (nekorištene) iz prošlih runova
    MRPPlannedOrder.objects.filter(
        company=company,
        status="planned",
    ).delete()

    planned_orders = []
    for item_id, req in net_requirements.items():
        item = req["item"]
        lead_time = getattr(item, "lead_time_days", DEFAULT_LEAD_TIME_DAYS) or DEFAULT_LEAD_TIME_DAYS

        # Provjeri ima li item BOM → produce, inače → purchase
        has_bom = BillOfMaterials.objects.filter(
            company=company,
            output_item=item,
            status="active",
        ).exists()

        # Earliest needed: najraniji planned_start od aktivnih naloga koji koriste ovaj item
        needed_by = date.today() + timedelta(days=horizon_days)
        for order in active_orders:
            if order.planned_start and order.planned_start.date() < needed_by:
                needed_by = order.planned_start.date()

        order_date = needed_by - timedelta(days=lead_time)
        if order_date < date.today():
            order_date = date.today()

        bom_ref = None
        if has_bom:
            bom_ref = BillOfMaterials.objects.filter(
                company=company,
                output_item=item,
                status="active",
            ).first()

        po = MRPPlannedOrder.objects.create(
            company=company,
            item=item,
            order_type="produce" if has_bom else "purchase",
            quantity=req["net"],
            needed_by=needed_by,
            order_date=order_date,
            bom=bom_ref,
            status="planned",
            mrp_run_id=run_id,
        )
        planned_orders.append(po)

    logger.info(
        f"MRP Run {run_id}: {len(active_orders)} orders, "
        f"{len(gross_requirements)} items, {len(planned_orders)} planned orders"
    )

    return {
        "run_id": run_id,
        "active_orders": active_orders.count(),
        "items_checked": len(gross_requirements),
        "items_short": len(net_requirements),
        "planned_orders": planned_orders,
        "message": f"MRP završen: {len(planned_orders)} planiranih naloga generirano.",
    }


# Need to import models for aggregate
from django.db import models


def create_purchase_suggestions(company):
    """
    Iz MRP planned orders tipa 'purchase' generiraj purchase suggestions.
    Grupira po dobavljaču ako item ima supplier field.
    """
    from production.models import MRPPlannedOrder

    purchase_plans = MRPPlannedOrder.objects.filter(
        company=company,
        order_type="purchase",
        status="planned",
    ).select_related("item")

    suggestions = []
    for po in purchase_plans:
        item = po.item
        supplier = getattr(item, "supplier", None) or getattr(item, "default_supplier", "")
        suggestions.append(
            {
                "item": item,
                "item_name": item.name,
                "item_sku": getattr(item, "sku", ""),
                "quantity": po.quantity,
                "needed_by": po.needed_by,
                "order_date": po.order_date,
                "supplier": str(supplier) if supplier else "Nepoznat",
                "estimated_cost": po.quantity
                * (getattr(item, "purchase_price", None) or getattr(item, "unit_price", Decimal("0"))),
                "mrp_planned_order_id": str(po.pk),
            }
        )

    # Grupiraj po dobavljaču
    by_supplier = {}
    for s in suggestions:
        key = s["supplier"]
        by_supplier.setdefault(key, []).append(s)

    return {
        "suggestions": suggestions,
        "by_supplier": by_supplier,
        "total_items": len(suggestions),
        "total_cost": sum(s["estimated_cost"] for s in suggestions),
    }


def calculate_workstation_load(company, days_ahead=14):
    """
    Kapacitet planiranje — koliko je svaka radna stanica opterećena.
    """
    from production.models import ProductionStep, Workstation

    date.today() + timedelta(days=days_ahead)
    workstations = Workstation.objects.filter(company=company, status="active")

    load = []
    for ws in workstations:
        # Sati dostupnog kapaciteta (8h/dan × days_ahead)
        available_hours = 8 * days_ahead

        # Planirani sati (iz koraka na aktivnim nalozima)
        planned_minutes = (
            ProductionStep.objects.filter(
                workstation=ws,
                order__status__in=("confirmed", "in_progress"),
                status__in=("pending", "in_progress"),
            ).aggregate(total=models.Sum("estimated_minutes"))["total"]
            or 0
        )

        planned_hours = planned_minutes / 60
        utilization = (planned_hours / available_hours * 100) if available_hours else 0

        load.append(
            {
                "workstation": ws,
                "available_hours": available_hours,
                "planned_hours": round(planned_hours, 1),
                "utilization_percent": round(utilization, 1),
                "status": "overloaded"
                if utilization > 100
                else "high"
                if utilization > 80
                else "normal"
                if utilization > 30
                else "idle",
            }
        )

    return sorted(load, key=lambda x: -x["utilization_percent"])
