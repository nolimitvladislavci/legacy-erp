"""Scan Views — ScanToken mobile portal + QR scan + Scan Batch.

ARHIVA-1: Komitent dobije link -> otvori na mobitelu -> slika racun -> ArhivaEntry.
Bez logina. Bez instalacije. Jedan gumb.
"""

import logging
from datetime import date as _date
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db import models
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from core.company_utils import get_user_company

from .models import ArhivaEntry, ScanBatch, ScanBatchImage, ScanToken
from .storage_backends import store_document

logger = logging.getLogger(__name__)


# ================================================================
# SCAN TOKEN — Persistent mobile scan portal (ARHIVA-1)
# ================================================================


def _get_categories_for_company(company):
    """Get categories applicable to this company (global + custom)."""
    from .models import ArhivaCategory

    return list(
        ArhivaCategory.objects.filter(
            is_active=True,
        )
        .filter(models.Q(company=company) | models.Q(company__isnull=True))
        .exclude(country__in=["DE", "AT", "SI", "IT"])  # Show EU + HR for now
        .order_by("sort_order")
        .values("code", "name_hr", "name_de", "name_en", "icon", "color")
    )


def _auto_categorize(partner_name, company):
    """AI keyword-based auto-categorization."""
    from .models import ArhivaCategory

    partner_lower = partner_name.lower()
    categories = ArhivaCategory.objects.filter(
        is_active=True,
    ).filter(models.Q(company=company) | models.Q(company__isnull=True))

    for cat in categories:
        if cat.ai_keywords:
            for kw in cat.ai_keywords:
                if kw.lower() in partner_lower:
                    return cat
    return None


def scan_mobile_page(request, token):
    """GET /scan/{token}/ — Mobile kamera sucelje. PUBLIC, bez logina."""
    scan_token = ScanToken.objects.select_related("company").filter(token=token).first()
    if not scan_token or not scan_token.is_valid():
        return render(
            request,
            "documents/scan_expired.html",
            {
                "reason": "invalid" if not scan_token else "expired",
            },
        )
    return render(
        request,
        "documents/scan_mobile.html",
        {
            "token": str(scan_token.token),
            "company_name": scan_token.company.name,
            "label": scan_token.label or "",
            "direct_upload": True,
            "categories": _get_categories_for_company(scan_token.company),
        },
    )


