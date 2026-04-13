import json

"""smart_import/views.py -- Upload, staging, confirm with full CRUD.
   v2 - 2026-03-17: Problem report, better status API, retry endpoint.
"""
import logging
import os
from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.company_utils import get_user_company
from inventory.models import GoodsReceipt, GoodsReceiptItem, InventoryItem
from partners.models import Partner
from smart_import.models import ImportBatch, ImportBatchItem, ProblemReport, VendorItemMapping
from smart_import.tasks import process_import_batch

logger = logging.getLogger(__name__)

_ALLOWED_EXT = {
    ".xml": "xml",
    ".pdf": "pdf",
    ".jpg": "image", ".jpeg": "image",
    ".png": "image", ".webp": "image",
    ".heic": "image", ".heif": "image",
}


@login_required
def upload_view(request):
    company   = get_user_company(request)
    suppliers = Partner.objects.filter(company=company, partner_type__in=["supplier", "both"]).order_by("name")

    if request.method == "POST":
        supplier_id = request.POST.get("supplier")
        supplier    = None
        if supplier_id:
            try:
                supplier = Partner.objects.get(pk=supplier_id, company=company)
            except Partner.DoesNotExist:
                pass

        control_amount = request.POST.get("control_amount", "").strip()

        uploaded_files = request.FILES.getlist("files")
        if not uploaded_files:
            return render(request, "smart_import/upload.html", {
                "suppliers": suppliers,
                "error": "Niste odabrali nijednu datoteku.",
            })

        # Classify files
        for uf in uploaded_files:
            ext = os.path.splitext(uf.name)[1].lower()
            ft = _ALLOWED_EXT.get(ext)
            if not ft:
                return render(request, "smart_import/upload.html", {
                    "suppliers": suppliers,
                    "error": "Nepodrzani format: {}. Prihvacamo XML, PDF i slike.".format(ext),
                })

        # Determine batch file_type
        if len(uploaded_files) == 1:
            ext = os.path.splitext(uploaded_files[0].name)[1].lower()
            batch_type = _ALLOWED_EXT[ext]
        else:
            batch_type = "multipage"

        batch = ImportBatch.objects.create(
            company=company,
            supplier=supplier,
            file=uploaded_files[0],
            file_type=batch_type,
            status="pending",
            status_message="Ucitavanje datoteke...",
            original_filename=uploaded_files[0].name[:255],
            created_by=request.user,
        )

        # Save extra files
        page_paths = [batch.file.path]
        for i, uf in enumerate(uploaded_files[1:], start=2):
            ext = os.path.splitext(uf.name)[1].lower() or ".jpg"
            save_name = "smart_import/pages/batch_{}_page_{}{}".format(batch.pk, i, ext)
            saved = default_storage.save(save_name, uf)
            page_paths.append(default_storage.path(saved))

        meta = {}
        if len(uploaded_files) > 1:
            meta["page_paths"] = page_paths
            meta["page_count"] = len(uploaded_files)
        if control_amount:
            try:
                meta["control_amount"] = str(Decimal(control_amount.replace(",", ".")))
            except (ValueError, TypeError):
                pass

        if meta:
            batch.raw_json = meta
            batch.save(update_fields=["raw_json"])

        process_import_batch.delay(batch.pk)
        return redirect("smart_import:stage", pk=batch.pk)

    recent = ImportBatch.objects.filter(company=company).order_by("-created_at")[:10]
    return render(request, "smart_import/upload.html", {"suppliers": suppliers, "recent_batches": recent})


@login_required
def stage_view(request, pk):
    company = get_user_company(request)
    batch   = get_object_or_404(ImportBatch, pk=pk, company=company)
    inv_items = InventoryItem.objects.filter(company=company, is_active=True).order_by("name")
    suppliers = Partner.objects.filter(company=company, partner_type__in=["supplier", "both"]).order_by("name")

    # Control amount check
    control_amount = None
    control_diff = None
    raw = batch.raw_json if isinstance(batch.raw_json, dict) else {}
    if raw.get("control_amount"):
        try:
            control_amount = Decimal(raw["control_amount"])
            items_total = sum(
                (bi.purchase_price * bi.quantity) for bi in batch.items.all()
            )
            control_diff = items_total - control_amount
        except (ValueError, TypeError):
            pass

    return render(request, "smart_import/stage.html", {
        "batch":          batch,
        "inv_items":      inv_items,
        "suppliers":      suppliers,
        "control_amount": control_amount,
        "control_diff":   control_diff,
    })


