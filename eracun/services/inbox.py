"""
eracun/services/inbox.py
Service for receiving and processing incoming e-invoices (UBL XML).
Supports: manual upload, API, email attachment, PEPPOL/FINA webhook.
"""
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation
from xml.etree import ElementTree as ET

from django.utils import timezone

logger = logging.getLogger(__name__)

# UBL 2.1 namespaces
NS = {
    'ubl': 'urn:oasis:names:specification:ubl:schema:xsd:Invoice-2',
    'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
    'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
    'cn': 'urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2',
}


def _text(el, xpath, default=''):
    """Safe text extraction from XML element."""
    node = el.find(xpath, NS)
    return (node.text or '').strip() if node is not None else default


def _dec(el, xpath, default=Decimal('0')):
    """Safe decimal extraction."""
    val = _text(el, xpath)
    try:
        return Decimal(val) if val else default
    except (InvalidOperation, ValueError):
        return default


def parse_ubl_xml(xml_string):
    """
    Parse UBL 2.1 Invoice or CreditNote XML into a dict.

    Returns:
        dict with all invoice fields, or raises ValueError on parse error.
    """
    try:
        root = ET.fromstring(xml_string)
    except ET.ParseError as e:
        raise ValueError(f'Invalid XML: {e}')

    # Detect document type
    tag = root.tag.split('}')[-1] if '}' in root.tag else root.tag
    if tag == 'Invoice':
        doc_type = '380'
    elif tag == 'CreditNote':
        doc_type = '381'
    else:
        doc_type = '380'

    # Basic fields
    data = {
        'doc_type': doc_type,
        'invoice_number': _text(root, 'cbc:ID'),
        'issue_date': _text(root, 'cbc:IssueDate'),
        'delivery_date': _text(root, 'cbc:DueDate'),  # fallback
        'due_date': _text(root, 'cbc:DueDate'),
        'currency': _text(root, 'cbc:DocumentCurrencyCode', 'EUR'),
        'note': _text(root, 'cbc:Note'),
    }

    # Delivery date from ActualDeliveryDate
    delivery = root.find('cac:Delivery/cbc:ActualDeliveryDate', NS)
    if delivery is not None and delivery.text:
        data['delivery_date'] = delivery.text.strip()

    # Supplier (AccountingSupplierParty)
    supplier = root.find('cac:AccountingSupplierParty/cac:Party', NS)
    if supplier is not None:
        data['issuer_name'] = _text(supplier, 'cac:PartyLegalEntity/cbc:RegistrationName')
        if not data['issuer_name']:
            data['issuer_name'] = _text(supplier, 'cac:PartyName/cbc:Name')
        data['issuer_oib'] = _text(supplier, 'cac:PartyTaxScheme/cbc:CompanyID')
        # Strip country prefix (HR12345678901 -> 12345678901)
        if data['issuer_oib'] and len(data['issuer_oib']) > 11:
            data['issuer_oib'] = data['issuer_oib'][-11:]

        addr = supplier.find('cac:PostalAddress', NS)
        if addr is not None:
            street = _text(addr, 'cbc:StreetName')
            building = _text(addr, 'cbc:BuildingNumber')
            data['issuer_address'] = f'{street} {building}'.strip()
            data['issuer_city'] = _text(addr, 'cbc:CityName')
            data['issuer_postal'] = _text(addr, 'cbc:PostalZone')
            data['issuer_country'] = _text(addr, 'cac:Country/cbc:IdentificationCode', 'HR')

        # IBAN
        fin_acc = supplier.find('cac:PartyLegalEntity/../cac:FinancialAccount', NS)
        if fin_acc is None:
            fin_acc = root.find('cac:PaymentMeans/cac:PayeeFinancialAccount', NS)
        if fin_acc is not None:
            data['issuer_iban'] = _text(fin_acc, 'cbc:ID')
            data['issuer_swift'] = _text(fin_acc, 'cac:FinancialInstitutionBranch/cbc:ID')

    # Customer (AccountingCustomerParty) = us (the receiver)
    customer = root.find('cac:AccountingCustomerParty/cac:Party', NS)
    if customer is not None:
        data['recipient_name'] = _text(customer, 'cac:PartyLegalEntity/cbc:RegistrationName')
        if not data['recipient_name']:
            data['recipient_name'] = _text(customer, 'cac:PartyName/cbc:Name')
        data['recipient_oib'] = _text(customer, 'cac:PartyTaxScheme/cbc:CompanyID')
        if data['recipient_oib'] and len(data['recipient_oib']) > 11:
            data['recipient_oib'] = data['recipient_oib'][-11:]

        addr = customer.find('cac:PostalAddress', NS)
        if addr is not None:
            street = _text(addr, 'cbc:StreetName')
            building = _text(addr, 'cbc:BuildingNumber')
            data['recipient_address'] = f'{street} {building}'.strip()
            data['recipient_city'] = _text(addr, 'cbc:CityName')
            data['recipient_postal'] = _text(addr, 'cbc:PostalZone')
            data['recipient_country'] = _text(addr, 'cac:Country/cbc:IdentificationCode', 'HR')

    # Payment
    pm = root.find('cac:PaymentMeans', NS)
    if pm is not None:
        data['payment_means_code'] = _text(pm, 'cbc:PaymentMeansCode', '30')
        data['payment_reference'] = _text(pm, 'cbc:PaymentID')

    # Totals (LegalMonetaryTotal)
    totals = root.find('cac:LegalMonetaryTotal', NS)
    if totals is not None:
        data['subtotal'] = _dec(totals, 'cbc:TaxExclusiveAmount')
        data['total'] = _dec(totals, 'cbc:PayableAmount')
        data['tax_amount'] = _dec(totals, 'cbc:TaxInclusiveAmount') - data['subtotal']

    # Tax totals
    tax_summaries = []
    for tt in root.findall('cac:TaxTotal/cac:TaxSubtotal', NS):
        tax_summaries.append({
            'tax_category': _text(tt, 'cac:TaxCategory/cbc:ID', 'S'),
            'tax_rate': _dec(tt, 'cac:TaxCategory/cbc:Percent', Decimal('25')),
            'taxable_amount': _dec(tt, 'cbc:TaxableAmount'),
            'tax_amount': _dec(tt, 'cbc:TaxAmount'),
        })
    data['tax_summaries'] = tax_summaries

    # Line items
    items = []
    line_tag = 'cac:InvoiceLine' if doc_type == '380' else 'cac:CreditNoteLine'
    for idx, line in enumerate(root.findall(line_tag, NS), 1):
        qty_tag = 'cbc:InvoicedQuantity' if doc_type == '380' else 'cbc:CreditedQuantity'
        qty_el = line.find(qty_tag, NS)
        unit_code = qty_el.get('unitCode', 'EA') if qty_el is not None else 'EA'

        item = {
            'line_number': idx,
            'description': _text(line, 'cac:Item/cbc:Name'),
            'quantity': _dec(line, qty_tag, Decimal('1')),
            'unit_code': unit_code,
            'unit_price': _dec(line, 'cac:Price/cbc:PriceAmount'),
            'line_total': _dec(line, 'cbc:LineExtensionAmount'),
            'tax_category': _text(line, 'cac:Item/cac:ClassifiedTaxCategory/cbc:ID', 'S'),
            'tax_rate': _dec(line, 'cac:Item/cac:ClassifiedTaxCategory/cbc:Percent', Decimal('25')),
        }

        # Discount
        allowance = line.find('cac:AllowanceCharge', NS)
        if allowance is not None and _text(allowance, 'cbc:ChargeIndicator') == 'false':
            item['discount_percent'] = _dec(allowance, 'cbc:MultiplierFactorNumeric')
        else:
            item['discount_percent'] = Decimal('0')

        items.append(item)

    data['items'] = items

    return data


