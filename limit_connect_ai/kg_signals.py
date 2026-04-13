"""
BORG FENIX — Knowledge Graph Signals (F2.3)
Auto-generates AdaptationRule candidates when RegulatoryUpdate is created.

Pipeline: NN Scraper → RegulatoryUpdate.post_save → auto-generate AdaptationRule
"""
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from limit_connect_ai.models_knowledge_graph import RegulatoryUpdate

logger = logging.getLogger('borg.kg_signals')

# Category → rule_type mapping
CATEGORY_RULE_MAP = {
    'TAX': 'tax_rate',
    'VAT': 'tax_rate',
    'FISCAL': 'config_change',
    'ERACUN': 'xml_schema',
    'LABOUR': 'notification',
    'CORP': 'notification',
    'TRADE': 'notification',
    'GDPR': 'config_change',
    'AML': 'config_change',
    'NONPROFIT': 'notification',
    'EU_FUND': 'notification',
    'OTHER': 'notification',
}

# Category → target_module mapping
CATEGORY_MODULE_MAP = {
    'TAX': 'companies.TaxRate',
    'VAT': 'companies.TaxRate',
    'FISCAL': 'fiskalizacija',
    'ERACUN': 'einvoice',
    'LABOUR': 'payroll',
    'CORP': 'companies',
    'TRADE': 'invoicing',
    'GDPR': 'accounts',
    'AML': 'aml',
    'NONPROFIT': 'udruge',
    'EU_FUND': 'intelligence',
    'OTHER': 'core',
}


@receiver(post_save, sender=RegulatoryUpdate)
def auto_generate_adaptation_rule(sender, instance, created, **kwargs):
    """
    When a new RegulatoryUpdate is saved, auto-generate an AdaptationRule candidate.
    Rules with impact_score >= 7 get can_auto_apply=True (for tax/config).
    Rules with impact_score < 7 are notification-only.
    """
    if not created:
        return

    if not instance.is_processed:
        return

    from limit_connect_ai.models_knowledge_graph import AdaptationRule

    # Don't duplicate
    if AdaptationRule.objects.filter(regulatory_update=instance).exists():
        return

    category = instance.category or 'OTHER'
    rule_type = CATEGORY_RULE_MAP.get(category, 'notification')
    target_module = CATEGORY_MODULE_MAP.get(category, 'core')

    # High-impact tax/config changes can be auto-applied
    can_auto = (
        instance.impact_score >= 7
        and rule_type in ('tax_rate', 'config_change')
        and not instance.is_breaking  # Breaking changes need human review
    )

    rule = AdaptationRule.objects.create(
        regulatory_update=instance,
        rule_type=rule_type,
        target_module=target_module,
        action_description=f"Auto-generated from: {instance.title[:200]}. "
                          f"Category: {category}, Impact: {instance.impact_score}/10. "
                          f"{'REQUIRES HUMAN REVIEW' if instance.is_breaking else 'Can auto-apply' if can_auto else 'Notification only'}",
        action_payload={
            'source_title': instance.title[:300],
            'category': category,
            'impact_score': instance.impact_score,
            'affected_modules': instance.affected_modules or [],
            'nn_number': instance.nn_number,
            'effective_date': str(instance.effective_date) if instance.effective_date else None,
        },
        can_auto_apply=can_auto,
    )

    logger.info(
        'Auto-generated AdaptationRule %s for RegulatoryUpdate "%s" '
        '(type=%s, module=%s, auto=%s)',
        rule.id, instance.title[:60], rule_type, target_module, can_auto,
    )


@receiver(post_save, sender=RegulatoryUpdate)
def auto_scan_opportunities(sender, instance, created, **kwargs):
    """
    When a new RegulatoryUpdate with EU_FUND category arrives,
    trigger opportunity scan for all companies.
    """
    if not created:
        return

    if instance.category != 'EU_FUND':
        return

    # Defer to Celery to avoid blocking
    try:
        from limit_connect_ai.tasks import scan_opportunities_task
        scan_opportunities_task.delay()
        logger.info('Triggered opportunity scan from EU_FUND update: %s', instance.title[:60])
    except ImportError:
        # If celery task doesn't exist, run inline
        try:
            from limit_connect_ai.services.kg_seeder import scan_all_companies
            scan_all_companies()
        except ImportError as e:
            logger.warning('Could not trigger opportunity scan: %s', e)
