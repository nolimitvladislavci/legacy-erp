"""
experiences/views.py — Agro-Turizam 360 views
"""
import json
from decimal import Decimal

from django.contrib import messages
from django.utils.translation import gettext as _
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.db import models, DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

from core.company_utils import get_user_company
from .models import (
    Experience, ExperienceSchedule, ExperienceBooking,
    ExperienceInclusion, ExperienceReview,
    AgroPackage, PackageComponent,
    RecallEvent, RecallNotification,
)


# ═══════════════════════════════════════════════════════════════════
# EXPERIENCE CRUD
# ═══════════════════════════════════════════════════════════════════

@login_required
def experience_list(request):
    company = get_user_company(request)
    if not company:
        messages.error(request, _('Niste povezani s tvrtkom. Odaberite tvrtku iz izbornika.'))
        return redirect('dashboard')

    qs = Experience.objects.filter(company=company)
    q = request.GET.get('q', '')
    if q:
        qs = qs.filter(models.Q(name__icontains=q) | models.Q(description__icontains=q))

    exp_type = request.GET.get('type', '')
    if exp_type:
        qs = qs.filter(experience_type=exp_type)

    stats = {
        'ukupno': qs.count(),
        'aktivnih': qs.filter(is_active=True).count(),
        'avg_rating': ExperienceReview.objects.filter(
            booking__schedule__experience__company=company
        ).aggregate(avg=models.Avg('rating'))['avg'] or 0,
    }

    paginator = Paginator(qs, 25)
    page = paginator.get_page(request.GET.get('page'))

    return render(request, 'experiences/experience_list.html', {
        'page': page, 'q': q, 'exp_type': exp_type, 'stats': stats,
        'type_choices': Experience.TYPE_CHOICES,
    })


@login_required
def experience_create(request):
    company = get_user_company(request)
    if not company:
        messages.error(request, _('Niste povezani s tvrtkom. Odaberite tvrtku iz izbornika.'))
        return redirect('dashboard')

    if request.method == 'POST':
        exp = Experience(
            company=company,
            name=request.POST.get('name', ''),
            experience_type=request.POST.get('experience_type', 'ostalo'),
            description=request.POST.get('description', ''),
            what_to_bring=request.POST.get('what_to_bring', ''),
            duration_minutes=int(request.POST.get('duration_minutes', 60)),
            capacity=int(request.POST.get('capacity', 10)),
            min_pax=int(request.POST.get('min_pax', 1)),
            difficulty=request.POST.get('difficulty', 'easy'),
            meeting_point=request.POST.get('meeting_point', ''),
            price_per_person=Decimal(request.POST.get('price_per_person', '0')),
            deposit_pct=int(request.POST.get('deposit_pct', 30)),
            cancellation_hours=int(request.POST.get('cancellation_hours', 12)),
            tax_rate=Decimal(request.POST.get('tax_rate', '25')),
            guide_languages=request.POST.get('guide_languages', 'hr'),
        )
        if request.POST.get('guide'):
            from django.contrib.auth import get_user_model
            try:
                exp.guide = get_user_model().objects.get(pk=request.POST['guide'])
            except ObjectDoesNotExist:
                pass
        exp.save()
        messages.success(request, f'Iskustvo "{exp.name}" kreirano.')
        return redirect('experiences:experience_detail', pk=exp.pk)

    return render(request, 'experiences/experience_form.html', {
        'type_choices': Experience.TYPE_CHOICES,
        'difficulty_choices': Experience.DIFFICULTY_CHOICES,
    })


@login_required
def experience_detail(request, pk):
    company = get_user_company(request)
    exp = get_object_or_404(Experience, pk=pk, company=company)

    schedules = exp.schedules.filter(date__gte=timezone.now().date()).order_by('date', 'time_from')[:20]
    inclusions = exp.inclusions.all()
    reviews = ExperienceReview.objects.filter(
        booking__schedule__experience=exp, is_public=True
    ).order_by('-created_at')[:10]

    avg_rating = reviews.aggregate(avg=models.Avg('rating'))['avg'] or 0
    total_bookings = ExperienceBooking.objects.filter(
        schedule__experience=exp, status__in=['confirmed', 'completed']
    ).aggregate(total=models.Sum('pax_count'))['total'] or 0

    return render(request, 'experiences/experience_detail.html', {
        'exp': exp, 'schedules': schedules, 'inclusions': inclusions,
        'reviews': reviews, 'avg_rating': avg_rating, 'total_bookings': total_bookings,
    })


