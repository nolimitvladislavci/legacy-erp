"""
SplitAllocation Service — generira internu izdatnicu pri prebacivanju
robe iz "za prodaju" u "internu upotrebu" (repromaterijal).

Zakonska podloga: svaki prebacaj mora imati StockMovement dokument
da bi porezna inspekcija mogla pratiti tok robe.
"""

import logging
from decimal import Decimal

logger = logging.getLogger("inventory.split_allocation")


def allocate_to_inhouse(item, qty, reason="", user=None):
    """
    Prebaci qty s unreserved na reserved_inhouse.
    Generira StockMovement(internal_use) kao internu izdatnicu.

    Returns: StockMovement instance
    Raises: ValueError ako nema dovoljno unreserved zalihe
    """
    from inventory.models import StockMovement

    if qty <= 0:
        raise ValueError("Količina mora biti pozitivna.")

    available = item.unreserved_qty
    if qty > available:
        raise ValueError(
            f"Nedovoljna slobodna zaliha: traženo {qty}, dostupno {available}. "
            f"Ukupno: {item.quantity}, in-house: {item.reserved_inhouse}, "
            f"marketplace: {item.reserved_marketplace}."
        )

    # 1. Kreiraj StockMovement kao internu izdatnicu
    movement = StockMovement.objects.create(
        item=item,
        movement_type="internal_use",
        quantity=qty,
        unit_price=item.unit_price or Decimal("0"),
        reason=reason or "SplitAllocation: prebačeno u internu upotrebu (repromaterijal)",
        performed_by=user,
    )

    # 2. Ažuriraj reserved_inhouse (quantity se već smanjio kroz StockMovement.save)
    item.refresh_from_db()
    item.reserved_inhouse += qty
    item.save(update_fields=["reserved_inhouse"])

    logger.info(
        "SplitAllocation: %s — %s kom prebačeno u internu upotrebu. Izdatnica #%d. Preostala zaliha: %s",
        item.name,
        qty,
        movement.pk,
        item.quantity,
    )

    return movement


def release_from_inhouse(item, qty, reason="", user=None):
    """
    Vrati qty iz reserved_inhouse natrag u unreserved.
    Generira StockMovement(in) kao korekciju.
    """
    from inventory.models import StockMovement

    if qty <= 0:
        raise ValueError("Količina mora biti pozitivna.")
    if qty > item.reserved_inhouse:
        raise ValueError(f"Ne može se osloboditi {qty} — samo {item.reserved_inhouse} rezervirano in-house.")

    movement = StockMovement.objects.create(
        item=item,
        movement_type="in",
        quantity=qty,
        unit_price=item.unit_price or Decimal("0"),
        reason=reason or "SplitAllocation: povrat iz interne upotrebe u slobodnu zalihu",
        performed_by=user,
    )

    item.refresh_from_db()
    item.reserved_inhouse = max(Decimal("0"), item.reserved_inhouse - qty)
    item.save(update_fields=["reserved_inhouse"])

    logger.info("SplitAllocation release: %s — %s kom vraćeno. Preostala zaliha: %s", item.name, qty, item.quantity)

    return movement
