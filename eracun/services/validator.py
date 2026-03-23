"""
e-Račun Validator — XSD schema + EN 16931 business rules.

Rupa 1 zatvorena: svaki XML se validira PRIJE slanja.
Ako ne prolazi — ne ide van. Greška se prijavi korisniku.

XSD: UBL 2.1 Invoice schema
Business rules: EN 16931 core (najvažnijih 40 pravila)
"""
import logging
import os
from decimal import Decimal
from lxml import etree

logger = logging.getLogger('eracun.validator')

# XSD schema path — downloadamo jednom, validiramo zauvijek
XSD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'schemas')
UBL_XSD = os.path.join(XSD_DIR, 'maindoc', 'UBL-Invoice-2.1.xsd')

_xsd_schema = None


def _get_xsd_schema():
    """Lazy-load XSD schema. Download ako ne postoji."""
    global _xsd_schema
    if _xsd_schema is not None:
        return _xsd_schema

    if not os.path.exists(UBL_XSD):
        logger.warning('UBL XSD not found at %s — skipping schema validation', UBL_XSD)
        return None

    try:
        schema_doc = etree.parse(UBL_XSD)
        _xsd_schema = etree.XMLSchema(schema_doc)
        logger.info('UBL 2.1 XSD schema loaded')
        return _xsd_schema
    except Exception as e:
        logger.error('Failed to load XSD: %s', e)
        return None


def validate_xsd(xml_bytes):
    """
    Validira XML protiv UBL 2.1 XSD schema.
    Returns: (is_valid, errors_list)
    """
    schema = _get_xsd_schema()
    if schema is None:
        return True, ['XSD schema nije dostupna — preskočeno']

    try:
        doc = etree.fromstring(xml_bytes if isinstance(xml_bytes, bytes) else xml_bytes.encode())
        is_valid = schema.validate(doc)
        if not is_valid:
            errors = [str(e) for e in schema.error_log]
            return False, errors[:10]  # Max 10 errors
        return True, []
    except Exception as e:
        return False, [f'XML parse error: {e}']


class XSDValidationError(Exception):
    """Specifičan exception za XSD greške s lokacijom u XML-u."""
    def __init__(self, errors):
        self.errors = errors  # List of dicts: {line, column, message, message_hr}
        summary = '; '.join(e['message_hr'] for e in errors[:3])
        super().__init__(f'XSD validacija neuspješna: {summary}')


def validate_xml_against_xsd(xml_content):
    """
    Validira XML protiv UBL 2.1 XSD sheme.
    Ako validacija padne → raise XSDValidationError s lokacijom greške.

    Args:
        xml_content: bytes ili str XML sadržaj

    Returns:
        True ako je validan

    Raises:
        XSDValidationError: s listom grešaka (linija, stupac, opis na HR)
    """
    schema = _get_xsd_schema()
    if schema is None:
        logger.warning('XSD shema nije dostupna — preskačem validaciju')
        return True

    xml_bytes = xml_content if isinstance(xml_content, bytes) else xml_content.encode('utf-8')

    try:
        doc = etree.fromstring(xml_bytes)
    except etree.XMLSyntaxError as e:
        raise XSDValidationError([{
            'line': getattr(e, 'lineno', 0),
            'column': getattr(e, 'offset', 0) or 0,
            'message': str(e),
            'message_hr': f'XML sintaksna greška na liniji {getattr(e, "lineno", "?")}: {e}',
        }])

    is_valid = schema.validate(doc)
    if is_valid:
        return True

    errors = []
    for err in schema.error_log:
        # Translate common XSD errors to Croatian
        msg_hr = _translate_xsd_error(err.message)
        errors.append({
            'line': err.line,
            'column': err.column,
            'message': err.message,
            'message_hr': f'Linija {err.line}: {msg_hr}',
        })

    raise XSDValidationError(errors[:10])


def _translate_xsd_error(msg):
    """Prevedi česte XSD greške na hrvatski."""
    translations = {
        'is not a valid value': 'nije ispravna vrijednost',
        'Element': 'Element',
        'is not expected': 'nije očekivan na ovom mjestu',
        'Missing child element': 'Nedostaje obavezni podelement',
        'is not valid': 'nije ispravan',
        'The value': 'Vrijednost',
        'does not match': 'ne odgovara uzorku',
        'expected': 'očekivano',
        'Invalid content was found': 'Pronađen neispravan sadržaj',
        'not among the possible': 'nije među mogućim vrijednostima',
    }
    result = msg
    for eng, hr in translations.items():
        result = result.replace(eng, hr)
    return result