@login_required
def experience_edit(request, pk):
    company = get_user_company(request)
    exp = get_object_or_404(Experience, pk=pk, company=company)

    if request.method == 'POST':
        exp.name = request.POST.get('name', exp.name)
        exp.experience_type = request.POST.get('experience_type', exp.experience_type)
        exp.description = request.POST.get('description', exp.description)
        exp.what_to_bring = request.POST.get('what_to_bring', exp.what_to_bring)
        exp.duration_minutes = int(request.POST.get('duration_minutes', exp.duration_minutes))
        exp.capacity = int(request.POST.get('capacity', exp.capacity))
        exp.price_per_person = Decimal(request.POST.get('price_per_person', str(exp.price_per_person)))
        exp.deposit_pct = int(request.POST.get('deposit_pct', exp.deposit_pct))
        exp.cancellation_hours = int(request.POST.get('cancellation_hours', exp.cancellation_hours))
        exp.tax_rate = Decimal(request.POST.get('tax_rate', str(exp.tax_rate)))
        exp.is_active = request.POST.get('is_active') == 'on'
        exp.save()
        messages.success(request, f'Iskustvo "{exp.name}" ažurirano.')
        return redirect('experiences:experience_detail', pk=exp.pk)

    return render(request, 'experiences/experience_form.html', {
        'exp': exp, 'edit': True,
        'type_choices': Experience.TYPE_CHOICES,
        'difficulty_choices': Experience.DIFFICULTY_CHOICES,
    })


@login_required
def schedule_create(request, pk):
    company = get_user_company(request)
    exp = get_object_or_404(Experience, pk=pk, company=company)

    if request.method == 'POST':
        sched = ExperienceSchedule(
            experience=exp,
            date=request.POST.get('date'),
            time_from=request.POST.get('time_from'),
            time_to=request.POST.get('time_to'),
            max_pax=int(request.POST.get('max_pax', exp.capacity)),
        )
        sched.save()
        messages.success(request, f'Termin {sched.date} {sched.time_from} dodan.')
        return redirect('experiences:experience_detail', pk=exp.pk)

    return render(request, 'experiences/schedule_form.html', {'exp': exp})


@login_required
def booking_create(request, schedule_pk):
    schedule = get_object_or_404(ExperienceSchedule, pk=schedule_pk)
    company = get_user_company(request)

    if not schedule.is_bookable:
        messages.error(request, _('Termin je popunjen ili zatvoren.'))
        return redirect('experiences:experience_detail', pk=schedule.experience.pk)

    if request.method == 'POST':
        pax = int(request.POST.get('pax_count', 1))
        children = int(request.POST.get('children_count', 0))

        if pax > schedule.available_spots:
            messages.error(request, f'Dostupno samo {schedule.available_spots} mjesta.')
            return redirect('experiences:experience_detail', pk=schedule.experience.pk)

        booking = ExperienceBooking(
            schedule=schedule,
            guest_name=request.POST.get('guest_name', ''),
            guest_email=request.POST.get('guest_email', ''),
            guest_phone=request.POST.get('guest_phone', ''),
            guest_country=request.POST.get('guest_country', ''),
            pax_count=pax,
            children_count=children,
            notes=request.POST.get('notes', ''),
        )
        # Poveži s rental bookingom ako postoji
        rental_booking_id = request.POST.get('rental_booking_id')
        if rental_booking_id:
            from rental.models import Booking as RentalBooking
            try:
                booking.rental_booking = RentalBooking.objects.get(pk=rental_booking_id)
            except RentalBooking.DoesNotExist:
                pass

        booking.save()
        messages.success(request,
            f'Rezervacija kreirana! Depozit: {booking.deposit_amount:.2f} EUR. '
            f'Ukupna cijena: {booking.price_total:.2f} EUR.')
        return redirect('experiences:experience_detail', pk=schedule.experience.pk)

    return render(request, 'experiences/booking_form.html', {'schedule': schedule})


