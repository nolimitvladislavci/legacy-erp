import json
import logging

from celery import shared_task
from django.db import DatabaseError, IntegrityError

logger = logging.getLogger(__name__)


@shared_task(bind=True, soft_time_limit=300)
def arhiva_ai_monitor(self):
    """
    AI agent koji svaki sat analizira arhivu za:
    1. Nelogičnosti (duplicati, sumnjivi iznosi, missing data)
    2. Cross-firma anomalije (managed firme)
    3. Nedostajući dokumenti (očekivani periodicitet)
    """
    from datetime import timedelta

    from django.db.models import Avg, Count, StdDev
    from django.utils import timezone

    from companies.models import Company
    from documents.models import ArhivaEntry
    from core.local_fallback import ocr_image, ocr_pdf, parse_invoice_text, suggest_konto

    alerts = []
    now = timezone.now()
    last_hour = now - timedelta(hours=1)

    # ── 1. Duplicati u zadnjem satu ──
    duplicates = (
        ArhivaEntry.objects.unscoped()
        .filter(archived_at__gte=last_hour)
        .values("company_id", "doc_number", "amount")
        .annotate(cnt=Count("id"))
        .filter(cnt__gt=1)
    )
    if duplicates.exists():
        alerts.append(
            {
                "type": "duplicate",
                "severity": "high",
                "message": f"{duplicates.count()} duplikata pronađeno u zadnjem satu",
                "data": list(duplicates.values())[:5],
            }
        )

    # ── 2. Sumnjivi iznosi (3σ anomalija) ──
    stats = (
        ArhivaEntry.objects.unscoped()
        .filter(
            amount__gt=0,
            archived_at__gte=now - timedelta(days=30),
        )
        .aggregate(avg=Avg("amount"), std=StdDev("amount"))
    )

    if stats["avg"] and stats["std"]:
        threshold = stats["avg"] + (3 * stats["std"])
        anomalies = ArhivaEntry.objects.unscoped().filter(
            archived_at__gte=last_hour,
            amount__gt=threshold,
        )
        if anomalies.exists():
            alerts.append(
                {
                    "type": "amount_anomaly",
                    "severity": "medium",
                    "message": f"{anomalies.count()} zapisa s neuobičajeno visokim iznosom (>{float(threshold):.2f})",
                    "data": list(anomalies.values("id", "doc_number", "amount", "company__name"))[:3],
                }
            )

    # ── 3. Cross-firma dual-access pattern ──
    dual_companies = Company.objects.filter(
        managing_partners__isnull=False,
        memberships__isnull=False,
    ).distinct()
    for company in dual_companies[:5]:
        partners = company.managing_partners.filter(valid_until__isnull=True)
        if partners.count() > 1:
            alerts.append(
                {
                    "type": "dual_access",
                    "severity": "info",
                    "message": f"{company.name} dostupna kod {partners.count()} partnera istovremeno",
                    "data": {
                        "company": company.name,
                        "partners": list(partners.values_list("partner_company__name", flat=True)),
                    },
                }
            )

    if not alerts:
        return {"alerts_count": 0, "timestamp": now.isoformat()}

    # ── 4. AI analiza ako ima alerta ──
    try:
        import anthropic

        client = anthropic.Anthropic()
        summary = json.dumps(alerts, ensure_ascii=False, indent=2, default=str)
        response = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=500,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Analiziraj ove anomalije u sustavu arhiviranja dokumenata i daj kratku ocjenu rizika "
                        "(1-3 rečenice). Odgovori na hrvatskom, budi koncizan. Navedi samo što je hitno.\n\n" + summary
                    ),
                }
            ],
        )
        ai_summary = response.content[0].text
    except (TypeError, ValueError) as e:
        ai_summary = f"AI analiza nedostupna: {e}"
        logger.warning("arhiva_ai_monitor: AI analiza failed: %s", e)

    # ── 5. Notifikacija superadminima + company adminima ──
    try:
        from django.contrib.auth import get_user_model

        from notifications.services import notify

        User = get_user_model()

        # Superadmini — vide sve anomalije
        for admin in User.objects.filter(is_superuser=True, is_active=True):
            notify(
                recipient=admin,
                notification_type="system",
                title="AI Arhiva Monitor — Anomalije",
                message=ai_summary,
                url="/hr/documents/arhiva/",
            )

        # Company admini — vide anomalije za svoju firmu
        affected_company_ids = set()
        for alert in alerts:
            data = alert.get("data", {})
            if isinstance(data, list):
                for d in data:
                    if isinstance(d, dict) and d.get("company_id"):
                        affected_company_ids.add(d["company_id"])
            elif isinstance(data, dict) and data.get("company_id"):
                affected_company_ids.add(data["company_id"])

        if affected_company_ids:
            from accounts.models import CompanyMembership

            memberships = CompanyMembership.objects.filter(
                company_id__in=affected_company_ids,
                role__in=["owner", "admin", "company_admin"],
                is_active=True,
                user__is_active=True,
                user__is_superuser=False,
            ).select_related("user", "company")
            for m in memberships:
                notify(
                    recipient=m.user,
                    notification_type="system",
                    title="Arhiva — Uočene anomalije",
                    message=ai_summary,
                    url="/hr/documents/arhiva/",
                    company=m.company,
                )

    except DatabaseError as e:
        logger.warning("arhiva_ai_monitor: notifikacija failed: %s", e)

    # ── 6. AIActionLog ──
    try:
        from superadmin_ai.models import AIActionLog

        AIActionLog.objects.create(
            company=None,
            module="arhiva_monitor",
            action_type="anomaly_detection",
            access_level=3,
            outcome="executed",
            details={"alerts": alerts, "ai_summary": ai_summary},
        )
    except (IntegrityError, DatabaseError) as e:
        logger.warning("arhiva_ai_monitor: AIActionLog failed: %s", e)

    return {"alerts_count": len(alerts), "timestamp": now.isoformat()}


