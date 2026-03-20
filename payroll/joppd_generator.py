"""
JOPPD XML Generator - Izvjesce o primicima, porezu na dohodak i prirezu
te doprinosima za obvezna osiguranja.
Format: JOPPD v4.0 (2024+)
"""
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime, date
from decimal import Decimal
import calendar


JOPPD_NS = 'http://e-porezna.porezna-uprava.hr/sheme/zahtjevi/ObscePorezanDohodak/v4-0'
META_NS = 'http://e-porezna.porezna-uprava.hr/sheme/Metapodaci/v2-0'


def _breakdown_from_payslip(ps):
    """Recalculate detailed breakdown from Payslip using hr_calculator."""
    from .hr_calculator import izracunaj_placu
    r = izracunaj_placu(ps.gross_amount)
    return {
        'bruto': r['bruto'],
        'mio_1': r['mio_1_stup'],
        'mio_2': r['mio_2_stup'],
        'dohodak': r['dohodak'],
        'osobni_odbitak': r['osobni_odbitak'],
        'porezna_osnovica': r['porezna_osnovica'],
        'porez': r['porez'],
        'prirez': r['prirez'],
        'neto': r['neto'],
        'zdravstvo': r['doprinos_zdravstvo'],
    }


def generate_joppd_xml(company, payroll_run, payslips, oznaka=None):
    """
    Generate JOPPD XML for a payroll run.

    Args:
        company: Company instance
        payroll_run: PayrollRun instance
        payslips: queryset or list of Payslip instances
        oznaka: JOPPD oznaka izvjesca (default: auto)
    """
    if oznaka is None:
        last_day = calendar.monthrange(payroll_run.year, payroll_run.month)[1]
        day_of_year = date(payroll_run.year, payroll_run.month, last_day).timetuple().tm_yday
        oznaka = f"{payroll_run.year % 100}{day_of_year:03d}"

    root = ET.Element('ObrazacJOPPD')
    root.set('xmlns', JOPPD_NS)
    root.set('verzijaSheme', '4.0')

    # Metapodaci
    meta = ET.SubElement(root, 'Metapodaci')
    meta.set('xmlns', META_NS)
    ET.SubElement(meta, 'Naslov').text = 'Obrazac JOPPD'
    ET.SubElement(meta, 'Autor').text = company.name
    ET.SubElement(meta, 'Datum').text = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    ET.SubElement(meta, 'Format').text = 'text/xml'
    ET.SubElement(meta, 'Jezik').text = 'hr-HR'
    ET.SubElement(meta, 'Identifikator').text = f'JOPPD-{company.oib}-{oznaka}'
    ET.SubElement(meta, 'Uskladjenost').text = 'ObscePorezanDohodak-v4-0'
    ET.SubElement(meta, 'Tip').text = 'Elektronicki obrazac'
    ET.SubElement(meta, 'Adresant').text = 'Ministarstvo Financija, Porezna Uprava'

    # Strana A — zaglavlje
    strana_a = ET.SubElement(root, 'StranaA')
    ET.SubElement(strana_a, 'DatumIzvjesca').text = datetime.now().strftime('%Y-%m-%d')
    ET.SubElement(strana_a, 'OznakaIzvjesca').text = str(oznaka)
    ET.SubElement(strana_a, 'VrstaIzvjesca').text = '1'

    podnositelj = ET.SubElement(strana_a, 'Podnositelj')
    ET.SubElement(podnositelj, 'Naziv').text = company.name
    ET.SubElement(podnositelj, 'OIB').text = company.oib
    ET.SubElement(podnositelj, 'Adresa').text = company.address or ''
    ET.SubElement(podnositelj, 'Mjesto').text = company.city or ''

    razdoblje = ET.SubElement(strana_a, 'Razdoblje')
    last_day = calendar.monthrange(payroll_run.year, payroll_run.month)[1]
    ET.SubElement(razdoblje, 'DatumOd').text = f"{payroll_run.year}-{payroll_run.month:02d}-01"
    ET.SubElement(razdoblje, 'DatumDo').text = f"{payroll_run.year}-{payroll_run.month:02d}-{last_day:02d}"

    # Izracunaj totale
    breakdowns = []
    for ps in payslips:
        bd = _breakdown_from_payslip(ps)
        bd['employee'] = ps.user
        breakdowns.append(bd)

    t_bruto = sum(b['bruto'] for b in breakdowns)
    t_mio1 = sum(b['mio_1'] for b in breakdowns)
    t_mio2 = sum(b['mio_2'] for b in breakdowns)
    t_porez = sum(b['porez'] for b in breakdowns)
    t_prirez = sum(b['prirez'] for b in breakdowns)
    t_zdravstvo = sum(b['zdravstvo'] for b in breakdowns)
    t_neto = sum(b['neto'] for b in breakdowns)

    ukupno = ET.SubElement(strana_a, 'UkupnoIznosi')
    ET.SubElement(ukupno, 'BrojPrimatelja').text = str(len(breakdowns))
    ET.SubElement(ukupno, 'UkupnoBruto').text = f"{t_bruto:.2f}"
    ET.SubElement(ukupno, 'UkupnoMIO1').text = f"{t_mio1:.2f}"
    ET.SubElement(ukupno, 'UkupnoMIO2').text = f"{t_mio2:.2f}"
    ET.SubElement(ukupno, 'UkupnoPorez').text = f"{t_porez:.2f}"
    ET.SubElement(ukupno, 'UkupnoPrirez').text = f"{t_prirez:.2f}"
    ET.SubElement(ukupno, 'UkupnoZdravstvo').text = f"{t_zdravstvo:.2f}"
    ET.SubElement(ukupno, 'UkupnoNeto').text = f"{t_neto:.2f}"

    # Strana B — po zaposleniku
    strana_b = ET.SubElement(root, 'StranaB')
    for idx, bd in enumerate(breakdowns, 1):
        emp = bd['employee']
        primatelj = ET.SubElement(strana_b, 'Primatelj')
        ET.SubElement(primatelj, 'RedniBroj').text = str(idx)

        # OIB zaposlenika
        emp_oib = ''
        try:
            from accounts.models import UserProfile
            profile = UserProfile.objects.get(user=emp)
            if hasattr(profile, 'tax_id'):
                emp_oib = profile.tax_id or ''
        except Exception:
            pass

        ET.SubElement(primatelj, 'OIB').text = emp_oib
        ET.SubElement(primatelj, 'ImePrezime').text = emp.get_full_name() or emp.username
        ET.SubElement(primatelj, 'OznakaPrimitka').text = '0001'
        ET.SubElement(primatelj, 'OznakaStjecatelja').text = '0001'

        ET.SubElement(primatelj, 'Bruto').text = f"{bd['bruto']:.2f}"
        ET.SubElement(primatelj, 'MIO1').text = f"{bd['mio_1']:.2f}"
        ET.SubElement(primatelj, 'MIO2').text = f"{bd['mio_2']:.2f}"
        ET.SubElement(primatelj, 'Dohodak').text = f"{bd['dohodak']:.2f}"
        ET.SubElement(primatelj, 'OsobniOdbitak').text = f"{bd['osobni_odbitak']:.2f}"
        ET.SubElement(primatelj, 'PoreznaOsnovica').text = f"{bd['porezna_osnovica']:.2f}"
        ET.SubElement(primatelj, 'Porez').text = f"{bd['porez']:.2f}"
        ET.SubElement(primatelj, 'Prirez').text = f"{bd['prirez']:.2f}"
        ET.SubElement(primatelj, 'Neto').text = f"{bd['neto']:.2f}"
        ET.SubElement(primatelj, 'DoprinosZdravstvo').text = f"{bd['zdravstvo']:.2f}"
        ET.SubElement(primatelj, 'NacinIsplate').text = '2'
        ET.SubElement(primatelj, 'SatiRada').text = '176'

    # Pretty print
    raw = ET.tostring(root, encoding='unicode')
    xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n' + raw
    try:
        dom = minidom.parseString(xml_str)
        xml_str = dom.toprettyxml(indent='  ')
    except Exception:
        pass

    return xml_str
