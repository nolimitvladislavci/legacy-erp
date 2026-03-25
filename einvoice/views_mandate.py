"""
Views za e-Račun Mandate (Punomoć) CRUD workflow.

Endpoints:
  - mandate_list:          GET    lista svih mandata za korisnikovu firmu
  - mandate_create:        POST   kreiraj novi mandat (JSON API)
  - mandate_pdf:           GET    download PDF punomoći
  - mandate_upload_signed: POST   upload potpisane punomoći
  - mandate_activate:      POST   registriraj mandat kod FINA (superadmin)
  - mandate_revoke:        POST   opozovi mandat
"""
import json
import logging
from datetime import date

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.company_utils import get_user_company
from einvoice.models.mandate import Mandate, MandateStatus, MandateType
from einvoice.services.mandate_pdf import generate_mandate_pdf

logger = logging.getLogger("propter.einvoice.views_mandate")


def _get_company_or_error(request):
    """Return user's company or None (with JSON error logged)."""
    company = get_user_company(request)
    if not company:
        logger.warning("mandate_view: user=%s has no company", request.user)
    return company


@login_required
def mandate_list(request):
    """Lista svih mandata za korisnikovu firmu."""
    company = _get_company_or_error(request)
    if not company:
        from django.contrib import messages as django_messages
        django_messages.error(request, "Nema aktivne firme.")
        return redirect("dashboard")

    mandates = Mandate.objects.filter(
        agent_company=company,
    ).select_related(
        "principal_company", "agent_company", "created_by",
    ).order_by("-created_at")

    # Also show mandates where this company is the principal
    mandates_given = Mandate.objects.filter(
        principal_company=company,
    ).select_related(
        "principal_company", "agent_company", "created_by",
    ).order_by("-created_at")

    stats = {
        "held_total": mandates.count(),
        "held_active": mandates.filter(status=MandateStatus.ACTIVE).count(),
        "given_total": mandates_given.count(),
        "given_active": mandates_given.filter(status=MandateStatus.ACTIVE).count(),
    }

    return render(request, "einvoice/mandate_list.html", {
        "mandates_held": mandates,
        "mandates_given": mandates_given,
        "stats": stats,
        "company": company,
        "is_superadmin": request.user.is_superuser,
    })


