"""
POS Utility functions — QR kodovi, formatiranje, pomoćne funkcije.
"""

import base64
import logging

logger = logging.getLogger("pos")


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
        from core.qr_views import qr_png_bytes

        # Format datuma: YYYYMMDD_HHMM
        if hasattr(receipt_date, "astimezone"):
            formatted_date = receipt_date.astimezone().strftime("%Y%m%d_%H%M")
        else:
            formatted_date = receipt_date.strftime("%Y%m%d_%H%M")

        # Iznos: uvijek 2 decimale, točka kao separator
        formatted_amount = "%.2f" % float(total_amount)

        # URL po FINA specifikaciji (ERROR_CORRECT_H per FINA standard)
        qr_data = "https://porezna.gov.hr/rn?z=%s&d=%s&i=%s" % (zki, formatted_date, formatted_amount)
        return base64.b64encode(qr_png_bytes(qr_data, size=100, error_correction="H")).decode()

    except (ValueError, TypeError) as e:
        logger.error("FINA QR generiranje neuspješno: %s", e)
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
