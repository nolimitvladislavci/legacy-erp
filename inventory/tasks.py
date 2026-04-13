"""
Celery tasks for predictive inventory reorder pipeline.
Runs daily at 05:00, checks all companies, generates reorder predictions,
and auto-creates DRAFT PurchaseOrders grouped by supplier.
"""
import logging
from celery import shared_task
from decimal import Decimal
from django.core.exceptions import ObjectDoesNotExist

logger = logging.getLogger('inventory.predictive')


@shared_task(bind=True, max_retries=2, retry_backoff=True)
def predictive_reorder_check(self):
    """Daily check: predict stock needs and auto-generate draft POs."""
    from companies.models import Company
    from inventory.reorder import predict_reorder
    from inventory.models import InventoryItem
    from procurement.models import PurchaseOrder, PurchaseOrderItem, SupplierPriceList
    from partners.models import Partner
    from notifications.services import notify
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from django.db.models import Q
    from datetime import timedelta

    User = get_user_model()
    results = []

    for company in Company.objects.all():
        try:
            # Get items that have a supplier AND are active
            items = InventoryItem.objects.filter(
                company=company,
                is_active=True,
                supplier__isnull=False,
            )

            # Group reorder needs by supplier
            supplier_orders = {}  # supplier_id -> [(item, prediction)]

            for item in items:
                pred = predict_reorder(item)
                if pred.get('insufficient_data'):
                    continue
                if pred.get('urgency') in ('critical', 'warning'):
                    supplier_id = item.supplier_id
                    if supplier_id not in supplier_orders:
                        supplier_orders[supplier_id] = []
                    supplier_orders[supplier_id].append((item, pred))

            # Create draft POs per supplier
            pos_created = 0
            for supplier_id, items_preds in supplier_orders.items():
                supplier = Partner.objects.get(id=supplier_id)

                # Check if there's already a draft PO for this supplier
                existing = PurchaseOrder.objects.filter(
                    company=company,
                    supplier=supplier,
                    status='draft',
                    notes__contains='[AUTO-REORDER]',
                ).first()

                if existing:
                    continue  # Don't duplicate

                # Generate PO number
                now = timezone.now()
                year = now.year
                last_po = PurchaseOrder.objects.filter(
                    company=company,
                    po_number__startswith=f'PO-{year}-',
                ).order_by('-po_number').first()

                if last_po:
                    try:
                        last_num = int(last_po.po_number.split('-')[-1])
                    except (ValueError, IndexError):
                        last_num = 0
                    next_num = last_num + 1
                else:
                    next_num = 1

                po_number = f'PO-{year}-{next_num:04d}'

                # Build item descriptions
                item_names = [ip[0].name for ip in items_preds[:5]]
                notes = (
                    f'[AUTO-REORDER] Automatski generirano na temelju prediktivne analize.\n'
                    f'Artikli s kritičnom/upozorenom zalihom: PLACEHOLDER'
                )

                po = PurchaseOrder.objects.create(
                    company=company,
                    po_number=po_number,
                    supplier=supplier,
                    status='draft',
                    priority='high' if any(ip[1]['urgency'] == 'critical' for ip in items_preds) else 'normal',
                    order_date=now.date(),
                    expected_delivery=now.date() + timedelta(days=7),
                    notes=notes,
                )

                # Add line items
                for item, pred in items_preds:
                    qty = Decimal(str(pred.get('suggested_qty', 0)))
                    if qty <= 0:
                        qty = item.min_quantity or Decimal('1')

                    # Check supplier price list
                    price = item.purchase_price or Decimal('0')
                    price_list = SupplierPriceList.objects.filter(
                        supplier=supplier,
                        inventory_item=item,
                        valid_from__lte=now.date(),
                    ).filter(
                        Q(valid_until__isnull=True) | Q(valid_until__gte=now.date())
                    ).first()
                    if price_list:
                        price = price_list.agreed_price

                    PurchaseOrderItem.objects.create(
                        purchase_order=po,
                        inventory_item=item,
                        description=item.name,
                        sku=item.sku or '',
                        quantity=qty,
                        unit=item.unit or 'kom',
                        unit_price=price,
                        tax_rate=Decimal('25.00'),
                    )

                po.recalculate()
                pos_created += 1

            # Notify company admins
            if pos_created > 0 or supplier_orders:
                total_critical = sum(
                    1 for items_preds in supplier_orders.values()
                    for _, p in items_preds if p['urgency'] == 'critical'
                )
                total_warning = sum(
                    1 for items_preds in supplier_orders.values()
                    for _, p in items_preds if p['urgency'] == 'warning'
                )

                admins = User.objects.filter(company=company, is_staff=True)[:3]

                for admin in admins:
                    notify(
                        recipient=admin,
                        notification_type='system',
                        title='\U0001f4e6 Prediktivna analiza zaliha',
                        message=f'{total_critical} kritičnih, {total_warning} upozorenja. Generirano {pos_created} nacrt-narudžbenica.',
                        url='/procurement/',
                        company=company,
                    )

            results.append({
                'company': company.name,
                'items_checked': items.count(),
                'critical': sum(1 for sp in supplier_orders.values() for _, p in sp if p['urgency'] == 'critical'),
                'warning': sum(1 for sp in supplier_orders.values() for _, p in sp if p['urgency'] == 'warning'),
                'pos_created': pos_created,
            })

            logger.info(f'Predictive reorder for {company.name}: {pos_created} POs created')

        except ObjectDoesNotExist as e:
            logger.error(f'Predictive reorder failed for {company.name}: {e}', exc_info=True)
            results.append({'company': company.name, 'status': 'error', 'error': str(e)})

    return results


@shared_task(name='inventory.tasks.depreciation_monthly_check')
def depreciation_monthly_check():
    """Svaki 1. u mjesecu — provjeri assete i šalje Mariji WhatsApp nacrt amortizacije."""
    from inventory.depreciation import check_depreciation_reminders
    count = check_depreciation_reminders()
    return {'checked_assets': count}