@login_required
@require_POST
def mandate_create(request):
    """
    Kreiraj novi mandat. JSON API.

    Expects JSON body:
      {
        "principal_company_id": <int>,
        "mandate_type": "full"|"send"|"receive",
        "valid_from": "YYYY-MM-DD",
        "valid_until": "YYYY-MM-DD" | null,
        "notes": "..."
      }

    Auto-fills OIBs from Company records.
    Generates initial PDF.
    Returns mandate ID.
    """
    company = _get_company_or_error(request)
    if not company:
        return JsonResponse({"error": "Nema aktivne firme."}, status=400)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Neispravan JSON."}, status=400)

    principal_company_id = data.get("principal_company_id")
    mandate_type = data.get("mandate_type", "full")
    valid_from_str = data.get("valid_from")
    valid_until_str = data.get("valid_until")
    notes = data.get("notes", "")

    # Validate principal company
    if not principal_company_id:
        return JsonResponse({"error": "principal_company_id je obavezan."}, status=400)

    from companies.models import Company
    try:
        principal = Company.objects.get(pk=principal_company_id)
    except Company.DoesNotExist:
        return JsonResponse({"error": "Firma opunomoćitelja nije pronađena."}, status=404)

    # Validate mandate_type
    valid_types = [c[0] for c in MandateType.choices]
    if mandate_type not in valid_types:
        return JsonResponse({
            "error": f"Nevažeći tip punomoći. Dozvoljeno: {', '.join(valid_types)}",
        }, status=400)

    # Parse dates
    try:
        valid_from = date.fromisoformat(valid_from_str) if valid_from_str else date.today()
    except (ValueError, TypeError):
        return JsonResponse({"error": "Neispravan format datuma valid_from (YYYY-MM-DD)."}, status=400)

    valid_until = None
    if valid_until_str:
        try:
            valid_until = date.fromisoformat(valid_until_str)
        except (ValueError, TypeError):
            return JsonResponse({"error": "Neispravan format datuma valid_until (YYYY-MM-DD)."}, status=400)

    if valid_until and valid_until <= valid_from:
        return JsonResponse({"error": "valid_until mora biti nakon valid_from."}, status=400)

    # Check for duplicate
    existing = Mandate.objects.filter(
        principal_company=principal,
        agent_company=company,
        status__in=[MandateStatus.DRAFT, MandateStatus.SIGNED, MandateStatus.ACTIVE],
    ).first()
    if existing:
        return JsonResponse({
            "error": f"Aktivan mandat već postoji (ID: {existing.id}, status: {existing.get_status_display()}).",
        }, status=409)

    # Create mandate
    mandate = Mandate.objects.create(
        principal_company=principal,
        principal_oib=principal.oib,
        agent_company=company,
        agent_oib=company.oib,
        mandate_type=mandate_type,
        status=MandateStatus.DRAFT,
        valid_from=valid_from,
        valid_until=valid_until,
        notes=notes,
        created_by=request.user,
    )

    logger.info(
        "mandate_create: user=%s created mandate=%s principal=%s(%s) agent=%s(%s)",
        request.user, mandate.id, principal.name, principal.oib, company.name, company.oib,
    )

    return JsonResponse({
        "id": str(mandate.id),
        "status": mandate.status,
        "principal": principal.name,
        "agent": company.name,
        "mandate_type": mandate.mandate_type,
        "pdf_url": f"/einvoice/mandates/{mandate.id}/pdf/",
        "message": "Mandat kreiran. Preuzmite PDF, potpišite, i uploadajte.",
    }, status=201)


@login_required
def mandate_pdf(request, mandate_id):
    """Download PDF punomoći."""
    company = _get_company_or_error(request)
    if not company:
        return JsonResponse({"error": "Nema aktivne firme."}, status=400)

    mandate = get_object_or_404(Mandate, pk=mandate_id)

    # Check access: user must be principal or agent company
    if mandate.principal_company_id != company.id and mandate.agent_company_id != company.id:
        if not request.user.is_superuser:
            return JsonResponse({"error": "Nemate pristup ovom mandatu."}, status=403)

    try:
        pdf_bytes = generate_mandate_pdf(mandate)
    except Exception:
        logger.exception("mandate_pdf: failed to generate PDF for mandate=%s", mandate_id)
        return JsonResponse({"error": "Greška pri generiranju PDF-a."}, status=500)

    filename = f"punomoc_{mandate.principal_oib}_{mandate.agent_oib}.pdf"
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
@require_POST
def mandate_upload_signed(request, mandate_id):
    """
    Upload potpisane punomoći (PDF/image).

    Expects multipart/form-data with 'document' file field.
    Transitions mandate status from DRAFT → SIGNED.
    """
    company = _get_company_or_error(request)
    if not company:
        return JsonResponse({"error": "Nema aktivne firme."}, status=400)

    mandate = get_object_or_404(Mandate, pk=mandate_id)

    # Check access
    if mandate.principal_company_id != company.id and mandate.agent_company_id != company.id:
        if not request.user.is_superuser:
            return JsonResponse({"error": "Nemate pristup ovom mandatu."}, status=403)

    if mandate.status not in (MandateStatus.DRAFT, MandateStatus.SIGNED):
        return JsonResponse({
            "error": f"Mandat nije u statusu za upload (trenutni: {mandate.get_status_display()}).",
        }, status=400)

    uploaded_file = request.FILES.get("document")
    if not uploaded_file:
        return JsonResponse({"error": "Datoteka 'document' je obavezna."}, status=400)

    # Validate file type
    allowed_types = [
        "application/pdf",
        "image/jpeg", "image/png", "image/tiff",
    ]
    if uploaded_file.content_type not in allowed_types:
        return JsonResponse({
            "error": f"Nedozvoljeni tip datoteke: {uploaded_file.content_type}. "
                     f"Dozvoljeno: PDF, JPEG, PNG, TIFF.",
        }, status=400)

    # Limit file size (10 MB)
    if uploaded_file.size > 10 * 1024 * 1024:
        return JsonResponse({"error": "Datoteka prevelika (max 10 MB)."}, status=400)

    mandate.mandate_document = uploaded_file
    mandate.status = MandateStatus.SIGNED
    mandate.save(update_fields=["mandate_document", "status", "updated_at"])

    logger.info(
        "mandate_upload_signed: user=%s uploaded signed doc for mandate=%s",
        request.user, mandate_id,
    )

    return JsonResponse({
        "id": str(mandate.id),
        "status": mandate.status,
        "message": "Potpisana punomoć uploadana. Čeka registraciju kod FINA.",
    })


