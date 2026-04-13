"""
rental/tz2_service.py — TZ-2 Obrazac + XML za ePorezna

TZ-2 = Prijava kapaciteta i obračun ČLANARINE turističkoj zajednici.
NE miješati s paušalnim porezom na dohodak (to je PO-SD).

Članarina (Zakon o članarinama u TZ, NN 52/19, 144/20):
  Stalni krevet:  5,97 EUR godišnje
  Pomoćni krevet: 2,99 EUR godišnje (50% stalnog)

Inovacija #1: Potpomognuta područja — 20% popust na članarinu
  (čl.7 st.2 — I. do IV. razvojna skupina)
  
Inovacija #2: Točka 17 — ukupni primitci auto iz EP evidencije

Inovacija #3: XML export za ePorezna (uz PDF za arhivu)
"""
import logging
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO
import xml.etree.ElementTree as ET

from django.db.models import Sum
from django.template.loader import render_to_string
from django.utils import timezone

logger = logging.getLogger(__name__)

# Zakonske stope članarine TZ (NN 52/19)
TZ_FEE_PERMANENT = Decimal('5.97')   # EUR po stalnom krevetu
TZ_FEE_AUXILIARY = Decimal('2.99')    # EUR po pomoćnom krevetu
TZ_ASSISTED_DISCOUNT = Decimal('0.80')  # 20% popust = množitelj 0.80
_Q = Decimal('0.01')


