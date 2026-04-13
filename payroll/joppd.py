"""
payroll/joppd.py — JOPPD obrazac generiranje

JOPPD (Izvješće o primicima, porezu na dohodak i prirezu te doprinosima
za obvezna osiguranja) je zakonski obvezno izvješće koje se predaje
e-Poreznoj upravi za svaki obračun plaće.

HR stope (2026):
  Doprinosi IZ plaće:
    - MIO I. stup:  20%
    - MIO II. stup:  0% (ukinut za nove) ili 5% (stari sustav)
  Doprinosi NA plaću:
    - Zdravstveno:   16.5%
  Porez na dohodak:
    - do 50.400€/god (4.200€/mj):  20%
    - iznad:                         30%
  Osobni odbitak: 560€/mj + uvećanja

XML format: JOPPD-v2, šalje se na ePorezna.hr
"""
import logging
from decimal import Decimal, ROUND_HALF_UP
from datetime import date
from xml.etree.ElementTree import Element, SubElement, tostring

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════
#  HR POREZNI ENGINE 2026
# ═══════════════════════════════════════════════════

# Stope
MIO_I_RATE = Decimal('0.20')       # I. stup mirovinskog
MIO_II_RATE = Decimal('0.00')      # II. stup (ukinut za većinu)
HEALTH_RATE = Decimal('0.165')     # Zdravstveno NA plaću

TAX_BRACKET_MONTHLY = Decimal('4200')  # Mjesečni prag (50.400€/god)
TAX_RATE_LOW = Decimal('0.20')
TAX_RATE_HIGH = Decimal('0.30')

PERSONAL_DEDUCTION = Decimal('560')  # Osnovni osobni odbitak