@shared_task(bind=True, soft_time_limit=60)
def arhiva_morning_brief(self):
    """
    Svaki dan u 06:00 — salje brief o stanju arhive svim superadminima.
    Claude Haiku generira personalizirani summary.
    """
    import os
    from datetime import timedelta

    from django.db.models import Sum
    from django.utils import timezone

    from documents.models import ArhivaEntry

    now = timezone.now()
    yesterday = now - timedelta(days=1)

    # Stats
    pending = (
        ArhivaEntry.objects.filter(is_booked=False).exclude(ai_proposal__isnull=True).exclude(ai_proposal={}).count()
    )
    total = ArhivaEntry.objects.count()
    new_24h = ArhivaEntry.objects.filter(archived_at__gte=yesterday).count()
    booked_24h = ArhivaEntry.objects.filter(is_booked=True, archived_at__gte=yesterday).count()
    total_amount = ArhivaEntry.objects.filter(doc_date__year=now.year).aggregate(t=Sum("amount"))["t"] or 0

    # AI brief
    brief_text = (
        f"Jutarnji arhiva brief ({now.strftime('%d.%m.%Y')}):\n"
        f"- {pending} dokumenata ceka knjizenje (AI prijedlog spreman)\n"
        f"- {new_24h} novih dokumenata u zadnjih 24h\n"
        f"- {booked_24h} proknjizenih u zadnjih 24h\n"
        f"- Ukupno: {total} dokumenata, {float(total_amount):,.2f} EUR (godina)\n"
    )

    try:
        import anthropic

        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if api_key:
            client = anthropic.Anthropic(api_key=api_key)
            response = client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=300,
                messages=[
                    {
                        "role": "user",
                        "content": f"Ti si AI asistent za racunovodstvo. Napravi kratki jutarnji brief (3-4 recenice, HR jezik, formalan ton) na temelju ovih podataka:\n{brief_text}\nAko ima pending dokumenata, naglasi to kao prioritet.",
                    }
                ],
            )
            brief_text = response.content[0].text
    except (IntegrityError, DatabaseError) as e:
        logger.warning("AI brief generation failed: %s", e)

    # Notifikacija
    try:
        from django.contrib.auth import get_user_model

        from notifications.services import notify_bulk

        User = get_user_model()
        admins = list(User.objects.filter(is_superuser=True, is_active=True))
        if admins:
            notify_bulk(admins, "info", "Jutarnji arhiva brief", brief_text, "/hr/documents/ai-inbox/")
            logger.info("Morning brief sent to %d admins", len(admins))
    except DatabaseError as e:
        logger.warning("Morning brief notification failed: %s", e)

    return {"pending": pending, "new_24h": new_24h, "brief_sent": True}


