import hashlib
import json

from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET

from .models import (
    CompetitorProfile, ComparisonFeature, CompetitorFeatureStatus,
    MigrationRequest, ReferralProgram, FreeToolUsage, SwitchWeekCampaign,
)


# ─── PUBLIC PAGES (no login required) ───────────────────────────────

def landing_page(request):
    """Glavna landing stranica — 'Prebaci se na LIMIT Connect'."""
    competitors = CompetitorProfile.objects.filter(is_active=True)
    active_campaign = SwitchWeekCampaign.objects.filter(
        is_active=True,
        start_date__lte=timezone.now().date(),
        end_date__gte=timezone.now().date(),
    ).first()

    context = {
        'competitors': competitors,
        'active_campaign': active_campaign,
        'page_title': 'LIMIT Connect — Moderna alternativa za vaše poslovanje',
        'meta_description': 'Prebacite se na LIMIT Connect. AI-powered ERP bez limita na račune. Besplatna migracija iz Minimaxa.',
    }
    return render(request, 'zeleni_otok/landing.html', context)


def pricing_page(request):
    """Javna pricing stranica s usporedbom."""
    from registration.models import PricingPlan
    plans = PricingPlan.objects.filter(is_active=True).order_by('sort_order')

    context = {
        'plans': plans,
        'page_title': 'Cjenik — LIMIT Connect',
        'meta_description': 'Transparentne cijene bez skrivenih troškova. Od besplatnog do enterprise paketa.',
    }
    return render(request, 'zeleni_otok/pricing.html', context)


def compare_page(request, competitor_slug=None):
    """Usporedna stranica LC vs konkurent."""
    if competitor_slug:
        competitor = get_object_or_404(CompetitorProfile, slug=competitor_slug, is_active=True)
        competitors = [competitor]
    else:
        competitors = CompetitorProfile.objects.filter(is_active=True)

    features = ComparisonFeature.objects.filter(is_active=True).select_related()

    # Build comparison matrix
    comparison_data = []
    for feature in features:
        row = {
            'feature': feature,
            'lc_available': feature.lc_available,
            'lc_note': feature.lc_note,
            'competitors': {}
        }
        for comp in competitors:
            try:
                status = CompetitorFeatureStatus.objects.get(competitor=comp, feature=feature)
                row['competitors'][comp.slug] = {
                    'status': status.status,
                    'note': status.note,
                    'display': status.get_status_display(),
                }
            except CompetitorFeatureStatus.DoesNotExist:
                row['competitors'][comp.slug] = {
                    'status': 'no',
                    'note': '',
                    'display': 'Ne',
                }
        comparison_data.append(row)

    context = {
        'competitors': competitors,
        'comparison_data': comparison_data,
        'competitor': competitors[0] if competitor_slug and competitors else None,
        'page_title': f'LIMIT Connect vs {competitors[0].name}' if competitor_slug and competitors else 'Usporedba ERP sustava',
        'meta_description': f'Detaljnausporedba LIMIT Connect i {competitors[0].name if competitor_slug and competitors else "konkurenata"}. Pogledajte zašto tvrtke prelaze na LC.',
    }
    return render(request, 'zeleni_otok/compare.html', context)


def migration_page(request):
    """Stranica za pokretanje migracije."""
    context = {
        'source_choices': MigrationRequest.SOURCE_CHOICES,
        'page_title': 'Besplatna migracija — LIMIT Connect',
        'meta_description': 'Prebacite se besplatno. Migracija podataka iz Minimaxa, Luceeda, Pantheona u LIMIT Connect.',
    }
    return render(request, 'zeleni_otok/migration.html', context)


@require_POST
def migration_submit(request):
    """Submit migracijskog zahtjeva."""
    mr = MigrationRequest(
        company_name=request.POST.get('company_name', ''),
        oib=request.POST.get('oib', ''),
        contact_name=request.POST.get('contact_name', ''),
        contact_email=request.POST.get('contact_email', ''),
        contact_phone=request.POST.get('contact_phone', ''),
        source_system=request.POST.get('source_system', 'minimax'),
        source_plan=request.POST.get('source_plan', ''),
        migrate_partners='migrate_partners' in request.POST,
        migrate_articles='migrate_articles' in request.POST,
        migrate_chart_of_accounts='migrate_chart_of_accounts' in request.POST,
        migrate_opening_balances='migrate_opening_balances' in request.POST,
        migrate_invoices='migrate_invoices' in request.POST,
        migrate_fixed_assets='migrate_fixed_assets' in request.POST,
        migrate_employees='migrate_employees' in request.POST,
        referral_code=request.POST.get('referral_code', ''),
    )

    if request.FILES.get('upload_file'):
        mr.upload_file = request.FILES['upload_file']
        mr.upload_format = mr.upload_file.name.rsplit('.', 1)[-1].lower() if '.' in mr.upload_file.name else ''

    if request.user.is_authenticated and hasattr(request, 'company'):
        mr.company = request.company

    mr.save()

    # Track referral
    if mr.referral_code:
        try:
            ref = ReferralProgram.objects.get(code=mr.referral_code, is_active=True)
            if ref.is_valid():
                ref.times_used += 1
                ref.save(update_fields=['times_used'])
        except ReferralProgram.DoesNotExist:
            pass

    if request.headers.get('HX-Request'):
        return render(request, 'zeleni_otok/partials/migration_success.html', {'migration': mr})

    return redirect('zeleni_otok:migration_status', pk=mr.pk)


