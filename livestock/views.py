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
