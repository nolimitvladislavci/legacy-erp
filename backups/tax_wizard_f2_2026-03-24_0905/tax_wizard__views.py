"""
tax_wizard/views.py — Porezni Savjetnik views

Wizard flow:
  1. GET  /porezni-savjetnik/start/PO-SD/  → kreira sesiju, redirect na wizard
  2. GET  /porezni-savjetnik/session/<id>/  → renderira wizard template
  3. POST /porezni-savjetnik/session/<id>/save/ → AJAX save koraka
  4. GET  /porezni-savjetnik/session/<id>/preview/ → preview podataka
  5. POST /porezni-savjetnik/session/<id>/finalize/ → zaključaj + XML
  6. GET  /porezni-savjetnik/session/<id>/xml/ → download XML

Button disable + "Obrada..." tekst se rješava na frontendu.
Greške se vraćaju kao JSON → frontend prikazuje Toast.
"""
import json
import logging

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.company_utils import get_user_company
from tax_wizard.models import (
    PausalTier,
    TaxDeadline,
    TaxFormTemplate,
    TaxWizardSession,
)
from tax_wizard.prefill_engine import PrefillEngine
from tax_wizard.services import (
    AIAdvisor,
    POSDCalculator,
    create_posd_session,
    finalize_posd_session,
    process_posd_step,
)

logger = logging.getLogger(__name__)


def _get_ip(request) -> str:
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    return xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR', '')


# ─── Dashboard ──────────────────────────────────────────────────

@login_required
def dashboard(request):
    """Porezni kalendar + pregled svih obrazaca za firmu."""
    company = get_user_company(request)
    if not company:
        return render(request, 'tax_wizard/no_company.html')

    deadlines = TaxDeadline.objects.filter(
        company=company,
    ).select_related('template').order_by('deadline_date')[:20]

    sessions = TaxWizardSession.objects.filter(
        company=company,
    ).select_related('template').order_by('-updated_at')[:10]

    # Dostupni obrasci za ovu firmu
    templates = TaxFormTemplate.objects.filter(is_active=True)
    if company.business_type:
        templates = templates.filter(
            applicable_business_types__contains=company.business_type,
        ) | templates.filter(applicable_business_types=[])

    # Paušal tierovi za info panel
    current_year = timezone.now().year
    tiers = PausalTier.get_all_tiers(current_year)

    return render(request, 'tax_wizard/dashboard.html', {
        'company': company,
        'deadlines': deadlines,
        'sessions': sessions,
        'templates': templates,
        'tiers': tiers,
        'current_year': current_year,
    })


# ─── Wizard Start ──────────────────────────────────────────────

@login_required
def wizard_start(request, form_type):
    """Pokreni novi wizard — kreira sesiju, prefill, redirect."""
    company = get_user_company(request)
    if not company:
        return JsonResponse({'ok': False, 'error': 'Nema tvrtke.'}, status=400)

    year = int(request.GET.get('year', timezone.now().year - 1))
    locale = request.GET.get('locale', 'hr')

    # Provjeri postoji li draft za ovu godinu
    existing = TaxWizardSession.objects.filter(
        company=company,
        template__form_type=form_type,
        tax_year=year,
        status__in=['draft', 'correction'],
    ).first()

    if existing:
        return redirect('tax_wizard:wizard_view', session_id=existing.id)

    # Referral — računovođa kreira za klijenta
    referred_by = None
    referral_company = None
    if request.GET.get('for_company'):
        from companies.models import Company
        try:
            target = Company.objects.get(pk=request.GET['for_company'])
            referred_by = request.user
            referral_company = company
            company = target
        except Company.DoesNotExist:
            pass

    try:
        session = create_posd_session(
            user=request.user,
            company=company,
            year=year,
            referred_by=referred_by,
            referral_company=referral_company,
            locale=locale,
        )
    except ValueError as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)

    # Prefill — povuci podatke iz sustava
    engine = PrefillEngine(company, year)
    try:
        breakdown = engine.aggregate()
        company_info = engine.get_company_info()

        # Spremi prefill podatke u sesiju
        session.form_data.update(company_info)
        session.form_data.update(breakdown.to_dict())
        session.form_data['_prefill_sources'] = breakdown.sources
        session.form_data['_prefill_timestamp'] = timezone.now().isoformat()
        session.save()

        logger.info(
            'Wizard started: %s PO-SD %d — prefill %.2f EUR from %s',
            company.name, year, breakdown.total, breakdown.sources,
        )
    except Exception as e:
        logger.warning('Prefill failed for %s: %s', company.name, e)
        # Wizard radi i bez prefilla — korisnik unosi ručno

    return redirect('tax_wizard:wizard_view', session_id=session.id)


# ─── Wizard View ────────────────────────────────────────────────