@login_required
def booking_confirm_deposit(request, pk):
    booking = get_object_or_404(ExperienceBooking, pk=pk)
    if request.method == 'POST':
        method = request.POST.get('payment_method', 'card')
        booking.confirm_deposit(method=method)
        messages.success(request, f'Depozit potvrđen za {booking.guest_name}.')
    return redirect('experiences:experience_detail', pk=booking.schedule.experience.pk)


@login_required
def booking_cancel(request, pk):
    booking = get_object_or_404(ExperienceBooking, pk=pk)
    if request.method == 'POST':
        booking.cancel()
        if booking.deposit_forfeited:
            messages.warning(request, f'Rezervacija otkazana. Depozit {booking.deposit_amount:.2f} EUR zadržan.')
        else:
            messages.success(request, f'Rezervacija otkazana. Povrat: {booking.refund_amount:.2f} EUR.')
    return redirect('experiences:experience_detail', pk=booking.schedule.experience.pk)


@login_required
def booking_check_in(request, pk):
    """
    Gost je došao — check-in.
    Auto-alocira inventory iz ExperienceInclusion kroz SplitAllocation servis.
    """
    booking = get_object_or_404(ExperienceBooking, pk=pk)

    if booking.status != 'confirmed':
        messages.error(request, f'Booking nije u statusu "potvrđen" (trenutno: {booking.get_status_display()}).')
        return redirect('experiences:experience_detail', pk=booking.schedule.experience.pk)

    if request.method == 'POST':
        booking.status = 'checked_in'
        booking.save(update_fields=['status'])

        # Auto-alociraj inventory za internu upotrebu
        from experiences.models import ExperienceInclusion
        inclusions = ExperienceInclusion.objects.filter(
            experience=booking.schedule.experience,
            inventory_item__isnull=False,
        ).select_related('inventory_item')

        allocated = []
        for incl in inclusions:
            qty_needed = incl.quantity_per_person * booking.pax_count
            try:
                from inventory.services.split_allocation import allocate_to_inhouse
                movement = allocate_to_inhouse(
                    item=incl.inventory_item,
                    qty=qty_needed,
                    reason=f'Experience check-in: {booking.guest_name} x{booking.pax_count} — {incl.description}',
                    user=request.user,
                )
                allocated.append(f'{incl.description} ({qty_needed} {incl.unit})')
            except ValueError as e:
                messages.warning(request, f'Zaliha upozorenje za {incl.description}: {e}')
            except Exception as e:
                import logging
                logging.getLogger('experiences').error('Check-in allocation error: %s', e)

        guest_msg = f'{booking.guest_name} (x{booking.pax_count}) — checked in!'
        if allocated:
            guest_msg += f' Alocirano: {", ".join(allocated)}.'
        messages.success(request, guest_msg)

    return redirect('experiences:experience_detail', pk=booking.schedule.experience.pk)


@login_required
def booking_complete(request, pk):
    """
    Iskustvo završeno — generira račun ako nema depozita.
    """
    booking = get_object_or_404(ExperienceBooking, pk=pk)

    if booking.status != 'checked_in':
        messages.error(request, f'Gost mora biti checked-in prije završetka.')
        return redirect('experiences:experience_detail', pk=booking.schedule.experience.pk)

    if request.method == 'POST':
        booking.status = 'completed'
        booking.save(update_fields=['status'])

        # Oslobodi schedule slot
        sched = booking.schedule
        if sched.status == 'full':
            sched.status = 'open'
            sched.save(update_fields=['status'])

        messages.success(request, f'{booking.guest_name} — iskustvo završeno.')

    return redirect('experiences:experience_detail', pk=booking.schedule.experience.pk)


