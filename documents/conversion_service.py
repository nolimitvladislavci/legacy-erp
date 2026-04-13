"""
documents/conversion_service.py

Pipeline: Slika ulaznog racuna -> AI ekstrakcija -> UBL XML
Smanjenje: ~200KB slika -> ~10KB XML (95% usteda)
"""
import hashlib
import io
import json
import logging
import os
import uuid
from datetime import datetime
from decimal import Decimal
from xml.etree.ElementTree import Element, SubElement, tostring

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# Register HEIC/HEIF opener for iPhone photos
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass

# ════════════════════════════════════════════════════════════
# AI EXTRACTION — Gemini 2.5-Flash Vision
# ════════════════════════════════════════════════════════════

INVOICE_EXTRACTION_PROMPT = """Analiziraj ovu sliku ulaznog racuna i ekstrahiraj SVE podatke u JSON formatu.

OBAVEZNA POLJA (vrati prazan string ako ne mozes procitati):
{
  "invoice_number": "broj racuna",
  "issue_date": "datum izdavanja (DD.MM.YYYY)",
  "due_date": "datum dospijeca (DD.MM.YYYY ili prazan)",
  "seller": {
    "name": "naziv prodavatelja/dobavljaca",
    "oib": "OIB (11 znamenki) ili VAT ID",
    "address": "adresa",
    "city": "grad",
    "postal_code": "postanski broj",
    "country": "drzava (ISO 2-slovo, npr HR, DE, AT)",
    "iban": "IBAN ako je vidljiv"
  },
  "buyer": {
    "name": "naziv kupca",
    "oib": "OIB kupca",
    "address": "adresa kupca",
    "city": "grad kupca",
    "postal_code": "postanski broj kupca",
    "country": "drzava kupca"
  },
  "items": [
    {
      "description": "opis artikla/usluge",
      "quantity": 1.0,
      "unit": "kom",
      "unit_price": 0.00,
      "vat_rate": 25,
      "line_total": 0.00
    }
  ],
  "subtotal": 0.00,
  "vat_amount": 0.00,
  "total": 0.00,
  "currency": "EUR",
  "payment_method": "virman",
  "payment_reference": "poziv na broj",
  "note": "napomena ako postoji",
  "tax_classification": "R1 ili R2",
  "zki": "zastitni kod izdavatelja ako postoji",
  "jir": "jedinstveni identifikator racuna ako postoji"
}

PRAVILA:
- Ako je racun na hrvatskom, prepoznaj hrvatske termine (PDV, ukupno, kolicina, jed.cijena)
- Ako je racun na njemackom/engleskom, prepoznaj odgovarajuce termine (MwSt, Betrag, Amount, VAT)
- Za invoice_number trazi: Rechnungsnummer, Rechnung Nr, BonNr, Belegnr, Beleg-Nr, Kassenbonnummer, Invoice No, Bill No, Receipt No - bilo koji od ovih je broj racuna
- Brojeve uvijek vrati kao decimalne (25.00, ne "25,00")
- Datume vrati u formatu DD.MM.YYYY
- Za PDV stopu koristi broj (25, 13, 5, 0)
- Ako stavka nema PDV, stavi vat_rate: 0
- Ako ne mozes procitati neko polje, vrati prazan string ili 0
- NIKAD ne izmisljaj podatke - samo ono sto vidis na slici
- ZKI i JIR su SAMO za hrvatske fiskalne racune. Njemacki TSE-Signatur, TSE-Signaturzaehler, TSE-Transaktion NISU ZKI/JIR - ostavi ta polja prazna za njemacke racune
- Za njemacke racune: Steuer Nr je porezni broj, UID Nr je VAT ID (spremi u seller.oib)

Vrati SAMO JSON, bez dodatnog teksta.
"""


def _encode_image_for_gemini(file_bytes, filename):
    """Pripremi sliku za Gemini Vision API."""
    try:
        from PIL import Image, ImageEnhance
        img = Image.open(io.BytesIO(file_bytes))

        # Auto-rotate from EXIF
        try:
            from PIL import ExifTags
            for orientation in ExifTags.TAGS:
                if ExifTags.TAGS[orientation] == 'Orientation':
                    break
            exif = img._getexif()
            if exif and orientation in exif:
                if exif[orientation] == 3:
                    img = img.rotate(180, expand=True)
                elif exif[orientation] == 6:
                    img = img.rotate(270, expand=True)
                elif exif[orientation] == 8:
                    img = img.rotate(90, expand=True)
        except ImportError:
            pass

        # Resize if too large
        max_dim = 2048
        if max(img.size) > max_dim:
            img.thumbnail((max_dim, max_dim), Image.LANCZOS)

        # Enhance for OCR
        img = ImageEnhance.Contrast(img).enhance(1.3)
        img = ImageEnhance.Sharpness(img).enhance(1.5)

        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')

        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=90)
        buf.seek(0)

        import base64
        return base64.b64encode(buf.read()).decode('utf-8')
    except ImportError:
        import base64
        return base64.b64encode(file_bytes).decode('utf-8')


