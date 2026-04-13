"""
invoicing/services/fiscalize.py
Fiskalizacija logika — izvucena iz views.py.
Nema request objekt, nema messages, nema redirect.
"""
import hashlib
import logging
import os

from django.utils import timezone

logger = logging.getLogger(__name__)


def generate_qr(invoice):
    """Generate QR code base64 for fiscal invoice."""
    try:
        import base64
        from io import BytesIO

        import qrcode
        url = f"https://porezna.gov.hr/rn?jir={invoice.jir}&datv={invoice.fiscal_datetime}&izn={invoice.total}"
        qr = qrcode.make(url)
        buf = BytesIO()
        qr.save(buf, format='PNG')
        return base64.b64encode(buf.getvalue()).decode()
    except ImportError:
        return ''


def generate_zki(invoice, cert_key='demo_key'):
    """Generate ZKI (Zastitni Kod Izdavatelja)."""
    raw = f"{invoice.issuer_oib}{invoice.date_issued}{invoice.number}{invoice.total}"
    return hashlib.md5(raw.encode()).hexdigest()


def _get_cert_config(company=None):
    """Get fiscal certificate config for company."""
    from fiskalizacija.models import FiscalConfig

    if company:
        config = FiscalConfig.objects.filter(company=company).first()
    else:
        config = FiscalConfig.objects.filter(is_active=True).first()

    if not config:
        raise ValueError("Nema aktivne FiscalConfig konfiguracije")

    # Resolve cert path
    cert_path = None
    if hasattr(config, 'cert_file') and config.cert_file:
        cert_path = config.cert_file.path
    elif hasattr(config, 'cert_filename') and config.cert_filename:
        cert_path = f"/var/www/fina-connect/certs/{config.cert_filename}"

    # Resolve password
    cert_password = None
    if hasattr(config, '_cert_password') and config._cert_password:
        cert_password = bytes(config._cert_password).decode('utf-8')
    elif hasattr(config, 'cert_password') and config.cert_password:
        cert_password = config.cert_password

    if not cert_password:
        pw_file = '/var/www/fina-connect/certs/.cert_password'
        if os.path.exists(pw_file):
            with open(pw_file) as f:
                cert_password = f.read().strip()

    return {
        'cert_path': cert_path,
        'cert_password': cert_password,
        'is_demo': config.is_demo,
        'is_production': not config.is_demo,
        'config': config,
    }


def fiscalize_invoice(invoice, user=None, ip_address=None):
    """
    Fiskaliziraj racun. Vraca dict s rezultatom.

    Args:
        invoice: Invoice instance
        user: User koji fiskalizira (za audit)
        ip_address: IP adresa (za audit)

    Returns:
        dict: {success: bool, zki: str, jir: str, error: str, demo: bool}
    """
    # Validacije
    if not getattr(invoice, 'is_hr', True):
        return {'success': False, 'error': 'Fiskalizacija dostupna samo za HR racune'}

    if invoice.is_fiscalized:
        return {'success': False, 'error': 'Racun je vec fiskaliziran',
                'zki': invoice.zki, 'jir': invoice.jir}

    if invoice.doctype != 'R':
        return {'success': False, 'error': 'Samo racuni (R) se mogu fiskalizirati'}

    try:
        cert = _get_cert_config(invoice.company)
    except ValueError as e:
        return {'success': False, 'error': str(e)}

    try:
        from fiscal.service import fiscalize_invoice as _fiscal_call

        result = _fiscal_call(
            invoice,
            cert_path=cert['cert_path'],
            cert_password=cert['cert_password'],
            production=cert['is_production'],
        )

        if result.get('success'):
            # Update invoice
            invoice.zki = result.get('zki', '')
            invoice.jir = result.get('jir', '')
            invoice.is_fiscalized = True
            invoice.fiscal_datetime = timezone.now()
            invoice.operator_oib = (
                invoice.operator.oib if hasattr(invoice, 'operator') and invoice.operator else ''
            )
            if not invoice.qr_code_base64:
                invoice.qr_code_base64 = generate_qr(invoice)

            # Lock (ZOR cl.9) + 11 year retention (ZOR cl.10)
            lock_invoice(invoice)

            invoice.save(update_fields=[
                'zki', 'jir', 'is_fiscalized', 'fiscal_datetime',
                'operator_oib', 'qr_code_base64', 'is_locked', 'deletion_protected_until',
            ])

            # Audit event
            log_invoice_event(
                invoice,
                event_type='fiscalized',
                title=f'Fiskalizirano — JIR: {invoice.jir}',
                detail=f'ZKI: {invoice.zki} | JIR: {invoice.jir} | Op OIB: {invoice.operator_oib}',
                metadata={'zki': invoice.zki, 'jir': invoice.jir, 'demo': cert['is_demo']},
                actor=user,
                ip_address=ip_address,
            )

            return {
                'success': True,
                'zki': invoice.zki,
                'jir': invoice.jir,
                'demo': cert['is_demo'],
            }
        else:
            return {'success': False, 'error': result.get('error', 'Unknown fiscal error')}

    except Exception as e:
        logger.exception("Fiscalization error")
        return {'success': False, 'error': str(e)}


def lock_invoice(invoice):
    """Lock invoice and set 11-year retention per ZOR cl.9 & cl.10."""
    invoice.is_locked = True
    if not invoice.deletion_protected_until and invoice.date_issued:
        try:
            issued = invoice.date_issued
            if hasattr(issued, 'date'):
                issued = issued.date()
            invoice.deletion_protected_until = issued.replace(year=issued.year + 11)
        except AttributeError:
            pass