@login_required
def batch_status_api(request, pk):
    company = get_user_company(request)
    batch   = get_object_or_404(ImportBatch, pk=pk, company=company)
    return JsonResponse({
        "status":         batch.status,
        "status_message": batch.status_message or "",
        "error":          batch.error_msg,
        "item_count":     batch.items.count(),
        "retry_count":    batch.retry_count or 0,
    })


@login_required
@require_POST
def retry_batch_api(request, pk):
    """Retry a failed batch."""
    company = get_user_company(request)
    batch   = get_object_or_404(ImportBatch, pk=pk, company=company)

    if batch.status not in ("error",):
        return JsonResponse({"ok": False, "error": "Batch nije u statusu greske."}, status=400)

    batch.status = "pending"
    batch.error_msg = ""
    batch.status_message = "Ponovni pokusaj..."
    batch.retry_count = 0
    batch.save(update_fields=["status", "error_msg", "status_message", "retry_count"])

    process_import_batch.delay(batch.pk)
    return JsonResponse({"ok": True})


@login_required
@require_POST
def report_problem_api(request, pk):
    """Report a problem with a batch."""
    company = get_user_company(request)
    batch   = get_object_or_404(ImportBatch, pk=pk, company=company)

    description = request.POST.get("description", "").strip()
    if not description:
        description = "Korisnik prijavio problem s uvozom (bez opisa)"

    ProblemReport.objects.create(
        batch=batch,
        company=company,
        reported_by=request.user,
        description=description,
    )

    logger.warning("Problem report for batch #%d by %s: %s", batch.pk, request.user, description[:100])

    return JsonResponse({"ok": True, "message": "Problem prijavljen. Hvala!"})


@login_required
@require_POST
def save_mapping_api(request, pk):
    """AJAX: save a manual vendor->inventory mapping and update the batch item."""
    company        = get_user_company(request)
    batch          = get_object_or_404(ImportBatch, pk=pk, company=company)
    batch_item_id  = request.POST.get("batch_item_id")
    inventory_id   = request.POST.get("inventory_item_id")

    try:
        batch_item = ImportBatchItem.objects.get(pk=batch_item_id, batch=batch)
        inv_item   = InventoryItem.objects.get(pk=inventory_id, company=company)
    except (ImportBatchItem.DoesNotExist, InventoryItem.DoesNotExist):
        return JsonResponse({"ok": False, "error": "Not found"}, status=404)

    batch_item.matched_item = inv_item
    batch_item.match_score  = 1.0
    batch_item.is_manual    = True
    batch_item.save(update_fields=["matched_item", "match_score", "is_manual"])

    VendorItemMapping.objects.update_or_create(
        company=company,
        vendor_item_name=batch_item.vendor_name,
        partner=batch.supplier,
        defaults={"inventory_item": inv_item},
    )

    return JsonResponse({"ok": True})


@login_required
@require_POST
def update_item_api(request, pk):
    """AJAX: update a batch item's fields (vendor_name, quantity, purchase_price, margin)."""
    company = get_user_company(request)
    batch   = get_object_or_404(ImportBatch, pk=pk, company=company)
    item_id = request.POST.get("item_id")

    try:
        item = ImportBatchItem.objects.get(pk=item_id, batch=batch)
    except ImportBatchItem.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Not found"}, status=404)

    changed = []
    if "vendor_name" in request.POST:
        item.vendor_name = request.POST["vendor_name"]
        changed.append("vendor_name")
    if "quantity" in request.POST:
        try:
            item.quantity = Decimal(request.POST["quantity"].replace(",", "."))
            changed.append("quantity")
        except (InvalidOperation, ValueError):
            pass
    if "purchase_price" in request.POST:
        try:
            item.purchase_price = Decimal(request.POST["purchase_price"].replace(",", "."))
            changed.append("purchase_price")
        except (InvalidOperation, ValueError):
            pass
    if "margin_override" in request.POST:
        val = request.POST["margin_override"].strip()
        if val:
            try:
                item.margin_override = Decimal(val.replace(",", "."))
                changed.append("margin_override")
            except (InvalidOperation, ValueError):
                pass
        else:
            item.margin_override = None
            changed.append("margin_override")

    if changed:
        item.save(update_fields=changed)

    return JsonResponse({"ok": True, "changed": changed})


