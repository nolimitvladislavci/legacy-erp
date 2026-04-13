"""
invoicing/tasks.py -- Dunning Engine
"""
import logging
from celery import shared_task
from django.utils import timezone
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)

DEFAULT_DUNNING_SEQUENCE = [
    {"step": 1, "days_overdue": 3,  "channel": "email",  "tone": "gentle", "cc_admin": False},
    {"step": 2, "days_overdue": 14, "channel": "both",   "tone": "firm",   "cc_admin": False},
    {"step": 3, "days_overdue": 30, "channel": "email",  "tone": "legal",  "cc_admin": True},
]

NL = chr(10)

def _get_dunning_rules(company):
    from .models import DunningRule
    rules = list(
        DunningRule.objects.filter(company=company, is_active=True)
        .order_by("step")
        .values("step", "days_overdue", "channel", "tone", "cc_admin")
    )
    return rules if rules else DEFAULT_DUNNING_SEQUENCE


def _already_sent_legacy(invoice, step):
    from .models import InvoiceEvent
    return InvoiceEvent.objects.filter(
        invoice=invoice,
        event_type__in=("sent_email", "sent_whatsapp"),
        metadata__dunning_step=step,
    ).exists()


def _already_sent(invoice, step):
    from .models import DunningHistory
    if DunningHistory.objects.filter(invoice=invoice, step=step, status="sent").exists():
        return True
    return _already_sent_legacy(invoice, step)


def _build_message(invoice, tone, is_hr):
    if is_hr:
        from .dunning_templates import get_template
        return get_template(tone, invoice, invoice.company)
    n = invoice.number
    name = invoice.client_name
    total = invoice.total
    cur = invoice.currency
    due = invoice.date_due
    iban = invoice.issuer_iban
    issuer = invoice.issuer_name
    subjects = {
        "gentle": f"Zahlungserinnerung: Rechnung {n}",
        "firm":   f"Zweite Mahnung: Rechnung {n}",
        "legal":  f"Letzte Mahnung: Rechnung {n} -- rechtliche Schritte",
    }
    bodies = {
        "gentle": f"Sehr geehrte/r {name},{NL}{NL}wir mochten Sie daran erinnern, dass Rechnung Nr. {n} uber {total} {cur} am {due} fallig war.{NL}{NL}Bitte uberweisen Sie den Betrag auf IBAN: {iban}{NL}{NL}Mit freundlichen Grussen,{NL}{issuer}",
        "firm": f"Sehr geehrte/r {name},{NL}{NL}trotz unserer ersten Erinnerung ist Rechnung {n} uber {total} {cur} noch nicht beglichen.{NL}{NL}Bitte zahlen Sie umgehend.{NL}{NL}{issuer}",
        "legal": f"Sehr geehrte/r {name},{NL}{NL}dies ist die letzte Mahnung fur Rechnung {n} uber {total} {cur}.{NL}Bei Nichtbegleichung innerhalb von 7 Tagen werden wir rechtliche Schritte einleiten.{NL}{NL}{issuer}",
    }
    return subjects.get(tone, subjects["gentle"]), bodies.get(tone, bodies["gentle"])


def _send_dunning_step(invoice, rule, company_admin_emails=None):
    from .models import InvoiceEvent, DunningHistory, DunningRule
    is_hr = getattr(invoice, "is_hr", True) or invoice.country == "HR"
    tone = rule["tone"]
    channel = rule["channel"]
    step = rule["step"]
    company = invoice.company
    subject, body = _build_message(invoice, tone, is_hr)
    result = {"email_sent": False, "wa_sent": False, "error": None}
    dunning_rule_obj = DunningRule.objects.filter(
        company=company, step=step, is_active=True
    ).first()

    if channel in ("email", "both") and invoice.client_email:
        recipient_list = [invoice.client_email]
        cc_list = []
        if rule.get("cc_admin") and company_admin_emails:
            cc_list = company_admin_emails
        try:
            send_mail(
                subject=subject, message=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=recipient_list, fail_silently=False,
            )
            result["email_sent"] = True
            DunningHistory.objects.create(
                company=company, invoice=invoice, dunning_rule=dunning_rule_obj,
                step=step, channel_used="email", status="sent",
                email_subject=subject, email_body=body,
                recipient_email=", ".join(recipient_list),
            )
            InvoiceEvent.objects.create(
                invoice=invoice, event_type="sent_email",
                title=f"Opomena korak {step}: {subject[:80]}",
                detail=body[:500],
                metadata={"dunning_step": step, "tone": tone, "recipients": recipient_list},
            )
            if cc_list:
                try:
                    send_mail(
                        subject=f"[CC] {subject}",
                        message=f"Opomena poslana klijentu {invoice.client_name}:{NL}{NL}{body}",
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=cc_list, fail_silently=True,
                    )
                except Exception:
                    pass
        except Exception as e:
            result["error"] = str(e)
            DunningHistory.objects.create(
                company=company, invoice=invoice, dunning_rule=dunning_rule_obj,
                step=step, channel_used="email", status="failed",
                error_message=str(e)[:500], email_subject=subject,
                email_body=body, recipient_email=invoice.client_email,
            )
            logger.error("Dunning email error invoice %s: %s", invoice.number, e)

    if channel in ("whatsapp", "both"):
        phone = ""
        try:
            from partners.models import Partner
            partner = Partner.objects.filter(company=invoice.company, oib=invoice.client_oib).first()
            if partner:
                phone = getattr(partner, "contact_phone", "") or getattr(partner, "phone", "")
        except Exception:
            pass
        try:
            from core.whatsapp import send_text as wa_send, is_gateway_healthy
            if phone and is_gateway_healthy():
                wa_text = f"{subject}{NL}{NL}{body[:300]}"
                wa_result = wa_send(phone, wa_text)
                if wa_result["success"]:
                    result["wa_sent"] = True
                    DunningHistory.objects.create(
                        company=company, invoice=invoice, dunning_rule=dunning_rule_obj,
                        step=step, channel_used="whatsapp", status="sent",
                        email_subject=subject, email_body=wa_text[:500],
                        recipient_email=phone,
                    )
                    InvoiceEvent.objects.create(
                        invoice=invoice, event_type="sent_whatsapp",
                        title=f"WhatsApp opomena korak {step}",
                        detail=wa_text[:300],
                        metadata={"dunning_step": step, "tone": tone, "phone": phone},
                    )
                else:
                    logger.warning("WA dunning failed for %s: %s", invoice.number, wa_result.get("error"))
        except ImportError:
            logger.info("WhatsApp module not available, skipping for %s", invoice.number)

    return result


