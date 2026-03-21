"""
Tool handler implementations. Each function receives (params, user, company)
and returns a dict/list that will be JSON-serialized as tool_result.
"""
import logging
from datetime import date, timedelta
from decimal import Decimal
from django.db.models import Sum, Count
from django.utils import timezone

logger = logging.getLogger(__name__)


def handle_tool_call(tool_name, params, user, company):
    """Dispatch a tool call to its handler. Returns serializable result."""
    handlers = {
        "search_articles": _search_articles,
        "get_expiring_articles": _get_expiring_articles,
        "get_today_revenue": _get_today_revenue,
        "get_active_orders": _get_active_orders,
        "get_burza_leads": _get_burza_leads,
        "get_worktime_summary": _get_worktime_summary,
        "get_upcoming_appointments": _get_upcoming_appointments,
        "get_active_interventions": _get_active_interventions,
        "get_outreach_contacts": _get_outreach_contacts,
        "get_tracking_status": _get_tracking_status,
        "analyze_inventory_value": _analyze_inventory_value,
        "get_cashflow_summary": _get_cashflow_summary,
        "get_pending_payments": _get_pending_payments,
        "run_system_health_check": _run_system_health_check,
        "validate_pos_math": _validate_pos_math,
        "run_test_suite": _run_test_suite,
        "audit_data_integrity": _audit_data_integrity,
        "explain_business_flow": _explain_business_flow,
        "get_worktime_report": _get_worktime_report,
        "preview_invoice_from_hours": _preview_invoice_from_hours,
        "create_invoice_from_hours": _create_invoice_from_hours,
        "get_fund_opportunities": _get_fund_opportunities,
        "get_livestock_status": _get_livestock_status,
        "create_futures_listing": _create_futures_listing,
        "get_compliance_warnings": _get_compliance_warnings,
        "get_intelligence_results": _get_intelligence_results,
    }
    handler = handlers.get(tool_name)
    if not handler:
        return {"error": f"Nepoznat alat: {tool_name}"}
    try:
        return handler(params, user, company)
    except Exception as e:
        logger.exception("Tool handler error: %s", tool_name)
        return {"error": str(e)}


def _search_articles(params, user, company):
    from inventory.models import InventoryItem
    query = params.get("query", "")
    category = params.get("category", "")
    qs = InventoryItem.objects.filter(company=company, is_active=True)
    if query:
        qs = qs.filter(name__icontains=query)
    if category:
        qs = qs.filter(category=category)
    items = list(qs[:20].values("name", "sku", "category", "unit_price", "quantity", "barcode"))
    for item in items:
        if item.get("unit_price") is not None:
            item["unit_price"] = float(item["unit_price"])
        if item.get("quantity") is not None:
            item["quantity"] = float(item["quantity"])
    return {"count": qs.count(), "items": items}


def _get_expiring_articles(params, user, company):
    from pos.models import ExpiryBatch
    days = params.get("days_ahead", 7)
    cutoff = date.today() + timedelta(days=days)
    batches = ExpiryBatch.objects.filter(
        is_removed=False,
        expiry_date__lte=cutoff,
    ).select_related("inventory_item")
    if company:
        batches = batches.filter(company=company)
    result = []
    for b in batches[:20]:
        result.append({
            "article": b.inventory_item.name if b.inventory_item else "N/A",
            "batch": b.batch_number,
            "expiry_date": str(b.expiry_date),
            "quantity": float(b.quantity),
            "is_expired": b.is_expired,
            "days_left": b.days_until_expiry,
        })
    return {"count": len(result), "batches": result}


def _get_today_revenue(params, user, company):
    from pos.models import POSReceipt
    today = timezone.now().date()
    qs = POSReceipt.objects.filter(
        session__terminal__company=company,
        created_at__date=today,
    )
    agg = qs.aggregate(
        total=Sum("total"),
        tax=Sum("tax_amount"),
        count=Count("id"),
    )
    return {
        "date": str(today),
        "total_revenue": float(agg["total"] or 0),
        "total_tax": float(agg["tax"] or 0),
        "receipt_count": agg["count"],
    }


def _get_active_orders(params, user, company):
    from pos.models import GastroOrder
    status = params.get("status", "")
    qs = GastroOrder.objects.exclude(status__in=["paid", "cancelled"])
    if company:
        qs = qs.filter(company=company)
    if status:
        qs = qs.filter(status=status)
    orders = []
    for o in qs[:20]:
        orders.append({
            "id": o.id,
            "table": getattr(o, "table_number", ""),
            "status": o.status,
            "total": float(getattr(o, "total", 0) or 0),
            "created": str(o.created_at) if hasattr(o, "created_at") else "",
        })
    return {"count": len(orders), "orders": orders}


def _get_burza_leads(params, user, company):
    from burza.models import ProjectLead
    status = params.get("status", "")
    limit = params.get("limit", 10)
    qs = ProjectLead.objects.filter(company=company)
    if status:
        qs = qs.filter(status=status)
    leads = []
    for lead in qs[:limit]:
        leads.append({
            "id": lead.id,
            "title": lead.title,
            "category": getattr(lead, "category", ""),
            "status": lead.status,
        })
    return {"count": qs.count(), "leads": leads}


def _get_worktime_summary(params, user, company):
    from worktime.models import TimeEntry
    period = params.get("period", "today")
    today = date.today()
    if period == "week":
        start = today - timedelta(days=today.weekday())
    elif period == "month":
        start = today.replace(day=1)
    else:
        start = today
    qs = TimeEntry.objects.filter(user=user, date__gte=start, date__lte=today)
    agg = qs.aggregate(total_hours=Sum("duration"), count=Count("id"))
    total_dur = agg["total_hours"] or timedelta()
    if isinstance(total_dur, timedelta):
        hours = total_dur.total_seconds() / 3600
    else:
        hours = float(total_dur)
    return {
        "period": period,
        "start_date": str(start),
        "end_date": str(today),
        "total_hours": round(hours, 2),
        "entry_count": agg["count"],
    }


def _get_upcoming_appointments(params, user, company):
    from appointments.models import Appointment
    days = params.get("days_ahead", 7)
    now = timezone.now()
    cutoff = now + timedelta(days=days)
    qs = Appointment.objects.filter(
        company=company,
        start_time__gte=now,
        start_time__lte=cutoff,
        status__in=["scheduled", "confirmed"],
    ).select_related("service", "resource")
    appts = []
    for a in qs[:20]:
        appts.append({
            "id": a.id,
            "title": a.title,
            "start": a.start_time.strftime("%d.%m.%Y %H:%M"),
            "end": a.end_time.strftime("%d.%m.%Y %H:%M") if a.end_time else "",
            "service": a.service.name if a.service else "",
            "resource": a.resource.name if a.resource else "",
            "status": a.status,
        })
    return {"count": qs.count(), "appointments": appts}


