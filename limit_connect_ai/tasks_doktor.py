"""Claude Doktor -- Celery tasks. Per-tenant AI dijagnostika."""
import json
import logging
from datetime import date, timedelta

from celery import shared_task
from django.conf import settings
from django.db import IntegrityError, DatabaseError

logger = logging.getLogger("claude_doktor")
HAIKU_MODEL = "claude-haiku-4-5-20251001"


@shared_task(bind=True, max_retries=2, default_retry_delay=120)
def run_clinic_diagnostics_all(self):
    """Master: sve aktivne firme, preskoci vec done."""
    from companies.models import Company
    from .models_doktor import DiagnosisReport
    today = date.today()
    already_done = set(DiagnosisReport.objects.filter(
        report_date=today, status="done").values_list("company_id", flat=True))
    companies = Company.objects.exclude(id__in=already_done)
    count = 0
    for company in companies:
        try:
            run_clinic_diagnostics_single.delay(str(company.id))
            count += 1
        except (ValueError, TypeError) as exc:
            logger.error("Doktor dispatch greska za %s: %s", company.id, exc)
    logger.info("Claude Doktor: pokrenuto %d dijagnoza", count)
    return f"Dispatched {count} diagnostics"


@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def run_clinic_diagnostics_single(self, company_id):
    """Dijagnostika jedne firme: collect -> score -> haiku -> save -> notify."""
    from companies.models import Company
    from .models_doktor import DiagnosisReport
    today = date.today()
    company = Company.objects.get(id=company_id)
    report, created = DiagnosisReport.objects.get_or_create(
        company=company, report_date=today, defaults={"status": "pending"})
    if not created and report.status == "done":
        return "Already done"
    try:
        raw = _collect_data(company)
        report.raw_data = raw
        scores = _calculate_scores(raw)
        report.score_fiskalizacija = scores["fiskalizacija"]
        report.score_pdv = scores["pdv"]
        report.score_cashflow = scores["cashflow"]
        report.score_zaposlenici = scores["zaposlenici"]
        report.score_podaci = scores["podaci"]
        report.score_gdpr = scores["gdpr"]
        weights = dict(fiskalizacija=0.25, pdv=0.20, cashflow=0.25,
                       zaposlenici=0.15, podaci=0.10, gdpr=0.05)
        report.overall_score = int(sum(scores[k] * w for k, w in weights.items()))
        yesterday = DiagnosisReport.objects.filter(
            company=company, report_date=today - timedelta(days=1), status="done").first()
        if yesterday:
            report.score_delta = report.overall_score - yesterday.overall_score
        ai_result = _call_haiku(company, raw, scores, report.overall_score)
        report.ai_summary = ai_result.get("summary", "")
        report.recommendations = ai_result.get("recommendations", [])
        report.status = "done"
        report.save()
        _send_notification_if_needed(company, report, yesterday)
        logger.info("Doktor OK: %s -- %d/100", company, report.overall_score)
        return f"{company}: {report.overall_score}/100"
    except (ValueError, TypeError) as exc:
        report.status = "error"
        report.error_message = str(exc)[:500]
        report.save()
        logger.error("Doktor GRESKA za %s: %s", company, exc)
        raise self.retry(exc=exc)