@login_required
@require_POST
def mandate_activate(request, mandate_id):
    """
    Označi da je mandat registriran kod FINA.

    Samo superadmin/cockpit korisnici mogu aktivirati mandat.
    Sets status=active, registered_with_fina=True, fina_registered_at=now().
    """
    if not request.user.is_superuser:
        return JsonResponse({"error": "Samo administrator može aktivirati mandat."}, status=403)

    mandate = get_object_or_404(Mandate, pk=mandate_id)

    if mandate.status != MandateStatus.SIGNED:
        return JsonResponse({
            "error": f"Mandat mora biti u statusu 'Potpisan' za aktivaciju "
                     f"(trenutni: {mandate.get_status_display()}).",
        }, status=400)

    # Parse optional FINA reference
    fina_ref = ""
    if request.content_type and "json" in request.content_type:
        try:
            data = json.loads(request.body)
            fina_ref = data.get("fina_mandate_id", "")
        except (json.JSONDecodeError, ValueError):
            pass

    now = timezone.now()
    mandate.status = MandateStatus.ACTIVE
    mandate.registered_with_fina = True
    mandate.fina_registered_at = now
    mandate.is_active = True
    if fina_ref:
        mandate.fina_mandate_id = fina_ref
    mandate.save(update_fields=[
        "status", "registered_with_fina", "fina_registered_at",
        "is_active", "fina_mandate_id", "updated_at",
    ])

    logger.info(
        "mandate_activate: superuser=%s activated mandate=%s fina_ref=%s",
        request.user, mandate_id, fina_ref,
    )

    return JsonResponse({
        "id": str(mandate.id),
        "status": mandate.status,
        "fina_registered_at": now.isoformat(),
        "message": "Mandat aktiviran i registriran kod FINA.",
    })


@login_required
@require_POST
def mandate_revoke(request, mandate_id):
    """Opozovi mandat."""
    company = _get_company_or_error(request)
    if not company:
        return JsonResponse({"error": "Nema aktivne firme."}, status=400)

    mandate = get_object_or_404(Mandate, pk=mandate_id)

    # Check access: principal, agent, or superadmin
    if (mandate.principal_company_id != company.id
            and mandate.agent_company_id != company.id
            and not request.user.is_superuser):
        return JsonResponse({"error": "Nemate pristup ovom mandatu."}, status=403)

    if mandate.status == MandateStatus.REVOKED:
        return JsonResponse({"error": "Mandat je već opozvan."}, status=400)

    mandate.revoke()

    logger.info(
        "mandate_revoke: user=%s revoked mandate=%s",
        request.user, mandate_id,
    )

    return JsonResponse({
        "id": str(mandate.id),
        "status": mandate.status,
        "message": "Mandat opozvan.",
    })
