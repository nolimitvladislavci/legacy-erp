import json
import logging
from datetime import date, timedelta
from decimal import Decimal
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.translation import gettext as _
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q, Sum, Count
from core.company_utils import get_user_company
from .models import Property, Booking, HousekeepingLog
from django.core.exceptions import ObjectDoesNotExist

logger = logging.getLogger(__name__)


@login_required
def dashboard(request):
    """Robot Hotel dashboard - overview."""
    company = get_user_company(request)
    if not company:
        return redirect('/')

    properties = Property.objects.filter(company=company, is_active=True)
    today = timezone.now().date()

    # Stats
    total_rooms = properties.count()
    occupied = properties.filter(status='occupied').count()
    available = properties.filter(status='available').count()
    cleaning = properties.filter(status='cleaning').count()

    # Today's arrivals and departures
    arrivals = Booking.objects.filter(
        company=company, check_in=today, status__in=('confirmed', 'pending')
    ).select_related('rental_property')
    departures = Booking.objects.filter(
        company=company, check_out=today, status='checked_in'
    ).select_related('rental_property')

    # Active stays
    active_stays = Booking.objects.filter(
        company=company, status='checked_in'
    ).select_related('rental_property').order_by('check_out')

    # Revenue this month
    first_of_month = today.replace(day=1)
    month_revenue = Booking.objects.filter(
        company=company, status__in=('checked_in', 'checked_out'),
        check_in__gte=first_of_month
    ).aggregate(total=Sum('total_price'))['total'] or 0

    # Upcoming bookings
    upcoming = Booking.objects.filter(
        company=company, check_in__gt=today,
        status__in=('pending', 'confirmed')
    ).select_related('rental_property').order_by('check_in')[:10]

    return render(request, 'rental/dashboard.html', {
        'properties': properties,
        'total_rooms': total_rooms,
        'occupied': occupied,
        'available': available,
        'cleaning': cleaning,
        'arrivals': arrivals,
        'departures': departures,
        'active_stays': active_stays,
        'month_revenue': month_revenue,
        'upcoming': upcoming,
        'today': today,
    })


@login_required
def property_list(request):
    """List all properties."""
    company = get_user_company(request)
    if not company:
        return redirect('/')
    properties = Property.objects.filter(company=company).order_by('floor', 'name')
    return render(request, 'rental/property_list.html', {'properties': properties})


@login_required
def property_form(request, pk=None):
    """Create/edit property."""
    company = get_user_company(request)
    if not company:
        return redirect('/')

    prop = get_object_or_404(Property, pk=pk, company=company) if pk else None

    if request.method == 'POST':
        if not prop:
            prop = Property(company=company)
        prop.name = request.POST.get('name', '').strip()
        prop.type = request.POST.get('type', 'room')
        prop.floor = request.POST.get('floor', '').strip()
        prop.description = request.POST.get('description', '').strip()
        prop.capacity = int(request.POST.get('capacity', 2))
        prop.beds = request.POST.get('beds', '').strip()
        prop.price_per_night = Decimal(request.POST.get('price_per_night', '0'))
        prop.price_weekend = Decimal(request.POST.get('price_weekend', '0')) or None
        prop.price_monthly = Decimal(request.POST.get('price_monthly', '0')) or None
        prop.tourist_tax = Decimal(request.POST.get('tourist_tax', '1'))
        prop.cleaning_fee = Decimal(request.POST.get('cleaning_fee', '0'))
        prop.min_nights = int(request.POST.get('min_nights', 1))
        prop.smart_lock_id = request.POST.get('smart_lock_id', '').strip()
        prop.smart_lock_type = request.POST.get('smart_lock_type', '').strip()
        prop.wifi_name = request.POST.get('wifi_name', '').strip()
        prop.wifi_password = request.POST.get('wifi_password', '').strip()
        prop.location = request.POST.get('location', '').strip()
        prop.save()
        messages.success(request, f'Nekretnina {prop.name} spremljena.')
        return redirect('rental:dashboard')

    return render(request, 'rental/property_form.html', {'prop': prop})


@login_required
def booking_list(request):
    """List all bookings."""
    company = get_user_company(request)
    if not company:
        return redirect('/')
    bookings = Booking.objects.filter(company=company).select_related('rental_property').order_by('-check_in')[:100]
    return render(request, 'rental/booking_list.html', {'bookings': bookings})