@shared_task(bind=True, soft_time_limit=600)
def generate_revizija_zip(self, company_id, date_from, date_to, user_email):
    """Async ZIP generacija za velike revizorske pakete. Salje email kad zavrsi."""
    import csv
    import io
    import os
    import zipfile
    from datetime import datetime

    from django.conf import settings as _s
    from django.db.models import Sum

    from companies.models import Company
    from documents.models import ArhivaEntry

    company = Company.objects.get(pk=company_id)
    entries = ArhivaEntry.objects.filter(
        company=company,
        doc_date__gte=date_from,
        doc_date__lte=date_to,
    ).order_by("doc_date", "archive_number")

    export_dir = os.path.join(_s.MEDIA_ROOT, "arhiva", "exports", str(company_id))
    os.makedirs(export_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_filename = f"Revizija_{company.oib or company_id}_{ts}.zip"
    zip_filepath = os.path.join(export_dir, zip_filename)

    with zipfile.ZipFile(zip_filepath, "w", zipfile.ZIP_DEFLATED) as zf:
        # CSV index
        csv_buf = io.StringIO()
        writer = csv.writer(csv_buf, delimiter=";")
        writer.writerow(
            ["Arhivski broj", "Vrsta", "Broj dokumenta", "Partner", "Iznos", "Valuta", "Datum", "ZKI", "JIR", "PDF"]
        )
        for e in entries:
            writer.writerow(
                [
                    e.archive_number,
                    e.source_type,
                    e.doc_number,
                    e.partner_name,
                    str(e.amount),
                    e.currency,
                    e.doc_date.strftime("%d.%m.%Y") if e.doc_date else "",
                    e.zki or "",
                    e.jir or "",
                    "DA" if e.has_pdf else "NE",
                ]
            )
        zf.writestr("INDEX.csv", csv_buf.getvalue())

        # URA
        ura = entries.filter(source_type__in=["invoice_in", "eracun", "purchase"])
        if ura.exists():
            buf = io.StringIO()
            w = csv.writer(buf, delimiter=";")
            w.writerow(["R.br.", "Datum", "Broj", "Dobavljac", "Osnovica", "PDV 25%", "PDV 13%", "PDV 5%", "Ukupno"])
            for i, e in enumerate(ura, 1):
                total = float(e.amount or 0)
                pdv25 = total - total / 1.25
                w.writerow(
                    [
                        i,
                        e.doc_date,
                        e.doc_number,
                        e.partner_name,
                        f"{total - pdv25:.2f}",
                        f"{pdv25:.2f}",
                        "0.00",
                        "0.00",
                        f"{total:.2f}",
                    ]
                )
            zf.writestr("KNJIGA_URA.csv", buf.getvalue())

        # IRA
        ira = entries.filter(source_type="invoice_out")
        if ira.exists():
            buf = io.StringIO()
            w = csv.writer(buf, delimiter=";")
            w.writerow(["R.br.", "Datum", "Broj", "Kupac", "Osnovica", "PDV 25%", "PDV 13%", "PDV 5%", "Ukupno"])
            for i, e in enumerate(ira, 1):
                total = float(e.amount or 0)
                pdv25 = total - total / 1.25
                w.writerow(
                    [
                        i,
                        e.doc_date,
                        e.doc_number,
                        e.partner_name,
                        f"{total - pdv25:.2f}",
                        f"{pdv25:.2f}",
                        "0.00",
                        "0.00",
                        f"{total:.2f}",
                    ]
                )
            zf.writestr("KNJIGA_IRA.csv", buf.getvalue())

        # PDFs
        pdf_count = 0
        for e in entries.filter(has_pdf=True, file_path__isnull=False).exclude(file_path=""):
            full = os.path.join(_s.MEDIA_ROOT, e.file_path)
            if os.path.isfile(full):
                zf.write(full, f"PDF/{e.source_type}/{e.archive_number}.pdf")
                pdf_count += 1

        # README
        total_in = float(ura.aggregate(t=Sum("amount"))["t"] or 0)
        total_out = float(ira.aggregate(t=Sum("amount"))["t"] or 0)
        zf.writestr(
            "README.txt",
            f"REVIZORSKI PAKET\n{company.name} (OIB: {company.oib})\n"
            f"Period: {date_from} — {date_to}\n\n"
            f"Dokumenti: {entries.count()}\nURA: {ura.count()} ({total_in:,.2f} EUR)\n"
            f"IRA: {ira.count()} ({total_out:,.2f} EUR)\nPDF: {pdf_count}\n\n"
            f"LIMIT Connect ERP — {datetime.now().strftime('%d.%m.%Y %H:%M')}",
        )

    # Email s linkom
    try:
        from django.core.mail import EmailMessage as _EM

        file_size_mb = os.path.getsize(zip_filepath) / (1024 * 1024)

        if file_size_mb < 20:
            # Manji od 20MB — posalji kao attachment
            em = _EM(
                subject=f"Revizorski paket — {company.name}",
                body=f"U prilogu je revizorski paket za {company.name}.\nPeriod: {date_from} — {date_to}\n\nLIMIT Connect ERP",
                to=[user_email],
            )
            with open(zip_filepath, "rb") as zf:
                em.attach(zip_filename, zf.read(), "application/zip")
            em.send()
        else:
            # Veci — samo obavijest (file ostaje na serveru)
            em = _EM(
                subject=f"Revizorski paket spreman — {company.name}",
                body=f"Revizorski paket ({file_size_mb:.1f} MB) je generiran.\nKontaktirajte admina za preuzimanje.\n\nLIMIT Connect ERP",
                to=[user_email],
            )
            em.send()
    except (FileNotFoundError, PermissionError, IOError) as mail_err:
        logger.warning("Revizija email: %s", mail_err)

    return {"zip": zip_filepath, "entries": entries.count(), "pdfs": pdf_count}


@shared_task(bind=True, soft_time_limit=120)
def generate_ai_proposal(self, entry_id):
    """
    Za dani ArhivaEntry — pročitaj dokument, pošalji AI-u, spremi prijedlog knjiženja.
    Poziva se async nakon svakog uploada ili email importa.
    """
    import base64
    import os
    import re

    import anthropic
    from django.conf import settings as _s

    from documents.models import ArhivaEntry

    try:
        entry = ArhivaEntry.objects.get(pk=entry_id)
    except ArhivaEntry.DoesNotExist:
        return {"error": "Entry not found"}

    if entry.ai_proposal:
        return {"skipped": "already has proposal"}

    # Update status: processing
    entry.ai_status = "processing"
    entry.ai_status_message = "AI čita dokument..."
    entry.save(update_fields=["ai_status", "ai_status_message"])

    # Čitaj datoteku
    file_bytes = None
    content_type = None
    if entry.file_path:
        full_path = os.path.join(_s.MEDIA_ROOT, entry.file_path)
        if os.path.isfile(full_path):
            with open(full_path, "rb") as f:
                file_bytes = f.read()
            ext = os.path.splitext(full_path)[1].lower()
            content_type = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".webp": "image/webp",
                ".pdf": "application/pdf",
            }.get(ext, "image/jpeg")

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {"error": "No API key"}

    client = anthropic.Anthropic(api_key=api_key)

    # Pripremi prompt
    doc_info = (
        f"Tip: {entry.get_source_type_display()}\n"
        f"Broj: {entry.doc_number}\n"
        f"Partner: {entry.partner_name}\n"
        f"Iznos: {entry.amount} {entry.currency}\n"
        f"Datum: {entry.doc_date}\n"
    )

    messages_content = []
    if file_bytes and content_type and content_type.startswith("image"):
        messages_content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": content_type,
                    "data": base64.b64encode(file_bytes).decode(),
                },
            }
        )

    messages_content.append(
        {
            "type": "text",
            "text": (
                f"Ti si računovođa u Hrvatskoj. Analiziraj ovaj dokument i predloži knjiženje.\n\n"
                f"Podaci iz sustava:\n{doc_info}\n\n"
                f"Odgovori ISKLJUČIVO u JSON formatu bez ikakvih komentara:\n"
                '{"debit": [{"account": "1200", "description": "Opis", "amount": 100.00}], '
                '"credit": [{"account": "2200", "description": "Opis", "amount": 100.00}], '
                '"confidence": "high", "note": "Kratka napomena na HR"}\n\n'
                f"Koristi hrvatske kontne planove. Za ulazni račun: D:1300/K:2200. "
                f"Za izlazni račun: D:1200/K:7500. Za troškove: D:4xxx/K:2200."
            ),
        }
    )

    _ai_ok = False
    try:
        response = client.messages.create(
            model="claude-3-5-haiku-20241022", max_tokens=400, messages=[{"role": "user", "content": messages_content}]
        )
        raw = response.content[0].text.strip()

        # Parse JSON
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            proposal = json.loads(match.group())
        else:
            proposal = {"note": raw, "confidence": "low"}

        # Spremi
        entry.ai_proposal = proposal
        entry.ai_status = "done"
        entry.ai_status_message = "AI analiza završena — prijedlog knjiženja spreman"
        entry.save(update_fields=["ai_proposal", "ai_status", "ai_status_message"])

        # Notifikacija kompanijskom adminu
        try:
            from accounts.models import CompanyMembership
            from notifications.services import notify

            admins = CompanyMembership.objects.filter(
                company=entry.company,
                role__in=["owner", "admin", "company_admin"],
                is_active=True,
                user__is_active=True,
            ).select_related("user")
            for m in admins:
                notify(
                    recipient=m.user,
                    notification_type="info",
                    title="Novi dokument spreman za knjiženje",
                    message=f"{entry.doc_number} — {entry.partner_name} — {entry.amount} {entry.currency}",
                    url="/hr/documents/ai-inbox/",
                    company=entry.company,
                )
        except DatabaseError as notif_err:
            logger.warning("generate_ai_proposal: notify failed: %s", notif_err)

        return {"entry_id": entry_id, "confidence": proposal.get("confidence", "unknown")}

    except Exception as e:
        logger.error("generate_ai_proposal failed for entry %s: %s", entry_id, e)
        try:
        logger.warning("AI API greska za entry %s: %s - fallback na lokalni", entry_id, e)
        # LOCAL FALLBACK
        _ocr_text = ""
        if file_bytes:
            from core.local_fallback import ocr_image, ocr_pdf, parse_invoice_text, suggest_konto
            _fr = ocr_pdf(file_bytes) if content_type == "application/pdf" else ocr_image(file_bytes)
            _ocr_text = _fr.text if _fr.success else ""
        _parsed = parse_invoice_text(_ocr_text) if _ocr_text else {}
        _konto = suggest_konto(_ocr_text or str(entry.partner_name or ""))
        _iznos = float(entry.amount or 0) or _parsed.get("iznos", 0)
        proposal = {
            "debit":  [{"account": _konto["konto"], "description": _konto["opis"], "amount": _iznos}],
            "credit": [{"account": "2200", "description": "Obveze prema dobavljacima", "amount": _iznos}],
            "confidence": "low",
            "note": "[LOKALNI FALLBACK] AI nedostupan. " + (_ocr_text[:150] if _ocr_text else "OCR N/A"),
            "fallback": True,
        }
        entry.ai_proposal = proposal
        entry.ai_status = "done"
        entry.ai_status_message = "Lokalna analiza (AI nedostupan) — provjeri rucno"
        entry.save(update_fields=["ai_proposal", "ai_status", "ai_status_message"])
        return {"entry_id": entry_id, "confidence": "low", "fallback": True}
        # Originalni error handling (nedostizno ako fallback prode):
            entry.ai_status = "error"
            entry.ai_status_message = f"AI greška: {str(e)[:150]}"
            entry.save(update_fields=["ai_status", "ai_status_message"])
        except (ValueError, TypeError):
            pass
        return {"error": str(e)}


