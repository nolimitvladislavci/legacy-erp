"""
tax_wizard/tasks.py — Celery taskovi za Porezni Savjetnik

Taskovi:
  1. check_tax_deadlines — svaki dan 7:00, šalje notifikacije
  2. prefill_quarterly_data — 1. u kvartalu, osvježi DRAFT sesije
  3. cleanup_expired_sessions — svaki dan 3:30, briši stare DRAFT-ove
  4. generate_annual_deadlines — 1.1. u 00:30, generiraj rokove za novu godinu
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.db import DatabaseError, IntegrityError
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, soft_time_limit=120)
def check_tax_deadlines(self):
    """
    Dnevna provjera poreznih rokova — 30d/14d/3d/overdue notifikacije.

    Notifikacijski kanali:
      30d → email
      14d → WhatsApp
      3d  → email + WhatsApp + in-app
      overdue → alert računovođa + klijent
    """
    from tax_wizard.models import TaxDeadline

    timezone.now().date()
    deadlines = TaxDeadline.objects.filter(
        is_filed=False,
    ).select_related("company", "template")

    counts = {"30d": 0, "14d": 0, "3d": 0, "overdue": 0}

    for deadline in deadlines:
        days = deadline.days_remaining

        # 30 dana — email
        if 28 <= days <= 30 and not deadline.notified_30d:
            _send_deadline_notification(deadline, "30d")
            deadline.notified_30d = True
            deadline.save(update_fields=["notified_30d"])
            counts["30d"] += 1

        # 14 dana — WhatsApp
        elif 12 <= days <= 14 and not deadline.notified_14d:
            _send_deadline_notification(deadline, "14d")
            deadline.notified_14d = True
            deadline.save(update_fields=["notified_14d"])
            counts["14d"] += 1

        # 3 dana — HITNO (email + WhatsApp + in-app)
        elif 1 <= days <= 3 and not deadline.notified_3d:
            _send_deadline_notification(deadline, "3d")
            deadline.notified_3d = True
            deadline.priority = "critical"
            deadline.save(update_fields=["notified_3d", "priority"])
            counts["3d"] += 1

        # Propušten rok
        elif days < 0 and not deadline.notified_overdue:
            _send_deadline_notification(deadline, "overdue")
            deadline.notified_overdue = True
            deadline.priority = "critical"
            deadline.save(update_fields=["notified_overdue", "priority"])
            counts["overdue"] += 1

    logger.info(
        "check_tax_deadlines: 30d=%d, 14d=%d, 3d=%d, overdue=%d",
        counts["30d"],
        counts["14d"],
        counts["3d"],
        counts["overdue"],
    )
    return counts


def _send_deadline_notification(deadline, urgency_level):
    """Šalje notifikaciju ovisno o urgency razini."""
    company = deadline.company
    form_type = deadline.template.form_type
    days = deadline.days_remaining
    date_str = deadline.deadline_date.strftime("%d.%m.%Y")

    if urgency_level == "overdue":
        subject = f"⚠️ PROPUŠTEN ROK: {form_type} — {date_str}"
        message = (
            f"Rok za podnošenje {form_type} obrasca ({date_str}) je propušten. "
            f"Zakonska kazna: {deadline.penalty_min}-{deadline.penalty_max} EUR. "
            f"Hitno kontaktirajte svog računovođu."
        )
    elif urgency_level == "3d":
        subject = f"🔴 HITNO: {form_type} — rok za {days} dana ({date_str})"
        message = (
            f"Imate još {days} dana za podnošenje {form_type} obrasca. Rok: {date_str}. Kliknite za brzo ispunjavanje."
        )
    elif urgency_level == "14d":
        subject = f"📋 Podsjetnik: {form_type} — rok za {days} dana"
        message = f"Rok za {form_type}: {date_str} ({days} dana). Vaš obrazac je već dijelom popunjen iz sustava."
    else:  # 30d
        subject = f"📅 Porezni rok: {form_type} — {date_str}"
        message = (
            f"Rok za podnošenje {form_type} obrasca je {date_str} ({days} dana). Možete započeti ispunjavanje već sada."
        )

    # Email
    try:
        from django.conf import settings as django_settings
        from django.core.mail import send_mail

        admin_emails = []
        from django.contrib.auth.models import User

        admins = User.objects.filter(
            is_active=True,
            employee_profile__company=company,
        ).values_list("email", flat=True)
        admin_emails = [e for e in admins if e]

        if admin_emails:
            send_mail(
                subject=subject,
                message=message,
                from_email=django_settings.DEFAULT_FROM_EMAIL,
                recipient_list=admin_emails[:5],
                fail_silently=True,
            )
            logger.info("Tax deadline email sent to %s for %s", admin_emails[:5], company.name)
    except DatabaseError as e:
        logger.warning("Failed to send tax deadline email for %s: %s", company.name, e)

    # WhatsApp za 14d, 3d, overdue
    if urgency_level in ("14d", "3d", "overdue"):
        try:
            from core.whatsapp_tasks import send_whatsapp_message

            phone = getattr(company, "phone", "") or ""
            if phone:
                send_whatsapp_message.delay(phone, message)
                logger.info("Tax deadline WhatsApp sent to %s", company.name)
        except ImportError as e:
            logger.warning("Failed to send tax deadline WhatsApp for %s: %s", company.name, e)


@shared_task(bind=True, max_retries=1, soft_time_limit=300)
def prefill_quarterly_data(self):
    """
    Kvartalni osvježavač — 1. u kvartalu, osvježi sve DRAFT sesije.

    Korisno jer korisnik može otvoriti wizard u Q2, ali Q3 podaci
    stižu naknadno. Ovaj task ih automatski ažurira.
    """
    from tax_wizard.models import TaxWizardSession
    from tax_wizard.prefill_engine import PrefillEngine

    current_year = timezone.now().year
    drafts = TaxWizardSession.objects.filter(
        status="draft",
        tax_year__gte=current_year - 1,
    ).select_related("company", "template")

    updated = 0
    for session in drafts:
        try:
            engine = PrefillEngine(session.company, session.tax_year)
            breakdown = engine.aggregate()

            dict(session.form_data)
            session.form_data.update(breakdown.to_dict())
            session.form_data["_prefill_timestamp"] = timezone.now().isoformat()

            # Confidence refresh
            confidence = engine.get_confidence_scores(breakdown)
            session.form_data["_confidence"] = confidence

            session.save()
            updated += 1
        except (IntegrityError, DatabaseError) as e:
            logger.warning("Prefill refresh failed for session %s: %s", session.id, e)

    logger.info("prefill_quarterly_data: %d DRAFT sessions refreshed", updated)
    return {"updated": updated}


@shared_task(bind=True, soft_time_limit=60)
def cleanup_expired_sessions(self):
    """Briši DRAFT sesije starije od 90 dana."""
    from tax_wizard.models import TaxWizardSession

    cutoff = timezone.now() - timedelta(days=90)
    expired = TaxWizardSession.objects.filter(
        status="draft",
        updated_at__lt=cutoff,
    )
    count = expired.count()

    if count > 0:
        expired.delete()
        logger.info("cleanup_expired_sessions: deleted %d expired DRAFT sessions", count)
    else:
        logger.debug("cleanup_expired_sessions: no expired sessions")

    return {"deleted": count}


@shared_task(bind=True, soft_time_limit=120)
def generate_annual_deadlines(self):
    """
    1. siječnja — generiraj TaxDeadline za svaku aktivnu firmu.

    Za svaki TaxFormTemplate × Company → TaxDeadline.
    Preskače firme koje nemaju odgovarajući business_type.
    """
    from companies.models import Company
    from tax_wizard.models import TaxDeadline, TaxFormTemplate

    year = timezone.now().year
    templates = TaxFormTemplate.objects.filter(is_active=True)
    companies = Company.objects.filter(is_active=True)

    created = 0
    for template in templates:
        applicable_types = template.applicable_business_types
        for company in companies:
            # Preskoci ako firma ne odgovara tipu
            if applicable_types and hasattr(company, "business_type"):
                if company.business_type and company.business_type not in applicable_types:
                    continue

            # Provjeri postoji li već
            _, was_created = TaxDeadline.objects.get_or_create(
                company=company,
                template=template,
                tax_year=year,
                tax_month=None,
                defaults={
                    "deadline_date": _calculate_deadline(template, year),
                    "penalty_min": _get_penalty(template, "min"),
                    "penalty_max": _get_penalty(template, "max"),
                },
            )
            if was_created:
                created += 1

    logger.info("generate_annual_deadlines: %d deadlines created for %d", created, year)
    return {"year": year, "created": created}


def _calculate_deadline(template, year):
    """Izračunaj rok iz template pravila."""
    from datetime import date

    rule = template.filing_deadline_rule
    if not rule:
        return date(year + 1, 1, 31)  # default: 31.01. sljedeće godine

    month_map = {
        "jan": 1,
        "feb": 2,
        "mar": 3,
        "apr": 4,
        "may": 5,
        "jun": 6,
        "jul": 7,
        "aug": 8,
        "sep": 9,
        "oct": 10,
        "nov": 11,
        "dec": 12,
    }
    if "-" in rule:
        parts = rule.split("-")
        month_str, day_str = parts[0].lower(), parts[1]
        if month_str in month_map:
            return date(year + 1, month_map[month_str], int(day_str))

    return date(year + 1, 1, 31)


def _get_penalty(template, kind):
    """Kazne po tipu obrasca."""
    from decimal import Decimal

    penalties = {
        "PO-SD": {"min": Decimal("265"), "max": Decimal("2650")},
        "DOH": {"min": Decimal("265"), "max": Decimal("5300")},
        "PD": {"min": Decimal("530"), "max": Decimal("13270")},
        "PDV": {"min": Decimal("265"), "max": Decimal("5300")},
        "PDV-K": {"min": Decimal("265"), "max": Decimal("5300")},
        "JOPPD": {"min": Decimal("530"), "max": Decimal("6630")},
        "GFI-POD": {"min": Decimal("265"), "max": Decimal("2650")},
    }
    form_type = template.form_type
    return penalties.get(form_type, {}).get(kind, Decimal("0"))