@csrf_exempt
def scan_upload(request, token):
    """POST /scan/{token}/upload/ — Prima sliku, kreira ArhivaEntry. PUBLIC."""
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    scan_token = ScanToken.objects.select_related("company").filter(token=token).first()
    if not scan_token or not scan_token.is_valid():
        return JsonResponse({"error": "Token nije valjan ili je istekao"}, status=410)

    uploaded = request.FILES.get("file")
    if not uploaded:
        return JsonResponse({"error": "Nema datoteke"}, status=400)

    allowed_types = ("image/", "application/pdf")
    if not any(uploaded.content_type.startswith(t) for t in allowed_types):
        return JsonResponse({"error": "Samo slike ili PDF"}, status=400)

    file_bytes = uploaded.read()
    if len(file_bytes) > 10 * 1024 * 1024:
        return JsonResponse({"error": "Max 10MB"}, status=400)

    company = scan_token.company
    is_image = uploaded.content_type.startswith("image/")
    is_pdf = uploaded.name.lower().endswith(".pdf")

    # Store file via storage backend
    try:
        result = store_document(
            file_bytes=file_bytes,
            filename=uploaded.name,
            company_id=company.id,
            source_type="receipt_scan",
        )
    except Exception:
        logger.exception("scan_upload: store_document failed for token %s", token)
        return JsonResponse({"error": "Greska pri spremanju"}, status=500)

    # Create ArhivaEntry
    try:
        # Resolve expense category
        category_code = request.POST.get("category", "")
        expense_cat = None
        if category_code:
            from .models import ArhivaCategory

            expense_cat = (
                ArhivaCategory.objects.filter(code=category_code, is_active=True)
                .filter(models.Q(company=company) | models.Q(company__isnull=True))
                .first()
            )

        entry = ArhivaEntry(
            company=company,
            source_type="receipt_scan",
            source_id=result.get("hash", ""),
            doc_number=uploaded.name,
            amount=Decimal("0"),
            currency="EUR",
            doc_date=_date.today(),
            file_path=result["path"],
            has_pdf=is_pdf,
            has_image=is_image,
            archived_by=scan_token.created_by,
            session_key=f"scan_token_{scan_token.pk}",
            content_category="scan",
            ai_status="pending",
            expense_category=expense_cat,
        )
        entry.save()
    except Exception:
        logger.exception("scan_upload: ArhivaEntry creation failed for token %s", token)
        return JsonResponse({"error": "Greska pri arhiviranju"}, status=500)

    # Increment use count
    scan_token.use()

    # Trigger AI OCR async
    ocr_result = {}
    try:
        from documents.tasks import generate_ai_proposal

        generate_ai_proposal.apply_async(args=[entry.pk], countdown=2)
    except Exception as e:
        logger.warning("scan_upload: AI task dispatch failed (non-blocking): %s", e)

    # Inline quick OCR for immediate feedback (if small image)
    if is_image and len(file_bytes) < 3_700_000:
        try:
            import base64

            from core.views_scan import _build_content, _call_anthropic, _parse_json, _post_process

            b64 = base64.b64encode(file_bytes).decode()
            content = _build_content([b64], "invoice")
            raw = _call_anthropic(content, max_tokens=400)
            fields = _parse_json(raw)
            fields = _post_process(fields, "invoice")
            ocr_result = fields

            # Update entry with OCR data
            update_fields = []
            if fields.get("dobavljac"):
                entry.partner_name = fields["dobavljac"]
                entry.doc_number = fields.get("broj_racuna") or uploaded.name
                update_fields.extend(["partner_name", "doc_number"])
            if fields.get("iznos_ukupno"):
                try:
                    entry.amount = Decimal(str(fields["iznos_ukupno"]))
                    update_fields.append("amount")
                except Exception:
                    pass
            if fields.get("datum"):
                try:
                    entry.doc_date = fields["datum"]
                    update_fields.append("doc_date")
                except Exception:
                    pass
            # Auto-categorize from OCR partner name
            if not expense_cat and fields.get("dobavljac"):
                auto_cat = _auto_categorize(fields["dobavljac"], company)
                if auto_cat:
                    entry.expense_category = auto_cat
                    update_fields.append("expense_category")
            if update_fields:
                entry.save(update_fields=update_fields)
                logger.info(
                    "scan_upload: OCR ok, partner=%s, amount=%s",
                    fields.get("dobavljac", "?"),
                    fields.get("iznos_ukupno", "?"),
                )
        except Exception as e:
            logger.warning("scan_upload: inline OCR failed (non-blocking): %s", e)

    return JsonResponse(
        {
            "ok": True,
            "message": "Arhivirano ✓",
            "entry_id": entry.pk,
            "partner": ocr_result.get("dobavljac", ""),
            "amount": str(ocr_result.get("iznos_ukupno", "")),
            "archive_number": entry.archive_number,
        }
    )


@login_required
def scan_poll(request, token):
    """Poll za status — legacy kompatibilnost. Sada samo vraća entry info."""
    scan_token = ScanToken.objects.filter(token=token).first()
    if not scan_token:
        return JsonResponse({"ready": False, "error": "Token ne postoji"})
    # Return last entry for this token
    last_entry = (
        ArhivaEntry.objects.filter(company=scan_token.company, session_key=f"scan_token_{scan_token.pk}")
        .order_by("-archived_at")
        .first()
    )
    if not last_entry:
        return JsonResponse({"ready": False})
    return JsonResponse(
        {
            "ready": True,
            "entry_id": last_entry.pk,
            "partner": last_entry.partner_name,
            "amount": str(last_entry.amount),
            "doc_number": last_entry.doc_number,
            "ai_status": last_entry.ai_status,
        }
    )


# ================================================================
# TOKEN MANAGEMENT — Kreiranje i upravljanje tokenima
# ================================================================


@login_required
def scan_create_token(request):
    """Kreiraj novi ScanToken za firmu. Vrati link + QR."""
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    company = get_user_company(request)
    if not company:
        return JsonResponse({"error": "Nema tvrtke"}, status=400)

    label = request.POST.get("label", "").strip()
    expires_days = request.POST.get("expires_days", "")
    max_uses = int(request.POST.get("max_uses", 0) or 0)

    expires_at = None
    if expires_days:
        try:
            expires_at = timezone.now() + timezone.timedelta(days=int(expires_days))
        except (ValueError, TypeError):
            pass

    scan_token = ScanToken.objects.create(
        company=company,
        created_by=request.user,
        label=label,
        expires_at=expires_at,
        max_uses=max_uses,
    )

    url = request.build_absolute_uri(reverse("documents:scan_mobile_page", args=[str(scan_token.token)]))

    from core.qr_views import qr_base64 as _qr_b64

    qr_data = _qr_b64(url, size=200, color="c9a84c", bg="0a0a0a")

    return JsonResponse(
        {
            "ok": True,
            "token": str(scan_token.token),
            "url": url,
            "qr_data": qr_data,
            "label": scan_token.label,
            "expires_at": scan_token.expires_at.isoformat() if scan_token.expires_at else None,
        }
    )