@login_required
def wizard_view(request, session_id):
    """Prikaz wizard sesije — renderira template s JSON stanjem."""
    session = get_object_or_404(
        TaxWizardSession.objects.select_related('template', 'company'),
        id=session_id,
    )

    # Provjeri pristup — samo vlasnik, referred_by, ili admin
    if (session.user != request.user
            and session.referred_by != request.user
            and not request.user.is_superuser):
        raise Http404

    # Template schema za frontend rendering
    schema = session.template.schema
    tiers = list(PausalTier.get_all_tiers(session.tax_year).values(
        'tier_number', 'min_income', 'max_income', 'annual_tax', 'monthly_tax',
    ))

    return render(request, 'tax_wizard/wizard.html', {
        'session': session,
        'session_json': json.dumps({
            'id': str(session.id),
            'current_step': session.current_step,
            'status': session.status,
            'form_data': session.form_data,
            'calculated_results': session.calculated_results,
            'ai_messages': session.ai_messages,
            'progress': session.progress_percent,
            'locale': session.locale,
            'is_editable': session.is_editable,
        }, default=str),
        'schema_json': json.dumps(schema),
        'tiers_json': json.dumps(tiers, default=str),
        'company': session.company,
        'template': session.template,
    })


# ─── Wizard Save Step (AJAX) ───────────────────────────────────

@login_required
@require_POST
def wizard_save_step(request, session_id):
    """
    AJAX endpoint — sprema korak wizarda.
    Body: { "step": int, "data": {...} }
    Response: { "ok": bool, "session": {...}, "ai_messages": [...], "errors": [...] }
    """
    session = get_object_or_404(TaxWizardSession, id=session_id)

    if session.user != request.user and session.referred_by != request.user:
        return JsonResponse({'ok': False, 'errors': ['Nemate pristup.']}, status=403)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'errors': ['Invalid JSON.']}, status=400)

    step = int(body.get('step', 0))
    data = body.get('data', {})

    result = process_posd_step(
        session=session,
        step=step,
        data=data,
        user=request.user,
        ip_address=_get_ip(request),
    )

    status_code = 200 if result['ok'] else 400
    return JsonResponse(result, status=status_code)


# ─── Wizard Preview ────────────────────────────────────────────

@login_required
def wizard_preview(request, session_id):
    """Preview — svi podaci za finalni pregled."""
    session = get_object_or_404(
        TaxWizardSession.objects.select_related('template', 'company'),
        id=session_id,
    )

    deadline = session.get_filing_deadline()
    is_overdue = session.is_overdue

    return JsonResponse({
        'ok': True,
        'form_data': session.form_data,
        'calculated_results': session.calculated_results,
        'ai_messages': session.ai_messages,
        'company': {
            'name': session.company.name,
            'oib': session.company.oib,
        },
        'deadline': deadline.isoformat() if deadline else None,
        'is_overdue': is_overdue,
        'status': session.status,
    })


# ─── Wizard Finalize ───────────────────────────────────────────

@login_required
@require_POST
def wizard_finalize(request, session_id):
    """Finaliziraj — generira XML, zaključaj sesiju."""
    session = get_object_or_404(TaxWizardSession, id=session_id)

    if session.user != request.user and not request.user.is_superuser:
        return JsonResponse({'ok': False, 'error': 'Nemate pristup.'}, status=403)

    result = finalize_posd_session(session, user=request.user)
    return JsonResponse(result)


# ─── XML Export ─────────────────────────────────────────────────

@login_required
def export_xml(request, session_id):
    """Download XML za ePorezna."""
    session = get_object_or_404(TaxWizardSession, id=session_id)

    if not session.xml_file:
        return JsonResponse({'error': 'XML nije generiran. Finalizirajte obrazac.'}, status=400)

    response = HttpResponse(session.xml_file.read(), content_type='application/xml')
    filename = f'PO-SD_{session.company.oib}_{session.tax_year}.xml'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    # Audit log
    from tax_wizard.models import TaxAuditLog
    TaxAuditLog.objects.create(
        session=session,
        user=request.user,
        action='xml_export',
        ip_address=_get_ip(request),
    )

    return response


# ─── PDF Export ─────────────────────────────────────────────────

@login_required
def export_pdf(request, session_id):
    """PDF preview — za arhivu ili print."""
    session = get_object_or_404(
        TaxWizardSession.objects.select_related('company'),
        id=session_id,
    )

    # Generiraj PDF iz HTML template-a
    from django.template.loader import render_to_string
    html = render_to_string('tax_wizard/posd_pdf.html', {
        'session': session,
        'data': session.form_data,
        'calc': session.calculated_results,
        'company': session.company,
        'generated_at': timezone.now(),
    })

    try:
        from weasyprint import HTML
        pdf = HTML(string=html).write_pdf()
        filename = f'PO-SD_{session.company.oib}_{session.tax_year}.pdf'
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except ImportError:
        return JsonResponse({'error': 'WeasyPrint nije instaliran.'}, status=500)


# ─── Simulacije ─────────────────────────────────────────────────

@login_required
def simulate_salary_dividend(request):
    """Plaća vs. dividenda simulator."""
    return JsonResponse({'status': 'coming_soon', 'phase': 'F3'})


