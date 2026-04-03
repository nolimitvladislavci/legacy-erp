from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from datetime import date, timedelta
from .models import PravniPredmet, DimnjacarskaInspekcija


@login_required
def pravnik_dashboard(request):
    company = request.user.userprofile.company
    predmeti = PravniPredmet.objects.filter(company=company, status='aktivan')
    pred_s_rokom = predmeti.filter(
        rok__gte=date.today(),
        rok__lte=date.today() + timedelta(days=7)
    )
    return render(request, 'notariat/pravnik_dashboard.html', {
        'predmeti': predmeti,
        'pred_s_rokom': pred_s_rokom,
        'page_title': 'Odvjetnički dashboard',
    })


@login_required
def dimnjacari_dashboard(request):
    company = request.user.userprofile.company
    inspekcije = DimnjacarskaInspekcija.objects.filter(company=company)
    sljedeci = inspekcije.filter(
        sljedeci_pregled__gte=date.today(),
        sljedeci_pregled__lte=date.today() + timedelta(days=30)
    ).order_by('sljedeci_pregled')
    return render(request, 'notariat/dimnjacari_dashboard.html', {
        'inspekcije': inspekcije,
        'sljedeci': sljedeci,
        'page_title': 'Dimnjačarski pregledi',
    })
