from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from core.company_utils import get_user_company
from .models import Livestock, Field, CropPlan


@login_required
def livestock_list(request):
    company = get_user_company(request)
    animals = Livestock.objects.filter(company=company)

    vrsta = request.GET.get('vrsta')
    status = request.GET.get('status')
    if vrsta:
        animals = animals.filter(vrsta=vrsta)
    if status:
        animals = animals.filter(status=status)

    stats = {
        'total': animals.count(),
        'krave': animals.filter(vrsta='krava').count(),
        'gravidne': animals.filter(status='gravidno').count(),
    }
    return render(request, 'livestock/livestock_list.html', {
        'animals': animals,
        'stats': stats,
        'vrsta_choices': Livestock.VRSTA_CHOICES,
        'status_choices': Livestock.STATUS_CHOICES,
    })


@login_required
def livestock_detail(request, pk):
    company = get_user_company(request)
    animal = get_object_or_404(Livestock, pk=pk, company=company)
    health_records = animal.health_records.all()[:10]
    milk_records = animal.milk_records.all()[:30]
    return render(request, 'livestock/livestock_detail.html', {
        'animal': animal,
        'health_records': health_records,
        'milk_records': milk_records,
    })


@login_required
def livestock_create(request):
    company = get_user_company(request)
    if request.method == 'POST':
        try:
            animal = Livestock(
                company=company,
                ear_tag=request.POST.get('ear_tag', '').strip(),
                name=request.POST.get('name', '').strip(),
                vrsta=request.POST.get('vrsta', 'krava'),
                status=request.POST.get('status', 'aktivno'),
                breed=request.POST.get('breed', '').strip(),
                notes=request.POST.get('notes', '').strip(),
            )
            dob = request.POST.get('date_of_birth')
            if dob:
                animal.date_of_birth = dob
            weight = request.POST.get('weight_kg')
            if weight:
                animal.weight_kg = weight
            milk = request.POST.get('avg_daily_milk_l')
            if milk:
                animal.avg_daily_milk_l = milk
            animal.is_organic = request.POST.get('is_organic') == 'on'
            animal.save()
            messages.success(request, f'Grlo {animal.ear_tag} uspjesno dodano.')
            return redirect('livestock:detail', pk=animal.pk)
        except Exception as e:
            messages.error(request, f'Greska: {e}')

    return render(request, 'livestock/livestock_create.html', {
        'vrsta_choices': Livestock.VRSTA_CHOICES,
        'status_choices': Livestock.STATUS_CHOICES,
    })


@login_required
def field_list(request):
    company = get_user_company(request)
    fields = Field.objects.filter(company=company)
    return render(request, 'livestock/field_list.html', {
        'fields': fields,
    })


@login_required
def crop_list(request):
    company = get_user_company(request)
    crops = CropPlan.objects.filter(company=company)
    return render(request, 'livestock/crop_list.html', {
        'crops': crops,
    })




# ============================================================
#  VET PORTAL & MILKING ROBOT API
# ============================================================

def vet_quick_entry(request, farm_token):
    """Public page for vet to log treatment -- no login, token auth."""
    from companies.models import Company
    from django.utils import timezone
    from .models import HealthRecord

    company = Company.objects.filter(booking_slug=farm_token).first()
    if not company:
        return render(request, 'livestock/vet_404.html')

    animals = Livestock.objects.filter(company=company, status='aktivno').order_by('ear_tag')

    if request.method == 'POST':
        ear_tag = request.POST.get('ear_tag')
        animal = Livestock.objects.filter(company=company, ear_tag=ear_tag).first()
        if not animal:
            messages.error(request, 'Grlo nije pronadjeno: %s' % ear_tag)
            return redirect('livestock:vet_quick_entry', farm_token=farm_token)

        HealthRecord.objects.create(
            animal=animal,
            datum=request.POST.get('datum') or timezone.now().date(),
            tip=request.POST.get('tip', 'tretman'),
            opis=request.POST.get('opis', ''),
            veterinar=request.POST.get('veterinar', ''),
            lijek=request.POST.get('lijek', ''),
            kolicina=request.POST.get('kolicina', ''),
            karencija_do=request.POST.get('karencija_do') or None,
        )

        # Notify farmer via WhatsApp
        try:
            from core.whatsapp import send_text
            owner_phone = company.phone or company.mobile
            if owner_phone:
                msg = 'Veterinar %s je zabilje\u017eio tretman za %s (%s).\nLijek: %s\nKarencija do: %s' % (
                    request.POST.get('veterinar', 'N/A'),
                    animal.ear_tag, animal.name or animal.get_vrsta_display(),
                    request.POST.get('lijek', 'N/A'),
                    request.POST.get('karencija_do', 'Nema'),
                )
                send_text(owner_phone, msg)
        except Exception:
            pass

        messages.success(request, 'Tretman zabilje\u017een za %s' % ear_tag)
        return redirect('livestock:vet_quick_entry', farm_token=farm_token)

    return render(request, 'livestock/vet_quick_entry.html', {
        'company': company, 'animals': animals, 'farm_token': farm_token,
    })


