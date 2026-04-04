"""
PDV-S generator — izracun iz faktura + XML export.
"""
import xml.etree.ElementTree as ET
from xml.dom import minidom
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime


PDV_NS = 'http://e-porezna.porezna-uprava.hr/sheme/zahtjevi/PDV-S/v2-0'

# HR VAT rates
RATE_25 = Decimal('0.25')
RATE_13 = Decimal('0.13')
RATE_5 = Decimal('0.05')


def _q(val):
    return Decimal(str(val)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _classify_partner(partner):
    """Classify partner as domestic/eu/export."""
    oib = getattr(partner, 'oib', '') or getattr(partner, 'tax_id', '') or ''
    country = getattr(partner, 'country', '') or 'HR'
    country = str(country).upper().strip()

    if country == 'HR' or (len(oib) == 11 and oib.isdigit()):
        return 'domestic'

    eu_countries = {
        'AT', 'BE', 'BG', 'CY', 'CZ', 'DE', 'DK', 'EE', 'ES', 'FI',
        'FR', 'GR', 'HU', 'IE', 'IT', 'LT', 'LU', 'LV', 'MT', 'NL',
        'PL', 'PT', 'RO', 'SE', 'SI', 'SK'
    }
    if country in eu_countries:
        return 'eu'

    return 'export'


def _get_rate_bucket(tax_rate):
    """Map tax rate to bucket."""
    rate = Decimal(str(tax_rate))
    if rate >= Decimal('0.24'):
        return '25'
    elif rate >= Decimal('0.12'):
        return '13'
    elif rate >= Decimal('0.04'):
        return '5'
    return '0'


def generate_pdv_s(company, year, month, invoices_in, invoices_out):
    # GAP6: Include POS revenue in PDV-S calculation
    # POS bonovi koji NISU R1 (R1 su već u invoices_out) se dodaju kao gotovinski prihod
    try:
        from pos.models import POSReceipt
        pos_receipts = POSReceipt.objects.filter(
            session__terminal__company=company,
            status='paid',
            paid_at__year=year,
            paid_at__month=month,
            is_r1=False,  # R1 su u invoices_out
        )
        pos_subtotal = sum(r.subtotal or 0 for r in pos_receipts)
        pos_tax = sum(r.tax_amount or 0 for r in pos_receipts)
        pos_consumption_tax = sum(r.consumption_tax_amount or 0 for r in pos_receipts)
    except Exception:
        pos_subtotal = pos_tax = pos_consumption_tax = 0

    """
    Calculate PDV-S report from invoices.

    Args:
        company: Company instance
        year, month: reporting period
        invoices_in: queryset of received invoices (purchases)
        invoices_out: queryset of issued invoices (sales)

    Returns dict with all PDV-S sections.
    """
    data = {
        # I. Primljene isporuke
        'i1_base': Decimal('0'), 'i1_tax': Decimal('0'),  # domestic
        'i2_base': Decimal('0'), 'i2_tax': Decimal('0'),  # EU
        'i3_base': Decimal('0'), 'i3_tax': Decimal('0'),  # import

        # II. Obavljene isporuke
        'ii1_base': Decimal('0'), 'ii1_tax': Decimal('0'),  # 25%
        'ii2_base': Decimal('0'), 'ii2_tax': Decimal('0'),  # 13%
        'ii3_base': Decimal('0'), 'ii3_tax': Decimal('0'),  # 5%
        'ii4_base': Decimal('0'),  # exempt
        'ii5_base': Decimal('0'),  # EU
        'ii6_base': Decimal('0'),  # export
    }

    # Process incoming invoices (purchases/inputs)
    for inv in invoices_in:
        partner = getattr(inv, 'partner', None)
        region = _classify_partner(partner) if partner else 'domestic'
        base = _q(getattr(inv, "total", 0) - getattr(inv, 'tax_amount', 0))
        tax = _q(getattr(inv, 'tax_amount', 0))

        if region == 'domestic':
            data['i1_base'] += base
            data['i1_tax'] += tax
        elif region == 'eu':
            data['i2_base'] += base
            data['i2_tax'] += tax
        else:
            data['i3_base'] += base
            data['i3_tax'] += tax

    # Process outgoing invoices (sales/outputs)
    for inv in invoices_out:
        partner = getattr(inv, 'partner', None)
        region = _classify_partner(partner) if partner else 'domestic'
        base = _q(getattr(inv, "total", 0) - getattr(inv, 'tax_amount', 0))
        tax = _q(getattr(inv, 'tax_amount', 0))
        tax_rate = getattr(inv, 'tax_rate', None) or Decimal('0.25')

        if region == 'eu':
            data['ii5_base'] += base
        elif region == 'export':
            data['ii6_base'] += base
        else:
            bucket = _get_rate_bucket(tax_rate)
            if bucket == '25':
                data['ii1_base'] += base
                data['ii1_tax'] += tax
            elif bucket == '13':
                data['ii2_base'] += base
                data['ii2_tax'] += tax
            elif bucket == '5':
                data['ii3_base'] += base
                data['ii3_tax'] += tax
            else:
                data['ii4_base'] += base

    # III. Pretporez
    data['iii_total_pretporez'] = data['i1_tax'] + data['i2_tax'] + data['i3_tax']
    data['iii_ispravak'] = Decimal('0')

    # IV. Obveza
    data['iv_pdv_isporuke'] = data['ii1_tax'] + data['ii2_tax'] + data['ii3_tax']
    data['iv_pretporez'] = data['iii_total_pretporez']
    data['iv_razlika'] = data['iv_pdv_isporuke'] - data['iv_pretporez']

    # Quantize all
    for k in data:
        data[k] = _q(data[k])

    data['company'] = company
    data['year'] = year
    data['month'] = month

    return data


def generate_pdv_s_from_tax_period(company, year, month, user=None):
    """
    Bridge: Generate PDV-S report from existing TaxPeriod + invoice data.
    Combines TaxPeriod aggregates with invoice-level PDV-S detail.
    Returns PDVSReport instance.
    """
    from django.db import models as dm
    from invoicing.models import Invoice
    from pdv_s.models import PDVSReport

    # Get invoices for the period
    invoices_in = Invoice.objects.filter(
        company=company,
        date_issued__year=year,
        date_issued__month=month,
    ).filter(
        dm.Q(doctype='URA') | dm.Q(source='eracun')
    ).exclude(status__in=['DRAFT', 'CANCELLED', 'STORNO'])

    invoices_out = Invoice.objects.filter(
        company=company,
        date_issued__year=year,
        date_issued__month=month,
        doctype__in=['R', 'A', 'S', 'FA', 'RN', 'GS'],  # Porezni dokumenti + storno korekcija (čl. 78+79a ZoPDV)
    ).exclude(status__in=['DRAFT', 'CANCELLED', 'STORNO'])

    pdv_data = generate_pdv_s(company, year, month, invoices_in, invoices_out)

    report, created = PDVSReport.objects.update_or_create(
        company=company, year=year, month=month,
        defaults={
            'i1_base': pdv_data['i1_base'], 'i1_tax': pdv_data['i1_tax'],
            'i2_base': pdv_data['i2_base'], 'i2_tax': pdv_data['i2_tax'],
            'i3_base': pdv_data['i3_base'], 'i3_tax': pdv_data['i3_tax'],
            'ii1_base': pdv_data['ii1_base'], 'ii1_tax': pdv_data['ii1_tax'],
            'ii2_base': pdv_data['ii2_base'], 'ii2_tax': pdv_data['ii2_tax'],
            'ii3_base': pdv_data['ii3_base'], 'ii3_tax': pdv_data['ii3_tax'],
            'ii4_base': pdv_data['ii4_base'],
            'ii5_base': pdv_data['ii5_base'],
            'ii6_base': pdv_data['ii6_base'],
            'iii_total_pretporez': pdv_data['iii_total_pretporez'],
            'iii_ispravak': pdv_data['iii_ispravak'],
            'iv_pdv_isporuke': pdv_data['iv_pdv_isporuke'],
            'iv_pretporez': pdv_data['iv_pretporez'],
            'iv_razlika': pdv_data['iv_razlika'],
            'generated_by': user,
        }
    )
    return report


def batch_generate_pdv_s(year, month, user=None):
    """Generate PDV-S for ALL companies with pdv_status='obveznik'."""
    from companies.models import Company
    results = []
    companies = Company.objects.filter(pdv_status='obveznik')
    for c in companies:
        try:
            report = generate_pdv_s_from_tax_period(c, year, month, user)
            results.append({'company': c.name, 'oib': c.oib, 'status': 'ok',
                            'razlika': float(report.iv_razlika)})
        except Exception as e:
            results.append({'company': c.name, 'oib': c.oib, 'status': 'error',
                            'error': str(e)})
    return results


def generate_pdv_s_xml(company, year, month, pdv_data):
    """Generate PDV-S XML for e-Porezna submission."""
    root = ET.Element('ObrazacPDV')
    root.set('xmlns', PDV_NS)
    root.set('verzijaSheme', '2.0')

    # Zaglavlje
    zag = ET.SubElement(root, 'Zaglavlje')
    ET.SubElement(zag, 'OIB').text = company.oib
    ET.SubElement(zag, 'Naziv').text = company.name
    ET.SubElement(zag, 'Adresa').text = getattr(company, 'address', '') or ''
    ET.SubElement(zag, 'Mjesto').text = getattr(company, 'city', '') or ''
    ET.SubElement(zag, 'GodinaObracuna').text = str(year)
    ET.SubElement(zag, 'MjesecObracuna').text = str(month)
    ET.SubElement(zag, 'VrstaPrijave').text = 'R'  # R=redovna, I=ispravak
    ET.SubElement(zag, 'DatumIzvjesca').text = datetime.now().strftime('%Y-%m-%d')

    # I. Primljene isporuke
    sec1 = ET.SubElement(root, 'PrimljeneIsporuke')
    for tag, base_key, tax_key, label in [
        ('Tuzemne', 'i1_base', 'i1_tax', 'I.1'),
        ('StjecanjeEU', 'i2_base', 'i2_tax', 'I.2'),
        ('Uvoz', 'i3_base', 'i3_tax', 'I.3'),
    ]:
        el = ET.SubElement(sec1, tag)
        ET.SubElement(el, 'Osnovica').text = f"{pdv_data[base_key]:.2f}"
        ET.SubElement(el, 'Pretporez').text = f"{pdv_data[tax_key]:.2f}"

    # II. Obavljene isporuke
    sec2 = ET.SubElement(root, 'ObavljeneIsporuke')
    for tag, base_key, tax_key in [
        ('Oporezive25', 'ii1_base', 'ii1_tax'),
        ('Oporezive13', 'ii2_base', 'ii2_tax'),
        ('Oporezive5', 'ii3_base', 'ii3_tax'),
    ]:
        el = ET.SubElement(sec2, tag)
        ET.SubElement(el, 'Osnovica').text = f"{pdv_data[base_key]:.2f}"
        ET.SubElement(el, 'PDV').text = f"{pdv_data[tax_key]:.2f}"

    ET.SubElement(sec2, 'OslobodeneIsporuke').text = f"{pdv_data['ii4_base']:.2f}"
    ET.SubElement(sec2, 'IsporukeEU').text = f"{pdv_data['ii5_base']:.2f}"
    ET.SubElement(sec2, 'Izvoz').text = f"{pdv_data['ii6_base']:.2f}"

    # III. Pretporez
    sec3 = ET.SubElement(root, 'Pretporez')
    ET.SubElement(sec3, 'UkupniPretporez').text = f"{pdv_data['iii_total_pretporez']:.2f}"
    ET.SubElement(sec3, 'Ispravak').text = f"{pdv_data['iii_ispravak']:.2f}"

    # IV. Obveza
    sec4 = ET.SubElement(root, 'ObvezaPDV')
    ET.SubElement(sec4, 'PDVNaIsporuke').text = f"{pdv_data['iv_pdv_isporuke']:.2f}"
    ET.SubElement(sec4, 'UkupniPretporez').text = f"{pdv_data['iv_pretporez']:.2f}"
    ET.SubElement(sec4, 'Razlika').text = f"{pdv_data['iv_razlika']:.2f}"

    # Pretty print
    raw = ET.tostring(root, encoding='unicode')
    xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n' + raw
    try:
        dom = minidom.parseString(xml_str)
        xml_str = dom.toprettyxml(indent='  ')
    except Exception:
        pass

    return xml_str


def format_pdv_s_text(pdv_data):
    """Format PDV-S as text summary."""
    lines = [
        f"PDV-S OBRAZAC — {pdv_data['month']:02d}/{pdv_data['year']}",
        f"Firma: {pdv_data['company'].name} (OIB: {pdv_data['company'].oib})",
        "=" * 60,
        "",
        "I. PRIMLJENE ISPORUKE (ulaz)",
        f"  I.1 Tuzemne:       osnovica {pdv_data['i1_base']:>12.2f}  pretporez {pdv_data['i1_tax']:>10.2f}",
        f"  I.2 Stjecanje EU:  osnovica {pdv_data['i2_base']:>12.2f}  pretporez {pdv_data['i2_tax']:>10.2f}",
        f"  I.3 Uvoz:          osnovica {pdv_data['i3_base']:>12.2f}  pretporez {pdv_data['i3_tax']:>10.2f}",
        "",
        "II. OBAVLJENE ISPORUKE (izlaz)",
        f"  II.1 Oporezive 25%: osnovica {pdv_data['ii1_base']:>12.2f}  PDV {pdv_data['ii1_tax']:>10.2f}",
        f"  II.2 Oporezive 13%: osnovica {pdv_data['ii2_base']:>12.2f}  PDV {pdv_data['ii2_tax']:>10.2f}",
        f"  II.3 Oporezive  5%: osnovica {pdv_data['ii3_base']:>12.2f}  PDV {pdv_data['ii3_tax']:>10.2f}",
        f"  II.4 Oslobodene:             {pdv_data['ii4_base']:>12.2f}",
        f"  II.5 Isporuke u EU:          {pdv_data['ii5_base']:>12.2f}",
        f"  II.6 Izvoz:                  {pdv_data['ii6_base']:>12.2f}",
        "",
        "III. PRETPOREZ",
        f"  Ukupni pretporez:  {pdv_data['iii_total_pretporez']:>12.2f}",
        f"  Ispravak:          {pdv_data['iii_ispravak']:>12.2f}",
        "",
        "IV. OBVEZA PDV-a",
        f"  PDV na isporuke:   {pdv_data['iv_pdv_isporuke']:>12.2f}",
        f"  Pretporez:         {pdv_data['iv_pretporez']:>12.2f}",
        f"  RAZLIKA:           {pdv_data['iv_razlika']:>12.2f}",
        "",
    ]

    if pdv_data['iv_razlika'] > 0:
        lines.append(f"  >>> ZA UPLATU: {pdv_data['iv_razlika']:.2f} EUR")
    elif pdv_data['iv_razlika'] < 0:
        lines.append(f"  >>> ZA POVRAT: {abs(pdv_data['iv_razlika']):.2f} EUR")
    else:
        lines.append("  >>> NULA — nema obveze")

    return "\n".join(lines)