@login_required
def scan_token_list(request):
    """Lista aktivnih tokena za firmu (JSON)."""
    company = get_user_company(request)
    if not company:
        return JsonResponse({"tokens": []})
    tokens = ScanToken.objects.filter(company=company).order_by("-created_at")[:50]
    return JsonResponse(
        {
            "tokens": [
                {
                    "token": str(t.token),
                    "label": t.label,
                    "use_count": t.use_count,
                    "is_active": t.is_active,
                    "is_valid": t.is_valid(),
                    "created_at": t.created_at.isoformat(),
                    "expires_at": t.expires_at.isoformat() if t.expires_at else None,
                    "url": request.build_absolute_uri(reverse("documents:scan_mobile_page", args=[str(t.token)])),
                }
                for t in tokens
            ]
        }
    )


@login_required
@require_POST
def scan_token_toggle(request, token):
    """Aktiviraj/deaktiviraj token."""
    company = get_user_company(request)
    scan_token = get_object_or_404(ScanToken, token=token, company=company)
    scan_token.is_active = not scan_token.is_active
    scan_token.save(update_fields=["is_active"])
    return JsonResponse({"ok": True, "is_active": scan_token.is_active})


# ================================================================
# SCAN BATCH — Enterprise Pipeline (existing, preserved)
# ================================================================


@login_required
def scan_batch_new(request):
    company = get_user_company(request)
    override_id = request.GET.get("company", "")
    if override_id:
        from accounts.models import CompanyMembership

        has_access = CompanyMembership.objects.filter(
            user=request.user, company_id=override_id, is_active=True
        ).exists()
        if has_access:
            from companies.models import Company

            company = Company.objects.filter(pk=override_id).first() or company
    if not company:
        return redirect("documents:list")
    batch = ScanBatch.objects.create(company=company, created_by=request.user)
    return redirect("documents:scan_batch_detail", pk=batch.pk)


@login_required
def scan_batch_detail(request, pk):
    company = get_user_company(request)
    batch = get_object_or_404(ScanBatch, pk=pk, company=company)
    return render(
        request,
        "documents/scan_batch.html",
        {"batch": batch, "images": batch.images.order_by("order")},
    )


@login_required
@require_POST
def scan_batch_upload(request, pk):
    company = get_user_company(request)
    batch = get_object_or_404(ScanBatch, pk=pk, company=company)
    if batch.status != "collecting":
        return JsonResponse({"ok": False, "error": "Batch nije u collecting statusu"}, status=400)
    files = request.FILES.getlist("images")
    if not files:
        return JsonResponse({"ok": False, "error": "Nema slika"}, status=400)
    current = batch.images.count()
    if current + len(files) > 100:
        return JsonResponse({"ok": False, "error": "Max 100 slika (trenutno %d)" % current}, status=400)
    for i, f in enumerate(files):
        ScanBatchImage.objects.create(
            batch=batch,
            image=f,
            order=current + i + 1,
            original_filename=f.name,
            file_size_kb=f.size // 1024,
        )
    batch.total_images = batch.images.count()
    batch.total_size_kb = sum(img.file_size_kb for img in batch.images.all())
    batch.save(update_fields=["total_images", "total_size_kb", "updated_at"])
    return JsonResponse(
        {
            "ok": True,
            "added": len(files),
            "total_images": batch.total_images,
            "total_size_kb": batch.total_size_kb,
        }
    )


@login_required
@require_POST
def scan_batch_process(request, pk):
    """Klik 2: Pokreni AI analizu. Self-rescheduling, zero blocking."""
    company = get_user_company(request)
    batch = get_object_or_404(ScanBatch, pk=pk, company=company)
    if batch.total_images == 0:
        return JsonResponse({"ok": False, "error": "Nema slika"}, status=400)
    batch.status = "processing"
    batch.error_message = "Pokrecem AI analizu..."
    batch.save(update_fields=["status", "error_message"])
    from documents.tasks_scan_gemini import process_scan_chunk

    process_scan_chunk.delay(batch.pk, 0, 0, 0)
    total = batch.total_images
    chunks = (total + 9) // 10
    est = max(1, chunks + (chunks - 1))
    return JsonResponse(
        {
            "ok": True,
            "status": "processing",
            "total_images": total,
            "estimated_minutes": est,
        }
    )