def extract_invoice_data_gemini(file_bytes, filename):
    """Koristi Gemini 2.5-Flash Vision za ekstrakciju podataka s racuna."""
    api_key = os.environ.get('GEMINI_API_KEY', '')
    if not api_key:
        raise RuntimeError('GEMINI_API_KEY not configured')

    b64_image = _encode_image_for_gemini(file_bytes, filename)

    try:
        from google import genai as _genai
        client = _genai.Client(api_key=api_key)
        import base64
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[
                {'role': 'user', 'parts': [
                    {'text': INVOICE_EXTRACTION_PROMPT},
                    {'inline_data': {'mime_type': 'image/jpeg', 'data': b64_image}},
                ]},
            ],
        )
        text = response.text.strip()
        # Extract JSON from response
        if text.startswith('```'):
            text = text.split('\n', 1)[1]
            text = text.rsplit('```', 1)[0]
        data = json.loads(text)

        # Token usage
        tokens = 0
        cost = Decimal('0')
        if hasattr(response, 'usage_metadata'):
            tokens = getattr(response.usage_metadata, 'total_token_count', 0) or 0
            cost = Decimal(str(tokens * 0.000000075))  # Gemini Flash pricing

        return data, tokens, cost

    except ImportError:
        # Fallback to Claude if Gemini not installed
        return _extract_invoice_data_claude(file_bytes, filename)


def _extract_invoice_data_claude(file_bytes, filename):
    """Fallback: Claude Haiku Vision."""
    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        raise RuntimeError('No AI API configured (GEMINI_API_KEY or ANTHROPIC_API_KEY)')

    import base64
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    b64_image = base64.b64encode(file_bytes).decode('utf-8')

    ext = os.path.splitext(filename)[1].lower()
    media_type = {'jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
                  '.webp': 'image/webp', '.gif': 'image/gif'}.get(ext, 'image/jpeg')

    response = client.messages.create(
        model='claude-haiku-4-5-20251001',
        max_tokens=4096,
        messages=[{
            'role': 'user',
            'content': [
                {'type': 'image', 'source': {'type': 'base64', 'media_type': media_type, 'data': b64_image}},
                {'type': 'text', 'text': INVOICE_EXTRACTION_PROMPT},
            ],
        }],
    )

    text = response.content[0].text.strip()
    if text.startswith('```'):
        text = text.split('\n', 1)[1]
        text = text.rsplit('```', 1)[0]
    data = json.loads(text)

    tokens = response.usage.input_tokens + response.usage.output_tokens
    cost = Decimal(str(tokens * 0.00000025))  # Haiku pricing

    return data, tokens, cost


# ════════════════════════════════════════════════════════════
# UBL XML GENERATION — Iz ekstrahiranih podataka
# ════════════════════════════════════════════════════════════

UBL_NS = 'urn:oasis:names:specification:ubl:schema:xsd:Invoice-2'
CAC_NS = 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2'
CBC_NS = 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2'


def _sub(parent, ns, tag, text=None, **attrs):
    """Helper: create subelement with namespace."""
    el = SubElement(parent, '{%s}%s' % (ns, tag), **attrs)
    if text is not None:
        el.text = str(text)
    return el