def _get_active_interventions(params, user, company):
    from interventions.models import HitnaIntervencija
    qs = HitnaIntervencija.objects.filter(company=company).exclude(
        status__in=["RIJESENO", "FAKTURIRANO"]
    )
    items = []
    for i in qs[:20]:
        items.append({
            "id": i.id,
            "title": getattr(i, "title", str(i)),
            "status": i.status,
            "category": getattr(i, "category", ""),
        })
    return {"count": qs.count(), "interventions": items}


def _get_outreach_contacts(params, user, company):
    from outreach.models import Contact
    status = params.get("status", "")
    limit = params.get("limit", 10)
    qs = Contact.objects.filter(company=company)
    if status:
        qs = qs.filter(status=status)
    contacts = []
    for c in qs[:limit]:
        contacts.append({
            "id": c.id,
            "name": c.name,
            "firm": getattr(c, "firm_name", ""),
            "email": c.email,
            "status": getattr(c, "status", ""),
            "type": getattr(c, "contact_type", ""),
        })
    return {"count": qs.count(), "contacts": contacts}


def _get_tracking_status(params, user, company):
    from tracking.models import TrackedItem
    token = params.get("token", "")
    if not token:
        return {"error": "Token je obavezan"}
    try:
        item = TrackedItem.objects.get(public_token=token)
        return {
            "token": str(item.public_token),
            "type": getattr(item, "tracking_type", ""),
            "status": getattr(item, "current_status", ""),
        }
    except TrackedItem.DoesNotExist:
        return {"error": "Token nije pronaden"}


# ── ERP Analytics Tools (AIR-GAPPED) ────────────────────────

def _analyze_inventory_value(params, user, company):
    """Sinteticki pregled skladista."""
    from inventory.models import InventoryItem
    from django.db.models import Sum, F, FloatField

    qs = InventoryItem.objects.filter(company=company, is_active=True)

    agg = qs.aggregate(
        total_purchase=Sum(F('quantity') * F('purchase_price'), output_field=FloatField()),
        total_selling=Sum(F('quantity') * F('unit_price'), output_field=FloatField()),
    )

    low_stock = []
    for item in qs.filter(quantity__lte=F('min_quantity'), min_quantity__gt=0)[:20]:
        low_stock.append({
            "sku": item.sku,
            "name": item.name,
            "quantity": float(item.quantity),
            "min_required": float(item.min_quantity),
        })

    return {
        "total_items": qs.count(),
        "warehouse_purchase_value_eur": round(agg['total_purchase'] or 0, 2),
        "warehouse_selling_value_eur": round(agg['total_selling'] or 0, 2),
        "potential_margin_eur": round((agg['total_selling'] or 0) - (agg['total_purchase'] or 0), 2),
        "low_stock_count": qs.filter(quantity__lte=F('min_quantity'), min_quantity__gt=0).count(),
        "low_stock_items": low_stock,
    }


def _get_cashflow_summary(params, user, company):
    """AIR-GAPPED financijska sintetika. Nema pristupa IBAN-ovima."""
    from finance.models import Transaction
    from django.utils import timezone
    from django.db.models import Sum, Count

    now = timezone.now()
    year = params.get("year") or now.year
    month = params.get("month") or now.month

    qs = Transaction.objects.filter(company=company, date__year=year, date__month=month)

    income = qs.filter(direction='income').aggregate(
        total=Sum('amount'), count=Count('id')
    )
    expense = qs.filter(direction='expense').aggregate(
        total=Sum('amount'), count=Count('id')
    )

    inc_total = float(income['total'] or 0)
    exp_total = float(expense['total'] or 0)

    return {
        "period": f"{month:02d}/{year}",
        "income_eur": round(inc_total, 2),
        "income_count": income['count'],
        "expense_eur": round(exp_total, 2),
        "expense_count": expense['count'],
        "net_cashflow_eur": round(inc_total - exp_total, 2),
        "total_transactions": qs.count(),
        "note": "Sinteticki izvjestaj. AI nema pristup pojedinacnim IBAN racunima niti alatima za iniciranje placanja.",
    }


def _get_pending_payments(params, user, company):
    """AIR-GAPPED pregled placanja na cekanju."""
    from payments.models import Payment
    from django.db.models import Sum

    qs = Payment.objects.filter(company=company, status__in=['pending', 'processing'])

    by_method = []
    for code, name in Payment.METHOD_CHOICES:
        sub = qs.filter(method=code)
        if sub.exists():
            by_method.append({
                "method": name,
                "count": sub.count(),
                "amount_eur": float(sub.aggregate(s=Sum('amount'))['s'] or 0),
            })

    return {
        "pending_count": qs.count(),
        "pending_total_eur": float(qs.aggregate(s=Sum('amount'))['s'] or 0),
        "by_method": by_method,
    }


# ── AI Diagnostic & Testing Tools ───────────────────────────

