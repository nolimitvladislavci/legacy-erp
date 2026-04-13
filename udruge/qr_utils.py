import logging
"""
Udruge QR kod i Viral code generatori.
QR za clanske iskaznice, donatorske potvrde, event ulaznice.
Viral code za referral link.
"""
import base64, hashlib, logging
from io import BytesIO

logger = logging.getLogger('udruge')


def generate_qr_base64(data, box_size=4, border=1):
    """Generira QR kod kao base64 PNG string."""
    try:
        import qrcode
        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M,
                            box_size=box_size, border=border)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color='black', back_color='white')
        buf = BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return base64.b64encode(buf.read()).decode()
    except IOError as e:
        logger.error('QR generiranje: %s', e)
        return None


def generate_membership_qr(clan, base_url='https://limit-connect.com'):
    """QR za clansku iskaznicu."""
    return generate_qr_base64('%s/udruge/verify/%s/%s/' % (
        base_url.rstrip('/'), clan.company_id, clan.pk))


def generate_donation_qr(donacija, base_url='https://limit-connect.com'):
    """QR za donatorsku potvrdu."""
    return generate_qr_base64('%s/udruge/donacije/%s/verify/' % (
        base_url.rstrip('/'), donacija.pk))


def generate_event_qr(dogadjaj, clan=None, base_url='https://limit-connect.com'):
    """QR za event ulaznicu."""
    if clan:
        return generate_qr_base64('%s/udruge/dogadjaji/%s/checkin/%s/' % (
            base_url.rstrip('/'), dogadjaj.pk, clan.pk))
    return generate_qr_base64('%s/udruge/dogadjaji/%s/' % (base_url.rstrip('/'), dogadjaj.pk))


def generate_viral_code(company_id, entity_id):
    """Viral/referral code. Format: LC-{hash6}-{id}"""
    import os
    secret = os.environ.get('VIRAL_CODE_SECRET', 'limit-connect-viral-2026')
    raw = '%s:%s:%s' % (company_id, entity_id, secret)
    h = hashlib.sha256(raw.encode()).hexdigest()[:6].upper()
    return 'LC-%s-%s' % (h, entity_id)


def verify_viral_code(code):
    """Verificira viral code, vraca entity_id ili None."""
    if not code or not code.startswith('LC-'):
        return None
    parts = code.split('-')
    if len(parts) != 3:
        return None
    try:
        return int(parts[2])
    except ValueError:
        return None


def generate_payment_qr(company, amount, purpose='Clanarina', reference=''):
    """HUB-3 barcode QR za uplatnicu (HR specifikacija)."""
    try:
        lines = ['HRVHUB30', 'EUR', '%.2f' % float(amount), '', '', '',
                 company.name[:30],
                 getattr(company, 'address', '')[:27],
                 '%s %s' % (getattr(company, 'zip_code', ''), getattr(company, 'city', '')),
                 getattr(company, 'iban', ''), 'HR00', reference or 'HR99', 'OTHR', purpose[:35]]
        return generate_qr_base64('\n'.join(lines), box_size=3)
    except (ValueError, TypeError) as e:
        logger.error('HUB-3 QR: %s', e)
        return None
