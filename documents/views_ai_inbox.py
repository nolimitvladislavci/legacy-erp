"""AI Inbox Views — AI proposal management + Conversion views."""

import json
import logging
import os
from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from core.company_utils import get_user_company

from .models import ArhivaEntry

logger = logging.getLogger(__name__)


def _safe_err(e, default="Greska pri obradi. Kontaktirajte administratora."):
    """Sanitizira exception poruku — ne salje stack trace korisniku."""
    msg = str(e)
    if len(msg) > 80 or any(x in msg for x in ['File "', "line ", "Traceback", "django.", "psycopg"]):
        return default
    return msg[:80]


def _normalize_confidence(ai_proposal):
    """Normalize confidence from ai_proposal to float 0-1.
    Handles: 'high', 'medium', 'low', floats like 0.6/0.95, None."""
    if not ai_proposal or not isinstance(ai_proposal, dict):
        return 0.0
    conf = ai_proposal.get("confidence")
    if conf is None:
        return 0.0
    if isinstance(conf, (int, float)):
        return min(max(float(conf), 0.0), 1.0)
    if isinstance(conf, str):
        conf_lower = conf.strip().lower()
        if conf_lower == "high":
            return 0.9
        elif conf_lower == "medium":
            return 0.6
        elif conf_lower == "low":
            return 0.3
        # Try parsing numeric string
        try:
            return min(max(float(conf_lower), 0.0), 1.0)
        except (ValueError, TypeError):
            return 0.0
    return 0.0


def _confidence_level(score):
    """Return 'high', 'medium', or 'low' from float score."""
    if score >= 0.8:
        return "high"
    elif score >= 0.5:
        return "medium"
    return "low"


def _proposal_has_debit_credit(ai_proposal):
    """Check if proposal has valid debit and credit entries."""
    if not ai_proposal or not isinstance(ai_proposal, dict):
        return False
    debit = ai_proposal.get("debit")
    credit = ai_proposal.get("credit")
    if not debit or not credit:
        return False
    if not isinstance(debit, list) or not isinstance(credit, list):
        return False
    if len(debit) == 0 or len(credit) == 0:
        return False
    # Check at least first entry has account
    if not debit[0].get("account") or not credit[0].get("account"):
        return False
    return True


def _create_journal_entry_from_proposal(entry, user=None):
    """Create JournalEntry + LedgerLines from ArhivaEntry.ai_proposal.
    Returns the JournalEntry or None on failure."""
    from konto.models import JournalEntry, KontoAccount, LedgerLine

    proposal = entry.ai_proposal
    if not _proposal_has_debit_credit(proposal):
        return None

    # Generate entry number
    year = date.today().year
    prefix = f"AI-{year}-"
    last = (
        JournalEntry.objects.filter(company=entry.company, entry_number__startswith=prefix)
        .order_by("-entry_number")
        .first()
    )
    if last:
        try:
            seq = int(last.entry_number.split("-")[-1]) + 1
        except (ValueError, IndexError):
            seq = 1
    else:
        seq = 1
    entry_number = f"{prefix}{seq:05d}"

    je = JournalEntry(
        company=entry.company,
        entry_number=entry_number,
        date=entry.doc_date or date.today(),
        description=f"AI: {entry.doc_number} — {entry.partner_name}"[:300],
        source_type="manual",
        is_posted=True,
        created_by=user,
    )
    je.save()

    for side_key, side_value in [("debit", "debit"), ("credit", "credit")]:
        for line_data in proposal.get(side_key, []):
            account_code = str(line_data.get("account", "")).strip()
            if not account_code:
                continue
            amount = line_data.get("amount", 0)
            try:
                amount = Decimal(str(round(float(amount), 2)))
            except (ValueError, TypeError):
                amount = Decimal("0")
            if amount <= 0:
                continue

            # Find or create KontoAccount
            account, _ = KontoAccount.objects.get_or_create(
                company=entry.company,
                code=account_code,
                defaults={
                    "name": line_data.get("description", f"Konto {account_code}")[:100],
                    "account_type": "expense"
                    if account_code.startswith("4")
                    else "revenue"
                    if account_code.startswith("7")
                    else "asset"
                    if account_code.startswith(("0", "1"))
                    else "liability"
                    if account_code.startswith("2")
                    else "equity",
                },
            )
            LedgerLine.objects.create(
                journal_entry=je,
                account=account,
                side=side_value,
                amount=amount,
                description=(line_data.get("description", "") or "")[:200],
            )

    return je