def generate_ubl_xml_from_extracted(data):
    """Generira UBL 2.1 XML iz ekstrahiranih podataka."""
    root = Element('{%s}Invoice' % UBL_NS)
    root.set('xmlns', UBL_NS)
    root.set('xmlns:cac', CAC_NS)
    root.set('xmlns:cbc', CBC_NS)

    # Header
    _sub(root, CBC_NS, 'CustomizationID',
         'urn:cen.eu:en16931:2017#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0')
    _sub(root, CBC_NS, 'ProfileID', 'urn:fdc:peppol.eu:2017:poacc:billing:01:1.0')
    _sub(root, CBC_NS, 'ID', data.get('invoice_number', 'UNKNOWN'))
    _sub(root, CBC_NS, 'IssueDate', _parse_date(data.get('issue_date', '')))

    due = data.get('due_date', '')
    if due:
        _sub(root, CBC_NS, 'DueDate', _parse_date(due))

    _sub(root, CBC_NS, 'InvoiceTypeCode', '380')  # Commercial invoice

    currency = data.get('currency', 'EUR')
    _sub(root, CBC_NS, 'DocumentCurrencyCode', currency)

    note = data.get('note', '')
    if note:
        _sub(root, CBC_NS, 'Note', note)

    # ZKI/JIR as additional document reference
    zki = data.get('zki', '')
    jir = data.get('jir', '')
    if zki:
        ref = _sub(root, CAC_NS, 'AdditionalDocumentReference')
        _sub(ref, CBC_NS, 'ID', 'ZKI:' + zki)
    if jir:
        ref = _sub(root, CAC_NS, 'AdditionalDocumentReference')
        _sub(ref, CBC_NS, 'ID', 'JIR:' + jir)

    # Seller (AccountingSupplierParty)
    seller = data.get('seller', {})
    sp = _sub(root, CAC_NS, 'AccountingSupplierParty')
    party = _sub(sp, CAC_NS, 'Party')
    if seller.get('oib'):
        pi = _sub(party, CAC_NS, 'PartyIdentification')
        _sub(pi, CBC_NS, 'ID', seller['oib'], schemeID='0191')  # HR OIB scheme
    pn = _sub(party, CAC_NS, 'PartyName')
    _sub(pn, CBC_NS, 'Name', seller.get('name', ''))
    addr = _sub(party, CAC_NS, 'PostalAddress')
    _sub(addr, CBC_NS, 'StreetName', seller.get('address', ''))
    _sub(addr, CBC_NS, 'CityName', seller.get('city', ''))
    _sub(addr, CBC_NS, 'PostalZone', seller.get('postal_code', ''))
    country_el = _sub(addr, CAC_NS, 'Country')
    _sub(country_el, CBC_NS, 'IdentificationCode', seller.get('country', 'HR'))
    if seller.get('oib'):
        tax_scheme = _sub(party, CAC_NS, 'PartyTaxScheme')
        _sub(tax_scheme, CBC_NS, 'CompanyID', 'HR' + seller['oib'])
        ts = _sub(tax_scheme, CAC_NS, 'TaxScheme')
        _sub(ts, CBC_NS, 'ID', 'VAT')

    # Buyer (AccountingCustomerParty)
    buyer = data.get('buyer', {})
    cp = _sub(root, CAC_NS, 'AccountingCustomerParty')
    party2 = _sub(cp, CAC_NS, 'Party')
    if buyer.get('oib'):
        pi2 = _sub(party2, CAC_NS, 'PartyIdentification')
        _sub(pi2, CBC_NS, 'ID', buyer['oib'], schemeID='0191')
    pn2 = _sub(party2, CAC_NS, 'PartyName')
    _sub(pn2, CBC_NS, 'Name', buyer.get('name', ''))
    addr2 = _sub(party2, CAC_NS, 'PostalAddress')
    _sub(addr2, CBC_NS, 'StreetName', buyer.get('address', ''))
    _sub(addr2, CBC_NS, 'CityName', buyer.get('city', ''))
    _sub(addr2, CBC_NS, 'PostalZone', buyer.get('postal_code', ''))
    country_el2 = _sub(addr2, CAC_NS, 'Country')
    _sub(country_el2, CBC_NS, 'IdentificationCode', buyer.get('country', 'HR'))

    # Payment means
    pm_code = '30'  # Bank transfer default
    payment_method = data.get('payment_method', '')
    if payment_method in ('gotovina', 'cash'):
        pm_code = '10'
    elif payment_method in ('kartica', 'card'):
        pm_code = '48'
    pm = _sub(root, CAC_NS, 'PaymentMeans')
    _sub(pm, CBC_NS, 'PaymentMeansCode', pm_code)
    if seller.get('iban'):
        pa = _sub(pm, CAC_NS, 'PayeeFinancialAccount')
        _sub(pa, CBC_NS, 'ID', seller['iban'])
    if data.get('payment_reference'):
        _sub(pm, CBC_NS, 'PaymentID', data['payment_reference'])

    # Tax totals
    subtotal = _to_decimal(data.get('subtotal', 0))
    vat_amount = _to_decimal(data.get('vat_amount', 0))
    total = _to_decimal(data.get('total', 0))

    # Group items by VAT rate
    vat_groups = {}
    items = data.get('items', [])
    for item in items:
        rate = int(item.get('vat_rate', 25))
        if rate not in vat_groups:
            vat_groups[rate] = {'taxable': Decimal('0'), 'tax': Decimal('0')}
        line_total = _to_decimal(item.get('line_total', 0))
        vat_groups[rate]['taxable'] += line_total
        vat_groups[rate]['tax'] += line_total * Decimal(str(rate)) / Decimal('100')

    tt = _sub(root, CAC_NS, 'TaxTotal')
    _sub(tt, CBC_NS, 'TaxAmount', _fmt(vat_amount), currencyID=currency)
    for rate, amounts in vat_groups.items():
        ts = _sub(tt, CAC_NS, 'TaxSubtotal')
        _sub(ts, CBC_NS, 'TaxableAmount', _fmt(amounts['taxable']), currencyID=currency)
        _sub(ts, CBC_NS, 'TaxAmount', _fmt(amounts['tax']), currencyID=currency)
        tc = _sub(ts, CAC_NS, 'TaxCategory')
        _sub(tc, CBC_NS, 'ID', 'S' if rate > 0 else 'Z')
        _sub(tc, CBC_NS, 'Percent', str(rate))
        tcs = _sub(tc, CAC_NS, 'TaxScheme')
        _sub(tcs, CBC_NS, 'ID', 'VAT')

    # Legal monetary totals
    lmt = _sub(root, CAC_NS, 'LegalMonetaryTotals')
    _sub(lmt, CBC_NS, 'LineExtensionAmount', _fmt(subtotal), currencyID=currency)
    _sub(lmt, CBC_NS, 'TaxExclusiveAmount', _fmt(subtotal), currencyID=currency)
    _sub(lmt, CBC_NS, 'TaxInclusiveAmount', _fmt(total), currencyID=currency)
    _sub(lmt, CBC_NS, 'PayableAmount', _fmt(total), currencyID=currency)

    # Invoice lines
    for idx, item in enumerate(items, 1):
        line = _sub(root, CAC_NS, 'InvoiceLine')
        _sub(line, CBC_NS, 'ID', str(idx))
        qty = _to_decimal(item.get('quantity', 1))
        _sub(line, CBC_NS, 'InvoicedQuantity', _fmt(qty), unitCode=_unit_code(item.get('unit', 'kom')))
        _sub(line, CBC_NS, 'LineExtensionAmount', _fmt(_to_decimal(item.get('line_total', 0))), currencyID=currency)

        # Item
        il_item = _sub(line, CAC_NS, 'Item')
        _sub(il_item, CBC_NS, 'Name', item.get('description', ''))
        ctc = _sub(il_item, CAC_NS, 'ClassifiedTaxCategory')
        _sub(ctc, CBC_NS, 'ID', 'S' if int(item.get('vat_rate', 25)) > 0 else 'Z')
        _sub(ctc, CBC_NS, 'Percent', str(int(item.get('vat_rate', 25))))
        ctcs = _sub(ctc, CAC_NS, 'TaxScheme')
        _sub(ctcs, CBC_NS, 'ID', 'VAT')

        # Price
        price = _sub(line, CAC_NS, 'Price')
        _sub(price, CBC_NS, 'PriceAmount', _fmt(_to_decimal(item.get('unit_price', 0))), currencyID=currency)

    # Serialize
    from xml.dom.minidom import parseString
    raw = tostring(root, encoding='unicode')
    pretty = parseString(raw).toprettyxml(indent='  ', encoding='UTF-8')
    return pretty


