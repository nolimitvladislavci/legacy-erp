"""inventory/sync.py — sinkronizacija InventoryItem → webshop.Product"""


def sync_to_webshop(item):
    """
    webshop_visible=True  → kreiraj ili ažuriraj webshop.Product
    webshop_visible=False → deaktiviraj linkani Product (ako postoji)
    """
    from webshop.models import Product

    # Safety: refresh quantity from DB if it's an F-expression
    try:
        int(item.quantity)
    except (TypeError, ValueError):
        item.refresh_from_db(fields=["quantity"])

    product = None
    try:
        product = Product.objects.get(inventory_item=item)
    except Product.DoesNotExist:
        product = Product.objects.filter(sku=item.sku).first()

    if not item.webshop_visible:
        if product and product.inventory_item_id == item.pk:
            product.is_active = False
            product.save(update_fields=["is_active"])
        return

    if product:
        product.name = item.name
        product.price = item.unit_price
        product.stock = max(0, int(item.quantity))
        product.is_active = item.is_active
        product.description = item.description or product.description
        product.inventory_item = item
        if item.image and not product.image:
            product.image = item.image
        product.save(update_fields=["name", "price", "stock", "is_active", "description", "inventory_item", "image"])
    else:
        Product.objects.create(
            inventory_item=item,
            sku=item.sku,
            name=item.name,
            price=item.unit_price,
            stock=max(0, int(item.quantity)),
            is_active=item.is_active,
            description=item.description or "",
            image=item.image or "",
        )
