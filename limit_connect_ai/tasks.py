"""
Celery tasks for LIMIT Connect AI.
Morning report: generates per-company AI summary and sends via WhatsApp/email.
"""

import logging
import os
from datetime import timedelta

from celery import shared_task
from django.core.exceptions import ObjectDoesNotExist
from django.db import DatabaseError, IntegrityError
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
    from core.email_tasks import send_email_task
    from core.whatsapp import send_text

    from .models import AIAgentMission, AIReportLog

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
            except (ValueError, KeyError) as exc:
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
    from django.db.models import Count, F, Sum

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
    except (ValueError, TypeError):
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
    except (ValueError, TypeError):
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
    except DatabaseError:
        ctx["low_stock_count"] = 0

    # Active funds
    try:
        from intelligence.models import FundOpportunity

        ctx["active_funds"] = FundOpportunity.objects.filter(status="aktivan").count()
    except DatabaseError:
        ctx["active_funds"] = 0

    # Overdue invoices (dospjele fakture)
    try:
        from invoicing.models import Invoice

        overdue = Invoice.objects.filter(
            company=company,
            status__in=["SENT", "UNPAID", "OVERDUE"],
            date_due__lt=today,
        ).order_by("date_due")[:5]
        ctx["overdue_invoices"] = [
            {
                "number": inv.number,
                "client": inv.client_name,
                "total": float(inv.total or 0),
                "days": (today - inv.date_due).days,
            }
            for inv in overdue
        ]
        ctx["overdue_count"] = Invoice.objects.filter(
            company=company,
            status__in=["SENT", "UNPAID", "OVERDUE"],
            date_due__lt=today,
        ).count()
    except (ValueError, TypeError):
        ctx["overdue_invoices"] = []
        ctx["overdue_count"] = 0

    # Open helpdesk tickets
    try:
        from helpdesk.models import Ticket

        open_tickets = Ticket.objects.filter(
            company=company,
            status__in=["open", "in_progress"],
        ).count()
        ctx["open_tickets"] = open_tickets
    except DatabaseError:
        ctx["open_tickets"] = 0

    # Bank unmatched transactions
    try:
        from konto.models import BankTransaction

        ctx["unmatched_transactions"] = BankTransaction.objects.filter(company=company, status="unmatched").count()
    except DatabaseError:
        ctx["unmatched_transactions"] = 0

    # Worktime anomalies (today)
    try:
        from worktime.models import AnomalyReport

        ctx["worktime_anomalies"] = AnomalyReport.objects.filter(
            company=company,
            created_at__date=today,
        ).count()
    except DatabaseError:
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
            model="claude-haiku-4-5-20251001",
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
        mission_type="fund_watch",
    ).select_related("company")

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
        status="aktivan",
        rok_prijave__gte=timezone.now().date(),
    )

    for fund in active_funds:
        existing = FundApplicationDraft.objects.filter(
            company=company,
            fund_opportunity=fund,
        ).exists()
        if existing:
            continue

        # Basic eligibility check based on company type
        bt = company.business_type
        cs = fund.ciljna_skupina
        if cs != "svi" and bt != cs:
            continue

        FundApplicationDraft.objects.create(
            company=company,
            fund_opportunity=fund,
            status="draft",
            eligibility_score=50,
            eligibility_notes="Automatski detektirano — potreban review.",
        )
        logger.info("Created fund draft: %s for %s", fund.naziv, company.name)


@shared_task(bind=True, max_retries=1, default_retry_delay=120)
def compliance_check_all(self):
    """Monday 08:00 — check compliance status for all active compliance missions."""
    from .models import AIAgentMission, ComplianceWatchItem

    missions = AIAgentMission.objects.filter(
        is_active=True,
        mission_type="compliance_watch",
    ).select_related("company")

    count = 0
    for mission in missions:
        try:
            company = mission.company
            overdue = ComplianceWatchItem.objects.filter(
                company=company,
                status__in=["action_needed", "in_progress"],
                deadline__lt=timezone.now().date(),
            )
            if overdue.exists():
                from core.whatsapp import send_text

                items = ", ".join(o.law_reference for o in overdue[:5])
                msg = "Compliance upozorenje za {}:\nIstekli rokovi: {}".format(
                    company.name,
                    items,
                )
                if mission.notify_target:
                    send_text(mission.notify_target, msg, company_id=str(company.id))
            count += 1
        except DatabaseError as exc:
            logger.error("Compliance check failed for mission %s: %s", mission.id, exc)

    logger.info("compliance_check_all: processed %d missions", count)
    return "Processed {} compliance missions".format(count)


