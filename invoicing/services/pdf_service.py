"""Invoice PDF, QR and eRačun generation."""
import hashlib
import hmac
import base64
from decimal import Decimal
from django.template.loader import render_to_string
from django.utils.translation import activate, get_language
from django.utils import timezone

RATE_NAMES = {
    '0':  'Oslobođeno',
    '5':  'Snižena (knjige, hrana)',
    '13': 'Snižena (ugost.)',
    '19': 'MwSt. (DE)',
    '25': 'Standardna',
}


def build_tax_groups(invoice):
    """Return list of tax-group dicts for invoice recap table."""
    groups = {}
    for item in invoice.items.all():
        key = str(int(item.tax_rate))
        if key not in groups:
            groups[key] = {'base': Decimal('0'), 'tax': Decimal('0')}
        groups[key]['base'] += item.total_price
        groups[key]['tax'] += item.total_price * item.tax_rate / 100
    return [
        {
            'rate': r,
            'name': RATE_NAMES.get(r, ''),
            'base': groups[r]['base'],
            'tax':  groups[r]['tax'],
            'total': groups[r]['base'] + groups[r]['tax'],
        }
        for r in ['0', '5', '13', '19', '25']
        if r in groups and groups[r]['base'] > 0
    ]


def generate_qr(invoice):
    """Generate QR code base64 string for invoice payment data."""
    try:
        import qrcode
        import io
        payment_data = (
            f"BCD\n002\n1\nSCT\n{invoice.issuer_iban}\n{invoice.issuer_name}\n"
            f"{invoice.issuer_iban}\nEUR{invoice.total}\n\n{invoice.number}\n"
            f"Plaćanje računa {invoice.number}"
        )
        qr = qrcode.QRCode(version=1, box_size=5, border=2)
        qr.add_data(payment_data)
        qr.make(fit=True)
        img = qr.make_image(fill_color='black', back_color='white')
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return ''


def generate_zki(invoice, cert_key='demo_key'):
    """Generate ZKI (zaštitni kod izdavatelja) for HR fiscalization."""
    data = (
        f"{invoice.issuer_oib}"
        f"{invoice.date_issued.strftime('%d.%m.%Y %H:%M:%S')}"
        f"{invoice.number}"
        f"{getattr(invoice, 'business_location_code', '1')}"
        f"{getattr(invoice, 'operator_device_code', '1')}"
        f"{invoice.total}"
    )
    return hmac.new(cert_key.encode(), data.encode(), hashlib.md5).hexdigest()


def _ensure_qr(invoice):
    if not invoice.qr_code_base64:
        invoice.qr_code_base64 = generate_qr(invoice)
        invoice.save(update_fields=['qr_code_base64'])


def _get_company_logo_b64(invoice):
    """Return base64 logo string for company, or empty string."""
    try:
        company = invoice.company
        if company and company.logo:
            logo_path = company.logo.path
            with open(logo_path, 'rb') as f:
                data = f.read()
            ext = logo_path.rsplit('.', 1)[-1].lower()
            mime = 'image/png' if ext == 'png' else 'image/jpeg'
            return f"data:{mime};base64,{base64.b64encode(data).decode()}"
    except Exception:
        pass
    return ''


def _get_lc_brand_qr_b64():
    """Return LIMIT Connect brand QR (navy) as base64 PNG."""
    try:
        import qrcode, io
        qr = qrcode.QRCode(version=1, box_size=4, border=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M)
        qr.add_data('https://limit-connect.com')
        qr.make(fit=True)
        img = qr.make_image(fill_color='#1e3a5f', back_color='white')
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return ''


def render_invoice_html(invoice, request=None):
    """Render invoice to HTML string using HR, DE, or bilingual template."""
    profile = getattr(invoice, 'invoice_profile', None)

    if profile and profile.language:
        render_lang = profile.language
    elif invoice.is_hr:
        render_lang = 'hr'
    else:
        render_lang = 'de'

    prev_lang = get_language()
    activate(render_lang)

    # Shared extra context — logo + brand QR + contacts
    contacts = []
    try:
        s = invoice.company.settings or {}
        contacts = s.get("invoice_contacts", [])
    except Exception:
        pass
    extra_ctx = {
        "company_logo_src": _get_company_logo_b64(invoice),
        "lc_qr_b64":        _get_lc_brand_qr_b64(),
        "invoice_contacts": contacts,
    }

    try:
        if profile and getattr(profile, 'bilingual', False) and profile.secondary_language:
            from .bilingual_labels import get_bilingual_labels
            primary_lang = render_lang
            secondary_lang = profile.secondary_language
            labels = get_bilingual_labels(primary_lang, secondary_lang, invoice.doctype)
            return render_to_string('invoicing/invoice_bilingual.html', {
                'invoice': invoice,
                'now': timezone.now(),
                'request': request,
                'tax_groups': build_tax_groups(invoice),
                'labels': labels,
                'primary_lang': primary_lang,
                'secondary_lang': secondary_lang,
                **extra_ctx,
            })
        template = 'invoicing/invoice_hr.html' if invoice.is_hr else 'invoicing/invoice_de.html'
        return render_to_string(template, {
            'invoice': invoice,
            'now': timezone.now(),
            'request': request,
            'tax_groups': build_tax_groups(invoice),
            **extra_ctx,
        })
    finally:
        if prev_lang:
            activate(prev_lang)


