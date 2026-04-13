"""
companies/views_komitent.py — KS LIMIT Komitent Manager

Dashboard za upravljanje klijentima knjigovodstvenog servisa.
Kreiranje, editiranje, promjena statusa, timeline, arhiva.
"""
import logging
from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.utils.translation import gettext as _
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404

from companies.models import Company, KomitentProfile, KomitentEvent, KomitentStatus
from django.db import DatabaseError

logger = logging.getLogger(__name__)


def _ensure_profiles():
    """Auto-create KomitentProfile for companies that don't have one."""
    companies_without = Company.objects.filter(komitent_profile__isnull=True)
    created = 0
    for c in companies_without:
        # Detect if Synesis import
        from synesis.models import SynesisConfig
        has_synesis = SynesisConfig.objects.filter(company=c).exists()

        KomitentProfile.objects.create(
            company=c,
            status='active',
            client_since=c.created_at.date() if c.created_at else None,
            synesis_imported=has_synesis,
            category=_detect_category(c),
        )
        created += 1
    return created


def _detect_category(company):
    bt = company.business_type
    mapping = {
        'doo': 'doo', 'jdoo': 'doo', 'dd': 'doo',
        'obrt': 'obrt', 'opg': 'opg', 'udruga': 'udruga',
        'ustanova': 'ustanova', 'gmbh': 'strano',
        'einzelunternehmen': 'strano', 'ag': 'strano',
    }
    return mapping.get(bt, '')


@login_required
def komitent_dashboard(request):
    """Glavni dashboard — KPI + lista svih komitenata."""
    if not request.user.is_superuser and not request.user.is_staff:
        messages.error(request, _('Nemate pristup upravljanju komitentima.'))
        return redirect('/')

    # Auto-create missing profiles
    created = _ensure_profiles()
    if created:
        messages.info(request, f'Automatski kreirano {created} profila za postojeće firme.')

    profiles = KomitentProfile.objects.select_related('company').all()

    # Filters
    status_filter = request.GET.get('status', '')
    category_filter = request.GET.get('category', '')
    search = request.GET.get('q', '').strip()

    if status_filter:
        profiles = profiles.filter(status=status_filter)
    if category_filter:
        profiles = profiles.filter(category=category_filter)
    if search:
        profiles = profiles.filter(
            Q(company__name__icontains=search) |
            Q(company__oib__icontains=search) |
            Q(contact_person__icontains=search) |
            Q(contact_email__icontains=search)
        )

    # KPI
    all_profiles = KomitentProfile.objects.all()
    kpi = {
        'total': all_profiles.count(),
        'active': all_profiles.filter(status='active').count(),
        'onboarding': all_profiles.filter(status='onboarding').count(),
        'notice': all_profiles.filter(status='notice').count(),
        'archived': all_profiles.filter(status='archived').count(),
        'paused': all_profiles.filter(status='paused').count(),
        'synesis': all_profiles.filter(synesis_imported=True).count(),
        'mrr': all_profiles.filter(status='active').aggregate(
            total=Sum('monthly_fee'))['total'] or Decimal('0'),
    }

    # Enrich profiles with stats
    enriched = []
    for p in profiles.order_by('company__name'):
        stats = {}
        try:
            stats['partners'] = p.company.partners.count()
            stats['invoices'] = p.company.invoices.count()
            stats['entries'] = p.company.journal_entries.count()
        except DatabaseError:
            stats = {'partners': 0, 'invoices': 0, 'entries': 0}

        # Subscription
        sub = None
        try:
            from registration.models import CompanySubscription
            sub = CompanySubscription.objects.filter(company=p.company).first()
        except DatabaseError:
            pass

        enriched.append({
            'profile': p,
            'company': p.company,
            'stats': stats,
            'subscription': sub,
        })

    return render(request, 'companies/komitent_dashboard.html', {
        'profiles': enriched,
        'kpi': kpi,
        'status_filter': status_filter,
        'category_filter': category_filter,
        'search': search,
        'status_choices': KomitentStatus.choices,
    })