def migration_status(request, pk):
    """Status migracije."""
    mr = get_object_or_404(MigrationRequest, pk=pk)
    context = {
        'migration': mr,
        'page_title': f'Status migracije — {mr.company_name}',
    }
    return render(request, 'zeleni_otok/migration_status.html', context)


# ─── FREE TOOLS ─────────────────────────────────────────────────────

def pdv_calculator(request):
    """Besplatni PDV kalkulator."""
    context = {
        'page_title': 'PDV Kalkulator — Besplatan online alat',
        'meta_description': 'Izračunajte PDV brzo i jednostavno. Podržava sve stope: 25%, 13%, 5%. Besplatan online kalkulator.',
    }
    return render(request, 'zeleni_otok/tools/pdv_calculator.html', context)


@require_POST
def pdv_calculate(request):
    """HTMX endpoint za PDV izračun."""
    try:
        amount = float(request.POST.get('amount', 0))
        rate = float(request.POST.get('rate', 25))
        direction = request.POST.get('direction', 'add')  # add or extract

        if direction == 'add':
            base = amount
            vat = round(base * rate / 100, 2)
            total = round(base + vat, 2)
        else:
            total = amount
            base = round(total / (1 + rate / 100), 2)
            vat = round(total - base, 2)

        result = {
            'base': f'{base:,.2f}',
            'vat': f'{vat:,.2f}',
            'total': f'{total:,.2f}',
            'rate': rate,
        }

        # Track usage
        _track_tool_usage(request, 'pdv_calc', {'amount': amount, 'rate': rate, 'direction': direction})

        return render(request, 'zeleni_otok/tools/partials/pdv_result.html', result)
    except (ValueError, TypeError):
        return render(request, 'zeleni_otok/tools/partials/pdv_result.html', {'error': 'Neispravan unos'})


def oib_lookup(request):
    """OIB provjera alat."""
    context = {
        'page_title': 'OIB Provjera — Besplatan online alat',
        'meta_description': 'Provjerite OIB tvrtke ili osobe. Besplatna provjera ispravnosti OIB-a s validacijom kontrolne znamenke.',
    }
    return render(request, 'zeleni_otok/tools/oib_lookup.html', context)


@require_POST
def oib_validate(request):
    """HTMX endpoint za OIB validaciju."""
    oib = request.POST.get('oib', '').strip()

    result = {'oib': oib, 'valid': False, 'errors': []}

    if not oib:
        result['errors'].append('Unesite OIB.')
    elif len(oib) != 11:
        result['errors'].append(f'OIB mora imati 11 znamenki (uneseno {len(oib)}).')
    elif not oib.isdigit():
        result['errors'].append('OIB smije sadržavati samo znamenke.')
    else:
        # ISO 7064, MOD 11,10 validation
        remainder = 10
        for digit in oib[:10]:
            remainder = (remainder + int(digit)) % 10
            if remainder == 0:
                remainder = 10
            remainder = (remainder * 2) % 11

        check = 11 - remainder
        if check == 10:
            check = 0

        if check == int(oib[10]):
            result['valid'] = True
            result['message'] = 'OIB je ispravan.'
        else:
            result['errors'].append(f'Kontrolna znamenka nije ispravna (očekivano: {check}, uneseno: {oib[10]}).')

    _track_tool_usage(request, 'oib_lookup', {'oib_length': len(oib)})

    return render(request, 'zeleni_otok/tools/partials/oib_result.html', result)


def r1_validator(request):
    """R-1 račun validator."""
    context = {
        'page_title': 'R-1 Validator — Provjera ispravnosti računa',
        'meta_description': 'Provjerite ispravnost R-1 računa prema Zakonu o fiskalizaciji. Besplatan online validator.',
    }
    return render(request, 'zeleni_otok/tools/r1_validator.html', context)


