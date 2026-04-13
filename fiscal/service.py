import logging
from .models import FiscalConfiguration, FiscalLog, FiscalProvider
from .providers.hr_fina import HRFinaProvider
from .providers.de_tse import DETseProvider
from .providers.at_rksv import ATRksvProvider
from django.db import IntegrityError, DatabaseError

logger = logging.getLogger(__name__)


def get_provider(company, branch=None):
    config = FiscalConfiguration.objects.filter(
        company=company, branch=branch, is_active=True
    ).first()
    if not config or config.provider == FiscalProvider.NONE:
        return None
    providers = {
        FiscalProvider.HR_FINA: HRFinaProvider,
        FiscalProvider.DE_TSE: DETseProvider,
        FiscalProvider.AT_RKSV: ATRksvProvider,
    }
    provider_class = providers.get(config.provider)
    return provider_class(config) if provider_class else None


def fiscalize_receipt(receipt_data, company, branch=None):
    provider = get_provider(company, branch)
    if not provider:
        return None
    result = provider.fiscalize(receipt_data)
    try:
        FiscalLog.objects.create(
            config=provider.config,
            receipt_type=receipt_data.get('receipt_type', 'unknown'),
            receipt_id=receipt_data.get('receipt_id', 0),
            status='success' if result.success else 'error',
            zki=result.zki, jir=result.jir,
            tse_signature=result.tse_signature,
            tse_transaction_number=result.tse_transaction_number,
            request_xml=result.raw_request,
            response_xml=result.raw_response,
            error_message=result.error_message,
            qr_code_data=result.qr_code_data,
        )
    except (IntegrityError, DatabaseError) as e:
        logger.error(f"FiscalLog creation failed: {e}")
    return result


def fiscalize_pos_receipt(receipt):
    """Convenience wrapper for POS receipts.

    Delegates to fiskalizacija.fisk (proven WS-Security SOAP) for HR,
    logs in FiscalLog, and returns JIR string or None.

    Usage in pos/views.py:
        from fiscal.service import fiscalize_pos_receipt
        jir = fiscalize_pos_receipt(receipt)
    """
    from .models import FiscalLog

    # IDEMPOTENCY GUARD — ne salji isti racun dvaput FINA-i
    from .models import FiscalLog
    existing = FiscalLog.objects.filter(
        receipt_type='pos_receipt', receipt_id=receipt.pk, status='success'
    ).first()
    if existing:
        import logging as _log
        _log.getLogger(__name__).warning(
            "Receipt %d already fiscalized — returning existing JIR", receipt.pk
        )
        return existing.jir or None

    # Use existing fiskalizacija.fisk engine (proper WS-Security)
    try:
        from fiskalizacija.fisk import fiscalize_receipt as fisk_fiscalize
        jir = fisk_fiscalize(receipt)
    except ImportError:
        logger.error("fiskalizacija.fisk not available")
        return None
    except Exception as e:
        # Log the failure
        _log_pos_fiscal(receipt, success=False, error=str(e))
        raise

    # Log success
    if jir:
        _log_pos_fiscal(receipt, success=True, jir=jir)
        # BORG Audit Entry — fiskalizacija uspjesna
        try:
            from borg_ops.audit_helpers import log_borg_audit
            company = receipt.session.terminal.company
            log_borg_audit(
                company=company,
                entry_type='FISCAL',
                summary=f'Fiskalizacija POS racuna #{receipt.receipt_number} — JIR: {jir}',
                document=receipt,
                verification_type='CIS',
                verification_result={'jir': jir, 'zki': getattr(receipt, 'zki', '')},
            )
        except Exception:
            pass  # Audit ne smije srusiti fiskalizaciju

    return jir


def _log_pos_fiscal(receipt, success=True, jir='', error=''):
    """Log POS fiscalization to FiscalLog."""
    from .models import FiscalLog, FiscalConfiguration
    try:
        company = receipt.session.terminal.company
        config = FiscalConfiguration.objects.filter(
            company=company, is_active=True
        ).first()
        if not config:
            return
        FiscalLog.objects.create(
            config=config,
            receipt_type='pos_receipt',
            receipt_id=receipt.pk,
            status='success' if success else 'error',
            zki=getattr(receipt, 'zki', '') or '',
            jir=jir,
            error_message=error,
        )
    except (IntegrityError, DatabaseError) as e:
        logger.debug("POS fiscal log skipped: %s", e)


def fiscalize_invoice(invoice, cert_path=None, cert_password=None, production=False):
    """Wrapper for invoice fiscalization via existing invoicing.fiscalization.

    Delegates to the proven invoicing.fiscalization.send_to_cis() engine,
    and logs the result to FiscalLog for centralised tracking.

    Returns the same dict as send_to_cis: {'success': bool, 'jir': str, 'zki': str, ...}
    """
    from .models import FiscalLog, FiscalConfiguration

    try:
        from invoicing.fiscalization import send_to_cis
        result = send_to_cis(invoice, cert_path=cert_path,
                             cert_password=cert_password, production=production)
    except Exception as e:
        logger.error("Invoice fiscalization error: %s", e)
        result = {'success': False, 'error': str(e)}

    # Log to FiscalLog
    try:
        company = getattr(invoice, 'company', None)
        config = None
        if company:
            config = FiscalConfiguration.objects.filter(
                company=company, is_active=True
            ).first()
        if config:
            FiscalLog.objects.create(
                config=config,
                receipt_type='invoice',
                receipt_id=invoice.pk,
                status='success' if result.get('success') else 'error',
                zki=result.get('zki', ''),
                jir=result.get('jir', ''),
                request_xml='',
                response_xml='',
                error_message=result.get('error', ''),
            )
    except (IntegrityError, DatabaseError) as e:
        logger.debug("Invoice fiscal log skipped: %s", e)

    return result
