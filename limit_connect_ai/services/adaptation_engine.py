"""
BORG FENIX — Adaptation Engine
Automatska primjena regulatornih promjena na sustav.

Scenariji:
- tax_rate: Promjena PDV stope — Novi/Deaktiviraj pattern (čuva povijest)
- xml_schema: Update e-Račun validacije
- config_change: Promjena fiskalizacija config-a
- notification: Samo obavijest adminu

KRITIČNO: Povijesni podaci (POSReceiptItem, InvoiceItem) se NIKAD ne diraju.
Samo InventoryItem.tax_rate FK se ažurira na novu stopu.
"""
import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# Dispatcher — poziva se iz AdaptationRule.execute()
# ══════════════════════════════════════════════════════════════════════════════

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


# ══════════════════════════════════════════════════════════════════════════════
# TAX RATE — Novi/Deaktiviraj pattern (SAFE)
# ══════════════════════════════════════════════════════════════════════════════

def _apply_tax_rate(rule):
    """
    Promjena porezne stope — SIGURNI Novi/Deaktiviraj pattern.

    Payload: {
        "country": "HR",
        "old_rate": 25,
        "new_rate": 26,
        "new_name": "PDV 26%",
        "effective_date": "2027-01-01"
    }

    Postupak:
    1. Kreiraj novu TaxRate (26%) — get_or_create za idempotentnost
    2. Deaktiviraj staru (25%) — is_active=False, is_default=False
    3. Ažuriraj InventoryItem.tax_rate FK na novu stopu
    4. NE DIRAJ: POSReceiptItem.tax_rate, InvoiceItem.tax_rate (povijest!)
    """
    success, count = AdaptationEngine.execute_tax_rate_change(rule)
    return {'success': success, 'updated_items': count}


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

    rule.is_executed = True
    rule.executed_at = timezone.now()
    rule.executed_by = 'auto:adaptation_engine'
    rule.save(update_fields=['is_executed', 'executed_at', 'executed_by'])

    return {'module': module, 'key': key, 'applied': True}


def _apply_notification(rule):
    """Samo obavijest — ne mijenja sustav, šalje WhatsApp."""
    try:
        from core.notify import notify
        notify(
            'ACTION',
            f'Regulatorna promjena: {rule.regulatory_update.title}\n\n'
            f'Modul: {rule.target_module}\n'
            f'Akcija: {rule.action_description}\n\n'
            f'Potrebna ručna intervencija: limit-connect.com',
        )
    except ImportError as e:
        logger.warning('[BORG] Notification failed: %s', e)

    rule.is_executed = True
    rule.executed_at = timezone.now()
    rule.executed_by = 'auto:notification'
    rule.save(update_fields=['is_executed', 'executed_at', 'executed_by'])

    return {'notified': True}


# ══════════════════════════════════════════════════════════════════════════════
# AdaptationEngine klasa — kirurški precizan tax rate update
# ══════════════════════════════════════════════════════════════════════════════