@login_required
def ai_inbox(request):
    """AI Inbox — svi dokumenti s AI prijedlogom koji nisu proknjizeni.
    Supports confidence_filter, source_type filter, sorted by confidence DESC then amount DESC."""

    is_superadmin = request.user.is_superuser
    if is_superadmin:
        qs = (
            ArhivaEntry.objects.filter(is_booked=False)
            .exclude(ai_proposal__isnull=True)
            .exclude(ai_proposal={})
            .select_related("company")
            .order_by("-archived_at")
        )
    else:
        company = get_user_company(request)
        if not company:
            return render(
                request,
                "documents/ai_inbox.html",
                {
                    "entries": [],
                    "stats": {},
                    "confidence_counts": {},
                    "confidence_filter": "all",
                    "source_type_filter": "",
                },
            )
        qs = (
            ArhivaEntry.objects.filter(company=company, is_booked=False)
            .exclude(ai_proposal__isnull=True)
            .exclude(ai_proposal={})
            .order_by("-archived_at")
        )

    # Filteri
    company_filter = request.GET.get("company", "")
    if company_filter and is_superadmin:
        qs = qs.filter(company_id=company_filter)

    source_type_filter = request.GET.get("source_type", "")
    if source_type_filter:
        qs = qs.filter(source_type=source_type_filter)

    # Compute confidence for ALL entries (before confidence filter)
    all_entries = list(qs)
    for e in all_entries:
        e.confidence_score = _normalize_confidence(e.ai_proposal)
        e.confidence_level = _confidence_level(e.confidence_score)
        e.confidence_pct = int(round(e.confidence_score * 100))

    # Confidence counts (before filtering)
    confidence_counts = {
        "high": sum(1 for e in all_entries if e.confidence_level == "high"),
        "medium": sum(1 for e in all_entries if e.confidence_level == "medium"),
        "low": sum(1 for e in all_entries if e.confidence_level == "low"),
        "all": len(all_entries),
    }

    # Apply confidence filter
    confidence_filter = request.GET.get("confidence", "all")
    if confidence_filter == "high":
        all_entries = [e for e in all_entries if e.confidence_level == "high"]
    elif confidence_filter == "medium":
        all_entries = [e for e in all_entries if e.confidence_level == "medium"]
    elif confidence_filter == "low":
        all_entries = [e for e in all_entries if e.confidence_level == "low"]

    # Sort by confidence DESC then amount DESC
    all_entries.sort(key=lambda e: (-e.confidence_score, -float(e.amount or 0)))

    # Stats (from full queryset, not filtered)
    total_pending = confidence_counts["all"]
    by_company = (
        qs.values("company__name", "company__id").annotate(cnt=Count("id"), total_amt=Sum("amount")).order_by("-cnt")
    )

    # Paginacija
    page = int(request.GET.get("page", 1))
    per_page = 50
    paginated_entries = all_entries[(page - 1) * per_page : page * per_page]
    has_next = len(all_entries) > page * per_page

    total_amount = qs.aggregate(t=Sum("amount"))["t"] or 0
    stats = {
        "total_pending": total_pending,
        "total_amount": total_amount,
        "company_count": by_company.count() if hasattr(by_company, "count") else len(list(by_company)),
        "by_company": list(by_company),
    }

    if request.GET.get("format") == "json":
        data = []
        for e in paginated_entries:
            data.append(
                {
                    "id": e.pk,
                    "company": str(e.company),
                    "company_id": str(e.company_id),
                    "doc_number": e.doc_number,
                    "partner_name": e.partner_name,
                    "amount": float(e.amount) if e.amount else 0,
                    "currency": e.currency,
                    "doc_date": e.doc_date.isoformat() if e.doc_date else None,
                    "source_type": e.source_type,
                    "ai_proposal": e.ai_proposal,
                    "is_booked": e.is_booked,
                    "confidence_score": e.confidence_score,
                    "confidence_level": e.confidence_level,
                }
            )
        return JsonResponse({"entries": data, "has_next": has_next, "page": page, "total": total_pending})

    return render(
        request,
        "documents/ai_inbox.html",
        {
            "entries": paginated_entries,
            "stats": stats,
            "page": page,
            "has_next": has_next,
            "is_superadmin": is_superadmin,
            "confidence_counts": confidence_counts,
            "confidence_filter": confidence_filter,
            "source_type_filter": source_type_filter,
            "source_types": ArhivaEntry.SOURCE_TYPES,
        },
    )


