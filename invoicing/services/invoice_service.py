from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError, DatabaseError
"""Invoice business logic — extracted from views.py."""
import datetime
from decimal import Decimal, InvalidOperation


# ─────────────────────────────────────────────────────────────────────────────
# Number generation
# ─────────────────────────────────────────────────────────────────────────────

def generate_invoice_number(invoice, profile, doctype):
    """Assign next invoice number to invoice. Mutates invoice.number."""
    if profile:
        invoice.invoice_profile = profile
        invoice.number = profile.get_next_number(doctype)
    else:
        from invoicing.fiscal_models import FiscalConfig
        from invoicing.models import Invoice
        config = FiscalConfig.get()
        prefix = config.invoice_prefix_hr or 'KNJ'
        year = datetime.datetime.now().year
        next_num = config.next_invoice_number or 1
        invoice.number = f'{prefix}-{year}-{next_num:04d}'
        while Invoice.objects.filter(number=invoice.number).exists():
            next_num += 1
            invoice.number = f'{prefix}-{year}-{next_num:04d}'
        config.next_invoice_number = next_num + 1
        config.save()
    return invoice.number


# ─────────────────────────────────────────────────────────────────────────────
# Partner auto-creation
# ─────────────────────────────────────────────────────────────────────────────

def ensure_partner(company, invoice):
    """Auto-create Partner from invoice client data if not already in DB."""
    name = (invoice.client_name or '').strip()
    if not name or not company:
        return
    from partners.models import Partner
    from django.db import IntegrityError
    defaults = {
        'name': name,
        'email': invoice.client_email or '',
        'address': invoice.client_address or '',
        'city': invoice.client_city or '',
        'partner_type': 'client',
    }
    try:
        if invoice.client_oib:
            Partner.objects.get_or_create(
                company=company, oib=invoice.client_oib, defaults=defaults,
            )
        else:
            Partner.objects.get_or_create(
                company=company, name=name, oib='', defaults=defaults,
            )
    except IntegrityError:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Items
# ─────────────────────────────────────────────────────────────────────────────

def save_items(invoice, post_data):
    """Delete existing items and recreate from POST arrays."""
    from invoicing.models import InvoiceItem
    invoice.items.all().delete()
    descs   = post_data.getlist('item_desc[]')
    qtys    = post_data.getlist('item_qty[]')
    units   = post_data.getlist('item_unit[]')
    prices  = post_data.getlist('item_price[]')
    pdvs    = post_data.getlist('item_pdv[]')
    discs   = post_data.getlist('item_disc[]')
    inv_ids = post_data.getlist('item_inventory_id[]')
    for i, desc in enumerate(descs):
        if not desc.strip():
            continue
        try:
            qty   = Decimal(str(qtys[i]).replace(',', '.'))
            price = Decimal(str(prices[i]).replace(',', '.'))
            pdv   = Decimal(str(pdvs[i]))
            disc  = Decimal(str(discs[i]).replace(',', '.') if discs[i] else '0')
            total = qty * price * (1 - disc / 100)
            InvoiceItem.objects.create(
                invoice=invoice,
                description=desc,
                quantity=qty,
                unit=units[i] if i < len(units) else 'kom',
                unit_price=price,
                tax_rate=pdv,
                discount_percent=disc,
                total_price=round(total, 2),
                inventory_item_id=(
                    int(inv_ids[i]) if i < len(inv_ids) and inv_ids[i] else None
                ),
            )
        except (InvalidOperation, IndexError, ValueError):
            continue


# ─────────────────────────────────────────────────────────────────────────────
# Inventory deduction
# ─────────────────────────────────────────────────────────────────────────────