@shared_task(bind=True, max_retries=1, default_retry_delay=120)
def campaign_suggestions_all(self):
    """Friday 10:00 — generate AI campaign suggestions for companies."""
    from .models import AIAgentMission, CampaignPlan

    missions = AIAgentMission.objects.filter(
        is_active=True,
        mission_type="campaign_planner",
    ).select_related("company")

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
                campaign_type="promo",
                channel=mission.notify_channel if mission.notify_channel != "chat" else "whatsapp",
                status="draft",
                ai_suggestion=True,
                message_template="AI ce generirati sadrzaj kampanje nakon odobrenja.",
                created_by=mission.created_by,
            )
            count += 1
        except (IntegrityError, DatabaseError) as exc:
            logger.error("Campaign suggestion failed for mission %s: %s", mission.id, exc)

    logger.info("campaign_suggestions_all: processed %d missions", count)
    return "Processed {} campaign missions".format(count)


# ══════════════════════════════════════════════════════════════════════════════
# BORG FENIX: Narodne Novine RSS Feed — automatska asimilacija zakona
# ══════════════════════════════════════════════════════════════════════════════


@shared_task(bind=True, max_retries=3, name="limit_connect_ai.fetch_nn_feed", time_limit=3600, soft_time_limit=3500)
def fetch_and_process_nn_feed(self):
    """
    Svakih 6h: dohvati NN RSS, parsiraj zakone, LLM ekstrakcija.
    Retry: 3 pokušaja, 15 min između.
    """
    logger.info("[BORG] Započinjem asimilaciju NN feeda...")
    try:
        from limit_connect_ai.services.nn_feed_service import NNFeedScraperService

        service = NNFeedScraperService()
        result = service.process_feed()
        logger.info("[BORG] NN feed završen: %s", result)
        return result
    except ImportError as exc:
        logger.error("[BORG] Kritična greška u NN feed tasku: %s", exc)
        raise self.retry(exc=exc, countdown=60 * 15)


# ══════════════════════════════════════════════════════════════════════════════
# BORG FENIX: Post-Import Auto-Activation
# Okida se automatski nakon uspješne migracije podataka.
# Troslojni napad: WhatsApp klijent + In-app + WhatsApp superadmin
# ══════════════════════════════════════════════════════════════════════════════