def _collect_data(company):
    from invoicing.models import Invoice
    today = date.today()
    raw = {}
    qs = Invoice.objects.filter(company=company, synesis_id__isnull=True)
    overdue_30 = qs.filter(status="UNPAID", created_at__date__lte=today - timedelta(days=30))
    raw["overdue_30_count"] = overdue_30.count()
    from django.db.models import Sum
    raw["overdue_30_amount"] = float(overdue_30.aggregate(s=Sum('total'))['s'] or 0)
    overdue_90 = qs.filter(status="UNPAID", created_at__date__lte=today - timedelta(days=90))
    raw["overdue_90_count"] = overdue_90.count()
    raw["unfiscalized_count"] = qs.filter(status="SENT", fiscal_datetime__isnull=True).count()
    raw["old_drafts_count"] = qs.filter(
        status="DRAFT", created_at__date__lte=today - timedelta(days=7)).count()
    try:
        from fiskalizacija.models import FiscalConfig
        config = FiscalConfig.objects.filter(company=company).first()
        raw["cert_days_left"] = 365
        if config:
            cert_fields = [f.name for f in config._meta.get_fields()]
            for fn in ["cert_valid_until", "valid_until", "certificate_expires", "cert_expires"]:
                if fn in cert_fields:
                    cert_date = getattr(config, fn, None)
                    if cert_date:
                        raw["cert_days_left"] = (cert_date - today).days
                    break
        else:
            raw["cert_days_left"] = -1
    except DatabaseError:
        raw["cert_days_left"] = 365
    raw["is_vat_registered"] = getattr(company, "is_vat_registered", True)
    try:
        from seasonal.models import SeasonalContract
        raw["pending_hzmo_count"] = SeasonalContract.objects.filter(
            worker__company=company, hzmo_prijava_sent=False).count()
    except DatabaseError:
        raw["pending_hzmo_count"] = 0
    raw["missing_company_fields"] = [
        f for f in ["email", "phone", "oib"] if not getattr(company, f, None)]
    raw["company_name"] = str(company)
    raw["report_date"] = str(today)
    return raw


def _calculate_scores(raw):
    s = {}
    score = 100 - min(50, raw.get("unfiscalized_count", 0) * 10)
    cert = raw.get("cert_days_left", 365)
    if cert < 0: score -= 30
    elif cert < 30: score -= 20
    elif cert < 90: score -= 10
    s["fiskalizacija"] = max(0, score)
    s["pdv"] = 90 if not raw.get("is_vat_registered", True) else 100
    score = (100 - min(20, raw.get("overdue_30_count", 0) * 5)
             - min(45, raw.get("overdue_90_count", 0) * 15))
    amt = raw.get("overdue_30_amount", 0)
    if amt > 50000: score -= 20
    elif amt > 10000: score -= 10
    s["cashflow"] = max(0, score)
    s["zaposlenici"] = max(0, 100 - min(40, raw.get("pending_hzmo_count", 0) * 20))
    s["podaci"] = max(0, 100 - len(raw.get("missing_company_fields", [])) * 10
                        - min(20, raw.get("old_drafts_count", 0) * 5))
    s["gdpr"] = 95
    return s


def _call_haiku(company, raw, scores, overall_score):
    """
    Claude Doktor AI — Haiku + Opus Advisor Strategy.
    Haiku radi standardnu dijagnostiku (jeftino, brzo).
    Za kritične anomalije (fiscal, cert, cash flow) konzultira Opus (max 1x).
    """
    data = {
        "firma": raw.get("company_name"),
        "datum": raw.get("report_date"),
        "ukupna_ocjena": overall_score,
        "ocjene": scores,
        "neplacene_30d": raw.get("overdue_30_count", 0),
        "iznos_eur": raw.get("overdue_30_amount", 0),
        "neplacene_90d": raw.get("overdue_90_count", 0),
        "nefiskalizirano": raw.get("unfiscalized_count", 0),
        "hzmo_cekanje": raw.get("pending_hzmo_count", 0),
        "cert_dana": raw.get("cert_days_left", 365),
    }

    # Odredi treba li advisor (kritični problemi)
    has_critical = (
        raw.get("unfiscalized_count", 0) > 0 or
        raw.get("cert_days_left", 365) < 30 or
        raw.get("overdue_90_count", 0) > 5 or
        overall_score < 40
    )

    system = (
        "Ti si iskusni hrvatski racunovoda i poslovni savjetnik. "
        "Analiziraj zdravstveno stanje firme. "
    )
    if has_critical:
        system += (
            "Imas pristup Opus advisoru — konzultiraj ga za: "
            "zakonske rizike (fiskalizacija, certifikati, HZMO), "
            "kriticne financijske probleme (cash flow, 90+ dana dugovanje), "
            "i prijedloge za hitno djelovanje. "
        )

    prompt = (
        "Odgovori SAMO validnim JSON-om, bez komentara ili markdown formatiranja. "
        "Format: "
        '{"summary": "2-3 recenice dijagnoze na hrvatskom. Konkretno.", '
        '"recommendations": ['
        '{"priority": "red", "title": "max 10 rijeci", "detail": "max 20 rijeci"}'
        ']} '
        "Prioriteti: red=hitno, yellow=vazno, green=preporuka. "
        "Generiraj 3-5 preporuka. "
        "PODACI: " + json.dumps(data, ensure_ascii=False)
    )

    try:
        if has_critical:
            # Advisor Strategy — Haiku + Opus za kritične
            from core.anthropic_advisor import haiku_with_advisor
            text = haiku_with_advisor(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=800,
                max_uses=1,
                system=system,
            )
            logger.info('Claude Doktor: Advisor mode (critical=%s, score=%s)', has_critical, overall_score)
        else:
            # Samo Haiku — standardna dijagnostika
            import anthropic
            client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
            msg = client.messages.create(
                model=HAIKU_MODEL, max_tokens=800,
                system=system,
                messages=[{"role": "user", "content": prompt}])
            text = msg.content[0].text.strip()

        if "```" in text:
            parts = text.split("```")
            text = parts[1].lstrip("json").strip() if len(parts) > 1 else text
        return json.loads(text)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("Doktor AI greska: %s", exc)
        return _fallback(raw, scores, overall_score)