@login_required
def booking_form(request, pk=None):
    """Create/edit booking."""
    company = get_user_company(request)
    if not company:
        return redirect('/')

    booking = get_object_or_404(Booking, pk=pk, company=company) if pk else None
    properties = Property.objects.filter(company=company, is_active=True)

    if request.method == 'POST':
        if not booking:
            booking = Booking(company=company)
        booking.rental_property_id = int(request.POST.get('rental_property_id'))
        booking.guest_name = request.POST.get('guest_name', '').strip()
        booking.guest_email = request.POST.get('guest_email', '').strip()
        booking.guest_phone = request.POST.get('guest_phone', '').strip()
        booking.guest_country = request.POST.get('guest_country', '').strip().upper()
        booking.guest_count = int(request.POST.get('guest_count', 1))
        booking.check_in = request.POST.get('check_in')
        booking.check_out = request.POST.get('check_out')
        booking.price_per_night = Decimal(request.POST.get('price_per_night') or str(booking.rental_property.price_per_night))
        booking.source = request.POST.get('source', 'direct')
        booking.notes = request.POST.get('notes', '').strip()
        booking.calculate_price()
        booking.save()
        messages.success(request, f'Rezervacija {booking.booking_number} spremljena.')
        return redirect('rental:dashboard')

    return render(request, 'rental/booking_form.html', {
        'booking': booking,
        'properties': properties,
    })


@login_required
def check_in(request, pk):
    """Check in a guest."""
    company = get_user_company(request)
    booking = get_object_or_404(Booking, pk=pk, company=company)

    if request.method == 'POST':
        booking.status = 'checked_in'
        booking.actual_check_in = timezone.now()
        booking.access_valid_from = timezone.now()
        booking.access_valid_until = timezone.make_aware(
            timezone.datetime.combine(booking.check_out, timezone.datetime.min.time().replace(hour=12))
        )
        booking.save()

        # Update property status
        booking.rental_property.status = 'occupied'
        booking.rental_property.save(update_fields=['status'])

        messages.success(request, f'{booking.guest_name} prijavljen u {booking.rental_property.name}')
        return redirect('rental:dashboard')

    return render(request, 'rental/check_in.html', {'booking': booking})


@login_required
def check_out(request, pk):
    """Check out a guest."""
    company = get_user_company(request)
    booking = get_object_or_404(Booking, pk=pk, company=company)

    if request.method == 'POST':
        booking.status = 'checked_out'
        booking.actual_check_out = timezone.now()
        booking.save()

        # Property goes to cleaning
        booking.rental_property.status = 'cleaning'
        booking.rental_property.save(update_fields=['status'])

        # Create housekeeping task
        HousekeepingLog.objects.create(
            rental_property=booking.rental_property,
            booking=booking,
            status='pending',
        )

        # Trigger payment if not paid
        if not booking.is_paid and booking.guest_email:
            try:
                from payments.services import create_payment
                base_url = request.build_absolute_uri('/').rstrip('/')
                payment = create_payment(
                    company=company,
                    source='rental',
                    source_id=str(booking.pk),
                    amount=booking.total_price,
                    method='stripe',
                    customer_email=booking.guest_email,
                    customer_name=booking.guest_name,
                    description=f'Boravak {booking.booking_number} - {booking.rental_property.name}',
                    success_url=base_url + '/rental/',
                    cancel_url=base_url + '/rental/',
                )
                booking.payment_id = payment.id
                booking.save(update_fields=['payment_id'])
            except Exception as e:
                logger.warning("Auto-payment on checkout failed: %s", e)

        messages.success(request, f'{booking.guest_name} odjavljen iz {booking.rental_property.name}')
        return redirect('rental:dashboard')

    return render(request, 'rental/check_out.html', {'booking': booking})


