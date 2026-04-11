# documents/views.py - Split into submodules for maintainability
#
# Generic document views are kept here.
# All other views are imported from submodules via wildcard re-export,
# so urls.py (which imports from documents.views) continues to work unchanged.

import logging

from django.contrib import messages
from django.utils.translation import gettext as _
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from rest_framework import viewsets

from core.company_utils import get_user_company
from partners.models import Partner

from .models import Document
from .serializers import DocumentSerializer


logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════
# Generic Document Views (kept in main views.py)
# ════════════════════════════════════════════════════════════

@login_required
def document_list(request):
    # Redirect to Arhiva (unified document archive)
    return redirect("documents:arhiva_list")


def document_list_legacy(request):
    q = request.GET.get("q", "")
    doc_type = request.GET.get("doc_type", "")
    is_paid = request.GET.get("is_paid", "")
    company = get_user_company(request)
    qs = Document.objects.filter(company=company).select_related("company", "partner").order_by("-date_issued") if company else Document.objects.none()
    if q:
        qs = qs.filter(Q(doc_number__icontains=q)|Q(partner__name__icontains=q))
    if doc_type:
        qs = qs.filter(doc_type=doc_type)
    if is_paid == "1":
        qs = qs.filter(is_paid=True)
    elif is_paid == "0":
        qs = qs.filter(is_paid=False)
    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get("page"))
    return render(request, "documents/document_list.html", {
        "page_obj": page, "q": q, "doc_type": doc_type, "is_paid": is_paid,
        "total": qs.count(), "type_choices": Document.TYPE_CHOICES,
    })


@login_required
def document_create(request):
    if request.method == "POST":
        try:
            company = get_user_company(request)
            if not company:
                messages.error(request, _('Niste povezani s tvrtkom. Odaberite tvrtku iz izbornika.'))
                return redirect('documents:list')
            partner_id = request.POST.get("partner")
            partner = Partner.objects.get(pk=partner_id) if partner_id else None
            doc = Document(
                company=company,
                partner=partner,
                doc_type=request.POST["doc_type"],
                doc_number=request.POST["doc_number"],
                date_issued=request.POST["date_issued"],
                total_amount=request.POST.get("total_amount", 0) or 0,
                is_paid="is_paid" in request.POST,
            )
            date_due = request.POST.get("date_due")
            if date_due:
                doc.date_due = date_due
            if "file" in request.FILES:
                doc.file = request.FILES["file"]
            doc.save()
            messages.success(request, f"Dokument {doc.doc_number} kreiran.")
            return redirect("documents:list")
        except Exception as e:
            logger.error('arhiva_upload FAILED: %s', e, exc_info=True)
            messages.error(request, str(e))
    company = get_user_company(request)
    return render(request, "documents/document_form.html", {
        "company": company,
        "partners": Partner.objects.filter(company=company, is_active=True).order_by("name") if company else Partner.objects.none(),
        "type_choices": Document.TYPE_CHOICES,
        "action": "Novi dokument",
    })


@login_required
def document_detail(request, pk):
    company = get_user_company(request)
    doc = get_object_or_404(Document, pk=pk, company=company)
    return render(request, "documents/document_detail.html", {"doc": doc})


@login_required
def document_toggle_paid(request, pk):
    company = get_user_company(request)
    doc = get_object_or_404(Document, pk=pk, company=company)
    doc.is_paid = not doc.is_paid
    doc.save(update_fields=["is_paid"])
    status = "plaćeno" if doc.is_paid else "neplaćeno"
    messages.success(request, f"Dokument {doc.doc_number} označen kao {status}.")
    return redirect("documents:list")


class DocumentViewSet(viewsets.ModelViewSet):
    serializer_class = DocumentSerializer

    def get_queryset(self):
        from core.company_utils import get_user_company
        company = get_user_company(self.request)
        if company:
            return Document.objects.filter(company=company)
        return Document.objects.none()


# ════════════════════════════════════════════════════════════
# Re-export all views from submodules
# ════════════════════════════════════════════════════════════
from .views_arhiva import *  # noqa: F401,F403
from .views_process_docs import *  # noqa: F401,F403
from .views_ai_inbox import *  # noqa: F401,F403
from .views_scan import *  # noqa: F401,F403
from .views_reports import *  # noqa: F401,F403
