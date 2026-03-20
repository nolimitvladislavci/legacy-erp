"""
Potvrda o primljenoj donaciji — zakonski dokument za poreznu olakšicu donatora.

Čl. 11 Zakona o porezu na dobit: donator ima pravo na poreznu olakšicu do 2% prihoda.
Za to mu treba OVA potvrda, ne obični račun.

Generira se automatski kad donacija dobije status PAID.
PDF sadrži: OIB udruge, izjava o neprofitnom statusu, svrha, potpis.
"""
import io
import logging
from datetime import date
from decimal import Decimal

from django.template.loader import render_to_string
from django.utils import timezone as tz

logger = logging.getLogger('donations')


def generate_donation_certificate(company, donor_name, donor_oib, amount, purpose,
                                  donation_date=None, certificate_number=None):
    """
    Generira PDF potvrdu o primljenoj donaciji.

    Args:
        company: Company (udruga koja prima donaciju)
        donor_name: str (ime tvrtke/osobe koja donira)
        donor_oib: str (OIB donatora)
        amount: Decimal
        purpose: str (svrha donacije)
        donation_date: date (default: danas)
        certificate_number: str (default: auto-generirano)

    Returns:
        bytes (PDF content)
    """
    if not donation_date:
        donation_date = date.today()
    if not certificate_number:
        certificate_number = 'DON-%d-%04d' % (
            donation_date.year,
            _next_certificate_number(company, donation_date.year)
        )

    context = {
        'company': company,
        'donor_name': donor_name,
        'donor_oib': donor_oib,
        'amount': amount,
        'amount_text': _amount_to_text(amount),
        'purpose': purpose,
        'donation_date': donation_date,
        'certificate_number': certificate_number,
        'generated_at': tz.now(),
        'legal_text_hr': (
            'Sukladno čl. 11. st. 2. Zakona o porezu na dobit (NN 177/04, 90/05, 57/06, '
            '146/08, 80/10, 22/12, 148/13, 143/14, 50/16, 115/16, 106/18, 121/19, 32/20, '
            '138/20, 114/22, 114/23), potvrđujemo primitak donacije u navedenom iznosu.'
        ),
        'legal_text_de': (
            'Gemäß § 9 Abs. 1 Nr. 2 KStG bestätigen wir den Erhalt der oben genannten Spende.'
        ),
        'nonprofit_statement_hr': (
            'Izjavljujemo da %s (OIB: %s) djeluje kao neprofitna organizacija '
            'te da će primljena sredstva biti korištena isključivo za neprofitne svrhe.' % (
                company.name, company.oib
            )
        ),
        'electronic_notice': (
            'Ova potvrda je izrađena elektronički i važeća je bez žiga i potpisa '
            '(čl. 9. st. 2. ZOR-a). / Dieser Nachweis wurde elektronisch erstellt '
            'und ist ohne Stempel und Unterschrift gültig.'
        ),
    }

    html = render_to_string('documents/donation_certificate_pdf.html', context)

    try:
        from xhtml2pdf import pisa
        buf = io.BytesIO()
        pisa.CreatePDF(html, dest=buf)
        buf.seek(0)
        return buf.read()
    except ImportError:
        return html.encode('utf-8')


def _next_certificate_number(company, year):
    """Sljedeći broj potvrde za godinu."""
    from documents.models import ArhivaEntry
    count = ArhivaEntry.objects.filter(
        company=company,
        source_type='donation',
        doc_date__year=year,
    ).count()
    return count + 1


def _amount_to_text(amount):
    """Pretvori iznos u tekst (pojednostavljeno)."""
    amt = Decimal(str(amount))
    eur = int(amt)
    cents = int((amt - eur) * 100)
    return '%d EUR i %02d centi' % (eur, cents)