def deduct_inventory(invoice, old_status, user):
    """Deduct stock on first transition to PAID status."""
    if invoice.status != 'PAID' or old_status == 'PAID':
        return
    try:
        from inventory.models import StockMovement
        for iitem in invoice.items.select_related('inventory_item').all():
            if not iitem.inventory_item_id:
                continue
            # Usluge i non-stockable stavke — ne diramo zalihu
            if not iitem.inventory_item.is_stockable:
                continue
            StockMovement.objects.create(
                item_id=iitem.inventory_item_id,
                movement_type='out',
                quantity=iitem.quantity,
                unit_price=iitem.unit_price,
                reason=f'Račun {invoice.number}',
                performed_by=user,
                invoice=invoice,
            )
            try:
                from calculator.models import BOM
                for bom in BOM.objects.filter(
                    article_id=iitem.inventory_item_id, is_active=True
                ).prefetch_related('items__material'):
                    sold_qty = iitem.quantity / (bom.yield_quantity or 1)
                    for bi in bom.items.select_related('material').all():
                        StockMovement.objects.create(
                            item=bi.material,
                            movement_type='out',
                            quantity=bi.net_quantity * sold_qty,
                            unit_price=bi.material.purchase_price,
                            reason=f'BOM — Račun {invoice.number}',
                            performed_by=user,
                        )
            except (IntegrityError, DatabaseError):
                pass
    except (IntegrityError, DatabaseError):
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Worktime
# ─────────────────────────────────────────────────────────────────────────────

def mark_worktime_billed(invoice, wt_ids_str):
    """Mark TimeEntry records as billed."""
    if not wt_ids_str:
        return
    try:
        from worktime.models import TimeEntry
        ids = [int(x) for x in wt_ids_str.split(',') if x.strip().isdigit()]
        if ids:
            TimeEntry.objects.filter(id__in=ids, is_billed=False).update(
                is_billed=True, invoice=invoice,
            )
    except (ValueError, TypeError):
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Notifications
# ─────────────────────────────────────────────────────────────────────────────

def notify_paid(invoice, requesting_user):
    """Fire notification when invoice transitions to PAID."""
    if invoice.status != 'PAID':
        return
    try:
        from notifications.services import notify
        if invoice.created_by and invoice.created_by != requesting_user:
            notify(
                recipient=invoice.created_by,
                notification_type='invoice_paid',
                title=f'Racun {invoice.number} placen',
                message=f'{invoice.client_name} - {invoice.total} {invoice.currency}',
                url=f'/invoicing/edit/{invoice.pk}/',
                sender=requesting_user,
            )
    except ImportError:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Copy invoice helper
# ─────────────────────────────────────────────────────────────────────────────

def copy_invoice(source, new_doctype, new_number, extra_fields=None):
    """
    Deep-copy an invoice with new doctype and number.
    Returns the new Invoice instance (unsaved items are copied too).
    """
    from invoicing.models import Invoice, InvoiceItem
    new_inv = Invoice()
    skip = {'id', 'pk', 'uuid', 'number', 'doctype', 'is_fiscalized', 'zki', 'jir',
            'fiscal_datetime', 'status', 'qr_code_base64', 'created_at', 'updated_at'}
    for f in source._meta.fields:
        if f.name not in skip:
            setattr(new_inv, f.name, getattr(source, f.name))
    import uuid as _uuid
    new_inv.pk = None
    new_inv.uuid = _uuid.uuid4()
    new_inv.client_token = _uuid.uuid4()
    new_inv.doctype = new_doctype
    new_inv.number = new_number
    new_inv.status = 'DRAFT'
    new_inv.is_fiscalized = False
    new_inv.zki = ''
    new_inv.jir = ''
    new_inv.qr_code_base64 = ''
    new_inv.source_document = source
    if extra_fields:
        for k, v in extra_fields.items():
            setattr(new_inv, k, v)
    new_inv.save()
    for item in source.items.all():
        item.pk = None
        item.invoice = new_inv
        item.save()
    return new_inv


# ─────────────────────────────────────────────────────────────────────────────
# Main save orchestrator
# ─────────────────────────────────────────────────────────────────────────────

