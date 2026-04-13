from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.translation import gettext as _
from django.db.models import Q, Count, Avg
from django.utils import timezone
from core.company_utils import get_user_company
from .models import Ticket, TicketMessage, TicketTemplate
from django.db import IntegrityError, DatabaseError


def _get_company(request):
    return get_user_company(request)


@login_required
def helpdesk_dashboard(request):
    company = _get_company(request)
    qs = Ticket.objects.filter(company=company)
    now = timezone.now()
    open_tickets = qs.filter(status__in=['open', 'in_progress', 'waiting_client', 'waiting_internal'])
    stats = {
        'total': qs.count(),
        'open': qs.filter(status='open').count(),
        'in_progress': qs.filter(status='in_progress').count(),
        'waiting': qs.filter(status__in=['waiting_client', 'waiting_internal']).count(),
        'resolved': qs.filter(status='resolved').count(),
        'closed': qs.filter(status='closed').count(),
        'unassigned': open_tickets.filter(assigned_to__isnull=True).count(),
        'overdue': open_tickets.filter(sla_deadline__lt=now).count(),
        'avg_satisfaction': qs.filter(satisfaction_rating__isnull=False).aggregate(avg=Avg('satisfaction_rating'))['avg'],
    }
    by_priority = qs.filter(status__in=['open', 'in_progress']).values('priority').annotate(cnt=Count('id'))
    by_category = qs.filter(status__in=['open', 'in_progress']).values('category').annotate(cnt=Count('id'))
    recent = qs.order_by('-created_at')[:10]
    return render(request, 'helpdesk/dashboard.html', {
        'stats': stats, 'by_priority': by_priority, 'by_category': by_category, 'recent': recent,
    })


@login_required
def ticket_list(request):
    company = _get_company(request)
    qs = Ticket.objects.filter(company=company)
    status = request.GET.get('status')
    priority = request.GET.get('priority')
    category = request.GET.get('category')
    assigned = request.GET.get('assigned')
    search = request.GET.get('q')
    if status:
        qs = qs.filter(status=status)
    if priority:
        qs = qs.filter(priority=priority)
    if category:
        qs = qs.filter(category=category)
    if assigned == 'me':
        qs = qs.filter(assigned_to=request.user)
    elif assigned == 'none':
        qs = qs.filter(assigned_to__isnull=True)
    if search:
        qs = qs.filter(Q(ticket_number__icontains=search) | Q(subject__icontains=search) | Q(client__name__icontains=search))
    return render(request, 'helpdesk/list.html', {
        'tickets': qs,
        'current_status': status, 'current_priority': priority,
        'current_category': category, 'current_assigned': assigned,
        'q': search or '',
        'statuses': Ticket.STATUS_CHOICES,
        'priorities': Ticket.PRIORITY_CHOICES,
        'categories': Ticket.CATEGORY_CHOICES,
    })


@login_required
def ticket_create(request):
    company = _get_company(request)
    if request.method == 'POST':
        ticket = Ticket(company=company, created_by=request.user)
        ticket.ticket_number = ticket.generate_ticket_number()
        ticket.subject = request.POST.get('subject', '')
        ticket.description = request.POST.get('description', '')
        ticket.category = request.POST.get('category', 'other')
        ticket.priority = request.POST.get('priority', 'normal')
        ticket.source = request.POST.get('source', 'internal')
        ticket.contact_name = request.POST.get('contact_name', '')
        ticket.contact_email = request.POST.get('contact_email', '')
        ticket.contact_phone = request.POST.get('contact_phone', '')
        ticket.tags = request.POST.get('tags', '')
        client_id = request.POST.get('client')
        if client_id:
            from partners.models import Partner
            ticket.client = Partner.objects.filter(id=client_id, company=company).first()
        assigned_id = request.POST.get('assigned_to')
        if assigned_id:
            from django.contrib.auth.models import User
            ticket.assigned_to = User.objects.filter(id=assigned_id).first()
        ticket.set_sla()
        # Retry on duplicate ticket number (race condition)
        for _attempt in range(5):
            ticket.ticket_number = ticket.generate_ticket_number()
            try:
                ticket.save()
                break
            except (IntegrityError, DatabaseError):
                if _attempt >= 4:
                    raise
                continue
        initial_msg = request.POST.get('description', '')
        if initial_msg:
            TicketMessage.objects.create(
                ticket=ticket, sender=request.user,
                sender_name=request.user.get_full_name() or request.user.username,
                body=initial_msg,
            )
        messages.success(request, f'Tiket {ticket.ticket_number} kreiran.')
        return redirect('helpdesk:detail', pk=ticket.pk)
    from partners.models import Partner
    from django.contrib.auth.models import User
    clients = Partner.objects.filter(company=company)
    from accounts.models import UserProfile
    company_user_ids = UserProfile.objects.filter(company=company).values_list('user_id', flat=True)
    users = User.objects.filter(pk__in=company_user_ids, is_active=True)
    return render(request, 'helpdesk/form.html', {
        'clients': clients, 'users': users,
        'categories': Ticket.CATEGORY_CHOICES,
        'priorities': Ticket.PRIORITY_CHOICES,
    })


@login_required
def ticket_detail(request, pk):
    company = _get_company(request)
    ticket = get_object_or_404(Ticket, pk=pk, company=company)
    ticket_messages = ticket.messages.all()
    templates = TicketTemplate.objects.filter(company=company, is_active=True)
    from django.contrib.auth.models import User
    users = User.objects.filter(is_active=True)
    return render(request, 'helpdesk/detail.html', {
        'ticket': ticket, 'messages': ticket_messages, 'templates': templates, 'users': users,
        'statuses': Ticket.STATUS_CHOICES,
    })