@login_required
def komitent_detail(request, pk):
    """Detalji komitenta + timeline + edit."""
    profile = get_object_or_404(KomitentProfile, pk=pk)
    company = profile.company

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'update_profile':
            old_status = profile.status
            profile.status = request.POST.get('status', profile.status)
            profile.contact_person = request.POST.get('contact_person', '')
            profile.contact_phone = request.POST.get('contact_phone', '')
            profile.contact_email = request.POST.get('contact_email', '')
            profile.contract_type = request.POST.get('contract_type', '')
            profile.monthly_fee = Decimal(request.POST.get('monthly_fee', '0') or '0')
            profile.category = request.POST.get('category', '')
            profile.notes = request.POST.get('notes', '')
            profile.referred_by = request.POST.get('referred_by', '')

            date_fields = {
                'client_since': 'client_since',
                'notice_date': 'notice_date',
                'left_date': 'left_date',
                'next_review': 'next_review',
            }
            for field, attr in date_fields.items():
                val = request.POST.get(field, '')
                if val:
                    from datetime import datetime
                    try:
                        setattr(profile, attr, datetime.strptime(val, '%Y-%m-%d').date())
                    except ValueError:
                        pass
                else:
                    setattr(profile, attr, None)

            profile.save()

            # Log status change
            if old_status != profile.status:
                KomitentEvent.objects.create(
                    profile=profile,
                    event_type=_status_to_event(profile.status),
                    description=f'Status promijenjen: {old_status} → {profile.status}',
                    old_value=old_status,
                    new_value=profile.status,
                    created_by=request.user,
                )

            messages.success(request, f'Profil {company.name} ažuriran.')
            return redirect('companies:komitent_detail', pk=pk)

        elif action == 'add_note':
            note_text = request.POST.get('note_text', '').strip()
            event_type = request.POST.get('event_type', 'note')
            if note_text:
                KomitentEvent.objects.create(
                    profile=profile,
                    event_type=event_type,
                    description=note_text,
                    created_by=request.user,
                )
                messages.success(request, _('Bilješka dodana.'))
            return redirect('companies:komitent_detail', pk=pk)

    # Timeline
    events = profile.events.select_related('created_by').all()[:50]

    # Stats
    stats = {}
    try:
        stats['partners'] = company.partners.count()
        stats['invoices'] = company.invoices.count()
        stats['entries'] = company.journal_entries.count()
        stats['items'] = company.inventory_items.count()

        from invoicing.models import Invoice
        from django.db.models import Sum
        inv_agg = Invoice.objects.filter(company=company).exclude(
            status__in=['CANCELLED', 'STORNO', 'DRAFT']
        ).aggregate(total=Sum('total'))
        stats['revenue'] = float(inv_agg['total'] or 0)
    except (ValueError, TypeError):
        pass

    return render(request, 'companies/komitent_detail.html', {
        'profile': profile,
        'company': company,
        'events': events,
        'stats': stats,
        'status_choices': KomitentStatus.choices,
    })


@login_required
def komitent_create(request):
    """Kreiranje novog komitenta (firma + profil)."""
    if request.method == 'POST':
        try:
            c = Company(
                name=request.POST['name'],
                oib=request.POST.get('oib', ''),
                address=request.POST.get('address', ''),
                city=request.POST.get('city', ''),
                zip_code=request.POST.get('zip_code', ''),
                iban=request.POST.get('iban', ''),
                business_type=request.POST.get('business_type', 'obrt'),
                email=request.POST.get('email', ''),
                phone=request.POST.get('phone', ''),
            )
            c.save()

            p = KomitentProfile.objects.create(
                company=c,
                status='onboarding',
                client_since=date.today(),
                contact_person=request.POST.get('contact_person', ''),
                contact_phone=request.POST.get('contact_phone', ''),
                contact_email=request.POST.get('contact_email', ''),
                contract_type=request.POST.get('contract_type', 'mjesecni'),
                monthly_fee=Decimal(request.POST.get('monthly_fee', '0') or '0'),
                category=request.POST.get('category', ''),
                referred_by=request.POST.get('referred_by', ''),
                notes=request.POST.get('notes', ''),
            )

            KomitentEvent.objects.create(
                profile=p,
                event_type='created',
                description=f'Novi komitent kreiran: {c.name}',
                created_by=request.user,
            )

            messages.success(request, f'Komitent {c.name} kreiran.')
            return redirect('companies:komitent_detail', pk=p.pk)
        except (ValueError, TypeError) as e:
            messages.error(request, _('Nešto je pošlo krivo. Pokušajte ponovo ili kontaktirajte podršku.'))

    return render(request, 'companies/komitent_form.html', {
        'action': 'Novi komitent',
        'status_choices': KomitentStatus.choices,
    })


@login_required
def komitent_quick_status(request, pk):
    """AJAX quick status change."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)

    profile = get_object_or_404(KomitentProfile, pk=pk)
    new_status = request.POST.get('status', '')
    if new_status not in dict(KomitentStatus.choices):
        return JsonResponse({'error': 'Invalid status'}, status=400)

    old = profile.status
    profile.status = new_status

    # Auto-set dates
    if new_status == 'notice' and not profile.notice_date:
        profile.notice_date = date.today()
    if new_status == 'archived' and not profile.left_date:
        profile.left_date = date.today()
    if new_status == 'active' and old in ('archived', 'notice'):
        profile.notice_date = None
        profile.left_date = None

    profile.save()

    KomitentEvent.objects.create(
        profile=profile,
        event_type=_status_to_event(new_status),
        description=f'Brza promjena statusa: {old} → {new_status}',
        old_value=old,
        new_value=new_status,
        created_by=request.user,
    )

    return JsonResponse({'ok': True, 'old': old, 'new': new_status})


def _status_to_event(status):
    mapping = {
        'active': 'activated',
        'paused': 'paused',
        'notice': 'notice',
        'archived': 'archived',
        'blocked': 'blocked',
        'onboarding': 'created',
        'lead': 'created',
    }
    return mapping.get(status, 'note')