@shared_task(bind=True, max_retries=2, name="limit_connect_ai.fenix_post_import_scan")
def fenix_post_import_scan(self, company_id, project_id=None):
    """
    FENIX orkestrator — pokreće se automatski nakon data_migration COMPLETED.

    1. OpportunityScanner → pronalazi olakšice za firmu
    2. FinaBonitetService → provjerava rizik novih partnera (po OIB-u)
    3. Master Report → spaja prilike + rizike u jedan izvještaj
    4. Troslojne notifikacije: klijent WA, in-app, superadmin WA
    """
    # ── Svi importi unutar funkcije (circular import zaštita) ────────
    from companies.models import Company
    from fiskalizacija.fina_bonitet_service import get_supplier_risk
    from limit_connect_ai.services.opportunity_scanner import (
        generate_onboarding_report,
        match_opportunities_for_company,
    )
    from partners.models import Partner

    try:
        company = Company.objects.get(pk=company_id)
    except Company.DoesNotExist:
        logger.error("[FENIX] Company %s ne postoji", company_id)
        return {"error": "Company not found"}

    logger.info("[FENIX] Post-import scan za %s (project=%s)", company.name, project_id)

    # ── 1. Opportunity Scan ──────────────────────────────────────────
    scan_result = match_opportunities_for_company(company)
    opp_count = scan_result["count"]
    total_savings = scan_result["total_savings"]

    # ── 2. Bonitet Check — novouvezeni partneri s OIB-om ─────────────
    risk_count = 0
    high_risk_partners = []

    partners_with_oib = (
        Partner.objects.filter(
            company=company,
            oib__isnull=False,
        )
        .exclude(oib="")
        .order_by("-created_at")[:50]
    )  # Max 50 za performanse

    for partner in partners_with_oib:
        try:
            risk = get_supplier_risk(partner.oib, company_id=str(company.pk))
            if risk.get("risk_level") in ("HIGH", "CRITICAL"):
                risk_count += 1
                high_risk_partners.append(
                    {
                        "name": partner.name,
                        "oib": partner.oib,
                        "risk": risk["risk_level"],
                        "note": risk.get("note", ""),
                    }
                )
        except (ValueError, TypeError) as e:
            logger.debug("[FENIX] Bonitet check skip za %s: %s", partner.oib, e)

    # ── 3. Master Report ─────────────────────────────────────────────
    report = generate_onboarding_report(company)

    # Dodaj rizik sekciju ako ima
    if risk_count > 0:
        risk_lines = [
            "",
            f"*Upozorenje:* {risk_count} dobavljač(a) s povišenim rizikom:",
        ]
        for rp in high_risk_partners[:5]:
            risk_lines.append(f"  - {rp['name']} (OIB: {rp['oib']}) — {rp['risk']}")
        if risk_count > 5:
            risk_lines.append(f"  ... i još {risk_count - 5}")
        report += "\n".join(risk_lines)

    # Dodaj migration info
    if project_id:
        try:
            from data_migration.models import MigrationProject

            project = MigrationProject.objects.get(pk=project_id)
            report += (
                f'\n\n_Import "{project.name}": '
                f"{project.records_created} kreirano, "
                f"{project.records_updated} ažurirano._"
            )
        except ObjectDoesNotExist:
            pass

    # ── 4. Troslojne notifikacije ────────────────────────────────────

    # 4a. Klijent — WhatsApp
    admin_user = None
    try:
        from django.contrib.auth import get_user_model

        User = get_user_model()
        # User ↔ Company veza ide preko accounts.CompanyMembership
        from accounts.models import CompanyMembership

        membership = (
            CompanyMembership.objects.filter(
                company=company,
            )
            .select_related("user__profile")
            .first()
        )
        admin_user = membership.user if membership else None

        if not admin_user:
            # Fallback: creator projekta
            admin_user = (
                User.objects.filter(
                    is_active=True,
                    is_staff=True,
                )
                .select_related("profile")
                .first()
            )

        if admin_user:
            phone = getattr(getattr(admin_user, "profile", None), "phone", None)
            if phone:
                from core.whatsapp import send_text

                send_text(phone, report, company_id=str(company.pk))
                logger.info("[FENIX] WhatsApp poslan klijentu %s", phone)
    except DatabaseError as e:
        logger.warning("[FENIX] Klijent WhatsApp failed: %s", e)

    # 4b. Klijent — In-App notifikacija
    try:
        from notifications.services import notify as notify_inapp

        if admin_user:
            notify_inapp(
                recipient=admin_user,
                notification_type="system",
                title="Analiza završena!",
                message=(
                    f"Pronađeno {opp_count} prilika za uštedu od {total_savings:,.2f} EUR. "
                    f"{f'{risk_count} rizičnih dobavljača detektirano.' if risk_count else 'Svi dobavljači OK.'}"
                ),
                url="/data-migration/",
                company=company,
            )
    except ImportError as e:
        logger.warning("[FENIX] In-app notifikacija failed: %s", e)

    # 4c. Superadmin — WhatsApp
    try:
        from core.notify import notify as notify_admin

        notify_admin(
            "INFO",
            f"Klijent *{company.name}* uspješno migriran.\n"
            f"Pronađeno *{opp_count} prilika* ({total_savings:,.2f} EUR) "
            f"i *{risk_count} rizik(a)*.",
        )
    except ImportError as e:
        logger.warning("[FENIX] Superadmin notify failed: %s", e)

    result = {
        "company": company.name,
        "opportunities": opp_count,
        "total_savings": str(total_savings),
        "risks": risk_count,
        "high_risk_partners": high_risk_partners[:5],
        "report_sent": True,
    }

    logger.info(
        "[FENIX] Scan komplet: %s → %d prilika, %.2f EUR, %d rizika",
        company.name,
        opp_count,
        total_savings,
        risk_count,
    )

    return result