def guest_self_checkin(request, access_qr):
    """Guest self check-in page - no login required. Robot Hotel!"""
    booking = get_object_or_404(Booking, access_qr=access_qr)

    if request.method == 'POST':
        # Guest submits their ID info
        booking.guest_id_number = request.POST.get('id_number', '').strip()
        booking.guest_country = request.POST.get('country', '').strip().upper()
        guest_count = request.POST.get('guest_count')
        if guest_count:
            booking.guest_count = int(guest_count)
        booking.status = 'checked_in'
        booking.actual_check_in = timezone.now()
        booking.access_valid_from = timezone.now()
        booking.access_valid_until = timezone.make_aware(
            timezone.datetime.combine(booking.check_out, timezone.datetime.min.time().replace(hour=12))
        )
        booking.calculate_price()
        booking.save()

        booking.rental_property.status = 'occupied'
        booking.rental_property.save(update_fields=['status'])

        return render(request, 'rental/guest_welcome.html', {'booking': booking})

    return render(request, 'rental/guest_checkin.html', {'booking': booking})


def guest_access(request, access_qr):
    """Guest access page - shows door code, WiFi, house rules."""
    booking = get_object_or_404(Booking, access_qr=access_qr)

    # Check if access is still valid
    now = timezone.now()
    access_valid = (
        booking.status == 'checked_in' and
        (not booking.access_valid_until or now <= booking.access_valid_until)
    )

    return render(request, 'rental/guest_access.html', {
        'booking': booking,
        'access_valid': access_valid,
    })


def guest_pay(request, access_qr):
    """Guest payment page."""
    booking = get_object_or_404(Booking, access_qr=access_qr)

    if request.method == 'POST':
        method = request.POST.get('method', 'stripe')
        try:
            from payments.services import create_payment
            base_url = request.build_absolute_uri('/').rstrip('/')
            payment = create_payment(
                company=booking.company,
                source='rental',
                source_id=str(booking.pk),
                amount=booking.total_price,
                method=method,
                customer_email=booking.guest_email,
                customer_name=booking.guest_name,
                description=f'Stay {booking.booking_number} - {booking.rental_property.name}',
                success_url=base_url + f'/rental/guest/{access_qr}/access/',
                cancel_url=base_url + f'/rental/guest/{access_qr}/pay/',
            )
            booking.payment_id = payment.id
            booking.save(update_fields=['payment_id'])
            if payment.external_url:
                return redirect(payment.external_url)
        except Exception as e:
            logger.error("Guest payment failed: %s", e)
            messages.error(request, _('Placanje nije uspjelo. Pokusajte ponovo.'))

    return render(request, 'rental/guest_pay.html', {'booking': booking})


@login_required
def housekeeping(request):
    """Housekeeping overview."""
    company = get_user_company(request)
    if not company:
        return redirect('/')
    logs = HousekeepingLog.objects.filter(
        rental_property__company=company
    ).select_related('rental_property', 'assigned_to').order_by('status', '-created_at')[:50]

    if request.method == 'POST':
        log_id = request.POST.get('log_id')
        new_status = request.POST.get('status')
        if log_id and new_status:
            log = get_object_or_404(HousekeepingLog, pk=log_id, rental_property__company=company)
            log.status = new_status
            if new_status == 'in_progress':
                log.started_at = timezone.now()
                log.assigned_to = request.user
            elif new_status == 'done':
                log.completed_at = timezone.now()
                # Mark property available
                log.property.status = 'available'
                log.property.save(update_fields=['status'])
            log.save()
            return redirect('rental:housekeeping')

    return render(request, 'rental/housekeeping.html', {'logs': logs})


@login_required
def calendar_view(request):
    """Visual calendar of bookings."""
    company = get_user_company(request)
    if not company:
        return redirect('/')

    today = date.today()
    start = today - timedelta(days=today.weekday())  # Monday
    end = start + timedelta(days=27)  # 4 weeks

    properties = Property.objects.filter(company=company, is_active=True).order_by('floor', 'name')
    bookings = Booking.objects.filter(
        company=company,
        check_out__gte=start,
        check_in__lte=end,
        status__in=('confirmed', 'checked_in', 'pending'),
    ).select_related('rental_property')

    # Build date range
    dates = [start + timedelta(days=i) for i in range(28)]

    # Build availability map
    calendar_data = []
    for prop in properties:
        row = {'property': prop, 'days': []}
        prop_bookings = [b for b in bookings if b.rental_property_id == prop.pk]
        for d in dates:
            booked = None
            for b in prop_bookings:
                if b.check_in <= d < b.check_out:
                    booked = b
                    break
            row['days'].append({'date': d, 'booking': booked})
        calendar_data.append(row)

    return render(request, 'rental/calendar.html', {
        'calendar_data': calendar_data,
        'dates': dates,
        'today': today,
    })


