"""
pos/ai/upsell.py — AI Upsell Engine za POS Joker.
Haiku analizira košaricu i predlaže 1-3 komplementarna artikla.
Cache per (items_hash, company_id) — 24h.
"""
import json
import hashlib
import logging

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger('pos_upsell')


def get_upsell_suggestions(company, cart_item_ids: list) -> list:
    """
    Vraća listu upsell prijedloga za danu košaricu.
    Returns: [{'sku_id': 123, 'name': '...', 'price': '...', 'reason': '...'}]
    """
    if not cart_item_ids or len(cart_item_ids) > 10:
        return []

    from inventory.models import InventoryItem

    # Get cart items
    cart_items = list(InventoryItem.objects.filter(
        pk__in=cart_item_ids, company=company, is_active=True
    ).values('pk', 'name', 'category', 'unit_price'))

    if not cart_items:
        return []

    # Cache key
    items_key = ','.join(sorted(str(i['pk']) for i in cart_items))
    cache_key = f"upsell:{company.pk}:{hashlib.md5(items_key.encode()).hexdigest()}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    # Get available items (exclude what's in cart, only in-stock)
    available = list(InventoryItem.objects.filter(
        company=company, is_active=True, quantity__gt=0
    ).exclude(
        pk__in=cart_item_ids
    ).values('pk', 'name', 'category', 'unit_price')[:50])

    if not available:
        return []

    # Try AI first, fallback to keyword
    suggestions = _ai_suggest(cart_items, available)
    if not suggestions:
        suggestions = _keyword_suggest(cart_items, available)

    # Cache 24h
    cache.set(cache_key, suggestions, timeout=86400)
    return suggestions


def _ai_suggest(cart_items, available) -> list:
    """Haiku-based upsell suggestion."""
    api_key = getattr(settings, 'ANTHROPIC_API_KEY', '')
    if not api_key:
        return []

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        cart_str = ', '.join(f"{i['name']} ({i['category']})" for i in cart_items)
        avail_str = '\n'.join(
            f"ID:{i['pk']} {i['name']} ({i['category']}) {i['unit_price']}EUR"
            for i in available[:30]
        )

        msg = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=200,
            messages=[{'role': 'user', 'content': (
                f"Košarica: {cart_str}\n\n"
                f"Dostupni artikli:\n{avail_str}\n\n"
                "Predloži 1-3 artikla koja bi kupac vjerojatno dodao. "
                "Razmišljaj o komplementarnosti (kava→mlijeko), "
                "margin upgrade (basic→premium), cross-sell.\n"
                'Odgovori SAMO JSON: [{"id": 123, "reason": "kratko objašnjenje"}]'
            )}],
        )

        raw = msg.content[0].text.strip()
        data = json.loads(raw)
        if not isinstance(data, list):
            return []

        # Map to full items
        avail_map = {i['pk']: i for i in available}
        result = []
        for s in data[:3]:
            item_id = s.get('id')
            if item_id and item_id in avail_map:
                item = avail_map[item_id]
                result.append({
                    'sku_id': item['pk'],
                    'name': item['name'],
                    'price': str(item['unit_price']),
                    'category': item['category'],
                    'reason': s.get('reason', ''),
                })
        return result

    except (json.JSONDecodeError, ValueError) as e:
        logger.warning('AI upsell fallback: %s', e)
        return []


def _keyword_suggest(cart_items, available) -> list:
    """Keyword-based fallback — same category, different item."""
    cart_cats = {i['category'] for i in cart_items}
    cart_ids = {i['pk'] for i in cart_items}

    # Same category suggestions
    same_cat = [i for i in available if i['category'] in cart_cats and i['pk'] not in cart_ids]
    # Different category (cross-sell)
    diff_cat = [i for i in available if i['category'] not in cart_cats]

    result = []
    for item in (same_cat[:2] + diff_cat[:1]):
        result.append({
            'sku_id': item['pk'],
            'name': item['name'],
            'price': str(item['unit_price']),
            'category': item['category'],
            'reason': 'Popularan izbor' if item in same_cat else 'Možda vas zanima',
        })

    return result[:3]
