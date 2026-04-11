"""
core/views_inspector.py — Inspektor Dashboard

Javni read-only pristup za inspektore — BEZ LOGINA.
Inspektor skenira QR → token u URL-u → vidi podatke firme.

Flow:
  1. Firma klikne Panic Button
  2. Odabere tip inspekcije + period
  3. Generira se QR (InspectionToken, 24-72h)
  4. Inspektor skenira QR
  5. Otvara se /inspektor/<token>/ — read-only dashboard
"""
import logging
from datetime import date, timedelta
from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt

from core.models import InspectionToken

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════
#  PUBLIC — Inspektor Dashboard (bez logina)
# ═══════════════════════════════════════════════════

def inspector_dashboard(request, token):
    """Inspektor pristupa ovdje — QR skenira, vidi read-only podatke."""
    tok = get_object_or_404(InspectionToken, token=token)

    if not tok.is_valid:
        return render(request, 'inspector/expired.html', {'token': tok})

    # Zahtijeva potpisan protokol
    if not hasattr(tok, 'protocol') or not tok.protocol.signed_at:
        return redirect('inspector_register', token=token)

    # Record access
    ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
    if ',' in ip:
        ip = ip.split(',')[0].strip()
    tok.record_access(ip=ip)

    company = tok.company
    scope = tok.scope
    date_from = tok.date_from or date(date.today().year, 1, 1)
    date_to = tok.date_to or date.today()

    ctx = {
        'token': tok,
        'company': company,
        'scope': scope,
        'date_from': date_from,
        'date_to': date_to,
        'tabs': _get_visible_tabs(scope),
    }

    # Gather data based on scope
    if scope in ('porezna', 'all'):
        ctx['porezna'] = _gather_porezna(company, date_from, date_to)
    if scope in ('pos', 'all'):
        ctx['pos'] = _gather_pos(company, date_from, date_to)
    if scope in ('radna', 'all'):
        ctx['radna'] = _gather_radna(company, date_from, date_to)
    if scope in ('sanitarna', 'hapih', 'jrdz', 'vetis', 'all'):
        ctx['livestock'] = _gather_livestock(company, scope)

    return render(request, 'inspector/dashboard.html', ctx)


def _get_visible_tabs(scope):
    tabs = []
    if scope in ('porezna', 'all'):
        tabs.append({'id': 'porezna', 'label': 'Porezna', 'icon': 'fa-landmark'})
    if scope in ('pos', 'all'):
        tabs.append({'id': 'pos', 'label': 'POS / Fiskalizacija', 'icon': 'fa-cash-register'})
    if scope in ('radna', 'all'):
        tabs.append({'id': 'radna', 'label': 'Radna inspekcija', 'icon': 'fa-hard-hat'})
    if scope in ('sanitarna', 'hapih', 'jrdz', 'vetis', 'all'):
        tabs.append({'id': 'livestock', 'label': 'Veterina / Sanitarna', 'icon': 'fa-paw'})
    return tabs


# ── POREZNA ────────────────────────────────────────────────────

def _gather_porezna(company, date_from, date_to):
    data = {}

    # Fakture u periodu
    try:
        from invoicing.models import Invoice
        from django.db.models import Sum, Count

        invoices = Invoice.objects.filter(
            company=company,
            date_issued__date__gte=date_from,
            date_issued__date__lte=date_to,
        ).exclude(status__in=['CANCELLED', 'STORNO', 'DRAFT'])

        data['invoices_count'] = invoices.count()
        agg = invoices.aggregate(total=Sum('total'), tax=Sum('tax_amount'))
        data['invoices_total'] = float(agg['total'] or 0)
        data['invoices_tax'] = float(agg['tax'] or 0)

        # Po tipu
        data['issued'] = invoices.filter(doctype__in=['R', 'FA', 'RN', 'A']).aggregate(
            cnt=Count('id'), total=Sum('total'))
        data['received'] = invoices.filter(doctype__in=['URA', 'IRA']).aggregate(
            cnt=Count('id'), total=Sum('total'))

        # Zadnjih 20 faktura
        data['recent_invoices'] = list(invoices.order_by('-date_issued').values(
            'number', 'doctype', 'client_name', 'client_oib', 'date_issued',
            'total', 'tax_amount', 'status'
        )[:20])
    except Exception as e:
        data['error_invoices'] = str(e)

    # Konto bilanca
    try:
        from konto.services_file import get_profit_loss, get_balance_sheet
        data['pnl'] = get_profit_loss(company, date_from, date_to)
        data['balance_sheet'] = get_balance_sheet(company, date_to)
    except Exception as e:
        data['error_konto'] = str(e)

    # PDV
    try:
        from konto.services_file import calculate_vat_period
        month = date_to.month
        year = date_to.year
        data['vat'] = {}
        tp = calculate_vat_period(company, 'monthly', year, month=month)
        data['vat'] = {
            'output': float(tp.total_output_vat),
            'input': float(tp.total_input_vat),
            'payable': float(tp.vat_payable),
            'revenue': float(tp.total_revenue),
        }
    except Exception:
        pass

    # Saldakonti
    try:
        from konto.services_file import get_open_receivables, get_open_payables
        data['receivables'] = get_open_receivables(company)[:15]
        data['payables'] = get_open_payables(company)[:15]
    except Exception:
        data['receivables'] = []
        data['payables'] = []

    return data


