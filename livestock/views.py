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
