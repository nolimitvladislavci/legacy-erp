"""
POS Utility functions — QR kodovi, formatiranje, pomoćne funkcije.
"""
import base64
import logging
from io import BytesIO

logger = logging.getLogger('pos')


def generate_fina_qr_base64(zki, receipt_date, total_amount):
    """
    Generira zakonski propisani QR kod za FINA fiskalizaciju.
    HR Zakon o fiskalizaciji — QR kod obavezan na svakom računu.

    Format: https://porezna.gov.hr/rn?z=ZKI&d=YYYYMMDD_HHMM&i=IZNOS

    Args:
        zki: Zaštitni kod izdavatelja (32 hex znaka)
        receipt_date: datetime objekt (vrijeme računa)
        total_amount: Decimal (ukupni iznos s PDV-om)

    Returns:
        base64 PNG string ili None ako nema ZKI
    """
    if not zki:
        return None

    try:
        import qrcode

        # Format datuma: YYYYMMDD_HHMM
        if hasattr(receipt_date, 'astimezone'):
            formatted_date = receipt_date.astimezone().strftime('%Y%m%d_%H%M')
        else:
            formatted_date = receipt_date.strftime('%Y%m%d_%H%M')

        # Iznos: uvijek 2 decimale, točka kao separator
        formatted_amount = '%.2f' % float(total_amount)

        # URL po FINA specifikaciji
        qr_data = 'https://porezna.gov.hr/rn?z=%s&d=%s&i=%s' % (
            zki, formatted_date, formatted_amount
        )

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=4,
            border=1,
        )
        qr.add_data(qr_data)
        qr.make(fit=True)

        img = qr.make_image(fill_color='black', back_color='white')
        buf = BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return base64.b64encode(buf.read()).decode()

    except (ValueError, TypeError) as e:
        logger.error('FINA QR generiranje neuspješno: %s', e)
        return None


def generate_receipt_qr_base64(receipt):
    """
    Wrapper — generira QR iz POSReceipt objekta.
    Koristi ZKI, fiscal_datetime i total.
    """
    if not receipt.zki:
        return None
    date = receipt.fiscal_datetime or receipt.paid_at
    if not date:
        return None
    return generate_fina_qr_base64(receipt.zki, date, receipt.total)
