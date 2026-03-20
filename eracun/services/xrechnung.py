"""
eracun/services/xrechnung.py
XRechnung (CII) generator for German e-invoicing.
EN 16931 compliant, CIUS-DE profile.

Germany requires CII (Cross Industry Invoice) format, NOT UBL.
XRechnung is the German CIUS (Core Invoice Usage Specification).
ZUGFeRD 2.x embeds CII XML inside a PDF/A-3.
"""
import xml.etree.ElementTree as ET
from xml.dom import minidom
from decimal import Decimal
from datetime import date
import logging

logger = logging.getLogger(__name__)

# CII Namespaces
RSM = 'urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100'
RAM = 'urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100'
QDT = 'urn:un:unece:uncefact:data:standard:QualifiedDataType:100'
UDT = 'urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100'

NSMAP = {
    'rsm': RSM,
    'ram': RAM,
    'qdt': QDT,
    'udt': UDT,
}

# XRechnung profile
XRECHNUNG_ID = 'urn:cen.eu:en16931:2017#compliant#urn:xeinkauf.de:kosit:xrechnung_3.0'
PROCESS_ID = 'urn:fdc:peppol.eu:2017:poacc:billing:01:1.0'


def _el(parent, tag, text=None, **attrs):
    """Create subelement with optional text and attributes."""
    ns, local = tag.split(':') if ':' in tag else ('rsm', tag)
    full_tag = f'{{{NSMAP[ns]}}}{local}'
    el = ET.SubElement(parent, full_tag)
    if text is not None:
        el.text = str(text)
    for k, v in attrs.items():
        el.set(k, str(v))
    return el


def _date_fmt(d):
    """Format date as CCYYMMDD (CII format)."""
    if isinstance(d, date):
        return d.strftime('%Y%m%d')
    if isinstance(d, str) and len(d) >= 10:
        return d[:10].replace('-', '')
    return ''