@shared_task(bind=True, soft_time_limit=1800)
def backfill_ai_proposals(self):
    """
    Masovni backfill — generiraj ai_proposal za sve dokumente koji ga nemaju.
    Pokreni jednom ručno: from documents.tasks import backfill_ai_proposals; backfill_ai_proposals.delay()
    """
    from documents.models import ArhivaEntry

    qs = (
        ArhivaEntry.objects.filter(ai_proposal__isnull=True)
        .exclude(source_type="pos_receipt")
        .order_by("-archived_at")[:500]
    )

    count = 0
    for entry in qs:
        generate_ai_proposal.delay(entry.pk)
        count += 1

    logger.info("backfill_ai_proposals: queued %d tasks", count)
    return {"queued": count}


@shared_task(bind=True, soft_time_limit=120)
def send_ai_inbox_summary_email(self, company_id=None):
    """
    Salje email sazetak AI Inboxa.
    Ako je company_id=None — salje svim kompanijama koje imaju pending dokumente.
    Moze se trigirati rucno ili automatski (svaki radni dan u 08:00).
    """
    from django.core.mail import EmailMultiAlternatives
    from django.db.models import Sum
    from django.utils import timezone

    from accounts.models import CompanyMembership
    from companies.models import Company
    from documents.models import ArhivaEntry

    now = timezone.now()

    if company_id:
        companies = Company.objects.filter(pk=company_id)
    else:
        companies = Company.objects.filter(
            arhivaentry__is_booked=False,
            arhivaentry__ai_proposal__isnull=False,
        ).distinct()

    sent = 0
    for company in companies:
        pending = (
            ArhivaEntry.objects.filter(company=company, is_booked=False)
            .exclude(ai_proposal__isnull=True)
            .exclude(ai_proposal={})
        )

        count = pending.count()
        if count == 0:
            continue

        total_amount = pending.aggregate(t=Sum("amount"))["t"] or 0

        rows = ""
        for e in pending[:10]:
            proposal = e.ai_proposal or {}
            debit = proposal.get("debit", [{}])[0] if proposal.get("debit") else {}
            credit = proposal.get("credit", [{}])[0] if proposal.get("credit") else {}
            confidence = proposal.get("confidence", "?")
            conf_color = "#16a34a" if confidence == "high" else "#d97706" if confidence == "medium" else "#dc2626"

            rows += (
                '<tr style="border-bottom:1px solid #e5e7eb">'
                '<td style="padding:8px;font-size:13px">%s</td>'
                '<td style="padding:8px;font-size:13px">%s</td>'
                '<td style="padding:8px;font-size:13px;text-align:right;font-weight:600">%.2f %s</td>'
                '<td style="padding:8px;font-size:12px;color:#6b7280">D:%s / K:%s</td>'
                '<td style="padding:8px;text-align:center">'
                '<span style="background:%s22;color:%s;border-radius:4px;padding:2px 8px;font-size:11px;font-weight:600">%s</span>'
                "</td></tr>"
            ) % (
                e.doc_number or "—",
                e.partner_name or "—",
                float(e.amount),
                e.currency,
                debit.get("account", "?"),
                credit.get("account", "?"),
                conf_color,
                conf_color,
                (confidence or "?").upper(),
            )

        more_text = "... i jos %d dokumenata" % (count - 10) if count > 10 else ""

        html = (
            '<!DOCTYPE html><html><body style="font-family:Arial,sans-serif;background:#f9fafb;margin:0;padding:20px">'
            '<div style="max-width:680px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.1)">'
            '<div style="background:linear-gradient(135deg,#0f172a,#1e293b);padding:24px 32px">'
            '<div style="color:#c9a84c;font-size:20px;font-weight:700;margin-bottom:4px">AI Inbox &mdash; %s</div>'
            '<div style="color:#94a3b8;font-size:14px">%s &mdash; Dnevni pregled</div></div>'
            '<div style="padding:24px 32px">'
            '<div style="display:flex;gap:24px;margin-bottom:24px">'
            '<div style="background:#fefce8;border:1px solid #fef08a;border-radius:8px;padding:16px 24px;flex:1;text-align:center">'
            '<div style="font-size:28px;font-weight:700;color:#854d0e">%d</div>'
            '<div style="color:#92400e;font-size:13px">dokumenata ceka</div></div>'
            '<div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:16px 24px;flex:1;text-align:center">'
            '<div style="font-size:28px;font-weight:700;color:#14532d">%.2f EUR</div>'
            '<div style="color:#166534;font-size:13px">ukupni iznos</div></div></div>'
            '<h3 style="color:#1f2937;margin:0 0 12px;font-size:15px">Dokumenti koji cekaju vase odobrenje:</h3>'
            '<table style="width:100%%;border-collapse:collapse;border:1px solid #e5e7eb;border-radius:8px;overflow:hidden">'
            '<thead><tr style="background:#f9fafb">'
            '<th style="padding:10px 8px;text-align:left;font-size:12px;color:#6b7280;text-transform:uppercase">Broj</th>'
            '<th style="padding:10px 8px;text-align:left;font-size:12px;color:#6b7280;text-transform:uppercase">Partner</th>'
            '<th style="padding:10px 8px;text-align:right;font-size:12px;color:#6b7280;text-transform:uppercase">Iznos</th>'
            '<th style="padding:10px 8px;text-align:left;font-size:12px;color:#6b7280;text-transform:uppercase">Konta</th>'
            '<th style="padding:10px 8px;text-align:center;font-size:12px;color:#6b7280;text-transform:uppercase">AI</th>'
            "</tr></thead><tbody>%s</tbody></table>"
            "%s"
            '<div style="text-align:center;margin-top:24px">'
            '<a href="https://limit-connect.com/hr/documents/ai-inbox/" '
            'style="background:#c9a84c;color:#0a0a0a;font-weight:700;padding:12px 32px;border-radius:10px;text-decoration:none;font-size:15px;display:inline-block">'
            "Pregledaj i odobri u sustavu</a></div>"
            '<p style="color:#9ca3af;font-size:12px;text-align:center;margin-top:16px">'
            "Automatska poruka iz LIMIT Connect ERP sustava.<br>"
            "Dokumenti se cuvaju 11 godina prema Zakonu o racunovodstvu.</p>"
            "</div></div></body></html>"
        ) % (
            company.name,
            now.strftime("%d.%m.%Y"),
            count,
            float(total_amount),
            rows,
            ('<p style="color:#6b7280;font-size:13px;text-align:center;margin-top:8px">%s</p>' % more_text)
            if more_text
            else "",
        )

        recipients = list(
            CompanyMembership.objects.filter(
                company=company,
                role__in=["owner", "admin", "company_admin"],
                is_active=True,
                user__is_active=True,
                user__email__isnull=False,
            )
            .exclude(user__email="")
            .values_list("user__email", flat=True)
        )

        if not recipients:
            continue

        try:
            msg = EmailMultiAlternatives(
                subject="%d dokumenata ceka knjizenje - %s (%s)" % (count, company.name, now.strftime("%d.%m.%Y")),
                body="%d dokumenata ceka vase odobrenje u LIMIT Connect AI Inboxu. Ukupno: %.2f EUR. Otvorite: https://limit-connect.com/hr/documents/ai-inbox/"
                % (count, float(total_amount)),
                to=recipients,
            )
            msg.attach_alternative(html, "text/html")
            msg.send()
            sent += 1
            logger.info("AI Inbox email poslan za %s na %s", company.name, recipients)
        except (ValueError, TypeError) as mail_err:
            logger.warning("send_ai_inbox_summary_email za %s: %s", company.name, mail_err)

    return {"companies_mailed": sent}