@login_required
@require_POST
def delete_item_api(request, pk):
    """AJAX: delete a batch item."""
    company = get_user_company(request)
    batch   = get_object_or_404(ImportBatch, pk=pk, company=company)
    item_id = request.POST.get("item_id")

    try:
        item = ImportBatchItem.objects.get(pk=item_id, batch=batch)
        item.delete()
        return JsonResponse({"ok": True, "remaining": batch.items.count()})
    except ImportBatchItem.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Not found"}, status=404)


@login_required
@require_POST
def add_item_api(request, pk):
    """AJAX: add a new batch item."""
    company = get_user_company(request)
    batch   = get_object_or_404(ImportBatch, pk=pk, company=company)

    vendor_name = request.POST.get("vendor_name", "").strip()
    if not vendor_name:
        return JsonResponse({"ok": False, "error": "Naziv je obavezan"}, status=400)

    try:
        qty = Decimal(request.POST.get("quantity", "1").replace(",", "."))
    except (InvalidOperation, ValueError):
        qty = Decimal("1")

    try:
        pp = Decimal(request.POST.get("purchase_price", "0").replace(",", "."))
    except (InvalidOperation, ValueError):
        pp = Decimal("0")

    from django.db.models import Max
    max_idx = batch.items.aggregate(m=Max("row_index"))["m"] or 0
    item = ImportBatchItem.objects.create(
        batch=batch,
        row_index=max_idx + 1,
        vendor_name=vendor_name,
        quantity=qty,
        purchase_price=pp,
    )

    return JsonResponse({
        "ok": True,
        "item": {
            "id": item.pk,
            "vendor_name": item.vendor_name,
            "quantity": str(item.quantity),
            "purchase_price": str(item.purchase_price),
            "row_index": item.row_index,
        }
    })


@login_required
@require_POST
def update_supplier_api(request, pk):
    """AJAX: change the batch supplier."""
    company = get_user_company(request)
    batch   = get_object_or_404(ImportBatch, pk=pk, company=company)
    supplier_id = request.POST.get("supplier_id", "").strip()

    if supplier_id:
        try:
            batch.supplier = Partner.objects.get(pk=supplier_id, company=company)
        except Partner.DoesNotExist:
            return JsonResponse({"ok": False, "error": "Dobavljac ne postoji"}, status=404)
    else:
        batch.supplier = None

    batch.save(update_fields=["supplier"])
    name = batch.supplier.name if batch.supplier else ""
    return JsonResponse({"ok": True, "supplier_name": name})


@login_required
@require_POST
def confirm_view(request, pk):
    """Create GoodsReceipt from confirmed staging table."""
    company = get_user_company(request)
    batch   = get_object_or_404(ImportBatch, pk=pk, company=company)

    if batch.status not in ("ready", "error"):
        return JsonResponse({"ok": False, "error": "Batch nije spreman."}, status=400)

    global_margin = Decimal(request.POST.get("global_margin") or "30")
    doc_number    = request.POST.get("document_number", "")

    matched_items = batch.items.filter(matched_item__isnull=False)
    if not matched_items.exists():
        return render(request, "smart_import/stage.html", {
            "batch":     batch,
            "inv_items": InventoryItem.objects.filter(company=company, is_active=True).order_by("name"),
            "suppliers": Partner.objects.filter(company=company, partner_type__in=["supplier", "both"]).order_by("name"),
            "error":     "Nema spojenih stavki. Molimo povezite barem jedan artikl.",
        })

    receipt = GoodsReceipt.objects.create(
        company=company,
        supplier=batch.supplier,
        date=date.today(),
        document_number=doc_number,
        status="draft",
        created_by=request.user,
    )

    for bi in matched_items:
        margin = bi.margin_override if bi.margin_override is not None else global_margin
        tax    = bi.matched_item.tax_rate.rate if bi.matched_item.tax_rate else Decimal("25")
        GoodsReceiptItem.objects.create(
            receipt=receipt,
            inventory_item=bi.matched_item,
            quantity=bi.quantity,
            purchase_price_unit=bi.purchase_price,
            dependent_costs_unit=Decimal("0"),
            margin_percent=margin,
            tax_rate=tax,
        )

    receipt.confirm()

    for bi in batch.items.filter(is_manual=True):
        if bi.matched_item:
            VendorItemMapping.objects.update_or_create(
                company=company,
                vendor_item_name=bi.vendor_name,
                partner=batch.supplier,
                defaults={"inventory_item": bi.matched_item},
            )

    batch.goods_receipt = receipt
    batch.status        = "confirmed"
    batch.status_message = "Primka kreirana!"
    batch.save(update_fields=["goods_receipt", "status", "status_message"])

    return redirect("inventory:receipt_detail", pk=receipt.pk)