@login_required
def ticket_reply(request, pk):
    company = _get_company(request)
    ticket = get_object_or_404(Ticket, pk=pk, company=company)
    if request.method == 'POST':
        body = request.POST.get('body', '')
        is_internal = request.POST.get('is_internal') == 'on'
        msg = TicketMessage(
            ticket=ticket, sender=request.user,
            sender_name=request.user.get_full_name() or request.user.username,
            body=body, is_internal=is_internal,
        )
        if 'attachment' in request.FILES:
            msg.attachment = request.FILES['attachment']
        msg.save()
        if not ticket.first_response_at and not is_internal:
            ticket.first_response_at = timezone.now()
            ticket.save(update_fields=['first_response_at'])
        if ticket.status == 'open':
            ticket.status = 'in_progress'
            ticket.save(update_fields=['status', 'updated_at'])
        messages.success(request, _('Odgovor poslan.'))
    return redirect('helpdesk:detail', pk=ticket.pk)


@login_required
def ticket_assign(request, pk):
    company = _get_company(request)
    ticket = get_object_or_404(Ticket, pk=pk, company=company)
    if request.method == 'POST':
        user_id = request.POST.get('assigned_to')
        if user_id:
            from django.contrib.auth.models import User
            ticket.assigned_to = User.objects.filter(id=user_id).first()
        else:
            ticket.assigned_to = None
        ticket.save(update_fields=['assigned_to', 'updated_at'])
        messages.success(request, _('Tiket dodijeljen.'))
    return redirect('helpdesk:detail', pk=ticket.pk)


@login_required
def ticket_status(request, pk):
    company = _get_company(request)
    ticket = get_object_or_404(Ticket, pk=pk, company=company)
    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status:
            ticket.status = new_status
            if new_status == 'resolved':
                ticket.resolved_at = timezone.now()
            elif new_status == 'closed':
                ticket.closed_at = timezone.now()
                if not ticket.resolved_at:
                    ticket.resolved_at = timezone.now()
            ticket.save()
            messages.success(request, f'Status promijenjen u: {ticket.get_status_display()}')
    return redirect('helpdesk:detail', pk=ticket.pk)


@login_required
def ticket_close(request, pk):
    company = _get_company(request)
    ticket = get_object_or_404(Ticket, pk=pk, company=company)
    if request.method == 'POST':
        ticket.status = 'closed'
        ticket.closed_at = timezone.now()
        if not ticket.resolved_at:
            ticket.resolved_at = timezone.now()
        rating = request.POST.get('satisfaction_rating')
        if rating:
            ticket.satisfaction_rating = int(rating)
        ticket.satisfaction_comment = request.POST.get('satisfaction_comment', '')
        ticket.save()
        messages.success(request, f'Tiket {ticket.ticket_number} zatvoren.')
    return redirect('helpdesk:detail', pk=ticket.pk)


# ═══ VIP CONTACTS ═══

@login_required
def vip_list(request):
    """VIP kontakt lista — dodaj, uredi, obriši."""
    from .models import VIPContact
    from django.contrib.auth.models import User

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'add':
            phone = request.POST.get('phone', '').replace('+', '').replace(' ', '').replace('-', '')
            name = request.POST.get('name', '')
            note = request.POST.get('note', '')
            priority = request.POST.get('priority', 'critical')
            assign_id = request.POST.get('auto_assign_to')
            assign_to = User.objects.filter(id=assign_id).first() if assign_id else None
            if phone and name:
                VIPContact.objects.get_or_create(
                    phone=phone,
                    defaults={'name': name, 'note': note, 'priority': priority, 'auto_assign_to': assign_to}
                )
                messages.success(request, f'VIP kontakt {name} dodan.')
            else:
                messages.error(request, _('Telefon i ime su obavezni.'))

        elif action == 'delete':
            vip_id = request.POST.get('vip_id')
            VIPContact.objects.filter(id=vip_id).delete()
            messages.success(request, _('VIP kontakt obrisan.'))

        elif action == 'toggle':
            vip_id = request.POST.get('vip_id')
            vip = VIPContact.objects.filter(id=vip_id).first()
            if vip:
                vip.is_active = not vip.is_active
                vip.save(update_fields=['is_active'])
                messages.success(request, f'{vip.name} {"aktiviran" if vip.is_active else "deaktiviran"}.')

        elif action == 'edit':
            vip_id = request.POST.get('vip_id')
            vip = VIPContact.objects.filter(id=vip_id).first()
            if vip:
                vip.phone = request.POST.get('phone', vip.phone).replace('+', '').replace(' ', '').replace('-', '')
                vip.name = request.POST.get('name', vip.name)
                vip.note = request.POST.get('note', vip.note)
                vip.priority = request.POST.get('priority', vip.priority)
                assign_id = request.POST.get('auto_assign_to')
                vip.auto_assign_to = User.objects.filter(id=assign_id).first() if assign_id else None
                vip.save()
                messages.success(request, f'{vip.name} azuriran.')

        return redirect('helpdesk:vip_list')

    vips = VIPContact.objects.all()
    users = User.objects.filter(is_active=True)
    return render(request, 'helpdesk/vip_list.html', {
        'vips': vips,
        'users': users,
        'priorities': Ticket.PRIORITY_CHOICES,
    })