# ── POS / FISKALIZACIJA ────────────────────────────────────────

def _gather_pos(company, date_from, date_to):
    data = {}

    try:
        from pos.models import POSSession, POSReceipt, POSPaymentLine, POSTerminal
        from django.db.models import Sum, Count

        # Terminali
        terminals = POSTerminal.objects.filter(company=company, is_active=True)
        data['terminals'] = list(terminals.values('name', 'terminal_code', 'pos_type', 'is_active'))

        # Sesije u periodu
        sessions = POSSession.objects.filter(
            terminal__company=company,
            opened_at__date__gte=date_from,
            opened_at__date__lte=date_to,
        ).order_by('-opened_at')

        data['sessions_count'] = sessions.count()
        data['sessions'] = list(sessions.values(
            'session_number', 'terminal__name', 'status',
            'opened_at', 'closed_at', 'opening_cash', 'closing_cash',
        )[:30])

        # Računi
        receipts = POSReceipt.objects.filter(
            session__terminal__company=company,
            created_at__date__gte=date_from,
            created_at__date__lte=date_to,
        ).exclude(status='cancelled')

        data['receipts_count'] = receipts.count()
        agg = receipts.aggregate(total=Sum('total'), tax=Sum('tax_amount'))
        data['receipts_total'] = float(agg['total'] or 0)
        data['receipts_tax'] = float(agg['tax'] or 0)

        # Fiskalizacija status
        data['fiscalized'] = receipts.filter(jir__isnull=False).exclude(jir='').count()
        data['not_fiscalized'] = receipts.filter(jir__isnull=True).count() + receipts.filter(jir='').count()

        # Po načinu plaćanja
        payments = POSPaymentLine.objects.filter(
            receipt__session__terminal__company=company,
            receipt__created_at__date__gte=date_from,
            receipt__created_at__date__lte=date_to,
        ).values('method').annotate(total=Sum('amount'), cnt=Count('id'))
        data['payment_methods'] = list(payments)

        # Zadnjih 20 računa s JIR/ZKI
        data['recent_receipts'] = list(receipts.order_by('-created_at').values(
            'global_number', 'total', 'tax_amount', 'status',
            'zki', 'jir', 'fiscal_datetime', 'created_at',
            'session__terminal__name',
        )[:20])

        # Fiskalni certifikat
        try:
            from invoicing.fiscal_models import FiscalCertificate
            cert = FiscalCertificate.objects.filter(company=company).first()
            if cert:
                data['cert'] = {
                    'subject': cert.subject_name or '',
                    'issuer': cert.issuer_name or '',
                    'valid_from': str(cert.valid_from) if cert.valid_from else '',
                    'valid_to': str(cert.valid_to) if cert.valid_to else '',
                    'is_valid': cert.is_valid if hasattr(cert, 'is_valid') else True,
                }
        except Exception:
            pass

    except Exception as e:
        data['error'] = str(e)

    return data


# ── RADNA INSPEKCIJA ──────────────────────────────────────────