@login_required
def booking_no_show(request, pk):
    booking = get_object_or_404(ExperienceBooking, pk=pk)
    if request.method == 'POST':
        booking.mark_no_show()
        msg = f'{booking.guest_name} — no-show. Depozit zadržan.'
        if booking.forfeited_invoice_id:
            msg += f' Račun #{booking.forfeited_invoice_id} generiran.'
        messages.warning(request, msg)
    return redirect('experiences:experience_detail', pk=booking.schedule.experience.pk)


@login_required
def review_create(request, pk):
    booking = get_object_or_404(ExperienceBooking, pk=pk, status='completed')

    if hasattr(booking, 'review'):
        messages.info(request, _('Ocjena već postoji.'))
        return redirect('experiences:experience_detail', pk=booking.schedule.experience.pk)

    if request.method == 'POST':
        review = ExperienceReview(
            booking=booking,
            rating=int(request.POST.get('rating', 5)),
            text=request.POST.get('text', ''),
        )
        review.save()
        messages.success(request, _('Hvala na ocjeni!'))
        return redirect('experiences:experience_detail', pk=booking.schedule.experience.pk)

    return render(request, 'experiences/review_form.html', {'booking': booking})


# ═══════════════════════════════════════════════════════════════════
# AGRO PAKETI
# ═══════════════════════════════════════════════════════════════════

@login_required
def package_list(request):
    company = get_user_company(request)
    if not company:
        messages.error(request, _('Niste povezani s tvrtkom. Odaberite tvrtku iz izbornika.'))
        return redirect('dashboard')

    qs = AgroPackage.objects.filter(company=company)
    return render(request, 'experiences/package_list.html', {'packages': qs})


@login_required
def package_create(request):
    company = get_user_company(request)
    if not company:
        messages.error(request, _('Niste povezani s tvrtkom. Odaberite tvrtku iz izbornika.'))
        return redirect('dashboard')

    if request.method == 'POST':
        pkg = AgroPackage(
            company=company,
            name=request.POST.get('name', ''),
            description=request.POST.get('description', ''),
            advertised_price=Decimal(request.POST.get('advertised_price', '0')),
            duration_days=int(request.POST.get('duration_days', 1)),
            max_guests=int(request.POST.get('max_guests', 2)),
        )
        pkg.save()
        messages.success(request, f'Paket "{pkg.name}" kreiran. Dodajte komponente.')
        return redirect('experiences:package_detail', pk=pkg.pk)

    return render(request, 'experiences/package_form.html')


@login_required
def package_detail(request, pk):
    company = get_user_company(request)
    pkg = get_object_or_404(AgroPackage, pk=pk, company=company)
    components = pkg.components.all()
    tax_info = pkg.tax_breakdown()

    return render(request, 'experiences/package_detail.html', {
        'pkg': pkg, 'components': components, 'tax_info': tax_info,
    })


@login_required
def package_tax_breakdown(request, pk):
    """JSON endpoint za TaxSplitter pregled."""
    company = get_user_company(request)
    pkg = get_object_or_404(AgroPackage, pk=pk, company=company)
    tb = pkg.tax_breakdown()

    # Serialize Decimal za JSON
    def decimal_to_str(obj):
        if isinstance(obj, Decimal):
            return str(obj)
        raise TypeError

    return JsonResponse(tb, json_dumps_params={'default': decimal_to_str})


# ═══════════════════════════════════════════════════════════════════
# RECALL — HACCP
# ═══════════════════════════════════════════════════════════════════

@login_required
def recall_list(request):
    company = get_user_company(request)
    if not company:
        messages.error(request, _('Niste povezani s tvrtkom. Odaberite tvrtku iz izbornika.'))
        return redirect('dashboard')

    qs = RecallEvent.objects.filter(company=company)
    return render(request, 'experiences/recall_list.html', {'recalls': qs})