@shared_task
def check_overdue_invoices():
    from invoicing.models import Invoice
    from accounts.models import UserProfile
    today = timezone.now().date()
    Invoice.objects.filter(status__in=["SENT", "UNPAID"], date_due__lt=today).update(status="OVERDUE")
    overdue_qs = Invoice.objects.filter(status="OVERDUE", date_due__isnull=False, company__isnull=False).select_related("company")
    sent_count = 0
    errors = 0
    companies_cache = {}
    for invoice in overdue_qs:
        days_late = (today - invoice.date_due).days
        company = invoice.company
        if company.pk not in companies_cache:
            rules = _get_dunning_rules(company)
            admin_emails = list(
                UserProfile.objects.filter(
                    company=company, user__is_active=True,
                    user__groups__name="company_admin",
                ).values_list("user__email", flat=True)
            )
            companies_cache[company.pk] = {"rules": rules, "admin_emails": admin_emails}
        rules = companies_cache[company.pk]["rules"]
        admin_emails = companies_cache[company.pk]["admin_emails"]
        for rule in sorted(rules, key=lambda r: r["step"]):
            if days_late >= rule["days_overdue"] and not _already_sent(invoice, rule["step"]):
                result = _send_dunning_step(invoice, rule, admin_emails)
                if result["email_sent"] or result["wa_sent"]:
                    sent_count += 1
                if result.get("error"):
                    errors += 1
                break
    logger.info("check_overdue_invoices: sent=%d errors=%d total_overdue=%d", sent_count, errors, overdue_qs.count())
    return {"sent": sent_count, "errors": errors}


@shared_task
def run_dunning_cycle():
    """Celery beat task -- radnim danima u 08:00. Full dunning cycle."""
    from invoicing.models import Invoice, DunningHistory
    from .models import DunningRule
    from accounts.models import UserProfile
    from companies.models import Company
    today = timezone.now().date()
    summary = {"overdue_marked": 0, "reminders_sent": 0, "errors": 0, "invoices_processed": 0, "companies_processed": 0}
    marked = Invoice.objects.filter(status__in=["SENT", "UNPAID"], date_due__lt=today).update(status="OVERDUE")
    summary["overdue_marked"] = marked
    companies_with_overdue = set(
        Invoice.objects.filter(status="OVERDUE", date_due__isnull=False, company__isnull=False).values_list("company_id", flat=True)
    )
    for company_id in companies_with_overdue:
        try:
            company = Company.objects.get(pk=company_id)
        except Company.DoesNotExist:
            continue
        summary["companies_processed"] += 1
        rules = _get_dunning_rules(company)
        admin_emails = list(
            UserProfile.objects.filter(
                company=company, user__is_active=True, user__groups__name="company_admin",
            ).values_list("user__email", flat=True)
        )
        overdue_invoices = Invoice.objects.filter(
            company=company, status="OVERDUE", date_due__isnull=False,
        ).select_related("company")
        for invoice in overdue_invoices:
            summary["invoices_processed"] += 1
            days_late = (today - invoice.date_due).days
            applicable_rule = None
            for rule in sorted(rules, key=lambda r: r["days_overdue"], reverse=True):
                if days_late >= rule["days_overdue"] and not _already_sent(invoice, rule["step"]):
                    applicable_rule = rule
                    break
            if applicable_rule is None:
                continue
            result = _send_dunning_step(invoice, applicable_rule, admin_emails)
            if result["email_sent"] or result["wa_sent"]:
                summary["reminders_sent"] += 1
            if result.get("error"):
                summary["errors"] += 1
    logger.info("run_dunning_cycle: summary=%s", summary)
    return summary