@shared_task(bind=True, soft_time_limit=600, name="documents.process_scan_batch")
def process_scan_batch(self, batch_id):
    """
    OCR + AI grupiranje za batch skeniranih slika.
    1. OCR svake slike (pytesseract ili postojeći pipeline)
    2. AI grupiranje višestraničnih dokumenata
    3. Update batch status
    """
    import logging

    logger = logging.getLogger("documents.tasks")

    from documents.models import ScanBatch

    try:
        batch = ScanBatch.objects.get(pk=batch_id)
    except ScanBatch.DoesNotExist:
        return {"error": "batch_not_found"}

    images = batch.images.all().order_by("order")
    if not images.exists():
        batch.status = "error"
        batch.error_message = "Nema slika u batchu"
        batch.save(update_fields=["status", "error_message"])
        return {"error": "no_images"}

    # FAZA 1: OCR
    batch.status = "processing"
    batch.save(update_fields=["status"])

    for img in images:
        try:
            # Koristi pytesseract ako je dostupan
            import pytesseract
            from PIL import Image

            pil_img = Image.open(img.image.path)
            text = pytesseract.image_to_string(pil_img, lang="hrv+deu+eng")
            img.extracted_text = text
            img.save(update_fields=["extracted_text"])
        except ImportError:
            # Fallback: označi da OCR nije dostupan
            img.extracted_text = "[OCR nedostupan — pytesseract nije instaliran]"
            img.save(update_fields=["extracted_text"])
        except (FileNotFoundError, PermissionError, IOError) as e:
            logger.warning("OCR failed za sliku %s: %s", img.pk, e)
            img.extracted_text = f"[OCR greška: {str(e)[:100]}]"
            img.save(update_fields=["extracted_text"])

    # FAZA 2: AI grupiranje
    batch.status = "grouping"
    batch.save(update_fields=["status"])

    # Jednostavno grupiranje: svaka slika = zaseban dokument
    # (AI grupiranje se može dodati kasnije kad Haiku bude spreman)
    for i, img in enumerate(images, 1):
        img.document_group = i
        img.page_in_group = 1
        img.ai_confidence = 0.8
        img.save(update_fields=["document_group", "page_in_group", "ai_confidence"])

    batch.status = "ready"
    batch.total_documents = images.count()
    batch.save(update_fields=["status", "total_documents"])

    logger.info("Scan batch %s: %d slika → %d dokumenata", batch_id, batch.total_images, batch.total_documents)
    return {"ok": True, "documents": batch.total_documents}