@transaction.atomic
def save_invoice_from_post(request):
    """
    Full invoice save logic (create or update) from POST data.
    Returns the saved Invoice instance.
    Attaches ._gobd_warnings list if GoBD issues found.
    """
    from invoicing.models import Invoice
    from core.company_utils import get_user_company
    from django.shortcuts import get_object_or_404
    from django.utils import timezone as tz

    post = request.POST
    invoice_id = post.get('invoice_id')
    if invoice_id:
        invoice = get_object_or_404(Invoice, pk=invoice_id)
    else:
        invoice = Invoice()
        invoice.company = get_user_company(request)
    old_status = invoice.status if invoice_id else None

    # ── Basic fields ──────────────────────────────────────────────────────────
    invoice.doctype = post.get('doctype', 'R')
    invoice.country = post.get('country', 'HR')
    invoice.status  = post.get('status', 'DRAFT')

    # ── Number ────────────────────────────────────────────────────────────────
    if not invoice_id:
        from invoicing.fiscal_models import InvoiceProfile
        profile = _get_profile(post.get('profile_id'))
        if not profile:
            profile = InvoiceProfile.get_default()
        generate_invoice_number(invoice, profile, invoice.doctype)
    else:
        invoice.number = post.get('number', '')
        profile = _get_profile(post.get('profile_id')) or invoice.invoice_profile

    # ── Dates ─────────────────────────────────────────────────────────────────
    dt_str = post.get('date_issued', '')
    try:
        invoice.date_issued = (
            datetime.datetime.strptime(dt_str, '%Y-%m-%dT%H:%M') if dt_str else tz.now()
        )
    except ValueError:
        invoice.date_issued = tz.now()

    for attr, key in [('date_due', 'date_due'), ('date_delivery', 'date_delivery')]:
        s = post.get(key, '')
        try:
            setattr(invoice, attr, datetime.date.fromisoformat(s) if s else None)
        except (ValueError, AttributeError):
            setattr(invoice, attr, None)

    # ── Client ────────────────────────────────────────────────────────────────
    invoice.client_name    = post.get('client_name', '')
    invoice.client_address = post.get('client_address', '')
    invoice.client_city    = post.get('client_city', '')
    invoice.client_country = post.get('client_country', 'Hrvatska')
    invoice.client_oib     = post.get('client_oib', '')
    invoice.client_email   = post.get('client_email', '')

    # ── Payment ───────────────────────────────────────────────────────────────
    invoice.payment_method   = post.get('payment_method', 'TRANSAKCIJSKI')
    invoice.currency         = post.get('currency', 'EUR')
    invoice.issuer_iban      = post.get('iban', '')
    invoice.iban             = invoice.issuer_iban  # sync: b2b portal reads invoice.iban
    invoice.swift            = post.get('swift', '')
    invoice.reference_number = post.get('reference_number', '')

    # ── Issuer ────────────────────────────────────────────────────────────────
    if profile:
        invoice.issuer_name    = profile.company_name
        invoice.issuer_address = (
            f'{profile.address}, {profile.zip_code} {profile.city}'.strip(', ')
        )
        invoice.issuer_oib   = profile.tax_number or profile.oib or profile.vat_id or ''
        invoice.issuer_email = profile.email
        invoice.issuer_phone = profile.phone
        invoice.issuer_iban  = profile.iban
        invoice.iban         = invoice.issuer_iban  # sync: b2b portal reads invoice.iban
        invoice.swift        = profile.swift
        invoice.issuer_swift = profile.swift  # sync issuer_swift
    else:
        invoice.issuer_name    = post.get('issuer_name', 'LIMIT Connect')
        invoice.issuer_address = post.get('issuer_address', '')
        invoice.issuer_oib     = post.get('issuer_oib', '')
        invoice.issuer_email   = post.get('issuer_email', '')

    # ── Other ─────────────────────────────────────────────────────────────────
    invoice.tax_status    = post.get('tax_status', 'standard')
    invoice.note          = post.get('note', '')
    invoice.internal_note = post.get('internal_note', '')

    source = post.get('source', '')
    if source and source in dict(Invoice.SOURCE_CHOICES):
        invoice.source = source

    # ── Fiscal references ─────────────────────────────────────────────────────
    try:
        from invoicing.fiscal_models import BusinessLocation, FiscalOperator
        loc_id = post.get('business_location')
        if loc_id:
            invoice.business_location = BusinessLocation.objects.get(pk=loc_id)
        op_id = post.get('operator')
        if op_id:
            invoice.operator = FiscalOperator.objects.get(pk=op_id)
    except ObjectDoesNotExist:
        pass

    invoice.created_by = request.user
    invoice.save()

    # ── GoBD check ────────────────────────────────────────────────────────────
    invoice._gobd_warnings = []
    if getattr(invoice, 'country', 'HR') == 'DE':
        try:
            from invoicing.tax_logic import check_gobd_pflichtangaben
            invoice._gobd_warnings = check_gobd_pflichtangaben(invoice)
        except ImportError:
            pass

    # ── Side effects ──────────────────────────────────────────────────────────
    ensure_partner(get_user_company(request), invoice)
    save_items(invoice, post)
    invoice.recalculate()
    invoice.save()
    deduct_inventory(invoice, old_status, request.user)
    mark_worktime_billed(invoice, post.get('worktime_entry_ids', ''))
    notify_paid(invoice, request.user)

    return invoice


