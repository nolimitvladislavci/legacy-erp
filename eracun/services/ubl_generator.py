"""
UBL 2.1 / EN 16931 compliant XML generator for Croatian e-Račun.

Generates XML per:
- EU Standard EN 16931-1:2017
- PEPPOL BIS Billing 3.0 (cross-border)
- Croatian CIUS-2025 (domestic B2B/B2G per NN 89/25)
- HR Extension urn:mfin.gov.hr:ext-2025:1.0
"""
from lxml import etree
from decimal import Decimal

# Namespaces
NS = {
    'ubl': 'urn:oasis:names:specification:ubl:schema:xsd:Invoice-2',
    'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
    'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
    'ccts': 'urn:un:unece:uncefact:documentation:2',
    'ext': 'urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2',
}

# ── Customization IDs per NN 89/25 ──────────────────────────────
# Domaći B2B/B2G (HR CIUS-2025 + HR Extension)
CIUS_HR_2025 = (
    'urn:cen.eu:en16931:2017'
    '#compliant#urn:mfin.gov.hr:cius-2025:1.0'
    '#conformant#urn:mfin.gov.hr:ext-2025:1.0'
)
PROFILE_HR_2025 = 'urn:mfin.gov.hr:profile:hr-eracun:1.0'

# Cross-border / PEPPOL
CIUS_PEPPOL = (
    'urn:cen.eu:en16931:2017'
    '#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0'
)
PROFILE_PEPPOL = 'urn:fdc:peppol.eu:2017:poacc:billing:01:1.0'

# Payment means mapping
PAYMENT_MEANS_MAP = {
    'T': '30',   # Transakcijski racun / Credit transfer
    'G': '10',   # Gotovina / Cash
    'K': '48',   # Kartica / Bank card
    'C': '30',   # Virman / Credit transfer
    'O': '1',    # Ostalo / Not defined
}

# Unit code mapping from Croatian to UN/ECE Rec 20
UNIT_MAP = {
    'kom': 'EA', 'komad': 'EA', 'pcs': 'EA',
    'sat': 'HUR', 'h': 'HUR', 'hr': 'HUR',
    'kg': 'KGM', 'kilogram': 'KGM',
    'm': 'MTR', 'metar': 'MTR',
    'l': 'LTR', 'litra': 'LTR',
    'm2': 'MTK', 'kvm': 'MTK',
    'dan': 'DAY', 'day': 'DAY',
    'mj': 'MON', 'mjesec': 'MON',
    'set': 'SET', 'pak': 'XPK',
}


def _el(parent, ns_tag, text=None, **attrs):
    """Helper to create subelement with namespace."""
    parts = ns_tag.split(':')
    if len(parts) == 2:
        ns_prefix, tag = parts
        full_tag = f"{{{NS[ns_prefix]}}}{tag}"
    else:
        full_tag = ns_tag
    el = etree.SubElement(parent, full_tag, **attrs)
    if text is not None:
        el.text = str(text)
    return el


def map_unit_code(unit):
    """Map Croatian unit names to UN/ECE Recommendation 20 codes."""
    if not unit:
        return 'EA'
    code = UNIT_MAP.get(unit.lower().strip(), unit.upper().strip())
    return code if len(code) <= 5 else 'EA'


def _is_domestic_hr(eracun):
    """Check if both issuer and recipient are HR — use CIUS-2025."""
    return (
        getattr(eracun, 'issuer_country', 'HR') == 'HR'
        and getattr(eracun, 'recipient_country', 'HR') == 'HR'
    )