@shared_task(bind=True, soft_time_limit=600, name="documents.verify_arhiva_integrity")
def verify_arhiva_integrity(self):
    """
    Weekly integrity hash verification (Sunday 03:15).
    Recomputes SHA-256 from current data and compares with stored hash.
    Logs discrepancies as FenixSignal (type='integrity_violation').
    """
    from documents.models import ArhivaEntry

    verified = 0
    violations = 0
    violation_details = []

    # Process in batches to avoid memory issues
    qs = (
        ArhivaEntry.objects.filter(
            integrity_hash__isnull=False,
        )
        .exclude(integrity_hash="")
        .order_by("id")
    )

    batch_size = 1000
    last_id = 0

    while True:
        batch = list(qs.filter(id__gt=last_id)[:batch_size])
        if not batch:
            break

        for entry in batch:
            last_id = entry.id
            current_hash = entry.compute_integrity_hash()
            if current_hash != entry.integrity_hash:
                violations += 1
                violation_details.append(
                    {
                        "entry_id": entry.id,
                        "archive_number": entry.archive_number,
                        "doc_number": entry.doc_number,
                        "company_id": entry.company_id,
                        "stored_hash": entry.integrity_hash[:16] + "...",
                        "computed_hash": current_hash[:16] + "...",
                    }
                )
            verified += 1

    logger.info(
        "verify_arhiva_integrity: verified=%d, violations=%d",
        verified,
        violations,
    )

    # Log violations as FenixSignal
    if violations > 0:
        try:
            from limit_connect_ai.models_signal import FenixSignal

            FenixSignal.objects.create(
                signal_type="bug",
                source="api",
                status="new",
                priority=1,  # Critical
                message=(
                    f"INTEGRITY VIOLATION: {violations} od {verified} arhivskih zapisa "
                    f"ima nepodudarnost hash-a. Moguca neovlastena izmjena podataka."
                ),
                context={
                    "type": "integrity_violation",
                    "verified": verified,
                    "violations": violations,
                    "details": violation_details[:20],  # Max 20 details
                },
            )
        except (IntegrityError, DatabaseError) as sig_err:
            logger.error("verify_arhiva_integrity: FenixSignal creation failed: %s", sig_err)

        # Notify superadmins
        try:
            from django.contrib.auth import get_user_model

            from notifications.services import notify

            User = get_user_model()
            for admin in User.objects.filter(is_superuser=True, is_active=True):
                notify(
                    recipient=admin,
                    notification_type="system",
                    title="INTEGRITET: Nepodudarnost hash-a u arhivi",
                    message=f"{violations} zapisa ima nepodudarnost. Moguca neovlastena izmjena.",
                    url="/hr/documents/arhiva/",
                )
        except DatabaseError as notif_err:
            logger.warning("verify_arhiva_integrity: notification failed: %s", notif_err)

    return {
        "verified": verified,
        "violations": violations,
        "details": violation_details[:5],
    }