def _parse_date(date_str):
    """Parse DD.MM.YYYY to YYYY-MM-DD."""
    if not date_str:
        return datetime.now().strftime('%Y-%m-%d')
    try:
        parts = date_str.replace('/', '.').replace('-', '.').split('.')
        if len(parts) == 3:
            if len(parts[0]) == 4:  # Already YYYY-MM-DD
                return date_str
            return '%s-%s-%s' % (parts[2], parts[1].zfill(2), parts[0].zfill(2))
    except (ValueError, AttributeError):
        pass
    return datetime.now().strftime('%Y-%m-%d')


def _to_decimal(val):
    """Safely convert to Decimal."""
    try:
        if isinstance(val, str):
            val = val.replace(',', '.')
        return Decimal(str(val))
    except (ValueError, TypeError):
        return Decimal('0')


def _fmt(d):
    """Format Decimal to 2 places."""
    return str(d.quantize(Decimal('0.01')))


UNIT_MAP = {
    'kom': 'EA', 'komad': 'EA', 'pcs': 'EA', 'ea': 'EA', 'stk': 'EA',
    'kg': 'KGM', 'g': 'GRM',
    'l': 'LTR', 'lit': 'LTR', 'ltr': 'LTR',
    'm': 'MTR', 'm2': 'MTK', 'm3': 'MTQ',
    'sat': 'HUR', 'h': 'HUR', 'std': 'HUR',
    'dan': 'DAY', 'mj': 'MON',
    'pak': 'XPK', 'set': 'SET',
}