def generate_ubl_xml(eracun, on_behalf_of_oib=None, mandate_id=None):
    """
    Generate EN 16931 compliant UBL 2.1 Invoice XML.

    Automatically selects:
      - CIUS-2025 (HR domestic B2B/B2G) when both parties are HR
      - PEPPOL BIS 3.0 for cross-border

    Args:
        eracun: ERacun model instance with related items and tax_summaries

    Returns:
        bytes: UTF-8 encoded XML
    """
    nsmap = {
        None: NS['ubl'],
        'cac': NS['cac'],
        'cbc': NS['cbc'],
    }

    domestic = _is_domestic_hr(eracun)

    root = etree.Element(f"{{{NS['ubl']}}}Invoice", nsmap=nsmap)

    # ── BT-24: CustomizationID ──────────────────────────────────
    _el(root, 'cbc:CustomizationID', CIUS_HR_2025 if domestic else CIUS_PEPPOL)

    # ── BT-23: ProfileID ────────────────────────────────────────
    _el(root, 'cbc:ProfileID', PROFILE_HR_2025 if domestic else PROFILE_PEPPOL)

    # ── BT-1: Invoice number ────────────────────────────────────
    _el(root, 'cbc:ID', eracun.invoice_number)

    # ── BT-2: Issue date ────────────────────────────────────────
    _el(root, 'cbc:IssueDate', eracun.issue_date.strftime('%Y-%m-%d'))

    # ── BT-9: Due date ──────────────────────────────────────────
    if eracun.due_date:
        _el(root, 'cbc:DueDate', eracun.due_date.strftime('%Y-%m-%d'))

    # ── BT-3: Invoice type code ─────────────────────────────────
    _el(root, 'cbc:InvoiceTypeCode', eracun.doc_type)

    # ── BT-22: Note (ZKI/JIR za fiskalizaciju) ─────────────────
    notes = []
    if eracun.note:
        notes.append(eracun.note)
    if eracun.zki:
        notes.append(f'ZKI: {eracun.zki}')
    if eracun.jir:
        notes.append(f'JIR: {eracun.jir}')
    if notes:
        _el(root, 'cbc:Note', ' | '.join(notes))

    # ── BT-5: Currency ──────────────────────────────────────────
    _el(root, 'cbc:DocumentCurrencyCode', eracun.currency)

    # ── BT-10: BuyerReference (obavezan za B2G, korisno za B2B) ─
    buyer_ref = getattr(eracun, 'buyer_reference', '') or ''
    if not buyer_ref and getattr(eracun, 'payment_reference', ''):
        buyer_ref = eracun.payment_reference
    if buyer_ref:
        _el(root, 'cbc:BuyerReference', buyer_ref)
    elif domestic:
        # CIUS-2025: BT-10 obavezan, stavimo N/A ako nema
        _el(root, 'cbc:BuyerReference', 'N/A')

    # ── BT-13: OrderReference (broj narudžbe kupca) ─────────────
    order_ref = getattr(eracun, 'order_reference', '') or ''
    if order_ref:
        oref = _el(root, 'cac:OrderReference')
        _el(oref, 'cbc:ID', order_ref)

    # ── BT-7: Tax point date / Invoice period ───────────────────
    if eracun.delivery_date:
        tax_point = _el(root, 'cac:InvoicePeriod')
        _el(tax_point, 'cbc:StartDate', eracun.delivery_date.strftime('%Y-%m-%d'))
        _el(tax_point, 'cbc:EndDate', eracun.delivery_date.strftime('%Y-%m-%d'))

    # ═══════════════════════════════════════════════════════════
    # Mandate reference (posrednik šalje u ime klijenta)
    if on_behalf_of_oib and mandate_id:
        adr = _el(root, 'cac:AdditionalDocumentReference')
        _el(adr, 'cbc:ID', f'MANDATE-{mandate_id}')
        _el(adr, 'cbc:DocumentTypeCode', '130')
        _el(adr, 'cbc:DocumentDescription',
            f'Informacijski posrednik, OIB opunomoćitelja: {on_behalf_of_oib}')

    # BG-4: Seller / AccountingSupplierParty
    # ═══════════════════════════════════════════════════════════
    supplier_party = _el(root, 'cac:AccountingSupplierParty')
    party = _el(supplier_party, 'cac:Party')

    # BT-29: Seller electronic address (CIUS-2025 obavezan)
    if domestic:
        ep = _el(party, 'cbc:EndpointID', eracun.issuer_oib, schemeID='0192')

    # BT-30: Seller ID
    pid = _el(party, 'cac:PartyIdentification')
    _el(pid, 'cbc:ID', eracun.issuer_oib, schemeID='0192')  # 0192 = HR:OIB

    # BT-27: Seller name
    pname = _el(party, 'cac:PartyName')
    _el(pname, 'cbc:Name', eracun.issuer_name)

    # BG-5: Seller address
    addr = _el(party, 'cac:PostalAddress')
    if eracun.issuer_address:
        _el(addr, 'cbc:StreetName', eracun.issuer_address)
    if eracun.issuer_city:
        _el(addr, 'cbc:CityName', eracun.issuer_city)
    if eracun.issuer_postal:
        _el(addr, 'cbc:PostalZone', eracun.issuer_postal)
    country = _el(addr, 'cac:Country')
    _el(country, 'cbc:IdentificationCode', eracun.issuer_country)

    # BT-31: Seller VAT identifier
    tax_scheme = _el(party, 'cac:PartyTaxScheme')
    _el(tax_scheme, 'cbc:CompanyID', f'HR{eracun.issuer_oib}')
    ts = _el(tax_scheme, 'cac:TaxScheme')
    _el(ts, 'cbc:ID', 'VAT')

    # BT-30: Seller legal entity
    legal = _el(party, 'cac:PartyLegalEntity')
    _el(legal, 'cbc:RegistrationName', eracun.issuer_name)
    _el(legal, 'cbc:CompanyID', eracun.issuer_oib, schemeID='0192')

    # ═══════════════════════════════════════════════════════════
    # BG-7: Buyer / AccountingCustomerParty
    # ═══════════════════════════════════════════════════════════
    customer_party = _el(root, 'cac:AccountingCustomerParty')
    cparty = _el(customer_party, 'cac:Party')

    # BT-49: Buyer electronic address (CIUS-2025 obavezan)
    if domestic:
        _el(cparty, 'cbc:EndpointID', eracun.recipient_oib, schemeID='0192')

    cpid = _el(cparty, 'cac:PartyIdentification')
    _el(cpid, 'cbc:ID', eracun.recipient_oib, schemeID='0192')

    cpname = _el(cparty, 'cac:PartyName')
    _el(cpname, 'cbc:Name', eracun.recipient_name)

    caddr = _el(cparty, 'cac:PostalAddress')
    if eracun.recipient_address:
        _el(caddr, 'cbc:StreetName', eracun.recipient_address)
    if eracun.recipient_city:
        _el(caddr, 'cbc:CityName', eracun.recipient_city)
    if eracun.recipient_postal:
        _el(caddr, 'cbc:PostalZone', eracun.recipient_postal)
    ccountry = _el(caddr, 'cac:Country')
    _el(ccountry, 'cbc:IdentificationCode', eracun.recipient_country)

    ctax = _el(cparty, 'cac:PartyTaxScheme')
    prefix = 'HR' if eracun.recipient_country == 'HR' else ''
    _el(ctax, 'cbc:CompanyID', f'{prefix}{eracun.recipient_oib}')
    cts = _el(ctax, 'cac:TaxScheme')
    _el(cts, 'cbc:ID', 'VAT')

    clegal = _el(cparty, 'cac:PartyLegalEntity')
    _el(clegal, 'cbc:RegistrationName', eracun.recipient_name)
    _el(clegal, 'cbc:CompanyID', eracun.recipient_oib, schemeID='0192')

    # ═══════════════════════════════════════════════════════════
    # BG-16: Payment means
    # ═══════════════════════════════════════════════════════════
    pm = _el(root, 'cac:PaymentMeans')
    _el(pm, 'cbc:PaymentMeansCode', eracun.payment_means_code)

    # BT-83: Payment ID / Poziv na broj (HR CIUS-2025)
    pay_ref = getattr(eracun, 'payment_reference', '') or ''
    pay_model = getattr(eracun, 'payment_model', '') or ''
    if pay_ref:
        # HR format: MODEL-POZIVNABROJ (npr. HR00-12345-67890)
        full_ref = f'{pay_model}-{pay_ref}' if pay_model else pay_ref
        _el(pm, 'cbc:PaymentID', full_ref)

    if eracun.issuer_iban:
        payee = _el(pm, 'cac:PayeeFinancialAccount')
        _el(payee, 'cbc:ID', eracun.issuer_iban)
        if eracun.issuer_swift:
            branch = _el(payee, 'cac:FinancialInstitutionBranch')
            _el(branch, 'cbc:ID', eracun.issuer_swift)

    # ═══════════════════════════════════════════════════════════
    # BG-17: Payment terms
    # ═══════════════════════════════════════════════════════════
    if eracun.due_date:
        pt = _el(root, 'cac:PaymentTerms')
        days = (eracun.due_date - eracun.issue_date).days
        _el(pt, 'cbc:Note', f'Rok placanja: {days} dana' if days > 0 else 'Placanje odmah')

    # ═══════════════════════════════════════════════════════════
    # BG-23: Tax totals
    # ═══════════════════════════════════════════════════════════
    tax_total = _el(root, 'cac:TaxTotal')
    _el(tax_total, 'cbc:TaxAmount', f'{eracun.tax_amount:.2f}', currencyID=eracun.currency)

    tax_summaries = eracun.tax_summaries.all()
    if tax_summaries.exists():
        for ts_obj in tax_summaries:
            subtotal = _el(tax_total, 'cac:TaxSubtotal')
            _el(subtotal, 'cbc:TaxableAmount', f'{ts_obj.taxable_amount:.2f}', currencyID=eracun.currency)
            _el(subtotal, 'cbc:TaxAmount', f'{ts_obj.tax_amount:.2f}', currencyID=eracun.currency)
            cat = _el(subtotal, 'cac:TaxCategory')
            _el(cat, 'cbc:ID', ts_obj.tax_category)
            _el(cat, 'cbc:Percent', f'{ts_obj.tax_rate:.2f}')
            scheme = _el(cat, 'cac:TaxScheme')
            _el(scheme, 'cbc:ID', 'VAT')
    else:
        subtotal = _el(tax_total, 'cac:TaxSubtotal')
        _el(subtotal, 'cbc:TaxableAmount', f'{eracun.subtotal:.2f}', currencyID=eracun.currency)
        _el(subtotal, 'cbc:TaxAmount', f'{eracun.tax_amount:.2f}', currencyID=eracun.currency)
        cat = _el(subtotal, 'cac:TaxCategory')
        _el(cat, 'cbc:ID', 'S')
        rate = Decimal('0')
        if eracun.subtotal and eracun.subtotal > 0:
            rate = (eracun.tax_amount / eracun.subtotal * 100).quantize(Decimal('0.01'))
        _el(cat, 'cbc:Percent', f'{rate:.2f}')
        scheme = _el(cat, 'cac:TaxScheme')
        _el(scheme, 'cbc:ID', 'VAT')

    # ═══════════════════════════════════════════════════════════
    # BG-22: Legal monetary totals
    # ═══════════════════════════════════════════════════════════
    lmt = _el(root, 'cac:LegalMonetaryTotal')
    _el(lmt, 'cbc:LineExtensionAmount', f'{eracun.subtotal:.2f}', currencyID=eracun.currency)
    _el(lmt, 'cbc:TaxExclusiveAmount', f'{eracun.subtotal:.2f}', currencyID=eracun.currency)
    _el(lmt, 'cbc:TaxInclusiveAmount', f'{eracun.total:.2f}', currencyID=eracun.currency)
    _el(lmt, 'cbc:PayableAmount', f'{eracun.total:.2f}', currencyID=eracun.currency)

    # ═══════════════════════════════════════════════════════════
    # BG-25: Invoice lines
    # ═══════════════════════════════════════════════════════════
    items = eracun.items.all()
    for item in items:
        line = _el(root, 'cac:InvoiceLine')
        _el(line, 'cbc:ID', str(item.line_number))
        _el(line, 'cbc:InvoicedQuantity', f'{item.quantity:.3f}', unitCode=item.unit_code)
        _el(line, 'cbc:LineExtensionAmount', f'{item.line_total:.2f}', currencyID=eracun.currency)

        # BG-30: Line item
        li = _el(line, 'cac:Item')
        _el(li, 'cbc:Name', item.description)

        # BT-151: Classified tax category
        tc = _el(li, 'cac:ClassifiedTaxCategory')
        _el(tc, 'cbc:ID', item.tax_category)
        _el(tc, 'cbc:Percent', f'{item.tax_rate:.2f}')
        tcs = _el(tc, 'cac:TaxScheme')
        _el(tcs, 'cbc:ID', 'VAT')

        # Classification (KPD/NKD)
        if item.classification_code:
            cic = _el(li, 'cac:CommodityClassification')
            _el(cic, 'cbc:ItemClassificationCode', item.classification_code, listID='CG')

        # BG-29: Price
        price = _el(line, 'cac:Price')
        _el(price, 'cbc:PriceAmount', f'{item.unit_price:.4f}', currencyID=eracun.currency)

    # Serialize
    xml_bytes = etree.tostring(
        root,
        pretty_print=True,
        xml_declaration=True,
        encoding='UTF-8',
    )
    return xml_bytes