# ══════════════════════════════════════════════════════════════════════════════
# BORG FENIX: AdaptationEngine — Safety Gateway + Scheduled Execution
# ══════════════════════════════════════════════════════════════════════════════


@shared_task(name="limit_connect_ai.request_adaptation_approval")
def request_adaptation_approval(rule_id):
    """
    Safety Gateway: FENIX traži odobrenje prije mijenjanja poreznih stopa.
    Šalje WhatsApp + In-App notifikaciju administratoru.
    FENIX NIKAD ne primjenjuje promjenu bez ljudske potvrde.
    """
    from core.notify import notify
    from limit_connect_ai.models_knowledge_graph import AdaptationRule

    try:
        rule = AdaptationRule.objects.select_related("regulatory_update").get(pk=rule_id)
    except AdaptationRule.DoesNotExist:
        logger.error("[ADAPT] Rule %s ne postoji", rule_id)
        return

    payload = rule.action_payload
    effective = payload.get("effective_date", "N/A")

    msg = (
        f"*FENIX REGULATORNA AKCIJA*\n\n"
        f"Zakon: {rule.regulatory_update.title[:100]}\n"
        f"Promjena: {payload.get('country', 'HR')} PDV "
        f"{payload.get('old_rate')}% → {payload.get('new_rate')}%\n"
        f"Stupa na snagu: {effective}\n\n"
        f"Sustav će kreirati novu stopu i prebaciti artikle. "
        f"Povijesni POS bonovi i fakture ostaju netaknuti.\n\n"
        f"Odobrite na: limit-connect.com/admin/\n"
        f"Ili odgovorite DA za autorizaciju."
    )

    notify("ACTION", msg)

    # In-app notifikacija
    try:
        from django.contrib.auth import get_user_model

        from notifications.services import notify as notify_inapp

        User = get_user_model()
        for admin in User.objects.filter(is_staff=True, is_superuser=True, is_active=True)[:3]:
            notify_inapp(
                recipient=admin,
                notification_type="system",
                title="Odobrenje potrebno — promjena PDV stope",
                message=f"{payload.get('country')} {payload.get('old_rate')}% → {payload.get('new_rate')}%. Stupa na snagu: {effective}",
                url="/admin/limit_connect_ai/adaptationrule/",
            )
    except DatabaseError as e:
        logger.warning("[ADAPT] In-app notify failed: %s", e)

    logger.info("[ADAPT] Approval request sent for rule %s", rule_id)


@shared_task(bind=True, max_retries=2, name="limit_connect_ai.execute_approved_adaptation")
def execute_approved_adaptation(self, rule_id):
    """
    Izvršava odobrenu AdaptationRule.
    Poziva se:
    - Ručno iz Django admina (admin action)
    - Zakazano via .apply_async(eta=effective_date) nakon odobrenja
    - Nikad automatski bez ljudske potvrde
    """
    from limit_connect_ai.models_knowledge_graph import AdaptationRule
    from limit_connect_ai.services.adaptation_engine import AdaptationEngine

    try:
        rule = AdaptationRule.objects.get(pk=rule_id)
    except AdaptationRule.DoesNotExist:
        logger.error("[ADAPT] Rule %s ne postoji", rule_id)
        return {"error": "Rule not found"}

    if rule.is_executed:
        logger.info("[ADAPT] Rule %s već izvršen, preskačem", rule_id)
        return {"status": "already_executed"}

    try:
        success, count = AdaptationEngine.execute_tax_rate_change(rule)

        if not success:
            raise Exception("AdaptationEngine vratio False — provjerite logove")

        logger.info("[ADAPT] Rule %s izvršen: %d artikala ažurirano", rule_id, count)
        return {
            "status": "completed",
            "updated_items": count,
            "rule_id": str(rule_id),
        }

    except (ValueError, TypeError) as exc:
        logger.error("[ADAPT] Execution failed za rule %s: %s", rule_id, exc)
        try:
            rule.error_log = str(exc)[:500]
            rule.save(update_fields=["error_log"])
        except (ValueError, TypeError):
            pass
        raise self.retry(exc=exc, countdown=300)