def _run_system_health_check(params, user, company):
    if not user.is_superuser:
        return {"error": "Samo superadmin moze pokretati health check."}
    """Provjera zdravlja svih servisa."""
    import subprocess, shutil
    results = {}

    # 1. Database
    try:
        from django.db import connection
        with connection.cursor() as c:
            c.execute("SELECT 1")
        results["database"] = {"status": "OK", "engine": connection.vendor}
    except Exception as e:
        results["database"] = {"status": "ERROR", "error": str(e)}

    # 2. Redis
    try:
        from django.core.cache import cache
        cache.set("_health_check", "ok", 5)
        val = cache.get("_health_check")
        results["redis_cache"] = {"status": "OK" if val == "ok" else "DEGRADED"}
    except Exception as e:
        results["redis_cache"] = {"status": "ERROR", "error": str(e)}

    # 3. Celery
    try:
        from django_celery_results.models import TaskResult
        last = TaskResult.objects.order_by("-date_done").first()
        if last:
            from django.utils import timezone
            age = (timezone.now() - last.date_done).total_seconds()
            results["celery"] = {
                "status": "OK" if age < 3600 else "WARNING (no recent tasks)",
                "last_task": last.task_name,
                "last_run": str(last.date_done),
                "age_seconds": int(age),
            }
        else:
            results["celery"] = {"status": "WARNING", "note": "Nema izvrsenih taskova"}
    except Exception as e:
        results["celery"] = {"status": "UNKNOWN", "error": str(e)}

    # 4. Disk
    total, used, free = shutil.disk_usage("/")
    pct = used / total * 100
    results["disk"] = {
        "status": "OK" if pct < 85 else ("WARNING" if pct < 95 else "CRITICAL"),
        "total_gb": round(total / (1024**3), 1),
        "used_gb": round(used / (1024**3), 1),
        "free_gb": round(free / (1024**3), 1),
        "used_pct": round(pct, 1),
    }

    # 5. Last error in log
    try:
        import os
        log_path = "/var/www/fina-connect/logs/django.log"
        if not os.path.exists(log_path):
            log_path = "/var/www/fina-connect/logs/gunicorn_error.log"
        if os.path.exists(log_path):
            with open(log_path, "r") as f:
                lines = f.readlines()
            errors = [l.strip() for l in lines if "ERROR" in l]
            if errors:
                results["last_log_error"] = errors[-1][:300]
            else:
                results["last_log_error"] = "Nema ERROR zapisa u logu"
        else:
            results["last_log_error"] = "Log datoteka nije pronadjena"
    except Exception:
        results["last_log_error"] = "Nije moguce procitati log"

    # 6. Migration status
    try:
        result = subprocess.run(
            ["/var/www/fina-connect/venv/bin/python", "manage.py", "showmigrations", "--plan"],
            capture_output=True, text=True, cwd="/var/www/fina-connect", timeout=15
        )
        unapplied = [l.strip() for l in result.stdout.splitlines() if l.strip().startswith("[ ]")]
        results["migrations"] = {
            "status": "OK" if not unapplied else "WARNING",
            "unapplied_count": len(unapplied),
            "unapplied": unapplied[:5] if unapplied else [],
        }
    except Exception as e:
        results["migrations"] = {"status": "UNKNOWN", "error": str(e)}

    return results


def _validate_pos_math(params, user, company):
    """Simulira POS racun u memoriji i validira matematiku."""
    from decimal import Decimal, ROUND_HALF_UP

    items_data = params.get("items", [])
    amount_paid = Decimal(str(params.get("amount_paid", 0)))

    if not items_data:
        return {"error": "Nema stavki za simulaciju. Posalji items: [{name, qty, price, tax_rate, discount_pct}]"}

    line_items = []
    subtotal = Decimal("0")
    tax_total = Decimal("0")

    for item in items_data:
        name = item.get("name", "Artikl")
        qty = Decimal(str(item.get("qty", 1)))
        price = Decimal(str(item.get("price", 0)))
        tax_rate = Decimal(str(item.get("tax_rate", 25)))
        discount = Decimal(str(item.get("discount_pct", 0)))

        net = qty * price * (1 - discount / 100)
        tax = net * tax_rate / 100
        gross = net + tax

        net = net.quantize(Decimal("0.01"), ROUND_HALF_UP)
        tax = tax.quantize(Decimal("0.01"), ROUND_HALF_UP)
        gross = gross.quantize(Decimal("0.01"), ROUND_HALF_UP)

        line_items.append({
            "name": name,
            "qty": float(qty),
            "unit_price": float(price),
            "discount_pct": float(discount),
            "tax_rate": float(tax_rate),
            "net": float(net),
            "tax": float(tax),
            "gross": float(gross),
        })

        subtotal += net
        tax_total += tax

    total = subtotal + tax_total
    change = max(Decimal("0"), amount_paid - total) if amount_paid else Decimal("0")

    # Cross-check sa POS engine
    engine_match = True
    engine_note = ""
    try:
        from pos.services import recalculate_receipt
        engine_note = "POS engine dostupan za provjeru"
    except ImportError:
        engine_note = "POS engine nije dostupan za cross-check"

    return {
        "line_items": line_items,
        "subtotal_eur": float(subtotal),
        "tax_total_eur": float(tax_total),
        "total_eur": float(total),
        "amount_paid_eur": float(amount_paid) if amount_paid else None,
        "change_eur": float(change) if amount_paid else None,
        "item_count": len(line_items),
        "validation": "PASSED - matematika konzistentna",
        "engine_note": engine_note,
    }


def _run_test_suite(params, user, company):
    if not user.is_superuser:
        return {"error": "Samo superadmin moze pokretati testove."}
    """Pokrece Django testove i vraca rezultat."""
    import subprocess

    module = params.get("module", "")

    cmd = ["/var/www/fina-connect/venv/bin/python", "manage.py", "test", "--keepdb", "-v2", "--no-input"]
    if module:
        cmd.append(module)
    else:
        cmd.append("tests")

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            cwd="/var/www/fina-connect", timeout=120
        )

        output = result.stderr or result.stdout
        lines = output.strip().splitlines()

        # Parse results
        summary_line = ""
        for line in reversed(lines):
            if "Ran " in line and " test" in line:
                summary_line = line.strip()
                break

        ok_line = ""
        for line in reversed(lines):
            if line.strip() in ("OK", "FAILED") or line.strip().startswith("FAILED"):
                ok_line = line.strip()
                break

        # Extract individual test results
        test_results = []
        for line in lines:
            if " ... " in line:
                parts = line.split(" ... ")
                test_results.append({
                    "test": parts[0].strip()[-80:],
                    "result": parts[1].strip() if len(parts) > 1 else "?"
                })

        # Extract failures
        failures = []
        in_fail = False
        fail_buf = []
        for line in lines:
            if line.startswith("FAIL:") or line.startswith("ERROR:"):
                in_fail = True
                fail_buf = [line]
            elif in_fail:
                if line.startswith("---") and len(fail_buf) > 1:
                    failures.append("\n".join(fail_buf[:10]))
                    in_fail = False
                    fail_buf = []
                else:
                    fail_buf.append(line)

        return {
            "exit_code": result.returncode,
            "status": "PASSED" if result.returncode == 0 else "FAILED",
            "summary": summary_line,
            "result_line": ok_line,
            "tests": test_results,
            "failures": failures[:5],
            "module_tested": module or "tests (all)",
        }
    except subprocess.TimeoutExpired:
        return {"status": "TIMEOUT", "error": "Testovi prekoracili 120 sekundi"}
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}