@login_required
@require_POST
def ai_inbox_accept(request, entry_id):
    """Prihvati AI prijedlog — proknjizi dokument i kreiraj temeljnicu."""
    entry = get_object_or_404(ArhivaEntry, pk=entry_id)

    # Security check
    if not request.user.is_superuser:
        company = get_user_company(request)
        if company and entry.company_id != company.pk:
            return JsonResponse({"error": "Nemate pristup"}, status=403)

    # Create JournalEntry from AI proposal
    je = None
    if _proposal_has_debit_credit(entry.ai_proposal):
        try:
            je = _create_journal_entry_from_proposal(entry, user=request.user)
        except Exception as exc:
            logger.warning("ai_inbox_accept: JournalEntry creation failed for %s: %s", entry_id, exc)

    entry.is_booked = True
    entry.save(update_fields=["is_booked"])

    logger.info(
        "ai_inbox_accept: entry=%s booked by user=%s, JE=%s",
        entry_id,
        request.user.username,
        je.entry_number if je else "N/A",
    )

    return JsonResponse(
        {
            "ok": True,
            "id": entry.pk,
            "message": "Proknjizeno!" + (f" Temeljnica: {je.entry_number}" if je else ""),
            "journal_entry": je.entry_number if je else None,
        }
    )


@login_required
@require_POST
def ai_inbox_bulk_accept(request):
    """Bulk prihvati AI prijedloge za odabranu firmu.
    Supports min_confidence filter: only accepts entries >= min_confidence with valid D/K."""
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        data = {}

    company_id = data.get("company_id") or request.POST.get("company_id", "")
    if not company_id:
        return JsonResponse({"error": "company_id required"}, status=400)

    min_confidence = float(data.get("min_confidence", 0))

    # Security
    if not request.user.is_superuser:
        user_company = get_user_company(request)
        if user_company and str(user_company.pk) != str(company_id):
            return JsonResponse({"error": "Nemate pristup"}, status=403)

    entries = (
        ArhivaEntry.objects.filter(company_id=company_id, is_booked=False)
        .exclude(ai_proposal__isnull=True)
        .exclude(ai_proposal={})
    )

    booked = 0
    je_count = 0
    for entry in entries:
        conf_score = _normalize_confidence(entry.ai_proposal)
        if min_confidence > 0 and conf_score < min_confidence:
            continue
        if min_confidence > 0 and not _proposal_has_debit_credit(entry.ai_proposal):
            continue

        # Create JournalEntry if proposal is valid
        if _proposal_has_debit_credit(entry.ai_proposal):
            try:
                je = _create_journal_entry_from_proposal(entry, user=request.user)
                if je:
                    je_count += 1
            except Exception as exc:
                logger.warning("ai_inbox_bulk_accept: JE failed for entry %s: %s", entry.pk, exc)

        entry.is_booked = True
        entry.save(update_fields=["is_booked"])
        booked += 1

    logger.info(
        "ai_inbox_bulk_accept: company=%s, booked=%d, JEs=%d, min_conf=%.2f, user=%s",
        company_id,
        booked,
        je_count,
        min_confidence,
        request.user.username,
    )

    return JsonResponse(
        {
            "ok": True,
            "count": booked,
            "journal_entries": je_count,
            "message": f"{booked} dokumenata proknjizeno! ({je_count} temeljnica kreirano)",
        }
    )