@login_required
def manual_entry_view(request, pk):
    """Manual data entry for failed Smart Import batch -- fallback when AI fails."""
    from django.utils.translation import gettext as _

    from documents.models import ArhivaEntry

    company = get_user_company(request)
    batch = get_object_or_404(ImportBatch, pk=pk, company=company)

    # Try to get any partial data from raw_json
    raw = batch.raw_json if isinstance(batch.raw_json, dict) else {}
    prefill = {}
    if isinstance(batch.raw_json, list) and batch.raw_json:
        first = batch.raw_json[0] if isinstance(batch.raw_json[0], dict) else {}
        prefill["partner_name"] = first.get("vendor", first.get("vendor_name", ""))
        prefill["amount"] = first.get("total", first.get("purchase_price", ""))
        prefill["doc_number"] = first.get("invoice_number", first.get("doc_number", ""))
    elif isinstance(raw, dict):
        prefill["partner_name"] = raw.get("vendor", "")
        prefill["amount"] = raw.get("total", "")
        prefill["doc_number"] = raw.get("invoice_number", "")

    if request.method == "POST":
        from datetime import date as _date
        doc_number = request.POST.get("doc_number", "").strip() or "RUCNI-{}".format(batch.pk)
        partner_name = request.POST.get("partner_name", "").strip()
        amount_str = request.POST.get("amount", "0").replace(",", ".")
        doc_date_str = request.POST.get("doc_date", "")
        source_type = request.POST.get("source_type", "invoice_in")
        description = request.POST.get("description", "").strip()

        try:
            from decimal import Decimal
            amount = Decimal(amount_str)
        except (ValueError, TypeError):
            amount = Decimal("0")

        try:
            from datetime import datetime
            doc_date = datetime.strptime(doc_date_str, "%Y-%m-%d").date()
        except ValueError:
            doc_date = _date.today()

        # Build file_path relative to MEDIA_ROOT if batch has a file
        file_path_rel = ""
        if batch.file:
            from django.conf import settings
            full = batch.file.path
            media = settings.MEDIA_ROOT.rstrip("/") + "/"
            if full.startswith(media):
                file_path_rel = full[len(media):]
            else:
                file_path_rel = batch.file.name

        has_image = batch.file_type in ("image", "img") if batch.file else False
        has_pdf = batch.file_type == "pdf" if batch.file else False

        entry = ArhivaEntry(
            company=company,
            source_type=source_type,
            source_id="smart_import:manual:{}".format(batch.pk),
            doc_number=doc_number,
            partner_name=partner_name,
            amount=amount,
            currency="EUR",
            doc_date=doc_date,
            file_path=file_path_rel,
            has_image=has_image,
            has_pdf=has_pdf,
            archived_by=request.user,
        )
        entry.integrity_hash = entry.compute_integrity_hash()
        entry.set_deletion_protection()
        entry.save()

        batch.status = "confirmed"
        batch.status_message = "Rucno uneseno u arhivu"
        batch.save(update_fields=["status", "status_message"])

        django_messages.success(request, _("Rucno uneseno: {} -- {}").format(doc_number, partner_name))
        return redirect("smart_import:upload")

    image_url = batch.file.url if batch.file and batch.file_type in ("image", "img") else None
    pdf_url = batch.file.url if batch.file and batch.file_type == "pdf" else None

    return render(request, "smart_import/manual_entry.html", {
        "batch": batch,
        "image_url": image_url,
        "pdf_url": pdf_url,
        "prefill": prefill,
    })


