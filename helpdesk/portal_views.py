from django.shortcuts import render, get_object_or_404, redirect
from django.http import Http404
from django.db import transaction
from django.utils import timezone

from .models import Ticket, TicketMessage


def _get_partner_from_token(token):
    """Get partner from B2B portal token."""
    from partners.models import Partner
    try:
        return Partner.objects.get(b2b_token=token)
    except Partner.DoesNotExist:
        raise Http404("Invalid token")


def portal_dashboard(request, token):
    partner = _get_partner_from_token(token)
    tickets = Ticket.objects.filter(client=partner).order_by('-created_at')

    open_tickets = tickets.exclude(status__in=['resolved', 'closed'])
    resolved_tickets = tickets.filter(status__in=['resolved', 'closed'])

    context = {
        'partner': partner,
        'token': token,
        'open_tickets': open_tickets[:20],
        'resolved_tickets': resolved_tickets[:10],
    }
    return render(request, 'helpdesk/portal/dashboard.html', context)


@transaction.atomic
def portal_new_ticket(request, token):
    partner = _get_partner_from_token(token)

    if request.method == 'POST':
        ticket = Ticket(
            company=partner.company,
            client=partner,
            subject=request.POST.get('subject', ''),
            description=request.POST.get('description', ''),
            category=request.POST.get('category', 'other'),
            priority='normal',
            source='portal',
            contact_name=request.POST.get('contact_name', ''),
            contact_email=request.POST.get('contact_email', ''),
        )
        ticket.ticket_number = ticket.generate_ticket_number()
        ticket.set_sla()
        ticket.save()

        if ticket.description:
            msg = TicketMessage.objects.create(
                ticket=ticket,
                sender_name=request.POST.get('contact_name', partner.name),
                body=ticket.description,
                is_from_client=True,
            )
            if request.FILES.get('attachment'):
                msg.attachment = request.FILES['attachment']
                msg.save()

        return redirect('helpdesk_portal_ticket', token=token, pk=ticket.pk)

    context = {'partner': partner, 'token': token}
    return render(request, 'helpdesk/portal/new_ticket.html', context)


def portal_ticket_detail(request, token, pk):
    partner = _get_partner_from_token(token)
    ticket = get_object_or_404(Ticket, pk=pk, client=partner)

    ticket_messages = ticket.messages.filter(is_internal=False).order_by('created_at')

    context = {
        'partner': partner,
        'token': token,
        'ticket': ticket,
        'messages': ticket_messages,
    }
    return render(request, 'helpdesk/portal/ticket_detail.html', context)


@transaction.atomic
def portal_ticket_reply(request, token, pk):
    partner = _get_partner_from_token(token)
    ticket = get_object_or_404(Ticket, pk=pk, client=partner)

    if request.method == 'POST' and ticket.status not in ('closed',):
        body = request.POST.get('body', '').strip()
        if body:
            msg = TicketMessage(
                ticket=ticket,
                sender_name=request.POST.get('sender_name', partner.name),
                body=body,
                is_from_client=True,
            )
            if request.FILES.get('attachment'):
                msg.attachment = request.FILES['attachment']
            msg.save()

            if ticket.status == 'waiting_client':
                ticket.status = 'in_progress'
                ticket.save(update_fields=['status', 'updated_at'])

    return redirect('helpdesk_portal_ticket', token=token, pk=pk)


def portal_ticket_rate(request, token, pk):
    partner = _get_partner_from_token(token)
    ticket = get_object_or_404(Ticket, pk=pk, client=partner)

    if request.method == 'POST' and ticket.status in ('resolved', 'closed'):
        rating = request.POST.get('rating')
        if rating and rating.isdigit() and 1 <= int(rating) <= 5:
            ticket.satisfaction_rating = int(rating)
            ticket.satisfaction_comment = request.POST.get('comment', '')
            ticket.save(update_fields=['satisfaction_rating', 'satisfaction_comment'])

    return redirect('helpdesk_portal_ticket', token=token, pk=pk)