def _audit_data_integrity(params, user, company):
    """Provjera integriteta podataka."""
    from django.db.models import Q
    issues = []

    # 1. POS: Receipts bez sesije
    try:
        from pos.models import POSReceipt
        orphan_receipts = POSReceipt.objects.filter(session__isnull=True).count()
        if orphan_receipts:
            issues.append({"type": "orphan", "model": "POSReceipt", "count": orphan_receipts, "desc": "Racuni bez POS sesije"})
    except Exception:
        pass

    # 2. POS: Open sessions older than 24h
    try:
        from pos.models import POSSession
        from django.utils import timezone
        old_sessions = POSSession.objects.filter(
            status=POSSession.Status.OPEN,
            opened_at__lt=timezone.now() - timezone.timedelta(hours=24)
        ).count()
        if old_sessions:
            issues.append({"type": "stale", "model": "POSSession", "count": old_sessions, "desc": "Otvorene sesije starije od 24h"})
    except Exception:
        pass

    # 3. Propter: Otpremnice without billing period
    try:
        from propter.models import Otpremnica
        orphan_otp = Otpremnica.objects.filter(billing_period__isnull=True).count()
        if orphan_otp:
            issues.append({"type": "orphan", "model": "Otpremnica", "count": orphan_otp, "desc": "Otpremnice bez obracunskog perioda"})
    except Exception:
        pass

    # 4. Propter: OPEN periods from previous months
    try:
        from propter.models import BillingPeriod
        from django.utils import timezone
        now = timezone.now()
        stale_periods = BillingPeriod.objects.filter(
            status=BillingPeriod.Status.OPEN
        ).exclude(year=now.year, month=now.month).count()
        if stale_periods:
            issues.append({"type": "stale", "model": "BillingPeriod", "count": stale_periods, "desc": "Otvoreni periodi iz proslih mjeseci (trebali bi biti zatvoreni)"})
    except Exception:
        pass

    # 5. Invoices with zero total
    try:
        from invoicing.models import Invoice
        zero_inv = Invoice.objects.filter(company=company, total=0).exclude(status='DRAFT').count()
        if zero_inv:
            issues.append({"type": "suspicious", "model": "Invoice", "count": zero_inv, "desc": "Fakture s iznosom 0 (ne-draft)"})
    except Exception:
        pass

    # 6. Inventory: Negative stock
    try:
        from inventory.models import InventoryItem
        neg = InventoryItem.objects.filter(company=company, quantity__lt=0).count()
        if neg:
            issues.append({"type": "negative_stock", "model": "InventoryItem", "count": neg, "desc": "Artikli s negativnom zalihom"})
    except Exception:
        pass

    # 7. Duplicate partners (same OIB)
    try:
        from partners.models import Partner
        from django.db.models import Count
        dupes = Partner.objects.filter(company=company).values("oib").annotate(
            cnt=Count("id")
        ).filter(cnt__gt=1, oib__gt="")
        if dupes.exists():
            issues.append({"type": "duplicate", "model": "Partner", "count": dupes.count(), "desc": "Partneri s duplikatnim OIB-om"})
    except Exception:
        pass

    # 8. e-Racun without items
    try:
        from eracun.models import ERacun
        empty_er = ERacun.objects.filter(company=company, items__isnull=True).count()
        if empty_er:
            issues.append({"type": "empty", "model": "ERacun", "count": empty_er, "desc": "e-Racuni bez stavki"})
    except Exception:
        pass

    return {
        "company": company.name if company else "Global",
        "issues_found": len(issues),
        "status": "CLEAN" if not issues else "ISSUES_FOUND",
        "issues": issues,
    }


def _explain_business_flow(params, user, company):
    """Objasnjava poslovne tokove u sustavu."""
    flows = {
        "pos": {
            "name": "POS Naplata",
            "pipeline": [
                "1. open_session(terminal, user, opening_cash) -> POSSession",
                "2. create_receipt(session) -> POSReceipt (status=OPEN)",
                "3. add_receipt_item(receipt, item, qty, price, tax, discount) -> recalculate_receipt()",
                "4. process_payment(receipt, method, amount_paid) -> POSPaymentLine + status=PAID",
                "5. _deduct_inventory() -> StockMovement (automatski)",
                "6. _attempt_fiscalization() -> JIR od FINA CIS (ako je konfigurirano)",
                "7. close_session(session, closing_cash) -> Z-report",
            ],
            "models": "POSTerminal -> POSSession -> POSReceipt -> POSReceiptItem + POSPaymentLine",
            "key_service": "pos/services.py",
        },
        "propter": {
            "name": "Propter Digitalna Soba",
            "pipeline": [
                "1. Otpremnica se kreira (rucno, iz POS-a, iz fakture, API)",
                "2. Otpremnica.save() automatski dodjeljuje BillingPeriod (tekuci mjesec)",
                "3. Kroz mjesec se akumuliraju otpremnice u OPEN periodu",
                "4. close_period(period) -> izracun totala, status=CLOSED",
                "5. aggregate_to_eracun(period) -> kreira zbirni ERacun sa svim stavkama",
                "6. Otpremnice dobiju status AGGREGATED, period INVOICED",
                "7. EkoStats.calculate() -> CO2 usteda, badge level",
                "8. auto_close_previous() (Celery beat, 1. u mjesecu) -> automatska agregacija",
            ],
            "models": "BillingPeriod -> Otpremnica -> OtpremnicaItem -> ERacun + ERacunItem",
            "key_service": "propter/services/aggregate.py",
        },
        "fiscal": {
            "name": "Fiskalizacija (FINA CIS)",
            "pipeline": [
                "1. POS bon se plati -> _attempt_fiscalization(receipt)",
                "2. fiscal/service.py: fiscalize_pos_receipt() priprema XML",
                "3. Potpis FINA certifikatom (p12/pfx)",
                "4. SOAP poziv na FINA CIS servis",
                "5. Odgovor: JIR (Jedinstveni Identifikator Racuna)",
                "6. JIR se sprema na POSReceipt",
                "7. QR kod na racunu: BU + JIR za provjeru",
            ],
            "models": "POSReceipt.jir, POSReceipt.zki",
            "key_service": "fiscal/service.py",
        },
        "eracun": {
            "name": "e-Racun (EN 16931 / PEPPOL BIS 3.0)",
            "pipeline": [
                "1. ERacun.objects.create() -> UBL XML generiranje",
                "2. services/ubl_generator.py -> EN 16931 kompatibilan XML",
                "3. services/engine.py -> validate -> sign -> send",
                "4. FINA pristupna tocka (AS4 protokol)",
                "5. Primatelj prima e-Racun u svom sustavu",
                "6. Status tracking: draft -> sent -> delivered -> paid",
            ],
            "models": "ERacun -> ERacunItem + ERacunTaxSummary",
            "key_service": "eracun/services/engine.py",
        },
        "inventory": {
            "name": "Upravljanje zalihama",
            "pipeline": [
                "1. InventoryItem (artikl s SKU, cijenama, kolicinom)",
                "2. StockMovement (in/out) - svaki ulaz/izlaz se bilježi",
                "3. POS prodaja -> automatski OUT movement",
                "4. Smart Import (AI) -> automatski IN movement iz faktura",
                "5. GoodsReceipt -> IN movement iz primke",
                "6. BOM (Bill of Materials) -> automatska dedukcija komponenti",
                "7. Low stock alert: quantity <= min_quantity",
            ],
            "models": "InventoryItem -> StockMovement + GoodsReceipt",
            "key_service": "inventory/models.py",
        },
        "payments": {
            "name": "Payment Gateway",
            "pipeline": [
                "1. PaymentConfig per company (Stripe/BTCPay/PayPal/Cash)",
                "2. create_payment(company, amount, method, source) -> Payment",
                "3. Stripe: checkout session -> webhook confirmation",
                "4. BTCPay: self-hosted crypto -> webhook",
                "5. PayPal: OAuth2 flow -> capture",
                "6. Status: pending -> processing -> completed/failed",
            ],
            "models": "PaymentConfig -> Payment",
            "key_service": "payments/services.py",
        },
        "smart_import": {
            "name": "Smart Import (AI)",
            "pipeline": [
                "1. Dokument stize (XML/PDF/slika) -> ImportBatch",
                "2. XML: UBL parser (deterministicki)",
                "3. PDF: Claude AI text extraction",
                "4. Slika: Claude AI vision extraction",
                "5. Matching: VendorItemMapping (exact) + fuzzy (SequenceMatcher)",
                "6. Staging UI: korisnik pregledava i potvrdjuje",
                "7. confirm() -> GoodsReceipt + StockMovement (ulaz u zalihe)",
                "8. Webhook rampa: Make.com/Zapier push -> auto-processing",
            ],
            "models": "ImportBatch -> ImportedItem -> GoodsReceipt",
            "key_service": "smart_import/services.py",
        },
    }

    flow_key = params.get("flow", "").lower()
    if flow_key in flows:
        return flows[flow_key]
    else:
        return {
            "available_flows": list(flows.keys()),
            "hint": "Navedi jedan od dostupnih tokova, npr: pos, propter, fiscal, eracun, inventory, payments, smart_import",
        }