@login_required
def vet_dashboard(request):
    """Veterinar dashboard -- sve farme koje obilazi."""
    from accounts.models import CompanyMembership
    from django.utils import timezone
    from .models import HealthRecord

    memberships = CompanyMembership.objects.filter(user=request.user, is_active=True)
    companies = [m.company for m in memberships]

    all_animals = Livestock.objects.filter(company__in=companies, status='aktivno')
    recent_records = HealthRecord.objects.filter(
        animal__company__in=companies
    ).select_related('animal', 'animal__company').order_by('-datum')[:20]

    today = timezone.now().date()
    in_karencija = HealthRecord.objects.filter(
        animal__company__in=companies, karencija_do__gte=today
    ).select_related('animal', 'animal__company')

    return render(request, 'livestock/vet_dashboard.html', {
        'companies': companies,
        'total_animals': all_animals.count(),
        'recent_records': recent_records,
        'in_karencija': in_karencija,
    })


from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse


@csrf_exempt
def robot_identify(request):
    """API for milking robot -- identify animal by ear tag, check karencija."""
    import json
    from companies.models import Company

    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)

    auth = request.META.get('HTTP_AUTHORIZATION', '')
    api_key = request.GET.get('api_key', '')

    if not auth and not api_key:
        return JsonResponse({'error': 'Authorization required'}, status=401)

    token = auth.replace('Bearer ', '') if auth else api_key

    company = Company.objects.filter(settings__contains={'robot_api_key': token}).first()
    if not company:
        company = Company.objects.filter(booking_slug=token).first()
    if not company:
        return JsonResponse({'error': 'Invalid token'}, status=403)

    try:
        data = json.loads(request.body)
    except Exception:
        data = {}

    ear_tag = data.get('ear_tag', request.GET.get('ear_tag', ''))
    if not ear_tag:
        return JsonResponse({'error': 'ear_tag required'}, status=400)

    try:
        animal = Livestock.objects.get(company=company, ear_tag=ear_tag)
    except Livestock.DoesNotExist:
        return JsonResponse({'error': 'Animal not found', 'ear_tag': ear_tag}, status=404)

    is_blocked = animal.is_in_karencija

    response = {
        'ear_tag': animal.ear_tag,
        'name': animal.name,
        'vrsta': animal.get_vrsta_display(),
        'status': animal.get_status_display(),
        'breed': animal.breed,
        'is_blocked': is_blocked,
        'can_milk': not is_blocked and animal.vrsta == 'krava',
        'can_slaughter': not is_blocked,
    }

    if is_blocked:
        response['karencija_end'] = str(animal.karencija_end)
        response['karencija_reason'] = animal.karencija_reason
        response['action'] = 'DIVERT'
        response['warning'] = 'KARENCIJA ACTIVE -- do not mix milk into main tank'
    else:
        response['action'] = 'MILK'

    last_milk = animal.milk_records.order_by('-datum').first()
    if last_milk:
        response['last_milk'] = {
            'date': str(last_milk.datum),
            'liters': float(last_milk.ukupno_l),
        }

    return JsonResponse(response)



# ══════════════════════════════════════════════════════════════
# INSTITUCIJSKI API (HAPIH, JRDZ, Sanitarna, VetIS)
# ══════════════════════════════════════════════════════════════

