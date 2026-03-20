"""
Predictive reorder service for InventoryItem.

Uses average daily consumption from StockMovement (type='out')
over the last N days to predict when stock will run out and
suggest reorder quantities.

Formula:
  avg_daily = sum(out_qty over last N days) / N
  days_left = current_qty / avg_daily
  reorder_point = avg_daily * lead_time_days * safety_factor
  suggested_qty = reorder_point - current_qty  (if current < reorder_point)

Requires minimum 90 days of StockMovement data to produce
meaningful predictions. Returns 'insufficient_data' flag otherwise.
"""
from datetime import timedelta
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone


# Configurable defaults
MIN_DATA_DAYS = 90       # Minimum days of movement history required
LOOKBACK_DAYS = 90       # Days to look back for avg consumption
LEAD_TIME_DAYS = 7       # Default supplier lead time
SAFETY_FACTOR = Decimal('1.5')  # Safety stock multiplier


def predict_reorder(item, lookback_days=LOOKBACK_DAYS, lead_time_days=LEAD_TIME_DAYS,
                    safety_factor=SAFETY_FACTOR):
    """
    Predict reorder needs for a single InventoryItem.

    Returns dict with:
      - insufficient_data: bool
      - avg_daily: Decimal (avg daily consumption)
      - days_left: int or None
      - reorder_point: Decimal
      - suggested_qty: Decimal
      - urgency: 'critical' | 'warning' | 'ok'
    """
    from inventory.models import StockMovement

    now = timezone.now()
    cutoff = now - timedelta(days=lookback_days)

    # Check data span
    movements = StockMovement.objects.filter(
        item=item,
        movement_type='out',
        created_at__gte=cutoff,
    )

    first_movement = StockMovement.objects.filter(
        item=item,
        movement_type='out',
    ).order_by('created_at').first()

    if not first_movement:
        return {
            'insufficient_data': True,
            'reason': 'Nema izlaznih kretanja za ovaj artikl.',
            'avg_daily': Decimal('0'),
            'days_left': None,
            'reorder_point': Decimal('0'),
            'suggested_qty': Decimal('0'),
            'urgency': 'ok',
        }

    data_span = (now - first_movement.created_at).days
    if data_span < MIN_DATA_DAYS:
        return {
            'insufficient_data': True,
            'reason': f'Nedovoljno podataka ({data_span} dana, potrebno min. {MIN_DATA_DAYS}).',
            'avg_daily': Decimal('0'),
            'days_left': None,
            'reorder_point': Decimal('0'),
            'suggested_qty': Decimal('0'),
            'urgency': 'ok',
        }

    # Compute average daily consumption
    total_out = movements.aggregate(total=Sum('quantity'))['total'] or Decimal('0')
    actual_days = max((now - cutoff).days, 1)
    avg_daily = total_out / actual_days

    if avg_daily <= 0:
        return {
            'insufficient_data': False,
            'avg_daily': Decimal('0'),
            'days_left': None,
            'reorder_point': Decimal('0'),
            'suggested_qty': Decimal('0'),
            'urgency': 'ok',
        }

    # Predictions
    current_qty = item.quantity
    days_left = int(current_qty / avg_daily) if avg_daily > 0 else None
    reorder_point = avg_daily * lead_time_days * safety_factor
    suggested_qty = max(reorder_point - current_qty, Decimal('0'))

    # Urgency
    if current_qty <= 0:
        urgency = 'critical'
    elif days_left is not None and days_left <= lead_time_days:
        urgency = 'critical'
    elif days_left is not None and days_left <= lead_time_days * 2:
        urgency = 'warning'
    else:
        urgency = 'ok'

    return {
        'insufficient_data': False,
        'avg_daily': avg_daily.quantize(Decimal('0.01')),
        'days_left': days_left,
        'reorder_point': reorder_point.quantize(Decimal('0.01')),
        'suggested_qty': suggested_qty.quantize(Decimal('0.01')),
        'urgency': urgency,
    }


