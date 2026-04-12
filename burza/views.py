import logging
logger = logging.getLogger(__name__)
import json

from django.contrib import messages
from django.utils.translation import gettext as _
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import LeadActivity, ProjectLead


def get_company(request):
    try:
        return request.user.profile.company
    except Exception:
        return None


def is_superadmin(request):
    try:
        return request.user.profile.role == 'superadmin'
    except Exception:
        return False


@login_required
def kanban_board(request):
    company = get_company(request)
    sa = is_superadmin(request)

    if sa:
        novi    = ProjectLead.objects.filter(status='NOVI_UPIT').select_related('company', 'taken_by')
        interna = ProjectLead.objects.filter(status='INTERNA_PROCJENA').select_related('company', 'assigned_to')
        burza   = ProjectLead.objects.filter(status='NA_BURZI').select_related('company')
        preuzeto= ProjectLead.objects.filter(status='PREUZETO').select_related('taken_by')
        rijeseno= ProjectLead.objects.filter(status='RIJESENO').select_related('taken_by')
    else:
        own    = ProjectLead.objects.filter(company=company)
        novi    = own.filter(status='NOVI_UPIT')
        interna = own.filter(status='INTERNA_PROCJENA')
        burza   = ProjectLead.objects.filter(status='NA_BURZI', is_public=True)
        preuzeto= own.filter(status='PREUZETO')
        rijeseno= own.filter(status='RIJESENO')

    columns = [
        {'id': 'NOVI_UPIT',        'label': 'Novi upit',        'icon': '\U0001f4e5', 'color': '#3b82f6', 'leads': novi},
        {'id': 'INTERNA_PROCJENA', 'label': 'Interna procjena', 'icon': '\U0001f50d', 'color': '#c9a84c', 'leads': interna},
        {'id': 'NA_BURZI',         'label': 'Na burzi',         'icon': '\U0001f3ea', 'color': '#10b981', 'leads': burza},
        {'id': 'PREUZETO',         'label': 'Preuzeto',         'icon': '\u2705', 'color': '#8b5cf6', 'leads': preuzeto},
        {'id': 'RIJESENO',         'label': 'Riješeno',         'icon': '\U0001f3c6', 'color': '#f59e0b', 'leads': rijeseno},
    ]
    return render(request, 'burza/kanban.html', {
        'columns': columns, 'is_superadmin': sa, 'company': company,
    })


@login_required
def lead_detail(request, pk):
    lead = get_object_or_404(ProjectLead, pk=pk)
    company = get_company(request)
    sa = is_superadmin(request)
    if not sa:
        if lead.company != company and not (lead.is_public and lead.status == 'NA_BURZI'):
            return JsonResponse({'ok': False, 'error': 'Nemate pristup.'}, status=403)

    # CardActivity timeline (new BORG audit trail)
    from borg_ops.models import CardActivity
    from django.contrib.contenttypes.models import ContentType
    card_activities = CardActivity.objects.filter(
        content_type=ContentType.objects.get_for_model(lead),
        object_id=str(lead.pk),
    )[:50]

    return render(request, 'burza/lead_detail.html', {
        'lead': lead,
        'activities': card_activities,
        'legacy_activities': lead.activities.all()[:20],
        'is_superadmin': sa, 'company': company,
    })


@login_required
@require_POST
def lead_move(request, pk):
    lead = get_object_or_404(ProjectLead, pk=pk)
    company = get_company(request)
    sa = is_superadmin(request)
    # Superadmin can move any lead; company admin can only move their own leads
    if not sa and (not company or lead.company != company):
        return JsonResponse({'ok': False, 'error': 'Nemate pristup ovom leadu.'}, status=403)
    try:
        data = json.loads(request.body)
        new_status = data.get('status')
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Neispravan zahtjev.'}, status=400)
    valid = [s[0] for s in ProjectLead.Status.choices]
    if new_status not in valid:
        return JsonResponse({'ok': False, 'error': f'Nepoznati status.'}, status=400)

    # FSM validated transition
    try:
        lead.transition_to(new_status, user=request.user, save=False)
    except ValueError as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)
    lead.is_public = (new_status == 'NA_BURZI')
    super(type(lead), lead).save(update_fields=[lead.STATUS_FIELD, 'is_public'])
    return JsonResponse({'ok': True, 'message': f'Pomičeno u: {lead.get_status_display()}'})