def generate_invoice_pdf(invoice, request=None):
    """Return (bytes, mime_type) for the invoice PDF (or HTML fallback)."""
    _ensure_qr(invoice)
    html = render_invoice_html(invoice, request)
    try:
        from weasyprint import HTML
        kwargs = {'string': html}
        if request:
            kwargs['base_url'] = request.build_absolute_uri('/')
        return HTML(**kwargs).write_pdf(), 'application/pdf'
    except ImportError:
        return html.encode('utf-8'), 'text/html'


def generate_eracun_xml(invoice):
    """Return UBL 2.1 XML string for e-račun."""
    oib_block = (
        f'<cac:PartyTaxScheme><cbc:CompanyID>{invoice.client_oib}</cbc:CompanyID>'
        f'<cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme></cac:PartyTaxScheme>'
        if invoice.client_oib else ''
    )
    items_xml = ''.join(
        f'<cac:InvoiceLine>'
        f'<cbc:ID>{i+1}</cbc:ID>'
        f'<cbc:InvoicedQuantity unitCode="{item.unit}">{item.quantity}</cbc:InvoicedQuantity>'
        f'<cbc:LineExtensionAmount currencyID="{invoice.currency}">{item.total_price}</cbc:LineExtensionAmount>'
        f'<cac:Item><cbc:Description>{item.description}</cbc:Description></cac:Item>'
        f'<cac:Price><cbc:PriceAmount currencyID="{invoice.currency}">{item.unit_price}</cbc:PriceAmount></cac:Price>'
        f'</cac:InvoiceLine>'
        for i, item in enumerate(invoice.items.all())
    )
    due = invoice.date_due.strftime('%Y-%m-%d') if invoice.date_due else ''
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"\n'
        '  xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"\n'
        '  xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">\n'
        f'  <cbc:UBLVersionID>2.1</cbc:UBLVersionID>\n'
        f'  <cbc:ID>{invoice.number}</cbc:ID>\n'
        f'  <cbc:UUID>{invoice.uuid}</cbc:UUID>\n'
        f'  <cbc:IssueDate>{invoice.date_issued.strftime("%Y-%m-%d")}</cbc:IssueDate>\n'
        f'  <cbc:DueDate>{due}</cbc:DueDate>\n'
        f'  <cbc:InvoiceTypeCode>380</cbc:InvoiceTypeCode>\n'
        f'  <cbc:DocumentCurrencyCode>{invoice.currency}</cbc:DocumentCurrencyCode>\n'
        f'  <cac:AccountingSupplierParty><cac:Party>\n'
        f'    <cac:PartyName><cbc:Name>{invoice.issuer_name}</cbc:Name></cac:PartyName>\n'
        f'    <cac:PostalAddress><cbc:StreetName>{invoice.issuer_address}</cbc:StreetName>'
        f'<cbc:CountrySubentity>{invoice.country}</cbc:CountrySubentity></cac:PostalAddress>\n'
        f'    <cac:PartyTaxScheme><cbc:CompanyID>{invoice.issuer_oib}</cbc:CompanyID>'
        f'<cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme></cac:PartyTaxScheme>\n'
        f'  </cac:Party></cac:AccountingSupplierParty>\n'
        f'  <cac:AccountingCustomerParty><cac:Party>\n'
        f'    <cac:PartyName><cbc:Name>{invoice.client_name}</cbc:Name></cac:PartyName>\n'
        f'    <cac:PostalAddress><cbc:StreetName>{invoice.client_address}</cbc:StreetName></cac:PostalAddress>\n'
        f'    {oib_block}\n'
        f'  </cac:Party></cac:AccountingCustomerParty>\n'
        f'  <cac:PaymentMeans><cbc:PaymentMeansCode>30</cbc:PaymentMeansCode>\n'
        f'    <cac:PayeeFinancialAccount><cbc:ID>{invoice.issuer_iban}</cbc:ID></cac:PayeeFinancialAccount>\n'
        f'  </cac:PaymentMeans>\n'
        f'  <cac:TaxTotal>\n'
        f'    <cbc:TaxAmount currencyID="{invoice.currency}">{invoice.tax_amount}</cbc:TaxAmount>\n'
        f'    <cac:TaxSubtotal>\n'
        f'      <cbc:TaxableAmount currencyID="{invoice.currency}">{invoice.subtotal}</cbc:TaxableAmount>\n'
        f'      <cbc:TaxAmount currencyID="{invoice.currency}">{invoice.tax_amount}</cbc:TaxAmount>\n'
        f'      <cac:TaxCategory><cbc:Percent>{invoice.tax_percent}</cbc:Percent>'
        f'<cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme></cac:TaxCategory>\n'
        f'    </cac:TaxSubtotal>\n'
        f'  </cac:TaxTotal>\n'
        f'  <cac:LegalMonetaryTotal>\n'
        f'    <cbc:LineExtensionAmount currencyID="{invoice.currency}">{invoice.subtotal}</cbc:LineExtensionAmount>\n'
        f'    <cbc:TaxExclusiveAmount currencyID="{invoice.currency}">{invoice.subtotal}</cbc:TaxExclusiveAmount>\n'
        f'    <cbc:TaxInclusiveAmount currencyID="{invoice.currency}">{invoice.total}</cbc:TaxInclusiveAmount>\n'
        f'    <cbc:PayableAmount currencyID="{invoice.currency}">{invoice.total}</cbc:PayableAmount>\n'
        f'  </cac:LegalMonetaryTotal>\n'
        f'  {items_xml}\n'
        '</Invoice>'
    )