def generate_tz2_data(company, year=None):
    """
    Prikupi SVE podatke za TZ-2 obrazac.

    Uključuje:
      - Osobne podatke iznajmljivača (LandlordProfile)
      - Objekte i smještajne jedinice (AccommodationUnit)
      - Članarinu TZ (5,97/2,99 po krevetu)
      - Paušalni porez posebno (iz company.settings)
      - Ukupne primitke iz EP evidencije (Točka 17)
      - Popust 20% za potpomognuta područja
    """
    from rental.models import Property, AccommodationUnit, LandlordProfile, TrafficRecord

    if year is None:
        year = timezone.now().year

    # Profil iznajmljivača
    try:
        profile = company.landlord_profile
    except LandlordProfile.DoesNotExist:
        raise ValueError(
            f'Firma {company.name} nema profil iznajmljivača. '
            f'Kreirajte ga u Admin → Rental → Profili iznajmljivača.'
        )

    # Objekti s jedinicama
    properties = Property.objects.filter(
        company=company, is_active=True,
    ).prefetch_related('units')

    if not properties.exists():
        raise ValueError(f'Firma {company.name} nema aktivnih objekata.')

    property_data = []
    total_permanent = 0
    total_auxiliary = 0
    any_assisted = False

    for prop in properties:
        units = prop.units.filter(is_active=True)
        prop_permanent = sum(u.permanent_beds for u in units)
        prop_auxiliary = sum(u.auxiliary_beds for u in units)

        if not units.exists():
            prop_permanent = prop.capacity or 0
            prop_auxiliary = 0

        total_permanent += prop_permanent
        total_auxiliary += prop_auxiliary

        # Potpomognuto područje check
        is_assisted = getattr(prop, 'is_assisted_area', False)
        if is_assisted:
            any_assisted = True

        expired_units = [u for u in units if u.categorization_expired]

        property_data.append({
            'property': prop,
            'units': list(units),
            'permanent_beds': prop_permanent,
            'auxiliary_beds': prop_auxiliary,
            'total_beds': prop_permanent + prop_auxiliary,
            'expired_units': expired_units,
            'razred': getattr(prop, 'razred_mjesta', '') or 'A',
            'is_assisted': is_assisted,
        })

    # ═══ ČLANARINA TZ (zakonske stope) ═══
    fee_permanent = (TZ_FEE_PERMANENT * total_permanent).quantize(_Q)
    fee_auxiliary = (TZ_FEE_AUXILIARY * total_auxiliary).quantize(_Q)
    fee_total = fee_permanent + fee_auxiliary

    # Inovacija #1: Popust 20% za potpomognuta područja
    assisted_discount = Decimal('0')
    if any_assisted:
        assisted_discount = (fee_total * (1 - TZ_ASSISTED_DISCOUNT)).quantize(_Q)
        fee_after_discount = (fee_total * TZ_ASSISTED_DISCOUNT).quantize(_Q)
    else:
        fee_after_discount = fee_total

    # Rate (3 rate: do 31.1., 30.4., 31.7.)
    rate_amount = (fee_after_discount / 3).quantize(_Q)
    rate_last = fee_after_discount - rate_amount * 2
    tz_rates = [
        {'r': 1, 'amount': rate_amount, 'deadline': date(year, 1, 31)},
        {'r': 2, 'amount': rate_amount, 'deadline': date(year, 4, 30)},
        {'r': 3, 'amount': rate_last, 'deadline': date(year, 7, 31)},
    ]

    # ═══ PAUŠALNI POREZ (JLS odluka, odvojeno od članarine) ═══
    settings = getattr(company, 'settings', None) or {}
    pausal_per_permanent = Decimal(str(settings.get('pausal_per_permanent_bed', '331.81')))
    pausal_per_auxiliary = Decimal(str(settings.get('pausal_per_auxiliary_bed', '265.45')))
    annual_tax = (pausal_per_permanent * total_permanent + pausal_per_auxiliary * total_auxiliary).quantize(_Q)
    prirez_rate = Decimal(str(settings.get('prirez_rate', '0.10')))
    prirez = (annual_tax * prirez_rate).quantize(_Q)
    tax_total = annual_tax + prirez
    tax_quarterly = (tax_total / 4).quantize(_Q)
    tax_quarterly_last = tax_total - tax_quarterly * 3

    # ═══ Inovacija #2: Ukupni primitci iz EP (Točka 17) ═══
    prev_year = year - 1
    ep_total = TrafficRecord.objects.filter(
        company=company,
        date__year=prev_year,
    ).aggregate(s=Sum('total'))['s'] or Decimal('0')

    ep_quarters = {}
    for q in range(1, 5):
        start_month = (q - 1) * 3 + 1
        end_month = q * 3
        q_total = TrafficRecord.objects.filter(
            company=company,
            date__year=prev_year,
            date__month__gte=start_month,
            date__month__lte=end_month,
        ).aggregate(s=Sum('total'))['s'] or Decimal('0')
        ep_quarters[f'q{q}'] = q_total

    # Pripremi data dict za HUB-3A
    locals_data = {
        'profile': profile, 'company': company, 'year': year,
        'tz_fee_total': fee_after_discount, 'tz_rates': tz_rates,
        'properties': property_data,
    }
    hub3a = {}
    try:
        from rental.hub3a import build_tz_membership_hub3a
        hub3a = build_tz_membership_hub3a(locals_data)
    except ImportError as e:
        logger.warning('HUB-3A generation failed: %s', e)

    return {
        'year': year,
        'prev_year': prev_year,
        'generated_at': timezone.now(),
        'deadline': date(year, 1, 15),

        'profile': profile,
        'company': company,

        'properties': property_data,
        'total_permanent': total_permanent,
        'total_auxiliary': total_auxiliary,
        'total_beds': total_permanent + total_auxiliary,

        # Članarina TZ
        'tz_fee_permanent_rate': TZ_FEE_PERMANENT,
        'tz_fee_auxiliary_rate': TZ_FEE_AUXILIARY,
        'tz_fee_permanent': fee_permanent,
        'tz_fee_auxiliary': fee_auxiliary,
        'tz_fee_subtotal': fee_total,
        'tz_assisted_discount': assisted_discount,
        'tz_any_assisted': any_assisted,
        'tz_fee_total': fee_after_discount,
        'tz_rates': tz_rates,

        # Paušalni porez (odvojeno)
        'tax_per_permanent': pausal_per_permanent,
        'tax_per_auxiliary': pausal_per_auxiliary,
        'tax_annual': annual_tax,
        'tax_prirez_rate': int(prirez_rate * 100),
        'tax_prirez': prirez,
        'tax_total': tax_total,
        'tax_quarterly': tax_quarterly,
        'tax_quarterly_last': tax_quarterly_last,

        # Točka 17 — primitci iz EP
        'ep_total': ep_total,
        'ep_quarters': ep_quarters,
        'ep_year': prev_year,

        # HUB-3A barkodovi
        'hub3a': hub3a,
        'hub3a_total_base64': hub3a.get('hub3a_base64', ''),
        'hub3a_rates': hub3a.get('rates', []),
        'hub3a_iban': hub3a.get('iban', ''),
        'hub3a_model': hub3a.get('model', ''),
        'hub3a_reference': hub3a.get('reference', ''),
    }