@login_required
@require_POST
def ai_inbox_send_email(request):
    """Rucni trigger email sazetka za trenutnu kompaniju."""
    from documents.tasks import send_ai_inbox_summary_email

    company = get_user_company(request)
    if company:
        send_ai_inbox_summary_email.delay(company_id=company.pk)
    elif request.user.is_superuser:
        send_ai_inbox_summary_email.delay()
    return JsonResponse({"ok": True, "message": "Email sazetak je u redu cekanja"})


# ════════════════════════════════════════════════════════════
# KONVERZIJA — Slika ulaznog racuna -> XML
# ════════════════════════════════════════════════════════════


@login_required
def arhiva_convert(request):
    """Upload slike ulaznog racuna za konverziju u XML."""
    if request.method == "POST" and request.FILES.get("file"):
        company = get_user_company(request)
        if not company:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"error": "Nema aktivne tvrtke"}, status=400)
            messages.error(request, _("Niste povezani s tvrtkom. Odaberite tvrtku iz izbornika."))
            return redirect("documents:arhiva_list")

        uploaded = request.FILES["file"]
        file_bytes = uploaded.read()

        # Validate file type
        ext = os.path.splitext(uploaded.name)[1].lower()
        if ext not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"error": "Samo slike (JPG, PNG, WebP). PDF koristite Smart Import."}, status=400)
            messages.error(request, _("Samo slike (JPG, PNG, WebP)."))
            return redirect("documents:arhiva_list")

        try:
            from documents.conversion_service import convert_image_to_xml

            record = convert_image_to_xml(
                file_bytes=file_bytes,
                filename=uploaded.name,
                company=company,
                user=request.user,
            )

            # ── Kreiraj ArhivaEntry iz ConversionRecord ──────────────────
            arhiva_entry = None
            if record and record.original_path:
                try:
                    from decimal import Decimal as _Dec
                    from django.utils import timezone as _tz
                    from documents.conversion_service import _parse_date_obj
                    from documents.views_arhiva import _fuzzy_match_partner

                    exdata = record.extracted_data or {}
                    seller = exdata.get("seller") or {}
                    partner_name = (seller.get("name") or "").strip()

                    amount_raw = exdata.get("total") or 0
                    try:
                        amount = _Dec(str(round(float(amount_raw), 2)))
                    except (ValueError, TypeError):
                        amount = _Dec("0")

                    doc_number = (exdata.get("invoice_number") or "").strip() or record.original_filename
                    doc_date = _parse_date_obj(exdata.get("issue_date", "")) if exdata.get("issue_date") else None
                    currency = (exdata.get("currency") or "EUR").upper()[:3]

                    matched_partner = None
                    if partner_name:
                        matched_partner, _ = _fuzzy_match_partner(partner_name, company)

                    arhiva_entry = ArhivaEntry.objects.create(
                        company=company,
                        source_type="invoice_in",
                        source_id=record.original_hash or "",
                        doc_number=doc_number,
                        partner_name=partner_name or (matched_partner.name if matched_partner else ""),
                        partner=matched_partner,
                        amount=amount,
                        currency=currency,
                        doc_date=doc_date or _tz.now().date(),
                        file_path=record.original_path,
                        has_image=True,
                        has_xml=bool(record.xml_path),
                        archived_by=request.user,
                        session_key=request.session.session_key or "",
                    )
                    record.arhiva_entry = arhiva_entry
                    record.save(update_fields=["arhiva_entry"])

                    # Trigeraj AI prijedlog
                    try:
                        from documents.tasks import generate_ai_proposal

                        arhiva_entry.ai_status = "pending"
                        arhiva_entry.ai_status_message = "Čekam AI analizu..."
                        arhiva_entry.save(update_fields=["ai_status", "ai_status_message"])
                        generate_ai_proposal.apply_async(args=[arhiva_entry.pk], countdown=3)
                    except Exception as _ai_e:
                        logger.warning("arhiva_convert: AI trigger failed: %s", _ai_e)

                    logger.info(
                        "arhiva_convert: ArhivaEntry %s kreiran za %s (partner=%s, iznos=%s)",
                        arhiva_entry.pk,
                        company,
                        partner_name,
                        amount,
                    )
                except Exception as _entry_err:
                    logger.warning("arhiva_convert: ArhivaEntry creation failed: %s", _entry_err, exc_info=True)

            result = {
                "success": True,
                "record_id": str(record.id),
                "entry_id": str(arhiva_entry.pk) if arhiva_entry else None,
                "archive_number": arhiva_entry.archive_number if arhiva_entry else None,
                "status": record.status,
                "confidence": record.ai_confidence,
                "confidence_score": record.ai_confidence_score,
                "fields_extracted": record.fields_extracted,
                "items_extracted": record.items_extracted,
                "original_size": record.original_size,
                "xml_size": record.xml_size,
                "size_reduction_pct": round(record.size_reduction_pct, 1),
                "is_valid": record.is_valid,
                "validation_errors": record.validation_errors,
                "extracted_data": record.extracted_data,
                "savings": record.savings_display,
                "message": "Konverzija zavrsena: %s -> XML (%s usteda)" % (uploaded.name, record.savings_display),
            }

            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse(result)

            if record.is_valid:
                messages.success(request, result["message"])
            else:
                messages.warning(
                    request, _("Konverzija zavrsena s upozorenjima: %s") % "; ".join(record.validation_errors)
                )

        except Exception as e:
            logger.error("arhiva_upload FAILED: %s", e, exc_info=True)
            logger.error("Conversion error: %s", e, exc_info=True)
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"error": str(e)}, status=500)
            messages.error(request, _safe_err(e))

        return redirect("documents:arhiva_list")

    # GET: show conversion page
    from documents.models import ConversionRecord

    company = get_user_company(request)
    if request.user.is_superuser:
        recent = ConversionRecord.objects.all()[:20]
    elif company:
        recent = ConversionRecord.objects.filter(company=company)[:20]
    else:
        recent = []

    return render(
        request,
        "documents/arhiva_convert.html",
        {
            "recent_conversions": recent,
        },
    )