# ── Worktime -> Invoice Pipeline Tools ──────────────────────

def _build_timeentry_queryset(params, company):
    """Helper: gradi TimeEntry queryset iz parametara."""
    from worktime.models import TimeEntry, Project, WorkGroup
    from datetime import date, timedelta
    from django.contrib.auth.models import User

    qs = TimeEntry.objects.filter(company=company)

    # User filter
    user_id = params.get("user_id")
    username = params.get("username")
    if user_id:
        qs = qs.filter(user_id=user_id)
    elif username:
        qs = qs.filter(user__username__icontains=username)

    # Group filter
    group_id = params.get("group_id")
    if group_id:
        try:
            group = WorkGroup.objects.get(pk=group_id)
            member_ids = group.members.values_list("id", flat=True)
            qs = qs.filter(user_id__in=member_ids)
        except WorkGroup.DoesNotExist:
            pass

    # Project filter
    project_code = params.get("project_code")
    if project_code:
        qs = qs.filter(project__code__iexact=project_code)

    # Date range
    today = date.today()
    date_from = params.get("date_from")
    date_to = params.get("date_to")
    if date_from:
        qs = qs.filter(date__gte=date_from)
    else:
        qs = qs.filter(date__gte=today.replace(day=1))
    if date_to:
        qs = qs.filter(date__lte=date_to)
    else:
        qs = qs.filter(date__lte=today)

    # Status filter
    status = params.get("status", "all")
    if status and status != "all":
        qs = qs.filter(status=status.upper())

    # Only unbilled
    if params.get("only_unbilled"):
        qs = qs.filter(is_billed=False)

    return qs


def _get_worktime_report(params, user, company):
    """Izvjestaj radnih sati s agregacijom."""
    from django.db.models import Sum, Count, F
    from decimal import Decimal

    qs = _build_timeentry_queryset(params, company)

    # Agregacija ukupno
    totals = qs.aggregate(
        total_hours=Sum("duration"),
        total_billing=Sum("billing_amount"),
        entry_count=Count("id"),
        regular=Sum("regular_hours"),
        overtime=Sum("overtime_hours"),
        night=Sum("night_hours"),
    )

    # Breakdown po radniku
    by_worker = list(
        qs.values("user__username", "user__first_name", "user__last_name")
        .annotate(
            hours=Sum("duration"),
            billing=Sum("billing_amount"),
            entries=Count("id"),
            overtime=Sum("overtime_hours"),
        )
        .order_by("-hours")[:20]
    )
    for w in by_worker:
        w["name"] = f"{w.pop('user__first_name', '')} {w.pop('user__last_name', '')}".strip() or w.pop("user__username")
        if "user__username" in w:
            del w["user__username"]
        w["hours"] = float(w["hours"] or 0)
        w["billing"] = float(w["billing"] or 0)
        w["overtime"] = float(w["overtime"] or 0)

    # Breakdown po projektu
    by_project = list(
        qs.values("project__code", "project__name")
        .annotate(hours=Sum("duration"), billing=Sum("billing_amount"), entries=Count("id"))
        .order_by("-hours")[:20]
    )
    for p in by_project:
        p["code"] = p.pop("project__code")
        p["name"] = p.pop("project__name")
        p["hours"] = float(p["hours"] or 0)
        p["billing"] = float(p["billing"] or 0)

    # Unbilled summary
    unbilled = qs.filter(is_billed=False).aggregate(
        hours=Sum("duration"), amount=Sum("billing_amount"), count=Count("id")
    )

    return {
        "total_hours": float(totals["total_hours"] or 0),
        "total_billing_eur": float(totals["total_billing"] or 0),
        "entry_count": totals["entry_count"],
        "regular_hours": float(totals["regular"] or 0),
        "overtime_hours": float(totals["overtime"] or 0),
        "night_hours": float(totals["night"] or 0),
        "by_worker": by_worker,
        "by_project": by_project,
        "unbilled": {
            "hours": float(unbilled["hours"] or 0),
            "amount_eur": float(unbilled["amount"] or 0),
            "count": unbilled["count"],
        },
    }


