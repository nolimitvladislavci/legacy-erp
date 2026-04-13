"""
B2B Klijentski Portal — views.
Partner pristupa putem portal_token (UUID), bez login-a.
"""

import json

from django.db import DatabaseError, IntegrityError
from django.db.models import Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from invoicing.models import Invoice
from partners.models import Partner


def _partner(token):
    """Dohvati aktivnog partnera po portal tokenu ili vrati 404."""
    return get_object_or_404(Partner, portal_token=token, is_active=True)


def _log_event(invoice, event_type, title, detail="", metadata=None):
    """Zabilježi event u timeline (ako InvoiceEvent postoji)."""
    try:
        from invoicing.models import InvoiceEvent

        InvoiceEvent.objects.create(
            invoice=invoice,
            event_type=event_type,
            title=title,
            detail=detail,
            metadata=metadata or {},
        )
    except (IntegrityError, DatabaseError):
        pass


# ── Dashboard ──────────────────────────────────────────────────────────────
def b2b_dashboard(request, token):
    partner = _partner(token)
    invoices = Invoice.objects.filter(partner=partner)

    stats = {
        "total": invoices.count(),
        "open_balance": invoices.filter(status__in=["SENT", "ACCEPTED", "OVERDUE", "UNPAID"]).aggregate(s=Sum("total"))[
            "s"
        ]
        or 0,
        "paid": invoices.filter(status="PAID").aggregate(s=Sum("total"))["s"] or 0,
        "overdue": invoices.filter(status="OVERDUE").count(),
    }

    recent = invoices.order_by("-date_issued")[:5]

    return render(
        request,
        "portal/dashboard.html",
        {
            "partner": partner,
            "token": token,
            "stats": stats,
            "recent": recent,
            "active_tab": "dashboard",
        },
    )


# ── Invoice List ───────────────────────────────────────────────────────────
def b2b_invoices(request, token):
    partner = _partner(token)
    qs = Invoice.objects.filter(partner=partner).order_by("-date_issued")

    status = request.GET.get("status", "")
    doctype = request.GET.get("doctype", "")

    if status:
        qs = qs.filter(status=status)
    if doctype:
        qs = qs.filter(doctype=doctype)

    return render(
        request,
        "portal/invoices.html",
        {
            "partner": partner,
            "token": token,
            "invoices": qs,
            "filter_status": status,
            "filter_doctype": doctype,
            "active_tab": "invoices",
        },
    )


# ── Invoice Detail ─────────────────────────────────────────────────────────
def b2b_invoice_detail(request, token, pk):
    partner = _partner(token)
    invoice = get_object_or_404(Invoice, pk=pk, partner=partner)

    items = invoice.items.all()
    has_discount = any(getattr(item, "discount_percent", None) for item in items)

    events = []
    try:
        from invoicing.models import InvoiceEvent

        events = list(InvoiceEvent.objects.filter(invoice=invoice).order_by("created_at"))
    except DatabaseError:
        pass

    return render(
        request,
        "portal/invoice_detail.html",
        {
            "partner": partner,
            "token": token,
            "invoice": invoice,
            "items": items,
            "has_discount": has_discount,
            "events": events,
            "active_tab": "invoices",
        },
    )


# ── Invoice Action (AJAX) ─────────────────────────────────────────────────
@require_POST
def b2b_invoice_action(request, token, pk):
    partner = _partner(token)
    invoice = get_object_or_404(Invoice, pk=pk, partner=partner)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse(
            {"ok": False, "error": "Neispravan zahtjev."},
            status=400,
        )

    action = body.get("action", "")

    # ── Accept ────────────────────────────────────────────────
    if action == "accept" and invoice.status in ("DRAFT", "SENT"):
        invoice.status = "ACCEPTED"
        invoice.save(update_fields=["status", "updated_at"])
        _log_event(
            invoice,
            "status_change",
            "Klijent prihvatio dokument",
            f"Partner {partner.name} prihvatio putem B2B portala.",
            {"action": "accept", "partner_id": partner.pk},
        )
        return JsonResponse(
            {
                "ok": True,
                "new_status": "ACCEPTED",
                "message": "Dokument je uspjesno prihvacen.",
            }
        )

    # ── Reject ────────────────────────────────────────────────
    if action == "reject" and invoice.status in ("DRAFT", "SENT"):
        reason = body.get("reason", "").strip()
        invoice.status = "REJECTED"
        invoice.save(update_fields=["status", "updated_at"])
        _log_event(
            invoice,
            "status_change",
            "Klijent odbio dokument",
            f"Partner {partner.name} odbio. Razlog: {reason or '—'}",
            {"action": "reject", "partner_id": partner.pk, "reason": reason},
        )
        return JsonResponse(
            {
                "ok": True,
                "new_status": "REJECTED",
                "message": "Dokument je odbijen.",
            }
        )

    # ── Comment ───────────────────────────────────────────────
    if action == "comment":
        text = body.get("text", "").strip()
        if not text:
            return JsonResponse(
                {"ok": False, "error": "Komentar ne moze biti prazan."},
                status=400,
            )
        _log_event(
            invoice,
            "note",
            f"Komentar partnera: {partner.name}",
            text,
            {"partner_id": partner.pk, "source": "b2b_portal"},
        )
        return JsonResponse(
            {
                "ok": True,
                "message": "Komentar je zabiljezen.",
            }
        )

    # ── Invalid action ────────────────────────────────────────
    return JsonResponse(
        {
            "ok": False,
            "error": f'Akcija "{action}" nije dozvoljena za status "{invoice.get_status_display()}".',
        },
        status=400,
    )


# ── Invoice PDF (public, token-gated) ──────────────────────────────────────
def b2b_invoice_pdf(request, token, pk):
    partner = _partner(token)
    invoice = get_object_or_404(Invoice, pk=pk, partner=partner)

    # Determine language
    lang = "hr"
    client_country = getattr(invoice, "client_country", "") or ""
    if client_country.upper() in ("DE", "AT", "CH"):
        lang = "de"

    template_name = f"invoicing/invoice_{lang}.html"

    items = invoice.items.all()
    company = invoice.company

    # Try to generate real PDF with weasyprint
    try:
        import weasyprint
        from django.template.loader import render_to_string

        html_string = render_to_string(
            template_name,
            {
                "invoice": invoice,
                "items": items,
                "company": company,
                "issuer": {
                    "name": company.name if company else "",
                    "oib": getattr(company, "oib", ""),
                    "address": getattr(company, "address", ""),
                    "email": getattr(company, "email", ""),
                    "iban": invoice.iban or "",
                    "swift": invoice.swift or "",
                },
            },
        )

        pdf_file = weasyprint.HTML(string=html_string).write_pdf()
        response = HttpResponse(pdf_file, content_type="application/pdf")
        filename = f"{invoice.number or 'dokument'}.pdf"
        response["Content-Disposition"] = f'inline; filename="{filename}"'
        return response

    except ImportError:
        # weasyprint not available — render HTML print view
        return render(
            request,
            template_name,
            {
                "invoice": invoice,
                "items": items,
                "company": company,
                "issuer": {
                    "name": company.name if company else "",
                    "oib": getattr(company, "oib", ""),
                    "address": getattr(company, "address", ""),
                    "email": getattr(company, "email", ""),
                    "iban": invoice.iban or "",
                    "swift": invoice.swift or "",
                },
            },
        )
    except Exception:
        # Any other error — return simple HTML
        return render(
            request,
            template_name,
            {
                "invoice": invoice,
                "items": items,
                "company": company,
            },
        )
