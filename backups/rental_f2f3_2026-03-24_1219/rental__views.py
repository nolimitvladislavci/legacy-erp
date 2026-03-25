import json
import logging
from datetime import date, timedelta
from decimal import Decimal
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q, Sum, Count
from core.company_utils import get_user_company
from .models import Property, Booking, HousekeepingLog

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
        booking.price_per_night = Decimal(request.POST.get('price_per_night') or str(booking.property.price_per_night))
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
        booking.property.status = 'occupied'
        booking.property.save(update_fields=['status'])

        messages.success(request, f'{booking.guest_name} prijavljen u {booking.property.name}')
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
        booking.property.status = 'cleaning'
        booking.property.save(update_fields=['status'])

        # Create housekeeping task
        HousekeepingLog.objects.create(
            property=booking.property,
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
                    description=f'Boravak {booking.booking_number} - {booking.property.name}',
                    success_url=base_url + '/rental/',
                    cancel_url=base_url + '/rental/',
                )
                booking.payment_id = payment.id
                booking.save(update_fields=['payment_id'])
            except Exception as e:
                logger.warning("Auto-payment on checkout failed: %s", e)

        messages.success(request, f'{booking.guest_name} odjavljen iz {booking.property.name}')
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

        booking.property.status = 'occupied'
        booking.property.save(update_fields=['status'])

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
                description=f'Stay {booking.booking_number} - {booking.property.name}',
                success_url=base_url + f'/rental/guest/{access_qr}/access/',
                cancel_url=base_url + f'/rental/guest/{access_qr}/pay/',
            )
            booking.payment_id = payment.id
            booking.save(update_fields=['payment_id'])
            if payment.external_url:
                return redirect(payment.external_url)
        except Exception as e:
            logger.error("Guest payment failed: %s", e)
            messages.error(request, 'Placanje nije uspjelo. Pokusajte ponovo.')

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