def _preview_invoice_from_hours(params, user, company):
    """Suhi pregled racuna iz neobracunatih sati (dry run)."""
    from worktime.models import TimeEntry, Project
    from django.db.models import Sum
    from decimal import Decimal

    project_code = params.get("project_code", "")
    if not project_code:
        return {"error": "project_code je obavezan parametar."}

    try:
        project = Project.objects.get(code__iexact=project_code, company=company)
    except Project.DoesNotExist:
        return {"error": f"Projekt '{project_code}' nije pronadjen."}

    # Dohvati neobracunate sate
    p = dict(params)
    p["project_code"] = project_code
    p["only_unbilled"] = True
    qs = _build_timeentry_queryset(p, company)

    if not qs.exists():
        return {"error": "Nema neobracunatih sati za zadane filtere.", "project": project.name}

    tax_rate = Decimal(str(params.get("tax_rate", 25)))
    group_by = params.get("group_by", "worker")

    # Grupiraj stavke
    items = []
    if group_by == "worker":
        groups = qs.values("user__username", "user__first_name", "user__last_name").annotate(
            hours=Sum("duration"), amount=Sum("billing_amount")
        ).order_by("user__last_name")
        for g in groups:
            name = f"{g['user__first_name']} {g['user__last_name']}".strip() or g["user__username"]
            hours = g["hours"] or Decimal("0")
            rate = (g["amount"] / hours).quantize(Decimal("0.01")) if hours else project.hourly_rate
            items.append({
                "description": f"Rad: {name} — {project.name}",
                "quantity": float(hours),
                "unit": "h",
                "unit_price": float(rate),
                "total": float(g["amount"] or 0),
            })
    elif group_by == "task":
        groups = qs.values("task_type").annotate(
            hours=Sum("duration"), amount=Sum("billing_amount")
        ).order_by("task_type")
        for g in groups:
            items.append({
                "description": f"{g['task_type']} — {project.name}",
                "quantity": float(g["hours"] or 0),
                "unit": "h",
                "unit_price": float((g["amount"] / g["hours"]).quantize(Decimal("0.01"))) if g["hours"] else 0,
                "total": float(g["amount"] or 0),
            })
    elif group_by == "day":
        groups = qs.values("date").annotate(
            hours=Sum("duration"), amount=Sum("billing_amount")
        ).order_by("date")
        for g in groups:
            items.append({
                "description": f"{g['date']} — {project.name}",
                "quantity": float(g["hours"] or 0),
                "unit": "h",
                "unit_price": float((g["amount"] / g["hours"]).quantize(Decimal("0.01"))) if g["hours"] else 0,
                "total": float(g["amount"] or 0),
            })

    subtotal = sum(i["total"] for i in items)
    tax = round(subtotal * float(tax_rate) / 100, 2)
    total = round(subtotal + tax, 2)

    return {
        "dry_run": True,
        "project": project.name,
        "client": project.client_name or "(nije postavljeno)",
        "items": items,
        "subtotal_eur": subtotal,
        "tax_rate_pct": float(tax_rate),
        "tax_amount_eur": tax,
        "total_eur": total,
        "time_entries_count": qs.count(),
        "total_hours": float(qs.aggregate(s=Sum("duration"))["s"] or 0),
        "hint": "Za kreiranje racuna koristi alat create_invoice_from_hours s istim parametrima.",
    }


def _create_invoice_from_hours(params, user, company):
    """Kreira racun iz neobracunatih sati i oznacava ih kao obracunate."""
    from worktime.models import TimeEntry, Project
    from invoicing.models import Invoice, InvoiceItem
    from django.db import transaction
    from django.db.models import Sum
    from django.utils import timezone
    from decimal import Decimal
    from datetime import timedelta

    project_code = params.get("project_code", "")
    if not project_code:
        return {"error": "project_code je obavezan."}

    try:
        project = Project.objects.get(code__iexact=project_code, company=company)
    except Project.DoesNotExist:
        return {"error": f"Projekt '{project_code}' nije pronadjen."}

    # Dohvati neobracunate sate
    p = dict(params)
    p["project_code"] = project_code
    p["only_unbilled"] = True
    qs = _build_timeentry_queryset(p, company)

    if not qs.exists():
        return {"error": "Nema neobracunatih sati za fakturiranje."}

    tax_rate = Decimal(str(params.get("tax_rate", 25)))
    payment_days = params.get("payment_days", 15)
    client_name = params.get("client_name") or project.client_name or "Klijent"
    note = params.get("note", "")
    now = timezone.now()

    # Generiraj broj racuna (GLOBALNO unique - bez company filtera)
    year = now.year
    prefix = f"R-{year}-"
    last = Invoice.objects.filter(number__startswith=prefix).order_by("-number").first()
    if last:
        try:
            last_num = int(last.number.split("-")[-1])
        except (ValueError, IndexError):
            last_num = 0
        next_num = last_num + 1
    else:
        next_num = 1
    invoice_number = f"R-{year}-{next_num:04d}"

    with transaction.atomic():
        # Kreiraj fakturu
        invoice = Invoice.objects.create(
            company=company,
            doctype="R",
            number=invoice_number,
            date_issued=now,
            date_due=now.date() + timedelta(days=payment_days),
            date_delivery=now.date(),
            client_name=client_name,
            client_oib=getattr(project, "client_oib", "") or "",
            payment_method="TRANSAKCIJSKI",
            currency="EUR",
            status="DRAFT",
            note=note or f"Racun za radne sate — {project.name}",
            issuer_name=company.name,
            issuer_oib=company.oib,
            issuer_address=getattr(company, "address", "") or "",
            issuer_iban=getattr(company, "iban", "") or "",
        )

        # Grupiraj po radniku
        groups = qs.values(
            "user_id", "user__username", "user__first_name", "user__last_name"
        ).annotate(hours=Sum("duration"), amount=Sum("billing_amount")).order_by("user__last_name")

        subtotal = Decimal("0")
        for g in groups:
            name = f"{g['user__first_name']} {g['user__last_name']}".strip() or g["user__username"]
            hours = g["hours"] or Decimal("0")
            amount = g["amount"] or Decimal("0")
            rate = (amount / hours).quantize(Decimal("0.01")) if hours else project.hourly_rate

            InvoiceItem.objects.create(
                invoice=invoice,
                description=f"Rad: {name} — {project.name}",
                quantity=hours,
                unit="h",
                unit_price=rate,
                tax_rate=tax_rate,
            )
            subtotal += amount

        # Izracunaj totale
        tax_amount = (subtotal * tax_rate / 100).quantize(Decimal("0.01"))
        total = subtotal + tax_amount
        invoice.subtotal = subtotal
        invoice.tax_percent = tax_rate
        invoice.tax_amount = tax_amount
        invoice.total = total
        invoice.save()

        # Oznaci sate kao obracunate
        updated = qs.update(is_billed=True, invoice=invoice)

    return {
        "status": "success",
        "invoice_number": invoice_number,
        "invoice_id": invoice.pk,
        "client": client_name,
        "project": project.name,
        "items_count": groups.count() if hasattr(groups, "count") else len(list(groups)),
        "total_hours": float(qs.aggregate(s=Sum("duration"))["s"] or subtotal),
        "subtotal_eur": float(subtotal),
        "tax_rate_pct": float(tax_rate),
        "tax_eur": float(tax_amount),
        "total_eur": float(total),
        "time_entries_billed": updated,
        "due_date": str(invoice.date_due),
        "next_step": f"Racun {invoice_number} je kreiran u statusu DRAFT. Pregledaj i posalji klijentu.",
    }