@login_required
@require_POST
def lead_preuzmi(request, pk):
    company = get_company(request)
    if not company:
        return JsonResponse({'ok': False, 'error': 'Niste povezani s tvrtkom.'}, status=403)
    try:
        sub = company.subscriptions.filter(is_active=True).first()
        if sub and sub.plan not in ('business', 'enterprise'):
            return JsonResponse({'ok': False, 'error': 'Potreban je BUSINESS ili ENTERPRISE plan.'}, status=403)
    except Exception:
        pass
    try:
        with transaction.atomic():
            lead = ProjectLead.objects.select_for_update().get(pk=pk)
            if lead.status != 'NA_BURZI':
                return JsonResponse({'ok': False, 'error': 'Posao više nije dostupan na burzi.'}, status=409)
            if lead.taken_by is not None:
                return JsonResponse({'ok': False, 'error': f'Posao je već preuzet.'}, status=409)
            if lead.company == company:
                return JsonResponse({'ok': False, 'error': 'Ne možete preuzeti vlastiti posao.'}, status=400)

            # FSM validated transition
            try:
                lead.transition_to('PREUZETO', user=request.user,
                                   note=f'Preuzela tvrtka: {company.name}', save=False)
            except ValueError as e:
                return JsonResponse({'ok': False, 'error': str(e)}, status=400)
            lead.taken_by = company
            lead.taken_by_user = request.user
            lead.taken_at = timezone.now()
            lead.is_public = False
            super(type(lead), lead).save()
    except ProjectLead.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Kartica ne postoji.'}, status=404)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': f'Greška: {str(e)}'}, status=500)
    return JsonResponse({'ok': True, 'message': f'Uspješno preuzeto: {lead.title}'})


def public_upit(request):
    if request.method == 'POST':
        try:
            lead = ProjectLead(
                title=request.POST.get('title','').strip(),
                description=request.POST.get('description','').strip(),
                category=request.POST.get('category','ostalo'),
                location=request.POST.get('location','').strip(),
                contact_name=request.POST.get('contact_name','').strip(),
                contact_phone=request.POST.get('contact_phone','').strip(),
                contact_email=request.POST.get('contact_email','').strip(),
                status='NOVI_UPIT', is_public=False,
            )
            bf = request.POST.get('budget_from','').strip()
            bt = request.POST.get('budget_to','').strip()
            if bf: lead.budget_from = float(bf)
            if bt: lead.budget_to = float(bt)
            lead.save()
            return redirect('burza:upit_hvala')
        except Exception as e:
            return render(request, 'burza/public_upit.html', {
                'error': str(e), 'categories': ProjectLead.Category.choices,
            })
    prefill = {k: request.GET.get(k, '') for k in ('title','description','location','budget_from','budget_to')}
    precat  = request.GET.get('category', '')
    # map 'adaptacija' -> 'kupaonica' (bathroom renovation)
    CAT_MAP = {'adaptacija': 'kupaonica', 'bathroom': 'kupaonica', 'badsanierung': 'kupaonica'}
    precat  = CAT_MAP.get(precat, precat)
    # parse budget from description if not set
    import re as _re
    if not prefill['budget_from'] and prefill['description']:
        m = _re.search(r'([\d\.]+)\s*\u20ac\s*\u2013\s*([\d\.]+)\s*\u20ac', prefill['description'])
        if m:
            prefill['budget_from'] = m.group(1).replace('.','')
            prefill['budget_to']   = m.group(2).replace('.','')
    return render(request, 'burza/public_upit.html', {
        'categories': ProjectLead.Category.choices,
        'prefill': prefill,
        'precat': precat,
        'from_calculator': bool(request.GET.get('title')),
    })


def upit_hvala(request):
    return render(request, 'burza/upit_hvala.html')


@login_required
def lead_new(request):
    sa = is_superadmin(request)
    company = get_company(request)
    if request.method == 'POST':
        try:
            lead = ProjectLead(
                company=company,
                title=request.POST.get('title','').strip(),
                description=request.POST.get('description','').strip(),
                category=request.POST.get('category','ostalo'),
                location=request.POST.get('location','').strip(),
                contact_name=request.POST.get('contact_name','').strip(),
                contact_phone=request.POST.get('contact_phone','').strip(),
                contact_email=request.POST.get('contact_email','').strip(),
                internal_notes=request.POST.get('internal_notes','').strip(),
                status='NOVI_UPIT', created_by=request.user,
            )
            bf = request.POST.get('budget_from','').strip()
            bt = request.POST.get('budget_to','').strip()
            if bf: lead.budget_from = float(bf)
            if bt: lead.budget_to = float(bt)
            lead.save()
            messages.success(request, _('Kartica kreirana uspješno.'))
            return redirect('burza:kanban')
        except Exception as e:
            messages.error(request, _('Nešto je pošlo krivo. Pokušajte ponovo ili kontaktirajte podršku.'))
    return render(request, 'burza/lead_form.html', {
        'categories': ProjectLead.Category.choices, 'is_superadmin': sa,
    })


