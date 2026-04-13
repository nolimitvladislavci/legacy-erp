"""AML — views."""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from datetime import date
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

from core.company_utils import get_user_company


@login_required
def aml_dashboard(request):
    """AML dashboard — pregled profila i transakcija."""
    company = get_user_company(request)
    from aml.models import AMLClientProfile, AMLTransaction

    profiles = AMLClientProfile.objects.filter(
        company__in=company.memberships.values_list('company', flat=True)
    ).select_related('company') if hasattr(company, 'memberships') else \
        AMLClientProfile.objects.none()

    # Fallback: all profiles where assessed_by is in company
    if not profiles.exists():
        profiles = AMLClientProfile.objects.filter(
            assessed_by__profile__company=company
        ).select_related('company')

    # Also show profiles for this specific company
    own_profile = AMLClientProfile.objects.filter(company=company)
    all_profiles = (profiles | own_profile).distinct()

    today = date.today()
    stats = {
        'total': all_profiles.count(),
        'high_risk': all_profiles.filter(overall_risk__in=['high', 'very_high']).count(),
        'expired': all_profiles.filter(next_review_date__lt=today).count(),
        'pending_tx': AMLTransaction.objects.filter(
            company=company, status__in=['detected', 'under_review']).count(),
    }

    return render(request, 'aml/dashboard.html', {
        'company': company,
        'profiles': all_profiles[:50],
        'stats': stats,
        'today': today,
    })


@login_required
def aml_profile_detail(request, pk):
    """Detalj AML profila."""
    company = get_user_company(request)
    from aml.models import AMLClientProfile
    profile = get_object_or_404(AMLClientProfile, pk=pk)
    documents = profile.documents.all()
    transactions = profile.transactions.all()

    return render(request, 'aml/profile_detail.html', {
        'profile': profile,
        'documents': documents,
        'transactions': transactions,
        'company': company,
    })


@login_required
def aml_profile_create(request):
    """Kreiranje/editiranje AML profila."""
    company = get_user_company(request)
    from aml.models import AMLClientProfile, AMLRiskCategory
    from companies.models import Company

    if request.method == 'POST':
        target_company_id = request.POST.get('target_company')
        target = get_object_or_404(Company, pk=target_company_id)

        profile, created = AMLClientProfile.objects.get_or_create(
            company=target,
            defaults={
                'assessed_by': request.user,
                'assessment_date': date.today(),
                'next_review_date': date(date.today().year + 1, date.today().month, date.today().day),
                'client_type': request.POST.get('client_type', 'pravna'),
                'legal_form': request.POST.get('legal_form', ''),
                'ownership_structure': request.POST.get('ownership_structure', ''),
                'beneficial_owners': request.POST.get('beneficial_owners', ''),
                'overall_risk': request.POST.get('overall_risk', 'low'),
                'id_verified': 'id_verified' in request.POST,
                'registry_checked': 'registry_checked' in request.POST,
                'pep_check': 'pep_check' in request.POST,
                'sanctions_check': 'sanctions_check' in request.POST,
                'adverse_media': 'adverse_media' in request.POST,
                'notes': request.POST.get('notes', ''),
                'status': 'active',
            }
        )

        if not created:
            # Update existing
            for field in ['client_type', 'legal_form', 'ownership_structure',
                          'beneficial_owners', 'overall_risk', 'notes']:
                setattr(profile, field, request.POST.get(field, getattr(profile, field)))
            for check in ['id_verified', 'registry_checked', 'pep_check',
                          'sanctions_check', 'adverse_media']:
                setattr(profile, check, check in request.POST)
            profile.assessed_by = request.user
            profile.assessment_date = date.today()
            profile.save()

        messages.success(request,
            f'AML profil {"kreiran" if created else "azuriran"}: {target.name}')
        return redirect('aml:detail', pk=profile.pk)

    # GET
    from companies.models import Company
    companies = Company.objects.all().order_by('name')
    risk_categories = AMLRiskCategory.objects.all()

    return render(request, 'aml/profile_form.html', {
        'company': company,
        'companies': companies,
        'risk_categories': risk_categories,
    })


@login_required
def aml_transaction_report(request):
    """Prijava sumnjive transakcije."""
    company = get_user_company(request)

    if request.method == 'POST':
        from aml.models import AMLTransaction, AMLClientProfile

        profile_id = request.POST.get('client_profile')
        profile = AMLClientProfile.objects.get(pk=profile_id) if profile_id else None

        tx = AMLTransaction.objects.create(
            company=company,
            client_profile=profile,
            reported_by=request.user,
            transaction_date=request.POST.get('transaction_date', date.today()),
            amount=request.POST.get('amount', 0),
            description=request.POST.get('description', ''),
            suspicion_reason=request.POST.get('suspicion_reason', ''),
            status='detected',
        )

        messages.warning(request,
            f'Sumnjiva transakcija prijavljena: {tx.amount} EUR')
        return redirect('aml:dashboard')

    from aml.models import AMLClientProfile
    profiles = AMLClientProfile.objects.select_related('company').order_by('company__name')

    return render(request, 'aml/transaction_form.html', {
        'company': company,
        'profiles': profiles,
    })