def _fallback(raw, scores, overall_score):
    recs = []
    n90 = raw.get("overdue_90_count", 0)
    if n90:
        recs.append({"priority": "red",
                     "title": f"Naplati {n90} faktura starijih od 90 dana",
                     "detail": "Rizik nenaplativosti. Pokreni opomene odmah."})
    n_fisc = raw.get("unfiscalized_count", 0)
    if n_fisc:
        recs.append({"priority": "red",
                     "title": f"{n_fisc} faktura bez fiskalizacije",
                     "detail": "Prekrsaj fiskalnih propisa. Fiskaliziraj odmah."})
    n_hzmo = raw.get("pending_hzmo_count", 0)
    if n_hzmo:
        recs.append({"priority": "yellow",
                     "title": f"HZMO prijave na cekanju: {n_hzmo}",
                     "detail": "Posalji M-1 prijave za sezonske radnike."})
    n30 = raw.get("overdue_30_count", 0)
    if n30:
        recs.append({"priority": "yellow",
                     "title": f"Neplaceno {n30} faktura",
                     "detail": "Prati naplatu ili posalji opomenu."})
    if overall_score >= 80:
        summary = "Firma je u dobrom stanju. Nema kriticnih problema."
    elif overall_score >= 60:
        summary = "Firma ima odredjenih problema koje treba rijesiti u kratkom roku."
    else:
        summary = "Kriticni problemi zahtijevaju hitnu akciju. Detaljno pregledaj preporuke."
    return {"summary": summary, "recommendations": recs}


def _send_notification_if_needed(company, report, yesterday):
    try:
        should_notify = (
            report.score_delta <= -10
            or len(report.red_recommendations) > 0
            or report.overall_score < 50
        )
        if not should_notify:
            return
        phone = getattr(settings, "MARIJA_PHONE", None)
        if not phone:
            return
        from core.whatsapp import send_text
        label = ("Dobro" if report.overall_score >= 80
                 else "Umjereno" if report.overall_score >= 60 else "KRITICNO")
        delta = ("+" if report.score_delta > 0 else "") + str(report.score_delta)
        msg = f"[Claude Doktor] {company}\nOcjena: {report.overall_score}/100 ({delta}) -- {label}\n"
        for rec in report.red_recommendations[:2]:
            msg += f"[HITNO] {rec['title']}\n"
        msg += f"limit-connect.com/doktor/{company.id}/"
        send_text(phone=phone, message=msg)
        report.notification_sent = True
        report.save(update_fields=["notification_sent"])
    except ImportError as exc:
        logger.warning("Doktor notifikacija greska: %s", exc)
