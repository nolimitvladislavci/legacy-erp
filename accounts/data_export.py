"""
GDPR Article 20 — Data Portability / Export.
Export all company data as a streaming JSON response.
"""
import json
import logging
from decimal import Decimal
from datetime import date, datetime
from uuid import UUID

from django.contrib.auth.decorators import login_required
from django.http import StreamingHttpResponse, JsonResponse
from django.utils import timezone as tz

from accounts.models import UserProfile
from django.core.exceptions import ObjectDoesNotExist
from core.company_utils import get_user_company
from django.db import IntegrityError, DatabaseError

logger = logging.getLogger('accounts')

# 50 MB limit
MAX_EXPORT_SIZE_BYTES = 50 * 1024 * 1024


class GDPRJsonEncoder(json.JSONEncoder):
    """Custom encoder for Django model types."""

    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, UUID):
            return str(obj)
        return super().default(obj)


def _model_to_dict(instance, fields=None, exclude=None):
    """Convert a model instance to a dict, respecting include/exclude lists."""
    exclude = exclude or []
    data = {}
    for field in instance._meta.get_fields():
        if not hasattr(field, 'attname'):
            continue
        name = field.attname
        if fields and name not in fields:
            continue
        if name in exclude:
            continue
        val = getattr(instance, name, None)
        data[name] = val
    return data


def _stream_json(data_generator):
    """Yield JSON chunks from a generator that produces dict sections."""
    yield '{\n'
    first = True
    for key, value in data_generator:
        if not first:
            yield ',\n'
        first = False
        yield f'  "{key}": '
        yield json.dumps(value, cls=GDPRJsonEncoder, ensure_ascii=False, indent=2)
    yield '\n}\n'


