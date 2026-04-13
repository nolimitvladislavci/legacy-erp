"""
marketplace/discounts.py — Discount calculation service.

Logika:
1. PartnerDiscount tier (Bronze 10%, Silver 15%, Gold 20%, Platinum 25%, Custom)
2. CategoryDiscount (per seller→buyer→category, stacks OR overrides partner tier)
3. VolumeDiscount (quantity breaks, additional on top)

Primjena: uzima se NAJVECI od (partner_tier, category_discount), pa se DODAJE volume_discount.
Maksimalni ukupni rabat: 50% (safety cap).
"""
from decimal import Decimal

from django.utils import timezone

TIER_DISCOUNTS = {
    'standard': Decimal('0'),
    'bronze': Decimal('10'),
    'silver': Decimal('15'),
    'gold': Decimal('20'),
    'platinum': Decimal('25'),
    'custom': None,  # uses PartnerDiscount.discount_percent
}

MAX_DISCOUNT = Decimal('50')


def get_discount_for_item(product, buyer_company, quantity=Decimal('1')):
    """
    Calculate total discount % for a product given buyer and quantity.

    Returns dict:
        {
            'partner_percent': Decimal,
            'category_percent': Decimal,
            'volume_percent': Decimal,
            'total_percent': Decimal,
            'tier': str,
            'original_price': Decimal,
            'discounted_price': Decimal,
            'savings_per_unit': Decimal,
        }
    """
    from .models import CategoryDiscount, PartnerDiscount, VolumeDiscount

    today = timezone.now().date()
    seller = product.seller_company

    # 1. Partner tier discount
    partner_pct = Decimal('0')
    tier = 'standard'
    try:
        pd = PartnerDiscount.objects.get(
            seller_company=seller,
            buyer_company=buyer_company,
            is_active=True,
        )
        if pd.valid_from and today < pd.valid_from:
            pd = None
        elif pd.valid_until and today > pd.valid_until:
            pd = None
        else:
            tier = pd.tier
            if pd.tier == 'custom':
                partner_pct = pd.discount_percent
            else:
                partner_pct = TIER_DISCOUNTS.get(pd.tier, Decimal('0'))
    except PartnerDiscount.DoesNotExist:
        pass

    # 2. Category discount (specific > general)
    cat_pct = Decimal('0')
    if product.category:
        cat_discounts = CategoryDiscount.objects.filter(
            seller_company=seller,
            category=product.category,
            is_active=True,
        ).filter(
            models_q_valid(today)
        )
        # Specific buyer first, then general (buyer=None)
        for cd in cat_discounts:
            if cd.buyer_company == buyer_company:
                cat_pct = cd.discount_percent
                break
            elif cd.buyer_company is None:
                cat_pct = cd.discount_percent

    # Take the HIGHER of partner vs category
    base_pct = max(partner_pct, cat_pct)

    # 3. Volume discount (additional, stacks on top)
    vol_pct = Decimal('0')
    vol_qs = VolumeDiscount.objects.filter(
        seller_company=seller,
        is_active=True,
        min_quantity__lte=quantity,
    ).order_by('-min_quantity')

    # Product-specific volume discount first
    product_vol = vol_qs.filter(product=product).first()
    if product_vol:
        vol_pct = product_vol.discount_percent
    elif product.category:
        cat_vol = vol_qs.filter(category=product.category, product__isnull=True).first()
        if cat_vol:
            vol_pct = cat_vol.discount_percent
    if not vol_pct:
        general_vol = vol_qs.filter(product__isnull=True, category__isnull=True).first()
        if general_vol:
            vol_pct = general_vol.discount_percent

    # Total with cap
    total_pct = min(base_pct + vol_pct, MAX_DISCOUNT)

    # Price calculation
    original = product.unit_price
    savings = original * total_pct / Decimal('100')
    discounted = original - savings

    return {
        'partner_percent': partner_pct,
        'category_percent': cat_pct,
        'volume_percent': vol_pct,
        'total_percent': total_pct,
        'tier': tier,
        'original_price': original,
        'discounted_price': discounted.quantize(Decimal('0.01')),
        'savings_per_unit': savings.quantize(Decimal('0.01')),
    }


def models_q_valid(today):
    """Return Q filter for date validity."""
    from django.db.models import Q
    return (
        (Q(valid_from__isnull=True) | Q(valid_from__lte=today)) &
        (Q(valid_until__isnull=True) | Q(valid_until__gte=today))
    )


def get_cart_with_discounts(cart_items, buyer_company):
    """
    Enhance cart items with discount info.
    cart_items: list of dicts with 'product_id', 'qty'
    Returns enriched list with discount fields.
    """
    from .models import MarketplaceProduct

    enriched = []
    for item in cart_items:
        product = MarketplaceProduct.objects.select_related(
            'seller_company', 'category'
        ).get(pk=item['product_id'])

        qty = Decimal(str(item['qty']))
        disc = get_discount_for_item(product, buyer_company, qty)

        line_original = product.unit_price * qty
        line_discounted = disc['discounted_price'] * qty
        line_savings = line_original - line_discounted

        enriched.append({
            **item,
            'product': product,
            'original_price': float(product.unit_price),
            'discounted_price': float(disc['discounted_price']),
            'discount_percent': float(disc['total_percent']),
            'tier': disc['tier'],
            'line_original': float(line_original),
            'line_total': float(line_discounted),
            'line_savings': float(line_savings),
            'has_discount': disc['total_percent'] > 0,
            'partner_pct': float(disc['partner_percent']),
            'volume_pct': float(disc['volume_percent']),
        })

    return enriched
