import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.models import BookingSignature
from permissions.decorators import require_permission

logger = logging.getLogger(__name__)
from django.db import DatabaseError, IntegrityError, transaction
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import permissions, viewsets

from core.company_utils import get_user_company

from .models import Invoice, InvoiceItem
from .serializers import InvoiceItemSerializer, InvoiceSerializer


# ── REST API
@extend_schema_view(list=extend_schema(tags=["Invoicing"]))
class InvoiceViewSet(viewsets.ModelViewSet):
    serializer_class = InvoiceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        from core.company_utils import get_user_company

        company = get_user_company(self.request)
        return (
            Invoice.objects.filter(company=company).select_related("storno_of", "business_location", "operator")
            if company
            else Invoice.objects.none()
        )


@extend_schema_view(list=extend_schema(tags=["Invoicing"]))
class InvoiceItemViewSet(viewsets.ModelViewSet):
    serializer_class = InvoiceItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        from core.company_utils import get_user_company

        company = get_user_company(self.request)
        return (
            InvoiceItem.objects.filter(invoice__company=company).select_related(
                "invoice", "tax_rate_obj", "inventory_item"
            )
            if company
            else InvoiceItem.objects.none()
        )


# ── LISTA RAČUNA
@login_required
def index(request):
    from django.utils import timezone

    today = timezone.now().date()
    # Auto-mark overdue (company-scoped)
    company = get_user_company(request)
    Invoice.objects.filter(company=company, status__in=["SENT", "UNPAID"], date_due__lt=today).update(status="OVERDUE")
    invoices = (
        Invoice.objects.filter(company=company)
        .select_related("pos_receipt")
        .prefetch_related("items")
        .order_by("-date_issued")
        if company
        else Invoice.objects.none()
    )
    status_filter = request.GET.get("status", "")
    country_filter = request.GET.get("country", "")
    doctype_filter = request.GET.get("doctype", "")
    search_q = request.GET.get("q", "").strip()
    sort_by = request.GET.get("sort", "-date_issued")
    year_filter = request.GET.get("year", "")
    year_filter_int = int(year_filter) if year_filter.isdigit() else None
    if status_filter:
        invoices = invoices.filter(status=status_filter)
    if country_filter:
        invoices = invoices.filter(country=country_filter)
    if doctype_filter:
        invoices = invoices.filter(doctype=doctype_filter)
    if year_filter:
        invoices = invoices.filter(synesis_year=int(year_filter))
    if search_q:
        from django.db.models import Q

        invoices = invoices.filter(
            Q(number__icontains=search_q)
            | Q(client_name__icontains=search_q)
            | Q(client_oib__icontains=search_q)
            | Q(note__icontains=search_q)
        )
    # Sorting
    allowed_sorts = {
        "date_issued": "date_issued",
        "-date_issued": "-date_issued",
        "total": "total",
        "-total": "-total",
        "number": "number",
        "-number": "-number",
        "client_name": "client_name",
        "-client_name": "-client_name",
    }
    sort_field = allowed_sorts.get(sort_by, "-date_issued")
    invoices = invoices.order_by(sort_field)
    from django.db.models import Sum

    all_inv = (
        Invoice.objects.filter(company=company).select_related("storno_of", "business_location", "operator")
        if company
        else Invoice.objects.none()
    )
    totals = {
        "total": all_inv.aggregate(s=Sum("total"))["s"] or 0,
        "unpaid": all_inv.filter(status__in=["UNPAID", "OVERDUE"]).aggregate(s=Sum("total"))["s"] or 0,
        "paid": all_inv.filter(status="PAID").aggregate(s=Sum("total"))["s"] or 0,
        "overdue": all_inv.filter(status="OVERDUE").count(),
        "draft": all_inv.filter(status="DRAFT").count(),
        "sent": all_inv.filter(status="SENT").count(),
        "quotes_total": all_inv.filter(doctype="PO").count(),
        "quotes_pending": all_inv.filter(doctype="PO", status__in=["DRAFT", "SENT"]).count(),
    }
    # Conversion rate (Z3)
    _total_q = totals["quotes_total"]
    _accepted_q = all_inv.filter(doctype="PO", status="ACCEPTED").count()
    totals["quote_conversion"] = round(_accepted_q / _total_q * 100, 1) if _total_q else 0
    totals["accepted_quotes"] = _accepted_q
    synesis_years = (
        Invoice.objects.filter(company=company, synesis_year__isnull=False)
        .values_list("synesis_year", flat=True)
        .distinct()
        .order_by("-synesis_year")
    )

    # ── POS daily aggregate (Simbioza Sprint 1) ──
    from django.db.models import Count as _Count
    from django.db.models import Sum as _Sum

    from pos.models import POSReceipt as _PR

    _pos_today = _PR.objects.filter(
        session__terminal__company=company, session__opened_at__date=today, status="paid"
    ).aggregate(total=_Sum("total"), count=_Count("id"))
    pos_total_today = _pos_today["total"] or 0
    pos_count_today = _pos_today["count"] or 0
    # Invoice today
    inv_today_agg = all_inv.filter(date_issued=today).aggregate(total=_Sum("total"), count=_Count("id"))
    inv_total_today = inv_today_agg["total"] or 0
    inv_count_today = inv_today_agg["count"] or 0
    combined_today = float(pos_total_today) + float(inv_total_today)

    return render(
        request,
        "invoicing/invoice_list.html",
        {
            "invoices": invoices[:200],
            "totals": totals,
            "today": today,
            "total_eur": totals["total"],
            "paid_eur": totals["paid"],
            "unpaid_eur": totals["unpaid"],
            "draft_count": totals["draft"],
            "status_filter": status_filter,
            "country_filter": country_filter,
            "doctype_filter": doctype_filter,
            "search_q": search_q,
            "sort_by": sort_by,
            "synesis_years": synesis_years,
            "year_filter": year_filter_int,
            "status_choices": Invoice.STATUS_CHOICES,
            "doctype_choices": Invoice.DOCTYPE_CHOICES,
            "pos_total_today": pos_total_today,
            "pos_count_today": pos_count_today,
            "inv_total_today": inv_total_today,
            "inv_count_today": inv_count_today,
            "combined_today": combined_today,
        },
    )


# ── GENERIRAJ QR KOD
def generate_qr(invoice):
    from invoicing.services.pdf_service import generate_qr as _gqr

    return _gqr(invoice)


# ── ZKI GENERIRANJE (HR Fiskalizacija - simulacija)
def generate_zki(invoice, cert_key="demo_key"):
    from invoicing.services.pdf_service import generate_zki as _gzki

    return _gzki(invoice, cert_key)