def receive_eracun(company, xml_string, received_via='upload', user=None):
    """
    Process an incoming e-invoice XML.

    Args:
        company: Company that is RECEIVING this invoice
        xml_string: UBL XML string
        received_via: 'upload', 'api', 'email', 'peppol', 'fina'
        user: User who triggered the import

    Returns:
        dict: {success: bool, eracun: ERacun, message: str}
    """
    from eracun.models import ERacun, ERacunItem, ERacunLog, ERacunTaxSummary

    try:
        data = parse_ubl_xml(xml_string)
    except ValueError as e:
        return {'success': False, 'error': f'XML parse error: {e}'}

    # Check for duplicate
    existing = ERacun.objects.filter(
        company=company,
        direction='incoming',
        invoice_number=data['invoice_number'],
        issuer_oib=data.get('issuer_oib', ''),
    ).first()

    if existing:
        return {
            'success': False,
            'error': f'Duplicate: e-Racun {data["invoice_number"]} od {data.get("issuer_name", "?")} vec postoji',
            'eracun': existing,
        }

    # Parse dates
    def _parse_date(ds):
        if not ds:
            return None
        for fmt in ('%Y-%m-%d', '%d.%m.%Y', '%m/%d/%Y'):
            try:
                return datetime.strptime(ds, fmt).date()
            except ValueError:
                continue
        return None

    # Create ERacun
    eracun = ERacun.objects.create(
        company=company,
        direction='incoming',
        doc_type=data.get('doc_type', '380'),
        invoice_number=data['invoice_number'],
        issue_date=_parse_date(data.get('issue_date')) or timezone.now().date(),
        delivery_date=_parse_date(data.get('delivery_date')),
        due_date=_parse_date(data.get('due_date')),
        currency=data.get('currency', 'EUR'),

        issuer_name=data.get('issuer_name', ''),
        issuer_oib=data.get('issuer_oib', ''),
        issuer_address=data.get('issuer_address', ''),
        issuer_city=data.get('issuer_city', ''),
        issuer_postal=data.get('issuer_postal', ''),
        issuer_country=data.get('issuer_country', 'HR'),
        issuer_iban=data.get('issuer_iban', ''),
        issuer_swift=data.get('issuer_swift', ''),

        recipient_name=data.get('recipient_name', company.name),
        recipient_oib=data.get('recipient_oib', company.oib),
        recipient_address=data.get('recipient_address', ''),
        recipient_city=data.get('recipient_city', ''),
        recipient_postal=data.get('recipient_postal', ''),
        recipient_country=data.get('recipient_country', 'HR'),

        subtotal=data.get('subtotal', Decimal('0')),
        tax_amount=data.get('tax_amount', Decimal('0')),
        total=data.get('total', Decimal('0')),

        payment_means_code=data.get('payment_means_code', '30'),
        payment_reference=data.get('payment_reference', ''),
        note=data.get('note', ''),

        status='accepted',
        original_xml=xml_string,
        received_at=timezone.now(),
        received_via=received_via,
        created_by=user,
    )

    # Create line items
    for item_data in data.get('items', []):
        ERacunItem.objects.create(
            eracun=eracun,
            line_number=item_data.get('line_number', 1),
            description=item_data.get('description', ''),
            quantity=item_data.get('quantity', Decimal('1')),
            unit_code=item_data.get('unit_code', 'EA'),
            unit_price=item_data.get('unit_price', Decimal('0')),
            discount_percent=item_data.get('discount_percent', Decimal('0')),
            line_total=item_data.get('line_total', Decimal('0')),
            tax_category=item_data.get('tax_category', 'S'),
            tax_rate=item_data.get('tax_rate', Decimal('25')),
        )

    # Create tax summaries
    for ts in data.get('tax_summaries', []):
        ERacunTaxSummary.objects.create(
            eracun=eracun,
            tax_category=ts.get('tax_category', 'S'),
            tax_rate=ts.get('tax_rate', Decimal('25')),
            taxable_amount=ts.get('taxable_amount', Decimal('0')),
            tax_amount=ts.get('tax_amount', Decimal('0')),
        )

    # Audit log
    ERacunLog.objects.create(
        eracun=eracun,
        action='received',
        status='accepted',
        message=f'Primljen e-Racun {eracun.invoice_number} od {eracun.issuer_name}',
        details={
            'via': received_via,
            'items': len(data.get('items', [])),
            'total': str(eracun.total),
        },
        user=user,
    )

    logger.info(f'eRacun inbox: {eracun.invoice_number} from {eracun.issuer_name} ({eracun.total} {eracun.currency})')

    # ── FENIX B2B Interceptor: async scan za rizike i olakšice ───────
    try:
        from limit_connect_ai.tasks import fenix_intercept_incoming
        fenix_intercept_incoming.delay(str(eracun.pk))
    except ImportError as e:
        logger.debug('FENIX intercept trigger skipped: %s', e)

    return {
        'success': True,
        'eracun': eracun,
        'message': f'Primljen e-Racun {eracun.invoice_number} od {eracun.issuer_name} ({eracun.total} EUR)',
    }
