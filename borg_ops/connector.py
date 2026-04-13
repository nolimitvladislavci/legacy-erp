"""
BORG FENIX - Ops Connector v2 (F4 - uses BorgTask model)
Auto-creates BorgTasks from overdue invoices, anomalies, signals, adaptations.
"""

import logging

from celery import shared_task
from django.db import DatabaseError, IntegrityError
from django.db.models import Count
from django.utils import timezone

logger = logging.getLogger("borg.ops")


@shared_task
def sync_ops_tasks():
    """
    Sync BORG tasks with business events:
    1. Overdue invoices -> followup tasks
    2. Unresolved signals -> signal tasks
    3. Pending adaptations -> adaptation tasks
    4. New opportunity matches -> opportunity tasks
    """
    from borg_ops.models import BorgTask

    stats = {"invoices": 0, "signals": 0, "adaptations": 0, "opportunities": 0}

    # 1. Overdue invoices
    try:
        from invoicing.models import Invoice

        overdue = Invoice.objects.filter(
            status__in=["UNPAID", "OVERDUE"],
            date_due__lt=timezone.now().date(),
        )
        existing_refs = set(BorgTask.objects.filter(task_type="followup").values_list("reference_id", flat=True))
        for inv in overdue[:50]:
            ref = str(inv.number or inv.id)
            if ref in existing_refs:
                continue
            BorgTask.objects.create(
                company=inv.company,
                task_type="followup",
                title=f"Naplata: {inv.number} - {inv.client_name or 'N/A'}",
                description=f"Faktura dospjela {inv.date_due}. Iznos: {inv.total} EUR.",
                priority=2 if float(inv.total or 0) > 1000 else 3,
                reference_type="invoice",
                reference_id=ref,
                due_date=inv.date_due,
            )
            stats["invoices"] += 1
    except (ValueError, TypeError) as e:
        logger.warning("Invoice sync: %s", e)

    # 2. Unresolved signals (triaged, not resolved)
    try:
        from limit_connect_ai.models_signal import FenixSignal

        signals = FenixSignal.objects.filter(status="new").order_by("-created_at")[:20]
        existing_sigs = set(BorgTask.objects.filter(task_type="signal").values_list("reference_id", flat=True))
        for sig in signals:
            ref = str(sig.id)
            if ref in existing_sigs:
                continue
            BorgTask.objects.create(
                task_type="signal",
                title=f"Signal: {sig.message[:80]}",
                description=f"Page: {sig.page_url or 'N/A'}",
                priority=3,
                reference_type="signal",
                reference_id=ref,
            )
            stats["signals"] += 1
    except (IntegrityError, DatabaseError) as e:
        logger.warning("Signal sync: %s", e)

    # 3. Pending adaptation rules
    try:
        from limit_connect_ai.models_knowledge_graph import AdaptationRule

        pending = AdaptationRule.objects.filter(is_executed=False)
        existing_adapt = set(BorgTask.objects.filter(task_type="adaptation").values_list("reference_id", flat=True))
        for rule in pending:
            ref = str(rule.id)
            if ref in existing_adapt:
                continue
            BorgTask.objects.create(
                task_type="adaptation",
                title=f"Adaptacija: {rule.action_description[:80]}",
                description=f"Tip: {rule.rule_type}, Modul: {rule.target_module}",
                priority=2 if rule.can_auto_apply else 3,
                reference_type="adaptation_rule",
                reference_id=ref,
            )
            stats["adaptations"] += 1
    except (IntegrityError, DatabaseError) as e:
        logger.warning("Adaptation sync: %s", e)

    # 4. New opportunity matches (notified but not acted on)
    try:
        from django.db.models import Sum

        from limit_connect_ai.models import ClientOpportunityMatch

        # Group by company, count matches
        companies_with_opps = (
            ClientOpportunityMatch.objects.filter(status="notified")
            .values("company_id", "company__name")
            .annotate(cnt=Count("id"), savings=Sum("calculated_savings"))
            .filter(cnt__gte=5)
            .order_by("-savings")[:20]
        )
        existing_opp = set(BorgTask.objects.filter(task_type="opportunity").values_list("reference_id", flat=True))
        for co in companies_with_opps:
            ref = f"opp-{co['company_id']}"
            if ref in existing_opp:
                continue
            BorgTask.objects.create(
                company_id=co["company_id"],
                task_type="opportunity",
                title=f"{co['company__name']}: {co['cnt']} prilika ({float(co['savings'] or 0):.0f} EUR)",
                description=f"{co['cnt']} neiskoristenih olaksica za {co['company__name']}.",
                priority=3,
                reference_type="opportunity_batch",
                reference_id=ref,
            )
            stats["opportunities"] += 1
    except (ValueError, TypeError) as e:
        logger.warning("Opportunity sync: %s", e)

    logger.info("Ops sync: %s", stats)
    return stats


@shared_task
def ops_dashboard_stats():
    """Return BORG Ops dashboard statistics."""
    from django.db.models import Count

    from borg_ops.models import BorgTask

    total = BorgTask.objects.count()
    by_status = dict(BorgTask.objects.values_list("status").annotate(c=Count("id")).values_list("status", "c"))
    by_type = dict(BorgTask.objects.values_list("task_type").annotate(c=Count("id")).values_list("task_type", "c"))
    by_priority = dict(BorgTask.objects.values_list("priority").annotate(c=Count("id")).values_list("priority", "c"))

    return {
        "total": total,
        "by_status": by_status,
        "by_type": by_type,
        "by_priority": by_priority,
    }
