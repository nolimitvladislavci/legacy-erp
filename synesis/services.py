"""
synesis/services.py — Helper functions to queue data for reverse sync to Synesis.

Usage from anywhere in ERP:
    from synesis.services import push_item_to_synesis, push_partner_to_synesis

    push_item_to_synesis(inventory_item, user=request.user)
    push_partner_to_synesis(partner, user=request.user)
"""
from decimal import Decimal
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist


def push_item_to_synesis(item, user=None, price_only=False):
    """
    Queue an InventoryItem for export to Synesis Storage.mdb.
    If SKU starts with 'SYN-', it's an update (we know the Synesis ID).
    Otherwise it's an insert (new article).
    """
    from .models import SynesisExportQueue, SynesisConfig

    company = item.company
    if not company:
        return None

    # Check if company has active Synesis config
    try:
        cfg = SynesisConfig.objects.get(company=company, is_active=True)
    except SynesisConfig.DoesNotExist:
        return None

    # Determine if update or insert
    synesis_id = ''
    action = 'insert'
    if item.sku and item.sku.startswith('SYN-'):
        synesis_id = item.sku.replace('SYN-', '')
        action = 'update'

    # Build payload (Synesis MDB field names)
    if price_only and action == 'update':
        payload = {
            'ITEM_PRICE': float(item.unit_price),
            'ITEM_NETPRICE': float(item.purchase_price),
        }
        desc = f'Cijena: {item.name} → {item.unit_price} EUR'
    else:
        vat_rate = float(item.tax_rate.rate) if item.tax_rate else 25.0
        payload = {
            'ITEM_NAME': item.name,
            'ITEM_MEASURE': item.unit or 'kom',
            'ITEM_BARCODE': item.barcode or '',
            'ITEM_PRICE': float(item.unit_price),
            'ITEM_NETPRICE': float(item.purchase_price),
            'VAT_RATE': vat_rate,
            'ITEM_REMARK': item.description or '',
        }
        if action == 'insert':
            desc = f'Novi artikl: {item.name}'
        else:
            desc = f'Azuriranje: {item.name}'

    q = SynesisExportQueue.objects.create(
        company=company,
        export_type='item',
        action=action,
        synesis_id=synesis_id,
        erp_object_id=str(item.pk),
        payload=payload,
        description=desc,
        created_by=user,
    )
    return q


def push_partner_to_synesis(partner, user=None):
    """
    Queue a Partner for export to Synesis Storage.mdb PARTNERS table.
    """
    from .models import SynesisExportQueue, SynesisConfig

    company = partner.company
    if not company:
        return None

    try:
        cfg = SynesisConfig.objects.get(company=company, is_active=True)
    except SynesisConfig.DoesNotExist:
        return None

    # Try to find matching Synesis partner by OIB
    synesis_id = ''
    action = 'insert'

    # If partner was imported from Synesis, we might have the ID
    # Check if there's an existing export for this partner
    existing = SynesisExportQueue.objects.filter(
        company=company, export_type='partner',
        erp_object_id=str(partner.pk), action='update'
    ).first()
    if existing and existing.synesis_id:
        synesis_id = existing.synesis_id
        action = 'update'

    # Map country back to Synesis format
    country_map = {
        'HR': 'HR', 'Hrvatska': 'HR',
        'DE': 'DE', 'Njemacka': 'DE', 'Njemačka': 'DE',
        'AT': 'AT', 'Austrija': 'AT',
        'SI': 'SI', 'Slovenija': 'SI',
        'BA': 'BA', 'Bosna i Hercegovina': 'BA',
        'RS': 'RS', 'Srbija': 'RS',
        'IT': 'IT', 'Italija': 'IT',
        'HU': 'HU', 'Madarska': 'HU',
    }
    country_code = country_map.get(partner.country, 'HR')

    # Partner type: Synesis uses 1=supplier, else=client
    ptype = '1' if partner.partner_type == 'supplier' else '2'

    payload = {
        'PARTNER_NAME': partner.name,
        'PARTNER_VATNUMBER': partner.oib or '',
        'PARTNER_STREET': partner.address or '',
        'CITY_NAME': partner.city or '',
        'CITY_ZIPCODE': partner.zip_code or '',
        'PARTNER_EMAIL': partner.email or '',
        'PARTNER_PHONE': partner.phone or '',
        'PARTNER_WEB': partner.web or '',
        'INT_COUNTRYID': country_code,
        'PARTNER_TYPE': ptype,
        'PARTNER_PAYMENTDAYS': partner.payment_term or 0,
        'PARTNER_DISCOUNTRATE': float(partner.discount_percent or 0),
    }

    desc = f'Partner: {partner.name}'
    if action == 'update':
        desc = f'Azuriranje partnera: {partner.name}'

    q = SynesisExportQueue.objects.create(
        company=company,
        export_type='partner',
        action=action,
        synesis_id=synesis_id,
        erp_object_id=str(partner.pk),
        payload=payload,
        description=desc,
        created_by=user,
    )
    return q


def push_price_change_to_synesis(item, new_price, new_purchase_price=None, user=None):
    """
    Quick price recalculation push — only updates prices in Synesis.
    """
    from .models import SynesisExportQueue, SynesisConfig

    company = item.company
    if not company:
        return None

    try:
        SynesisConfig.objects.get(company=company, is_active=True)
    except SynesisConfig.DoesNotExist:
        return None

    synesis_id = ''
    if item.sku and item.sku.startswith('SYN-'):
        synesis_id = item.sku.replace('SYN-', '')

    if not synesis_id:
        return None  # Can only update prices for known Synesis items

    payload = {
        'ITEM_PRICE': float(new_price),
    }
    if new_purchase_price is not None:
        payload['ITEM_NETPRICE'] = float(new_purchase_price)

    q = SynesisExportQueue.objects.create(
        company=company,
        export_type='item',
        action='update',
        synesis_id=synesis_id,
        erp_object_id=str(item.pk),
        payload=payload,
        description=f'Kalkulacija: {item.name} → {new_price} EUR',
        created_by=user,
    )
    return q


def get_pending_export_count(company):
    """Get count of pending exports for dashboard widget."""
    from .models import SynesisExportQueue
    return SynesisExportQueue.objects.filter(
        company=company, is_exported=False
    ).count()
