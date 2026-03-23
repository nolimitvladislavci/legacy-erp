"""
Fiskalizacija async tasks — supplier risk checks.
"""
import logging
from celery import shared_task

logger = logging.getLogger('fiskalizacija.tasks')


@shared_task(name='fiskalizacija.check_supplier_risk', bind=True, max_retries=2, default_retry_delay=60)
def check_supplier_risk_async(self, supplier_oib, company_id):
    """
    Async provjera boniteta dobavljača.
    Triggerano iz invoicing.signals kad se kreira ulazna faktura.
    """
    try:
        from fiskalizacija.fina_bonitet_service import get_supplier_risk
        result = get_supplier_risk(supplier_oib, company_id=company_id)
        logger.info(
            'Supplier risk check: OIB=%s company=%s → %s',
            supplier_oib, company_id, result.get('risk_level', 'UNKNOWN'),
        )
        return result
    except Exception as exc:
        logger.warning('Supplier risk check failed: OIB=%s err=%s', supplier_oib, exc)
        raise self.retry(exc=exc)