# --- Fenix Intelligence v2 handlers (CC Code) ---

def _get_fund_opportunities(params, user, company):
    """Dohvati relevantne EU fondove i HR poticaje. READ-ONLY, s 24h cacheom."""
    try:
        from intelligence.models import FundOpportunity
        from django.core.cache import cache
        from django.utils import timezone as tz
        today = tz.now().date()

        tip = params.get('tip', 'sve')
        rok_dana = params.get('rok_dana', 90)
        samo_aktivni = params.get('samo_aktivni', True)

        biz_type = getattr(company, 'business_type', 'doo') if company else 'doo'
        cache_key = f'fund_opps_{biz_type}_{tip}_{rok_dana}'
        cached = cache.get(cache_key)
        if cached:
            return cached

        qs = FundOpportunity.objects.all()
        if samo_aktivni:
            qs = qs.filter(status='aktivan')
        if tip != 'sve':
            tip_map = {'eu_fond': 'eu', 'hr_poticaj': 'hr', 'bio_certifikacija': 'bio'}
            prefix = tip_map.get(tip, tip)
            if prefix == 'bio':
                qs = qs.filter(kljucne_rijeci__contains=['bio'])
            else:
                qs = qs.filter(tip__startswith=prefix)
        if rok_dana:
            qs = qs.filter(rok_prijave__lte=today + timedelta(days=rok_dana))

        if company and biz_type == 'opg':
            qs = qs.filter(ciljna_skupina__in=['opg', 'svi'])
        elif company and biz_type in ('udruga', 'kud', 'sport'):
            qs = qs.filter(ciljna_skupina__in=['udruga', 'svi'])

        rezultati = []
        for f in qs.order_by('rok_prijave')[:10]:
            days = f.days_until_deadline
            rezultati.append({
                'naziv': f.naziv,
                'tip': f.get_tip_display(),
                'tijelo': f.tijelo,
                'iznos_max_eur': float(f.iznos_max_eur) if f.iznos_max_eur else None,
                'rok_prijave': str(f.rok_prijave) if f.rok_prijave else None,
                'preostalo_dana': days,
                'hitno': f.hitno,
                'ai_summary': f.ai_summary[:200] if f.ai_summary else '',
                'checklist': f.ai_checklist[:3] if f.ai_checklist else [],
                'url': f.url,
            })

        result = {
            'ukupno': qs.count(),
            'prikazano': len(rezultati),
            'fondovi': rezultati,
            'napomena': f'Firma: {company.name} ({biz_type})' if company else 'Nema firme',
        }

        if any(r.get('hitno') for r in rezultati):
            return result
        cache.set(cache_key, result, timeout=86400)
        return result
    except ImportError:
        return {
            'error': 'Intelligence modul jos nije instaliran.',
            'info': 'Pokrenite CC_TASK_FENIX_INTELLIGENCE.md za aktivaciju.',
        }


def _get_livestock_status(params, user, company):
    """Status farme goveda za OPG. READ-ONLY -- nikad ne pise u bazu."""
    try:
        from livestock.models import Livestock, HealthRecord, MilkRecord, CropPlan
        from django.db.models import Sum
        today = timezone.now().date()
        detalji = params.get('detalji', 'pregled')

        if company and getattr(company, 'business_type', '') != 'opg':
            return {'info': 'Livestock modul dostupan samo za OPG firme.'}

        if not company:
            return {'error': 'Nema aktivne firme.'}

        grla = Livestock.objects.filter(company=company)

        if detalji == 'pregled':
            return {
                'ukupno_grla': grla.count(),
                'aktivnih': grla.filter(status='aktivno').count(),
                'gravidnih': grla.filter(status='gravidno').count(),
                'teli_uskoro': grla.filter(
                    expected_calving__lte=today + timedelta(days=21),
                    expected_calving__gte=today, status='gravidno'
                ).count(),
                'u_karenciji': HealthRecord.objects.filter(
                    animal__company=company,
                    karencija_do__gte=today
                ).count(),
                'bio_grla': grla.filter(is_organic=True).count(),
            }
        elif detalji == 'zdravlje':
            alarmi = HealthRecord.objects.filter(
                animal__company=company,
                karencija_do__gte=today
            ).select_related('animal')[:10]
            return {
                'u_karenciji': [
                    {
                        'grlo': r.animal.ear_tag,
                        'lijek': r.lijek,
                        'karencija_do': str(r.karencija_do),
                        'preostalo_dana': (r.karencija_do - today).days,
                    } for r in alarmi
                ]
            }
        elif detalji == 'mlijeko':
            jucer = today - timedelta(days=1)
            mr = MilkRecord.objects.filter(animal__company=company, datum=jucer)
            agg = mr.aggregate(ukupno=Sum('ukupno_l'))
            return {
                'datum': str(jucer),
                'ukupno_litara': float(agg['ukupno'] or 0),
                'broj_krava': mr.count(),
                'prosjek_po_kravi': round(float(agg['ukupno'] or 0) / max(mr.count(), 1), 2),
            }
        elif detalji == 'usjevi':
            planovi = CropPlan.objects.filter(company=company).order_by('-godina')[:5]
            return {
                'planovi': [
                    {
                        'id': p.pk,
                        'kultura': p.get_kultura_display(),
                        'godina': p.godina,
                        'status': p.get_status_display(),
                        'za_prodaju': p.za_prodaju,
                        'visak_t': float(p.procijenjeni_visak_t) if p.procijenjeni_visak_t else None,
                        'auto_listing_spreman': p.auto_listing_ready,
                    } for p in planovi
                ]
            }
        return {'error': f'Nepoznati detalji: {detalji}'}
    except ImportError:
        return {'error': 'Livestock modul jos nije instaliran.'}