# ── PDF GENERIRANJE
@login_required
def generate_pdf(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    from invoicing.services.pdf_service import generate_invoice_pdf

    content, mime = generate_invoice_pdf(invoice, request)
    resp = HttpResponse(content, content_type=mime)
    resp["Content-Disposition"] = f'inline; filename="racun_{invoice.number}.pdf"'
    return resp


@login_required
def download_pdf(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    from invoicing.services.pdf_service import generate_invoice_pdf

    content, mime = generate_invoice_pdf(invoice)
    resp = HttpResponse(content, content_type=mime)
    resp["Content-Disposition"] = f'attachment; filename="racun_{invoice.number}.pdf"'
    return resp


def public_pdf(request, token):
    """Javni PDF endpoint — klijentski portal, bez login_required."""
    from django.core.cache import cache

    cache_key = f"pdf_throttle:{token}"
    if cache.get(cache_key):
        return HttpResponse("Previše zahtjeva. Pokušajte za 30 sekundi.", status=429)
    cache.set(cache_key, True, 30)
    invoice = get_object_or_404(Invoice, client_token=token)
    from invoicing.services.pdf_service import generate_invoice_pdf

    content, mime = generate_invoice_pdf(invoice, request)
    resp = HttpResponse(content, content_type=mime)
    resp["Content-Disposition"] = f'inline; filename="{invoice.number}.pdf"'
    return resp


@login_required
def send_email(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    from invoicing.services.email_service import send_invoice_email

    ok, msg = send_invoice_email(invoice)
    if ok:
        messages.success(request, _(msg))
    else:
        messages.error(request, _(msg))
    return redirect("invoicing:index")


@login_required
def send_invoice_whatsapp(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    phone = (invoice.partner.phone if invoice.partner else "") or invoice.client_email or ""
    if not phone:
        messages.error(request, _("Klijent nema broj telefona u sustavu."))
        return redirect("invoicing:index")
    portal_url = f"https://limit-connect.com/hr/invoicing/client/{invoice.client_token}/"
    doctype_names = {"PO": "Ponuda", "P": "Predračun", "R": "Račun", "A": "Avansni"}
    doc_name = doctype_names.get(invoice.doctype, "Dokument")
    msg = (
        f"❤️ *{doc_name} {invoice.number}*\n"
        f"Iznos: *{invoice.total} {invoice.currency}*\n"
        f"Datum: {invoice.date_issued.strftime('%d.%m.%Y') if invoice.date_issued else '-'}\n"
        f"\nPregled i potvrda: {portal_url}"
    )
    try:
        from core.whatsapp import send_text

        company = get_user_company(request)
        result = send_text(phone, msg, company_id=company.id if company else None)
        if result.get("success"):
            messages.success(request, _(f"WhatsApp poslan na {phone}!"))
        else:
            messages.warning(request, _(f"WhatsApp: {result.get('error', 'Greška')}. Kopirajte link: {portal_url}"))
    except ImportError:
        messages.warning(request, _(f"WhatsApp nije dostupan. Portal link: {portal_url}"))
    return redirect("invoicing:index")


@login_required
def generate_eracun(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    from invoicing.services.pdf_service import generate_eracun_xml

    xml = generate_eracun_xml(invoice)
    resp = HttpResponse(xml, content_type="application/xml; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="eracun_{invoice.number}.xml"'
    return resp


# ── FISKALIZACIJA (HR - produkcijska implementacija)
@login_required
def fiscalize(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    from invoicing.services import fiscalize_invoice as _fiscalize

    ip = (request.META.get("HTTP_X_FORWARDED_FOR", "") or "").split(",")[0].strip() or request.META.get(
        "REMOTE_ADDR", ""
    )
    result = _fiscalize(invoice, user=request.user, ip_address=ip)
    if result["success"]:
        if result.get("demo"):
            messages.success(request, _("Račun fiskaliziran (DEMO režim)!"))
            messages.warning(request, f"ZKI: {result['zki']} | JIR: {result['jir']}")
        else:
            messages.success(request, _("Račun uspješno fiskaliziran!"))
            messages.success(request, f"ZKI: {result['zki']} | JIR: {result['jir']}")
    else:
        messages.error(request, _("Fiskalizacija nije uspjela. Provjerite certifikat i vezu."))
    return redirect("invoicing:index")


# ── STORNO RAČUN
@require_permission("invoices.manage")
@transaction.atomic
@login_required
def storno(request, pk):
    original = get_object_or_404(Invoice, pk=pk)
    from invoicing.services import create_storno

    ip = (request.META.get("HTTP_X_FORWARDED_FOR", "") or "").split(",")[0].strip() or request.META.get(
        "REMOTE_ADDR", ""
    )
    cancel_reason = request.POST.get("cancel_reason", "").strip()[:200] if request.method == "POST" else ""
    result = create_storno(original, user=request.user, ip_address=ip, cancel_reason=cancel_reason)
    if result["success"]:
        messages.success(
            request,
            _("Storno račun {n} kreiran! Originalni račun je poništen.").format(n=result["storno_invoice"].number),
        )
        try:
            BookingSignature.log(
                request,
                "storno",
                target_model="Invoice",
                target_id=str(original.pk),
                target_repr=f"Storno {result['storno_invoice'].number} za {original.number}",
            )
        except (ValueError, TypeError):
            pass
        return redirect("invoicing:index")
    else:
        messages.error(request, result["message"])
        return redirect("invoicing:index")


# ── WORKFLOW: PONUDA → PREDRAČUN → RAČUN ──────────────────────────────────────


def _copy_invoice(source, new_doctype, new_number, extra_fields=None):
    from invoicing.services.invoice_service import copy_invoice

    return copy_invoice(source, new_doctype, new_number, extra_fields)


@transaction.atomic
@login_required
def convert_to_predracun(request, pk):
    """Ponuda → Predračun"""
    source = get_object_or_404(Invoice, pk=pk)

    if source.doctype != "PO":
        messages.error(request, _("Samo ponude se mogu pretvoriti u predračun!"))
        return redirect("invoicing:index")

    if Invoice.objects.unscoped().filter(source_document=source, doctype="P").exists():
        existing = Invoice.objects.unscoped().get(source_document=source, doctype="P")
        messages.warning(request, _(f"Predračun već postoji: {existing.number}"))
        return redirect("invoicing:invoice_edit", pk=existing.pk)

    from django.utils import timezone

    from .fiscal_models import FiscalConfig

    FiscalConfig.get()
    now = timezone.now()
    new_number = f"PR-{now.year}-{now.strftime('%m%d%H%M%S')}"

    new_doc = _copy_invoice(source, "P", new_number)
    new_doc.created_by = request.user
    new_doc.save()

    for item in source.items.all():
        InvoiceItem.objects.create(
            invoice=new_doc,
            description=item.description,
            quantity=item.quantity,
            unit=item.unit,
            unit_price=item.unit_price,
            discount_percent=item.discount_percent,
            total_price=item.total_price,
            tax_rate=item.tax_rate,
            tax_rate_obj=item.tax_rate_obj,
            inventory_item=item.inventory_item,
        )

    source.status = "ACCEPTED"
    source.save(update_fields=["status"])

    messages.success(request, _(f"Predračun {new_doc.number} kreiran iz ponude {source.number}!"))
    return redirect("invoicing:invoice_edit", pk=new_doc.pk)


@transaction.atomic
@login_required
def convert_to_invoice(request, pk):
    """Ponuda ili Predračun → Račun"""
    source = get_object_or_404(Invoice, pk=pk)

    if source.doctype not in ("PO", "P"):
        messages.error(request, _("Samo ponude ili predračuni se mogu pretvoriti u račun!"))
        return redirect("invoicing:index")

    if Invoice.objects.unscoped().filter(source_document=source, doctype="R").exists():
        existing = Invoice.objects.unscoped().get(source_document=source, doctype="R")
        messages.warning(request, _(f"Račun već postoji: {existing.number}"))
        return redirect("invoicing:invoice_edit", pk=existing.pk)

    from django.utils import timezone

    from .fiscal_models import FiscalConfig

    config = FiscalConfig.get()
    now = timezone.now()

    # Sljedeći broj računa
    last = Invoice.objects.unscoped().filter(doctype="R").order_by("-id").first()
    seq = (last.invoice_sequence + 1) if last else 1
    prefix = config.invoice_prefix_hr if config else "KNJ"
    new_number = f"{prefix}-{now.year}-{seq:04d}"

    new_doc = _copy_invoice(
        source,
        "R",
        new_number,
        {
            "invoice_sequence": seq,
            "date_due": (now + __import__("datetime").timedelta(days=30)).date(),
        },
    )
    new_doc.created_by = request.user
    new_doc.save()

    for item in source.items.all():
        InvoiceItem.objects.create(
            invoice=new_doc,
            description=item.description,
            quantity=item.quantity,
            unit=item.unit,
            unit_price=item.unit_price,
            discount_percent=item.discount_percent,
            total_price=item.total_price,
            tax_rate=item.tax_rate,
            tax_rate_obj=item.tax_rate_obj,
            inventory_item=item.inventory_item,
        )

    source.status = "ACCEPTED"
    source.save(update_fields=["status"])

    messages.success(request, _(f"Račun {new_doc.number} kreiran iz {source.get_doctype_display()} {source.number}!"))
    return redirect("invoicing:invoice_edit", pk=new_doc.pk)


@login_required
def mark_sent(request, pk):
    """Označi dokument kao poslan (DRAFT → SENT)."""
    doc = get_object_or_404(Invoice, pk=pk)
    if doc.status == "DRAFT":
        doc.status = "SENT"
        doc.save(update_fields=["status"])
        messages.success(request, _(f"{doc.get_doctype_display()} {doc.number} označen kao poslan."))
    else:
        messages.warning(request, _("Dokument nije u statusu Nacrt."))
    return redirect("invoicing:index")


@login_required
def mark_accepted(request, pk):
    """Označi ponudu/predračun kao prihvaćen (SENT → ACCEPTED)."""
    doc = get_object_or_404(Invoice, pk=pk)
    if doc.doctype in ("PO", "P") and doc.status in ("DRAFT", "SENT"):
        doc.status = "ACCEPTED"
        doc.save(update_fields=["status"])
        messages.success(request, _(f"{doc.get_doctype_display()} {doc.number} označen kao prihvaćen."))
    else:
        messages.warning(request, _("Nije moguće označiti kao prihvaćeno."))
    return redirect("invoicing:index")


@login_required
def mark_rejected(request, pk):
    """Označi ponudu kao odbijenu."""
    doc = get_object_or_404(Invoice, pk=pk)
    if doc.doctype in ("PO", "P") and doc.status not in ("PAID", "STORNO"):
        doc.status = "REJECTED"
        doc.save(update_fields=["status"])
        messages.success(request, _(f"{doc.get_doctype_display()} {doc.number} označen kao odbijen."))
    else:
        messages.warning(request, _("Nije moguće označiti kao odbijeno."))
    return redirect("invoicing:index")


# -- WIZARD ZA NOVI RACUN
@require_permission("invoices.create")
@login_required
def invoice_wizard(request):
    from .models import Invoice

    try:
        from .fiscal_models import BusinessLocation, FiscalConfig, FiscalOperator, InvoiceProfile

        locations = BusinessLocation.objects.filter(is_active=True).select_related("company", "branch")
        operators = FiscalOperator.objects.filter(is_active=True).select_related("user", "default_location")
        config = FiscalConfig.get()
    except DatabaseError:
        logger.warning("Suppressed error", exc_info=True)
        locations = []
        operators = []
        config = None
    from django.utils import timezone

    now = timezone.now()

    # Invoice profiles (filtered by company)
    from core.company_utils import get_user_company as _guc

    _co = _guc(request)
    profiles = (
        InvoiceProfile.objects.filter(is_active=True, company=_co).select_related(
            "default_tax_rate", "company", "branch"
        )
        if _co
        else InvoiceProfile.objects.filter(is_active=True)
    )
    default_profile = profiles.filter(is_default=True).first() or profiles.first()

    # Next number from default profile or fallback
    if default_profile:
        prefix = default_profile.invoice_prefix or "KNJ"
        next_num_int = default_profile.next_invoice_number or 1
        next_num = f"{prefix}-{now.year}-{next_num_int:04d}"
    else:
        last = Invoice.objects.order_by("-id").first()
        next_num = f"KNJ-{now.year}-{(last.id + 1 if last else 1):04d}"

    # ── from_receipt pre-fill (Simbioza Sprint 1) ──
    from_receipt_id = request.GET.get("from_receipt", "")
    prefill_receipt = None
    if from_receipt_id:
        try:
            from pos.models import POSReceipt

            prefill_receipt = POSReceipt.objects.select_related("session__terminal__company").get(
                pk=int(from_receipt_id), session__terminal__company=_co
            )
        except (ValueError, TypeError):
            prefill_receipt = None

    ctx = {
        "title": "Novi dokument - Wizard",
        "invoice": None,
        "items": [],
        "locations": locations,
        "operators": operators,
        "default_issuer": config,
        "default_iban": default_profile.iban if default_profile else (config.default_iban if config else ""),
        "next_number": next_num,
        "now_datetime": now.strftime("%Y-%m-%dT%H:%M"),
        "status_choices": Invoice.STATUS_CHOICES,
        "payment_choices": Invoice.PAYMENT_CHOICES,
        "profiles": profiles,
        "default_profile": default_profile,
        "doctype": request.GET.get("doctype", "R"),
        "prefill_receipt": prefill_receipt,
    }
    # Onboarding: check if company has inventory items
    from core.company_utils import get_user_company
    from inventory.models import InventoryItem

    _wb_company = get_user_company(request)
    ctx["has_items"] = (
        InventoryItem.objects.filter(company=_wb_company, is_active=True).exists() if _wb_company else False
    )
    ctx["company_name"] = _wb_company.name if _wb_company else ""
    return render(request, "invoicing/wizard.html", ctx)


# ── FORMA ZA NOVI/EDIT RAČUN
@require_permission("invoices.create")
@login_required
def invoice_create(request):
    from .models import Invoice

    try:
        from .fiscal_models import BusinessLocation, FiscalConfig, FiscalOperator

        locations = BusinessLocation.objects.filter(is_active=True).select_related("company", "branch")
        operators = FiscalOperator.objects.filter(is_active=True).select_related("user", "default_location")
        config = FiscalConfig.get()
    except DatabaseError:
        logger.warning("Suppressed error", exc_info=True)
        locations = []
        operators = []
        config = None

    from django.utils import timezone

    now = timezone.now()
    # Sljedeći broj računa
    last = Invoice.objects.order_by("-id").first()
    next_num = f"KNJ-{now.year}-{(last.id + 1 if last else 1):04d}"

    ctx = {
        "title": "Novi dokument",
        "invoice": None,
        "items": [],
        "locations": locations,
        "operators": operators,
        "default_issuer": config,
        "default_iban": config.default_iban if config else "",
        "next_number": next_num,
        "now_datetime": now.strftime("%Y-%m-%dT%H:%M"),
        "status_choices": Invoice.STATUS_CHOICES,
        "payment_choices": Invoice.PAYMENT_CHOICES,
    }
    return render(request, "invoicing/create.html", ctx)


@require_permission("invoices.create")
@login_required
def invoice_edit(request, pk):
    from .models import Invoice

    invoice = get_object_or_404(Invoice, pk=pk)
    if invoice.is_locked:
        messages.warning(
            request, _("Ovaj dokument je zaključan (Synesis arhiva). Za izmjene kontaktirajte administratora.")
        )
        return redirect("invoicing:index")
    try:
        from .fiscal_models import BusinessLocation, FiscalConfig, FiscalOperator

        locations = BusinessLocation.objects.filter(is_active=True).select_related("company", "branch")
        operators = FiscalOperator.objects.filter(is_active=True).select_related("user", "default_location")
        config = FiscalConfig.get()
    except DatabaseError:
        logger.warning("Suppressed error", exc_info=True)
        locations = []
        operators = []
        config = None

    # Build timeline steps
    STATUS_ORDER = ["DRAFT", "SENT", "ACCEPTED", "PAID"]
    STATUS_LABELS = {
        "DRAFT": "Nacrt",
        "SENT": "Poslano",
        "ACCEPTED": "Prihvaćeno",
        "PAID": "Plaćeno",
        "UNPAID": "Neplaćeno",
        "OVERDUE": "Dospijelo",
        "STORNO": "Storno",
        "CANCELLED": "Otkazano",
        "REJECTED": "Odbijeno",
    }
    gold = "#c9a84c"
    blue = "#3b82f6"
    gray = "#334155"
    curr_idx = STATUS_ORDER.index(invoice.status) if invoice.status in STATUS_ORDER else -1
    tl = []
    for i, sid in enumerate(STATUS_ORDER):
        if i < curr_idx:
            tl.append((sid, STATUS_LABELS[sid], gold))
        elif i == curr_idx:
            tl.append((sid, STATUS_LABELS[sid], blue))
        else:
            tl.append((sid, STATUS_LABELS[sid], gray))

    # Get partners and profile for the form
    from core.company_utils import get_user_company

    company = get_user_company(request)
    from partners.models import Partner

    partners = Partner.objects.filter(company=company) if company else Partner.objects.none()
    profile = None
    if not invoice.invoice_profile:
        try:
            from .fiscal_models import InvoiceProfile as _IP

            profile = _IP.get_default()
        except ImportError:
            profile = None

    ctx = {
        "title": f"Uredi: {invoice.number}",
        "invoice": invoice,
        "items": invoice.items.all(),
        "partners": partners,
        "active_company": company,
        "profile": invoice.invoice_profile or profile,
        "locations": locations,
        "operators": operators,
        "default_issuer": config,
        "default_iban": config.default_iban if config else "",
        "next_number": invoice.number,
        "now_datetime": invoice.date_issued.strftime("%Y-%m-%dT%H:%M") if invoice.date_issued else "",
        "status_choices": Invoice.STATUS_CHOICES,
        "payment_choices": Invoice.PAYMENT_CHOICES,
        "invoice_timeline": tl,
    }
    return render(request, "invoicing/create.html", ctx)


@require_permission("invoices.create")
@login_required
def invoice_save(request):
    if request.method != "POST":
        return redirect("invoicing:invoice_create")

    # Backend validation
    errors = []
    doctype = request.POST.get("doctype", "R")
    issuer_oib = request.POST.get("issuer_oib", "").strip()
    country = request.POST.get("country", "HR")

    # OIB validation for invoices and advance invoices (not offers/quotes)
    if doctype in ("R", "A") and country == "HR":
        if not issuer_oib:
            errors.append("OIB izdavatelja je obavezan za račun.")
        elif len(issuer_oib) == 11 and issuer_oib.isdigit():
            # MOD 11,10 checksum (ISO 7064)
            remainder = 10
            for digit in issuer_oib[:10]:
                remainder = (remainder + int(digit)) % 10
                if remainder == 0:
                    remainder = 10
                remainder = (remainder * 2) % 11
            check = (11 - remainder) % 10
            if check != int(issuer_oib[10]):
                errors.append("OIB izdavatelja nije valjan (neispravan kontrolni broj).")
        elif len(issuer_oib) != 11 or not issuer_oib.isdigit():
            errors.append("OIB izdavatelja mora imati 11 znamenki.")

    if errors:
        for err in errors:
            messages.error(request, f"❌ {err}")
        inv_id = request.POST.get("invoice_id")
        if inv_id:
            return redirect("invoicing:invoice_edit", pk=inv_id)
        return redirect("invoicing:invoice_create")

    from invoicing.services.invoice_service import save_invoice_from_post

    try:
        invoice = save_invoice_from_post(request)
        # Fix: populate issuer_phone from profile (invoice_service.py is root-owned)
        if invoice.invoice_profile and not invoice.issuer_phone:
            invoice.issuer_phone = getattr(invoice.invoice_profile, "phone", "") or ""
            invoice.save(update_fields=["issuer_phone"])
        for _, label in getattr(invoice, "_gobd_warnings", []):
            messages.warning(request, f'GoBD upozorenje: nedostaje "{label}"')
        # Success message with document type
        dtype_names = {
            "R": "Račun",
            "PO": "Ponuda",
            "P": "Predračun",
            "A": "Avansni račun",
            "S": "Storno",
            "GS": "Gutschrift",
        }
        dtype_name = dtype_names.get(invoice.doctype, "Dokument")
        is_new = not request.POST.get("invoice_id")
        if is_new:
            messages.success(request, f"✅ {dtype_name} {invoice.number} uspješno kreiran!")
            try:
                BookingSignature.log(
                    request,
                    "book",
                    target_model="Invoice",
                    target_id=str(invoice.pk),
                    target_repr=f"Kreiran {dtype_name} {invoice.number}",
                )
            except (ValueError, TypeError):
                pass
        else:
            messages.success(request, f"✅ {dtype_name} {invoice.number} uspješno ažuriran!")
            try:
                BookingSignature.log(
                    request,
                    "update",
                    target_model="Invoice",
                    target_id=str(invoice.pk),
                    target_repr=f"Ažuriran {dtype_name} {invoice.number}",
                )
            except (ValueError, TypeError):
                pass
            # ── FIX: InvoiceEvent za svaku izmjenu (GoBD §147, ZOR čl.9) ──
            try:
                from .models import InvoiceEvent

                _ip = (request.META.get("HTTP_X_FORWARDED_FOR", "") or "").split(",")[0].strip() or request.META.get(
                    "REMOTE_ADDR", ""
                )
                InvoiceEvent.objects.create(
                    invoice=invoice,
                    event_type="edited",
                    title="Izmjena dokumenta",
                    detail=f"Dokument {invoice.number} izmijenjen",
                    actor=request.user,
                    updated_by=request.user,
                    client_ip=_ip or None,
                )
            except (IntegrityError, DatabaseError) as _ev_err:
                logger.warning(f"InvoiceEvent edited failed: {_ev_err}")
    except (IntegrityError, DatabaseError):
        messages.error(
            request, _("Spremanje dokumenta nije uspjelo. Provjerite sva obavezna polja i pokušajte ponovo.")
        )
        logger.error("Invoice save error", exc_info=True)
        inv_id = request.POST.get("invoice_id")
        if inv_id:
            return redirect("invoicing:invoice_edit", pk=inv_id)
        return redirect("invoicing:invoice_create")
    return redirect("invoicing:invoice_edit", pk=invoice.pk)


# ── API ZA INVOICE PROFILE PRETRAGU
@login_required
def api_invoice_profiles(request):
    from .fiscal_models import InvoiceProfile

    profiles = InvoiceProfile.objects.filter(is_active=True).select_related("default_tax_rate", "company", "branch")
    data = []
    for p in profiles:
        data.append(
            {
                "id": p.id,
                "name": p.name,
                "country": p.country,
                "currency": p.currency,
                "language": p.language,
                "iban": p.iban,
                "swift": p.swift,
                "company_name": p.company_name,
                "oib": p.oib,
                "vat_id": p.vat_id,
                "address": p.address,
                "city": p.city,
                "zip_code": p.zip_code,
                "email": p.email,
                "phone": p.phone,
                "invoice_prefix": p.invoice_prefix,
                "default_due_days": p.default_due_days,
                "default_payment_method": p.default_payment_method,
                "is_default": p.is_default,
            }
        )
    from django.http import JsonResponse

    return JsonResponse(data, safe=False)


# ── API ZA PARTNER PRETRAGU
@login_required
def api_partners(request):
    q = request.GET.get("q", "")
    try:
        from partners.models import Partner

        company = get_user_company(request)
        if not company:
            return JsonResponse([], safe=False)
        qs = Partner.objects.filter(company=company)
        partners = qs.filter(name__icontains=q).values("id", "name", "oib", "email", "address", "city")[:10]
        return JsonResponse(list(partners), safe=False)
    except DatabaseError:
        logger.warning("Suppressed error", exc_info=True)
        return JsonResponse([], safe=False)


# -- API ZA ARTIKLE IZ INVENTARA
@login_required
def api_articles(request):
    q = request.GET.get("q", "")
    try:
        from inventory.models import InventoryItem

        qs = InventoryItem.objects.filter(is_active=True).select_related("tax_rate")
        if q:
            from django.db.models import Q

            qs = qs.filter(Q(name__icontains=q) | Q(sku__icontains=q))
        items = []
        for item in qs[:20]:
            items.append(
                {
                    "id": item.id,
                    "name": item.name,
                    "sku": item.sku,
                    "unit": item.unit,
                    "unit_price": float(item.unit_price),
                    "category": item.category,
                    "tax_rate": float(item.tax_rate.rate) if item.tax_rate else 25,
                    "quantity": float(item.quantity),
                }
            )
        return JsonResponse(items, safe=False)
    except (ValueError, TypeError):
        logger.warning("Suppressed error", exc_info=True)
        return JsonResponse([], safe=False)


# -- API ZA POREZNE STOPE PO DRZAVI
@login_required
def api_tax_rates(request):
    country = request.GET.get("country", "HR")
    try:
        from companies.models import TaxRate

        rates = TaxRate.objects.filter(country=country, is_active=True).order_by("-rate")
        data = [{"rate": float(r.rate), "name": r.name, "is_default": r.is_default} for r in rates]
        return JsonResponse(data, safe=False)
    except (ValueError, TypeError):
        logger.warning("Suppressed error", exc_info=True)
        # Fallback defaults
        if country == "DE":
            return JsonResponse(
                [
                    {"rate": 19, "name": "Regelsteuersatz", "is_default": True},
                    {"rate": 7, "name": "PDV 7% (Snižena)", "is_default": False},
                    {"rate": 0, "name": "PDV 0% (Oslobođeno)", "is_default": False},
                ],
                safe=False,
            )
        return JsonResponse(
            [
                {"rate": 25, "name": "Standardna", "is_default": True},
                {"rate": 13, "name": "Snižena (ugost.)", "is_default": False},
                {"rate": 5, "name": "Snižena (hrana/knj.)", "is_default": False},
                {"rate": 0, "name": "Oslobođeno", "is_default": False},
            ],
            safe=False,
        )


# ── DODAJ RADNE SATE NA RAČUN ─────────────────────────────────────────────
@transaction.atomic
@login_required
def invoice_add_hours(request, pk):
    """GET: return filtered unbilled time entries as JSON.
    POST: create InvoiceItem(s) and mark entries as billed."""
    from decimal import Decimal

    from worktime.models import TimeEntry

    try:
        invoice = Invoice.objects.get(pk=pk)
    except Invoice.DoesNotExist:
        from django.http import Http404

        raise Http404

    if request.method == "GET":
        qs = TimeEntry.objects.filter(status__in=["APPROVED", "PENDING"]).select_related(
            "user", "project", "project_lead"
        )

        # filters
        worker_id = request.GET.get("worker", "")
        date_from = request.GET.get("date_from", "")
        date_to = request.GET.get("date_to", "")
        lead_id = request.GET.get("lead", "")
        proj_id = request.GET.get("project", "")
        unbilled_only = request.GET.get("unbilled", "1")

        if worker_id:
            qs = qs.filter(user_id=worker_id)
        if date_from:
            qs = qs.filter(date__gte=date_from)
        if date_to:
            qs = qs.filter(date__lte=date_to)
        if lead_id:
            qs = qs.filter(project_lead_id=lead_id)
        if proj_id:
            qs = qs.filter(project_id=proj_id)
        if unbilled_only == "1":
            qs = qs.filter(is_billed=False)

        qs = qs.order_by("-date")[:200]

        from django.contrib.auth import get_user_model

        from burza.models import ProjectLead
        from worktime.models import Project as WProject

        entries = []
        for e in qs:
            dur = float(e.duration) if e.duration else 0
            billing = float(e.billing_amount) if e.billing_amount else 0
            rate = round(billing / dur, 2) if dur else 0
            entries.append(
                {
                    "id": e.pk,
                    "date": str(e.date),
                    "worker": e.user.get_full_name() or e.user.username,
                    "project": e.project.code + " – " + e.project.name if e.project else "–",
                    "lead": str(e.project_lead) if e.project_lead else "",
                    "description": e.description or "",
                    "hours": dur,
                    "rate": rate,
                    "total": billing,
                    "is_billed": e.is_billed,
                }
            )

        # dropdown options for filters
        User = get_user_model()
        workers = list(
            User.objects.filter(time_entries__isnull=False)
            .distinct()
            .values("id", "first_name", "last_name", "username")
        )
        projects = list(WProject.objects.filter(status="ACTIVE").values("id", "code", "name"))
        leads = list(ProjectLead.objects.filter(status__in=["PREUZETO", "RIJESENO"]).values("id", "title"))

        return JsonResponse(
            {
                "entries": entries,
                "workers": workers,
                "projects": projects,
                "leads": leads,
            }
        )

    # POST – add to invoice
    import json as _json

    try:
        body = _json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        logger.warning("Suppressed error", exc_info=True)
        body = request.POST.dict()

    mode = body.get("mode", "ZBIRNO")  # ZBIRNO or POJEDINACNO
    entry_ids = body.get("entry_ids", [])
    tax_rate = Decimal(str(body.get("tax_rate", "25")))

    if not entry_ids:
        return JsonResponse({"error": "Nema odabranih unosa"}, status=400)

    entries = TimeEntry.objects.filter(pk__in=entry_ids, is_billed=False).select_related("user", "project")
    if not entries.exists():
        return JsonResponse({"error": "Nema dostupnih unosa"}, status=400)

    if mode == "ZBIRNO":
        total_hours = sum(float(e.duration or 0) for e in entries)
        total_billing = sum(float(e.billing_amount or 0) for e in entries)
        avg_rate = round(total_billing / total_hours, 2) if total_hours else 0
        dates = sorted(set(str(e.date) for e in entries))
        period = f"{dates[0]} – {dates[-1]}" if len(dates) > 1 else dates[0] if dates else ""
        desc = f"Radni sati {period}"
        item = InvoiceItem(
            invoice=invoice,
            description=desc,
            quantity=Decimal(str(round(total_hours, 2))),
            unit="h",
            unit_price=Decimal(str(avg_rate)),
            tax_rate=tax_rate,
        )
        item.save()
    else:
        for e in entries:
            dur = float(e.duration or 0)
            billing = float(e.billing_amount or 0)
            rate = round(billing / dur, 2) if dur else 0
            worker = e.user.get_full_name() or e.user.username
            proj = e.project.code if e.project else ""
            desc = f"{worker} · {proj} · {e.date}"
            if e.description:
                desc += f" · {e.description[:60]}"
            item = InvoiceItem(
                invoice=invoice,
                description=desc,
                quantity=Decimal(str(round(dur, 2))),
                unit="h",
                unit_price=Decimal(str(rate)),
                tax_rate=tax_rate,
            )
            item.save()

    # Mark entries billed and link to invoice
    entries.update(is_billed=True, invoice=invoice)

    # Recalculate invoice totals
    invoice.recalculate()
    invoice.save()

    return JsonResponse({"ok": True, "added": len(entry_ids)})


def _notify_quote_action(invoice, action: str):
    """
    Globalna notifikacija — šalje email + WhatsApp vlasniku firme
    kad klijent prihvati ili odbije ponudu iz client portala.
    Radi za sve kompanije automatski.
    """
    import logging

    log = logging.getLogger("invoicing.notify")

    action_map = {
        "accepted": ("✅", "prihvaćena", "angenommen"),
        "rejected": ("❌", "odbijena", "abgelehnt"),
        "undo_accepted": ("↩", "prihvaćanje opozvano", "Bestätigung zurückgezogen"),
    }
    emoji, verb_hr, verb_de = action_map.get(action, ("ℹ️", action, action))

    # ── Pronađi kontakt podatke kompanije ──────────────────────
    company = invoice.company
    admin_phones = []
    admin_emails = []

    # 1. Company email / phone
    if getattr(company, "email", None):
        admin_emails.append(company.email)
    if getattr(company, "phone", None):
        admin_phones.append(company.phone)

    # 2. Admin/owner UserProfile za tu firmu
    try:
        from accounts.models import UserProfile

        admins = (
            UserProfile.objects.filter(
                company=company,
                user__is_active=True,
            )
            .select_related("user")
            .order_by("-user__is_staff", "id")[:3]
        )

        for up in admins:
            if up.phone and up.phone not in admin_phones:
                admin_phones.append(up.phone)
            if up.user.email and up.user.email not in admin_emails:
                admin_emails.append(up.user.email)
    except DatabaseError as e:
        log.warning("notify: cannot fetch admin profiles: %s", e)

    portal_url = f"https://limit-connect.com/hr/invoicing/{invoice.pk}/edit/"

    # ── WhatsApp ────────────────────────────────────────────────
    wa_msg = (
        f"{emoji} *Ponuda {verb_hr}!*\n\n"
        f"Broj: {invoice.number}\n"
        f"Klijent: {invoice.client_name}\n"
        f"Iznos: {invoice.total} {invoice.currency}\n\n"
        f"👉 {portal_url}"
    )

    try:
        from core.whatsapp import normalize_phone, send_text

        for phone in admin_phones:
            if phone and len(phone) >= 8:
                normalized = normalize_phone(phone)
                send_text(normalized, wa_msg)
                log.info("notify WA sent to %s for %s (%s)", normalized, invoice.number, action)
    except ImportError as e:
        log.error("notify WhatsApp failed: %s", e)

    # ── Email ───────────────────────────────────────────────────
    try:
        from django.conf import settings
        from django.core.mail import send_mail

        subject = f"{emoji} Ponuda {invoice.number} — {verb_hr} ({invoice.client_name})"
        body = (
            f"Ponuda je {verb_hr}.\n\n"
            f"Broj: {invoice.number}\n"
            f"Klijent: {invoice.client_name}\n"
            f"Iznos: {invoice.total} {invoice.currency}\n"
            f"Datum: {invoice.date_issued.strftime('%d.%m.%Y.')}\n\n"
            f"Otvori u panelu:\n{portal_url}\n\n"
            f"---\n"
            f"Automatska poruka — LIMIT Connect"
        )

        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@limit-connect.com")

        if admin_emails:
            send_mail(
                subject=subject,
                message=body,
                from_email=from_email,
                recipient_list=admin_emails,
                fail_silently=True,
            )
            log.info("notify email sent to %s for %s (%s)", admin_emails, invoice.number, action)
    except ImportError as e:
        log.error("notify email failed: %s", e)


# ── CLIENT PORTAL (no login) ──────────────────────────────────────────────────
def client_portal(request, token):
    invoice = get_object_or_404(Invoice, client_token=token)

    # Aktiviraj jezik prema državi kupca (HR→hr, DE→de)
    from django.utils.translation import activate

    lang_map = {"HR": "hr", "DE": "de"}
    activate(lang_map.get(invoice.country, "hr"))

    # Track views
    invoice.view_count += 1
    if not invoice.first_viewed_at:
        invoice.first_viewed_at = timezone.now()
    update_fields = ["view_count", "first_viewed_at"]
    if invoice.status == "SENT" and not invoice.first_viewed_at:
        pass  # Keep SENT — already viewed tracking via first_viewed_at
    invoice.save(update_fields=update_fields)

    if request.method == "POST" and invoice.status in ("DRAFT", "SENT", "ACCEPTED", "REJECTED"):
        action = request.POST.get("action")
        if action == "accept":
            invoice.status = "ACCEPTED"
            invoice.save(update_fields=["status"])
            _notify_quote_action(invoice, "accepted")
            messages.success(request, _("Hvala! Vaša potvrda je zabilježena. Kontaktirat ćemo vas uskoro."))

        elif action == "reject":
            invoice.status = "REJECTED"
            invoice.save(update_fields=["status"])
            _notify_quote_action(invoice, "rejected")
            messages.info(request, _("Ponuda je odbijena. Slobodno nas kontaktirajte za prilagodbu."))

        elif action == "undo_accept" and invoice.status == "ACCEPTED":
            # Klijent je slučajno prihvatio — vraća se na SENT
            invoice.status = "SENT"
            invoice.save(update_fields=["status"])
            _notify_quote_action(invoice, "undo_accepted")
            messages.info(request, _("Prihvaćanje je opozvano. Ponuda je aktivna — možete ponovo odlučiti."))

        elif action == "undo_reject" and invoice.status == "REJECTED":
            # Klijent se predomislio — direktno prihvaća
            invoice.status = "ACCEPTED"
            invoice.save(update_fields=["status"])
            _notify_quote_action(invoice, "accepted")
            messages.success(request, _("Odlično! Ponuda je prihvaćena. Kontaktirat ćemo vas uskoro."))
        return redirect(request.path)

    # Dohvati sekcije za renderiranje (ista logika kao PDF)
    from invoicing.services.pdf_service import build_sections

    try:
        sections = build_sections(invoice)
    except Exception:
        sections = [{"name": "", "items": list(invoice.items.all()), "subtotal": invoice.subtotal}]

    # Razdvoji radove i materijal za ponude
    all_items = invoice.items.all().order_by("section", "sort_order")
    work_items = all_items.filter(item_type="work")
    material_items = all_items.filter(item_type="material")
    work_total = sum(i.total_price for i in work_items)
    material_total = sum(i.total_price for i in material_items)
    has_split = work_items.exists() and material_items.exists()

    return render(
        request,
        "invoicing/client_portal.html",
        {
            "invoice": invoice,
            "items": all_items,
            "sections": sections,
            "can_accept": invoice.doctype == "PO" and invoice.status in ("DRAFT", "SENT"),
            "work_items": work_items,
            "material_items": material_items,
            "work_total": work_total,
            "material_total": material_total,
            "has_split": has_split,
        },
    )


# ── CLONE INVOICE ─────────────────────────────────────────────────────────────────────────────
@transaction.atomic
@login_required
def invoice_clone(request, pk):
    src = get_object_or_404(Invoice, pk=pk)
    from django.utils import timezone

    now = timezone.now()
    # Prefix po doctype — ne uvijek KNJ
    prefix_map = {"PO": "PO", "P": "PR", "R": "KNJ", "A": "AV", "GS": "GS", "FA": "FA"}
    prefix = prefix_map.get(src.doctype, "KNJ")
    new_num = f"{prefix}-{now.year}-{now.strftime('%m%d%H%M%S')}"
    clone = _copy_invoice(
        src,
        src.doctype,
        new_num,
        extra_fields={
            "source": "duplicate",
            "status": "DRAFT",
            "validity_date": None,
            "is_fiscalized": False,
            "zki": None,
            "jir": None,
        },
    )
    clone.created_by = request.user
    clone.status = "DRAFT"
    clone.save()
    for item in src.items.all():
        InvoiceItem.objects.create(
            invoice=clone,
            description=item.description,
            quantity=item.quantity,
            unit=item.unit,
            unit_price=item.unit_price,
            discount_percent=item.discount_percent,
            total_price=item.total_price,
            tax_rate=item.tax_rate,
            tax_rate_obj=item.tax_rate_obj,
            inventory_item=item.inventory_item,
        )
    clone.recalculate()
    clone.save()
    messages.success(request, _("Kopija kreirana: {n}. Možete je urediti i poslati.").format(n=clone.number))
    return redirect("invoicing:invoice_edit", pk=clone.pk)


# ── API ZA UVOZ IZ MODULA
@login_required
def api_import(request, module):
    data = []
    try:
        if module == "worktime":
            from worktime.models import TimeEntry

            entries = (
                TimeEntry.objects.filter(status="APPROVED", is_billed=False)
                .select_related("user", "project")
                .order_by("-date")[:30]
            )
            for e in entries:
                try:
                    rate = float(e.user.employeeprofile.hourly_rate)
                except (ValueError, TypeError):
                    logger.warning("Suppressed error", exc_info=True)
                    rate = float(e.project.hourly_rate) if e.project else 25.0
                data.append(
                    {
                        "title": f"Radni sati – {e.project.name if e.project else 'Opće'} ({e.user.get_full_name() or e.user.username})",
                        "subtitle": str(e.date),
                        "quantity": float(e.duration),
                        "unit": "h",
                        "price": rate,
                        "pdv": 25,
                        "client_name": "",
                    }
                )
        elif module == "rental":
            from rental.models import Booking

            bookings = (
                Booking.objects.filter(status="completed")
                .select_related("property", "guest")
                .order_by("-check_in")[:20]
            )
            for b in bookings:
                data.append(
                    {
                        "title": f"Najam – {b.property.name}",
                        "subtitle": f"{b.check_in} – {b.check_out}",
                        "quantity": 1,
                        "unit": "usl",
                        "price": float(b.total_price) if hasattr(b, "total_price") else 0,
                        "pdv": 13,
                        "client_name": b.guest.name if hasattr(b, "guest") and b.guest else "",
                    }
                )
        elif module == "appointments":
            from appointments.models import Appointment

            apts = Appointment.objects.filter(status="completed").order_by("-start_time")[:20]
            for a in apts:
                data.append(
                    {
                        "title": f"Termin – {a.title}",
                        "subtitle": str(a.start_time)[:16] if a.start_time else "",
                        "quantity": 1,
                        "unit": "usl",
                        "price": float(a.price) if hasattr(a, "price") else 0,
                        "pdv": 25,
                    }
                )
        elif module == "webshop":
            from webshop.models import Order

            orders = Order.objects.filter(status="completed").order_by("-created_at")[:20]
            for o in orders:
                data.append(
                    {
                        "title": f"Webshop narudžba #{o.id}",
                        "subtitle": str(o.created_at)[:16] if o.created_at else "",
                        "quantity": 1,
                        "unit": "kom",
                        "price": float(o.total) if hasattr(o, "total") else 0,
                        "pdv": 25,
                    }
                )
        elif module == "projects":
            from projects.models import Project

            projects = Project.objects.filter(status="active").select_related("client")[:20]
            for p in projects:
                data.append(
                    {
                        "title": f"Projekt – {p.name}",
                        "subtitle": p.code,
                        "quantity": 1,
                        "unit": "usl",
                        "price": float(p.budget) if p.budget else 0,
                        "pdv": 25,
                        "client_name": str(p.client) if p.client else "",
                    }
                )
    except Exception as e:
        logger.exception("Unexpected error", exc_info=True)
        pass
    return JsonResponse(data, safe=False)


# ── UREDSKI WIZARD (desktop, za racunovodstvo)
@login_required
def invoice_office_wizard(request):
    """Desktop 5-step invoice wizard for office/accounting staff."""
    from core.company_utils import get_user_company as _guc2

    from .fiscal_models import BusinessLocation, FiscalOperator, InvoiceProfile

    _co2 = _guc2(request)
    profiles = (
        InvoiceProfile.objects.filter(is_active=True, company=_co2)
        .select_related("default_tax_rate", "company", "branch")
        .order_by("-is_default", "company_name")
        if _co2
        else InvoiceProfile.objects.filter(is_active=True).order_by("-is_default", "company_name")
    )
    default_profile = InvoiceProfile.get_default()
    locations = (
        BusinessLocation.objects.filter(company=_co2).select_related("company", "branch")
        if _co2
        else BusinessLocation.objects.none()
    )
    operators = FiscalOperator.objects.all().select_related(
        "user", "default_location"
    )  # FiscalOperator has no company FK — global
    country = "HR"
    if default_profile:
        country = default_profile.country or "HR"
    return render(
        request,
        "invoicing/office_wizard.html",
        {
            "profiles": profiles,
            "default_profile": default_profile,
            "locations": locations,
            "operators": operators,
            "country": country,
        },
    )


# ── TERENSKI WIZARD (mobilni, za majstore)
@login_required
def invoice_field_wizard(request):
    """Mobile-first 4-step invoice wizard for field workers."""
    from .fiscal_models import InvoiceProfile

    profile = InvoiceProfile.get_default()
    country = "HR"
    issuer_name = ""
    issuer_address = ""
    if profile:
        country = profile.country or "HR"
        issuer_name = profile.company_name or ""
        issuer_address = f"{profile.address or ''}, {profile.zip_code or ''} {profile.city or ''}".strip(", ")
    return render(
        request,
        "invoicing/field_wizard.html",
        {
            "country": country,
            "issuer_name": issuer_name,
            "issuer_address": issuer_address,
        },
    )


# ── API: FIELD CREATE (terenski wizard POST)
@login_required
def api_field_create(request):
    """POST endpoint for field wizard — thin view, delegates to DocumentEntry."""
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "POST required"}, status=405)

    import datetime
    from decimal import Decimal, InvalidOperation

    from invoicing.services.entry_point import DocumentEntry

    from .fiscal_models import InvoiceProfile

    try:
        profile = InvoiceProfile.get_default()
        action = request.POST.get("action", "draft")
        country = request.POST.get("country", "HR")

        # ── 1. Prepare document data ──
        status_map = {"draft": "DRAFT", "issued": "SENT", "email": "SENT", "paid": "PAID"}

        doc_data = {
            "doctype": "R",
            "country": country,
            "date_issued": timezone.now(),
            "date_due": (timezone.now() + datetime.timedelta(days=15)).date(),
            "client_name": request.POST.get("client_name", ""),
            "client_address": request.POST.get("client_address", ""),
            "client_city": request.POST.get("client_city", ""),
            "client_oib": request.POST.get("client_oib", ""),
            "client_email": request.POST.get("client_email", ""),
            "client_country": "Deutschland" if country == "DE" else "Hrvatska",
            "payment_method": "GOTOVINA" if action == "paid" else "TRANSAKCIJSKI",
            "currency": "EUR",
            "note": request.POST.get("note", ""),
            "status": status_map.get(action, "DRAFT"),
        }

        # Profile-based numbering
        if profile:
            doc_data["invoice_profile"] = profile
            doc_data["number"] = profile.get_next_number("R")
            doc_data["issuer_name"] = profile.company_name
            doc_data["issuer_address"] = (
                f"{profile.address or ''}, {profile.zip_code or ''} {profile.city or ''}".strip(", ")
            )
            doc_data["issuer_oib"] = profile.oib or profile.vat_id or ""
            doc_data["issuer_email"] = profile.email or ""
            doc_data["issuer_iban"] = profile.iban or ""
            doc_data["swift"] = profile.swift or ""

        # Partner link
        partner_id = request.POST.get("partner_id")
        if partner_id:
            try:
                from partners.models import Partner

                doc_data["partner"] = Partner.objects.get(pk=partner_id)
            except ObjectDoesNotExist:
                pass

        # Work description
        work_desc = request.POST.get("work_description", "")
        if work_desc:
            doc_data["internal_note"] = f"[Teren] {request.POST.get('work_category', '')}: {work_desc}"

        # Photo
        if request.FILES.get("photo"):
            doc_data["photo"] = request.FILES["photo"]

        # ── 2. Parse items from POST arrays ──
        items = []
        descs = request.POST.getlist("item_desc[]")
        qtys = request.POST.getlist("item_qty[]")
        units = request.POST.getlist("item_unit[]")
        prices = request.POST.getlist("item_price[]")
        pdvs = request.POST.getlist("item_pdv[]")

        for i, desc in enumerate(descs):
            if not desc.strip():
                continue
            try:
                items.append(
                    {
                        "description": desc,
                        "quantity": Decimal(str(qtys[i]).replace(",", ".")) if i < len(qtys) else Decimal("1"),
                        "unit": units[i] if i < len(units) else "kom",
                        "unit_price": Decimal(str(prices[i]).replace(",", ".")) if i < len(prices) else Decimal("0"),
                        "tax_rate": Decimal(str(pdvs[i])) if i < len(pdvs) else Decimal("25"),
                        "discount_percent": Decimal("0"),
                    }
                )
            except (InvalidOperation, IndexError, ValueError):
                continue

        # ── 3. DocumentEntry creates everything atomically ──
        ip = (request.META.get("HTTP_X_FORWARDED_FOR", "") or "").split(",")[0].strip() or request.META.get(
            "REMOTE_ADDR", ""
        )
        company = get_user_company(request)

        entry = DocumentEntry(company=company, created_by=request.user, source="wizard_field", ip_address=ip)
        result = entry.create(doc_data, items)

        # ── 4. Post-creation: email if requested ──
        if action == "email" and result.invoice and result.invoice.client_email:
            try:
                from core.email_tasks import send_email_with_attachment_task

                send_email_with_attachment_task.delay(result.invoice.pk)
            except ImportError:
                pass

        return JsonResponse(
            {
                "success": result.success,
                "invoice_id": result.invoice.pk if result.invoice else None,
                "number": result.invoice.number if result.invoice else "",
                "total": float(result.invoice.total) if result.invoice else 0,
                "fiscal_status": result.fiscal.success if result.fiscal else None,
                "jir": result.fiscal.jir if result.fiscal else None,
            }
        )

    except (ValueError, TypeError) as e:
        logger.exception("api_field_create error")
        return JsonResponse({"success": False, "error": str(e)}, status=500)


# ── API: GRID EDITOR ─ AJAX ENDPOINTS
@login_required
def api_update_item(request, pk):
    """PATCH endpoint to update a single InvoiceItem inline."""
    if request.method != "PATCH":
        return JsonResponse({"success": False, "error": "PATCH required"}, status=405)

    import json
    from decimal import Decimal

    from .models import InvoiceItem

    try:
        item = InvoiceItem.objects.select_related("invoice").get(pk=pk)
    except InvoiceItem.DoesNotExist:
        return JsonResponse({"success": False, "error": "Item not found"}, status=404)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON"}, status=400)

    # Update only provided fields
    if "description" in data:
        item.description = data["description"]
    if "quantity" in data:
        item.quantity = Decimal(str(data["quantity"]).replace(",", "."))
    if "unit" in data:
        item.unit = data["unit"]
    if "unit_price" in data:
        item.unit_price = Decimal(str(data["unit_price"]).replace(",", "."))
    if "discount_percent" in data:
        item.discount_percent = Decimal(str(data["discount_percent"]).replace(",", "."))
    if "tax_rate" in data:
        item.tax_rate = Decimal(str(data["tax_rate"]))

    item.save()  # auto-calculates total_price and gross_total

    # Recalculate invoice totals
    invoice = item.invoice
    invoice.recalculate()
    invoice.save()

    return JsonResponse(
        {
            "success": True,
            "item": {
                "id": item.pk,
                "total_price": float(item.total_price),
                "gross_total": float(item.gross_total),
            },
            "invoice": {
                "subtotal": float(invoice.subtotal),
                "tax_amount": float(invoice.tax_amount),
                "total": float(invoice.total),
            },
        }
    )


@login_required
def api_update_invoice(request, pk):
    """PATCH endpoint to update invoice header fields."""
    if request.method != "PATCH":
        return JsonResponse({"success": False, "error": "PATCH required"}, status=405)

    import json

    from .models import Invoice

    try:
        Invoice.objects.get(pk=pk)
    except Invoice.DoesNotExist:
        return JsonResponse({"success": False, "error": "Invoice not found"}, status=404)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON"}, status=400)

    allowed_fields = [
        "client_name",
        "client_address",
        "client_city",
        "client_oib",
        "client_email",
        "note",
        "internal_note",
        "payment_method",
        "reference_number",
        "date_due",
        "date_delivery",
    ]

    for field in allowed_fields:
        if field in data:
            data[field]


@login_required
def api_oib_lookup(request):
    """
    AJAX: Dohvati podatke firme po OIB-u / VAT ID-u.
    Koristi centralni core.business_lookup servis (VIES + FINA Info.BIZ).
    Poziva se iz forme za novi račun i predračun.
    """
    oib = request.GET.get("oib", "").strip()
    country = request.GET.get("country", "HR").strip().upper()[:2]
    if not oib:
        return JsonResponse({"error": "OIB je obavezan"}, status=400)
    from core.oib_validator import validate_vat_id

    if not validate_vat_id(oib, country):
        return JsonResponse({"error": "Neispravan OIB/VAT format", "valid_format": False}, status=400)
    company = get_user_company(request)
    from core.business_lookup import lookup_business

    result = lookup_business(oib, country, company=company)
    return JsonResponse(result.to_dict())


@login_required
def api_partner_hint(request):
    """
    AI Partner Assistant — bez Geminija, cisti ORM.
    Vraca povijest suradnje s partnerom za pametno popunjavanje fakture.
    """
    oib = request.GET.get("oib", "").strip()
    if not oib:
        return JsonResponse({"hint": None})

    company = get_user_company(request)
    from django.db.models import Avg, Count

    qs = Invoice.objects.filter(company=company, client_oib=oib).select_related(
        "storno_of", "business_location", "operator"
    )

    if not qs.exists():
        return JsonResponse({"hint": None, "msg": "Novi partner — nema povijesti"})

    total_count = qs.count()
    unpaid_count = qs.filter(status__in=["UNPAID", "OVERDUE"]).count()

    # Top artikli ovog partnera
    from invoicing.models import InvoiceItem

    top_items = list(
        InvoiceItem.objects.filter(invoice__company=company, invoice__client_oib=oib)
        .values("description")
        .annotate(cnt=Count("id"), avg_price=Avg("unit_price"))
        .order_by("-cnt")[:3]
    )
    # Serialize Decimal to float
    for item in top_items:
        item["avg_price"] = float(item["avg_price"] or 0)

    last_inv = qs.order_by("-created_at").first()

    warning = None
    if unpaid_count >= 3:
        warning = f"{unpaid_count} neplacenih racuna!"
    elif unpaid_count >= 1:
        warning = f"{unpaid_count} neplacen racun"

    return JsonResponse(
        {
            "hint": {
                "total_invoices": total_count,
                "unpaid_count": unpaid_count,
                "warning": warning,
                "last_doctype": last_inv.doctype if last_inv else "R",
                "last_currency": last_inv.currency if last_inv else "EUR",
                "last_payment_method": getattr(last_inv, "payment_method", "TRANSAKCIJSKI")
                if last_inv
                else "TRANSAKCIJSKI",
                "top_items": top_items,
                "partner_name": last_inv.client_name if last_inv else "",
            }
        }
    )


def email_tracking_pixel(request, token):
    """1x1 transparent GIF tracking pixel with HMAC verification."""
    import hashlib
    import hmac

    GIF = bytes.fromhex("47494638396101000100800000ffffff00000021f90400000000002c00000000010001000002024401003b")
    resp = HttpResponse(GIF, content_type="image/gif")
    resp["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp["Pragma"] = "no-cache"
    resp["Expires"] = "0"
    try:
        # Token format: {pk}.{hmac_hex[:16]}
        parts = token.rsplit(".", 1)
        if len(parts) != 2:
            return resp
        pk_str, sig = parts
        expected = hmac.new(settings.SECRET_KEY[:32].encode(), pk_str.encode(), hashlib.sha256).hexdigest()[:16]
        if not hmac.compare_digest(sig, expected):
            return resp
        pk = int(pk_str)
        from django.utils import timezone

        from documents.models import ArhivaEntry

        ArhivaEntry.objects.filter(pk=pk).update(
            email_opened_at=models.Case(
                models.When(email_opened_at__isnull=True, then=models.Value(timezone.now())),
                default=models.F("email_opened_at"),
            ),
            email_open_count=models.F("email_open_count") + 1,
        )
    except (ValueError, TypeError):
        pass
    return resp


@login_required
def api_nkd_search(request):
    """
    AJAX: Pretraga NKD šifarnika za select2 dropdown na fakturi/partneru.
    ?q=trgovina  →  [{"code":"46.90","name":"Nespecijalizirana trgovina na veliko"}]
    """
    q = request.GET.get("q", "").strip()
    from core.business_lookup import get_nkd_choices_for_select

    results = get_nkd_choices_for_select(q, limit=20)
    return JsonResponse({"results": results})


# ── Stub views (referenced in urls.py, to be implemented) ──────────


@login_required
def api_delete_item(request, pk):
    from invoicing.models import InvoiceItem

    item = get_object_or_404(InvoiceItem, pk=pk)
    # Synesis archive protection
    if item.invoice.is_locked:
        return JsonResponse({"error": "Synesis arhiva - stavke zaključane"}, status=403)
    invoice_pk = item.invoice_id
    item.delete()
    return JsonResponse({"ok": True, "invoice_pk": invoice_pk})


@login_required
def api_add_item(request, pk):
    return JsonResponse({"error": "Not implemented yet"}, status=501)


@login_required
def api_update_status(request, pk):
    return JsonResponse({"error": "Not implemented yet"}, status=501)


@login_required
def api_tax_calculate(request):
    return JsonResponse({"error": "Not implemented yet"}, status=501)


@login_required
def api_worktime_entries(request):
    return JsonResponse({"entries": []})


@login_required
def fiscal_batch_view(request):
    from invoicing.fiscal_models import FiscalBatch

    company = getattr(getattr(request.user, "profile", None), "company", None)
    unfiscalized = []
    batches = []
    if company:
        unfiscalized = list(
            Invoice.objects.filter(
                company=company,
                doctype="R",
                status__in=["SENT", "PAID"],
                is_fiscalized=False,
            ).order_by("-date_issued")[:200]
        )
        batches = (
            FiscalBatch.objects.filter(company=company)
            .select_related("company", "created_by", "invoices")
            .order_by("-created_at")[:50]
        )
    return render(
        request,
        "invoicing/fiscal_batch.html",
        {
            "unfiscalized": unfiscalized,
            "batches": batches,
        },
    )


@login_required
def fiscal_batch_list(request):
    return fiscal_batch_view(request)


@login_required
def fiscal_batch_create(request):
    if request.method != "POST":
        return redirect("invoicing:fiscal_batch")
    from django.contrib import messages as _msg
    from django.utils import timezone as _tz

    from invoicing.fiscal_models import FiscalBatch
    from invoicing.fiscalization import send_to_cis

    company = getattr(getattr(request.user, "profile", None), "company", None)
    invoice_ids = request.POST.getlist("invoice_ids")
    if not invoice_ids:
        _msg.warning(request, "Nisu odabrani racuni za fiskalizaciju.")
        return redirect("invoicing:fiscal_batch")
    invoices = list(
        Invoice.objects.filter(pk__in=invoice_ids, company=company, is_fiscalized=False).select_related(
            "storno_of", "business_location", "operator"
        )
    )
    already_done = len(invoice_ids) - len(invoices)
    if not invoices:
        _msg.warning(request, "Svi odabrani racuni su vec fiskalizirani.")
        return redirect("invoicing:fiscal_batch")
    batch = FiscalBatch.objects.create(
        company=company, created_by=request.user, status="processing", total_count=len(invoices), started_at=_tz.now()
    )
    batch.invoices.set(invoices)
    results = {}
    success = errors = 0
    for inv in invoices:
        try:
            res = send_to_cis(inv)
            if res.get("ok"):
                success += 1
                results[str(inv.pk)] = {"ok": True, "jir": res.get("jir", "")}
            else:
                errors += 1
                results[str(inv.pk)] = {"ok": False, "error": res.get("error", "Greska")}
        except (ValueError, TypeError) as e:
            errors += 1
            results[str(inv.pk)] = {"ok": False, "error": str(e)}
    batch.success_count = success
    batch.error_count = errors
    batch.results_json = results
    batch.completed_at = _tz.now()
    batch.status = "completed" if errors == 0 else ("partial" if success > 0 else "failed")
    batch.save()
    if success:
        _msg.success(request, f"Fiskalizirano {success}/{len(invoices)} racuna.")
    if errors:
        _msg.error(request, f"{errors} racuna nije uspjelo.")
    if already_done:
        _msg.warning(request, f"{already_done} racun(a) preskoceno.")
    return redirect("invoicing:fiscal_batch")


@login_required
def fiscal_certificates(request):
    from invoicing.fiscal_models import FiscalCertificate

    company = getattr(getattr(request.user, "profile", None), "company", None)
    certs = FiscalCertificate.objects.filter(company=company).select_related("company", "location") if company else []
    return render(request, "invoicing/fiscal_certificates.html", {"certs": certs, "company": company})


@login_required
def fiscal_certificate_upload(request):
    if request.method != "POST":
        return redirect("invoicing:fiscal_certificates")
    from django.contrib import messages as _msg

    from invoicing import cert_manager
    from invoicing.fiscal_models import FiscalCertificate

    company = getattr(getattr(request.user, "profile", None), "company", None)
    cert_file = request.FILES.get("cert_file")
    if not cert_file:
        _msg.error(request, "Molimo odaberite .p12 datoteku.")
        return redirect("invoicing:fiscal_certificates")
    password = request.POST.get("cert_password", "")
    cert = FiscalCertificate(company=company)
    result = cert_manager.validate_and_save_cert(cert, cert_file, password)
    if result["ok"]:
        cert.save()
        _msg.success(request, f'Certifikat "{cert.cert_name}" uspjesno ucitan.')
    else:
        _msg.error(request, f"Neispravan certifikat: {result.get('error', 'Greska')}")
    return redirect("invoicing:fiscal_certificates")


@login_required
def fiscal_certificate_test(request, pk):
    if request.method != "POST":
        return redirect("invoicing:fiscal_certificates")
    from django.contrib import messages as _msg
    from django.http import Http404
    from django.utils import timezone as _tz

    from invoicing import cert_manager
    from invoicing.fiscal_models import FiscalCertificate

    company = getattr(getattr(request.user, "profile", None), "company", None)
    try:
        cert = FiscalCertificate.objects.get(pk=pk, company=company)
    except FiscalCertificate.DoesNotExist:
        raise Http404
    use_production = request.POST.get("use_production") == "1"
    result = cert_manager.test_cert_against_cis(cert, use_production=use_production)
    cert.last_test = _tz.now()
    cert.last_test_result = result["ok"]
    cert.save(update_fields=["last_test", "last_test_result"])
    if result["ok"]:
        _msg.success(request, f"CIS test uspjesan: {result.get('message', '')}")
    else:
        _msg.error(request, f"CIS test neuspjesan: {result.get('message', '')}")
    return redirect("invoicing:fiscal_certificates")


@login_required
def fiscal_certificate_delete(request, pk):
    if request.method != "POST":
        return redirect("invoicing:fiscal_certificates")
    from django.contrib import messages as _msg
    from django.http import Http404

    from invoicing.fiscal_models import FiscalCertificate

    company = getattr(getattr(request.user, "profile", None), "company", None)
    try:
        cert = FiscalCertificate.objects.get(pk=pk, company=company)
    except FiscalCertificate.DoesNotExist:
        raise Http404
    name = cert.cert_name or "Certifikat"
    cert.delete()
    _msg.success(request, f'Certifikat "{name}" obrisan.')
    return redirect("invoicing:fiscal_certificates")


@login_required
def invoice_form_view(request):
    return redirect("invoicing:invoice_wizard")


@login_required
def standalone_invoice_form(request):
    return redirect("invoicing:invoice_wizard")


# ══════════════════════════════════════════════════════════════════════════════
# TRANSACTIONAL CANVAS — Smart Lookup, Timeline, Morphing
# ══════════════════════════════════════════════════════════════════════════════


@login_required
def api_smart_lookup(request):
    """
    Universal Smart Command Bar lookup.
    Single endpoint that searches everything: local partners, VIES, name match.
    Returns results + tax configuration recommendations.

    GET /invoicing/api/smart-lookup/?q=Roma
    GET /invoicing/api/smart-lookup/?q=DE119948368
    GET /invoicing/api/smart-lookup/?q=92922919857
    """
    import re

    from core.company_utils import get_user_company
    from partners.models import Partner

    q = request.GET.get("q", "").strip()
    if len(q) < 2:
        return JsonResponse({"results": [], "lookup": None, "tax_config": None})

    company = get_user_company(request)
    results = []
    lookup_result = None
    tax_config = None

    # Detect if query looks like a tax ID
    is_oib = bool(re.match(r"^\d{11}$", q))
    is_de_vat = bool(re.match(r"^DE\d{9}$", q, re.IGNORECASE))
    is_eu_vat = bool(re.match(r"^[A-Z]{2}\d{5,}", q, re.IGNORECASE))

    # 1. Search local partners by name (always)
    if company:
        partners = Partner.objects.filter(company=company)
        if is_oib:
            partners = partners.filter(oib__icontains=q)
        elif is_eu_vat:
            partners = partners.filter(oib__icontains=q[2:])
        else:
            from django.db.models import Q

            partners = partners.filter(Q(name__icontains=q) | Q(oib__icontains=q) | Q(city__icontains=q))

        for p in partners[:8]:
            results.append(
                {
                    "type": "partner",
                    "id": p.pk,
                    "name": p.name,
                    "oib": p.oib or "",
                    "address": p.address or "",
                    "city": p.city or "",
                    "email": p.email or "",
                    "country": getattr(p, "country", "") or "",
                    "source": "database",
                }
            )

    # 2. If it looks like a tax ID, run VIES lookup in background
    if is_oib or is_de_vat or is_eu_vat:
        from core.business_lookup import lookup_business

        country = "HR"
        if is_de_vat:
            country = "DE"
        elif is_eu_vat:
            country = q[:2].upper()

        biz = lookup_business(q, country, company=company)
        if biz.found:
            lookup_result = biz.to_dict()
            # Check if this partner is already in results
            already = any(r.get("oib") == biz.tax_id for r in results)
            if not already:
                results.insert(
                    0,
                    {
                        "type": "registry",
                        "id": None,
                        "name": biz.name,
                        "oib": biz.tax_id,
                        "address": biz.address,
                        "city": biz.city,
                        "email": "",
                        "country": biz.country,
                        "source": biz.source,
                        "vat_id": biz.vat_id,
                    },
                )

            # Tax configuration based on lookup
            issuer_country = "HR"
            if company and hasattr(company, "country"):
                issuer_country = getattr(company, "country", "HR") or "HR"

            client_country = biz.country or country
            is_cross_border = client_country != issuer_country
            is_eu = client_country in (
                "HR",
                "DE",
                "AT",
                "SI",
                "IT",
                "FR",
                "NL",
                "BE",
                "PL",
                "CZ",
                "HU",
                "SK",
                "RO",
                "BG",
                "IE",
                "PT",
                "ES",
                "FI",
                "SE",
                "DK",
                "EE",
                "LV",
                "LT",
                "LU",
                "MT",
                "CY",
                "EL",
                "GR",
            )

            tax_config = {
                "reverse_charge": is_cross_border and is_eu and biz.found,
                "client_country": client_country,
                "issuer_country": issuer_country,
                "vat_valid": biz.found and biz.source == "vies",
                "suggested_tax_rate": 0 if (is_cross_border and is_eu) else None,
                "suggested_currency": "EUR",
                "clause": "",
            }

            if tax_config["reverse_charge"]:
                tax_config["clause"] = (
                    "Prijenos porezne obveze / Reverse Charge "
                    "(cl. 196 Direktive 2006/112/EZ). "
                    "PDV obracunava primatelj usluge/robe."
                )
        else:
            lookup_result = biz.to_dict()

    return JsonResponse(
        {
            "results": results,
            "lookup": lookup_result,
            "tax_config": tax_config,
            "query": q,
        }
    )


@login_required
def api_invoice_timeline(request, pk):
    """Get timeline events for an invoice."""
    from .models import InvoiceEvent

    invoice = get_object_or_404(Invoice, pk=pk)
    events = (
        InvoiceEvent.objects.filter(invoice=invoice)
        .select_related("invoice", "actor", "updated_by")
        .order_by("created_at")
    )
    return JsonResponse(
        {
            "events": [e.to_dict() for e in events],
            "invoice_pk": pk,
        }
    )


@login_required
def api_invoice_morph(request, pk):
    """
    Morph a document to a new doctype (state transition).
    POST with {target_doctype: 'R'} to morph Draft -> Invoice, etc.
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    import json

    from .models import InvoiceEvent

    invoice = get_object_or_404(Invoice, pk=pk)
    body = json.loads(request.body)
    target = body.get("target_doctype", "").strip()

    VALID_TRANSITIONS = {
        "PO": ["P", "R"],  # Ponuda -> Predracun, Racun
        "P": ["R"],  # Predracun -> Racun
        "R": ["S"],  # Racun -> Storno
        "DRAFT": ["PO", "P", "R"],  # Draft can become anything
    }

    current = invoice.doctype
    allowed = VALID_TRANSITIONS.get(current, [])
    if target not in allowed and invoice.status != "DRAFT":
        return JsonResponse(
            {
                "error": f"Nije moguce pretvoriti {current} u {target}",
                "allowed": allowed,
            },
            status=400,
        )

    old_doctype = invoice.get_doctype_display()
    invoice.doctype = target
    invoice.save(update_fields=["doctype", "updated_at"])

    DOCTYPE_NAMES = dict(Invoice.DOCTYPE_CHOICES)
    new_name = DOCTYPE_NAMES.get(target, target)

    InvoiceEvent.objects.create(
        invoice=invoice,
        event_type="morphed",
        title=f"Dokument mutirao: {old_doctype} -> {new_name}",
        detail="Automatska tranzicija dokumenta.",
        actor=request.user,
        metadata={"from": current, "to": target},
    )

    return JsonResponse(
        {
            "ok": True,
            "new_doctype": target,
            "new_doctype_display": new_name,
        }
    )


def _log_invoice_event(invoice, event_type, title, detail="", actor=None, metadata=None):
    from invoicing.services import log_invoice_event

    log_invoice_event(invoice, event_type, title, detail=detail, metadata=metadata, actor=actor)


def transaction_canvas(request):
    """
    Transactional Canvas — Omni-Document approach.
    New invoice creation with Smart Command Bar, morphing, and timeline.
    """
    from core.company_utils import get_user_company
    from inventory.models import InventoryItem
    from invoicing.fiscal_models import InvoiceProfile

    company = get_user_company(request)
    profiles = []
    default_profile = None
    if company:
        from core.company_utils import get_user_company as _guca

        _coa = _guca(request)  # noqa: I001
        profiles = list(
            InvoiceProfile.objects.filter(is_active=True, company=_coa)
            .select_related("default_tax_rate", "company", "branch")
            .values(
                "id",
                "name",
                "country",
                "currency",
                "language",
                "iban",
                "swift",
                "company_name",
                "oib",
                "vat_id",
                "address",
                "city",
                "zip_code",
                "email",
                "phone",
                "default_due_days",
                "default_payment_method",
                "invoice_prefix",
                "is_default",
            )
        )
        default_profile = next((p for p in profiles if p.get("is_default")), profiles[0] if profiles else None)

    # Next number
    next_number = ""
    if default_profile:
        prefix = default_profile.get("invoice_prefix", "R")
        from django.utils import timezone

        year = timezone.now().year
        count = (
            Invoice.objects.filter(
                company=company,
                number__startswith=f"{prefix}-{year}",
            ).count()
            + 1
        )
        next_number = f"{prefix}-{year}-{count:04d}"

    from django.utils import timezone

    now_dt = timezone.now().strftime("%Y-%m-%dT%H:%M")

    has_items = InventoryItem.objects.filter(company=company, is_active=True).exists() if company else False

    # Payment choices
    payment_choices = Invoice.PAYMENT_CHOICES

    # Default issuer info
    default_issuer = {}
    if company:
        default_issuer = {
            "company_name": company.name,
            "oib": getattr(company, "oib", ""),
            "address": getattr(company, "address", ""),
            "email_from": getattr(company, "email", ""),
        }

    ctx = {
        "profiles": profiles,
        "default_profile": default_profile or {},
        "next_number": next_number,
        "now_datetime": now_dt,
        "has_items": has_items,
        "payment_choices": payment_choices,
        "company": company,
        "company_name": company.name if company else "",
        "default_issuer": default_issuer,
        "default_iban": default_profile.get("iban", "") if default_profile else "",
    }
    return render(request, "invoicing/canvas.html", ctx)


# ═══ INVOICE PROFILE CRUD ════════════════════════════════════════════════
@login_required
def invoice_profiles_list(request):
    """List and manage invoice profiles for current company."""
    from core.company_utils import get_user_company

    from .fiscal_models import InvoiceProfile

    company = get_user_company(request)
    if not company:
        return redirect("dashboard")
    profiles = (
        InvoiceProfile.objects.filter(company=company, is_active=True)
        .select_related("default_tax_rate", "company", "branch")
        .order_by("-is_default", "name")
    )
    return render(
        request,
        "invoicing/profiles_list.html",
        {
            "profiles": profiles,
            "company": company,
        },
    )


@login_required
def invoice_profile_save(request):
    """Create or update an InvoiceProfile (AJAX)."""
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "POST required"})
    from core.company_utils import get_user_company

    from .fiscal_models import InvoiceProfile

    company = get_user_company(request)
    if not company:
        return JsonResponse({"ok": False, "error": "Nema tvrtke"})

    pk = request.POST.get("id")
    if pk:
        try:
            profile = InvoiceProfile.objects.get(pk=pk, company=company)
        except InvoiceProfile.DoesNotExist:
            return JsonResponse({"ok": False, "error": "Profil nije pronađen"})
    else:
        profile = InvoiceProfile(company=company)

    profile.name = request.POST.get("name", "").strip()
    profile.company_name = request.POST.get("company_name", "").strip()
    profile.address = request.POST.get("address", "").strip()
    profile.city = request.POST.get("city", "").strip()
    profile.zip_code = request.POST.get("zip_code", "").strip()
    profile.country = request.POST.get("country", "HR")
    profile.oib = request.POST.get("oib", "").strip()
    profile.vat_id = request.POST.get("vat_id", "").strip()
    profile.iban = request.POST.get("iban", "").strip()
    profile.swift = request.POST.get("swift", "").strip()
    profile.bank_name = request.POST.get("bank_name", "").strip()
    profile.phone = request.POST.get("phone", "").strip()
    profile.email = request.POST.get("email", "").strip()
    profile.invoice_prefix = request.POST.get("invoice_prefix", "R").strip()
    profile.default_due_days = int(request.POST.get("default_due_days", 15) or 15)
    profile.default_payment_method = request.POST.get("default_payment_method", "TRANSAKCIJSKI")
    profile.footer_note = request.POST.get("footer_note", "").strip()
    profile.language = request.POST.get("language", "hr")
    profile.currency = request.POST.get("currency", "EUR")
    profile.bilingual = request.POST.get("bilingual") == "1"
    profile.secondary_language = request.POST.get("secondary_language", "")

    is_default = request.POST.get("is_default") == "1"
    if is_default:
        profile.is_default = True

    if not profile.name:
        return JsonResponse({"ok": False, "error": "Naziv profila je obavezan"})

    profile.save()
    return JsonResponse({"ok": True, "message": "Profil spremljen", "id": profile.pk})


@login_required
def invoice_profile_delete(request, pk):
    """Deactivate an InvoiceProfile."""
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "POST required"})
    from core.company_utils import get_user_company

    from .fiscal_models import InvoiceProfile

    company = get_user_company(request)
    try:
        profile = InvoiceProfile.objects.get(pk=pk, company=company)
        profile.is_active = False
        profile.save(update_fields=["is_active"])
        return JsonResponse({"ok": True, "message": "Profil deaktiviran"})
    except InvoiceProfile.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Profil nije pronađen"})


@login_required
def api_recent_for_copy(request):
    """Vraca zadnjih 10 racuna za kopianje stavki (UI - Kopiraj s prethodnog racuna)."""
    from core.company_utils import get_user_company

    company = get_user_company(request)
    recent = Invoice.objects.filter(
        company=company,
        doctype__in=["R", "P", "OF"],
    ).order_by("-date_issued")[:10]
    data = []
    for inv in recent:
        data.append(
            {
                "pk": inv.pk,
                "number": inv.number,
                "client_name": inv.client_name or "",
                "date_issued": inv.date_issued.strftime("%d.%m.%Y") if inv.date_issued else "",
                "total_amount": str(inv.total_amount or 0),
                "doctype": inv.doctype,
            }
        )
    return JsonResponse({"invoices": data})


@login_required
def api_invoice_items(request, pk):
    """Vraca stavke racuna za kopianje u novi racun."""
    from core.company_utils import get_user_company

    company = get_user_company(request)
    try:
        invoice = Invoice.objects.get(pk=pk, company=company)
    except Invoice.DoesNotExist:
        return JsonResponse({"error": "Racun nije pronaden"}, status=404)
    items = []
    for item in invoice.items.all():
        items.append(
            {
                "description": item.description or "",
                "quantity": str(item.quantity or 1),
                "unit_price": str(item.unit_price or 0),
                "tax_rate": str(item.tax_rate or 0),
                "discount_percent": str(item.discount_percent or 0),
                "unit": item.unit or "kom",
            }
        )
    return JsonResponse({"items": items})


@login_required
def dunning_dashboard(request):
    from django.db.models import Sum
    from django.utils import timezone

    from .models import DunningHistory, DunningRule, Invoice
    from .tasks import run_dunning_cycle

    company = get_user_company(request)
    today = timezone.now().date()

    # Trigger manual run
    if request.method == "POST" and request.POST.get("action") == "run_now":
        run_dunning_cycle.delay()
        messages.success(request, _("Proces opomena pokrenut! Rezultati će biti vidljivi za nekoliko minuta."))
        return redirect("invoicing:dunning_dashboard")

    # Overdue invoices
    overdue_invoices = (
        Invoice.objects.filter(
            company=company,
            status__in=["OVERDUE", "UNPAID", "SENT"],
            date_due__lt=today,
            date_due__isnull=False,
        )
        .select_related("company")
        .order_by("date_due")
    )

    # Annotate with last dunning step
    invoice_data = []
    for inv in overdue_invoices:
        days_overdue = (today - inv.date_due).days
        last_history = DunningHistory.objects.filter(invoice=inv, status="sent").order_by("-step").first()
        invoice_data.append(
            {
                "invoice": inv,
                "days_overdue": days_overdue,
                "last_step": last_history.step if last_history else 0,
                "last_sent": last_history.sent_at if last_history else None,
            }
        )

    # Stats
    total_overdue = overdue_invoices.count()
    total_amount = overdue_invoices.aggregate(s=Sum("total"))["s"] or 0
    first_of_month = today.replace(day=1)
    reminders_this_month = DunningHistory.objects.filter(
        company=company,
        sent_at__date__gte=first_of_month,
        status="sent",
    ).count()

    # History log
    history = DunningHistory.objects.filter(company=company).select_related("invoice", "dunning_rule")[:50]

    # Dunning rules
    rules = DunningRule.objects.filter(company=company).select_related("company").order_by("step")

    return render(
        request,
        "invoicing/dunning_dashboard.html",
        {
            "invoice_data": invoice_data,
            "total_overdue": total_overdue,
            "total_amount": total_amount,
            "reminders_this_month": reminders_this_month,
            "history": history,
            "rules": rules,
        },
    )


@login_required
def ira_ura_dashboard(request):
    """GAP7: Unified IRA/URA dashboard — all invoices in one place."""
    from django.db.models import Sum
    from django.utils import timezone

    from core.company_utils import get_user_company
    from invoicing.models import Invoice

    company = get_user_company(request)
    if not company:
        return redirect("/")

    today = timezone.now().date()
    year = int(request.GET.get("year", today.year))
    month = int(request.GET.get("month", today.month))

    base_qs = Invoice.objects.filter(company=company).select_related("storno_of", "business_location", "operator")

    # IRA (izdani računi) — doctype R, FA, RN, A
    ira_qs = base_qs.filter(doctype__in=("R", "FA", "RN", "A"))
    ira_month = ira_qs.filter(issue_date__year=year, issue_date__month=month)
    ira_stats = {
        "count": ira_month.count(),
        "total": ira_month.aggregate(s=Sum("total"))["s"] or 0,
        "paid": ira_month.filter(status="PAID").aggregate(s=Sum("total"))["s"] or 0,
        "unpaid": ira_month.filter(status__in=("UNPAID", "OVERDUE", "SENT")).aggregate(s=Sum("total"))["s"] or 0,
        "overdue": ira_month.filter(status="OVERDUE").count(),
    }

    # URA (ulazni računi) — doctype URA
    ura_qs = base_qs.filter(doctype="URA")
    ura_month = ura_qs.filter(issue_date__year=year, issue_date__month=month)
    ura_stats = {
        "count": ura_month.count(),
        "total": ura_month.aggregate(s=Sum("total"))["s"] or 0,
        "paid": ura_month.filter(status="PAID").aggregate(s=Sum("total"))["s"] or 0,
        "unpaid": ura_month.filter(status__in=("UNPAID", "OVERDUE", "SENT")).aggregate(s=Sum("total"))["s"] or 0,
    }

    # POS prihod (non-R1)
    pos_total = 0
    pos_count = 0
    try:
        from pos.models import POSReceipt

        pos_qs = POSReceipt.objects.filter(
            session__terminal__company=company,
            status="paid",
            paid_at__year=year,
            paid_at__month=month,
        )
        pos_total = pos_qs.aggregate(s=Sum("total"))["s"] or 0
        pos_count = pos_qs.count()
    except DatabaseError:
        pass

    # PDV bilanca
    pdv_out = ira_month.aggregate(s=Sum("tax_amount"))["s"] or 0  # Izlazni PDV
    pdv_in = ura_month.aggregate(s=Sum("tax_amount"))["s"] or 0  # Ulazni PDV (pretporez)
    pdv_balance = pdv_out - pdv_in  # Pozitivno = plaćamo, negativno = povrat

    recent_ira = ira_qs.order_by("-issue_date")[:10]
    recent_ura = ura_qs.order_by("-issue_date")[:10]

    return render(
        request,
        "invoicing/ira_ura_dashboard.html",
        {
            "ira_stats": ira_stats,
            "ura_stats": ura_stats,
            "pos_total": pos_total,
            "pos_count": pos_count,
            "pdv_out": pdv_out,
            "pdv_in": pdv_in,
            "pdv_balance": pdv_balance,
            "recent_ira": recent_ira,
            "recent_ura": recent_ura,
            "year": year,
            "month": month,
            "page_title": f"IRA/URA Pregled — {month:02d}/{year}",
        },
    )
