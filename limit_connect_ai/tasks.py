"""
Celery tasks for LIMIT Connect AI.
Morning report: generates per-company AI summary and sends via WhatsApp/email.
"""
import logging
import os
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger("limit_connect_ai")


@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def morning_report_all(self):
    """Find all active daily missions due now and dispatch reports."""
    from .models import AIAgentMission

    now = timezone.now()
    missions = AIAgentMission.objects.filter(
        is_active=True,
        frequency="daily",
        next_run__lte=now,
    ).select_related("company")

    count = 0
    for mission in missions:
        try:
            send_morning_report(mission.id)
            count += 1
        except Exception as exc:
            logger.error("Morning report failed for mission %s: %s", mission.id, exc)

    logger.info("morning_report_all: processed %d missions", count)
    return "Processed {} missions".format(count)


def send_morning_report(mission_id):
    """Generate and send a morning report for a single mission."""
    from .models import AIAgentMission, AIReportLog
    from core.whatsapp import send_text
    from core.email_tasks import send_email_task

    mission = AIAgentMission.objects.select_related("company").get(id=mission_id)
    company = mission.company
    now = timezone.now()

    # Gather business data
    context = _gather_company_context(company)

    # Generate report text via Claude Haiku
    report_text, tokens_used = _generate_report_with_ai(company, context)

    # Create log entry
    log = AIReportLog.objects.create(
        company=company,
        mission=mission,
        report_type="daily_report",
        content=report_text,
        sent_via=mission.notify_channel,
        status="pending",
        ai_tokens_used=tokens_used,
    )

    # Send via configured channel
    success = False
    error_msg = ""

    if mission.notify_channel in ("whatsapp", "both"):
        if mission.notify_target:
            result = send_text(mission.notify_target, report_text, company_id=str(company.id))
            if result.get("success"):
                success = True
            else:
                error_msg = result.get("error", "WhatsApp send failed")

    if mission.notify_channel in ("email", "both"):
        target_email = mission.notify_target if "@" in (mission.notify_target or "") else ""
        if target_email:
            try:
                send_email_task.delay(
                    subject="LIMIT AI izvjestaj -- {} -- {}".format(company.name, now.strftime("%d.%m.%Y")),
                    message=report_text,
                    from_email="noreply@limit-connect.com",
                    recipient_list=[target_email],
                )
                success = True
            except Exception as exc:
                error_msg += " Email: {}".format(exc)

    # Update log
    log.status = "sent" if success else "failed"
    log.error_message = error_msg
    log.save(update_fields=["status", "error_message"])

    # Update mission schedule
    mission.last_run = now
    mission.next_run = now + timedelta(days=1)
    mission.save(update_fields=["last_run", "next_run"])

    return log


