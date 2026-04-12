"""
Virtualni Ured — views.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.translation import gettext as _
from django.http import HttpResponse
from django.utils import timezone
from django.db.models import Count, Q

from core.company_utils import get_user_company


@login_required
def virtual_office_dashboard(request):
    """Dashboard — pregled pristigle poste za firmu."""
    company = get_user_company(request)

    from virtual_office.models import IncomingMail, VirtualMailbox

    mailbox, _ = VirtualMailbox.objects.get_or_create(
        company=company,
        defaults={'address_line': ''}
    )

    mail_qs = IncomingMail.objects.filter(company=company)

    # Stats
    total = mail_qs.count()
    unread = mail_qs.filter(client_viewed=False).count()
    by_type = dict(mail_qs.values_list('mail_type').annotate(c=Count('id')).values_list('mail_type', 'c'))
    by_status = dict(mail_qs.values_list('status').annotate(c=Count('id')).values_list('status', 'c'))

    # Recent mail (last 30 items)
    recent = mail_qs[:30]

    return render(request, 'virtual_office/dashboard.html', {
        'company': company,
        'mailbox': mailbox,
        'total': total,
        'unread': unread,
        'by_type': by_type,
        'by_status': by_status,
        'recent_mail': recent,
    })


@login_required
def mail_detail(request, pk):
    """Detalj pristigle poste — oznaci kao pregledano."""
    company = get_user_company(request)
    from virtual_office.models import IncomingMail

    mail = get_object_or_404(IncomingMail, pk=pk, company=company)

    # Oznaci kao pregledano
    if not mail.client_viewed:
        mail.client_viewed = True
        mail.client_viewed_at = timezone.now()
        mail.save(update_fields=['client_viewed', 'client_viewed_at'])

    return render(request, 'virtual_office/mail_detail.html', {
        'mail': mail,
        'company': company,
    })


@login_required
def mail_create(request):
    """Unos nove pristigle poste (admin/racunovodja)."""
    company = get_user_company(request)

    if request.method == 'POST':
        from virtual_office.models import IncomingMail

        mail = IncomingMail(
            company=company,
            received_date=request.POST.get('received_date', timezone.now().date()),
            sender=request.POST.get('sender', ''),
            mail_type=request.POST.get('mail_type', 'letter'),
            subject=request.POST.get('subject', ''),
            status='received',
            notes=request.POST.get('notes', ''),
            processed_by=request.user,
            processed_at=timezone.now(),
        )

        if request.FILES.get('scanned_file'):
            mail.scanned_file = request.FILES['scanned_file']
            mail.status = 'scanned'

        mail.save()
        messages.success(request, f'Posta zaprimljena: {mail.sender or "bez posiljatelja"}')
        return redirect('virtual_office:dashboard')

    return render(request, 'virtual_office/mail_form.html', {
        'company': company,
        'mail_types': [
            ('letter', 'Pismo'),
            ('invoice', 'Racun'),
            ('notice', 'Obavijest'),
            ('tax', 'Porezna uprava'),
            ('court', 'Sud / Odvjetnik'),
            ('bank', 'Banka'),
            ('insurance', 'Osiguranje'),
            ('package', 'Paket'),
            ('other', 'Ostalo'),
        ],
    })


@login_required
def mail_upload_scan(request, pk):
    """Upload skenirani dokument za postojecu postu."""
    company = get_user_company(request)
    from virtual_office.models import IncomingMail

    mail = get_object_or_404(IncomingMail, pk=pk, company=company)

    if request.method == 'POST' and request.FILES.get('scanned_file'):
        mail.scanned_file = request.FILES['scanned_file']
        mail.status = 'scanned'
        mail.processed_by = request.user
        mail.processed_at = timezone.now()
        mail.save()
        messages.success(request, _('Sken uploadan.'))

    return redirect('virtual_office:detail', pk=pk)


@login_required
def mail_archive(request, pk):
    """Arhiviraj postu."""
    company = get_user_company(request)
    from virtual_office.models import IncomingMail

    mail = get_object_or_404(IncomingMail, pk=pk, company=company)
    mail.status = 'archived'
    mail.save(update_fields=['status'])
    messages.success(request, _('Posta arhivirana.'))
    return redirect('virtual_office:dashboard')