@login_required
def export_company_data(request):
    """
    GDPR čl. 20 — Export svih podataka firme u JSON.
    Uključuje:
    - Company info (name, OIB, address)
    - Users (name, email — NOT passwords)
    - Partners (clients, suppliers)
    - Inventory items
    - Invoices (with items)
    - POS receipts (with items, payments)
    - Worktime entries
    - Documents metadata

    Returns: StreamingHttpResponse with JSON file
    Max: 50MB per export (paginate if larger)
    """
    company = get_user_company(request)
    if not company:
        return JsonResponse({'error': 'Nije moguće odrediti tvrtku.'}, status=400)

    # Audit trail
    try:
        from worktime.tracker import track
        track(
            request.user, 'ACCOUNTS', 'DATA_EXPORT',
            ref=str(company.pk),
            detail=f'GDPR čl. 20 export zatražen za {company.name}',
            company=company,
        )
    except ImportError:
        logger.exception('Audit trail failed for data export')

    def data_sections():
        """Generator yielding (key, value) tuples for each data section."""

        # ── Export metadata ──────────────────────────────────────────
        yield ('_export_metadata', {
            'exported_at': tz.now().isoformat(),
            'exported_by': request.user.username,
            'company_id': str(company.pk),
            'gdpr_article': '20 — Right to data portability',
            'format_version': '1.0',
        })

        # ── Company info ─────────────────────────────────────────────
        yield ('company', {
            'name': company.name,
            'oib': company.oib,
            'address': company.address,
            'city': company.city,
            'zip_code': company.zip_code,
            'country': company.country,
            'business_type': company.business_type,
            'email': company.email,
            'phone': company.phone,
            'mobile': getattr(company, 'mobile', ''),
            'iban': company.iban,
            'swift': company.swift,
            'vat_id': company.vat_id,
            'currency': company.currency,
            'is_vat_registered': company.is_vat_registered,
            'created_at': company.created_at,
        })

        # ── Users (NO passwords) ────────────────────────────────────
        profiles = UserProfile.objects.filter(company=company).select_related('user')
        users_data = []
        for profile in profiles:
            u = profile.user
            users_data.append({
                'username': u.username,
                'first_name': u.first_name,
                'last_name': u.last_name,
                'email': u.email,
                'is_active': u.is_active,
                'date_joined': u.date_joined,
                'last_login': u.last_login,
                'role': getattr(profile, 'role', ''),
            })
        yield ('users', users_data)

        # ── Partners ─────────────────────────────────────────────────
        try:
            from partners.models import Partner
            partners = Partner.objects.filter(company=company)
            partners_data = []
            for p in partners.iterator(chunk_size=500):
                partners_data.append({
                    'id': p.pk,
                    'name': p.name,
                    'oib': p.oib,
                    'address': p.address,
                    'city': p.city,
                    'zip_code': p.zip_code,
                    'email': p.email,
                    'phone': p.phone,
                    'contact_person': p.contact_person,
                    'contact_email': p.contact_email,
                    'iban': p.iban,
                    'is_vat_registered': p.is_vat_registered,
                })
            yield ('partners', partners_data)
        except DatabaseError:
            logger.exception('Failed to export partners')
            yield ('partners', [])

        # ── Inventory items ──────────────────────────────────────────
        try:
            from inventory.models import InventoryItem
            items = InventoryItem.objects.filter(company=company)
            items_data = []
            for item in items.iterator(chunk_size=500):
                items_data.append({
                    'id': item.pk,
                    'name': getattr(item, 'name', ''),
                    'sku': getattr(item, 'sku', ''),
                    'barcode': getattr(item, 'barcode', ''),
                    'price': getattr(item, 'price', None),
                    'stock_quantity': getattr(item, 'stock_quantity', None),
                    'unit': getattr(item, 'unit', ''),
                    'is_active': getattr(item, 'is_active', True),
                })
            yield ('inventory_items', items_data)
        except DatabaseError:
            logger.exception('Failed to export inventory')
            yield ('inventory_items', [])

        # ── Invoices (with items) ────────────────────────────────────
        try:
            from invoicing.models import Invoice, InvoiceItem
            invoices = Invoice.objects.filter(company=company).order_by('-id')
            invoices_data = []
            for inv in invoices.iterator(chunk_size=200):
                inv_items = InvoiceItem.objects.filter(invoice=inv)
                inv_dict = {
                    'id': inv.pk,
                    'number': getattr(inv, 'number', ''),
                    'date': getattr(inv, 'date', None),
                    'due_date': getattr(inv, 'due_date', None),
                    'total': getattr(inv, 'total', None),
                    'status': getattr(inv, 'status', ''),
                    'jir': getattr(inv, 'jir', ''),
                    'zki': getattr(inv, 'zki', ''),
                    'items': [],
                }
                for ii in inv_items:
                    inv_dict['items'].append({
                        'description': getattr(ii, 'description', ''),
                        'quantity': getattr(ii, 'quantity', None),
                        'unit_price': getattr(ii, 'unit_price', None),
                        'total': getattr(ii, 'total', None),
                        'tax_rate': getattr(ii, 'tax_rate', None),
                    })
                invoices_data.append(inv_dict)
            yield ('invoices', invoices_data)
        except DatabaseError:
            logger.exception('Failed to export invoices')
            yield ('invoices', [])

        # ── POS receipts (with items, payments) ──────────────────────
        try:
            from pos.models import POSReceipt, POSReceiptItem
            receipts = POSReceipt.objects.filter(company=company).order_by('-id')
            receipts_data = []
            for r in receipts.iterator(chunk_size=200):
                r_items = POSReceiptItem.objects.filter(receipt=r)
                r_dict = {
                    'id': r.pk,
                    'receipt_number': getattr(r, 'receipt_number', ''),
                    'created_at': getattr(r, 'created_at', None),
                    'total': getattr(r, 'total', None),
                    'status': getattr(r, 'status', ''),
                    'jir': getattr(r, 'jir', ''),
                    'zki': getattr(r, 'zki', ''),
                    'payment_method': getattr(r, 'payment_method', ''),
                    'items': [],
                }
                for ri in r_items:
                    r_dict['items'].append({
                        'name': getattr(ri, 'name', ''),
                        'quantity': getattr(ri, 'quantity', None),
                        'unit_price': getattr(ri, 'unit_price', None),
                        'total': getattr(ri, 'total', None),
                        'tax_rate': getattr(ri, 'tax_rate', None),
                    })
                receipts_data.append(r_dict)
            yield ('pos_receipts', receipts_data)
        except DatabaseError:
            logger.exception('Failed to export POS receipts')
            yield ('pos_receipts', [])

        # ── Worktime entries ─────────────────────────────────────────
        try:
            from worktime.models import TimeEntry
            entries = TimeEntry.objects.filter(company=company).order_by('-id')
            entries_data = []
            for te in entries.iterator(chunk_size=500):
                entries_data.append({
                    'id': te.pk,
                    'user': str(getattr(te, 'user', '')),
                    'date': getattr(te, 'date', None),
                    'start_time': getattr(te, 'start_time', None),
                    'end_time': getattr(te, 'end_time', None),
                    'hours': getattr(te, 'hours', None),
                    'description': getattr(te, 'description', ''),
                })
            yield ('worktime_entries', entries_data)
        except DatabaseError:
            logger.exception('Failed to export worktime entries')
            yield ('worktime_entries', [])

        # ── Documents metadata ───────────────────────────────────────
        try:
            from documents.models import Document
            docs = Document.objects.filter(company=company).order_by('-id')
            docs_data = []
            for doc in docs.iterator(chunk_size=500):
                docs_data.append({
                    'id': doc.pk,
                    'title': getattr(doc, 'title', ''),
                    'type': getattr(doc, 'type', ''),
                    'created_at': getattr(doc, 'created_at', None),
                    'filename': getattr(doc, 'filename', ''),
                })
            yield ('documents', docs_data)
        except DatabaseError:
            logger.exception('Failed to export documents')
            yield ('documents', [])

    # Stream response
    filename = f'limit-connect-export-{company.oib}-{tz.now().strftime("%Y%m%d-%H%M%S")}.json'
    response = StreamingHttpResponse(
        _stream_json(data_sections()),
        content_type='application/json; charset=utf-8',
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
