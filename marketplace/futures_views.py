"""marketplace/futures_views.py — Futures listing and reservation views."""
from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.utils.translation import gettext as _
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from core.company_utils import get_user_company
from .discounts import get_discount_for_item
from .models import FuturesListing, FuturesReservation, FuturesDeliverySlot


@login_required
def futures_catalog(request):
    """Browse available futures listings."""
    today = timezone.now().date()
    qs = FuturesListing.objects.filter(
        status='open',
        booking_deadline__gte=today,
    ).select_related('seller_company', 'category')

    q = request.GET.get('q', '')
    if q:
        qs = qs.filter(name__icontains=q)

    cat = request.GET.get('category', '')
    if cat:
        qs = qs.filter(category__slug=cat)

    return render(request, 'marketplace/futures_catalog.html', {
        'listings': qs,
        'q': q,
        'today': today,
    })


@login_required
def futures_detail(request, pk):
    """Detail view for a futures listing."""
    listing = get_object_or_404(FuturesListing, pk=pk)
    company = get_user_company(request)
    my_reservation = None
    if company:
        my_reservation = FuturesReservation.objects.filter(
            listing=listing, buyer_company=company
        ).first()

    # Check if buyer has partner discount with this seller
    discount_info = None
    if company and listing.product:
        discount_info = get_discount_for_item(listing.product, company)

    return render(request, 'marketplace/futures_detail.html', {
        'listing': listing,
        'my_reservation': my_reservation,
        'discount_info': discount_info,
        'reservations': listing.reservations.select_related('buyer_company').order_by('-created_at')[:10],
    })


@login_required
def futures_reserve(request, pk):
    """Reserve quantity from a futures listing."""
    listing = get_object_or_404(FuturesListing, pk=pk)
    company = get_user_company(request)

    if not company:
        messages.error(request, _('Nemate aktivnu firmu.'))
        return redirect('marketplace:futures_detail', pk=pk)

    if not listing.is_bookable:
        messages.error(request, _('Ova ponuda vise nije dostupna za rezervaciju.'))
        return redirect('marketplace:futures_detail', pk=pk)

    if request.method == 'POST':
        qty = Decimal(request.POST.get('quantity', '0'))

        if qty < listing.min_order_qty:
            messages.error(request, f'Minimalna narudzba je {listing.min_order_qty} {listing.unit}.')
            return redirect('marketplace:futures_detail', pk=pk)

        if qty > listing.available_qty:
            messages.error(request, f'Dostupno samo {listing.available_qty} {listing.unit}.')
            return redirect('marketplace:futures_detail', pk=pk)

        # Check for existing reservation
        existing = FuturesReservation.objects.filter(listing=listing, buyer_company=company).first()
        if existing:
            messages.warning(request, _('Vec imate rezervaciju za ovu ponudu.'))
            return redirect('marketplace:futures_detail', pk=pk)

        # Calculate discount (partner tier applies to futures too)
        discount_pct = Decimal('0')
        if listing.product:
            disc = get_discount_for_item(listing.product, company, qty)
            discount_pct = disc['total_percent']

        # Early-bird bonus: +3% if booking > 30 days before availability
        today = timezone.now().date()
        days_ahead = (listing.available_from - today).days
        if days_ahead > 30:
            discount_pct = min(discount_pct + Decimal('3'), Decimal('50'))

        reservation = FuturesReservation.objects.create(
            listing=listing,
            buyer_company=company,
            buyer_user=request.user,
            quantity=qty,
            unit_price=listing.unit_price,
            delivery_preference=request.POST.get('delivery_preference', 'delivery'),
            delivery_address=request.POST.get('delivery_address', company.address or ''),
            delivery_notes=request.POST.get('delivery_notes', ''),
            recurring_weekly=bool(request.POST.get('recurring_weekly')),
            discount_percent=discount_pct,
            notes=request.POST.get('notes', ''),
        )

        # Update listing reserved qty
        listing.reserved_qty += qty
        if listing.reserved_qty >= listing.total_capacity:
            listing.status = 'fully_booked'
        listing.save(update_fields=['reserved_qty', 'status'])

        # Create weekly delivery slots if recurring
        if reservation.recurring_weekly:
            _create_weekly_slots(reservation)

        pct_display = f' (-{discount_pct}% rabat!)' if discount_pct > 0 else ''
        messages.success(
            request,
            f'Rezervacija uspjesna! {qty} {listing.unit} {listing.name}'
            f' — avans: {reservation.deposit_amount} EUR{pct_display}'
        )
        return redirect('marketplace:futures_my')

    return redirect('marketplace:futures_detail', pk=pk)