@login_required
def create_invoice_from_lead(request, pk):
    """Create a draft Invoice pre-filled from a ProjectLead and redirect to edit."""
    lead = get_object_or_404(ProjectLead, pk=pk)
    sa = is_superadmin(request)
    company = get_company(request)
    if not sa and company != lead.taken_by:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden('Nemate pristup.')

    import datetime

    from django.utils import timezone

    from invoicing.models import Invoice

    now = timezone.now()
    # Generate unique invoice number
    base_num = f"BURZA-{now.year}"
    last = Invoice.objects.filter(number__startswith=base_num).order_by('-id').first()
    seq = 1
    if last:
        try:
            seq = int(last.number.split('-')[-1]) + 1
        except ValueError:
            seq = Invoice.objects.count() + 1
    candidate = f"{base_num}-{seq:04d}"
    while Invoice.objects.filter(number=candidate).exists():
        seq += 1
        candidate = f"{base_num}-{seq:04d}"

    invoice = Invoice.objects.create(
        number=candidate,
        date_issued=now,
        date_due=(now + datetime.timedelta(days=15)).date(),
        client_name=lead.contact_name or '',
        client_address=lead.location or '',
        client_email=lead.contact_email or '',
        company=lead.taken_by,
        status='DRAFT',
        internal_note=f'Kreirano iz Burza kartice #{lead.pk}: {lead.title}',
    )
    messages.success(request, f'Nacrt fakture {invoice.number} kreiran.')
    return redirect(f'/invoicing/{invoice.pk}/edit/')


@login_required
def bathroom_to_project(request, lead_pk):
    import re, uuid
    from django.utils import timezone
    from core.company_utils import get_user_company
    from burza.models import ProjectLead
    from projects.models import Project
    from calculator.models import Calculation, CalculationItem, Normative
    from partners.models import Partner

    lead = get_object_or_404(ProjectLead, pk=lead_pk)
    company = get_user_company(request)

    if request.method == "POST":
        margin    = float(request.POST.get("margin", 20))
        vat       = float(request.POST.get("vat", 19))
        proj_name = request.POST.get("proj_name", lead.title)
        client_id = request.POST.get("client_id") or None
        code      = "BAD-" + timezone.now().strftime("%Y%m%d") + "-" + uuid.uuid4().hex[:4].upper()

        proj = Project.objects.create(
            name=proj_name, code=code, description=lead.description,
            location=lead.location, status="planning", company=company,
            client_id=client_id,
        )
        calc = Calculation.objects.create(
            project=proj, margin_percentage=margin, vat_percentage=vat,
        )
        norm_ids = request.POST.getlist("norm_ids")
        qtys     = request.POST.getlist("norm_qty")
        for i, nid in enumerate(norm_ids):
            try:
                n   = Normative.objects.get(pk=int(nid))
                qty = float(qtys[i]) if i < len(qtys) else 1.0
                CalculationItem.objects.create(
                    calculation=calc, normative=n, description=n.name,
                    quantity=qty, unit_price_material=n.base_material_cost,
                    labor_hours_per_unit=n.estimated_hours_per_unit,
                    labor_rate_applied=65.00,
                )
            except (ValueError, Normative.DoesNotExist):
                continue

        lead.status = "INTERNA_PROCJENA"
        lead.internal_notes += "\nProject: " + proj.code
        lead.save()
        messages.success(request, _("Project ") + proj.code + " kreiran.")
        return redirect("burza:bathroom_pdf", pk=calc.pk)

    desc    = lead.description or ""
    m2_re   = re.search(r"(\d+(?:[.,]\d+)?)\s*m", desc)
    floor_m2 = float(m2_re.group(1).replace(",", ".")) if m2_re else 8.0
    quality  = "Premium" if "premium" in desc.lower() else ("Luxus" if "luxus" in desc.lower() else "Standard")

    suggested_ids = []
    q_pk_map = {"standard": 1, "premium": 2, "luxus": 3}
    try: suggested_ids.append(Normative.objects.get(pk=q_pk_map.get(quality.lower(), 1)).pk)
    except Normative.DoesNotExist: pass
    for kw in ["Verfugung", "Abdichtung"]:
        try: suggested_ids.append(Normative.objects.get(name__icontains=kw).pk)
        except Normative.DoesNotExist: pass
    for kw, nm in [("wc","WC-Montage"),("dusch","Dusche komplett"),("badewanne","Badewanne"),("waschbecken","Waschbecken")]:
        if kw in desc.lower():
            try: suggested_ids.append(Normative.objects.get(name__icontains=nm).pk)
            except Normative.DoesNotExist: pass
    if "komplett" in desc.lower():
        try: suggested_ids.append(Normative.objects.get(name__icontains="Abbruch Fliesen komplett").pk)
        except Normative.DoesNotExist: pass
    if "sanit" in desc.lower():
        try: suggested_ids.append(Normative.objects.get(name__icontains="mittel neue").pk)
        except Normative.DoesNotExist: pass
    if "elektro" in desc.lower():
        try: suggested_ids.append(Normative.objects.get(name__icontains="Elektroarbeiten gering").pk)
        except Normative.DoesNotExist: pass

    normatives = Normative.objects.all().order_by("unit", "name")
    partners   = Partner.objects.filter(company=company).order_by("name") if company else []
    return render(request, "calculator/bathroom_to_project.html", {
        "lead": lead, "normatives": normatives, "suggested_ids": suggested_ids,
        "floor_m2": floor_m2, "quality": quality, "partners": partners,
    })