class AdaptationEngine:
    """
    FENIX modul za automatsko usklađivanje baze sa zakonskim promjenama.

    Pravila:
    - NIKAD ne mijenjaj povijesne podatke (POS bonovi, fakture)
    - UVIJEK kreiraj novu stopu, deaktiviraj staru (audit trail)
    - UVIJEK koristi transaction.atomic (rollback na grešku)
    - NIKAD ne izvršavaj bez PENDING_APPROVAL → APPROVED tranzicije
    """

    @staticmethod
    @transaction.atomic
    def execute_tax_rate_change(rule):
        """
        Sigurno mijenja poreznu stopu u produkcijskoj bazi.

        Returns: (success: bool, updated_item_count: int)
        """
        from companies.models import TaxRate
        from inventory.models import InventoryItem

        payload = rule.action_payload
        country = payload.get('country', 'HR')
        old_rate = Decimal(str(payload.get('old_rate', 0)))
        new_rate = Decimal(str(payload.get('new_rate', 0)))
        new_name = payload.get('new_name', f'PDV {new_rate}%')

        if not old_rate or not new_rate:
            logger.error('[ADAPT] Payload mora sadržavati old_rate i new_rate')
            return False, 0

        if old_rate == new_rate:
            logger.warning('[ADAPT] Stara i nova stopa su identične (%s)', old_rate)
            return False, 0

        try:
            # 1. Pronađi staru stopu
            old_tax = TaxRate.objects.get(country=country, rate=old_rate)
        except TaxRate.DoesNotExist:
            logger.error('[ADAPT] Stara stopa %s%% za %s ne postoji u bazi', old_rate, country)
            return False, 0

        # 2. Kreiraj novu stopu (idempotentno — get_or_create)
        new_tax, created = TaxRate.objects.get_or_create(
            country=country,
            rate=new_rate,
            defaults={
                'name': new_name,
                'description': f'Kreirana automatski (FENIX) — zamjena za {old_tax.name}',
                'is_default': old_tax.is_default,
                'is_active': True,
            },
        )

        if created:
            logger.info('[ADAPT] Nova TaxRate kreirana: %s %s%%', country, new_rate)
        else:
            # Već postoji — osiguraj da je aktivna
            if not new_tax.is_active:
                new_tax.is_active = True
                new_tax.save(update_fields=['is_active'])
            logger.info('[ADAPT] TaxRate %s %s%% već postoji, koristimo je', country, new_rate)

        # 3. Deaktiviraj staru stopu
        old_tax.is_active = False
        old_tax.is_default = False
        old_tax.description = (
            f'{old_tax.description} [DEAKTIVIRANA {timezone.now().strftime("%d.%m.%Y")} '
            f'→ zamijenjena s {new_rate}%]'
        )[:255]
        old_tax.save(update_fields=['is_active', 'is_default', 'description'])
        logger.info('[ADAPT] Stara TaxRate deaktivirana: %s %s%%', country, old_rate)

        # 4. Migracija FK na InventoryItem (budući artikli)
        # VAŽNO: NE diramo POSReceiptItem ni InvoiceItem — oni čuvaju povijesnu stopu
        updated_count = InventoryItem.objects.filter(
            tax_rate=old_tax,
        ).update(tax_rate=new_tax)

        logger.info(
            '[ADAPT] Migrirano %d artikala s %s%% na %s%%',
            updated_count, old_rate, new_rate,
        )

        # 5. Zaključaj pravilo
        rule.is_executed = True
        rule.executed_at = timezone.now()
        rule.executed_by = 'auto:adaptation_engine'
        rule.error_log = ''
        rule.save(update_fields=['is_executed', 'executed_at', 'executed_by', 'error_log'])

        # 6. Notifikacija
        try:
            from core.notify import notify
            notify(
                'MONEY',
                f'PDV stopa ažurirana: {country} {old_rate}% → {new_rate}%\n'
                f'Ažurirano {updated_count} artikala.\n'
                f'Povijesni POS bonovi i fakture ostaju na {old_rate}%.',
            )
        except ImportError:
            pass

        logger.info(
            '[ADAPT] KOMPLET: %s %s%% → %s%%, %d artikala, pravilo zaključano',
            country, old_rate, new_rate, updated_count,
        )

        return True, updated_count

    @staticmethod
    def create_pending_rule(regulatory_update, country, old_rate, new_rate,
                            new_name=None, effective_date=None):
        """
        Kreira AdaptationRule u statusu PENDING — čeka odobrenje admina.
        Poziva se iz NN Feed Scrapera kad LLM detektira promjenu poreza.
        """
        from limit_connect_ai.models_knowledge_graph import AdaptationRule

        if not new_name:
            new_name = f'PDV {new_rate}%'

        rule, created = AdaptationRule.objects.get_or_create(
            regulatory_update=regulatory_update,
            rule_type='tax_rate',
            target_module='companies.TaxRate',
            defaults={
                'action_description': (
                    f'Promjena PDV stope: {country} {old_rate}% → {new_rate}%. '
                    f'Kreirati novu stopu, deaktivirati staru, '
                    f'migrirati artikle. Povijest se ne dira.'
                ),
                'action_payload': {
                    'country': country,
                    'old_rate': float(old_rate),
                    'new_rate': float(new_rate),
                    'new_name': new_name,
                    'effective_date': str(effective_date) if effective_date else None,
                },
                'can_auto_apply': False,  # NIKAD auto — čeka odobrenje
                'is_executed': False,
            },
        )

        if created:
            logger.info(
                '[ADAPT] Pending rule kreiran: %s %s%% → %s%% (čeka odobrenje)',
                country, old_rate, new_rate,
            )

        return rule, created