def calculate_hr_payslip(gross, personal_deduction=None, prirez_rate=Decimal('0')):
    """
    Izračunaj neto plaću po HR zakonu (2026).

    Args:
        gross: Bruto plaća
        personal_deduction: Osobni odbitak (default 560€)
        prirez_rate: Prirez općine/grada (npr. 0.18 za Osijek, 0.10 za Čepin)

    Returns dict:
        gross, mio_i, mio_ii, dohodak, osobni_odbitak, porezna_osnovica,
        porez, prirez, ukupno_porez, neto, doprinosi_na (zdravstveno)
    """
    if personal_deduction is None:
        personal_deduction = PERSONAL_DEDUCTION

    gross = Decimal(str(gross))

    # 1. Doprinosi IZ plaće
    mio_i = (gross * MIO_I_RATE).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    mio_ii = (gross * MIO_II_RATE).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    total_mio = mio_i + mio_ii

    # 2. Dohodak = bruto - MIO
    dohodak = gross - total_mio

    # 3. Porezna osnovica = dohodak - osobni odbitak
    porezna_osnovica = max(Decimal('0'), dohodak - personal_deduction)

    # 4. Porez
    if porezna_osnovica <= TAX_BRACKET_MONTHLY:
        porez = (porezna_osnovica * TAX_RATE_LOW).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    else:
        porez_low = (TAX_BRACKET_MONTHLY * TAX_RATE_LOW).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        porez_high = ((porezna_osnovica - TAX_BRACKET_MONTHLY) * TAX_RATE_HIGH).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        porez = porez_low + porez_high

    # 5. Prirez (postotak na porez)
    prirez = (porez * prirez_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    # 6. Ukupno porez + prirez
    ukupno_porez = porez + prirez

    # 7. Neto = dohodak - porez - prirez
    neto = dohodak - ukupno_porez

    # 8. Doprinosi NA plaću (plaća poslodavac, ne smanjuju neto)
    zdravstveno = (gross * HEALTH_RATE).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    return {
        'gross': gross,
        'mio_i': mio_i,
        'mio_ii': mio_ii,
        'total_mio': total_mio,
        'dohodak': dohodak,
        'osobni_odbitak': personal_deduction,
        'porezna_osnovica': porezna_osnovica,
        'porez': porez,
        'prirez': prirez,
        'prirez_rate': prirez_rate,
        'ukupno_porez': ukupno_porez,
        'neto': neto,
        'zdravstveno_na': zdravstveno,
        'total_cost': gross + zdravstveno,  # Ukupni trošak poslodavca
    }


def calculate_payroll_run(payroll_run, prirez_rate=Decimal('0')):
    """
    Izračunaj sve payslipove u payroll runu.
    Koristi worktime.TimeEntry za sate, EmployeeProfile za satnice.
    """
    from payroll.models import Payslip
    from worktime.models import TimeEntry, EmployeeProfile

    company = payroll_run.company
    year = payroll_run.year
    month = payroll_run.month

    total_gross = Decimal('0')
    total_net = Decimal('0')
    total_tax = Decimal('0')

    # Nađi sve zaposlenike s EmployeeProfile
    profiles = EmployeeProfile.objects.filter(company=company)

    for profile in profiles:
        user = profile.user

        # Agregiraj sate iz TimeEntry
        entries = TimeEntry.objects.filter(
            user=user,
            date__year=year,
            date__month=month,
            status='approved',
        )

        from django.db.models import Sum
        agg = entries.aggregate(
            reg=Sum('regular_hours'),
            ot=Sum('overtime_hours'),
            night=Sum('night_hours'),
        )
        regular = Decimal(str(agg['reg'] or 0))
        overtime = Decimal(str(agg['ot'] or 0))
        night = Decimal(str(agg['night'] or 0))
        total = regular + overtime + night

        # Izračunaj bruto
        hourly = Decimal(str(profile.hourly_rate or 0))
        ot_rate = Decimal(str(profile.overtime_rate or hourly * Decimal('1.5')))
        gross = (regular * hourly) + (overtime * ot_rate) + (night * hourly * Decimal('1.25'))

        if gross <= 0:
            continue

        # Izračunaj neto
        calc = calculate_hr_payslip(gross, prirez_rate=prirez_rate)

        # Create/update payslip
        slip, created = Payslip.objects.update_or_create(
            payroll_run=payroll_run,
            user=user,
            defaults={
                'regular_hours': regular,
                'overtime_hours': overtime,
                'night_hours': night,
                'total_hours': total,
                'hourly_rate_snapshot': hourly,
                'overtime_rate_snapshot': ot_rate,
                'gross_amount': calc['gross'],
                'contributions_amount': calc['total_mio'],
                'tax_base': calc['porezna_osnovica'],
                'tax_amount': calc['ukupno_porez'],
                'net_amount': calc['neto'],
                'employee_iban': getattr(profile, 'bank_iban', '') or '',
            }
        )

        total_gross += calc['gross']
        total_net += calc['neto']
        total_tax += calc['ukupno_porez']

    # Update run totals
    payroll_run.total_gross = total_gross
    payroll_run.total_net = total_net
    payroll_run.total_tax = total_tax
    payroll_run.save(update_fields=['total_gross', 'total_net', 'total_tax'])

    return payroll_run


# ═══════════════════════════════════════════════════
#  JOPPD XML GENERIRANJE
# ═══════════════════════════════════════════════════

def generate_joppd_xml(payroll_run):
    """
    Generira JOPPD XML za ePorezna predaju.

    Struktura:
      <JOPPD xmlns="...">
        <Zaglavlje> ... meta podaci ...
        <StranaA> ... poslodavac ukupni iznosi ...
        <StranaB> ... po radniku ...
    """
    company = payroll_run.company
    slips = payroll_run.payslips.select_related('user').all()
    oib = getattr(company, 'oib', '') or ''

    # Root element
    root = Element('JOPPD')
    root.set('xmlns', 'http://e-porezna.porezna-uprava.hr/sheme/zahtjevi/JOPPD/v2')
    root.set('verzijaSheme', '2.0')

    # ── Zaglavlje ──
    zaglavlje = SubElement(root, 'Zaglavlje')
    SubElement(zaglavlje, 'DatumIzvjesca').text = date.today().isoformat()
    SubElement(zaglavlje, 'OznakaIzvjesca').text = f'{payroll_run.year}{payroll_run.month:02d}1'
    SubElement(zaglavlje, 'VrstaIzvjesca').text = '1'  # 1 = novo, 2 = ispravak
    SubElement(zaglavlje, 'OIBPodnositelja').text = oib
    SubElement(zaglavlje, 'NazivPodnositelja').text = company.name
    SubElement(zaglavlje, 'OznakaObrasca').text = 'JOPPD'

    # ── Strana A (ukupno) ──
    strana_a = SubElement(root, 'StranaA')
    SubElement(strana_a, 'BrojOsiguranika').text = str(slips.count())
    SubElement(strana_a, 'BrojRedova').text = str(slips.count())

    from django.db.models import Sum
    totals = slips.aggregate(
        gross=Sum('gross_amount'),
        mio=Sum('contributions_amount'),
        tax=Sum('tax_amount'),
        net=Sum('net_amount'),
    )

    total_gross = totals['gross'] or Decimal('0')
    total_mio = totals['mio'] or Decimal('0')
    total_tax = totals['tax'] or Decimal('0')
    total_net = totals['net'] or Decimal('0')
    total_zdravstveno = (total_gross * HEALTH_RATE).quantize(Decimal('0.01'))

    SubElement(strana_a, 'P1').text = f'{total_gross:.2f}'  # Ukupni primitak
    SubElement(strana_a, 'P2').text = f'{total_mio:.2f}'     # Ukupni MIO
    SubElement(strana_a, 'P3').text = f'{total_tax:.2f}'     # Ukupni porez+prirez
    SubElement(strana_a, 'P4').text = f'{total_zdravstveno:.2f}'  # Zdravstveno NA
    SubElement(strana_a, 'P5').text = f'{total_net:.2f}'     # Ukupni neto

    # ── Strana B (po radniku) ──
    strana_b = SubElement(root, 'StranaB')
    for i, slip in enumerate(slips, 1):
        red = SubElement(strana_b, 'R')
        user = slip.user
        user_oib = ''
        try:
            profile = user.profile
            user_oib = getattr(profile, 'oib', '') or ''
        except (AttributeError, TypeError):
            pass

        SubElement(red, 'RedniBroj').text = str(i)
        SubElement(red, 'OIBStjecatelja').text = user_oib
        SubElement(red, 'NazivStjecatelja').text = user.get_full_name() or user.username
        SubElement(red, 'OznakaStjecatelja').text = '0001'  # Radnik u radnom odnosu
        SubElement(red, 'OznakaPrimitka').text = '0001'     # Plaća
        SubElement(red, 'OznakaNačinaIsplate').text = '1'    # 1=žiro, 2=gotovina

        # Razdoblje
        SubElement(red, 'OdMjesec').text = f'{payroll_run.year}-{payroll_run.month:02d}'
        SubElement(red, 'DoMjesec').text = f'{payroll_run.year}-{payroll_run.month:02d}'
        SubElement(red, 'SatiRada').text = f'{slip.total_hours:.2f}'

        # Iznosi
        SubElement(red, 'Primitak').text = f'{slip.gross_amount:.2f}'
        SubElement(red, 'DoprinosiIz').text = f'{slip.contributions_amount:.2f}'
        SubElement(red, 'Dohodak').text = f'{(slip.gross_amount - slip.contributions_amount):.2f}'
        SubElement(red, 'OsobniOdbitak').text = f'{PERSONAL_DEDUCTION:.2f}'
        SubElement(red, 'PoreznaOsnovica').text = f'{slip.tax_base:.2f}'
        SubElement(red, 'Porez').text = f'{slip.tax_amount:.2f}'
        SubElement(red, 'Neto').text = f'{slip.net_amount:.2f}'

        # Doprinosi NA plaću
        zdrav = (slip.gross_amount * HEALTH_RATE).quantize(Decimal('0.01'))
        SubElement(red, 'DoprinosiNa').text = f'{zdrav:.2f}'

    return tostring(root, encoding='unicode', xml_declaration=True)


def generate_ip1(payslip):
    """
    Generira IP1 potvrdu za radnika (za banku, vizu, itd.).
    Returns dict za template rendering.
    """
    company = payslip.payroll_run.company
    calc = calculate_hr_payslip(payslip.gross_amount)

    return {
        'company_name': company.name,
        'company_oib': getattr(company, 'oib', ''),
        'company_address': getattr(company, 'address', ''),
        'employee_name': payslip.employee_name,
        'period': payslip.payroll_run.period_label,
        'year': payslip.payroll_run.year,
        'month': payslip.payroll_run.month,
        'gross': payslip.gross_amount,
        'mio_i': calc['mio_i'],
        'mio_ii': calc['mio_ii'],
        'dohodak': calc['dohodak'],
        'osobni_odbitak': calc['osobni_odbitak'],
        'porezna_osnovica': calc['porezna_osnovica'],
        'porez': calc['porez'],
        'prirez': calc['prirez'],
        'neto': payslip.net_amount,
        'total_hours': payslip.total_hours,
        'regular_hours': payslip.regular_hours,
        'overtime_hours': payslip.overtime_hours,
    }