def _create_weekly_slots(reservation):
    """Split reservation into weekly delivery slots."""
    listing = reservation.listing
    weeks = max(1, (listing.available_until - listing.available_from).days // 7)
    weekly_qty = (reservation.quantity / Decimal(str(weeks))).quantize(Decimal('0.01'))
    remainder = reservation.quantity - (weekly_qty * weeks)

    current_date = listing.available_from
    for i in range(weeks):
        qty = weekly_qty + (remainder if i == weeks - 1 else Decimal('0'))
        FuturesDeliverySlot.objects.create(
            reservation=reservation,
            scheduled_date=current_date,
            quantity=qty,
        )
        current_date += timedelta(days=7)


@login_required
def futures_my(request):
    """My futures reservations."""
    company = get_user_company(request)
    if not company:
        return redirect('/')

    reservations = FuturesReservation.objects.filter(
        buyer_company=company
    ).select_related('listing__seller_company').order_by('-created_at')

    # Also show my listings (if I'm a seller)
    my_listings = FuturesListing.objects.filter(seller_company=company).order_by('-created_at')

    return render(request, 'marketplace/futures_my.html', {
        'reservations': reservations,
        'my_listings': my_listings,
    })


@login_required
def futures_create(request):
    """Create a new futures listing (seller view)."""
    company = get_user_company(request)
    if not company:
        messages.error(request, _('Nemate aktivnu firmu.'))
        return redirect('/')

    if request.method == 'POST':
        from .models import MarketplaceCategory
        listing = FuturesListing.objects.create(
            seller_company=company,
            name=request.POST.get('name', ''),
            description=request.POST.get('description', ''),
            unit=request.POST.get('unit', 'kg'),
            unit_price=Decimal(request.POST.get('unit_price', '0')),
            total_capacity=Decimal(request.POST.get('total_capacity', '0')),
            min_order_qty=Decimal(request.POST.get('min_order_qty', '1')),
            available_from=request.POST.get('available_from'),
            available_until=request.POST.get('available_until'),
            booking_deadline=request.POST.get('booking_deadline'),
            deposit_percent=Decimal(request.POST.get('deposit_percent', '20')),
            origin_region=request.POST.get('origin_region', ''),
            is_organic=bool(request.POST.get('is_organic')),
            requires_cold_chain=bool(request.POST.get('requires_cold_chain')),
            status='open',
        )
        cat_id = request.POST.get('category')
        if cat_id:
            listing.category_id = cat_id
            listing.save(update_fields=['category'])

        messages.success(request, f'Futures ponuda "{listing.name}" kreirana!')
        return redirect('marketplace:futures_my')

    from .models import MarketplaceCategory
    categories = MarketplaceCategory.objects.filter(is_active=True)
    return render(request, 'marketplace/futures_form.html', {
        'categories': categories,
    })


@login_required
def futures_seller_action(request, pk):
    """Seller confirms or manages a reservation."""
    if request.method != 'POST':
        return redirect('marketplace:futures_my')

    company = get_user_company(request)
    reservation = get_object_or_404(
        FuturesReservation, pk=pk, listing__seller_company=company
    )
    action = request.POST.get('action')

    if action == 'confirm' and reservation.status == 'pending':
        reservation.status = 'confirmed'
        reservation.confirmed_at = timezone.now()
        reservation.save(update_fields=['status', 'confirmed_at'])
        messages.success(request, f'Rezervacija potvrdjena: {reservation.buyer_company.name}')

    elif action == 'mark_ready' and reservation.status in ('confirmed', 'deposit_paid'):
        reservation.status = 'ready'
        reservation.save(update_fields=['status'])
        messages.success(request, _('Roba oznacena kao spremna.'))

    elif action == 'cancel':
        reservation.status = 'cancelled'
        reservation.save(update_fields=['status'])
        # Return reserved qty
        listing = reservation.listing
        listing.reserved_qty -= reservation.quantity
        if listing.reserved_qty < 0:
            listing.reserved_qty = Decimal('0')
        if listing.status == 'fully_booked':
            listing.status = 'open'
        listing.save(update_fields=['reserved_qty', 'status'])
        messages.warning(request, _('Rezervacija otkazana.'))

    return redirect('marketplace:futures_my')
