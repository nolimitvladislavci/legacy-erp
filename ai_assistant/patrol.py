import json
import logging
import os

from django.db import DatabaseError

logger = logging.getLogger("ai_assistant.patrol")


def _gather_patrol_data(company):
    """Collect data points from all modules."""
    from datetime import timedelta

    from django.utils import timezone

    now = timezone.now()
    data = {}

    # 1. Tracking - late deliveries
    try:
        from delivery.models import ConsolidatedDelivery

        active = ConsolidatedDelivery.objects.filter(hub_company=company, status__in=["dispatched", "in_transit"])
        late = active.filter(eta__lt=now)
        data["tracking"] = {
            "active_deliveries": active.count(),
            "late_deliveries": late.count(),
            "late_details": list(late.values("delivery_number", "eta", "buyer_company__name")[:5]),
        }
    except DatabaseError:
        data["tracking"] = {"error": "Module not available"}

    # 2. Inventory - low stock & expiring
    try:
        from django.db.models import F

        from inventory.models import InventoryItem, StockBatch

        low = InventoryItem.objects.filter(
            company=company, is_active=True, quantity__lte=F("min_quantity"), min_quantity__gt=0
        )
        expiring = StockBatch.objects.filter(
            item__company=company, quarantine_status="active", expiry_date__lte=now.date() + timedelta(days=7)
        )
        data["inventory"] = {
            "low_stock_count": low.count(),
            "low_stock_items": list(low.values("name", "sku", "quantity", "min_quantity")[:10]),
            "expiring_batches_7d": expiring.count(),
            "expiring_details": list(expiring.values("item__name", "batch_number", "expiry_date", "quantity")[:5]),
        }
    except DatabaseError:
        data["inventory"] = {"error": "Module not available"}

    # 3. SmartBox - temperature alerts
    try:
        from delivery.models import SmartBox

        boxes = SmartBox.objects.filter(owner_company=company, has_sensor=True)
        alerts = []
        for box in boxes:
            if box.last_temp is not None and not box.is_temp_ok:
                alerts.append(
                    {
                        "box_id": box.box_id,
                        "temp": float(box.last_temp),
                        "target": "{}-{}C".format(float(box.target_min_temp), float(box.target_max_temp)),
                        "haccp": box.haccp_status,
                    }
                )
        data["smartbox"] = {"total_boxes": boxes.count(), "temp_alerts": alerts}
    except (ValueError, TypeError):
        data["smartbox"] = {"error": "Module not available"}

    # 4. Propter - unbilled otpremnice
    try:
        from django.db.models import Sum

        from propter.models import Otpremnica

        unbilled = Otpremnica.objects.filter(company=company, status="issued")
        agg = unbilled.aggregate(total=Sum("total"))
        data["propter"] = {
            "unbilled_count": unbilled.count(),
            "unbilled_total_eur": float(agg["total"] or 0),
        }
    except (ValueError, TypeError):
        data["propter"] = {"error": "Module not available"}

    # 5. Maintenance - expiring documents
    try:
        from maintenance.models import Asset

        threshold = now.date() + timedelta(days=14)
        expiring = Asset.objects.filter(company=company, status="active")
        exp_items = []
        for asset in expiring:
            for field, label in [
                ("insurance_until", "Osiguranje"),
                ("registration_until", "Registracija"),
                ("warranty_until", "Garancija"),
                ("leasing_until", "Leasing"),
            ]:
                val = getattr(asset, field, None)
                if val and val <= threshold:
                    exp_items.append(
                        {
                            "asset": asset.name,
                            "document": label,
                            "expires": str(val),
                            "days_left": (val - now.date()).days,
                        }
                    )
        data["maintenance"] = {"expiring_documents": exp_items[:10], "expiring_count": len(exp_items)}
    except DatabaseError:
        data["maintenance"] = {"error": "Module not available"}

    # 6. Invoicing - overdue invoices
    try:
        from django.db.models import Sum

        from invoicing.models import Invoice

        overdue = Invoice.objects.filter(company=company, status="OVERDUE")
        agg = overdue.aggregate(total=Sum("total"))
        data["invoicing"] = {
            "overdue_count": overdue.count(),
            "overdue_total_eur": float(agg["total"] or 0),
            "overdue_details": list(overdue.values("number", "partner__name", "total", "date_due")[:5]),
        }
    except (ValueError, TypeError):
        data["invoicing"] = {"error": "Module not available"}

    # 7. Helpdesk - open/overdue tickets
    try:
        from helpdesk.models import Ticket

        open_tickets = Ticket.objects.filter(company=company, status__in=["open", "in_progress"])
        overdue_tickets = [t for t in open_tickets if t.is_overdue]
        data["helpdesk"] = {
            "open_tickets": open_tickets.count(),
            "overdue_tickets": len(overdue_tickets),
        }
    except DatabaseError:
        data["helpdesk"] = {"error": "Module not available"}

    # 8. Procurement - pending POs
    try:
        from procurement.models import PurchaseOrder

        pending = PurchaseOrder.objects.filter(company=company, status__in=["draft", "sent", "confirmed"])
        data["procurement"] = {
            "pending_pos": pending.count(),
            "pending_details": list(pending.values("po_number", "supplier__name", "total", "status")[:5]),
        }
    except DatabaseError:
        data["procurement"] = {"error": "Module not available"}

    # 9. POS - yesterday's revenue
    try:
        from django.db.models import Sum

        from pos.models import POSReceipt

        yesterday = (now - timedelta(days=1)).date()
        receipts = POSReceipt.objects.filter(
            session__terminal__company=company, created_at__date=yesterday, status="paid"
        )
        rev = receipts.aggregate(total=Sum("total"))
        data["pos"] = {"yesterday_receipts": receipts.count(), "yesterday_revenue_eur": float(rev["total"] or 0)}
    except (ValueError, TypeError):
        data["pos"] = {"error": "Module not available"}

    # 10. Payments - pending
    try:
        from django.db.models import Sum

        from payments.models import Payment

        pending = Payment.objects.filter(company=company, status__in=["pending", "processing"])
        agg = pending.aggregate(total=Sum("amount"))
        data["payments"] = {"pending_count": pending.count(), "pending_total_eur": float(agg["total"] or 0)}
    except (ValueError, TypeError):
        data["payments"] = {"error": "Module not available"}

    def _sanitize_data(obj):
        import datetime
        from decimal import Decimal

        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, (datetime.date, datetime.datetime)):
            return str(obj)
        if isinstance(obj, dict):
            return {k: _sanitize_data(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_sanitize_data(v) for v in obj]
        return obj

    return _sanitize_data(data)


def _fallback_summary(data, company):
    """Generate a simple text summary if Gemini is unavailable."""
    lines = ["Jutarnji izvjestaj za {}:".format(company.name)]

    t = data.get("tracking", {})
    if t.get("late_deliveries", 0):
        lines.append("UPOZORENJE: {} kasnih isporuka!".format(t["late_deliveries"]))

    inv = data.get("inventory", {})
    if inv.get("low_stock_count", 0):
        lines.append("UPOZORENJE: {} artikala ispod minimalne zalihe".format(inv["low_stock_count"]))
    if inv.get("expiring_batches_7d", 0):
        lines.append("UPOZORENJE: {} serija istjece u 7 dana".format(inv["expiring_batches_7d"]))

    sb = data.get("smartbox", {})
    if sb.get("temp_alerts"):
        lines.append("KRITICNO: {} SmartBox temperaturnih alarma!".format(len(sb["temp_alerts"])))

    p = data.get("propter", {})
    if p.get("unbilled_count", 0):
        lines.append(
            "INFO: {} otpremnica za fakturiranje ({:.0f} EUR)".format(
                p["unbilled_count"], p.get("unbilled_total_eur", 0)
            )
        )

    m = data.get("maintenance", {})
    if m.get("expiring_count", 0):
        lines.append("UPOZORENJE: {} dokumenata istjece uskoro".format(m["expiring_count"]))

    i = data.get("invoicing", {})
    if i.get("overdue_count", 0):
        lines.append(
            "UPOZORENJE: {} neplacenih faktura ({:.0f} EUR)".format(i["overdue_count"], i.get("overdue_total_eur", 0))
        )

    h = data.get("helpdesk", {})
    if h.get("overdue_tickets", 0):
        lines.append("UPOZORENJE: {} prekoracenih tiketa".format(h["overdue_tickets"]))

    pos = data.get("pos", {})
    if pos.get("yesterday_revenue_eur", 0):
        lines.append(
            "INFO: Jucerasnji POS promet: {:.0f} EUR ({} bonova)".format(
                pos["yesterday_revenue_eur"], pos.get("yesterday_receipts", 0)
            )
        )

    if len(lines) == 1:
        lines.append("SVE OK. Nema kriticnih upozorenja.")

    return "\n".join(lines)


def run_patrol(company):
    """Run AI patrol for a company. Returns report dict."""
    data = _gather_patrol_data(company)

    has_issues = any(
        [
            data.get("tracking", {}).get("late_deliveries", 0) > 0,
            data.get("inventory", {}).get("low_stock_count", 0) > 0,
            data.get("inventory", {}).get("expiring_batches_7d", 0) > 0,
            len(data.get("smartbox", {}).get("temp_alerts", [])) > 0,
            data.get("propter", {}).get("unbilled_count", 0) > 0,
            data.get("maintenance", {}).get("expiring_count", 0) > 0,
            data.get("invoicing", {}).get("overdue_count", 0) > 0,
            data.get("helpdesk", {}).get("overdue_tickets", 0) > 0,
        ]
    )

    system_prompt = (
        "Ti si AI patrol agent za ERP sustav LIMIT Connect. "
        "Tvoj zadatak je analizirati nocne podatke i generirati sazet jutarnji izvjestaj za direktora.\n\n"
        "PRAVILA:\n"
        "- Pisi na hrvatskom jeziku\n"
        "- Budi koncizan - max 5-6 recenica\n"
        "- Navedi SAMO probleme i prilike za akciju\n"
        "- Ako je sve u redu, reci 'Sve je u redu' i navedi samo kljucne brojke\n"
        "- Ako ima problema, sortiraj ih po hitnosti (KRITICNO > UPOZORENJE > INFO)\n"
        "- Za svaki problem predlozi konkretnu akciju\n"
        "- Zavrsi s jednim pozivom na akciju ako je relevantan\n"
        "- NE ponavljaj sirove brojke - interpretiraj ih"
    )

    data_json = json.dumps(data, indent=2, default=str, ensure_ascii=True)
    user_prompt = 'Evo nocnog skeniranja modula za tvrtku "{}":\n\n{}\n\nGeneriraj jutarnji sazatak.'.format(
        company.name, data_json
    )

    # Sanitize prompts to avoid surrogate encoding issues
    system_prompt = system_prompt.encode("utf-8", errors="replace").decode("utf-8")
    user_prompt = user_prompt.encode("utf-8", errors="replace").decode("utf-8")
    try:
        import google.generativeai as genai

        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            from django.conf import settings

            api_key = getattr(settings, "GEMINI_API_KEY", "")

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.5-flash")

        response = model.generate_content(
            [{"role": "user", "parts": [{"text": system_prompt + "\n\n" + user_prompt}]}],
            generation_config={"temperature": 0.3, "max_output_tokens": 1000},
        )

        summary = response.text
    except ImportError as e:
        logger.error("Gemini patrol failed for {}: {}".format(company.name, e))
        summary = _fallback_summary(data, company)

    return {
        "company_id": company.id,
        "company_name": company.name,
        "has_issues": has_issues,
        "summary": summary,
        "raw_data": data,
    }


def generate_insights(report):
    """Generate actionable insights from patrol report findings."""
    insights = []
    if not report.findings:
        return insights

    findings = report.findings if isinstance(report.findings, list) else []
    for finding in findings:
        severity = finding.get("severity", "info")
        module = finding.get("module", "")
        message = finding.get("message", "")

        insight = {
            "module": module,
            "severity": severity,
            "message": message,
            "action_url": "",
            "action_label": "",
        }

        msg_lower = message.lower()
        if "zalihe" in msg_lower or "stock" in msg_lower or module == "inventory":
            insight["action_url"] = "/inventory/?filter=low_stock"
            insight["action_label"] = "Pregled zaliha"
        elif "faktur" in msg_lower or "invoice" in msg_lower or module == "invoicing":
            insight["action_url"] = "/invoicing/?status=OVERDUE"
            insight["action_label"] = "Dospjele fakture"
        elif "dostav" in msg_lower or "delivery" in msg_lower or module == "tracking":
            insight["action_url"] = "/delivery/"
            insight["action_label"] = "Pregled dostava"
        elif "temperatur" in msg_lower or module == "smartbox":
            insight["action_url"] = "/delivery/smartbox/"
            insight["action_label"] = "SmartBox nadzor"
        elif "pos" in msg_lower or module == "pos":
            insight["action_url"] = "/pos/"
            insight["action_label"] = "POS pregled"
        elif "helpdesk" in msg_lower or "tiket" in msg_lower:
            insight["action_url"] = "/helpdesk/"
            insight["action_label"] = "Otvoreni tiketi"

        insights.append(insight)

    return insights


def send_patrol_notifications(company, report):
    """Send notifications to company admins with patrol insights."""
    try:
        from notifications.services import notify
    except ImportError:
        return
    from accounts.models import UserProfile

    insights = generate_insights(report)
    if not insights and not report.has_issues:
        return

    admins = UserProfile.objects.filter(company=company, role__in=["company_admin", "superadmin"]).select_related(
        "user"
    )

    for profile in admins:
        title = "Connect Patrol"
        if report.has_issues:
            title += " — Problemi!"
        else:
            title += " — OK"

        notify(
            recipient=profile.user,
            notification_type="system",
            title=title,
            message=report.summary[:300] if report.summary else "Jutarnji pregled zavrsen.",
            url="/ai/patrol/",
            company=company,
        )

        for insight in insights:
            if insight["severity"] in ("critical", "warning"):
                notify(
                    recipient=profile.user,
                    notification_type="system",
                    title="Connect Insight: %s" % insight["module"],
                    message=insight["message"][:200],
                    url=insight.get("action_url", "/ai/patrol/"),
                    company=company,
                )
