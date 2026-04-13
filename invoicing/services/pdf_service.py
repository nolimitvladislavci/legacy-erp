"""Invoice PDF, QR and eRačun generation."""
import hashlib
import hmac
import base64
import os as _os
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

# Mapa pdf_template → template fajlovi (DE i HR varijanta)
TEMPLATE_MAP = {
    'viskovic': {
        'de': 'invoicing/invoice_de.html',
        'hr': 'invoicing/invoice_hr.html',
    },
    'datev': {
        'de': 'invoicing/invoice_de_datev.html',
        'hr': 'invoicing/invoice_hr_datev.html',
    },
    'modern': {
        'de': 'invoicing/invoice_de_modern.html',
        'hr': 'invoicing/invoice_hr_modern.html',
    },
}
TEMPLATE_FALLBACK = {
    'de': 'invoicing/invoice_de.html',
    'hr': 'invoicing/invoice_hr.html',
}


def build_tax_groups(invoice):
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


def build_sections(invoice):
    """
    Grupira InvoiceItem po section polju (ako postoji u DB).
    Koristi raw SQL za sortiranje — otporno na ORM cache koji ne zna za nova polja.
    Vraća: [{'name': str, 'items': [...], 'subtotal': Decimal}, ...]
    Fallback: jedna grupa bez naslova ako section polje ne postoji u DB.
    """
    from django.db import connection

    # Provjeri postoji li section kolona u bazi (ne u ORM cache!)
    has_section_col = False
    try:
        with connection.cursor() as c:
            c.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name='invoicing_invoiceitem' AND column_name='section'
            """)
            has_section_col = bool(c.fetchone())
    except Exception:
        pass

    if not has_section_col:
        # Nema kolone — vrati sve stavke u jednoj grupi bez naslova
        items = list(invoice.items.all().order_by('id'))
        return [{'name': '', 'items': items, 'subtotal': sum(i.total_price for i in items)}]

    # Fetch item IDs sortiranih po section, sort_order, id — raw SQL
    try:
        with connection.cursor() as c:
            c.execute("""
                SELECT id, section
                FROM invoicing_invoiceitem
                WHERE invoice_id = %s
                ORDER BY
                    CASE WHEN section IS NULL OR section = '' THEN 1 ELSE 0 END,
                    section,
                    sort_order,
                    id
            """, [invoice.pk])
            rows = c.fetchall()
    except Exception:
        items = list(invoice.items.all().order_by('id'))
        return [{'name': '', 'items': items, 'subtotal': sum(i.total_price for i in items)}]

    if not rows:
        return [{'name': '', 'items': [], 'subtotal': Decimal('0')}]

    # Fetch svih item objekata odjednom (1 query)
    id_order = [r[0] for r in rows]
    id_to_section = {r[0]: (r[1] or '') for r in rows}
    items_by_id = {item.id: item for item in invoice.items.filter(id__in=id_order)}

    # Sortirani item objekti
    sorted_items = [items_by_id[i] for i in id_order if i in items_by_id]

    # Provjeri ima li uopće sekcija
    has_any_section = any(id_to_section.get(i.id, '') for i in sorted_items)

    if not has_any_section:
        total = sum(i.total_price for i in sorted_items)
        return [{'name': '', 'items': sorted_items, 'subtotal': total}]

    # Grupiraj po sekciji (uz čuvanje redoslijeda)
    sections = []
    seen = {}
    for item in sorted_items:
        sec = id_to_section.get(item.id, '')
        if sec not in seen:
            seen[sec] = []
            sections.append({'name': sec, '_items': seen[sec]})
        seen[sec].append(item)

    return [
        {'name': s['name'], 'items': s['_items'],
         'subtotal': sum(i.total_price for i in s['_items'])}
        for s in sections
    ]


def generate_qr(invoice):
    try:
        import qrcode, io
        iban = (invoice.issuer_iban or '').replace(' ', '')
        payment_data = (
            f"BCD\n002\n1\nSCT\n{invoice.swift or ''}\n"
            f"{invoice.issuer_name}\n{iban}\n"
            f"EUR{invoice.total}\n\n{invoice.number}\n"
            f"Zahlung {invoice.number}"
        )
        qr = qrcode.QRCode(version=1, box_size=5, border=2)
        qr.add_data(payment_data)
        qr.make(fit=True)
        img = qr.make_image(fill_color='black', back_color='white')
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return base64.b64encode(buf.getvalue()).decode()
    except ValueError:
        return ''


def generate_zki(invoice, cert_key='demo_key'):
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


def _logo_to_data_uri(path):
    with open(path, 'rb') as f:
        data = f.read()
    if data[:4] == bytes([0x89, 0x50, 0x4e, 0x47]):
        mime = 'image/png'
    elif data[:2] == bytes([0xff, 0xd8]):
        mime = 'image/jpeg'
    elif data[:4] in (b'<svg', b'\xef\xbb\xbf<'):
        mime = 'image/svg+xml'
    else:
        mime = 'image/png'
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def _get_company_logo_b64(invoice):
    try:
        company = invoice.company
        if not company:
            return ''
        if company.logo and company.logo.name:
            try:
                path = company.logo.path
                if _os.path.exists(path):
                    return _logo_to_data_uri(path)
            except OSError:
                pass
        settings = company.settings or {}
        path = settings.get('logo_path', '')
        if path and _os.path.exists(path):
            return _logo_to_data_uri(path)
    except OSError:
        pass
    return ''


def _get_lc_brand_qr_b64():
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
    except ValueError:
        return ''


def _pick_template(invoice, lang):
    from django.template.loader import get_template
    from django.template.exceptions import TemplateDoesNotExist

    pdf_tmpl = 'viskovic'
    try:
        if invoice.company:
            pdf_tmpl = invoice.company.pdf_template or 'viskovic'
    except AttributeError:
        pass

    lang_key = 'hr' if lang == 'hr' else 'de'
    tmap = TEMPLATE_MAP.get(pdf_tmpl, TEMPLATE_MAP['viskovic'])
    template_name = tmap.get(lang_key, TEMPLATE_FALLBACK[lang_key])

    try:
        get_template(template_name)
    except TemplateDoesNotExist:
        template_name = TEMPLATE_FALLBACK[lang_key]

    return template_name


def render_invoice_html(invoice, request=None):
    """Render invoice to HTML string using correct template."""
    profile = getattr(invoice, 'invoice_profile', None)

    if profile and profile.language:
        render_lang = profile.language
    elif invoice.is_hr:
        render_lang = 'hr'
    else:
        render_lang = 'de'

    prev_lang = get_language()
    activate(render_lang)

    contacts = []
    try:
        s = invoice.company.settings or {}
        contacts = s.get('invoice_contacts', [])
    except AttributeError:
        pass

    extra_ctx = {
        'company_logo_src': _get_company_logo_b64(invoice),
        'lc_qr_b64':        _get_lc_brand_qr_b64(),
        'invoice_contacts': contacts,
    }

    try:
        if profile and getattr(profile, 'bilingual', False) and profile.secondary_language:
            from .bilingual_labels import get_bilingual_labels
            labels = get_bilingual_labels(render_lang, profile.secondary_language, invoice.doctype)
            return render_to_string('invoicing/invoice_bilingual.html', {
                'invoice': invoice,
                'now': timezone.now(),
                'request': request,
                'tax_groups': build_tax_groups(invoice),
                'sections': build_sections(invoice),
                'labels': labels,
                'primary_lang': render_lang,
                'secondary_lang': profile.secondary_language,
                **extra_ctx,
            })

        template = _pick_template(invoice, render_lang)
        return render_to_string(template, {
            'invoice': invoice,
            'now': timezone.now(),
            'request': request,
            'tax_groups': build_tax_groups(invoice),
            'sections': build_sections(invoice),
            **extra_ctx,
        })
    finally:
        if prev_lang:
            activate(prev_lang)


def generate_invoice_pdf(invoice, request=None):
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