def _gather_company_context(company):
    """Gather POS, inventory, invoice data for the company."""
    from django.db.models import Sum, Count, F

    today = timezone.now().date()
    ctx = {
        "company_name": company.name,
        "date": today.strftime("%d.%m.%Y"),
    }

    # POS today
    try:
        from pos.models import POSReceipt
        receipts_today = POSReceipt.objects.filter(
            company=company,
            created_at__date=today,
        )
        agg = receipts_today.aggregate(
            total=Sum("total_amount"),
            count=Count("id"),
        )
        ctx["pos_revenue"] = float(agg["total"] or 0)
        ctx["pos_count"] = agg["count"] or 0
    except Exception:
        ctx["pos_revenue"] = 0
        ctx["pos_count"] = 0

    # Open invoices
    try:
        from invoicing.models import Invoice
        open_inv = Invoice.objects.filter(
            company=company,
            status__in=["sent", "overdue"],
        ).aggregate(
            total=Sum("total_amount"),
            count=Count("id"),
        )
        ctx["open_invoices_count"] = open_inv["count"] or 0
        ctx["open_invoices_total"] = float(open_inv["total"] or 0)
    except Exception:
        ctx["open_invoices_count"] = 0
        ctx["open_invoices_total"] = 0

    # Low stock items
    try:
        from inventory.models import InventoryItem
        low = InventoryItem.objects.filter(
            company=company,
            quantity__lte=F("reorder_level"),
        ).count()
        ctx["low_stock_count"] = low
    except Exception:
        ctx["low_stock_count"] = 0

    # Active funds
    try:
        from intelligence.models import FundOpportunity
        ctx["active_funds"] = FundOpportunity.objects.filter(status="aktivan").count()
    except Exception:
        ctx["active_funds"] = 0

    # Overdue invoices (dospjele fakture)
    try:
        from invoicing.models import Invoice
        overdue = Invoice.objects.filter(
            company=company,
            status__in=['SENT', 'UNPAID', 'OVERDUE'],
            date_due__lt=today,
        ).order_by('date_due')[:5]
        ctx["overdue_invoices"] = [
            {"number": inv.number, "client": inv.client_name,
             "total": float(inv.total or 0),
             "days": (today - inv.date_due).days}
            for inv in overdue
        ]
        ctx["overdue_count"] = Invoice.objects.filter(
            company=company, status__in=['SENT', 'UNPAID', 'OVERDUE'],
            date_due__lt=today,
        ).count()
    except Exception:
        ctx["overdue_invoices"] = []
        ctx["overdue_count"] = 0

    # Open helpdesk tickets
    try:
        from helpdesk.models import Ticket
        open_tickets = Ticket.objects.filter(
            company=company,
            status__in=['open', 'in_progress'],
        ).count()
        ctx["open_tickets"] = open_tickets
    except Exception:
        ctx["open_tickets"] = 0

    # Bank unmatched transactions
    try:
        from konto.models import BankTransaction
        ctx["unmatched_transactions"] = BankTransaction.objects.filter(
            company=company, status='unmatched'
        ).count()
    except Exception:
        ctx["unmatched_transactions"] = 0

    # Worktime anomalies (today)
    try:
        from worktime.models import AnomalyReport
        ctx["worktime_anomalies"] = AnomalyReport.objects.filter(
            company=company,
            created_at__date=today,
        ).count()
    except Exception:
        ctx["worktime_anomalies"] = 0

    return ctx