@login_required
def scan_batch_status(request, pk):
    """Polling endpoint — delegira na DocumentProcessor."""
    company = get_user_company(request)
    batch = get_object_or_404(ScanBatch, pk=pk, company=company)
    from documents.services.document_processor import DocumentProcessor

    return JsonResponse(DocumentProcessor.get_summary(batch.pk))


@login_required
@require_POST
def scan_batch_archive(request, pk):
    """Klik 3: Async arhiviranje s atomic transactions."""
    company = get_user_company(request)
    batch = get_object_or_404(ScanBatch, pk=pk, company=company)
    if batch.status != "ready":
        return JsonResponse({"ok": False, "error": "Batch nije spreman"}, status=400)
    from documents.tasks_scan_gemini import archive_scan_batch

    archive_scan_batch.delay(batch.pk, request.user.pk)
    return JsonResponse(
        {
            "ok": True,
            "message": "Arhiviranje pokrenuto. Dokumenti se pojavljuju u arhivi.",
        }
    )


# ================================================================
# ARHIVA PORTAL — Magic Link pristup (ARHIVA-2)
# ================================================================


def arhiva_portal(request, token):
    """GET /arhiva-portal/{token}/ — Read-only pristup arhivi. PUBLIC, bez logina."""
    from .models import ArhivaAccessToken

    access_token = ArhivaAccessToken.objects.select_related("company").filter(token=token).first()
    if not access_token or not access_token.is_valid():
        return render(
            request,
            "documents/arhiva_portal_expired.html",
            {
                "reason": "invalid" if not access_token else "expired",
            },
        )

    company = access_token.company
    access_token.record_access()

    # Fetch arhiva entries for this company
    entries = ArhivaEntry.objects.filter(company=company).order_by("-archived_at")

    total_count = entries.count()
    total_amount = entries.aggregate(total=models.Sum("amount"))["total"] or 0

    # Group by year
    from collections import defaultdict

    by_year = defaultdict(list)
    for e in entries[:200]:  # Limit for performance
        year = e.doc_date.year if e.doc_date else "Nepoznato"
        by_year[year].append(e)

    # ZOR info
    from datetime import date

    zor_until = date.today().year + 11

    # Category stats

    cats_with_entries = (
        entries.filter(expense_category__isnull=False)
        .values(
            "expense_category__code", "expense_category__name_hr", "expense_category__icon", "expense_category__color"
        )
        .annotate(count=models.Count("id"), total=models.Sum("amount"))
        .order_by("-count")
    )
    uncategorized = entries.filter(expense_category__isnull=True).count()

    context = {
        "token": str(access_token.token),
        "company": company,
        "label": access_token.label,
        "total_count": total_count,
        "total_amount": total_amount,
        "entries_by_year": dict(sorted(by_year.items(), reverse=True)),
        "entries_recent": entries[:20],
        "zor_until": zor_until,
        "scan_tokens": ScanToken.objects.filter(company=company, is_active=True)[:5],
        "category_stats": list(cats_with_entries),
        "uncategorized_count": uncategorized,
    }
    return render(request, "documents/arhiva_portal.html", context)


@login_required
def arhiva_access_create(request):
    """Kreiraj ArhivaAccessToken za firmu. Umbrella panel."""
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    company = get_user_company(request)
    if not company:
        return JsonResponse({"error": "Nema tvrtke"}, status=400)

    # Target company (umbrella child)
    target_company_id = request.POST.get("company_id", "")
    if target_company_id:
        from companies.models import Company as _Company

        target = _Company.objects.filter(pk=target_company_id).first()
        if not target:
            return JsonResponse({"error": "Firma ne postoji"}, status=404)
    else:
        target = company

    label = request.POST.get("label", "").strip() or f"Pristup arhivi — {target.name}"
    expires_days = request.POST.get("expires_days", "")

    expires_at = None
    if expires_days:
        try:
            expires_at = timezone.now() + timezone.timedelta(days=int(expires_days))
        except (ValueError, TypeError):
            pass

    from .models import ArhivaAccessToken

    access_token = ArhivaAccessToken.objects.create(
        company=target,
        created_by=request.user,
        label=label,
        expires_at=expires_at,
    )

    url = request.build_absolute_uri(f"/hr/arhiva-portal/{access_token.token}/")

    from core.qr_views import qr_base64 as _qr_b64

    qr_data = _qr_b64(url, size=200, color="c9a84c", bg="0a0a0a")

    return JsonResponse(
        {
            "ok": True,
            "token": str(access_token.token),
            "url": url,
            "qr_data": qr_data,
            "label": access_token.label,
            "company_name": target.name,
            "expires_at": access_token.expires_at.isoformat() if access_token.expires_at else None,
        }
    )