def _unit_code(unit):
    """Map Croatian unit names to UN/ECE codes."""
    return UNIT_MAP.get(unit.lower().strip(), 'EA')


# ════════════════════════════════════════════════════════════
# VALIDATION
# ════════════════════════════════════════════════════════════

def validate_extracted_data(data):
    """Validacija ekstrahiranih podataka. Vraca (is_valid, errors, confidence_score)."""
    errors = []
    score = 1.0

    # Obavezna polja
    if not data.get('invoice_number'):
        errors.append('Nedostaje broj racuna')
        score -= 0.3
    if not data.get('issue_date'):
        errors.append('Nedostaje datum izdavanja')
        score -= 0.2
    if not data.get('total') or float(data.get('total', 0)) == 0:
        errors.append('Nedostaje ukupan iznos')
        score -= 0.3

    seller = data.get('seller', {})
    if not seller.get('name'):
        errors.append('Nedostaje naziv prodavatelja')
        score -= 0.2
    if not seller.get('oib'):
        errors.append('Nedostaje OIB prodavatelja')
        score -= 0  # OIB validacija samo informativna, ne penalizira score

    items = data.get('items', [])
    if not items:
        errors.append('Nema stavki racuna')
        score -= 0.3

    # Konzistentnost iznosa
    if items:
        calc_subtotal = sum(float(i.get('line_total', 0)) for i in items)
        stated_subtotal = float(data.get('subtotal', 0))
        if stated_subtotal > 0 and abs(calc_subtotal - stated_subtotal) > 1.0:
            errors.append('Neslaganje: suma stavki (%.2f) != medjuzbroj (%.2f)' % (calc_subtotal, stated_subtotal))
            score -= 0.15

    # OIB checksum (ISO 7064)
    oib = seller.get('oib', '')
    if oib and len(oib) == 11 and oib.isdigit():
        if not _validate_oib(oib):
            errors.append('OIB prodavatelja ne prolazi kontrolni zbroj')
            score -= 0  # OIB validacija samo informativna, ne penalizira score

    score = max(0, min(1, score))

    if score >= 0.9:
        confidence = 'high'
    elif score >= 0.7:
        confidence = 'medium'
    else:
        confidence = 'low'

    return len(errors) == 0, errors, score, confidence


def _validate_oib(oib):
    """ISO 7064 MOD 11,10 checksum."""
    try:
        a = 10
        for digit in oib[:10]:
            a = (a + int(digit)) % 10
            if a == 0:
                a = 10
            a = (a * 2) % 11
        control = 11 - a
        if control == 10:
            control = 0
        return control == int(oib[10])
    except (ValueError, TypeError):
        return False


# ════════════════════════════════════════════════════════════
# MAIN PIPELINE
# ════════════════════════════════════════════════════════════