def reorder_report(company, top_n=20):
    """
    Generate reorder report for a company.
    Returns list of items needing attention, sorted by urgency.
    """
    from inventory.models import InventoryItem

    items = InventoryItem.objects.filter(company=company)

    results = []
    insufficient_count = 0

    for item in items:
        prediction = predict_reorder(item)
        if prediction['insufficient_data']:
            insufficient_count += 1
            continue
        if prediction['urgency'] in ('critical', 'warning'):
            results.append({
                'item': item,
                **prediction,
            })

    # Sort: critical first, then warning, then by days_left ascending
    urgency_order = {'critical': 0, 'warning': 1, 'ok': 2}
    results.sort(key=lambda r: (urgency_order[r['urgency']], r['days_left'] or 999))

    return {
        'items': results[:top_n],
        'total_items': items.count(),
        'insufficient_count': insufficient_count,
        'has_enough_data': insufficient_count < items.count(),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# PREDICTIVE ANALYTICS ENGINE — Phase 2
# Weighted moving average demand prediction + Auto PO generation
# ═══════════════════════════════════════════════════════════════════════════════

def predict_weekly_demand(item, weeks_ahead=2):
    """
    Predict demand for the next N weeks using weighted moving average.
    Gives more weight to recent weeks (2x for last 45 days).
    Returns dict with daily avg, weekly demand, stockout prediction.
    """
    from inventory.models import StockMovement
    from django.db.models import Sum

    now = timezone.now()
    lookback = now - timedelta(days=90)

    # Get daily outflows
    daily_out = (
        StockMovement.objects.filter(
            item=item,
            movement_type='out',
            created_at__gte=lookback,
        )
        .extra(select={'day': 'DATE(created_at)'})
        .values('day')
        .annotate(total=Sum('quantity'))
        .order_by('day')
    )

    if not daily_out:
        return None

    # Calculate weighted average (recent days get 2x weight)
    mid_point = now - timedelta(days=45)
    total_weighted = Decimal('0')
    total_weight = Decimal('0')

    for entry in daily_out:
        from datetime import datetime as _dt
        day = entry['day']
        if isinstance(day, str):
            day = _dt.strptime(day, '%Y-%m-%d').date()
        weight = Decimal('2') if day >= mid_point.date() else Decimal('1')
        total_weighted += abs(entry['total']) * weight
        total_weight += weight

    if total_weight == 0:
        return None

    # Count actual days in period
    first_movement = StockMovement.objects.filter(
        item=item, movement_type='out', created_at__gte=lookback,
    ).order_by('created_at').first()

    if not first_movement:
        return None

    actual_days = (now.date() - first_movement.created_at.date()).days or 1
    avg_daily = total_weighted / Decimal(str(actual_days))

    weekly_demand = avg_daily * 7

    return {
        'avg_daily': round(avg_daily, 2),
        'weekly_demand': round(weekly_demand, 2),
        'predicted_demand': round(weekly_demand * weeks_ahead, 2),
        'weeks_ahead': weeks_ahead,
        'current_stock': item.quantity,
        'days_of_stock': int(item.quantity / avg_daily) if avg_daily > 0 else 999,
        'will_stockout': item.quantity < (weekly_demand * weeks_ahead),
        'stockout_date': (now + timedelta(days=int(item.quantity / avg_daily))).date() if avg_daily > 0 else None,
    }


def generate_draft_po(company, supplier=None, items=None):
    """
    Auto-generate draft PurchaseOrder(s) based on reorder predictions.
    Groups items by supplier. Uses SupplierPriceList for pricing.

    Args:
        company: Company instance
        supplier: Optional — filter to a specific supplier
        items: Optional list of dicts with item_id, suggested_qty (or item objects)

    Returns list of created PurchaseOrder PKs.
    """
    from inventory.models import InventoryItem
    from procurement.models import PurchaseOrder, PurchaseOrderItem, SupplierPriceList
    from django.db.models import Q

    today = timezone.now().date()
    created_pos = []

    # Get items needing reorder
    if items is None:
        report = reorder_report(company, top_n=50)
        items_to_order = [
            r for r in report['items']
            if r['urgency'] in ('critical', 'warning') and r.get('suggested_qty', Decimal('0')) > 0
        ]
    else:
        items_to_order = items

    if not items_to_order:
        return created_pos

    # Group by supplier
    by_supplier = {}
    for r in items_to_order:
        # Support both dict (from reorder_report) and raw item objects
        if isinstance(r, dict):
            item_id = r.get('item_id') or (r['item'].pk if 'item' in r and hasattr(r['item'], 'pk') else None)
            if not item_id:
                continue
            try:
                item = InventoryItem.objects.get(pk=item_id, company=company)
            except InventoryItem.DoesNotExist:
                try:
                    item = InventoryItem.objects.get(pk=item_id)
                except InventoryItem.DoesNotExist:
                    continue
            suggested = Decimal(str(r.get('suggested_qty', r.get('reorder_point', 10))))
        else:
            item = r
            suggested = Decimal('10')

        sup = item.supplier
        if supplier and sup != supplier:
            continue
        if not sup:
            continue

        if sup.pk not in by_supplier:
            by_supplier[sup.pk] = {'supplier': sup, 'items': []}
        by_supplier[sup.pk]['items'].append({
            'item': item,
            'qty': suggested,
        })

    # Create PO per supplier
    for sup_id, data in by_supplier.items():
        sup = data['supplier']
        po = PurchaseOrder(
            company=company,
            supplier=sup,
            status='draft',
            priority='normal',
            order_date=today,
            expected_delivery=today + timedelta(days=7),
            notes=f'Automatski generirano \u2014 Prediktivna analiza {today:%d.%m.%Y}',
        )
        po.po_number = po.generate_po_number()
        po.save()

        for entry in data['items']:
            item = entry['item']
            qty = entry['qty']

            # Try to get price from SupplierPriceList
            price_entry = SupplierPriceList.objects.filter(
                company=company,
                supplier=sup,
                inventory_item=item,
                valid_from__lte=today,
            ).filter(
                Q(valid_until__isnull=True) | Q(valid_until__gte=today)
            ).order_by('-valid_from').first()

            unit_price = price_entry.agreed_price if price_entry else (item.purchase_price or Decimal('0'))

            PurchaseOrderItem.objects.create(
                purchase_order=po,
                inventory_item=item,
                description=item.name,
                sku=item.sku or '',
                quantity=qty,
                unit=item.unit or 'kom',
                unit_price=unit_price,
                tax_rate=Decimal('25.00'),
            )

        po.recalculate()
        created_pos.append(po.pk)

    return created_pos