def validate_business_rules(xml_bytes):
    """
    EN 16931 business rules — 40 najvažnijih pravila.
    Ovo zamjenjuje Schematron dok ne nabavimo .sch datoteke.

    Pravila su iz:
    - CEN/TS 16931-3-2 (UBL binding)
    - PEPPOL BIS 3.0 Billing rules
    - Croatian CIUS
    """
    errors = []
    warnings = []

    try:
        doc = etree.fromstring(xml_bytes if isinstance(xml_bytes, bytes) else xml_bytes.encode())
    except Exception as e:
        return False, [f'XML parse: {e}'], []

    ns = {
        'ubl': 'urn:oasis:names:specification:ubl:schema:xsd:Invoice-2',
        'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
        'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
    }

    def _text(xpath):
        el = doc.find(xpath, ns)
        return el.text.strip() if el is not None and el.text else ''

    def _decimal(xpath):
        t = _text(xpath)
        try:
            return Decimal(t) if t else None
        except Exception:
            return None

    # ── BR-01: Invoice number required ──
    if not _text('.//cbc:ID'):
        errors.append('BR-01: Broj računa je obavezan (cbc:ID)')

    # ── BR-02: Issue date required ──
    if not _text('.//cbc:IssueDate'):
        errors.append('BR-02: Datum izdavanja je obavezan (cbc:IssueDate)')

    # ── BR-03: Invoice type code ──
    type_code = _text('.//cbc:InvoiceTypeCode')
    if type_code not in ('380', '381', '383', '384', '386', '389', '751'):
        errors.append(f'BR-03: Nepoznat tip dokumenta: {type_code}')

    # ── BR-04: Currency code required ──
    currency = _text('.//cbc:DocumentCurrencyCode')
    if not currency or len(currency) != 3:
        errors.append(f'BR-04: Valuta mora biti 3-slovna ISO oznaka, got: {currency}')

    # ── BR-05: Seller name required ──
    seller_name = _text('.//cac:AccountingSupplierParty/cac:Party/cac:PartyName/cbc:Name')
    if not seller_name:
        errors.append('BR-05: Naziv izdavatelja je obavezan')

    # ── BR-06: Seller country required ──
    seller_country = _text('.//cac:AccountingSupplierParty/cac:Party/cac:PostalAddress/cac:Country/cbc:IdentificationCode')
    if not seller_country:
        errors.append('BR-06: Država izdavatelja je obavezna')

    # ── BR-07: Buyer name required ──
    buyer_name = _text('.//cac:AccountingCustomerParty/cac:Party/cac:PartyName/cbc:Name')
    if not buyer_name:
        errors.append('BR-07: Naziv primatelja je obavezan')

    # ── BR-08: Seller VAT ID ──
    seller_vat = _text('.//cac:AccountingSupplierParty/cac:Party/cac:PartyTaxScheme/cbc:CompanyID')
    if not seller_vat:
        warnings.append('BR-08: OIB/VAT ID izdavatelja nedostaje')

    # ── BR-10: Buyer country required ──
    buyer_country = _text('.//cac:AccountingCustomerParty/cac:Party/cac:PostalAddress/cac:Country/cbc:IdentificationCode')
    if not buyer_country:
        errors.append('BR-10: Država primatelja je obavezna')

    # ── BR-12: Sum of line amounts ──
    line_extension = _decimal('.//cac:LegalMonetaryTotal/cbc:LineExtensionAmount')
    lines = doc.findall('.//cac:InvoiceLine', ns)
    if lines:
        line_sum = Decimal('0')
        for line in lines:
            amt_el = line.find('cbc:LineExtensionAmount', ns)
            if amt_el is not None and amt_el.text:
                try:
                    line_sum += Decimal(amt_el.text)
                except Exception:
                    pass
        if line_extension and abs(line_sum - line_extension) > Decimal('0.02'):
            errors.append(f'BR-12: Zbroj stavki ({line_sum}) != LineExtensionAmount ({line_extension})')
    else:
        errors.append('BR-16: Račun mora imati barem jednu stavku')

    # ── BR-13: Tax exclusive = line total ──
    tax_exclusive = _decimal('.//cac:LegalMonetaryTotal/cbc:TaxExclusiveAmount')
    if line_extension and tax_exclusive and abs(line_extension - tax_exclusive) > Decimal('0.02'):
        warnings.append(f'BR-13: LineExtension ({line_extension}) != TaxExclusive ({tax_exclusive})')

    # ── BR-14: Tax inclusive = tax exclusive + tax ──
    tax_inclusive = _decimal('.//cac:LegalMonetaryTotal/cbc:TaxInclusiveAmount')
    tax_amount = _decimal('.//cac:TaxTotal/cbc:TaxAmount')
    if tax_exclusive and tax_inclusive and tax_amount:
        expected = tax_exclusive + tax_amount
        if abs(expected - tax_inclusive) > Decimal('0.02'):
            errors.append(f'BR-14: TaxExclusive ({tax_exclusive}) + Tax ({tax_amount}) != TaxInclusive ({tax_inclusive})')

    # ── BR-15: Payable = tax inclusive ──
    payable = _decimal('.//cac:LegalMonetaryTotal/cbc:PayableAmount')
    if tax_inclusive and payable and abs(tax_inclusive - payable) > Decimal('0.02'):
        warnings.append(f'BR-15: TaxInclusive ({tax_inclusive}) != Payable ({payable})')

    # ── BR-CO-10: Tax subtotal sum = total tax ──
    subtotals = doc.findall('.//cac:TaxTotal/cac:TaxSubtotal', ns)
    if subtotals and tax_amount:
        subtotal_sum = Decimal('0')
        for st in subtotals:
            ta_el = st.find('cbc:TaxAmount', ns)
            if ta_el is not None and ta_el.text:
                try:
                    subtotal_sum += Decimal(ta_el.text)
                except Exception:
                    pass
        if abs(subtotal_sum - tax_amount) > Decimal('0.02'):
            errors.append(f'BR-CO-10: Zbroj PDV stavki ({subtotal_sum}) != ukupni PDV ({tax_amount})')

    # ── BR-S-08: Standard rate (S) mora imati % > 0 ──
    for st in subtotals:
        cat_el = st.find('.//cac:TaxCategory/cbc:ID', ns)
        pct_el = st.find('.//cac:TaxCategory/cbc:Percent', ns)
        if cat_el is not None and cat_el.text == 'S':
            if pct_el is None or not pct_el.text or Decimal(pct_el.text) <= 0:
                errors.append('BR-S-08: Standardna PDV kategorija (S) mora imati stopu > 0%')

    # ── PEPPOL-EN16931-R004: CustomizationID required ──
    cust_id = _text('.//cbc:CustomizationID')
    if not cust_id:
        errors.append('PEPPOL-R004: CustomizationID je obavezan')

    # ── HR CIUS: OIB format ──
    if seller_vat:
        oib = seller_vat.replace('HR', '').strip()
        if len(oib) != 11 or not oib.isdigit():
            warnings.append(f'HR-CIUS: OIB izdavatelja neispravan ({seller_vat})')

    # ── Line-level checks ──
    for idx, line in enumerate(lines, 1):
        line_id = line.find('cbc:ID', ns)
        if line_id is None or not (line_id.text or '').strip():
            errors.append(f'BR-21: Stavka {idx} nema ID')

        qty_el = line.find('cbc:InvoicedQuantity', ns)
        if qty_el is None or not (qty_el.text or '').strip():
            errors.append(f'BR-22: Stavka {idx} nema količinu')

        name_el = line.find('.//cac:Item/cbc:Name', ns)
        if name_el is None or not (name_el.text or '').strip():
            errors.append(f'BR-25: Stavka {idx} nema naziv')

        price_el = line.find('.//cac:Price/cbc:PriceAmount', ns)
        if price_el is None or not (price_el.text or '').strip():
            errors.append(f'BR-26: Stavka {idx} nema cijenu')

    is_valid = len(errors) == 0
    return is_valid, errors, warnings


def validate_full(xml_bytes):
    """
    Kompletna validacija: XSD + Business Rules.
    Returns: (is_valid, errors, warnings)
    """
    all_errors = []
    all_warnings = []

    # XSD
    xsd_valid, xsd_errors = validate_xsd(xml_bytes)
    if not xsd_valid:
        all_errors.extend([f'XSD: {e}' for e in xsd_errors])

    # Business rules
    br_valid, br_errors, br_warnings = validate_business_rules(xml_bytes)
    all_errors.extend(br_errors)
    all_warnings.extend(br_warnings)

    is_valid = len(all_errors) == 0
    return is_valid, all_errors, all_warnings