@require_POST
def r1_validate(request):
    """HTMX endpoint za R-1 validaciju."""
    errors = []
    warnings = []

    # Required fields per ZoFi
    fields = {
        'seller_oib': request.POST.get('seller_oib', '').strip(),
        'seller_name': request.POST.get('seller_name', '').strip(),
        'invoice_number': request.POST.get('invoice_number', '').strip(),
        'date_time': request.POST.get('date_time', '').strip(),
        'total': request.POST.get('total', '').strip(),
        'payment_method': request.POST.get('payment_method', ''),
        'operator_oib': request.POST.get('operator_oib', '').strip(),
        'zki': request.POST.get('zki', '').strip(),
        'jir': request.POST.get('jir', '').strip(),
    }

    # Validations
    if not fields['seller_oib'] or len(fields['seller_oib']) != 11:
        errors.append('OIB prodavatelja mora imati 11 znamenki.')
    if not fields['seller_name']:
        errors.append('Naziv prodavatelja je obavezan.')
    if not fields['invoice_number']:
        errors.append('Broj računa je obavezan.')
    elif '/' not in fields['invoice_number']:
        warnings.append('Broj računa bi trebao biti u formatu BROJ/PP/NU (npr. 1/1/1).')
    if not fields['date_time']:
        errors.append('Datum i vrijeme su obavezni.')
    if not fields['total']:
        errors.append('Ukupni iznos je obavezan.')
    if not fields['payment_method']:
        errors.append('Način plaćanja je obavezan.')
    if not fields['operator_oib'] or len(fields['operator_oib']) != 11:
        errors.append('OIB operatera mora imati 11 znamenki.')
    if not fields['zki'] and not fields['jir']:
        errors.append('Račun mora sadržavati ZKI ili JIR.')
    if fields['zki'] and len(fields['zki']) != 32:
        warnings.append(f'ZKI bi trebao imati 32 znaka (MD5 hash), uneseno: {len(fields["zki"])}.')
    if fields['jir'] and len(fields['jir']) != 36:
        warnings.append(f'JIR bi trebao biti UUID format (36 znakova), uneseno: {len(fields["jir"])}.')

    result = {
        'fields': fields,
        'errors': errors,
        'warnings': warnings,
        'valid': len(errors) == 0,
        'score': max(0, 100 - len(errors) * 15 - len(warnings) * 5),
    }

    _track_tool_usage(request, 'r1_validator', {'error_count': len(errors)})

    return render(request, 'zeleni_otok/tools/partials/r1_result.html', result)


def roi_calculator(request):
    """ROI kalkulator — 'Koliko štedite prelaskom na LC'."""
    context = {
        'page_title': 'ROI Kalkulator — Koliko štedite prelaskom na LIMIT Connect',
        'meta_description': 'Izračunajte uštede prelaskom na LIMIT Connect. Personalizirana usporedba troškova.',
    }
    return render(request, 'zeleni_otok/tools/roi_calculator.html', context)


@require_POST
def roi_calculate(request):
    """HTMX endpoint za ROI izračun."""
    from decimal import Decimal

    try:
        current_monthly = Decimal(request.POST.get('current_monthly', '0'))
        num_users = int(request.POST.get('num_users', '1'))
        num_invoices = int(request.POST.get('num_invoices', '100'))
        num_payrolls = int(request.POST.get('num_payrolls', '0'))
        source = request.POST.get('source_system', 'minimax')

        # Calculate competitor cost (Minimax example)
        competitor_cost = current_monthly
        extra_invoice_cost = Decimal('0')
        extra_payroll_cost = Decimal('0')

        if source == 'minimax':
            if num_invoices > 500:
                extra_invoice_cost = Decimal('0.05') * (num_invoices - 500)
            if num_payrolls > 50:
                extra_payroll_cost = Decimal('0.30') * (num_payrolls - 50)

        total_competitor = competitor_cost + extra_invoice_cost + extra_payroll_cost

        # Calculate LC cost
        if num_users <= 1 and num_invoices <= 10:
            lc_plan = 'LC Free'
            lc_monthly = Decimal('0')
        elif num_users <= 3:
            lc_plan = 'LC Starter'
            lc_monthly = Decimal('9.99')
        elif num_payrolls > 0:
            lc_plan = 'LC Business'
            lc_monthly = Decimal('19.99')
        elif num_users <= 10:
            lc_plan = 'LC Pro'
            lc_monthly = Decimal('34.99')
        else:
            lc_plan = 'LC Agency'
            lc_monthly = Decimal('49.99')

        extra_users_lc = Decimal('0')
        if num_users > 1 and lc_plan != 'LC Agency':
            included = {'LC Free': 1, 'LC Starter': 3, 'LC Business': 5, 'LC Pro': 10}.get(lc_plan, 1)
            if num_users > included:
                extra_users_lc = Decimal('4.99') * (num_users - included)

        total_lc = lc_monthly + extra_users_lc

        monthly_saving = total_competitor - total_lc
        yearly_saving = monthly_saving * 12
        migration_saving = Decimal('79.63')  # Minimax migration cost we don't charge

        result = {
            'competitor_base': f'{competitor_cost:.2f}',
            'competitor_extra_invoices': f'{extra_invoice_cost:.2f}',
            'competitor_extra_payrolls': f'{extra_payroll_cost:.2f}',
            'competitor_total': f'{total_competitor:.2f}',
            'lc_plan': lc_plan,
            'lc_monthly': f'{lc_monthly:.2f}',
            'lc_extra_users': f'{extra_users_lc:.2f}',
            'lc_total': f'{total_lc:.2f}',
            'monthly_saving': f'{monthly_saving:.2f}',
            'yearly_saving': f'{yearly_saving:.2f}',
            'migration_saving': f'{migration_saving:.2f}',
            'saves_money': monthly_saving > 0,
            'source': source,
        }

        _track_tool_usage(request, 'roi_calculator', {
            'current_monthly': str(current_monthly),
            'source': source,
            'saving': str(monthly_saving),
        })

        return render(request, 'zeleni_otok/tools/partials/roi_result.html', result)
    except (ValueError, TypeError) as e:
        return render(request, 'zeleni_otok/tools/partials/roi_result.html', {'error': str(e)})