# ═══════════════════════════════════════════════════════════════
#  F3: Check-in Flow + OCR + eVisitor + Accountant Dashboard
# ═══════════════════════════════════════════════════════════════

@login_required
def checkin_flow(request, pk):
    """Check-in forma za iznajmljivača — lista gostiju + OCR + eVisitor."""
    company = get_user_company(request)
    booking = get_object_or_404(Booking, pk=pk, rental_property__company=company)
    guests = booking.guests.all()

    if request.method == 'POST':
        # Ručni unos gosta
        from rental.models import Guest
        guest = Guest.objects.create(
            booking=booking,
            first_name=request.POST.get('first_name', ''),
            last_name=request.POST.get('last_name', ''),
            nationality=request.POST.get('nationality', 'HRV'),
            document_type=request.POST.get('document_type', 'id_card'),
            document_number=request.POST.get('document_number', ''),
            sex=request.POST.get('sex', ''),
            is_primary=not guests.exists(),
            consent_given='consent' in request.POST,
            consent_given_at=timezone.now() if 'consent' in request.POST else None,
        )
        # Date of birth
        dob = request.POST.get('date_of_birth', '')
        if dob:
            from datetime import date
            try:
                guest.date_of_birth = date.fromisoformat(dob)
                guest.save()
            except (ValueError, TypeError):
                pass

        from django.contrib import messages
        messages.success(request, f'Gost {guest.full_name} dodan.')
        return redirect('rental:checkin_flow', pk=pk)

    # Izračun
    nights = (booking.check_out - booking.check_in).days or 1
    from rental.tourist_tax import calculate_booking_tourist_tax
    tax = calculate_booking_tourist_tax(booking)
    total = booking.price_per_night * nights + tax + (booking.rental_property.cleaning_fee or 0)

    return render(request, 'rental/checkin_flow.html', {
        'booking': booking,
        'guests': guests,
        'nights': nights,
        'tourist_tax': tax,
        'total': total,
    })