@csrf_exempt
def institutional_api(request, scope):
    """API za institucije — token auth, rate limited, audited."""
    import json
    from django.http import JsonResponse
    from .models import InstitutionalAccessToken, InstitutionalAccessLog, Livestock, HealthRecord

    auth = request.META.get('HTTP_AUTHORIZATION', '').replace('Bearer ', '')
    api_key = request.GET.get('token', '') or auth
    if not api_key:
        return JsonResponse({'error': 'Token required'}, status=401)

    try:
        token_obj = InstitutionalAccessToken.objects.select_related('company').get(
            token=api_key, scope=scope, is_active=True,
        )
    except InstitutionalAccessToken.DoesNotExist:
        return JsonResponse({'error': 'Invalid or expired token'}, status=403)

    if not token_obj.is_valid:
        return JsonResponse({'error': 'Token expired'}, status=403)
    if not token_obj.rate_ok:
        return JsonResponse({'error': 'Rate limit exceeded'}, status=429)

    token_obj.record_access()
    company = token_obj.company
    ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0] or request.META.get('REMOTE_ADDR', '')

    # Audit log
    InstitutionalAccessLog.objects.create(
        token=token_obj, endpoint=scope, ip_address=ip, response_code=200,
    )

    if scope == 'hapih':
        # EU Reg 2019/6 — knjiga lijekova
        records = HealthRecord.objects.filter(
            animal__company=company,
        ).select_related('animal').order_by('-datum')[:100]
        data = [{
            'ear_tag': r.animal.ear_tag,
            'animal_type': r.animal.get_vrsta_display(),
            'date': str(r.datum),
            'type': r.get_tip_display(),
            'description': r.opis,
            'drug': r.lijek,
            'dose': r.kolicina,
            'withdrawal_until': str(r.karencija_do) if r.karencija_do else None,
            'in_withdrawal': r.u_karenciji,
            'veterinarian': r.veterinar,
        } for r in records]
        return JsonResponse({'farm': company.name, 'oib': company.oib, 'records': data, 'count': len(data)})

    elif scope == 'jrdz':
        # Kretanje zivotinja
        animals = Livestock.objects.filter(company=company).order_by('ear_tag')
        data = [{
            'ear_tag': a.ear_tag,
            'type': a.get_vrsta_display(),
            'breed': a.breed,
            'status': a.get_status_display(),
            'date_of_birth': str(a.date_of_birth) if a.date_of_birth else None,
            'weight_kg': float(a.weight_kg) if a.weight_kg else None,
            'is_organic': a.is_organic,
        } for a in animals]
        return JsonResponse({'farm': company.name, 'oib': company.oib, 'animals': data, 'count': len(data)})

    elif scope == 'sanitarna':
        # Blokade mlijeka u realnom vremenu
        from django.utils import timezone
        today = timezone.now().date()
        blocked = HealthRecord.objects.filter(
            animal__company=company, karencija_do__gte=today,
        ).select_related('animal')
        data = [{
            'ear_tag': r.animal.ear_tag,
            'drug': r.lijek,
            'withdrawal_until': str(r.karencija_do),
            'days_remaining': (r.karencija_do - today).days,
            'milk_blocked': True,
            'meat_blocked': True,
        } for r in blocked]
        return JsonResponse({
            'farm': company.name, 'oib': company.oib,
            'blocked_animals': data, 'count': len(data),
            'farm_status': 'BLOCKED' if data else 'CLEAR',
        })

    elif scope == 'vetis':
        # Kompletna vet knjiga
        animals = Livestock.objects.filter(company=company).prefetch_related('health_records')
        data = []
        for a in animals:
            records = [{
                'date': str(r.datum), 'type': r.get_tip_display(),
                'drug': r.lijek, 'dose': r.kolicina,
                'withdrawal': str(r.karencija_do) if r.karencija_do else None,
                'vet': r.veterinar,
            } for r in a.health_records.order_by('-datum')[:10]]
            data.append({
                'ear_tag': a.ear_tag, 'name': a.name,
                'type': a.get_vrsta_display(), 'status': a.get_status_display(),
                'health_records': records,
            })
        return JsonResponse({'farm': company.name, 'oib': company.oib, 'animals': data})

    return JsonResponse({'error': 'Unknown scope'}, status=400)


@login_required
def token_management(request):
    """Farmer manages institutional access tokens."""
    from core.company_utils import get_user_company
    from .models import InstitutionalAccessToken
    company = get_user_company(request)
    if not company:
        return redirect('dashboard')

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'create':
            InstitutionalAccessToken.objects.create(
                company=company,
                name=request.POST.get('name', ''),
                scope=request.POST.get('scope', 'hapih'),
                created_by=request.user,
            )
            messages.success(request, 'Token kreiran!')
        elif action == 'revoke':
            pk = request.POST.get('token_id')
            InstitutionalAccessToken.objects.filter(pk=pk, company=company).update(is_active=False)
            messages.success(request, 'Token opozvan.')
        elif action == 'regenerate':
            pk = request.POST.get('token_id')
            t = InstitutionalAccessToken.objects.filter(pk=pk, company=company).first()
            if t:
                t.regenerate()
                messages.success(request, 'Novi token generiran.')
        return redirect('livestock:token_management')

    tokens = InstitutionalAccessToken.objects.filter(company=company).order_by('-created_at')
    return render(request, 'livestock/token_management.html', {
        'tokens': tokens, 'company': company,
    })



# ══════════════════════════════════════════════════════════════
# INSPEKTORSKI MOD — QR + PDF + Panic Button
# ══════════════════════════════════════════════════════════════