@login_required
def conversion_detail(request, pk):
    """API: detalji konverzije."""
    from documents.models import ConversionRecord

    record = get_object_or_404(ConversionRecord, pk=pk)

    if not request.user.is_superuser:
        company = get_user_company(request)
        if record.company != company:
            return JsonResponse({"error": "Forbidden"}, status=403)

    return JsonResponse(
        {
            "id": str(record.id),
            "status": record.status,
            "status_display": record.get_status_display(),
            "original_filename": record.original_filename,
            "original_size": record.original_size,
            "original_hash": record.original_hash,
            "ai_model": record.ai_model,
            "ai_confidence": record.ai_confidence,
            "ai_confidence_score": record.ai_confidence_score,
            "ai_cost_eur": str(record.ai_cost_eur),
            "fields_extracted": record.fields_extracted,
            "items_extracted": record.items_extracted,
            "xml_size": record.xml_size,
            "xml_hash": record.xml_hash,
            "size_reduction_pct": round(record.size_reduction_pct, 1),
            "is_valid": record.is_valid,
            "validation_errors": record.validation_errors,
            "extracted_data": record.extracted_data,
            "savings": record.savings_display,
            "created_at": record.created_at.strftime("%d.%m.%Y %H:%M") if record.created_at else "",
            "completed_at": record.completed_at.strftime("%d.%m.%Y %H:%M") if record.completed_at else "",
        }
    )


