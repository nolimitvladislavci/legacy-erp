"""
rental/hub3a.py — HUB-3A barcode generator za uplatnice

HUB-3A = Hrvatski standard za 2D barkod na uplatnicama.
Format: PDF417, fiksna struktura 15 polja razdvojenih LF (\n).

Banka čita barkod → sva polja se auto-popune → klijent samo potvrdi.

Spec: HUB-3A v1.03 (HUBCG, 2015)
"""
import io
import base64
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)

# HUB-3A header (obavezan)
HUB3A_HEADER = 'HRVHUB30'
HUB3A_CURRENCY = 'EUR'
HUB3A_PAY_CODE = 'OTHR'  # Ostala plaćanja


def build_hub3a_string(
    amount: Decimal,
    sender_name: str,
    sender_address: str,
    sender_city: str,
    receiver_name: str,
    receiver_address: str,
    receiver_city: str,
    receiver_iban: str,
    model: str,
    reference: str,
    purpose: str,
    description: str,
) -> str:
    """
    Gradi HUB-3A string za PDF417 barkod.

    Format: 15 redova, svaki max duljine, razdvojeni \\n.
    Iznos: 15 znakova, desno poravnato, bez decimalne točke (centi).
    """
    # Iznos: 123.45 → "000000000012345"
    cents = int(amount * 100)
    amount_str = str(cents).zfill(15)

    lines = [
        HUB3A_HEADER,                          # 1. Header
        HUB3A_CURRENCY,                         # 2. Valuta
        amount_str,                             # 3. Iznos (centi, 15 znakova)
        _trunc(sender_name, 30),                # 4. Platitelj ime
        _trunc(sender_address, 27),             # 5. Platitelj adresa
        _trunc(sender_city, 27),                # 6. Platitelj mjesto
        _trunc(receiver_name, 25),              # 7. Primatelj ime
        _trunc(receiver_address, 25),           # 8. Primatelj adresa
        _trunc(receiver_city, 27),              # 9. Primatelj mjesto
        receiver_iban.replace(' ', ''),          # 10. IBAN primatelja
        model.replace(' ', ''),                 # 11. Model plaćanja
        _trunc(reference.replace(' ', ''), 22), # 12. Poziv na broj
        HUB3A_PAY_CODE,                         # 13. Šifra namjene
        _trunc(description, 35),                # 14. Opis plaćanja
    ]

    return '\n'.join(lines)


def generate_hub3a_image(hub3a_string: str, scale: int = 3) -> bytes:
    """
    Generira PDF417 barkod sliku iz HUB-3A stringa.

    Returns: PNG bytes
    """
    from pdf417gen import encode, render_image

    codes = encode(hub3a_string, columns=8)
    img = render_image(codes, scale=scale, ratio=3, padding=5)

    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return buffer.read()


def generate_hub3a_base64(hub3a_string: str, scale: int = 3) -> str:
    """Base64 PNG za embedding u HTML/PDF."""
    png = generate_hub3a_image(hub3a_string, scale)
    return base64.b64encode(png).decode('ascii')


def build_tz_membership_hub3a(data: dict) -> dict:
    """
    Gradi HUB-3A za uplatu TZ članarine.

    Args:
        data: dict iz generate_tz2_data() 

    Returns: {
        'hub3a_string': str,
        'hub3a_base64': str (PNG),
        'iban': str,
        'model': str,
        'reference': str,
        'amount': Decimal,
        'rates': [{'r': 1, 'amount': ..., 'hub3a_base64': ...}, ...]
    }
    """
    profile = data['profile']
    company = data['company']
    year = data['year']

    # IBAN turističke zajednice — iz company.settings ili profila
    settings = getattr(company, 'settings', None) or {}
    tz_iban = settings.get('tz_iban', '')
    tz_name = profile.tz_name or 'Turistička zajednica'

    if not tz_iban:
        logger.warning('TZ IBAN nije konfiguriran za %s', company.name)
        return {'error': 'TZ IBAN nije konfiguriran u postavkama firme.'}

    # Model i poziv na broj
    model = 'HR68'
    oib = company.oib or ''
    reference = f'5327-{oib}-{year}'

    sender_name = profile.full_name
    sender_address = company.address or ''
    sender_city = f'{company.zip_code} {company.city}'.strip()

    # Parsaj TZ adresu iz settings ili fallback
    tz_address = settings.get('tz_address', '')
    tz_city = settings.get('tz_city', '')

    # Generiraj za ukupan iznos
    total_string = build_hub3a_string(
        amount=data['tz_fee_total'],
        sender_name=sender_name,
        sender_address=sender_address,
        sender_city=sender_city,
        receiver_name=_trunc(tz_name, 25),
        receiver_address=tz_address,
        receiver_city=tz_city,
        receiver_iban=tz_iban,
        model=model,
        reference=reference,
        purpose='OTHR',
        description=f'TZ clanarina {year}',
    )

    # Generiraj za svaku ratu
    rates_with_barcode = []
    for rate in data['tz_rates']:
        rate_ref = f'5327-{oib}-{year}-R{rate["r"]}'
        rate_string = build_hub3a_string(
            amount=rate['amount'],
            sender_name=sender_name,
            sender_address=sender_address,
            sender_city=sender_city,
            receiver_name=_trunc(tz_name, 25),
            receiver_address=tz_address,
            receiver_city=tz_city,
            receiver_iban=tz_iban,
            model=model,
            reference=rate_ref,
            purpose='OTHR',
            description=f'TZ clanarina {year} rata {rate["r"]}',
        )
        rates_with_barcode.append({
            **rate,
            'hub3a_base64': generate_hub3a_base64(rate_string),
            'reference': rate_ref,
        })

    return {
        'hub3a_string': total_string,
        'hub3a_base64': generate_hub3a_base64(total_string),
        'iban': tz_iban,
        'model': model,
        'reference': reference,
        'amount': data['tz_fee_total'],
        'rates': rates_with_barcode,
    }


def _trunc(s: str, maxlen: int) -> str:
    """Skrati string na maxlen, zamijeni HR dijakritike za barkod safety."""
    if not s:
        return ''
    # HUB-3A dopušta UTF-8, ali neke banke imaju probleme
    # Za sigurnost ostavimo originalne znakove
    return s[:maxlen]