def inspector_live_view(request, scope, token):
    """Read-only HTML view za inspektora — skenira QR, vidi podatke."""
    from .models import InstitutionalAccessToken, Livestock, HealthRecord
    from django.utils import timezone

    try:
        tok = InstitutionalAccessToken.objects.select_related('company').get(
            token=token, scope=scope, is_active=True,
        )
    except InstitutionalAccessToken.DoesNotExist:
        return render(request, 'livestock/inspector_invalid.html')

    if not tok.is_valid:
        return render(request, 'livestock/inspector_invalid.html')

    tok.record_access()
    company = tok.company
    today = timezone.now().date()

    animals = Livestock.objects.filter(company=company, status='aktivno').order_by('ear_tag')
    blocked = HealthRecord.objects.filter(
        animal__company=company, karencija_do__gte=today,
    ).select_related('animal').order_by('-karencija_do')
    all_records = HealthRecord.objects.filter(
        animal__company=company,
    ).select_related('animal').order_by('-datum')[:50]

    return render(request, 'livestock/inspector_live_view.html', {
        'company': company, 'scope': scope, 'animals': animals,
        'blocked': blocked, 'all_records': all_records, 'today': today,
        'total_animals': animals.count(), 'total_blocked': blocked.count(),
    })


@login_required
def inspector_panic_button(request):
    """Panic button — farmer generira QR + PDF za inspekciju."""
    from core.company_utils import get_user_company
    from .models import InstitutionalAccessToken, Livestock, HealthRecord
    from django.utils import timezone

    company = get_user_company(request)
    if not company:
        return redirect('dashboard')

    today = timezone.now().date()

    if request.method == 'POST':
        scope = request.POST.get('scope', 'sanitarna')

        # Create temporary token (expires in 24h)
        tok = InstitutionalAccessToken.objects.create(
            company=company,
            name='Inspekcija %s' % today.strftime('%d.%m.%Y'),
            scope=scope,
            created_by=request.user,
            expires_at=timezone.now() + timezone.timedelta(hours=24),
        )

        qr_url = request.build_absolute_uri(
            '/livestock/inspect/%s/%s/' % (scope, tok.token)
        )

        return render(request, 'livestock/panic_qr.html', {
            'company': company, 'qr_url': qr_url, 'token': tok,
            'scope': scope,
        })

    # GET: show panic button options
    blocked = HealthRecord.objects.filter(
        animal__company=company, karencija_do__gte=today,
    ).count()

    return render(request, 'livestock/panic_button.html', {
        'company': company, 'blocked_count': blocked,
    })


@login_required
def generate_inspection_pdf(request):
    """Generira PDF Knjigu lijecenja za inspekciju — WeasyPrint."""
    from django.http import HttpResponse
    from core.company_utils import get_user_company
    from .models import Livestock, HealthRecord
    from core.doc_integrity import get_integrity_badge_context
    from django.utils import timezone
    import io

    company = get_user_company(request)
    if not company:
        return redirect('dashboard')

    today = timezone.now().date()
    scope = request.GET.get('scope', 'sanitarna')

    animals = Livestock.objects.filter(company=company).order_by('ear_tag')
    records = HealthRecord.objects.filter(
        animal__company=company,
    ).select_related('animal').order_by('animal__ear_tag', '-datum')

    blocked = HealthRecord.objects.filter(
        animal__company=company, karencija_do__gte=today,
    ).select_related('animal')

    ctx = {
        'company': company, 'animals': animals, 'records': records,
        'blocked': blocked, 'today': today, 'scope': scope,
        'generated_at': timezone.now(),
    }

    # Add integrity badge
    from django.template.loader import render_to_string
    style = request.GET.get('style', 'modern')
    template_map = {
        'modern': 'livestock/inspection_pdf_modern.html',
        'datev': 'livestock/inspection_pdf_datev.html',
        'viskovic': 'livestock/inspection_pdf_viskovic.html',
    }
    pdf_template = template_map.get(style, 'livestock/inspection_pdf_modern.html')
    html = render_to_string(pdf_template, ctx)
    ctx.update(get_integrity_badge_context(
        request=request, document_id='INS-%s-%s' % (company.oib, today),
        content=html, company=company,
    ))
    style = request.GET.get('style', 'modern')
    template_map = {
        'modern': 'livestock/inspection_pdf_modern.html',
        'datev': 'livestock/inspection_pdf_datev.html',
        'viskovic': 'livestock/inspection_pdf_viskovic.html',
    }
    pdf_template = template_map.get(style, 'livestock/inspection_pdf_modern.html')
    html = render_to_string(pdf_template, ctx)

    # Generate PDF with WeasyPrint
    try:
        from weasyprint import HTML
        pdf = HTML(string=html).write_pdf()
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="Knjiga_lijecenja_%s_%s.pdf"' % (
            company.oib, today.strftime('%Y%m%d'))
        return response
    except Exception:
        # Fallback: return HTML
        return HttpResponse(html)