@login_required
def guest_ocr_upload(request, pk):
    """AJAX: prima sliku dokumenta, pokreće OCR, vraća JSON."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    company = get_user_company(request)
    booking = get_object_or_404(Booking, pk=pk, rental_property__company=company)

    image = request.FILES.get('image')
    if not image:
        return JsonResponse({'error': 'No image'}, status=400)

    # Kreiraj Guest + GuestDocument
    from rental.models import Guest, GuestDocument
    guest = Guest.objects.create(
        booking=booking,
        first_name='',
        last_name='',
        is_primary=not booking.guests.exists(),
        consent_given=True,
        consent_given_at=timezone.now(),
    )

    doc = GuestDocument.objects.create(
        guest=guest,
        image=image,
    )

    # GDPR: postavi brisanje 24h nakon check-outa
    if booking.check_out:
        from datetime import timedelta, datetime
        checkout_dt = datetime.combine(booking.check_out, datetime.min.time())
        from django.utils.timezone import make_aware
        doc.delete_after = make_aware(checkout_dt) + timedelta(hours=24)
        doc.save()

    # OCR
    try:
        from rental.ocr import apply_ocr_to_guest
        result = apply_ocr_to_guest(doc.pk)
        guest.refresh_from_db()

        return JsonResponse({
            'ok': True,
            'guest_id': guest.pk,
            'data': {
                'first_name': guest.first_name,
                'last_name': guest.last_name,
                'date_of_birth': str(guest.date_of_birth) if guest.date_of_birth else '',
                'nationality': guest.nationality,
                'document_type': guest.document_type,
                'document_number': guest.document_number,
                'sex': guest.sex,
            },
            'confidence': result.get('confidence', 0),
        })
    except Exception as e:
        return JsonResponse({
            'ok': False,
            'guest_id': guest.pk,
            'error': str(e),
            'confidence': 0,
        })


@login_required
def evisitor_xml_download(request, pk):
    """Download eVisitor XML za booking."""
    company = get_user_company(request)
    booking = get_object_or_404(Booking, pk=pk, rental_property__company=company)

    from rental.evisitor import build_evisitor_xml
    xml = build_evisitor_xml(booking)

    response = HttpResponse(xml, content_type='application/xml')
    response['Content-Disposition'] = (
        f'attachment; filename="eVisitor_{booking.booking_number}.xml"'
    )
    return response


@login_required
def rental_invoice_pdf(request, pk):
    """Generiraj/preuzmi račun za booking."""
    company = get_user_company(request)
    booking = get_object_or_404(Booking, pk=pk, rental_property__company=company)

    # Kreiraj invoice ako ne postoji
    from rental.models import RentalInvoice
    try:
        ri = booking.rental_invoice
    except RentalInvoice.DoesNotExist:
        from rental.invoice_service import create_rental_invoice
        ri = create_rental_invoice(booking)

    if ri.invoice:
        # Redirect na invoicing PDF
        return redirect('invoicing:invoice_pdf', pk=ri.invoice.pk)

    return JsonResponse({'error': 'Račun nije generiran.'}, status=400)


@login_required
def rental_accountant_dashboard(request):
    """Marija vidi sve klijente iznajmljivače."""
    from rental.models import Property
    from rental.ai_assistant import check_annual_limit_warning
    from companies.models import Company

    # Sve firme koje imaju rental objekte
    company_ids = Property.objects.filter(
        is_active=True,
    ).values_list('company_id', flat=True).distinct()

    clients = []
    for cid in company_ids:
        try:
            company = Company.objects.get(pk=cid)
            props = Property.objects.filter(company=company, is_active=True)
            limit = check_annual_limit_warning(company)

            clients.append({
                'company': company,
                'property_count': props.count(),
                'total_beds': sum(p.capacity or 0 for p in props),
                'ytd': limit['ytd'],
                'percent': limit['percent'],
                'remaining': limit['remaining'],
                'warning_level': limit.get('warning_level'),
                'message': limit.get('message'),
            })
        except ObjectDoesNotExist:
            pass

    # Sortiraj po % praga (najhitniji gore)
    clients.sort(key=lambda x: x['percent'], reverse=True)

    return render(request, 'rental/accountant_dashboard.html', {
        'clients': clients,
    })


# ═══════════════════════════════════════════════════════════════
#  QuickAction API endpoints (POS → Rental bridge)
# ═══════════════════════════════════════════════════════════════

@login_required
def api_today_arrivals(request):
    """API za POS QuickAction — današnji dolasci."""
    company = get_user_company(request)
    today = timezone.now().date()

    bookings = Booking.objects.filter(
        rental_property__company=company,
        check_in=today,
        status__in=['confirmed', 'pending'],
    ).select_related('rental_property')

    data = [{
        'id': b.pk,
        'guest_name': b.guest_name,
        'property_name': b.rental_property.name,
        'nights': (b.check_out - b.check_in).days,
        'total_price': float(b.total_price),
        'guests_count': b.guests.count() if hasattr(b, 'guests') else b.guest_count,
        'check_in': b.check_in.strftime('%H:%M') if hasattr(b.check_in, 'strftime') and hasattr(b.check_in, 'hour') else str(b.check_in),
    } for b in bookings]

    return JsonResponse({'bookings': data})


@login_required
def api_today_departures(request):
    """API za POS QuickAction — današnji odlasci."""
    company = get_user_company(request)
    today = timezone.now().date()

    bookings = Booking.objects.filter(
        rental_property__company=company,
        check_out=today,
        status='checked_in',
    ).select_related('rental_property')

    data = [{
        'id': b.pk,
        'guest_name': b.guest_name,
        'property_name': b.rental_property.name,
        'is_paid': b.is_paid,
    } for b in bookings]

    return JsonResponse({'bookings': data})


@login_required
def api_evisitor_pending(request):
    """API za POS QuickAction — bookings bez eVisitor prijave."""
    company = get_user_company(request)

    bookings = Booking.objects.filter(
        rental_property__company=company,
        status='checked_in',
    ).select_related('rental_property')

    pending = []
    for b in bookings:
        unsynced = b.guests.filter(evisitor_synced=False).count() if hasattr(b, 'guests') else 0
        if unsynced > 0 or not hasattr(b, 'guests') or not b.guests.exists():
            hours = 0
            if b.actual_check_in:
                hours = int((timezone.now() - b.actual_check_in).total_seconds() / 3600)
            pending.append({
                'id': b.pk,
                'guest_name': b.guest_name,
                'property_name': b.rental_property.name,
                'check_in': b.check_in.strftime('%d.%m.') if b.check_in else '',
                'hours_pending': hours,
                'unsynced_guests': unsynced,
            })

    return JsonResponse({'bookings': pending})


@login_required
def api_active_bookings(request):
    """API za POS QuickAction — aktivni bookings za OCR."""
    company = get_user_company(request)

    bookings = Booking.objects.filter(
        rental_property__company=company,
        status__in=['confirmed', 'checked_in'],
    ).select_related('rental_property').order_by('-check_in')[:20]

    data = [{
        'id': b.pk,
        'guest_name': b.guest_name,
        'property_name': b.rental_property.name,
        'check_in': b.check_in.strftime('%d.%m.') if b.check_in else '',
    } for b in bookings]

    return JsonResponse({'bookings': data})


# ═══════════════════════════════════════════════════════════════
#  TZ-2 Obrazac — PDF generacija i pregled
# ═══════════════════════════════════════════════════════════════

@login_required
def tz2_preview(request, year=None):
    """Pregled TZ-2 podataka prije generiranja PDF-a."""
    company = get_user_company(request)
    if year is None:
        year = timezone.now().year

    try:
        from rental.tz2_service import generate_tz2_data
        data = generate_tz2_data(company, year)
        return render(request, 'rental/tz2_preview.html', data)
    except ValueError as e:
        from django.contrib import messages
        messages.error(request, str(e))
        return redirect('rental:dashboard')


@login_required
def tz2_download(request, year=None):
    """Download TZ-2 PDF."""
    company = get_user_company(request)
    if year is None:
        year = timezone.now().year

    try:
        from rental.tz2_service import generate_tz2_pdf
        pdf = generate_tz2_pdf(company, year)

        response = HttpResponse(pdf, content_type='application/pdf')
        filename = f'TZ-2_{company.oib}_{year}.pdf'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except (ValueError, RuntimeError) as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
def tz2_accountant_download(request, company_id, year):
    """Marija downloadira TZ-2 za klijenta."""
    from companies.models import Company
    company = get_object_or_404(Company, pk=company_id)

    try:
        from rental.tz2_service import generate_tz2_pdf
        pdf = generate_tz2_pdf(company, year)

        response = HttpResponse(pdf, content_type='application/pdf')
        filename = f'TZ-2_{company.oib}_{year}.pdf'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except (ValueError, RuntimeError) as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
def tz2_xml_download(request, year=None):
    """Download TZ-2 XML za ePorezna upload."""
    company = get_user_company(request)
    if year is None:
        year = timezone.now().year

    try:
        from rental.tz2_service import generate_tz2_xml
        xml = generate_tz2_xml(company, year)

        response = HttpResponse(xml, content_type='application/xml')
        filename = f'TZ-2_{company.oib}_{year}.xml'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except (ValueError, RuntimeError) as e:
        return JsonResponse({'error': str(e)}, status=400)


# ═══════════════════════════════════════════════════════════════
#  PO-SD Obrazac — paušalni porez iznajmljivača
# ═══════════════════════════════════════════════════════════════

@login_required
def posd_preview(request, year=None):
    """Pregled PO-SD podataka."""
    company = get_user_company(request)
    if year is None:
        year = timezone.now().year

    try:
        from rental.posd_service import generate_posd_data
        data = generate_posd_data(company, year)
        return render(request, 'rental/posd_preview.html', data)
    except ValueError as e:
        from django.contrib import messages
        messages.error(request, str(e))
        return redirect('rental:dashboard')


@login_required
def posd_pdf(request, year=None):
    """Download PO-SD PDF."""
    company = get_user_company(request)
    if year is None:
        year = timezone.now().year
    try:
        from rental.posd_service import generate_posd_pdf
        pdf = generate_posd_pdf(company, year)
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="PO-SD_{company.oib}_{year}.pdf"'
        return response
    except (ValueError, RuntimeError) as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
def posd_xml(request, year=None):
    """Download PO-SD XML za ePorezna."""
    company = get_user_company(request)
    if year is None:
        year = timezone.now().year
    try:
        from rental.posd_service import generate_posd_xml
        xml = generate_posd_xml(company, year)
        response = HttpResponse(xml, content_type='application/xml')
        response['Content-Disposition'] = f'attachment; filename="PO-SD_{company.oib}_{year}.xml"'
        return response
    except (ValueError, RuntimeError) as e:
        return JsonResponse({'error': str(e)}, status=400)