@shared_task(bind=True, soft_time_limit=600, name="documents.auto_book_high_confidence")
def auto_book_high_confidence(self):
    """
    Dnevni task (06:00) — auto-proknjizi sve unbooked entries s confidence >= 0.8
    koji imaju validan debit+credit u ai_proposal.
    Kreira JournalEntry + LedgerLine za svaki entry.
    """
    from documents.models import ArhivaEntry
    from documents.views import (
        _create_journal_entry_from_proposal,
        _normalize_confidence,
        _proposal_has_debit_credit,
    )

    qs = (
        ArhivaEntry.objects.filter(
            is_booked=False,
        )
        .exclude(ai_proposal__isnull=True)
        .exclude(ai_proposal={})
    )

    booked = 0
    je_created = 0
    errors = 0

    for entry in qs.iterator():
        conf_score = _normalize_confidence(entry.ai_proposal)
        if conf_score < 0.8:
            continue
        if not _proposal_has_debit_credit(entry.ai_proposal):
            continue

        try:
            je = _create_journal_entry_from_proposal(entry, user=None)
            if je:
                je_created += 1
            entry.is_booked = True
            entry.save(update_fields=["is_booked"])
            booked += 1
        except Exception as exc:
            errors += 1
            logger.warning("auto_book_high_confidence: failed for entry %s: %s", entry.pk, exc)

    logger.info(
        "auto_book_high_confidence: booked=%d, JEs=%d, errors=%d",
        booked,
        je_created,
        errors,
    )

    return {"booked": booked, "journal_entries": je_created, "errors": errors}