def convert_image_to_xml(file_bytes, filename, company, user=None):
    """
    Glavni pipeline: Slika -> AI ekstrakcija -> Validacija -> UBL XML

    Returns: ConversionRecord instance
    """
    from documents.models import ConversionRecord, ArhivaEntry
    from documents.storage_backends import store_document, get_file_hash

    original_hash = hashlib.sha256(file_bytes).hexdigest()
    original_size = len(file_bytes)

    ext = os.path.splitext(filename)[1].lower()
    content_type = {
        '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
        '.webp': 'image/webp', '.gif': 'image/gif',
        '.heic': 'image/heic', '.heif': 'image/heif',
    }.get(ext, 'image/octet-stream')

    # Duplikat detekcija po hash-u slike
    existing = ConversionRecord.objects.filter(
        company=company,
        original_hash=original_hash,
        status__in=['validated', 'xml_generated', 'extracted'],
    ).first()
    if existing:
        raise ValueError(
            'Duplikat: ova slika je vec konvertirana (ID: %s, datum: %s). '
            'Preskoceno.' % (str(existing.id)[:8], existing.created_at.strftime('%d.%m.%Y %H:%M'))
        )

    # Create ConversionRecord
    record = ConversionRecord.objects.create(
        company=company,
        original_filename=filename,
        original_size=original_size,
        original_hash=original_hash,
        original_content_type=content_type,
        status='pending',
        created_by=user,
    )

    try:
        # Step 1: Save original image (cloud + local backup)
        store_result = store_document(
            file_bytes=file_bytes,
            filename=filename,
            company_id=company.id,
            source_type='invoice_in',
            backend_name=None,  # Use default
        )
        record.original_path = store_result['path']

        # Step 2: AI extraction
        logger.info('Starting AI extraction for %s', filename)
        extracted_data, tokens, cost = extract_invoice_data_gemini(file_bytes, filename)

        record.extracted_data = extracted_data
        record.ai_response_tokens = tokens
        record.ai_cost_eur = cost
        record.status = 'extracted'
        record.items_extracted = len(extracted_data.get('items', []))

        # Count non-empty fields
        field_count = 0
        for key, val in extracted_data.items():
            if isinstance(val, dict):
                field_count += sum(1 for v in val.values() if v)
            elif isinstance(val, list):
                field_count += len(val)
            elif val:
                field_count += 1
        record.fields_extracted = field_count

        # Step 3: Validate
        is_valid, errors, confidence_score, confidence = validate_extracted_data(extracted_data)
        record.validation_errors = errors
        record.ai_confidence = confidence
        record.ai_confidence_score = confidence_score

        # Step 4: Generate XML
        xml_bytes = generate_ubl_xml_from_extracted(extracted_data)
        xml_content = xml_bytes.decode('utf-8') if isinstance(xml_bytes, bytes) else xml_bytes

        record.xml_content = xml_content
        record.xml_hash = hashlib.sha256(xml_content.encode('utf-8')).hexdigest()
        record.xml_size = len(xml_content.encode('utf-8'))
        record.status = 'xml_generated'

        # Save XML file
        xml_filename = os.path.splitext(filename)[0] + '.xml'
        xml_store = store_document(
            file_bytes=xml_content.encode('utf-8'),
            filename=xml_filename,
            company_id=company.id,
            source_type='invoice_in',
            backend_name='local',
            auto_compress=False,
            content_type='application/xml',
        )
        record.xml_path = xml_store['path']

        # Size reduction
        if original_size > 0:
            record.size_reduction_pct = (1 - record.xml_size / original_size) * 100

        record.is_valid = is_valid
        if is_valid:
            record.status = 'validated'
        record.completed_at = timezone.now()
        record.save()

        # Step 5: Create/update ArhivaEntry
        arhiva = ArhivaEntry.objects.create(
            company=company,
            source_type='invoice_in',
            source_id='conversion:%s' % record.id,
            doc_number=extracted_data.get('invoice_number', filename),
            partner_name=extracted_data.get('seller', {}).get('name', ''),
            amount=_to_decimal(extracted_data.get('total', 0)),
            currency=extracted_data.get('currency', 'EUR'),
            doc_date=_parse_date_obj(extracted_data.get('issue_date', '')),
            file_path=record.xml_path,
            has_xml=True,
            has_image=True,
            zki=extracted_data.get('zki', '')[:64],
            jir=extracted_data.get('jir', '')[:64],
            archived_by=user,
            session_key='',
        )
        record.arhiva_entry_id = arhiva.pk
        record.save(update_fields=["arhiva_entry_id"])

        logger.info(
            'Conversion complete: %s -> %s (%.0f%% reduction, confidence: %s)',
            filename, xml_filename, record.size_reduction_pct, confidence
        )

        return record

    except ValueError as e:
        record.status = 'failed'
        record.validation_errors = [str(e)]
        record.save()
        logger.error('Conversion failed for %s: %s', filename, e, exc_info=True)
        raise


def _parse_date_obj(date_str):
    """Parse date string to date object."""
    from datetime import date
    try:
        parts = date_str.replace('/', '.').replace('-', '.').split('.')
        if len(parts) == 3:
            if len(parts[0]) == 4:
                return date(int(parts[0]), int(parts[1]), int(parts[2]))
            return date(int(parts[2]), int(parts[1]), int(parts[0]))
    except (ValueError, TypeError):
        pass
    return date.today()
