"""
rental/tz2_service.py — TZ-2 Obrazac generacija

Obrazac TZ-2 = Prijava kapaciteta turističkoj zajednici.
Rok predaje: 15. siječnja za tekuću godinu.

Podaci se povlače iz:
  - LandlordProfile (osobni + porezni podaci)
  - Property (objekt, kategorija, razred)
  - AccommodationUnit (stalni + pomoćni kreveti po jedinici)

Output: PDF spreman za potpis i predaju.
"""
import logging
from datetime import date
from decimal import Decimal
from io import BytesIO

from django.template.loader import render_to_string
from django.utils import timezone

logger = logging.getLogger(__name__)


def generate_tz2_data(company, year=None):
    """
    Prikupi sve podatke za TZ-2 obrazac.

    Returns dict s svim podacima ili raises ValueError ako fali nešto.
    """
    from rental.models import Property, LandlordProfile

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

    for prop in properties:
        units = prop.units.filter(is_active=True)
        prop_permanent = sum(u.permanent_beds for u in units)
        prop_auxiliary = sum(u.auxiliary_beds for u in units)

        # Fallback: ako nema jedinica, koristi Property.capacity
        if not units.exists():
            prop_permanent = prop.capacity or 0
            prop_auxiliary = 0

        total_permanent += prop_permanent
        total_auxiliary += prop_auxiliary

        # Provjera kategorizacije
        expired_units = [u for u in units if u.categorization_expired]

        property_data.append({
            'property': prop,
            'units': list(units),
            'permanent_beds': prop_permanent,
            'auxiliary_beds': prop_auxiliary,
            'total_beds': prop_permanent + prop_auxiliary,
            'expired_units': expired_units,
            'razred': prop.razred_mjesta or 'A',
        })

    # Paušalni porez izračun
    settings = getattr(company, 'settings', None) or {}
    pausal_per_permanent = Decimal(str(settings.get('pausal_per_permanent_bed', '331.81')))
    pausal_per_auxiliary = Decimal(str(settings.get('pausal_per_auxiliary_bed', '265.45')))

    annual_tax_permanent = pausal_per_permanent * total_permanent
    annual_tax_auxiliary = pausal_per_auxiliary * total_auxiliary
    annual_tax_total = annual_tax_permanent + annual_tax_auxiliary

    # Prirez (iz company settings ili default 10%)
    prirez_rate = Decimal(str(settings.get('prirez_rate', '0.10')))
    prirez_amount = (annual_tax_total * prirez_rate).quantize(Decimal('0.01'))
    total_with_prirez = annual_tax_total + prirez_amount

    # Tromjesečne rate
    quarterly = (total_with_prirez / 4).quantize(Decimal('0.01'))
    last_quarter = total_with_prirez - quarterly * 3  # ostatak u Q4

    return {
        'year': year,
        'generated_at': timezone.now(),
        'deadline': date(year, 1, 15),

        # Iznajmljivač
        'profile': profile,
        'company': company,

        # Objekti
        'properties': property_data,
        'total_permanent': total_permanent,
        'total_auxiliary': total_auxiliary,
        'total_beds': total_permanent + total_auxiliary,

        # Porezni izračun
        'pausal_per_permanent': pausal_per_permanent,
        'pausal_per_auxiliary': pausal_per_auxiliary,
        'annual_tax_permanent': annual_tax_permanent,
        'annual_tax_auxiliary': annual_tax_auxiliary,
        'annual_tax_total': annual_tax_total,
        'prirez_rate': prirez_rate,
        'prirez_rate_pct': int(prirez_rate * 100),
        'prirez_amount': prirez_amount,
        'total_with_prirez': total_with_prirez,

        # Tromjesečne rate
        'quarterly_amount': quarterly,
        'quarterly_last': last_quarter,
        'quarterly_deadlines': [
            {'q': 1, 'amount': quarterly, 'deadline': date(year, 1, 31)},
            {'q': 2, 'amount': quarterly, 'deadline': date(year, 4, 30)},
            {'q': 3, 'amount': quarterly, 'deadline': date(year, 7, 31)},
            {'q': 4, 'amount': last_quarter, 'deadline': date(year, 10, 31)},
        ],
    }


def generate_tz2_pdf(company, year=None):
    """
    Generira TZ-2 PDF obrazac.
    Returns: bytes (PDF content)
    """
    data = generate_tz2_data(company, year)

    html = render_to_string('rental/tz2_form.html', data)

    from xhtml2pdf import pisa
    buffer = BytesIO()
    pisa_status = pisa.CreatePDF(html, dest=buffer, encoding='utf-8')

    if pisa_status.err:
        raise RuntimeError(f'PDF generation error: {pisa_status.err}')

    buffer.seek(0)
    return buffer.read()