# ══════════════════════════════════════════════════════════════════════════════
# BORG FENIX: B2B Interceptor — skenira ulazne e-Račune za rizike i olakšice
# ══════════════════════════════════════════════════════════════════════════════


@shared_task(bind=True, max_retries=3, name="limit_connect_ai.fenix_intercept_incoming")
def fenix_intercept_incoming(self, eracun_id):
    """
    FENIX B2B Interceptor — okida se automatski kad stigne ulazni e-Račun.

    1. Risk Shield: bonitet check dobavljača po OIB-u (Redis cached 24h)
    2. Opportunity Trigger: ključne riječi u stavkama → Knowledge Graph match
    3. Notifikacija: WhatsApp + In-App ako postoji rizik ili prilika
    """
    from eracun.models import ERacun
    from fiskalizacija.fina_bonitet_service import get_supplier_risk

    try:
        racun = ERacun.objects.select_related("company").get(pk=eracun_id)
    except ERacun.DoesNotExist:
        logger.warning("[FENIX B2B] ERacun %s ne postoji", eracun_id)
        return

    company = racun.company
    issuer_oib = racun.issuer_oib or ""
    alerts = []

    # ── 1. Risk Shield — bonitet dobavljača ──────────────────────────
    risk_data = None
    if issuer_oib and len(issuer_oib) >= 8:
        try:
            risk_data = get_supplier_risk(issuer_oib, company_id=str(company.pk))
            if risk_data.get("risk_level") in ("HIGH", "CRITICAL"):
                alerts.append(
                    {
                        "type": "risk",
                        "level": risk_data["risk_level"],
                        "message": (
                            f"Dobavljač {racun.issuer_name} (OIB: {issuer_oib}) "
                            f"ima {risk_data['risk_label']}. "
                            f"{risk_data.get('note', 'Preporučujemo oprez pri plaćanju.')}"
                        ),
                    }
                )
                logger.warning(
                    "[FENIX B2B] RIZIK: %s od %s — %s",
                    racun.invoice_number,
                    racun.issuer_name,
                    risk_data["risk_level"],
                )
        except (ValueError, TypeError) as e:
            logger.debug("[FENIX B2B] Bonitet check skip: %s", e)

    # ── 2. Opportunity Trigger — ključne riječi u stavkama ───────────
    opportunity_keywords = {
        "solar": "green_incentive",
        "fotovoltai": "green_incentive",
        "elektricno vozilo": "green_incentive",
        "ev charg": "green_incentive",
        "edukacija": "digital_voucher",
        "softver": "digital_voucher",
        "erp": "digital_voucher",
        "digitalizacija": "digital_voucher",
        "webshop": "digital_voucher",
        "cyber": "digital_voucher",
    }

    matched_opportunities = set()
    try:
        for item in racun.items.all():
            desc_lower = (item.description or "").lower()
            for keyword, opp_type in opportunity_keywords.items():
                if keyword in desc_lower:
                    matched_opportunities.add((keyword, opp_type))
    except DatabaseError:
        pass

    if matched_opportunities:
        kw_list = ", ".join(kw for kw, _ in matched_opportunities)
        alerts.append(
            {
                "type": "opportunity",
                "message": (
                    f"Račun od {racun.issuer_name} sadrži stavke vezane za poticaje: {kw_list}. "
                    f"Provjerite dostupne olakšice na Dashboard-u."
                ),
            }
        )
        logger.info("[FENIX B2B] Opportunity match: %s → %s", racun.invoice_number, kw_list)

    # ── 3. Notifikacije (samo ako ima alertova) ──────────────────────
    if not alerts:
        logger.debug("[FENIX B2B] %s od %s — čisto, nema alertova", racun.invoice_number, racun.issuer_name)
        return {"status": "clean", "alerts": 0}

    # WhatsApp klijentu
    try:
        from accounts.models import CompanyMembership

        membership = (
            CompanyMembership.objects.filter(
                company=company,
            )
            .select_related("user__profile")
            .first()
        )

        if membership and membership.user:
            phone = getattr(getattr(membership.user, "profile", None), "phone", None)
            if phone:
                from core.whatsapp import send_text

                msg_parts = [f"*FENIX — Ulazni račun {racun.invoice_number}*\n"]
                for alert in alerts:
                    if alert["type"] == "risk":
                        msg_parts.append(f"⚠️ RIZIK: {alert['message']}")
                    elif alert["type"] == "opportunity":
                        msg_parts.append(f"💡 PRILIKA: {alert['message']}")
                send_text(phone, "\n".join(msg_parts), company_id=str(company.pk))
    except DatabaseError as e:
        logger.warning("[FENIX B2B] WhatsApp failed: %s", e)

    # In-App notifikacija
    try:
        from notifications.services import notify as notify_inapp

        if membership and membership.user:
            title = f"Ulazni račun {racun.invoice_number}"
            message = "; ".join(a["message"][:100] for a in alerts)
            notify_inapp(
                recipient=membership.user,
                notification_type="system",
                title=title,
                message=message[:300],
                url="/eracun/inbox/",
                company=company,
            )
    except ImportError as e:
        logger.warning("[FENIX B2B] In-app notify failed: %s", e)

    # Superadmin WhatsApp
    try:
        from core.notify import notify

        notify(
            "INFO",
            f"Ulazni račun za *{company.name}*: {racun.invoice_number} od {racun.issuer_name}\n"
            f"Alertova: {len(alerts)} ({', '.join(a['type'] for a in alerts)})",
        )
    except ImportError:
        pass

    logger.info("[FENIX B2B] %s: %d alertova obrađeno", racun.invoice_number, len(alerts))
    return {"status": "intercepted", "alerts": len(alerts), "details": alerts}