@login_required
def simulate_deductions(request):
    """AI olakšice finder."""
    return JsonResponse({'status': 'coming_soon', 'phase': 'F2'})


@login_required
def simulate_pausal_tier(request):
    """Paušal tier optimizacija — real-time kalkulator."""
    company = get_user_company(request)
    year = int(request.GET.get('year', timezone.now().year))
    income = request.GET.get('income')

    if not income:
        # Vrati sve tierove za slider UI
        tiers = list(PausalTier.get_all_tiers(year).values(
            'tier_number', 'min_income', 'max_income',
            'annual_tax', 'monthly_tax', 'monthly_contributions',
        ))
        return JsonResponse({'tiers': tiers, 'year': year})

    # Izračun za specifični primitak
    from decimal import Decimal
    calc = POSDCalculator(year)
    result = calc.calculate(
        q1=Decimal(income) / 4,
        q2=Decimal(income) / 4,
        q3=Decimal(income) / 4,
        q4=Decimal(income) / 4,
    )

    advisor = AIAdvisor(year)
    messages = advisor.analyze(result, company)

    return JsonResponse({
        'calculation': {k: float(v) if isinstance(v, type(Decimal())) else v for k, v in result.items()},
        'ai_messages': messages,
    })


# ─── Računovođa B2B2C ──────────────────────────────────────────

@login_required
def accountant_dashboard(request):
    """Dashboard za računovođe — referred sesije."""
    referred = TaxWizardSession.objects.filter(
        referred_by=request.user,
    ).select_related('company', 'template').order_by('-updated_at')

    # Statistike
    stats = {
        'total': referred.count(),
        'draft': referred.filter(status='draft').count(),
        'review': referred.filter(status='review').count(),
        'finalized': referred.filter(status='final').count(),
        'submitted': referred.filter(status='submitted').count(),
    }

    return render(request, 'tax_wizard/accountant_dashboard.html', {
        'sessions': referred,
        'stats': stats,
    })


@login_required
@require_POST
def accountant_review(request, session_id):
    """Računovođa pregledava klijentov draft — odobri ili vrati na ispravak."""
    session = get_object_or_404(TaxWizardSession, id=session_id)

    if session.referred_by != request.user and not request.user.is_superuser:
        return JsonResponse({'ok': False, 'error': 'Nemate pristup.'}, status=403)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'Invalid JSON.'}, status=400)

    action = body.get('action')  # 'approve' or 'reject'
    notes = body.get('notes', '')

    if action == 'approve':
        session.status = 'final'
        session.reviewer = request.user
        session.review_notes = notes
        session.finalized_at = timezone.now()
        session.save()

        from tax_wizard.models import TaxAuditLog
        TaxAuditLog.objects.create(
            session=session,
            user=request.user,
            action='review',
            details={'decision': 'approved', 'notes': notes},
        )

        return JsonResponse({'ok': True, 'status': 'final'})

    elif action == 'reject':
        session.status = 'correction'
        session.reviewer = request.user
        session.review_notes = notes
        session.save()

        from tax_wizard.models import TaxAuditLog
        TaxAuditLog.objects.create(
            session=session,
            user=request.user,
            action='correction',
            details={'decision': 'rejected', 'notes': notes},
        )

        return JsonResponse({'ok': True, 'status': 'correction'})

    return JsonResponse({'ok': False, 'error': 'Nepoznata akcija.'}, status=400)


# ─── API ────────────────────────────────────────────────────────

@login_required
def api_deadlines(request):
    """API — svi rokovi za korisnikovu firmu."""
    company = get_user_company(request)
    if not company:
        return JsonResponse({'deadlines': []})

    deadlines = TaxDeadline.objects.filter(
        company=company,
    ).select_related('template').order_by('deadline_date')

    data = [{
        'id': str(d.id),
        'form_type': d.template.form_type,
        'deadline': d.deadline_date.isoformat(),
        'days_remaining': d.days_remaining,
        'urgency': d.urgency_level,
        'is_filed': d.is_filed,
        'penalty_min': float(d.penalty_min),
        'penalty_max': float(d.penalty_max),
    } for d in deadlines]

    return JsonResponse({'deadlines': data})


@login_required
def api_calendar(request, year):
    """API — godišnji kalendar obrazaca."""
    company = get_user_company(request)
    if not company:
        return JsonResponse({'year': year, 'calendar': {}})

    deadlines = TaxDeadline.objects.filter(
        company=company, tax_year=year,
    ).select_related('template').order_by('deadline_date')

    months = {}
    for d in deadlines:
        month = d.deadline_date.month
        if month not in months:
            months[month] = []
        months[month].append({
            'form_type': d.template.form_type,
            'deadline': d.deadline_date.isoformat(),
            'urgency': d.urgency_level,
            'is_filed': d.is_filed,
        })

    return JsonResponse({'year': year, 'calendar': months})
