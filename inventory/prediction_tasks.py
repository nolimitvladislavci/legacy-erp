"""Celery tasks for predictive inventory analytics."""

import logging

from celery import shared_task

logger = logging.getLogger("inventory.predictions")


@shared_task(bind=True, max_retries=2, retry_backoff=True)
def check_predictive_stockouts(self):
    """
    Daily check: predict stockouts for next 7 days.
    If critical items found, notify admins + auto-generate draft POs.
    Runs daily at 06:30 via Celery Beat.
    """
    from django.contrib.auth import get_user_model

    from companies.models import Company
    from inventory.models import InventoryItem
    from inventory.reorder import generate_draft_po, predict_reorder
    from notifications.services import notify

    User = get_user_model()

    # Company nema is_active field — filter po firmama koje imaju inventory
    for company in Company.objects.filter(inventory_items__isnull=False).distinct():
        try:
            # Get items with critical/warning reorder status
            items = InventoryItem.objects.filter(
                company=company,
                is_active=True,
                supplier__isnull=False,
            )

            critical_items = []
            for item in items:
                prediction = predict_reorder(item)
                if prediction and not prediction.get("insufficient_data"):
                    if prediction["urgency"] in ("critical", "warning"):
                        critical_items.append(
                            {
                                "item_id": item.pk,
                                "item_name": item.name,
                                "current_qty": float(item.quantity),
                                "days_left": prediction.get("days_left"),
                                "suggested_qty": float(prediction.get("suggested_qty", 0)),
                                "reorder_point": float(prediction.get("reorder_point", 0)),
                                "urgency": prediction["urgency"],
                                "supplier_name": item.supplier.name if item.supplier else "N/A",
                            }
                        )

            if not critical_items:
                continue

            # Auto-generate draft POs
            po_ids = generate_draft_po(company, items=critical_items)

            # Build notification message
            msg_lines = [f"\U0001f4e6 Prediktivna analiza \u2014 {len(critical_items)} artikala treba naru\u010diti:\n"]
            for ci in critical_items[:10]:
                emoji = "\U0001f534" if ci["urgency"] == "critical" else "\U0001f7e1"
                days = ci["days_left"]
                days_str = f"{days} dana" if days and days > 0 else "DANAS"
                msg_lines.append(f"{emoji} {ci['item_name']}: zaliha za {days_str}, treba {ci['suggested_qty']:.0f}")

            if po_ids:
                msg_lines.append(f"\n\u2705 Generirano {len(po_ids)} nacrt narud\u017ebenica. Pregledajte i potvrdite.")

            message = "\n".join(msg_lines)

            # Notify company admins
            from accounts.models import UserProfile

            admin_ids = UserProfile.objects.filter(company=company).values_list("user_id", flat=True)
            admins = User.objects.filter(id__in=admin_ids, is_active=True, is_staff=True)[:5]

            for admin in admins:
                notify(
                    recipient=admin,
                    notification_type="system",
                    title=f"\U0001f4e6 Prediktivna nabava \u2014 {len(critical_items)} artikala",
                    message=message[:500],
                    url="/procurement/" if po_ids else "/inventory/reorder-predictions/",
                    company=company,
                )

            logger.info(
                f"Predictive check for {company.name}: {len(critical_items)} items, {len(po_ids)} POs generated"
            )

        except (ValueError, TypeError) as e:
            logger.error(f"Predictive check failed for {company.id}: {e}")