@login_required
@require_POST
def conversion_create_primka(request, pk):
    """Kreira GoodsReceipt primku iz ConversionRecord extracted_data.

    Kontrole:
    - Duplikat: ako vec postoji primka iz iste konverzije, vraca link na postojecu
    - Auto-broj: PRIMKA-YYYY-NNNN sekvencijalni (HR propisi, ZOR cl. 9)
    - Ako nema broja ulaznog racuna: napomena za rucnu provjeru
    """
    from datetime import date as _date

    from documents.conversion_service import _parse_date_obj
    from documents.models import ConversionRecord
    from inventory.models import GoodsReceipt, GoodsReceiptItem, InventoryItem
    from partners.models import Partner

    record = get_object_or_404(ConversionRecord, pk=pk)
    company = get_user_company(request)

    if not request.user.is_superuser and record.company != company:
        return JsonResponse({"error": "Forbidden"}, status=403)

    # ── Duplikat kontrola: trazi primku s istim conversion ID u notes ──
    conv_marker = "conversion:%s" % record.id
    existing = GoodsReceipt.objects.filter(
        company=company,
        notes__contains=conv_marker,
    ).first()
    if existing:
        return JsonResponse(
            {
                "ok": True,
                "duplicate": True,
                "primka_id": existing.pk,
                "primka_url": "/inventory/receipts/%s/" % existing.pk,
                "message": "Primka %s vec postoji iz ove konverzije" % existing.receipt_number,
            }
        )

    data = record.extracted_data or {}
    seller = data.get("seller", {})

    # ── Partner: pronadi po OIB-u ili imenu ──
    partner = None
    oib = seller.get("oib", "").strip()
    if oib:
        partner = Partner.objects.filter(company=company, oib=oib).first()
    if not partner and seller.get("name"):
        partner = Partner.objects.filter(company=company, name__icontains=seller["name"][:20]).first()

    # ── Auto-broj primke: PRIMKA-YYYY-NNNN ──
    year = _date.today().year
    prefix = "PRIMKA-%d-" % year
    last = (
        GoodsReceipt.objects.filter(
            company=company,
            receipt_number__startswith=prefix,
        )
        .order_by("-receipt_number")
        .first()
    )
    seq = 1
    if last and last.receipt_number:
        try:
            seq = int(last.receipt_number.split("-")[-1]) + 1
        except (ValueError, IndexError):
            pass
    receipt_number = "%s%04d" % (prefix, seq)

    # ── Broj ulaznog racuna ──
    invoice_number = (data.get("invoice_number") or "").strip()
    notes_parts = ["[conversion:%s]" % record.id]
    if not invoice_number:
        notes_parts.append(
            'NAPOMENA: Broj ulaznog racuna nije prepoznat iz slike - provjeriti rucno i unijeti u polje "Broj ulaznog racuna"'
        )
    notes_parts.append("Izvor: AI konverzija slike %s" % record.original_filename)

    # ── Vrsta primke (iz POST body ili default) ──
    import json as _json

    try:
        body = _json.loads(request.body) if request.content_type == "application/json" else {}
    except (ValueError, TypeError):
        body = {}
    receipt_type = body.get("receipt_type", "supplier")
    valid_types = ("supplier", "return", "transfer", "inventory", "consignment", "complaint")
    if receipt_type not in valid_types:
        receipt_type = "supplier"

    # ── Kreiraj primku ──
    issue_date = _parse_date_obj(data.get("issue_date", ""))

    primka = GoodsReceipt.objects.create(
        company=company,
        supplier=partner,
        receipt_number=receipt_number,
        date=issue_date or _date.today(),
        document_number=invoice_number,
        linked_invoice_number=invoice_number,
        notes="\n".join(notes_parts),
        status="draft",
        created_by=request.user,
        receipt_type=receipt_type,
    )

    # ── Stavke ──
    items_added = 0
    items_skipped = 0
    skipped_names = []
    for item_data in data.get("items", []):
        desc = item_data.get("description", "")
        inv_item = None
        if desc:
            inv_item = InventoryItem.objects.filter(company=company, name__icontains=desc[:30]).first()

        if not inv_item:
            items_skipped += 1
            skipped_names.append(desc[:40] if desc else "?")
            continue

        gi = GoodsReceiptItem(
            receipt=primka,
            inventory_item=inv_item,
            quantity=item_data.get("quantity", 1),
            purchase_price_unit=item_data.get("unit_price", 0),
            tax_rate=item_data.get("vat_rate", 25),
        )
        gi.calculate()
        gi.save()
        items_added += 1

    msg = "Primka %s kreirana" % receipt_number
    details = []
    if items_added:
        details.append("%d stavki dodano" % items_added)
    if items_skipped:
        details.append("%d preskoceno (artikl nije pronadjen)" % items_skipped)
    if not invoice_number:
        details.append("broj racuna nije prepoznat")
    if details:
        msg += " (%s)" % ", ".join(details)

    return JsonResponse(
        {
            "ok": True,
            "primka_id": primka.pk,
            "primka_url": "/inventory/receipts/%s/" % primka.pk,
            "receipt_number": receipt_number,
            "items_added": items_added,
            "items_skipped": items_skipped,
            "skipped_items": skipped_names[:5],
            "missing_invoice_number": not bool(invoice_number),
            "message": msg,
        }
    )