@login_required
def bathroom_pdf(request, pk):
    import io, re
    from calculator.models import Calculation
    from burza.models import ProjectLead
    from projects.models import Project
    from django.template.loader import get_template

    # pk moze biti Calculation.pk ili Lead.pk — probaj oba
    calculation = Calculation.objects.filter(pk=pk).first()
    if not calculation:
        lead = get_object_or_404(ProjectLead, pk=pk)
        notes = lead.internal_notes or ""
        codes = re.findall(r'BAD-[A-Z0-9-]+', notes)
        if codes:
            proj = Project.objects.filter(code=codes[-1]).first()
            if proj:
                calculation = Calculation.objects.filter(project=proj).first()
        if not calculation:
            return HttpResponse(
                "<h2 style='font-family:sans-serif;padding:40px'>Keine Kalkulation gefunden.</h2>"
                "<p style='font-family:sans-serif;padding:0 40px'>"
                "Bitte erst <a href='/burza/lead/" + str(pk) + "/bathroom/'>Angebot erstellen</a>.</p>",
                status=404)
    LABOR_RATE  = 65.0
    # Recalculate totals using LABOR_RATE (ignores labor_rate_applied in DB)
    raw = calculation.items.select_related('normative').all()
    mat_total   = sum(float(it.unit_price_material) * it.quantity for it in raw)
    lohn_total  = sum(it.labor_hours_per_unit * LABOR_RATE * it.quantity for it in raw)
    net_cost    = round(mat_total + lohn_total, 2)
    margin      = calculation.margin_percentage / 100
    vat         = calculation.vat_percentage / 100
    offer_net   = round(net_cost * (1 + margin), 2)
    offer_vat   = round(offer_net * (1 + vat), 2)
    totals = {
        'material': round(mat_total, 2),
        'labor':    round(lohn_total, 2),
        'net_cost': net_cost,
        'offer_total_net': offer_net,
        'offer_total_vat': offer_vat,
    }
    raw_items   = calculation.items.select_related("normative").all()
    items_with_total = []
    for it in raw_items:
        mat_line   = float(it.unit_price_material) * it.quantity
        labor_line = it.labor_hours_per_unit * LABOR_RATE * it.quantity
        items_with_total.append({
            "obj":         it,
            "mat_line":    round(mat_line, 2),
            "labor_line":  round(labor_line, 2),
            "total_line":  round(mat_line + labor_line, 2),
        })
    context     = {"calculation": calculation, "items": items_with_total,
                   "totals": totals, "project": calculation.project,
                   "labor_rate": LABOR_RATE}
    try:
        from xhtml2pdf import pisa
        template = get_template("calculator/bathroom_pdf.html")
        html     = template.render(context)
        buf      = io.BytesIO()
        pisa.pisaDocument(io.BytesIO(html.encode("UTF-8")), buf)
        code     = calculation.project.code.replace("/", "-")
        response = HttpResponse(buf.getvalue(), content_type="application/pdf")
        response["Content-Disposition"] = "inline; filename=\"Angebot_" + code + ".pdf\""
        return response
    except Exception:
        logger.exception("Bathroom PDF failed")
    return HttpResponse("PDF Fehler", status=500)


@login_required
def kanban_col(request, status):
    """HTMX partial: returns cards for a single kanban column."""
    company = get_company(request)
    sa = is_superadmin(request)
    valid_statuses = [s[0] for s in ProjectLead.Status.choices]
    if status not in valid_statuses:
        return render(request, 'burza/partials/kanban_col.html', {'leads': [], 'status': status})

    if sa:
        leads = ProjectLead.objects.filter(status=status).select_related('company', 'taken_by')
    elif status == 'NA_BURZI':
        leads = ProjectLead.objects.filter(status='NA_BURZI', is_public=True)
    else:
        leads = ProjectLead.objects.filter(company=company, status=status)

    return render(request, 'burza/partials/kanban_col.html', {
        'leads': leads.order_by('-created_at')[:30],
        'status': status,
        'is_superadmin': sa,
        'company': company,
    })