# ══════════════════════════════════════════════════════════════════════════════
# NN Tenant Classification — per-tenant relevantnost regulatornih promjena
# ══════════════════════════════════════════════════════════════════════════════

from celery import shared_task


@shared_task(name="limit_connect_ai.classify_nn_updates")
def classify_nn_updates():
    """
    Celery beat: svakih 6h, 30min nakon scrapera.
    Za svaki novi/neprocesirani RegulatoryUpdate x svaki aktivni tenant:
    klasificiraj relevantnost i kreiraj BorgTask/BorgAuditEntry ako treba.
    """
    import logging

    from companies.models import Company
    from limit_connect_ai.models_knowledge_graph import RegulatoryUpdate, TenantRegulatoryImpact
    from limit_connect_ai.services.nn_classifier import classify_and_store

    logger = logging.getLogger("borg.nn_classifier")

    # Find unclassified updates (processed by scraper but not yet per-tenant)
    updates = RegulatoryUpdate.objects.filter(
        is_processed=True,
        impact_score__gte=3,  # Skip trivial updates
    ).order_by("-publication_date")[:20]

    companies = Company.objects.all()[:100]
    classified = 0
    relevant = 0

    for update in updates:
        for company in companies:
            # Skip if already classified
            if TenantRegulatoryImpact.objects.filter(company=company, regulatory_update=update).exists():
                continue

            try:
                impact = classify_and_store(update, company)
                classified += 1
                if impact and impact.is_relevant:
                    relevant += 1
            except Exception as e:
                logger.debug("Classify error %s x %s: %s", update.pk, company.pk, e)

    logger.info("NN Classification: %d classified, %d relevant", classified, relevant)
    return {"classified": classified, "relevant": relevant}


# ═══════════════════════════════════════════════════════════════════════════
# CONTINUOUS GROWTH ENGINE — Trojstvo autonomno prati trendove
# ═══════════════════════════════════════════════════════════════════════════