# ════════════════════════════════════════════════════════════
# MERGE KONVERZIJA — Više slika → jedan dokument
# ════════════════════════════════════════════════════════════


@login_required
def arhiva_convert_merge(request):
    """Merge više slika u jedan PDF dokument pa konvertiraj u XML + ArhivaEntry.

    POST multipart/form-data:
      file_0, file_1, ... file_N  — slike stranica računa (max 10)
      csrfmiddlewaretoken

    Vraca JSON identičan kao arhiva_convert single-mode.
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    company = get_user_company(request)
    if not company:
        return JsonResponse({"error": "Nema aktivne tvrtke"}, status=400)

    # Prikupi sve uploadane slike (file_0..file_9 ili files[])
    images = []
    for key in sorted(request.FILES.keys()):
        f = request.FILES[key]
        ext = os.path.splitext(f.name)[1].lower()
        if ext not in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"):
            continue
        images.append((f.name, f.read()))

    if not images:
        return JsonResponse({"error": "Nema slika za spajanje"}, status=400)
    if len(images) > 10:
        return JsonResponse({"error": "Max 10 stranica po dokumentu"}, status=400)

    if len(images) == 1:
        # Single image — delegate to regular convert
        import io as _io
        from django.core.files.uploadedfile import InMemoryUploadedFile

        name, data = images[0]
        f_obj = InMemoryUploadedFile(_io.BytesIO(data), "file", name, "image/jpeg", len(data), None)
        request.FILES["file"] = f_obj
        return arhiva_convert(request)

    # Merge images into a single PDF using PyMuPDF
    try:
        import fitz  # PyMuPDF
        import io as _io

        merged_pdf = fitz.open()

        for name, img_bytes in images:
            try:
                img_doc = fitz.open(stream=img_bytes, filetype="image")
                merged_pdf.insert_pdf(img_doc)
                img_doc.close()
            except Exception as img_err:
                logger.warning("arhiva_convert_merge: cannot add image %s: %s", name, img_err)
                continue

        if merged_pdf.page_count == 0:
            return JsonResponse({"error": "Spajanje neuspješno — niti jedna stranica"}, status=500)

        pdf_bytes = merged_pdf.tobytes(deflate=True)
        merged_pdf.close()

        first_name = images[0][0]
        merged_filename = os.path.splitext(first_name)[0] + "_spoj_%dstr.pdf" % len(images)

    except Exception as merge_err:
        logger.error("arhiva_convert_merge: PDF merge failed: %s", merge_err, exc_info=True)
        return JsonResponse({"error": "Spajanje slika neuspješno"}, status=500)

    # Now process merged PDF as a single conversion
    try:
        from documents.conversion_service import convert_image_to_xml

        record = convert_image_to_xml(
            file_bytes=pdf_bytes,
            filename=merged_filename,
            company=company,
            user=request.user,
        )

        # Create ArhivaEntry
        arhiva_entry = None
        if record and record.original_path:
            try:
                from decimal import Decimal as _Dec
                from django.utils import timezone as _tz
                from documents.conversion_service import _parse_date_obj
                from documents.views_arhiva import _fuzzy_match_partner

                exdata = record.extracted_data or {}
                seller = exdata.get("seller") or {}
                partner_name = (seller.get("name") or "").strip()

                try:
                    amount = _Dec(str(round(float(exdata.get("total") or 0), 2)))
                except (ValueError, TypeError):
                    amount = _Dec("0")

                doc_number = (exdata.get("invoice_number") or "").strip() or merged_filename
                doc_date = _parse_date_obj(exdata.get("issue_date", "")) if exdata.get("issue_date") else None
                currency = (exdata.get("currency") or "EUR").upper()[:3]

                matched_partner = None
                if partner_name:
                    matched_partner, _ = _fuzzy_match_partner(partner_name, company)

                arhiva_entry = ArhivaEntry.objects.create(
                    company=company,
                    source_type="invoice_in",
                    source_id=record.original_hash or "",
                    doc_number=doc_number,
                    partner_name=partner_name or (matched_partner.name if matched_partner else ""),
                    partner=matched_partner,
                    amount=amount,
                    currency=currency,
                    doc_date=doc_date or _tz.now().date(),
                    file_path=record.original_path,
                    has_image=False,
                    has_pdf=True,
                    has_xml=bool(record.xml_path),
                    archived_by=request.user,
                    session_key=request.session.session_key or "",
                )
                record.arhiva_entry = arhiva_entry
                record.save(update_fields=["arhiva_entry"])

                try:
                    from documents.tasks import generate_ai_proposal

                    arhiva_entry.ai_status = "pending"
                    arhiva_entry.ai_status_message = "Čekam AI analizu..."
                    arhiva_entry.save(update_fields=["ai_status", "ai_status_message"])
                    generate_ai_proposal.apply_async(args=[arhiva_entry.pk], countdown=3)
                except Exception as _ai_e:
                    logger.warning("arhiva_convert_merge: AI trigger failed: %s", _ai_e)

            except Exception as _entry_err:
                logger.warning("arhiva_convert_merge: ArhivaEntry failed: %s", _entry_err, exc_info=True)

        return JsonResponse(
            {
                "success": True,
                "merged": True,
                "pages": len(images),
                "record_id": str(record.id),
                "entry_id": str(arhiva_entry.pk) if arhiva_entry else None,
                "archive_number": arhiva_entry.archive_number if arhiva_entry else None,
                "status": record.status,
                "confidence": record.ai_confidence,
                "confidence_score": record.ai_confidence_score,
                "fields_extracted": record.fields_extracted,
                "items_extracted": record.items_extracted,
                "original_size": record.original_size,
                "xml_size": record.xml_size,
                "size_reduction_pct": round(record.size_reduction_pct, 1),
                "is_valid": record.is_valid,
                "validation_errors": record.validation_errors,
                "extracted_data": record.extracted_data,
                "savings": record.savings_display,
                "message": "Spoj %d stranica konvertiran u arhivu" % len(images),
            }
        )

    except Exception as e:
        logger.error("arhiva_convert_merge FAILED: %s", e, exc_info=True)
        return JsonResponse({"error": _safe_err(e)}, status=500)