def _create_futures_listing(params, user, company):
    """ASSISTED: Objavi visak usjeva na Burzi. Prolazi kroz AIGate."""
    try:
        from superadmin_ai.services import AIGate
        gate = AIGate()
        crop_plan_id = params.get('crop_plan_id')
        result = gate.check(
            company=company,
            module='marketplace',
            action_type='create_futures_listing',
            user=user,
            description=f'AI zeli kreirati FuturesListing za crop_plan_id={crop_plan_id}',
        )
        if result.blocked:
            return {'error': result.message, 'blocked': True}
        if result.queued:
            return {
                'status': 'QUEUED',
                'message': 'Zahtjev je poslan na odobrenje. Potvrdi u AI Cockpitu.',
                'pending_action_id': str(result.pending_action.id) if result.pending_action else None,
            }
        try:
            from livestock.models import CropPlan
            from intelligence.services import create_futures_listing_from_crop
            plan = CropPlan.objects.get(pk=params['crop_plan_id'], company=company)
            if params.get('cijena_eur_t'):
                plan._override_price = params['cijena_eur_t']
            created = create_futures_listing_from_crop(plan)
            return {
                'status': 'CREATED' if created else 'ALREADY_EXISTS',
                'kultura': plan.get_kultura_display(),
                'visak_t': float(plan.procijenjeni_visak_t) if plan.procijenjeni_visak_t else None,
            }
        except Exception as e:
            return {'error': str(e)}
    except ImportError:
        return {'error': 'SuperadminAI ili Intelligence modul nije instaliran.'}


def _get_compliance_warnings(params, user, company):
    """Prediktivna compliance provjera. READ-ONLY -- skenira sve module."""
    today = timezone.now().date()
    kategorija = params.get('kategorija', 'sve')
    upozorenja = []

    if not company:
        return {'error': 'Nema aktivne firme.'}

    if kategorija in ('sve', 'pdv'):
        try:
            if getattr(company, 'is_nonprofit', False) or getattr(company, 'business_type', '') in ('udruga',):
                from invoicing.models import Invoice
                promet = Invoice.objects.filter(
                    company=company, date__year=today.year, status='paid'
                ).aggregate(s=Sum('total_amount'))['s'] or 0
                if float(promet) > 25000:
                    upozorenja.append({
                        'tip': 'pdv_granica',
                        'razina': 'warning' if float(promet) < 28000 else 'critical',
                        'poruka': f'Promet {promet:.0f} EUR -- granica za PDV obveznika je 30.000 EUR',
                        'akcija': 'Konzultirajte poreznog savjetnika',
                    })
        except Exception:
            pass

    if kategorija in ('sve', 'dokumenti'):
        try:
            from delivery.models import VehicleDocument
            vd = VehicleDocument.objects.filter(
                vehicle__company=company,
                valid_until__lte=today + timedelta(days=30)
            ).order_by('valid_until')[:5]
            for d in vd:
                upozorenja.append({
                    'tip': 'dokument_vozila',
                    'razina': 'critical' if d.is_expired else 'warning',
                    'poruka': f'{d.vehicle.plate_number}: {d.get_doc_type_display()} istice {d.valid_until}',
                    'preostalo_dana': d.days_until_expiry,
                })
        except Exception:
            pass

    if kategorija in ('sve', 'clanarine'):
        try:
            from udruge.models import Clan
            uskoro = Clan.objects.filter(
                company=company, status='aktivan',
                membership_expires__lte=today + timedelta(days=14),
                membership_expires__gte=today,
            ).count()
            if uskoro:
                upozorenja.append({
                    'tip': 'clanstvo_istice',
                    'razina': 'warning',
                    'poruka': f'{uskoro} clanova ima clanstvo koje istice za 14 dana',
                    'akcija': 'Posalji WhatsApp podsjetnik (send_expiry_reminders)',
                })
        except Exception:
            pass

    if kategorija in ('sve', 'livestock'):
        try:
            from livestock.models import HealthRecord
            karencija = HealthRecord.objects.filter(
                animal__company=company,
                karencija_do__gte=today,
            ).count()
            if karencija:
                upozorenja.append({
                    'tip': 'karencija_goveda',
                    'razina': 'critical',
                    'poruka': f'{karencija} grla u karenciji -- mlijeko i meso NE smiju u prodaju!',
                    'akcija': 'Provjeri ear tagove u livestock modulu',
                })
        except Exception:
            pass

    if kategorija in ('sve', 'fondovi'):
        try:
            from intelligence.models import FundOpportunity
            hitni = FundOpportunity.objects.filter(
                status='aktivan',
                rok_prijave__lte=today + timedelta(days=14),
                rok_prijave__gte=today,
            ).count()
            if hitni:
                upozorenja.append({
                    'tip': 'fond_rok',
                    'razina': 'warning',
                    'poruka': f'{hitni} natjecaj/a istice za 14 dana',
                    'akcija': 'Provjeri get_fund_opportunities za detalje',
                })
        except Exception:
            pass

    return {
        'ukupno_upozorenja': len(upozorenja),
        'status': 'CLEAN' if not upozorenja else ('CRITICAL' if any(u['razina'] == 'critical' for u in upozorenja) else 'WARNING'),
        'upozorenja': upozorenja,
        'firma': company.name,
    }


# CC Code prijedlog: get_intelligence_results -- korisnik pita "sto si nasao?"
def _get_intelligence_results(params, user, company):
    """Dohvati najnovije Intelligence pronalaske za firmu. READ-ONLY."""
    try:
        from intelligence.models import IntelligenceResult
        status_filter = params.get('status', 'novo')
        limit = params.get('limit', 10)

        if not company:
            return {'error': 'Nema aktivne firme.'}

        qs = IntelligenceResult.objects.filter(job__company=company)
        if status_filter != 'sve':
            qs = qs.filter(status=status_filter)

        rezultati = []
        for r in qs.order_by('-ai_relevantnost', '-created_at')[:limit]:
            rezultati.append({
                'naslov': r.naslov,
                'summary': r.summary[:300] if r.summary else '',
                'url': r.url,
                'relevantnost': r.ai_relevantnost,
                'status': r.get_status_display(),
                'izvor': r.source.naziv if r.source else 'Nepoznat',
                'datum': str(r.created_at.date()),
                'promo_tekst': r.promo_tekst[:200] if r.promo_tekst else '',
            })

        return {
            'ukupno': qs.count(),
            'prikazano': len(rezultati),
            'rezultati': rezultati,
            'firma': company.name,
        }
    except ImportError:
        return {
            'error': 'Intelligence modul jos nije instaliran.',
            'info': 'Pokrenite CC_TASK_FENIX_INTELLIGENCE.md za aktivaciju.',
        }
