"""
synesis/services.py — Reverse sync helpers: ERP → Synesis export queue.
"""


def push_item_to_synesis(company, item, action="update"):
    """Queue an InventoryItem change for reverse sync to Synesis MDB."""
    from .models import SynesisExportQueue

    fields = {
        "ITEM_NAME": item.name,
        "ITEM_PRICE": float(item.unit_price),
        "ITEM_NETPRICE": float(item.purchase_price),
        "ITEM_MEASURE": item.unit,
        "ITEM_BARCODE": item.barcode,
        "VAT_RATE": float(item.tax_rate),
    }
    synesis_id = item.sku.replace("SYN-", "") if item.sku and item.sku.startswith("SYN-") else ""

    SynesisExportQueue.objects.create(
        company=company,
        export_type="item",
        action=action,
        synesis_id=synesis_id,
        erp_object_id=str(item.pk),
        description=item.name,
        payload=fields,
    )


def push_partner_to_synesis(company, partner, action="update"):
    """Queue a Partner change for reverse sync to Synesis MDB."""
    from .models import SynesisExportQueue

    country_map = {
        "Hrvatska": "HR",
        "Njemacka": "DE",
        "Slovenija": "SI",
        "Austrija": "AT",
    }
    country_code = country_map.get(partner.country, "HR")

    fields = {
        "PARTNER_NAME": partner.name,
        "PARTNER_VATNUMBER": partner.oib,
        "PARTNER_STREET": partner.address,
        "CITY_NAME": partner.city,
        "CITY_ZIPCODE": partner.zip_code,
        "PARTNER_EMAIL": partner.email,
        "PARTNER_PHONE": partner.phone,
        "PARTNER_WEB": partner.web,
        "INT_COUNTRYID": country_code,
        "PARTNER_DISCOUNTRATE": float(partner.discount_percent),
        "PARTNER_PAYMENTDAYS": partner.payment_term,
    }
    SynesisExportQueue.objects.create(
        company=company,
        export_type="partner",
        action=action,
        synesis_id="",
        erp_object_id=str(partner.pk),
        description=partner.name,
        payload=fields,
    )
