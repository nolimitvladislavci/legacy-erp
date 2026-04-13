"""
webshop/cart_engine.py
Polymorphic Cart Engine — domain-specific validation + race-safe stock lock.
Single engine, single Product model, domain rules via category field.
"""

from django.db import transaction


class CartError(Exception):
    def __init__(self, message, code="VALIDATION", status=400):
        self.message = message
        self.code = code
        self.status = status
        super().__init__(message)


def validate_food_rules(product, qty, attributes):
    """HACCP + volumetry rules for FOOD domain."""
    if product.is_expired:
        raise CartError(
            f'Artikl "{product.name}" ima istekao rok trajanja ({product.expiry_date}). '
            "HACCP karantena — prodaja zabranjena.",
            code="HACCP_EXPIRED",
            status=403,
        )
    capacity = product.packaging_capacity_kg
    if capacity and capacity > 0:
        if qty > int(capacity):
            raise CartError(
                f"Trazena kolicina ({qty} kg) premasuje kapacitet ambalaze "
                f'"{product.packaging_unit}" ({capacity} kg). '
                "Cijepanje veleprodajne ambalaze nije dozvoljeno.",
                code="PACKAGING_OVERFLOW",
                status=400,
            )


def validate_optics_rules(product, qty, attributes):
    """Medical attribute rules for OPTICS domain."""
    attrs = attributes or {}
    domain_attrs = product.domain_attrs or {}
    requires_sph = domain_attrs.get("requires_sph", True)
    if requires_sph and not attrs.get("sph"):
        raise CartError(
            "Dioptrija (SPH) je obavezna za opticki artikl. Unesite vrijednost sfericne korekcije.",
            code="MISSING_SPH",
            status=400,
        )
    requires_cyl = domain_attrs.get("requires_cyl", False)
    if requires_cyl and not attrs.get("cyl"):
        raise CartError(
            "Cilindar (CYL) je obavezan za ovaj artikl.",
            code="MISSING_CYL",
            status=400,
        )


DOMAIN_VALIDATORS = {
    "FOOD": validate_food_rules,
    "OPTICS": validate_optics_rules,
}


@transaction.atomic
def add_to_cart(user, product_id, qty, attributes=None, company=None):
    """
    Add item to cart with:
    1. Domain-specific validation (FOOD/OPTICS/etc.)
    2. Stock lock via select_for_update (race-safe)
    3. Atomic quantity reservation
    """
    from webshop.models import CartItem, Product

    attributes = attributes or {}

    try:
        product = Product.objects.select_for_update().get(pk=product_id)
    except Product.DoesNotExist:
        raise CartError("Proizvod ne postoji.", code="NOT_FOUND", status=404)

    if not product.is_active:
        raise CartError("Proizvod nije aktivan.", code="INACTIVE", status=400)

    # Domain-specific validation
    validator = DOMAIN_VALIDATORS.get(product.category)
    if validator:
        validator(product, qty, attributes)

    # Stock check (skip for SERVICE)
    if product.category != "SERVICE":
        if qty > product.available_qty:
            raise CartError(
                f"Nedovoljna zaliha. Trazeno: {qty}, dostupno: {product.available_qty}.",
                code="OUT_OF_STOCK",
                status=409,
            )
        product.available_qty -= qty
        product.save(update_fields=["available_qty", "updated_at"])

    cart_item = CartItem.objects.create(
        user=user,
        product=product,
        quantity=qty,
        item_attributes=attributes,
        company=company,
    )
    return cart_item
