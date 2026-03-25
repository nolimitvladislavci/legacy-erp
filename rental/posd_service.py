"""
rental/posd_service.py — PO-SD Obrazac za iznajmljivače

PO-SD = Izvješće o paušalnom dohotku od samostalnih djelatnosti.
Predaje se Poreznoj upravi tromjesečno (rok: 15. sljedećeg mjeseca nakon kvartala).

Podaci:
  Dio I  — Osobni podaci iz LandlordProfile
  Dio II — Promet po kvartalima iz TrafficRecord (EP evidencija)
  Dio III— Paušalni porez: stalni kreveti × iznos po krevetu (JLS odluka)

NAPOMENA: Pomoćni kreveti se NE oporezuju paušalnim porezom na dohodak!
(Samo TZ članarina ih uključuje.)
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

_Q = Decimal('0.01')

# Rokovi predaje PO-SD
POSD_DEADLINES = {
    1: (4, 15),   # Q1 → 15. travnja
    2: (7, 15),   # Q2 → 15. srpnja
    3: (10, 15),  # Q3 → 15. listopada
    4: (1, 15),   # Q4 → 15. siječnja sljedeće godine
}


def generate_posd_data(company, year, quarter=None):
    """
    Prikupi podatke za PO-SD obrazac.

    Ako quarter=None → godišnji pregled (sva 4 kvartala).
    Ako quarter=1-4 → tromjesečni obrazac.
    """
    from rental.models import Property, AccommodationUnit, LandlordProfile, TrafficRecord

    # ═══ VALIDACIJA ═══
    try:
        profile = company.landlord_profile
    except LandlordProfile.DoesNotExist:
        raise ValueError('Nema profila iznajmljivača.')

    if not profile.is_pausal:
        raise ValueError(
            f'Iznajmljivač {profile.full_name} nije paušalac '
            f'(status: {profile.get_tax_status_display()}). PO-SD se generira samo za paušalce.'
        )

    # ═══ DIO I: OSOBNI PODACI ═══
    osobni = {
        'ime_prezime': profile.full_name,
        'oib': company.oib or '',
        'adresa': f'{company.address}, {company.zip_code} {company.city}'.strip(', '),
        'porezna_uprava': profile.tax_office or '',
        'ispostava': profile.tax_branch or '',
        'djelatnost': f'{profile.nkd_code} — Iznajmljivanje smještaja',
        'pocetak_djelatnosti': profile.activity_start_date,
        'iban': company.iban or '',
    }

    # ═══ DIO II: PROMET PO KVARTALIMA (iz EP) ═══
    quarters = {}
    for q in range(1, 5):
        start_month = (q - 1) * 3 + 1
        end_month = q * 3
        q_total = TrafficRecord.objects.filter(
            company=company,
            date__year=year,
            date__month__gte=start_month,
            date__month__lte=end_month,
        ).aggregate(s=Sum('total'))['s'] or Decimal('0')
        quarters[q] = q_total.quantize(_Q)

    godisnji_promet = sum(quarters.values())

    # ═══ DIO III: OBRAČUN PAUŠALNOG POREZA ═══
    # Samo STALNI kreveti (pomoćni se ne oporezuju!)
    properties = Property.objects.filter(company=company, is_active=True)
    units = AccommodationUnit.objects.filter(
        rental_property__in=properties, is_active=True,
    )

    stalni_kreveti = sum(u.permanent_beds for u in units)
    if stalni_kreveti == 0:
        # Fallback: Property.capacity
        stalni_kreveti = sum(p.capacity or 0 for p in properties)

    # Iznos po krevetu — iz company.settings (JLS odluka)
    settings = getattr(company, 'settings', None) or {}
    porez_po_krevetu = Decimal(str(settings.get('posd_tax_per_bed', '0')))

    if porez_po_krevetu == 0:
        # Fallback na pausal_per_permanent_bed
        porez_po_krevetu = Decimal(str(settings.get('pausal_per_permanent_bed', '331.81')))

    godisnji_porez = (porez_po_krevetu * stalni_kreveti).quantize(_Q)

    # Prirez
    prirez_rate = Decimal(str(settings.get('prirez_rate', '0.10')))
    prirez = (godisnji_porez * prirez_rate).quantize(_Q)
    ukupno_godisnje = godisnji_porez + prirez

    # Tromjesečna rata
    tromjesecna_rata = (ukupno_godisnje / 4).quantize(_Q)
    zadnja_rata = ukupno_godisnje - tromjesecna_rata * 3

    # Rokovi
    rokovi = []
    for q in range(1, 5):
        m, d = POSD_DEADLINES[q]
        yr = year + 1 if q == 4 else year
        rata = zadnja_rata if q == 4 else tromjesecna_rata
        rokovi.append({
            'q': q,
            'promet': quarters[q],
            'rata': rata,
            'deadline': date(yr, m, d),
            'label': f'Q{q} ({_quarter_months(q)})',
        })

    # Efektivna stopa
    efektivna_stopa = Decimal('0')
    if godisnji_promet > 0:
        efektivna_stopa = (ukupno_godisnje / godisnji_promet * 100).quantize(Decimal('0.1'))

    # ═══ HUB-3A za Poreznu upravu ═══
    hub3a_data = {}
    pu_iban = settings.get('pu_iban', 'HR1210010051863000160')  # Državni proračun
    if pu_iban:
        try:
            from rental.hub3a import build_hub3a_string, generate_hub3a_base64
            oib = company.oib or ''
            for rok in rokovi:
                ref = f'1427-{oib}-{year}'
                hs = build_hub3a_string(
                    amount=rok['rata'],
                    sender_name=profile.full_name,
                    sender_address=company.address or '',
                    sender_city=f'{company.zip_code} {company.city}'.strip(),
                    receiver_name='Drzavni proracun RH',
                    receiver_address='',
                    receiver_city='10000 Zagreb',
                    receiver_iban=pu_iban,
                    model='HR68',
                    reference=ref,
                    purpose='OTHR',
                    description=f'Pausalni porez Q{rok["q"]}/{year}',
                )
                rok['hub3a_base64'] = generate_hub3a_base64(hs)
                rok['hub3a_reference'] = ref
        except Exception as e:
            logger.warning('PO-SD HUB-3A failed: %s', e)

    return {
        'year': year,
        'quarter': quarter,
        'generated_at': timezone.now(),
        'company': company,
        'profile': profile,

        # Dio I
        'osobni': osobni,

        # Dio II
        'quarters': quarters,
        'q1': quarters[1], 'q2': quarters[2],
        'q3': quarters[3], 'q4': quarters[4],
        'godisnji_promet': godisnji_promet,

        # Dio III
        'stalni_kreveti': stalni_kreveti,
        'porez_po_krevetu': porez_po_krevetu,
        'godisnji_porez': godisnji_porez,
        'prirez_rate': int(prirez_rate * 100),
        'prirez': prirez,
        'ukupno_godisnje': ukupno_godisnje,
        'tromjesecna_rata': tromjesecna_rata,
        'efektivna_stopa': efektivna_stopa,

        # Rokovi s HUB-3A
        'rokovi': rokovi,

        # Status
        'porez_konfiguriran': porez_po_krevetu > 0,
        'pu_iban': pu_iban,
    }


def generate_posd_pdf(company, year, quarter=None):
    """Generira PO-SD PDF."""
    data = generate_posd_data(company, year, quarter)
    html = render_to_string('rental/posd_form.html', data)

    from xhtml2pdf import pisa
    buffer = BytesIO()
    pisa.CreatePDF(html, dest=buffer, encoding='utf-8')
    buffer.seek(0)
    return buffer.read()


def generate_posd_xml(company, year, quarter=None):
    """XML za ePorezna upload."""
    data = generate_posd_data(company, year, quarter)

    root = ET.Element('POSDObrazac')
    root.set('version', '1.0')
    root.set('godina', str(year))

    # Obveznik
    ob = ET.SubElement(root, 'Obveznik')
    ET.SubElement(ob, 'ImePrezime').text = data['osobni']['ime_prezime']
    ET.SubElement(ob, 'OIB').text = data['osobni']['oib']
    ET.SubElement(ob, 'Adresa').text = data['osobni']['adresa']
    ET.SubElement(ob, 'PoreznaUprava').text = data['osobni']['porezna_uprava']
    ET.SubElement(ob, 'Ispostava').text = data['osobni']['ispostava']
    ET.SubElement(ob, 'Djelatnost').text = data['osobni']['djelatnost']
    ET.SubElement(ob, 'IBAN').text = data['osobni']['iban']

    # Promet
    promet = ET.SubElement(root, 'Promet')
    ET.SubElement(promet, 'Q1').text = f"{data['q1']:.2f}"
    ET.SubElement(promet, 'Q2').text = f"{data['q2']:.2f}"
    ET.SubElement(promet, 'Q3').text = f"{data['q3']:.2f}"
    ET.SubElement(promet, 'Q4').text = f"{data['q4']:.2f}"
    ET.SubElement(promet, 'Ukupno').text = f"{data['godisnji_promet']:.2f}"

    # Porez
    porez = ET.SubElement(root, 'Porez')
    ET.SubElement(porez, 'StalniKreveti').text = str(data['stalni_kreveti'])
    ET.SubElement(porez, 'IznosPoKrevetu').text = f"{data['porez_po_krevetu']:.2f}"
    ET.SubElement(porez, 'GodisnjiPorez').text = f"{data['godisnji_porez']:.2f}"
    ET.SubElement(porez, 'Prirez').text = f"{data['prirez']:.2f}"
    ET.SubElement(porez, 'Ukupno').text = f"{data['ukupno_godisnje']:.2f}"
    ET.SubElement(porez, 'TromjesecnaRata').text = f"{data['tromjesecna_rata']:.2f}"

    ET.indent(root, space='  ')
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding='unicode')


def _quarter_months(q):
    m = {1: 'sij–ožu', 2: 'tra–lip', 3: 'srp–ruj', 4: 'lis–pro'}
    return m.get(q, '')