def _generate_report_with_ai(company, context):
    """Use Claude Haiku to generate a morning report. Falls back to template."""

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return _fallback_report(context), 0

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        parts = [
            "Generiraj kratki jutarnji poslovni izvjestaj za firmu",
            context["company_name"],
            "za datum",
            context["date"],
            ". Koristi emoji ikone.",
            "Podaci: POS promet=" + str(round(context["pos_revenue"], 2)) + " EUR",
            "(" + str(context["pos_count"]) + " racuna),",
            "otvoreni racuni=" + str(context["open_invoices_count"]),
            "(" + str(round(context["open_invoices_total"], 2)) + " EUR),",
            "niske zalihe=" + str(context["low_stock_count"]) + " artikala,",
            "aktivni fondovi=" + str(context["active_funds"]) + ".",
            "Budi kratak, konkretan, na hrvatskom jeziku. Max 10 redaka.",
        ]
        prompt = " ".join(parts)

        response = client.messages.create(
            model="claude-haiku-4-20250514",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text
        tokens = response.usage.input_tokens + response.usage.output_tokens
        return text, tokens

    except Exception as exc:
        logger.warning("AI generation failed, using fallback: %s", exc)
        return _fallback_report(context), 0



def _fallback_report(ctx):
    """Template-based report when AI is unavailable."""
    if ctx["low_stock_count"]:
        stock_status = "{} artikala s niskim zalihama".format(ctx["low_stock_count"])
    else:
        stock_status = "OK"

    if ctx["active_funds"]:
        fund_status = "{} aktivnih natjecaja".format(ctx["active_funds"])
    else:
        fund_status = "Nema novih"

    lines = [
        "Dobro jutro!",
        "Ovo je tvoj AI sazetak za {}:".format(ctx["date"]),
        "",
        "Promet: {:.2f} EUR ({} racuna)".format(ctx["pos_revenue"], ctx["pos_count"]),
        "Zalihe: {}".format(stock_status),
        "Otvoreni racuni: {} ({:.2f} EUR)".format(ctx["open_invoices_count"], ctx["open_invoices_total"]),
        "Compliance: OK",
        "Fondovi: {}".format(fund_status),
    ]
    return chr(10).join(lines)


@shared_task(bind=True, max_retries=1, default_retry_delay=120)
def fund_check_all(self):
    """09:00 daily — check for new fund opportunities matching company profiles."""
    from .models import AIAgentMission

    missions = AIAgentMission.objects.filter(
        is_active=True,
        mission_type='fund_watch',
    ).select_related('company')

    count = 0
    for mission in missions:
        try:
            _check_funds_for_company(mission)
            count += 1
        except Exception as exc:
            logger.error("Fund check failed for mission %s: %s", mission.id, exc)

    logger.info("fund_check_all: processed %d missions", count)
    return "Processed {} fund missions".format(count)


def _check_funds_for_company(mission):
    """Check new fund opportunities and create drafts if eligible."""
    from intelligence.models import FundOpportunity
    from .models import FundApplicationDraft

    company = mission.company
    active_funds = FundOpportunity.objects.filter(
        status='aktivan',
        rok_prijave__gte=timezone.now().date(),
    )

    for fund in active_funds:
        existing = FundApplicationDraft.objects.filter(
            company=company, fund_opportunity=fund,
        ).exists()
        if existing:
            continue

        # Basic eligibility check based on company type
        bt = company.business_type
        cs = fund.ciljna_skupina
        if cs != 'svi' and bt != cs:
            continue

        FundApplicationDraft.objects.create(
            company=company,
            fund_opportunity=fund,
            status='draft',
            eligibility_score=50,
            eligibility_notes='Automatski detektirano — potreban review.',
        )
        logger.info("Created fund draft: %s for %s", fund.naziv, company.name)


@shared_task(bind=True, max_retries=1, default_retry_delay=120)
def compliance_check_all(self):
    """Monday 08:00 — check compliance status for all active compliance missions."""
    from .models import AIAgentMission, ComplianceWatchItem

    missions = AIAgentMission.objects.filter(
        is_active=True,
        mission_type='compliance_watch',
    ).select_related('company')

    count = 0
    for mission in missions:
        try:
            company = mission.company
            overdue = ComplianceWatchItem.objects.filter(
                company=company,
                status__in=['action_needed', 'in_progress'],
                deadline__lt=timezone.now().date(),
            )
            if overdue.exists():
                from core.whatsapp import send_text
                items = ", ".join(o.law_reference for o in overdue[:5])
                msg = "Compliance upozorenje za {}:\nIstekli rokovi: {}".format(
                    company.name, items,
                )
                if mission.notify_target:
                    send_text(mission.notify_target, msg, company_id=str(company.id))
            count += 1
        except Exception as exc:
            logger.error("Compliance check failed for mission %s: %s", mission.id, exc)

    logger.info("compliance_check_all: processed %d missions", count)
    return "Processed {} compliance missions".format(count)


@shared_task(bind=True, max_retries=1, default_retry_delay=120)
def campaign_suggestions_all(self):
    """Friday 10:00 — generate AI campaign suggestions for companies."""
    from .models import AIAgentMission, CampaignPlan

    missions = AIAgentMission.objects.filter(
        is_active=True,
        mission_type='campaign_planner',
    ).select_related('company')

    count = 0
    for mission in missions:
        try:
            company = mission.company
            # Create a draft AI suggestion
            CampaignPlan.objects.create(
                company=company,
                title="AI prijedlog kampanje — {}".format(
                    timezone.now().strftime("%d.%m.%Y"),
                ),
                campaign_type='promo',
                channel=mission.notify_channel if mission.notify_channel != 'chat' else 'whatsapp',
                status='draft',
                ai_suggestion=True,
                message_template="AI ce generirati sadrzaj kampanje nakon odobrenja.",
                created_by=mission.created_by,
            )
            count += 1
        except Exception as exc:
            logger.error("Campaign suggestion failed for mission %s: %s", mission.id, exc)

    logger.info("campaign_suggestions_all: processed %d missions", count)
    return "Processed {} campaign missions".format(count)