def generate_xrechnung(eracun):
    """
    Generate XRechnung CII XML from ERacun instance.
    Returns XML string.
    """
    # Register namespaces
    for prefix, uri in NSMAP.items():
        ET.register_namespace(prefix, uri)

    root = ET.Element(f'{{{RSM}}}CrossIndustryInvoice')

    # ── ExchangedDocumentContext ──
    ctx = _el(root, 'rsm:ExchangedDocumentContext')
    bp = _el(ctx, 'ram:BusinessProcessSpecifiedDocumentContextParameter')
    _el(bp, 'ram:ID', PROCESS_ID)
    gl = _el(ctx, 'ram:GuidelineSpecifiedDocumentContextParameter')
    _el(gl, 'ram:ID', XRECHNUNG_ID)

    # ── ExchangedDocument ──
    doc = _el(root, 'rsm:ExchangedDocument')
    _el(doc, 'ram:ID', eracun.invoice_number)
    # TypeCode: 380=Invoice, 381=CreditNote
    type_map = {'380': '380', '381': '381', '383': '383', '386': '386'}
    _el(doc, 'ram:TypeCode', type_map.get(eracun.doc_type, '380'))
    dt = _el(doc, 'ram:IssueDateTime')
    _el(dt, 'udt:DateTimeString', _date_fmt(eracun.issue_date), format='102')
    if eracun.note:
        inc = _el(doc, 'ram:IncludedNote')
        _el(inc, 'ram:Content', eracun.note)

    # ── SupplyChainTradeTransaction ──
    txn = _el(root, 'rsm:SupplyChainTradeTransaction')

    # ── Line Items ──
    for item in eracun.items.all().order_by('line_number'):
        li = _el(txn, 'ram:IncludedSupplyChainTradeLineItem')

        # Line doc
        line_doc = _el(li, 'ram:AssociatedDocumentLineDocument')
        _el(line_doc, 'ram:LineID', str(item.line_number))

        # Product
        prod = _el(li, 'ram:SpecifiedTradeProduct')
        _el(prod, 'ram:Name', item.description)
        # KPD/Classification
        kpd = getattr(item, 'kpd_code', '') or getattr(item, 'classification_code', '')
        if kpd:
            cls = _el(prod, 'ram:DesignatedProductClassification')
            cc = _el(cls, 'ram:ClassCode', kpd, listID='IB')  # IB = buyer classification

        # Line agreement
        agr = _el(li, 'ram:SpecifiedLineTradeAgreement')
        net_price = _el(agr, 'ram:NetPriceProductTradePrice')
        _el(net_price, 'ram:ChargeAmount', f'{item.unit_price:.4f}')

        # Line delivery
        dlv = _el(li, 'ram:SpecifiedLineTradeDelivery')
        _el(dlv, 'ram:BilledQuantity', f'{item.quantity:.3f}', unitCode=item.unit_code or 'EA')

        # Line settlement
        stl = _el(li, 'ram:SpecifiedLineTradeSettlement')
        tax = _el(stl, 'ram:ApplicableTradeTax')
        _el(tax, 'ram:TypeCode', 'VAT')
        cat = item.tax_category if item.tax_category in ('S', 'Z', 'E', 'AE', 'K', 'G', 'O') else 'S'
        _el(tax, 'ram:CategoryCode', cat)
        _el(tax, 'ram:RateApplicablePercent', f'{item.tax_rate:.2f}')

        monetary = _el(stl, 'ram:SpecifiedTradeSettlementLineMonetarySummation')
        _el(monetary, 'ram:LineTotalAmount', f'{item.line_total:.2f}')

    # ── HeaderTradeAgreement (Seller + Buyer) ──
    agr = _el(txn, 'ram:ApplicableHeaderTradeAgreement')

    # Seller (Verkaeufer)
    seller = _el(agr, 'ram:SellerTradeParty')
    _el(seller, 'ram:Name', eracun.issuer_name)
    if eracun.issuer_oib:
        # German tax number (Steuernummer) or VAT ID
        tax_id = _el(seller, 'ram:SpecifiedTaxRegistration')
        is_vat = eracun.issuer_oib.startswith('DE')
        _el(tax_id, 'ram:ID', eracun.issuer_oib, schemeID='VA' if is_vat else 'FC')

    seller_addr = _el(seller, 'ram:PostalTradeAddress')
    if eracun.issuer_address:
        _el(seller_addr, 'ram:LineOne', eracun.issuer_address)
    if eracun.issuer_postal:
        _el(seller_addr, 'ram:PostcodeCode', eracun.issuer_postal)
    if eracun.issuer_city:
        _el(seller_addr, 'ram:CityName', eracun.issuer_city)
    _el(seller_addr, 'ram:CountryID', eracun.issuer_country or 'DE')

    # Buyer (Kaeufer)
    buyer = _el(agr, 'ram:BuyerTradeParty')
    _el(buyer, 'ram:Name', eracun.recipient_name)
    if eracun.recipient_oib:
        tax_id = _el(buyer, 'ram:SpecifiedTaxRegistration')
        is_vat = eracun.recipient_oib.startswith('DE') or len(eracun.recipient_oib) > 11
        _el(tax_id, 'ram:ID', eracun.recipient_oib, schemeID='VA' if is_vat else 'FC')

    buyer_addr = _el(buyer, 'ram:PostalTradeAddress')
    if eracun.recipient_address:
        _el(buyer_addr, 'ram:LineOne', eracun.recipient_address)
    if eracun.recipient_postal:
        _el(buyer_addr, 'ram:PostcodeCode', eracun.recipient_postal)
    if eracun.recipient_city:
        _el(buyer_addr, 'ram:CityName', eracun.recipient_city)
    _el(buyer_addr, 'ram:CountryID', eracun.recipient_country or 'DE')

    # ── HeaderTradeDelivery ──
    dlv = _el(txn, 'ram:ApplicableHeaderTradeDelivery')
    if eracun.delivery_date:
        occ = _el(dlv, 'ram:ActualDeliverySupplyChainEvent')
        occ_dt = _el(occ, 'ram:OccurrenceDateTime')
        _el(occ_dt, 'udt:DateTimeString', _date_fmt(eracun.delivery_date), format='102')

    # ── HeaderTradeSettlement ──
    stl = _el(txn, 'ram:ApplicableHeaderTradeSettlement')
    _el(stl, 'ram:InvoiceCurrencyCode', eracun.currency or 'EUR')

    # Payment means
    pm = _el(stl, 'ram:SpecifiedTradeSettlementPaymentMeans')
    _el(pm, 'ram:TypeCode', eracun.payment_means_code or '58')  # 58=SEPA
    if eracun.issuer_iban:
        acct = _el(pm, 'ram:PayeePartyDebtorFinancialAccount')
        _el(acct, 'ram:IBANID', eracun.issuer_iban)
        if eracun.issuer_swift:
            inst = _el(pm, 'ram:PayeeSpecifiedCreditorFinancialInstitution')
            _el(inst, 'ram:BICID', eracun.issuer_swift)

    # Tax summary
    for ts in eracun.tax_summaries.all():
        tax = _el(stl, 'ram:ApplicableTradeTax')
        _el(tax, 'ram:CalculatedAmount', f'{ts.tax_amount:.2f}')
        _el(tax, 'ram:TypeCode', 'VAT')
        _el(tax, 'ram:BasisAmount', f'{ts.taxable_amount:.2f}')
        cat = ts.tax_category if ts.tax_category in ('S', 'Z', 'E', 'AE') else 'S'
        _el(tax, 'ram:CategoryCode', cat)
        _el(tax, 'ram:RateApplicablePercent', f'{ts.tax_rate:.2f}')

    # Payment terms
    if eracun.due_date:
        pt = _el(stl, 'ram:SpecifiedTradePaymentTerms')
        dd = _el(pt, 'ram:DueDateDateTime')
        _el(dd, 'udt:DateTimeString', _date_fmt(eracun.due_date), format='102')

    # Monetary totals
    totals = _el(stl, 'ram:SpecifiedTradeSettlementHeaderMonetarySummation')
    _el(totals, 'ram:LineTotalAmount', f'{eracun.subtotal:.2f}')
    _el(totals, 'ram:TaxBasisTotalAmount', f'{eracun.subtotal:.2f}')
    tax_total = _el(totals, 'ram:TaxTotalAmount', f'{eracun.tax_amount:.2f}')
    tax_total.set('currencyID', eracun.currency or 'EUR')
    _el(totals, 'ram:GrandTotalAmount', f'{eracun.total:.2f}')
    _el(totals, 'ram:DuePayableAmount', f'{eracun.total:.2f}')

    # Serialize
    raw = ET.tostring(root, encoding='unicode', xml_declaration=False)
    xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n' + raw

    try:
        dom = minidom.parseString(xml_str)
        xml_str = dom.toprettyxml(indent='  ', encoding=None)
        if isinstance(xml_str, bytes):
            xml_str = xml_str.decode('utf-8')
        # Remove extra xml declaration from toprettyxml
        if xml_str.count('<?xml') > 1:
            xml_str = xml_str.replace('<?xml version="1.0" ?>\n', '', 1)
    except Exception:
        pass

    return xml_str