def generate_tz2_pdf(company, year=None):
    """Generira TZ-2 PDF obrazac."""
    data = generate_tz2_data(company, year)
    html = render_to_string('rental/tz2_form.html', data)

    from xhtml2pdf import pisa
    buffer = BytesIO()
    pisa_status = pisa.CreatePDF(html, dest=buffer, encoding='utf-8')
    if pisa_status.err:
        raise RuntimeError(f'PDF generation error: {pisa_status.err}')
    buffer.seek(0)
    return buffer.read()


def generate_tz2_xml(company, year=None):
    """
    Inovacija #3: XML za ePorezna upload.

    Format prema ePorezna shemi za TZ-2 obrazac.
    Marija preuzme XML, ulogira se na ePorezna, uploada.
    """
    data = generate_tz2_data(company, year)

    root = ET.Element('TZ2Obrazac')
    root.set('version', '1.0')
    root.set('godina', str(data['year']))

    # Obveznik
    obveznik = ET.SubElement(root, 'PodaciOObvezniku')
    ET.SubElement(obveznik, 'ImePrezime').text = data['profile'].full_name
    ET.SubElement(obveznik, 'OIB').text = data['company'].oib or ''
    ET.SubElement(obveznik, 'Adresa').text = f"{data['company'].address}, {data['company'].zip_code} {data['company'].city}"
    ET.SubElement(obveznik, 'IBAN').text = data['company'].iban or ''
    ET.SubElement(obveznik, 'NKD').text = data['profile'].nkd_code or '55.20'
    ET.SubElement(obveznik, 'TuristickaZajednica').text = data['profile'].tz_name or ''
    ET.SubElement(obveznik, 'PoreznaIspostava').text = data['profile'].tax_office or ''

    # Objekti i kapaciteti
    kapaciteti = ET.SubElement(root, 'Kapaciteti')
    for p in data['properties']:
        obj = ET.SubElement(kapaciteti, 'Objekt')
        ET.SubElement(obj, 'Naziv').text = p['property'].name
        ET.SubElement(obj, 'Adresa').text = p['property'].location or ''
        ET.SubElement(obj, 'Razred').text = p['razred']
        ET.SubElement(obj, 'PotpomognutoPodručje').text = 'DA' if p['is_assisted'] else 'NE'

        for u in p['units']:
            jed = ET.SubElement(obj, 'SmjestajnaJedinica')
            ET.SubElement(jed, 'Oznaka').text = u.name
            ET.SubElement(jed, 'Vrsta').text = u.get_unit_type_display()
            ET.SubElement(jed, 'StalniKreveti').text = str(u.permanent_beds)
            ET.SubElement(jed, 'PomocniKreveti').text = str(u.auxiliary_beds)

    ET.SubElement(kapaciteti, 'UkupnoStalniKreveti').text = str(data['total_permanent'])
    ET.SubElement(kapaciteti, 'UkupnoPomocniKreveti').text = str(data['total_auxiliary'])

    # Članarina
    clanarina = ET.SubElement(root, 'Clanarina')
    ET.SubElement(clanarina, 'StalniKreveti').text = f"{data['tz_fee_permanent']:.2f}"
    ET.SubElement(clanarina, 'PomocniKreveti').text = f"{data['tz_fee_auxiliary']:.2f}"
    ET.SubElement(clanarina, 'Ukupno').text = f"{data['tz_fee_subtotal']:.2f}"
    ET.SubElement(clanarina, 'PopustPotpomognuto').text = f"{data['tz_assisted_discount']:.2f}"
    ET.SubElement(clanarina, 'ZaUplatu').text = f"{data['tz_fee_total']:.2f}"

    # Točka 17 — primitci
    primitci = ET.SubElement(root, 'Primitci')
    ET.SubElement(primitci, 'Godina').text = str(data['ep_year'])
    ET.SubElement(primitci, 'Ukupno').text = f"{data['ep_total']:.2f}"
    for k, v in data['ep_quarters'].items():
        ET.SubElement(primitci, k.upper()).text = f"{v:.2f}"

    ET.indent(root, space='  ')
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding='unicode')
