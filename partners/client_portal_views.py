"""
Unified Client Portal — single URL for tracking, invoices, helpdesk, payments.
Token-based auth (no login required).
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.db.models import Sum, Count, Q
from django.utils import timezone

from partners.models import Partner
from django.db import IntegrityError, DatabaseError


def _get_partner(token):
    return get_object_or_404(Partner, portal_token=token, is_active=True)


# ── Dashboard ──────────────────────────────────────────────────────────────
def client_dashboard(request, token):
    """Unified client dashboard — the 'one URL' for everything."""
    partner = _get_partner(token)
    company = partner.company
    now = timezone.now()

    context = {'partner': partner, 'token': token, 'active_tab': 'dashboard'}

    # 1. Active deliveries & tracking
    try:
        from delivery.models import ConsolidatedDelivery, SmartBox
        deliveries = ConsolidatedDelivery.objects.filter(
            buyer_company__name=partner.name,
            status__in=['collecting', 'consolidating', 'dispatched', 'in_transit']
        ).order_by('-id')[:5]

        active_boxes = []
        for d in deliveries:
            boxes = SmartBox.objects.filter(current_delivery=d)
            for box in boxes:
                active_boxes.append({
                    'box_id': box.box_id,
                    'temp': float(box.last_temp) if box.last_temp else None,
                    'temp_ok': box.is_temp_ok if box.last_temp else None,
                    'target': "{}-{}\u00b0C".format(float(box.target_min_temp), float(box.target_max_temp)),
                    'haccp': box.haccp_status,
                    'updated': box.last_reading_at,
                    'delivery': d.delivery_number,
                })

        context['deliveries'] = deliveries
        context['smart_boxes'] = active_boxes
        context['delivery_count'] = deliveries.count() if hasattr(deliveries, 'count') else len(deliveries)
    except (ValueError, TypeError):
        context['deliveries'] = []
        context['smart_boxes'] = []
        context['delivery_count'] = 0

    # 2. Invoices
    try:
        from invoicing.models import Invoice
        invoices = Invoice.objects.filter(company=company, partner=partner).order_by('-date_issued')

        context['invoices_recent'] = invoices[:5]
        context['invoices_unpaid'] = invoices.filter(
            status__in=['SENT', 'OVERDUE', 'UNPAID']
        ).aggregate(count=Count('id'), total=Sum('total'))
        context['invoices_paid'] = invoices.filter(
            status='PAID'
        ).aggregate(count=Count('id'), total=Sum('total'))
    except DatabaseError:
        context['invoices_recent'] = []
        context['invoices_unpaid'] = {'count': 0, 'total': 0}
        context['invoices_paid'] = {'count': 0, 'total': 0}

    # 3. Helpdesk tickets
    try:
        from helpdesk.models import Ticket
        tickets = Ticket.objects.filter(company=company, client=partner)
        context['tickets_open'] = tickets.filter(
            status__in=['open', 'in_progress', 'waiting_client']
        ).order_by('-created_at')[:5]
        context['tickets_count'] = tickets.filter(
            status__in=['open', 'in_progress', 'waiting_client']
        ).count()
    except DatabaseError:
        context['tickets_open'] = []
        context['tickets_count'] = 0

    # 4. Payments
    try:
        from payments.models import Payment
        payments = Payment.objects.filter(
            company=company,
            customer_name__icontains=partner.name
        ).order_by('-created_at')
        context['payments_recent'] = payments[:5]
        context['payments_pending'] = payments.filter(
            status__in=['pending', 'processing']
        ).aggregate(count=Count('id'), total=Sum('amount'))
    except DatabaseError:
        context['payments_recent'] = []
        context['payments_pending'] = {'count': 0, 'total': 0}

    # 5. Otpremnice
    try:
        from propter.models import Otpremnica
        context['otpremnice'] = Otpremnica.objects.filter(
            company=company,
            recipient_oib=partner.oib
        ).order_by('-issue_date')[:5]
    except DatabaseError:
        context['otpremnice'] = []

    return render(request, 'portal/client_dashboard.html', context)


# ── Deliveries ─────────────────────────────────────────────────────────────
def client_deliveries(request, token):
    """Full delivery list with tracking."""
    partner = _get_partner(token)

    try:
        from delivery.models import ConsolidatedDelivery
        deliveries = ConsolidatedDelivery.objects.filter(
            buyer_company__name=partner.name,
        ).order_by('-id')

        status_filter = request.GET.get('status')
        if status_filter:
            deliveries = deliveries.filter(status=status_filter)
    except DatabaseError:
        deliveries = []

    return render(request, 'portal/client_deliveries.html', {
        'partner': partner, 'token': token, 'deliveries': deliveries,
        'active_tab': 'deliveries',
    })


# ── Single Delivery Tracking ──────────────────────────────────────────────
def client_delivery_track(request, token, delivery_id):
    """Real-time tracking page for a single delivery."""
    partner = _get_partner(token)

    try:
        from delivery.models import ConsolidatedDelivery, SmartBox, SensorReading
        delivery = get_object_or_404(ConsolidatedDelivery, id=delivery_id)

        boxes = SmartBox.objects.filter(current_delivery=delivery)
        readings = []
        for box in boxes:
            recent = SensorReading.objects.filter(smart_box=box).order_by('-timestamp')[:50]
            readings.extend([{
                'box': box.box_id,
                'temp': float(r.temperature),
                'humidity': float(r.humidity) if r.humidity else None,
                'time': r.timestamp.isoformat(),
                'lat': float(r.latitude) if r.latitude else None,
                'lng': float(r.longitude) if r.longitude else None,
            } for r in recent])

        events = []
        if delivery.tracked_item:
            from tracking.models import TrackingEvent
            events = TrackingEvent.objects.filter(
                tracked_item=delivery.tracked_item
            ).order_by('-created_at')
    except (ValueError, TypeError):
        delivery = None
        boxes = []
        readings = []
        events = []

    return render(request, 'portal/client_tracking.html', {
        'partner': partner, 'token': token, 'delivery': delivery,
        'boxes': boxes, 'readings_json': readings, 'events': events,
        'active_tab': 'deliveries',
    })


# ── Invoices ───────────────────────────────────────────────────────────────
def client_invoices(request, token):
    """Full invoice list with filters."""
    partner = _get_partner(token)
    company = partner.company

    try:
        from invoicing.models import Invoice
        invoices = Invoice.objects.filter(
            company=company, partner=partner
        ).order_by('-date_issued')

        status_filter = request.GET.get('status')
        if status_filter:
            invoices = invoices.filter(status=status_filter)
    except DatabaseError:
        invoices = []

    return render(request, 'portal/client_invoices.html', {
        'partner': partner, 'token': token, 'invoices': invoices,
        'filter_status': request.GET.get('status', ''),
        'active_tab': 'invoices',
    })


# ── New Ticket ─────────────────────────────────────────────────────────────
def client_new_ticket(request, token):
    """Create a new support ticket."""
    partner = _get_partner(token)
    company = partner.company

    categories = [
        ('general', 'Opcenito'),
        ('delivery', 'Dostava'),
        ('invoice', 'Faktura'),
        ('quality', 'Kvaliteta'),
        ('technical', 'Tehnicki problem'),
        ('complaint', 'Reklamacija'),
    ]

    if request.method == 'POST':
        from helpdesk.models import Ticket
        subject = request.POST.get('subject', '').strip()
        description = request.POST.get('description', '').strip()
        category = request.POST.get('category', 'general')
        priority = request.POST.get('priority', 'normal')

        if subject and description:
            ticket = Ticket(
                company=company,
                client=partner,
                subject=subject,
                description=description,
                category=category,
                priority=priority,
                status='open',
                source='client_portal',
            )
            ticket.save()
            return redirect('client_portal:dashboard', token=token)

    return render(request, 'portal/client_new_ticket.html', {
        'partner': partner, 'token': token, 'categories': categories,
        'active_tab': 'support',
    })


# ── Ticket Detail ──────────────────────────────────────────────────────────
def client_ticket_detail(request, token, ticket_id):
    """View ticket conversation and add replies."""
    partner = _get_partner(token)

    from helpdesk.models import Ticket, TicketMessage
    ticket = get_object_or_404(Ticket, id=ticket_id, client=partner)

    if request.method == 'POST':
        body = request.POST.get('message', '').strip()
        if body:
            TicketMessage.objects.create(
                ticket=ticket,
                body=body,
                is_from_client=True,
                is_internal=False,
                sender_name=partner.name,
            )
            if ticket.status == 'waiting_client':
                ticket.status = 'in_progress'
                ticket.save(update_fields=['status', 'updated_at'])

    messages_list = TicketMessage.objects.filter(
        ticket=ticket, is_internal=False
    ).order_by('created_at')

    return render(request, 'portal/client_ticket.html', {
        'partner': partner, 'token': token, 'ticket': ticket,
        'messages': messages_list,
        'active_tab': 'support',
    })


# ── Document Upload (Drag & Drop) ─────────────────────────────────
import json

def client_upload(request, token):
    """AJAX: Klijent uploada fakturu (slika/PDF) → draft URA via Gemini OCR."""
    partner = _get_partner(token)
    company = partner.company

    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    file = request.FILES.get('file')
    if not file:
        return JsonResponse({'error': 'Nema datoteke'}, status=400)

    # Validate file type
    allowed = ('.pdf', '.jpg', '.jpeg', '.png', '.webp')
    ext = '.' + file.name.rsplit('.', 1)[-1].lower() if '.' in file.name else ''
    if ext not in allowed:
        return JsonResponse({'error': f'Nepodržan format. Dozvoljeno: {", ".join(allowed)}'}, status=400)

    # Max 10MB
    if file.size > 10 * 1024 * 1024:
        return JsonResponse({'error': 'Datoteka prevelika (max 10 MB)'}, status=400)

    # Save to ArhivaEntry
    try:
        from documents.models import ArhivaEntry
        entry = ArhivaEntry.objects.create(
            company=company,
            title=f'Upload: {file.name}',
            category='URA',
            source='client_portal',
            notes=f'Uploadao klijent {partner.name} via portal',
        )
        # Save file
        from django.core.files.storage import default_storage
        path = f'portal_uploads/{company.id}/{timezone.now():%Y/%m}/{file.name}'
        saved_path = default_storage.save(path, file)
        entry.notes += f'\nFile: {saved_path}'
        entry.save(update_fields=['notes'])

    except (IntegrityError, DatabaseError) as e:
        return JsonResponse({'ok': True, 'status': 'saved', 'message': f'Dokument spremljen (OCR nedostupan: {e})'})

    # Try OCR via smart_import if available
    ocr_result = None
    try:
        from smart_import.services import extract_invoice_data
        ocr_result = extract_invoice_data(saved_path)
    except ImportError:
        pass

    return JsonResponse({
        'ok': True,
        'status': 'uploaded',
        'file_name': file.name,
        'entry_id': entry.id if entry else None,
        'ocr': ocr_result,
        'message': f'Dokument "{file.name}" spremljen. ' + (
            'OCR obrada pokrenuta.' if ocr_result else 'Računovođa će ga obraditi.'
        ),
    })


# ── eRačun Timeline ───────────────────────────────────────────────
def client_eracun_timeline(request, token):
    """AJAX: dohvati eRačun status timeline za partnera."""
    partner = _get_partner(token)
    company = partner.company

    try:
        from eracun.models import ERacun
        eracuni = ERacun.objects.filter(
            company=company,
            recipient_oib=partner.oib,
        ).order_by('-created_at')[:20]

        data = []
        for er in eracuni:
            steps = [
                {'key': 'draft', 'label': 'Kreiran', 'done': True, 'date': er.created_at.isoformat()},
                {'key': 'valid', 'label': 'Validiran', 'done': er.status not in ('draft', 'validating', 'invalid'), 'date': ''},
                {'key': 'signed', 'label': 'Potpisan', 'done': er.status not in ('draft', 'validating', 'valid', 'invalid', 'signing'), 'date': ''},
                {'key': 'sent', 'label': 'Poslan', 'done': er.sent_at is not None, 'date': er.sent_at.isoformat() if er.sent_at else ''},
                {'key': 'accepted', 'label': 'Zaprimljen', 'done': er.status == 'accepted', 'date': er.accepted_at.isoformat() if er.accepted_at else ''},
            ]
            # Mark current step
            current = er.status
            if current == 'error':
                for s in steps:
                    if not s['done']:
                        s['error'] = True
                        s['label'] += f' (Greška)'
                        break

            data.append({
                'id': str(er.id),
                'number': er.invoice_number,
                'date': er.issue_date.isoformat(),
                'total': str(er.total),
                'currency': er.currency,
                'status': er.status,
                'status_display': er.get_status_display(),
                'zki': er.zki or '',
                'jir': er.jir or '',
                'steps': steps,
            })

        return JsonResponse({'ok': True, 'eracuni': data})
    except DatabaseError as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)