@login_required
def arhiva_access_list(request):
    """Lista aktivnih access tokena."""
    company = get_user_company(request)
    if not company:
        return JsonResponse({"tokens": []})

    from .models import ArhivaAccessToken

    # Show tokens for this company AND all umbrella children
    company_ids = [company.pk]
    from companies.models import Company as _Company

    children = _Company.objects.filter(umbrella_parent=company).values_list("pk", flat=True)
    company_ids.extend(children)

    tokens = (
        ArhivaAccessToken.objects.filter(company_id__in=company_ids)
        .select_related("company")
        .order_by("-created_at")[:100]
    )

    return JsonResponse(
        {
            "tokens": [
                {
                    "token": str(t.token),
                    "label": t.label,
                    "company_name": t.company.name,
                    "access_count": t.access_count,
                    "is_active": t.is_active,
                    "is_valid": t.is_valid(),
                    "last_accessed_at": t.last_accessed_at.isoformat() if t.last_accessed_at else None,
                    "created_at": t.created_at.isoformat(),
                    "expires_at": t.expires_at.isoformat() if t.expires_at else None,
                    "url": request.build_absolute_uri(f"/hr/arhiva-portal/{t.token}/"),
                }
                for t in tokens
            ]
        }
    )


@login_required
def arhiva_access_bulk_create(request):
    """Bulk kreiranje access tokena za sve umbrella children."""
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    company = get_user_company(request)
    if not company:
        return JsonResponse({"error": "Nema tvrtke"}, status=400)

    from companies.models import Company as _Company

    from .models import ArhivaAccessToken

    children = _Company.objects.filter(umbrella_parent=company)
    created = 0
    skipped = 0

    for child in children:
        # Skip if already has active token
        if ArhivaAccessToken.objects.filter(company=child, is_active=True).exists():
            skipped += 1
            continue
        ArhivaAccessToken.objects.create(
            company=child,
            created_by=request.user,
            label=f"Pristup arhivi — {child.name}",
        )
        created += 1

    return JsonResponse(
        {
            "ok": True,
            "created": created,
            "skipped": skipped,
            "total_children": children.count(),
        }
    )


# ================================================================
# PORTAL DOWNLOAD — Token-authorized file download (ARHIVA-2+)
# ================================================================


def arhiva_portal_download(request, token, entry_id):
    """Download file from portal — authorized by ArhivaAccessToken or ScanToken."""
    import os

    from django.http import FileResponse, Http404

    from .models import ArhivaAccessToken, ArhivaEntry, DocumentBlob

    # Authorize via access token
    access_token = ArhivaAccessToken.objects.select_related("company").filter(token=token).first()
    if not access_token or not access_token.is_valid():
        raise Http404

    company = access_token.company

    # Get entry — must belong to same company
    entry = ArhivaEntry.objects.filter(pk=entry_id, company=company).first()
    if not entry:
        raise Http404

    # Try file_path
    if entry.file_path:
        full_path = entry.file_path
        if not os.path.isabs(full_path):
            full_path = os.path.join("/var/www/fina-connect", full_path)
        if os.path.exists(full_path):
            # Log download
            from .models import ArhivaAuditLog, log_arhiva_action

            log_arhiva_action(entry, ArhivaAuditLog.Action.DOWNLOADED, request=request)
            return FileResponse(
                open(full_path, "rb"),
                as_attachment=True,
                filename=os.path.basename(full_path),
            )

    # Try DocumentBlob
    from django.http import HttpResponse

    blob = DocumentBlob.objects.filter(
        company=company,
        source_type=entry.source_type,
    ).first()
    if blob:
        response = HttpResponse(blob.file_data, content_type=blob.content_type)
        response["Content-Disposition"] = f'attachment; filename="{blob.filename}"'
        return response

    raise Http404