# -- WEBHOOK RAMPA (Push arhitektura za email racune) --
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from companies.models import Company


# CSRF exempt: external webhook — no browser session
@csrf_exempt
@require_POST
def inbound_email_webhook(request, secret):
    """
    Prima POST s privitcima iz Make.com / Zapier / Mailgun / SendGrid.
    Autentifikacija: tajni token u URL-u (ne treba login).
    """
    expected_secret = os.getenv("WEBHOOK_SECRET")
    if not expected_secret or secret != expected_secret:
        logger.warning("Webhook Rampa: neovlasten pristup! Secret: %s...", secret[:8])
        return HttpResponse("Unauthorized", status=401)

    company = Company.objects.first()
    if not company:
        logger.error("Webhook Rampa: nema tvrtke u bazi.")
        return HttpResponse("No company configured", status=400)

    allowed_exts = {
        ".xml": "xml", ".pdf": "pdf",
        ".jpg": "image", ".jpeg": "image", ".png": "image",
        ".webp": "image", ".heic": "image", ".heif": "image",
    }

    saved_count = 0
    for file_key, uploaded_file in request.FILES.items():
        ext = os.path.splitext(uploaded_file.name)[1].lower()
        if ext not in allowed_exts:
            continue

        batch = ImportBatch.objects.create(
            company=company,
            file_type=allowed_exts[ext],
            status="pending",
            status_message="Primljeno putem webhooka",
            original_filename=uploaded_file.name[:255],
        )
        safe_name = uploaded_file.name.replace(" ", "_")
        batch.file.save(safe_name, uploaded_file, save=True)
        process_import_batch.delay(batch.pk)
        saved_count += 1
        logger.info("Webhook Rampa: '%s' -> Batch #%d (%s)", safe_name, batch.pk, allowed_exts[ext])

    if saved_count == 0:
        return HttpResponse("No valid attachments found.", status=400)

    logger.info("Webhook Rampa: primljeno %d privitaka.", saved_count)
    return HttpResponse("OK. Processed %d attachments." % saved_count, status=200)


# ── Predarhiva: Staging bulk upload + progress ─────────────────────────

@login_required
def staging_upload(request):
    """Bulk upload — Marija učita 1000 slika, AI ih obradi u pozadini."""
    company = get_user_company(request)
    if not company:
        return render(request, 'smart_import/staging.html', {'no_company': True})

    if request.method == 'POST':
        files = request.FILES.getlist('files')
        if not files:
            return render(request, 'smart_import/staging.html', {
                'company': company, 'error': 'Niste odabrali nijedan fajl.',
            })

        from .models import StagingBatch, StagingFile
        title = request.POST.get('title', '').strip() or 'Bulk upload %s' % date.today().strftime('%d.%m.%Y')
        batch = StagingBatch.objects.create(
            company=company,
            title=title,
            total_files=len(files),
            created_by=request.user,
        )

        for f in files:
            StagingFile.objects.create(
                staging_batch=batch,
                file=f,
                original_filename=f.name,
            )

        return redirect('smart_import:staging_detail', pk=batch.pk)

    # GET — show upload form + list of existing batches
    from .models import StagingBatch
    batches = StagingBatch.objects.filter(company=company).order_by('-created_at')[:20]
    return render(request, 'smart_import/staging.html', {
        'company': company,
        'batches': batches,
    })


@login_required
def staging_detail(request, pk):
    """Detail view for a staging batch — preview files, start processing."""
    company = get_user_company(request)
    from .models import StagingBatch
    batch = get_object_or_404(StagingBatch, pk=pk, company=company)
    files = batch.files.all()
    return render(request, 'smart_import/staging_detail.html', {
        'company': company,
        'batch': batch,
        'files': files,
    })


@login_required
@require_POST
def staging_start(request, pk):
    """Start AI processing of a staging batch."""
    company = get_user_company(request)
    from .models import StagingBatch
    batch = get_object_or_404(StagingBatch, pk=pk, company=company)

    if batch.status != 'pending':
        return JsonResponse({'error': 'Batch nije u statusu pending.'}, status=400)

    batch.status = 'queued'
    batch.save(update_fields=['status'])

    from .tasks import process_staging_batch
    process_staging_batch.delay(batch.pk)

    return redirect('smart_import:staging_detail', pk=batch.pk)


