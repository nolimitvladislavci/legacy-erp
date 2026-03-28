"""
marketplace/services/inventory_audit.py — Audit log za inventar vs marketplace.

Problem: Tko je tocno "pojeo" jaja koja su trebala ici na Burzu?
Rjesenje: Svaka promjena zalihe (prodaja, interna potrosnja, otpis) se bilježi
s jasnim razlogom i vezom na source (POS bon, Marketplace order, ručni otpis).

Usage:
    from marketplace.services.inventory_audit import log_stock_change
    log_stock_change(item, qty=-10, reason='marketplace_sale', order=order, user=request.user)
    log_stock_change(item, qty=-5, reason='internal_consumption', user=request.user, note='Fritaja za rucak')
"""
import logging
from decimal import Decimal

from django.utils import timezone

logger = logging.getLogger('inventory')

# Razlozi za promjenu zalihe
REASON_CHOICES = {
    'marketplace_sale':       'Prodaja na Marketplace tržnici',
    'pos_sale':               'Prodaja na POS blagajni',
    'internal_consumption':   'Interna potrošnja (vlastita kuhinja)',
    'gastro_bridge':          'Prebačeno u gastro meni (Last Call)',
    'expired':                'Istekao rok — otpis',
    'damaged':                'Oštećeno — otpis',
    'karenca_pull':           'Povučeno s tržnice (zdravstvena karenca)',
    'manual_adjustment':      'Ručna korekcija zalihe',
    'donation':               'Donirano',
}


def log_stock_change(item, qty, reason, user=None, note='',
                     marketplace_order=None, pos_receipt=None):
    """
    Bilježi promjenu zalihe s punim audit trailom.

    Args:
        item: InventoryItem
        qty: Decimal — negativan za izlaz, pozitivan za ulaz
        reason: str — ključ iz REASON_CHOICES
        user: User koji je napravio promjenu
        note: str — dodatno objašnjenje
        marketplace_order: MarketplaceOrder (optional)
        pos_receipt: POSReceipt (optional)

    Returns:
        StockMovement instance
    """
    from inventory.models import StockMovement

    qty = Decimal(str(qty))

    # Map reason to movement_type
    if qty < 0:
        if reason in ('expired', 'damaged', 'karenca_pull'):
            movement_type = 'writeoff'
        elif reason == 'donation':
            movement_type = 'donation_in'  # wait, donation out
            movement_type = 'out'
        else:
            movement_type = 'out'
    else:
        movement_type = 'in'

    reason_display = REASON_CHOICES.get(reason, reason)
    full_reason = reason_display
    if note:
        full_reason += ' — %s' % note
    if marketplace_order:
        full_reason += ' [MKT: %s]' % getattr(marketplace_order, 'order_number', str(marketplace_order))
    if pos_receipt:
        full_reason += ' [POS: %s]' % getattr(pos_receipt, 'receipt_number', str(pos_receipt))

    movement = StockMovement.objects.create(
        item=item,
        movement_type=movement_type,
        quantity=abs(qty),
        unit_price=item.price if hasattr(item, 'price') else Decimal('0'),
        reason=full_reason[:255],
        performed_by=user,
        invoice=getattr(marketplace_order, 'invoice', None),
    )

    # Update stock on item
    if hasattr(item, 'stock_qty'):
        item.stock_qty += qty
        item.save(update_fields=['stock_qty'])

    logger.info(
        '[INVENTORY AUDIT] %s %s: %s%s %s | reason=%s | user=%s',
        item.name if hasattr(item, 'name') else item,
        movement_type,
        '+' if qty > 0 else '',
        qty,
        getattr(item, 'unit', ''),
        reason,
        user,
    )

    return movement


def get_audit_summary(company, item=None, days=30):
    """
    Generira audit summary za firmu — koliko je otišlo na Marketplace vs POS vs interno.

    Returns:
        dict: {
            'marketplace_sales': Decimal,
            'pos_sales': Decimal,
            'internal_consumption': Decimal,
            'writeoffs': Decimal,
            'total_out': Decimal,
        }
    """
    from inventory.models import StockMovement
    from django.db.models import Sum, Q
    from datetime import timedelta

    since = timezone.now() - timedelta(days=days)

    qs = StockMovement.objects.filter(
        item__company=company,
        created_at__gte=since,
        movement_type='out',
    )
    if item:
        qs = qs.filter(item=item)

    marketplace = qs.filter(
        Q(reason__icontains='Marketplace') | Q(reason__icontains='MKT:')
    ).aggregate(s=Sum('quantity'))['s'] or Decimal('0')

    pos = qs.filter(
        Q(reason__icontains='POS') | Q(reason__icontains='blagajni')
    ).aggregate(s=Sum('quantity'))['s'] or Decimal('0')

    internal = qs.filter(
        reason__icontains='Interna'
    ).aggregate(s=Sum('quantity'))['s'] or Decimal('0')

    writeoffs = StockMovement.objects.filter(
        item__company=company,
        created_at__gte=since,
        movement_type='writeoff',
    ).aggregate(s=Sum('quantity'))['s'] or Decimal('0')

    total = qs.aggregate(s=Sum('quantity'))['s'] or Decimal('0')

    return {
        'marketplace_sales': marketplace,
        'pos_sales': pos,
        'internal_consumption': internal,
        'writeoffs': writeoffs,
        'total_out': total,
        'days': days,
    }