@shared_task(bind=True, soft_time_limit=120)
def gmail_ura_import(self):
    """
    Gmail URA auto-import — čita ulazne račune iz email-a.

    PREDUVJET: Ivan mora postaviti Gmail OAuth2 na console.cloud.google.com
    Scope: https://www.googleapis.com/auth/gmail.modify
    .env: GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN, GMAIL_IMPORT_EMAIL

    Status: pending_review (ne odmah WhatsApp — Marija ne treba alarm za kataloge)
    Batch: 10 emailova = 1 zbirna WhatsApp poruka
    """
    import os

    client_id = os.environ.get("GMAIL_CLIENT_ID", "")
    client_secret = os.environ.get("GMAIL_CLIENT_SECRET", "")
    refresh_token = os.environ.get("GMAIL_REFRESH_TOKEN", "")

    if not all([client_id, client_secret, refresh_token]):
        logger.info("Gmail credentials nisu konfigurirani — preskačem. Ivan treba postaviti OAuth2.")
        return {"status": "skipped", "reason": "missing_credentials"}

    # TODO: Implementirati kad Ivan postavi OAuth
    # 1. OAuth2 refresh token flow
    # 2. Fetch unread emails s attachment-ima (PDF/XML)
    # 3. Za svaki: ArhivaEntry(source_type='email_in', status='pending_review')
    # 4. AI ekstrakcija iznosa, partnera, datuma
    # 5. Batch WhatsApp digest: "10 novih URA importirano, pregledaj na /documents/ai-inbox/"
    logger.info("Gmail OAuth configured but import not yet implemented.")
    return {"status": "pending_setup"}


# ═══════════════════════════════════════════════════════════════
# AI Image Tagging — auto-tag photos with Claude Haiku
# ═══════════════════════════════════════════════════════════════


@shared_task(bind=True, max_retries=2, retry_backoff=True)
def ai_tag_photos(self):
    """
    Process untagged photo ArhivaEntries — call Claude Haiku for auto-tagging.
    Runs every 30 min via celery beat. Batch of 5 per run.
    """
    import base64
    import json
    import os

    from django.conf import settings as django_settings

    from documents.models import ArhivaEntry

    logger = logging.getLogger("documents.tasks")

    api_key = getattr(django_settings, "ANTHROPIC_API_KEY", "")
    if not api_key:
        return {"status": "skipped", "reason": "no_api_key"}

    # Find photos without tags
    entries = list(
        ArhivaEntry.objects.filter(
            content_category="photo",
            has_image=True,
            tags=[],
        )
        .exclude(file_path="")
        .order_by("archived_at")[:5]
    )

    if not entries:
        return {"status": "ok", "tagged": 0}

    tagged = 0
    for entry in entries:
        abs_path = os.path.join(django_settings.MEDIA_ROOT, entry.file_path)
        if not os.path.exists(abs_path):
            # Mark with error tag so we don't retry
            entry.tags = ["_file_missing"]
            entry.save(update_fields=["tags"])
            continue

        # Read and encode image
        try:
            with open(abs_path, "rb") as f:
                img_bytes = f.read()
            if len(img_bytes) > 5_000_000:
                entry.tags = ["_too_large"]
                entry.save(update_fields=["tags"])
                continue
            b64 = base64.b64encode(img_bytes).decode()
        except OSError:
            continue

        # Detect media type
        ext = os.path.splitext(entry.file_path)[1].lower()
        media_type = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }.get(ext, "image/jpeg")

        # Call Claude Haiku
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=api_key)
            response = client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=200,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {"type": "base64", "media_type": media_type, "data": b64},
                            },
                            {
                                "type": "text",
                                "text": (
                                    "Analiziraj sliku i vrati JSON array tagova na hrvatskom jeziku. "
                                    "Max 5 tagova. Primjeri: prozor, vrata, fasada, gradiliste, "
                                    "ostecenje, ugradnja, prije, poslije, interijer, eksterijer, "
                                    "dostava, potpis, racun, dokument, zivotinja, kuca, stan, "
                                    "ured, skladiste, alat, materijal. "
                                    'Odgovori SAMO JSON array, npr: ["prozor", "ugradnja", "poslije"]'
                                ),
                            },
                        ],
                    }
                ],
            )

            text = response.content[0].text.strip()
            # Parse JSON array
            if text.startswith("["):
                tags = json.loads(text)
                if isinstance(tags, list) and all(isinstance(t, str) for t in tags):
                    # Merge with existing tags (preserve source tags)
                    existing = entry.tags or []
                    merged = list(set(existing + [t.lower().strip() for t in tags[:5]]))
                    entry.tags = merged
                    entry.save(update_fields=["tags"])
                    tagged += 1
                    logger.info("ai_tag: %s → %s", entry.archive_number, merged)

        except Exception as e:
            logger.warning("ai_tag failed for %s: %s", entry.pk, e)

    logger.info("ai_tag_photos: tagged %d/%d", tagged, len(entries))
    return {"tagged": tagged, "total": len(entries)}