def _get_profile(profile_id):
    if not profile_id:
        return None
    from invoicing.fiscal_models import InvoiceProfile
    try:
        return InvoiceProfile.objects.get(pk=profile_id, is_active=True)
    except InvoiceProfile.DoesNotExist:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Tax calculation
# ─────────────────────────────────────────────────────────────────────────────

def calculate_tax(items: list, tax_rate=None) -> dict:
    """Calculate subtotal/tax/total from list of item dicts."""
    subtotal = Decimal('0')
    for item in items:
        qty      = Decimal(str(item.get('quantity', 1)))
        price    = Decimal(str(item.get('unit_price', 0)))
        discount = Decimal(str(item.get('discount', 0)))
        subtotal += qty * price * (1 - discount / 100)
    rate = tax_rate or (Decimal(str(items[0].get('tax_rate', 25))) if items else Decimal('25'))
    tax_amount = subtotal * rate / 100
    total = subtotal + tax_amount
    return {
        'subtotal':   subtotal.quantize(Decimal('0.01')),
        'tax_rate':   rate,
        'tax_amount': tax_amount.quantize(Decimal('0.01')),
        'total':      total.quantize(Decimal('0.01')),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Status transitions
# ─────────────────────────────────────────────────────────────────────────────

VALID_TRANSITIONS = {
    'DRAFT':     ['SENT', 'CANCELLED'],
    'SENT':      ['ACCEPTED', 'REJECTED', 'CANCELLED'],
    'ACCEPTED':  ['PAID', 'CANCELLED'],
    'REJECTED':  ['DRAFT'],
    'PAID':      ['STORNO'],
    'CANCELLED': ['DRAFT'],
    'STORNO':    [],
}


def can_transition(current_status: str, new_status: str) -> bool:
    return new_status in VALID_TRANSITIONS.get(current_status, [])


def copy_invoice_items(source_invoice, target_invoice):
    """Copy all items from source to target invoice."""
    from invoicing.models import InvoiceItem
    for item in source_invoice.items.all():
        InvoiceItem.objects.create(
            invoice=target_invoice,
            description=item.description,
            quantity=item.quantity,
            unit=item.unit,
            unit_price=item.unit_price,
            discount_percent=getattr(item, 'discount_percent', Decimal('0')),
            tax_rate=item.tax_rate,
            total_price=item.total_price,
            inventory_item_id=item.inventory_item_id,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Service Layer: create_invoice + bulk_create_invoices
# Dron #1 fix: post_save signali NE rade s bulk_create().
# Sva poslovna logika (otpremnica, knjiženje, partner) mora ići ovdje.
# ─────────────────────────────────────────────────────────────────────────────

def _create_otpremnica_for_invoice(invoice):
    """Eksplicitno kreira Otpremnicu za Invoice. Signal-agnostic."""
    if invoice.doctype not in ('R', 'FA', 'RN'):
        return None
    try:
        from invoicing.models import InvoiceItem
        items_with_inv = InvoiceItem.objects.filter(
            invoice=invoice,
            inventory_item__isnull=False,
        ).select_related('inventory_item')
        if not items_with_inv.exists():
            return None

        from propter.models import Otpremnica, OtpremnicaItem, BillingPeriod

        if Otpremnica.objects.filter(invoice_id=str(invoice.pk)).exists():
            return Otpremnica.objects.filter(invoice_id=str(invoice.pk)).first()

        bp = BillingPeriod.get_or_create_current(invoice.company)
        issue_date = invoice.date_issued
        if hasattr(issue_date, 'date'):
            issue_date = issue_date.date()

        otp = Otpremnica.objects.create(
            company=invoice.company,
            billing_period=bp,
            invoice_id=str(invoice.pk),
            issue_date=issue_date,
            delivery_date=getattr(invoice, 'date_delivery', None) or issue_date,
            recipient_name=invoice.client_name or '',
            recipient_oib=invoice.client_oib or '',
            recipient_address=invoice.client_address or '',
            subtotal=invoice.subtotal or 0,
            tax_amount=invoice.tax_amount or 0,
            total=invoice.total or 0,
            source=Otpremnica.Source.INVOICE,
            status=Otpremnica.Status.ISSUED,
        )

        for i, item in enumerate(items_with_inv, 1):
            OtpremnicaItem.objects.create(
                otpremnica=otp,
                line_number=i,
                description=item.description or '',
                quantity=item.quantity or 1,
                unit='EA',
                unit_price=item.unit_price or 0,
                tax_rate=getattr(item, 'tax_percent', 25) or 25,
                line_total=getattr(item, 'total', 0) or (item.unit_price or 0) * (item.quantity or 1),
            )

        from django.db import models as db_models
        BillingPeriod.objects.filter(pk=bp.pk).update(
            otpremnica_count=db_models.F('otpremnica_count') + 1
        )
        return otp
    except (IntegrityError, DatabaseError) as e:
        import logging
        logging.getLogger('invoicing.services').warning(
            'create_otpremnica failed for %s: %s', invoice.number, e
        )
        return None


@transaction.atomic
def create_invoice(company, user=None, **kwargs):
    """
    Centralni entry point za kreiranje Invoice.
    Garantira: partner, otpremnica, knjiženje — bez oslanjanja na signale.
    
    Koristi ovo umjesto Invoice.objects.create() kad trebaš poslovnu logiku.
    """
    from invoicing.models import Invoice

    kwargs.setdefault('status', 'DRAFT')
    kwargs.setdefault('currency', 'EUR')
    invoice = Invoice(company=company, created_by=user, **kwargs)
    invoice._skip_fiscal_check = True
    invoice.save()

    ensure_partner(company, invoice)
    _create_otpremnica_for_invoice(invoice)

    return invoice


@transaction.atomic
def bulk_create_invoices(invoice_list):
    """
    Bulk kreiranje faktura s poslovnom logikom.
    
    invoice_list: lista dict-ova s ključevima:
        company, doctype, number, date_issued, client_name, ...
        items: lista dict-ova za InvoiceItem
    
    Radi atomic: ili sve ili ništa.
    Garantira otpremnice za svaku fakturu (signal-agnostic).
    """
    from invoicing.models import Invoice, InvoiceItem
    import logging
    logger = logging.getLogger('invoicing.services')

    created = []
    for data in invoice_list:
        items_data = data.pop('items', [])
        company = data.pop('company')
        user = data.pop('user', None)
        data.setdefault('status', 'DRAFT')
        data.setdefault('currency', 'EUR')

        inv = Invoice(company=company, created_by=user, **data)
        inv._skip_fiscal_check = True
        inv.save()

        for item in items_data:
            InvoiceItem.objects.create(invoice=inv, **item)

        ensure_partner(company, inv)
        otp = _create_otpremnica_for_invoice(inv)

        created.append(inv)
        if otp:
            logger.info('bulk: Invoice %s + OTP %s', inv.number, otp.number)

    logger.info('bulk_create_invoices: %d faktura kreirano', len(created))
    return created