@login_required
def staging_progress_api(request, pk):
    """AJAX endpoint — polling svakih 3s za live progress."""
    company = get_user_company(request)
    from .models import StagingBatch
    batch = get_object_or_404(StagingBatch, pk=pk, company=company)

    recent_files = batch.files.filter(
        status__in=['done', 'error']
    ).order_by('-processed_at')[:5]

    return JsonResponse({
        'status': batch.status,
        'progress_pct': batch.progress_pct,
        'processed': batch.processed_files,
        'total': batch.total_files,
        'failed': batch.failed_files,
        'last_message': batch.last_message,
        'estimated_minutes': batch.estimated_minutes_remaining,
        'recent': [
            {
                'filename': f.original_filename,
                'message': f.ai_message,
                'status': f.status,
            } for f in recent_files
        ],
        'is_done': batch.status in ('done', 'done_with_errors'),
    })


# ══════════════════════════════════════════════════════════════════════════════
# PREDKOMORA: Side-by-Side Review Dashboard
# Marija pregleda sumnjive račune — split-screen: slika lijevo, forma desno
# ══════════════════════════════════════════════════════════════════════════════

@login_required
def review_dashboard(request):
    """Predkomora — svi StagingFileHeader koji trebaju pregled."""
    company = get_user_company(request)
    if not company:
        return redirect('smart_import:staging_upload')

    import json

    from .models import StagingFileHeader

    # Svi headeri za ovu tvrtku, sortirani: needs_review=True prvi
    headers = StagingFileHeader.objects.filter(
        staging_file__staging_batch__company=company,
    ).select_related(
        'staging_file', 'matched_partner',
    ).order_by('-needs_review', '-created_at')[:200]

    items = []
    items_json = []

    for h in headers:
        sf = h.staging_file
        # Detektiraj duplikat (ponovo provjeri za display)
        is_dup = False
        if h.supplier_oib and h.invoice_number and h.total_amount:
            is_dup = StagingFileHeader.objects.filter(
                staging_file__staging_batch__company=company,
                supplier_oib=h.supplier_oib,
                invoice_number=h.invoice_number,
                total_amount=h.total_amount,
            ).exclude(pk=h.pk).exists()

        item = {
            'sf': sf,
            'header': h,
            'is_dup': is_dup,
        }
        items.append(item)

        items_json.append({
            'sf_id': sf.pk,
            'header_id': h.pk,
            'image_url': sf.file.url if sf.file else '',
            'supplier_name': h.supplier_name or '',
            'supplier_oib': h.supplier_oib or '',
            'invoice_number': h.invoice_number or '',
            'invoice_date': h.invoice_date.isoformat() if h.invoice_date else '',
            'total_amount': str(h.total_amount) if h.total_amount else '',
            'vat_amount': str(h.vat_amount) if h.vat_amount else '',
            'base_amount': str(h.base_amount) if h.base_amount else '',
            'currency': h.currency or 'EUR',
            'confidence': h.confidence or 0,
            'needs_review': h.needs_review,
            'is_dup': is_dup,
            'matched_partner_name': h.matched_partner.name if h.matched_partner else '',
            'filename': sf.original_filename,
        })

    pending_count = sum(1 for i in items if i['header'].needs_review)
    dup_count = sum(1 for i in items if i['is_dup'])
    low_conf_count = sum(1 for i in items if (i['header'].confidence or 0) < 0.7)
    resolved_count = sum(1 for i in items if not i['header'].needs_review)

    return render(request, 'smart_import/review_dashboard.html', {
        'items': items,
        'items_json': json.dumps(items_json),
        'pending_count': pending_count,
        'dup_count': dup_count,
        'low_conf_count': low_conf_count,
        'resolved_count': resolved_count,
    })