def tax_calendar(request):
    """Porezni kalendar s push notifikacijama."""
    from datetime import date

    today = date.today()
    year = today.year
    month = today.month

    # HR tax deadlines
    deadlines = [
        {'date': f'{year}-{month:02d}-15', 'name': 'Predujam poreza na dobit', 'type': 'tax'},
        {'date': f'{year}-{month:02d}-15', 'name': 'Predujam poreza na dohodak', 'type': 'tax'},
        {'date': f'{year}-{month:02d}-15', 'name': 'Plaća — doprinosi i porez', 'type': 'payroll'},
        {'date': f'{year}-{month:02d}-20', 'name': 'PDV prijava (mjesečni obveznici)', 'type': 'vat'},
        {'date': f'{year}-{month:02d}-20', 'name': 'Intrastat prijava', 'type': 'eu'},
        {'date': f'{year}-{month:02d}-28', 'name': 'Obračunska prijava za doprinose', 'type': 'payroll'},
    ]

    # Quarterly deadlines
    if month in (1, 4, 7, 10):
        deadlines.append({'date': f'{year}-{month:02d}-20', 'name': 'PDV prijava (tromjesečni obveznici)', 'type': 'vat'})

    # Annual deadlines
    if month == 1:
        deadlines.append({'date': f'{year}-01-31', 'name': 'PD obrazac (porez na dohodak)', 'type': 'annual'})
    if month == 2:
        deadlines.append({'date': f'{year}-02-28', 'name': 'JOPPD godišnji', 'type': 'annual'})
    if month == 4:
        deadlines.append({'date': f'{year}-04-30', 'name': 'Prijava poreza na dobit (PD)', 'type': 'annual'})
        deadlines.append({'date': f'{year}-04-30', 'name': 'GFI-POD (FINA)', 'type': 'annual'})
    if month == 6:
        deadlines.append({'date': f'{year}-06-30', 'name': 'Godišnja prijava poreza na dohodak', 'type': 'annual'})

    deadlines.sort(key=lambda d: d['date'])

    context = {
        'deadlines': deadlines,
        'current_month': today.strftime('%B %Y'),
        'page_title': 'Porezni kalendar — Svi rokovi na jednom mjestu',
        'meta_description': 'Besplatni porezni kalendar s rokovima za PDV, doprinose, porez na dobit i dohodak.',
    }
    return render(request, 'zeleni_otok/tools/tax_calendar.html', context)


# ─── REFERRAL ───────────────────────────────────────────────────────

def referral_landing(request, code):
    """Landing stranica za referral link."""
    try:
        ref = ReferralProgram.objects.get(code=code, is_active=True)
        ref.times_shared += 1
        ref.save(update_fields=['times_shared'])

        context = {
            'referral': ref,
            'page_title': f'{ref.referrer_company.name} vas poziva na LIMIT Connect',
        }
        return render(request, 'zeleni_otok/referral_landing.html', context)
    except ReferralProgram.DoesNotExist:
        return redirect('zeleni_otok:landing')


# ─── HELPERS ────────────────────────────────────────────────────────

def _track_tool_usage(request, tool_name, input_data=None):
    """Spremi korištenje alata za analytics."""
    try:
        ip = request.META.get('REMOTE_ADDR', '')
        ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:16]
        session_id = request.session.session_key or ''

        FreeToolUsage.objects.create(
            tool=tool_name,
            session_id=session_id[:64],
            ip_hash=ip_hash,
            input_data=input_data or {},
            utm_source=request.GET.get('utm_source', ''),
            utm_medium=request.GET.get('utm_medium', ''),
            utm_campaign=request.GET.get('utm_campaign', ''),
        )
    except Exception:
        pass  # Analytics failure should never break the tool