@login_required
def recall_create(request):
    company = get_user_company(request)
    if not company:
        messages.error(request, _('Niste povezani s tvrtkom. Odaberite tvrtku iz izbornika.'))
        return redirect('dashboard')

    if request.method == 'POST':
        recall = RecallEvent(
            company=company,
            source_model=request.POST.get('source_model', ''),
            source_id=int(request.POST.get('source_id', 0)),
            lot_number=request.POST.get('lot_number', ''),
            title=request.POST.get('title', ''),
            description=request.POST.get('description', ''),
            severity=request.POST.get('severity', 'warning'),
            created_by=request.user,
        )
        recall.save()

        # Odmah pokreni trace
        affected = recall.trace_affected()
        messages.warning(request,
            f'RECALL #{recall.pk} kreiran. '
            f'Pogođeno: {len(affected["marketplace_orders"])} narudžbi, '
            f'{len(affected["marketplace_products"])} listinga.')
        return redirect('experiences:recall_detail', pk=recall.pk)

    return render(request, 'experiences/recall_form.html', {
        'severity_choices': RecallEvent.SEVERITY_CHOICES,
    })


@login_required
def recall_detail(request, pk):
    company = get_user_company(request)
    recall = get_object_or_404(RecallEvent, pk=pk, company=company)
    notifications = recall.notifications.all()

    return render(request, 'experiences/recall_detail.html', {
        'recall': recall, 'notifications': notifications,
    })


@login_required
def recall_trace(request, pk):
    """Pokreni trace — pronađi sve pogođene."""
    company = get_user_company(request)
    recall = get_object_or_404(RecallEvent, pk=pk, company=company)

    affected = recall.trace_affected()
    return JsonResponse(affected, safe=False, json_dumps_params={'default': str})


@login_required
def recall_notify(request, pk):
    """Pošalji obavijesti svim pogođenima."""
    company = get_user_company(request)
    recall = get_object_or_404(RecallEvent, pk=pk, company=company)

    if request.method == 'POST':
        affected = recall.trace_affected()
        created = 0

        # Obavijesti kupce na marketplaceu
        for order_data in affected['marketplace_orders']:
            order_number = order_data.get('order__order_number', '')
            buyer_name = order_data.get('order__buyer_company__name', '')

            RecallNotification.objects.create(
                recall=recall,
                channel='email',
                recipient_type='marketplace_buyer',
                recipient_name=buyer_name,
                recipient_contact=buyer_name,
                message=f'UPOZORENJE: Proizvod iz narudžbe {order_number} je povučen. '
                        f'Razlog: {recall.title}. {recall.description}. '
                        f'NE KONZUMIRATI. Kontaktirajte nas za povrat.',
            )
            created += 1

        recall.status = 'notified'
        recall.save(update_fields=['status'])

        messages.success(request, f'Kreirano {created} obavijesti za slanje.')
        return redirect('experiences:recall_detail', pk=recall.pk)

    return redirect('experiences:recall_detail', pk=recall.pk)


@login_required
def normativ_preview(request, pk):
    """
    GET /experiences/<pk>/normativ/?pax=10
    Vraća JSON s normativom za zadani broj gostiju + stock status.
    """
    from .models import Experience, ExperienceInclusion
    from django.http import JsonResponse

    exp = get_object_or_404(Experience, pk=pk)
    pax = int(request.GET.get('pax', 1))

    items = []
    total_cost = 0
    all_sufficient = True

    for incl in exp.inclusions.select_related('inventory_item').all():
        needed = float(incl.total_for_pax(pax))
        available = float(incl.inventory_item.quantity) if incl.inventory_item else None
        sufficient = incl.stock_sufficient(pax)
        deficit = float(incl.stock_deficit(pax)) if incl.inventory_item else 0

        if not sufficient:
            all_sufficient = False

        cost = 0
        if incl.inventory_item and incl.inventory_item.purchase_price:
            cost = float(incl.inventory_item.purchase_price) * needed

        items.append({
            'description': incl.description,
            'per_person': float(incl.quantity_per_person),
            'unit': incl.unit,
            'total_needed': needed,
            'available': available,
            'sufficient': sufficient,
            'deficit': deficit,
            'cost': round(cost, 2),
        })
        total_cost += cost

    return JsonResponse({
        'experience': exp.name,
        'pax': pax,
        'items': items,
        'all_sufficient': all_sufficient,
        'total_material_cost': round(total_cost, 2),
    })