@login_required
@require_POST
def review_approve(request):
    """
    Proknjiži i spoji — ARMIRANO:
    - Zamka 2: matematička validacija (osnovica + PDV = ukupno ±0.02)
    - Zamka 3: atomska provjera stanja (select_for_update + conflict guard)
    """
    from decimal import Decimal, InvalidOperation

    from django.db import transaction

    from .models import StagingFileHeader

    company = get_user_company(request)
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'ok': False, 'error': 'Invalid JSON'}, status=400)

    header_id = data.get('header_id')
    if not header_id:
        return JsonResponse({'ok': False, 'error': 'Missing header_id'}, status=400)

    with transaction.atomic():
        # ── ZAMKA 3: select_for_update — atomska brava ──
        try:
            header = StagingFileHeader.objects.select_for_update().select_related(
                'staging_file__staging_batch'
            ).get(pk=header_id, staging_file__staging_batch__company=company)
        except StagingFileHeader.DoesNotExist:
            return JsonResponse({'ok': False, 'error': 'Header ne postoji'}, status=404)

        # Conflict guard — već proknjiženo?
        if not header.needs_review:
            return JsonResponse({
                'ok': False,
                'error': 'Ovaj račun je već proknjižen (vjerojatno drugi korisnik).',
                'code': 'CONFLICT',
            }, status=409)

        # ── Parse input fields ──
        header.supplier_name = data.get('supplier_name', header.supplier_name)[:255]
        header.supplier_oib = data.get('supplier_oib', header.supplier_oib)[:20].strip()
        header.invoice_number = data.get('invoice_number', header.invoice_number)[:100]

        inv_date = data.get('invoice_date', '')
        if inv_date:
            try:
                from datetime import datetime
                header.invoice_date = datetime.strptime(inv_date[:10], '%Y-%m-%d').date()
            except (ValueError, TypeError):
                pass

        for field, key in [('total_amount', 'total_amount'), ('vat_amount', 'vat_amount'), ('base_amount', 'base_amount')]:
            val = data.get(key)
            if val:
                try:
                    setattr(header, field, Decimal(str(val)))
                except (InvalidOperation, ValueError):
                    pass

        # ── ZAMKA 2: matematička validacija ──
        base = header.base_amount or Decimal('0')
        vat = header.vat_amount or Decimal('0')
        total = header.total_amount or Decimal('0')

        if base > 0 and vat >= 0 and total > 0:
            expected = base + vat
            diff = abs(expected - total)
            if diff > Decimal('0.02'):
                return JsonResponse({
                    'ok': False,
                    'error': (
                        'Matematika računa nije ispravna. '
                        'Osnovica ({base}) + PDV ({vat}) = {expected}, '
                        'ali Ukupno je {total}. Razlika: {diff}. '
                        'Ispravite iznose.'
                    ).format(
                        base=base, vat=vat, expected=expected,
                        total=total, diff=diff,
                    ),
                    'code': 'MATH_MISMATCH',
                }, status=400)

        # ── Re-match partner after OIB correction ──
        header.matched_partner = None
        header.save()
        header.auto_match_partner()

        # ── Finalize ──
        header.needs_review = False
        header.confidence = max(header.confidence, 0.95)
        header.save(update_fields=[
            'supplier_name', 'supplier_oib', 'invoice_number',
            'invoice_date', 'total_amount', 'vat_amount', 'base_amount',
            'needs_review', 'confidence', 'matched_partner',
        ])

        # Update ImportBatch supplier if matched
        sf = header.staging_file
        if sf.result_batch and header.matched_partner:
            sf.result_batch.supplier = header.matched_partner
            sf.result_batch.save(update_fields=['supplier'])

    return JsonResponse({
        'ok': True,
        'header_id': header.pk,
        'matched_partner': header.matched_partner.name if header.matched_partner else None,
    })


@login_required
@require_POST
def review_discard(request):
    """Odbaci — označi staging fajl kao skipped."""
    from .models import StagingFile

    company = get_user_company(request)
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'ok': False, 'error': 'Invalid JSON'}, status=400)

    sf_id = data.get('sf_id')
    try:
        sf = StagingFile.objects.select_related('staging_batch').get(
            pk=sf_id, staging_batch__company=company,
        )
    except StagingFile.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'File ne postoji'}, status=404)

    sf.status = 'skipped'
    sf.ai_message = 'Odbačeno u Predkomori'
    sf.save(update_fields=['status', 'ai_message'])

    # Delete header too
    if hasattr(sf, 'header'):
        sf.header.delete()

    return JsonResponse({'ok': True})
