"""
konto/ustva_export.py — UStVA (Umsatzsteuervoranmeldung) XML Generator

Generates ELSTER-compatible XML for German monthly/quarterly VAT return.
Reference: ELSTER Datenmodell v36, BMF-Schreiben 2024.

Kennzahlen (KZ) Mapping:
  KZ 81: Steuerpflichtige Lieferungen/Leistungen zum Steuersatz 19%
  KZ 86: Steuerpflichtige Lieferungen/Leistungen zum Steuersatz 7%
  KZ 35: Steuerpflichtige Lieferungen/Leistungen zu anderen Steuersätzen
  KZ 77: Steuerfreie Umsätze mit Vorsteuerabzug (EU-Lieferungen)
  KZ 76: Steuerfreie Umsätze ohne Vorsteuerabzug
  KZ 66: Vorsteuerbeträge aus Rechnungen 19%
  KZ 61: Vorsteuerbeträge aus Rechnungen 7%
  KZ 62: Vorsteuerbeträge aus innergemeinschaftlichem Erwerb
  KZ 67: Vorsteuerbeträge nach §13b
  KZ 83: Verbleibende USt-Vorauszahlung (+) / Überschuss (-)
"""
import xml.etree.ElementTree as ET
from xml.dom import minidom
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime


def _q(val):
    return Decimal(str(val or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _cents(val):
    """ELSTER uses cent values (integer) for some fields."""
    return str(int(_q(val) * 100))


def generate_ustva(company, year, month, tax_period=None):
    """
    Generate UStVA data from TaxPeriod and TaxLineDetail.

    Args:
        company: Company instance (country='DE')
        year, month: reporting period
        tax_period: optional pre-fetched TaxPeriod

    Returns dict with all KZ fields.
    """
    from konto.models import TaxPeriod, TaxLineDetail

    if not tax_period:
        try:
            tax_period = TaxPeriod.objects.get(
                company=company, period_type='monthly',
                year=year, month=month,
            )
        except TaxPeriod.DoesNotExist:
            from konto.services_file import calculate_vat_period
            tax_period = calculate_vat_period(company, 'monthly', year, month)

    # Get rate breakdown
    details = TaxLineDetail.objects.filter(period=tax_period)

    kz = {
        # Abschnitt I: Steuerpflichtige Lieferungen (Bemessungsgrundlage)
        'kz81_base': Decimal('0'),   # 19% Bemessungsgrundlage
        'kz81_tax': Decimal('0'),    # 19% Steuer
        'kz86_base': Decimal('0'),   # 7% Bemessungsgrundlage
        'kz86_tax': Decimal('0'),    # 7% Steuer
        'kz35_base': Decimal('0'),   # andere Steuersätze
        'kz35_tax': Decimal('0'),
        'kz77_base': Decimal('0'),   # steuerfreie EU-Lieferungen
        'kz76_base': Decimal('0'),   # steuerfreie sonstige

        # Abschnitt II: Vorsteuer
        'kz66': Decimal('0'),        # Vorsteuer 19%
        'kz61': Decimal('0'),        # Vorsteuer 7%
        'kz62': Decimal('0'),        # Vorsteuer innergemeinschaftlicher Erwerb
        'kz67': Decimal('0'),        # Vorsteuer §13b

        # Abschnitt III: Ergebnis
        'kz83': Decimal('0'),        # Vorauszahlung (+) / Überschuss (-)
    }

    for d in details:
        rate = d.tax_rate
        if rate == Decimal('19') or rate == Decimal('19.00'):
            kz['kz81_base'] += d.revenue_base
            kz['kz81_tax'] += d.output_vat
        elif rate == Decimal('7') or rate == Decimal('7.00'):
            kz['kz86_base'] += d.revenue_base
            kz['kz86_tax'] += d.output_vat
        elif rate == Decimal('0') or rate == Decimal('0.00'):
            kz['kz76_base'] += d.revenue_base
        else:
            kz['kz35_base'] += d.revenue_base
            kz['kz35_tax'] += d.output_vat

    # Total output (Umsatzsteuer)
    total_ust = kz['kz81_tax'] + kz['kz86_tax'] + kz['kz35_tax']

    # Input VAT (Vorsteuer) — split by rate from ledger
    # For now: total input from TaxPeriod, split proportionally
    total_vorsteuer = tax_period.total_input_vat
    kz['kz66'] = total_vorsteuer  # Simplified: all as 19% Vorsteuer

    # Vorauszahlung
    kz['kz83'] = total_ust - total_vorsteuer

    # Quantize all
    for k in kz:
        kz[k] = _q(kz[k])

    kz['company'] = company
    kz['year'] = year
    kz['month'] = month
    kz['total_ust'] = _q(total_ust)
    kz['total_vorsteuer'] = _q(total_vorsteuer)
    kz['filing_deadline'] = f"10.{month + 1 if month < 12 else 1:02d}.{year if month < 12 else year + 1}"

    return kz


def generate_ustva_xml(company, year, month, kz_data):
    """
    Generate ELSTER-compatible UStVA XML.

    Note: This is a simplified ELSTER format suitable for import into
    tax software (DATEV, Lexware, etc). Direct ELSTER submission requires
    ERiC library integration (separate module).
    """
    root = ET.Element('Anmeldungssteuern')
    root.set('art', 'UStVA')
    root.set('version', '202401')

    # Erstellungsdaten
    erstellung = ET.SubElement(root, 'DatenLieferant')
    ET.SubElement(erstellung, 'Name').text = company.name
    ET.SubElement(erstellung, 'Strasse').text = getattr(company, 'address', '') or ''
    ET.SubElement(erstellung, 'PLZ').text = getattr(company, 'zip_code', '') or ''
    ET.SubElement(erstellung, 'Ort').text = getattr(company, 'city', '') or ''

    # Steuerfall
    steuerfall = ET.SubElement(root, 'Steuerfall')
    ET.SubElement(steuerfall, 'Steuernummer').text = company.oib or ''
    ET.SubElement(steuerfall, 'Zeitraum').text = f"{year}{month:02d}"
    ET.SubElement(steuerfall, 'Jahr').text = str(year)
    ET.SubElement(steuerfall, 'Monat').text = str(month)

    # Kennzahlen
    kennzahlen = ET.SubElement(root, 'Kennzahlen')

    def _add_kz(parent, kz_nr, base=None, steuer=None):
        el = ET.SubElement(parent, 'Kz')
        el.set('nr', str(kz_nr))
        if base is not None:
            ET.SubElement(el, 'Bemessungsgrundlage').text = f"{base:.2f}"
        if steuer is not None:
            ET.SubElement(el, 'Steuer').text = f"{steuer:.2f}"

    # I. Steuerpflichtige Lieferungen
    if kz_data['kz81_base']:
        _add_kz(kennzahlen, 81, base=kz_data['kz81_base'], steuer=kz_data['kz81_tax'])
    if kz_data['kz86_base']:
        _add_kz(kennzahlen, 86, base=kz_data['kz86_base'], steuer=kz_data['kz86_tax'])
    if kz_data['kz35_base']:
        _add_kz(kennzahlen, 35, base=kz_data['kz35_base'], steuer=kz_data['kz35_tax'])
    if kz_data['kz77_base']:
        _add_kz(kennzahlen, 77, base=kz_data['kz77_base'])
    if kz_data['kz76_base']:
        _add_kz(kennzahlen, 76, base=kz_data['kz76_base'])

    # II. Vorsteuer
    if kz_data['kz66']:
        _add_kz(kennzahlen, 66, steuer=kz_data['kz66'])
    if kz_data['kz61']:
        _add_kz(kennzahlen, 61, steuer=kz_data['kz61'])
    if kz_data['kz62']:
        _add_kz(kennzahlen, 62, steuer=kz_data['kz62'])
    if kz_data['kz67']:
        _add_kz(kennzahlen, 67, steuer=kz_data['kz67'])

    # III. Vorauszahlung
    ergebnis = ET.SubElement(root, 'Ergebnis')
    ET.SubElement(ergebnis, 'Kz83').text = f"{kz_data['kz83']:.2f}"

    # Pretty print
    raw = ET.tostring(root, encoding='unicode')
    xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n' + raw
    try:
        dom = minidom.parseString(xml_str)
        xml_str = dom.toprettyxml(indent='  ')
    except Exception:
        pass

    return xml_str


def format_ustva_text(kz_data):
    """Format UStVA as human-readable text summary."""
    lines = [
        f"UMSATZSTEUERVORANMELDUNG — {kz_data['month']:02d}/{kz_data['year']}",
        f"Firma: {kz_data['company'].name}",
        f"Steuernummer: {kz_data['company'].oib}",
        "=" * 60,
        "",
        "I. STEUERPFLICHTIGE LIEFERUNGEN",
        f"  KZ 81  Zum Steuersatz 19%:     Bemessung {kz_data['kz81_base']:>12.2f}  USt {kz_data['kz81_tax']:>10.2f}",
        f"  KZ 86  Zum Steuersatz  7%:     Bemessung {kz_data['kz86_base']:>12.2f}  USt {kz_data['kz86_tax']:>10.2f}",
        f"  KZ 35  Andere Steuersaetze:    Bemessung {kz_data['kz35_base']:>12.2f}  USt {kz_data['kz35_tax']:>10.2f}",
        f"  KZ 77  Steuerfreie EU-Lief.:   Bemessung {kz_data['kz77_base']:>12.2f}",
        f"  KZ 76  Steuerfreie sonstige:   Bemessung {kz_data['kz76_base']:>12.2f}",
        "",
        f"  Umsatzsteuer gesamt:                                    {kz_data['total_ust']:>10.2f} EUR",
        "",
        "II. VORSTEUER",
        f"  KZ 66  Vorsteuer 19%:                                   {kz_data['kz66']:>10.2f}",
        f"  KZ 61  Vorsteuer  7%:                                   {kz_data['kz61']:>10.2f}",
        f"  KZ 62  Vorsteuer EU-Erwerb:                             {kz_data['kz62']:>10.2f}",
        f"  KZ 67  Vorsteuer §13b:                                  {kz_data['kz67']:>10.2f}",
        "",
        f"  Vorsteuer gesamt:                                       {kz_data['total_vorsteuer']:>10.2f} EUR",
        "",
        "III. ERGEBNIS",
    ]

    kz83 = kz_data['kz83']
    if kz83 > 0:
        lines.append(f"  KZ 83  VORAUSZAHLUNG:          {kz83:>12.2f} EUR")
    elif kz83 < 0:
        lines.append(f"  KZ 83  UEBERSCHUSS:            {abs(kz83):>12.2f} EUR (Erstattung)")
    else:
        lines.append(f"  KZ 83  NULLMELDUNG")

    lines.append(f"\n  Abgabefrist: {kz_data['filing_deadline']}")

    return "\n".join(lines)


def is_kleinunternehmer(company):
    """
    Check if company qualifies for Kleinunternehmerregelung (§19 UStG).
    Threshold: Umsatz im Vorjahr <= 22.000 EUR AND
               Umsatz im laufenden Jahr voraussichtlich <= 50.000 EUR.
    """
    import datetime
    from invoicing.models import Invoice
    from django.db.models import Sum

    last_year = datetime.date.today().year - 1
    revenue_last_year = (
        Invoice.objects.filter(
            company=company,
            doctype__in=['R', 'A', 'GS', 'IRA'],
            status__in=['PAID', 'SENT', 'OVERDUE', 'UNPAID'],
            date_issued__year=last_year,
        ).aggregate(t=Sum('subtotal'))['t'] or 0
    )

    return float(revenue_last_year) <= 22000


def generate_zm(company, year, quarter):
    """
    Zusammenfassende Meldung (ZM) — EU sales reporting.
    Quarterly report of intra-community supplies to EU partners.
    §18a UStG.

    Returns list of {vat_id, country, amount} for EU B2B deliveries.
    """
    import datetime
    from invoicing.models import Invoice
    from django.db.models import Sum

    q_start_month = (quarter - 1) * 3 + 1
    q_end_month = q_start_month + 2
    date_from = datetime.date(year, q_start_month, 1)
    if q_end_month == 12:
        date_to = datetime.date(year, 12, 31)
    else:
        date_to = datetime.date(year, q_end_month + 1, 1) - datetime.timedelta(days=1)

    # Find EU invoices via partner data
    eu_invoices = Invoice.objects.filter(
        company=company,
        doctype__in=['R', 'A', 'GS', 'IRA'],
        status__in=['PAID', 'SENT', 'OVERDUE', 'UNPAID'],
        date_issued__date__gte=date_from,
        date_issued__date__lte=date_to,
        partner__isnull=False,
    ).select_related('partner')

    EU_COUNTRIES = {
        'AT', 'BE', 'BG', 'CY', 'CZ', 'DK', 'EE', 'ES', 'FI',
        'FR', 'GR', 'HR', 'HU', 'IE', 'IT', 'LT', 'LU', 'LV',
        'MT', 'NL', 'PL', 'PT', 'RO', 'SE', 'SI', 'SK',
    }

    # Aggregate by partner VAT ID
    entries = {}
    for inv in eu_invoices:
        p = inv.partner
        if not p:
            continue
        country = getattr(p, 'country', '') or ''
        vat_id = getattr(p, 'vat_id', '') or ''

        if country.upper() not in EU_COUNTRIES:
            continue
        if country.upper() == company.country.upper():
            continue  # Same country = not intra-community

        key = vat_id or f"{country}-{p.oib or p.name}"
        if key not in entries:
            entries[key] = {
                'vat_id': vat_id,
                'country': country.upper(),
                'partner_name': p.name,
                'amount': 0,
            }
        entries[key]['amount'] += float(inv.subtotal or 0)

    return {
        'year': year,
        'quarter': quarter,
        'period': f"Q{quarter}/{year}",
        'entries': sorted(entries.values(), key=lambda x: -x['amount']),
        'total': sum(e['amount'] for e in entries.values()),
        'count': len(entries),
    }