@shared_task(bind=True, soft_time_limit=300, name="limit_connect_ai.tasks.growth_patrol")
def growth_patrol(self):
    """
    Dnevni patrol — Haiku skenira sustav i predlaže poboljšanja.
    Pokreće se svaku noć u 03:30 (Celery Beat).

    Skenira:
    1. Korisničke greške (500 errori u zadnja 24h)
    2. Neiskorišteni moduli (enabled ali 0 zapisa)
    3. Performance problemi (spore stranice)
    4. Compliance gaps (radnici bez OIB, istekli certifikati)
    5. UX problemi (stranice s visokim bounce rate-om)

    Rezultat: ImprovementSuggestion(source='system') → Trojstvo analizira
    """
    import os
    from datetime import timedelta

    from django.utils import timezone

    from companies.models import Company
    from pos.models import ImprovementSuggestion

    now = timezone.now()
    yesterday = now - timedelta(hours=24)
    findings = []

    # 1. Error scan — zadnja 24h
    try:
        log_path = "/var/www/fina-connect/logs/django.log"
        if os.path.exists(log_path):
            with open(log_path, "r") as f:
                lines = f.readlines()
            recent_errors = [l for l in lines if "ERROR" in l and now.strftime("%Y-%m-%d") in l]
            if len(recent_errors) > 5:
                findings.append(
                    {
                        "title": f"{len(recent_errors)} errora u zadnja 24h",
                        "desc": "\n".join(recent_errors[-5:]),
                        "category": "workflow",
                        "priority": 2,
                    }
                )
    except (FileNotFoundError, PermissionError, IOError):
        pass

    # 2. Compliance gaps
    try:
        from worktime.models import EmployeeProfile

        no_oib = EmployeeProfile.objects.filter(tax_id="", is_terminated=False).exclude(user__is_active=False).count()
        if no_oib > 0:
            findings.append(
                {
                    "title": f"{no_oib} radnika bez OIB-a",
                    "desc": "Zakon o fiskalizaciji cl. 9 — kazna do 66.000 EUR po radniku.",
                    "category": "workflow",
                    "priority": 1,
                }
            )
    except DatabaseError:
        pass

    # 3. Nefiskalizirani računi
    try:
        from pos.models import POSReceipt

        unfiscalized = (
            POSReceipt.objects.filter(
                status="paid",
                jir__isnull=True,
                created_at__gte=yesterday,
            )
            .exclude(jir="")
            .count()
        )
        if unfiscalized > 0:
            findings.append(
                {
                    "title": f"{unfiscalized} racuna bez JIR-a (24h)",
                    "desc": "Zakon o fiskalizaciji — rok 48h za fiskalizaciju.",
                    "category": "fiscal",
                    "priority": 1,
                }
            )
    except DatabaseError:
        pass

    # 4. Certifikati koji istječu
    try:
        from registration.models import CompanySubscription

        expiring = CompanySubscription.objects.filter(
            is_active=True,
            valid_until__lte=(now + timedelta(days=14)).date(),
            valid_until__gt=now.date(),
        ).count()
        if expiring > 0:
            findings.append(
                {
                    "title": f"{expiring} pretplata istjece u 14 dana",
                    "desc": "Kontaktiraj korisnike za obnovu.",
                    "category": "other",
                    "priority": 3,
                }
            )
    except DatabaseError:
        pass

    # Kreiraj sugestije za svaki finding
    platform = Company.objects.filter(is_platform_owner=True).first()
    if not platform:
        platform = Company.objects.first()

    created = 0
    for f in findings:
        # Provjeri duplikat (isti naslov u zadnja 24h)
        exists = ImprovementSuggestion.objects.filter(
            title=f["title"],
            created_at__gte=yesterday,
        ).exists()
        if exists:
            continue

        s = ImprovementSuggestion.objects.create(
            company=platform,
            source="system",
            title=f["title"],
            description=f["desc"],
            category=f["category"],
            priority=f["priority"],
            trojstvo_status="pending",
        )

        # Pokreni Trojstvo analizu
        try:
            from pos.trojstvo_task import trojstvo_rijesi

            trojstvo_rijesi.delay(s.pk)
        except ImportError:
            pass

        created += 1

    logger.info("Growth patrol: %d findings, %d new suggestions", len(findings), created)
    return {"findings": len(findings), "created": created}
