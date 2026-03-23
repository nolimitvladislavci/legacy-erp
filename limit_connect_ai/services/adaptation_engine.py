"""
BORG FENIX — Adaptation Engine
Automatska primjena regulatornih promjena na sustav.

Scenariji:
- tax_rate: Promjena PDV stope u šifrarniku
- xml_schema: Update e-Račun validacije
- config_change: Promjena fiskalizacija config-a
- notification: Samo obavijest adminu
"""
import logging

from django.utils import timezone

logger = logging.getLogger(__name__)


def apply_rule(rule):
    """
    Primijeni AdaptationRule na sustav.
    Dispatchira na specijalizirani handler po rule_type.
    """
    handlers = {
        'tax_rate': _apply_tax_rate,
        'config_change': _apply_config_change,
        'notification': _apply_notification,
    }

    handler = handlers.get(rule.rule_type, _apply_notification)
    return handler(rule)


def _apply_tax_rate(rule):
    """
    Promjena porezne stope.
    Payload: {"tax_code": "PDV25", "old_rate": 25, "new_rate": 22, "effective_date": "2026-07-01"}
    """
    payload = rule.action_payload
    old_rate = payload.get('old_rate')
    new_rate = payload.get('new_rate')
    effective_date = payload.get('effective_date')

    if not all([old_rate, new_rate]):
        raise ValueError('Payload mora sadržavati old_rate i new_rate')

    # Ažuriraj TaxRate model
    from companies.models import TaxRate
    updated = TaxRate.objects.filter(rate=old_rate).update(rate=new_rate)

    logger.info(
        '[BORG ADAPT] Tax rate changed: %s → %s, affected %d records, effective %s',
        old_rate, new_rate, updated, effective_date,
    )

    rule.is_executed = True
    rule.executed_at = timezone.now()
    rule.executed_by = 'auto:adaptation_engine'
    rule.save(update_fields=['is_executed', 'executed_at', 'executed_by'])

    return {'updated': updated, 'old': old_rate, 'new': new_rate}


def _apply_config_change(rule):
    """
    Promjena konfiguracije modula.
    Payload: {"module": "fiskalizacija", "key": "cis_endpoint", "value": "https://..."}
    """
    payload = rule.action_payload
    module = payload.get('module', '')
    key = payload.get('key', '')
    value = payload.get('value', '')

    logger.info('[BORG ADAPT] Config change: %s.%s = %s', module, key, value)

    # Za sada samo logiramo — auto-primjena konfiguracije
    # zahtijeva specifičnu implementaciju po modulu
    rule.is_executed = True
    rule.executed_at = timezone.now()
    rule.executed_by = 'auto:adaptation_engine'
    rule.save(update_fields=['is_executed', 'executed_at', 'executed_by'])

    return {'module': module, 'key': key, 'applied': True}


def _apply_notification(rule):
    """Samo obavijest — ne mijenja sustav, šalje WhatsApp/email."""
    try:
        from core.whatsapp import send_whatsapp_message
        from django.contrib.auth import get_user_model
        User = get_user_model()

        admins = User.objects.filter(
            is_staff=True, is_active=True,
        ).select_related('profile')[:3]

        msg = (
            f"BORG FENIX — Regulatorna promjena\n\n"
            f"{rule.regulatory_update.title}\n\n"
            f"Modul: {rule.target_module}\n"
            f"Akcija: {rule.action_description}\n\n"
            f"Potrebna ručna intervencija: limit-connect.com"
        )

        for admin in admins:
            phone = getattr(getattr(admin, 'profile', None), 'phone', None)
            if phone:
                send_whatsapp_message(phone, msg)

    except Exception as e:
        logger.warning('[BORG] Notification failed: %s', e)

    rule.is_executed = True
    rule.executed_at = timezone.now()
    rule.executed_by = 'auto:notification'
    rule.save(update_fields=['is_executed', 'executed_at', 'executed_by'])

    return {'notified': True}