def _gather_radna(company, date_from, date_to):
    data = {}

    try:
        from worktime.models import TimeEntry, EmployeeProfile
        from django.db.models import Sum, Count, F

        # Zaposlenici
        profiles = EmployeeProfile.objects.filter(company=company)
        data['employees_count'] = profiles.count()
        data['employees'] = list(profiles.values(
            'user__first_name', 'user__last_name', 'user__username',
            'hourly_rate', 'employment_type',
        )[:50])

        # Evidencija radnog vremena
        entries = TimeEntry.objects.filter(
            user__employeeprofile__company=company,
            date__gte=date_from,
            date__lte=date_to,
        )

        data['entries_count'] = entries.count()
        agg = entries.aggregate(
            reg=Sum('regular_hours'),
            ot=Sum('overtime_hours'),
            night=Sum('night_hours'),
        )
        data['total_regular'] = float(agg['reg'] or 0)
        data['total_overtime'] = float(agg['ot'] or 0)
        data['total_night'] = float(agg['night'] or 0)

        # Prekovremeni po zaposleniku (ZOR limit: 180h/god, 10h/tj)
        from django.db.models import F as Ff
        overtime_by_user = entries.values(
            'user__first_name', 'user__last_name'
        ).annotate(
            ot_total=Sum('overtime_hours')
        ).filter(ot_total__gt=0).order_by('-ot_total')[:20]
        data['overtime_by_user'] = list(overtime_by_user)

        # ZOR compliance provjera
        warnings = []
        for row in overtime_by_user:
            ot = float(row['ot_total'] or 0)
            name = f"{row['user__first_name']} {row['user__last_name']}"
            if ot > 180:
                warnings.append(f'{name}: {ot:.0f}h prekovremeno (ZOR limit 180h/god!)')
            elif ot > 150:
                warnings.append(f'{name}: {ot:.0f}h prekovremeno (blizu ZOR limita)')
        data['zor_warnings'] = warnings

        # Putni nalozi
        try:
            from worktime.models import TravelOrder
            travels = TravelOrder.objects.filter(
                user__employeeprofile__company=company,
                date_from__gte=date_from,
                date_to__lte=date_to,
            )
            data['travel_orders'] = travels.count()
        except Exception:
            data['travel_orders'] = 0

    except Exception as e:
        data['error'] = str(e)

    # Payroll
    try:
        from payroll.models import PayrollRun
        runs = PayrollRun.objects.filter(
            company=company,
            year__gte=date_from.year,
        ).order_by('-year', '-month')[:12]
        data['payroll_runs'] = list(runs.values(
            'year', 'month', 'status', 'total_gross', 'total_net', 'total_tax',
        ))
    except Exception:
        data['payroll_runs'] = []

    return data


# ── LIVESTOCK / SANITARNA ─────────────────────────────────────

def _gather_livestock(company, scope):
    data = {}
    try:
        from livestock.models import Animal, HealthRecord, Field
        from django.db.models import Count

        animals = Animal.objects.filter(company=company)
        data['animals_count'] = animals.count()
        data['animals'] = list(animals.values(
            'ear_tag', 'name', 'species', 'breed', 'birth_date', 'status',
        )[:50])

        # Karencija
        today = date.today()
        data['in_karencija'] = HealthRecord.objects.filter(
            animal__company=company,
            karencija_do__gte=today,
        ).count()

        # Zdravstveni zapisi
        records = HealthRecord.objects.filter(animal__company=company).order_by('-date')
        data['health_records'] = list(records.values(
            'animal__ear_tag', 'animal__name', 'date', 'diagnosis',
            'treatment', 'vet_name', 'karencija_do',
        )[:30])

        # Polja
        data['fields_count'] = Field.objects.filter(company=company).count()

    except Exception as e:
        data['error'] = str(e)

    return data


# ═══════════════════════════════════════════════════
#  PANIC BUTTON — generiranje tokena (login required)
# ═══════════════════════════════════════════════════

