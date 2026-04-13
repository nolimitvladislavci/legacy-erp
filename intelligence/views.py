from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
from core.company_utils import get_user_company
from .models import IntelligenceJob, IntelligenceResult, FundOpportunity


@login_required
def dashboard(request):
    company = get_user_company(request)
    job = IntelligenceJob.objects.filter(company=company).first()
    recent_results = IntelligenceResult.objects.filter(
        job__company=company
    ).order_by('-created_at')[:10] if job else []
    funds = FundOpportunity.objects.filter(status='aktivan').order_by('rok_prijave')[:5]
    return render(request, 'intelligence/dashboard.html', {
        'job': job,
        'recent_results': recent_results,
        'funds': funds,
    })


@login_required
def results_list(request):
    company = get_user_company(request)
    results = IntelligenceResult.objects.filter(
        job__company=company
    ).order_by('-created_at')
    return render(request, 'intelligence/results_list.html', {
        'results': results,
    })


@login_required
def funds_list(request):
    funds = FundOpportunity.objects.filter(status='aktivan').order_by('rok_prijave')
    return render(request, 'intelligence/funds_list.html', {
        'funds': funds,
    })


@login_required
def fund_detail(request, pk):
    fund = get_object_or_404(FundOpportunity, pk=pk)
    return render(request, 'intelligence/fund_detail.html', {
        'fund': fund,
    })