@login_required
def panic_button(request):
    """Inspekcijski pristup — firma generira QR + inspektor se registrira."""
    from core.company_utils import get_user_company
    company = get_user_company(request)
    if not company:
        return redirect('dashboard')

    if request.method == 'POST':
        scope = request.POST.get('scope', 'all')
        hours = int(request.POST.get('hours', '24'))
        date_from = request.POST.get('date_from', '')
        date_to = request.POST.get('date_to', '')

        from datetime import datetime
        df = None
        dt = None
        try:
            if date_from:
                df = datetime.strptime(date_from, '%Y-%m-%d').date()
            if date_to:
                dt = datetime.strptime(date_to, '%Y-%m-%d').date()
        except ValueError:
            pass

        if not df:
            df = date(date.today().year, 1, 1)
        if not dt:
            dt = date.today()

        scope_labels = dict(InspectionToken.SCOPE_CHOICES)
        tok = InspectionToken.objects.create(
            company=company,
            scope=scope,
            label=f'{scope_labels.get(scope, scope)} — {company.name} — {date.today().strftime("%d.%m.%Y")}',
            date_from=df,
            date_to=dt,
            expires_at=timezone.now() + timedelta(hours=hours),
            created_by=request.user,
        )

        # Audit
        try:
            from core.models import BookingSignature
            BookingSignature.log(request, 'create', target_obj=tok,
                target_repr=f'Inspekcija: {scope_labels.get(scope)} {df}—{dt}',
                changes={'scope': scope, 'hours': hours})
        except Exception:
            pass

        qr_url = request.build_absolute_uri(f'/inspektor/{tok.token}/')

        return render(request, 'inspector/qr_generated.html', {
            'company': company,
            'token': tok,
            'qr_url': qr_url,
            'scope': scope,
            'scope_label': scope_labels.get(scope, scope),
        })

    # GET
    active_tokens = InspectionToken.objects.filter(
        company=company, is_active=True,
        expires_at__gt=timezone.now(),
    ).select_related('protocol')

    return render(request, 'inspector/panic_button.html', {
        'company': company,
        'active_tokens': active_tokens,
    })


@login_required
def panic_revoke(request, token_id):
    """Revoke an inspection token."""
    from core.company_utils import get_user_company
    company = get_user_company(request)
    tok = get_object_or_404(InspectionToken, pk=token_id, company=company)
    tok.is_active = False
    tok.save(update_fields=['is_active'])
    return redirect('panic_button')



# ═══════════════════════════════════════════════════
#  INSPECTOR REGISTRATION — inspektor se identificira
# ═══════════════════════════════════════════════════

def inspector_register(request, token):
    """Inspektor popunjava podatke i potpisuje zapisnik PRIJE pristupa."""
    from core.models import InspectionProtocol

    tok = get_object_or_404(InspectionToken, token=token)

    if not tok.is_valid:
        return render(request, 'inspector/expired.html', {'token': tok})

    # Ako je vec potpisan — idi na dashboard
    if hasattr(tok, 'protocol') and tok.protocol.signed_at:
        return redirect('inspector_dashboard', token=token)

    scope_labels = dict(InspectionToken.SCOPE_CHOICES)

    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        badge = request.POST.get('badge', '').strip()
        institution = request.POST.get('institution', '').strip()
        phone = request.POST.get('inspector_phone', '').strip()
        email = request.POST.get('inspector_email', '').strip()
        legal_basis = request.POST.get('legal_basis', '').strip()
        signature = request.POST.get('signature', '')
        terms = request.POST.get('terms_accepted', '')
        lat = request.POST.get('latitude', '')
        lng = request.POST.get('longitude', '')

        errors = []
        if not first_name:
            errors.append('Ime je obavezno.')
        if not last_name:
            errors.append('Prezime je obavezno.')
        if not terms:
            errors.append('Morate prihvatiti uvjete pristupa.')
        if not signature:
            errors.append('Potpis je obavezan.')

        if errors:
            return render(request, 'inspector/register.html', {
                'token': tok,
                'scope_label': scope_labels.get(tok.scope, tok.scope),
                'errors': errors,
                'form_data': request.POST,
            })

        ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
        if ',' in ip:
            ip = ip.split(',')[0].strip()

        protocol, created = InspectionProtocol.objects.update_or_create(
            token=tok,
            defaults={
                'inspector_first_name': first_name,
                'inspector_last_name': last_name,
                'inspector_badge': badge,
                'inspector_institution': institution,
                'inspector_phone': phone,
                'inspector_email': email,
                'legal_basis': legal_basis,
                'terms_accepted': True,
                'signature': signature,
                'signed_at': timezone.now(),
                'signed_ip': ip or None,
                'latitude': float(lat) if lat else None,
                'longitude': float(lng) if lng else None,
            }
        )

        # Audit
        try:
            from core.models import BookingSignature
            BookingSignature.log(request, 'approve', target_obj=protocol,
                target_repr=f'Inspektor: {first_name} {last_name} ({badge})',
                changes={
                    'scope': tok.scope,
                    'institution': institution,
                    'ip': ip,
                })
        except Exception:
            pass

        return redirect('inspector_dashboard', token=token)

    return render(request, 'inspector/register.html', {
        'token': tok,
        'scope_label': scope_labels.get(tok.scope, tok.scope),
        'errors': [],
        'form_data': {},
    })
