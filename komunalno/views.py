import logging
import hashlib
import json
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

from .models import (
    WasteStation, WasteCategory, CitizenCard, AnnualQuota,
    WasteDelivery, ScaleReading, OntoExportBatch, WasteQuickButton,
)


# ─── DASHBOARD ──────────────────────────────────────────────────────

@login_required
def dashboard(request):
    """Glavni dashboard za komunalno upravljanje."""
    company = request.company
    today = timezone.localdate()

    stations = WasteStation.objects.filter(company=company, is_active=True)

    # Danas statistika
    today_deliveries = WasteDelivery.objects.filter(
        company=company,
        delivery_date__date=today,
        status='confirmed'
    )
    today_count = today_deliveries.count()
    today_weight = today_deliveries.aggregate(t=Sum('quantity'))['t'] or Decimal('0')
    today_charges = today_deliveries.filter(charge_amount__gt=0).aggregate(t=Sum('charge_amount'))['t'] or Decimal('0')

    # e-ONTO status
    pending_onto = OntoExportBatch.objects.filter(
        company=company,
        status__in=['pending', 'error', 'retry']
    ).count()

    # Prekoračenja danas
    overages_today = today_deliveries.filter(over_quota__gt=0).count()

    context = {
        'stations': stations,
        'today_count': today_count,
        'today_weight': today_weight,
        'today_charges': today_charges,
        'pending_onto': pending_onto,
        'overages_today': overages_today,
    }
    return render(request, 'komunalno/dashboard.html', context)


# ─── KIOSK MODE (Terenski UI) ──────────────────────────────────────

@login_required
def kiosk_home(request, station_id):
    """
    Početni ekran kioska — Mina #1 rješenje.
    Full-screen, ogromni gumbi, touch-friendly.
    Operater skenira QR iskaznice ili unosi broj ručno.
    """
    station = get_object_or_404(WasteStation, pk=station_id, company=request.company)

    # Današnja statistika za ovaj station
    today = timezone.localdate()
    today_count = WasteDelivery.objects.filter(
        station=station, delivery_date__date=today, status='confirmed'
    ).count()
    today_weight = WasteDelivery.objects.filter(
        station=station, delivery_date__date=today, status='confirmed'
    ).aggregate(t=Sum('quantity'))['t'] or Decimal('0')

    context = {
        'station': station,
        'today_count': today_count,
        'today_weight': today_weight,
    }
    return render(request, 'komunalno/kiosk/home.html', context)


@login_required
def kiosk_scan(request, station_id):
    """
    HTMX endpoint — rezultat skeniranja QR/barkoda.
    Traži CitizenCard po card_number.
    """
    station = get_object_or_404(WasteStation, pk=station_id, company=request.company)
    scan_input = request.POST.get('scan_input', '').strip()

    if not scan_input:
        return render(request, 'komunalno/kiosk/partials/scan_error.html', {
            'error': 'Skenirajte iskaznicu ili unesite broj.'
        })

    # Traži po card_number ili partner OIB
    card = CitizenCard.objects.filter(
        company=request.company,
        is_active=True
    ).filter(
        Q(card_number=scan_input) | Q(partner__oib=scan_input)
    ).select_related('partner').first()

    if not card:
        return render(request, 'komunalno/kiosk/partials/scan_error.html', {
            'error': f'Iskaznica "{scan_input}" nije pronađena.',
            'scan_input': scan_input,
        })

    return redirect('komunalno:kiosk_citizen', station_id=station.pk, card_id=card.pk)


@login_required
def kiosk_citizen(request, station_id, card_id):
    """
    Ekran odabira kategorije otpada — veliki gumbi u boji.
    Prikazuje info o građaninu i preostale kvote.
    """
    station = get_object_or_404(WasteStation, pk=station_id, company=request.company)
    card = get_object_or_404(CitizenCard, pk=card_id, company=request.company, is_active=True)

    # Brzi gumbi — per-station ili globalni
    buttons = WasteQuickButton.objects.filter(
        company=request.company,
        is_active=True
    ).filter(
        Q(station=station) | Q(station__isnull=True)
    ).select_related('category').order_by('sort_order')

    # Kvote za svaku kategoriju
    year = timezone.localdate().year
    button_data = []
    for btn in buttons:
        remaining = card.get_remaining_quota(btn.category)
        used = card.get_quota_usage(btn.category, year)
        quota = card._get_quota(btn.category)
        button_data.append({
            'button': btn,
            'remaining': remaining,
            'used': used,
            'quota': quota,
            'is_over': remaining is not None and remaining <= 0,
        })

    context = {
        'station': station,
        'card': card,
        'button_data': button_data,
        'has_scale': station.scale_type != 'none',
    }
    return render(request, 'komunalno/kiosk/citizen.html', context)


@login_required
@require_POST
def kiosk_deliver(request, station_id):
    """
    Procesira dostavu otpada.
    Ako vaga je spojena — quantity dolazi s vage (ScaleReading).
    Ako prekoračenje — generira POS račun.
    """
    station = get_object_or_404(WasteStation, pk=station_id, company=request.company)
    card_id = request.POST.get('card_id')
    category_id = request.POST.get('category_id')
    quantity = request.POST.get('quantity', '0')
    scale_reading_id = request.POST.get('scale_reading_id')

    card = get_object_or_404(CitizenCard, pk=card_id, company=request.company)
    category = get_object_or_404(WasteCategory, pk=category_id)

    try:
        qty = Decimal(quantity)
    except (ValueError, TypeError):
        qty = Decimal('0')

    if qty <= 0:
        return render(request, 'komunalno/kiosk/partials/delivery_error.html', {
            'error': 'Količina mora biti veća od 0.'
        })

    # Kreiraj delivery
    delivery = WasteDelivery(
        company=request.company,
        station=station,
        citizen=card,
        category=category,
        quantity=qty,
        operator=request.user,
    )

    # Vaga integracija (Mina #2)
    if scale_reading_id:
        try:
            reading = ScaleReading.objects.get(pk=scale_reading_id, station=station)
            delivery.scale_reading = reading
            delivery.weight_source = 'scale'
            # Provjeri integritet
            if not reading.verify_integrity():
                reading.is_tampered = True
                reading.save(update_fields=['is_tampered'])
        except ScaleReading.DoesNotExist:
            pass

    # Integrity hash za delivery
    payload = f'{card.pk}|{category.pk}|{qty}|{timezone.now().isoformat()}|{station.pk}'
    from django.conf import settings as django_settings
    secret = getattr(django_settings, 'SCALE_INTEGRITY_SECRET', django_settings.SECRET_KEY[:16])
    delivery.integrity_hash = hashlib.sha256(f'{payload}|{secret}'.encode()).hexdigest()

    delivery.save()

    # Procesiraj (kvota check + naknada)
    delivery.process_delivery()

    # Ako prekoračenje → kreiraj POS račun
    if delivery.charge_amount > 0:
        _create_overage_receipt(request, delivery)

    return redirect('komunalno:kiosk_confirm', station_id=station.pk, delivery_id=delivery.pk)


@login_required
def kiosk_confirm(request, station_id, delivery_id):
    """Potvrda dostave — prikazuje rezultat i kvotu."""
    station = get_object_or_404(WasteStation, pk=station_id, company=request.company)
    delivery = get_object_or_404(WasteDelivery, pk=delivery_id, company=request.company)

    remaining_after = delivery.citizen.get_remaining_quota(delivery.category)

    context = {
        'station': station,
        'delivery': delivery,
        'remaining_after': remaining_after,
        'has_charge': delivery.charge_amount > 0,
    }
    return render(request, 'komunalno/kiosk/confirm.html', context)


@login_required
def kiosk_receipt(request, station_id, delivery_id):
    """Printable receipt za građanina."""
    delivery = get_object_or_404(WasteDelivery, pk=delivery_id, company=request.company)
    context = {
        'delivery': delivery,
        'company': request.company,
    }
    return render(request, 'komunalno/kiosk/receipt.html', context)


# ─── SCALE API ──────────────────────────────────────────────────────

@login_required
@require_POST
def api_scale_reading(request, station_id):
    """
    Prima očitanje s vage via JavaScript Web Serial API.
    Browser čita RS232/USB vagu → šalje raw data ovamo.
    Mina #2 rješenje: hardverski povučena težina, hash-protected.
    """
    station = get_object_or_404(WasteStation, pk=station_id, company=request.company)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    raw_data = data.get('raw_data', '').strip()
    weight_str = data.get('weight_kg', '0')
    is_stable = data.get('is_stable', True)
    source = data.get('source', 'web_serial')

    try:
        weight_kg = Decimal(str(weight_str))
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Invalid weight'}, status=400)

    if weight_kg <= 0:
        return JsonResponse({'error': 'Weight must be positive'}, status=400)

    now = timezone.now()
    integrity_hash = ScaleReading.compute_hash(raw_data, now, station.pk)

    reading = ScaleReading.objects.create(
        company=request.company,
        station=station,
        raw_data=raw_data,
        weight_kg=weight_kg,
        is_stable=is_stable,
        integrity_hash=integrity_hash,
        source=source,
        operator=request.user,
        read_at=now,
    )

    return JsonResponse({
        'id': reading.pk,
        'weight_kg': str(reading.weight_kg),
        'is_stable': reading.is_stable,
        'hash': reading.integrity_hash[:8],
        'read_at': reading.read_at.isoformat(),
    })


@login_required
@require_GET
def api_scale_latest(request, station_id):
    """Dohvati zadnje očitanje s vage (za polling)."""
    station = get_object_or_404(WasteStation, pk=station_id, company=request.company)

    reading = ScaleReading.objects.filter(
        station=station,
        read_at__gte=timezone.now() - timedelta(minutes=5)
    ).order_by('-read_at').first()

    if not reading:
        return JsonResponse({'weight_kg': '0', 'available': False})

    return JsonResponse({
        'id': reading.pk,
        'weight_kg': str(reading.weight_kg),
        'is_stable': reading.is_stable,
        'available': True,
        'read_at': reading.read_at.isoformat(),
    })


@login_required
def api_citizen_lookup(request):
    """HTMX API za lookup građanina po scan inputu."""
    q = request.GET.get('q', '').strip()
    if len(q) < 2:
        return render(request, 'komunalno/kiosk/partials/citizen_result.html', {'cards': []})

    cards = CitizenCard.objects.filter(
        company=request.company,
        is_active=True,
    ).filter(
        Q(card_number__icontains=q) |
        Q(partner__name__icontains=q) |
        Q(partner__oib__startswith=q) |
        Q(address__icontains=q)
    ).select_related('partner')[:10]

    return render(request, 'komunalno/kiosk/partials/citizen_result.html', {'cards': cards})


# ─── e-ONTO ─────────────────────────────────────────────────────────

@login_required
def onto_dashboard(request):
    """Pregled e-ONTO batcheva."""
    batches = OntoExportBatch.objects.filter(company=request.company).order_by('-created_at')[:50]

    # Neposlane deliverije
    unsent = WasteDelivery.objects.filter(
        company=request.company,
        status='confirmed',
        onto_exported=False,
    ).count()

    context = {
        'batches': batches,
        'unsent_count': unsent,
    }
    return render(request, 'komunalno/onto/dashboard.html', context)


@login_required
def onto_batch_detail(request, batch_id):
    """Detalji jednog e-ONTO batcha."""
    batch = get_object_or_404(OntoExportBatch, pk=batch_id, company=request.company)
    deliveries = WasteDelivery.objects.filter(onto_batch=batch).select_related('citizen__partner', 'category')

    context = {
        'batch': batch,
        'deliveries': deliveries,
    }
    return render(request, 'komunalno/onto/batch_detail.html', context)


@login_required
@require_POST
def onto_manual_export(request):
    """Ručno pokreni e-ONTO export za danas."""
    from .tasks import create_onto_batch

    station_id = request.POST.get('station_id')
    if station_id:
        station = get_object_or_404(WasteStation, pk=station_id, company=request.company)
        create_onto_batch(request.company.pk, station.pk)

    if request.headers.get('HX-Request'):
        return render(request, 'komunalno/onto/partials/export_started.html')
    return redirect('komunalno:onto_dashboard')


# ─── REPORTS ────────────────────────────────────────────────────────

@login_required
def reports(request):
    """Pregled izvještaja."""
    return render(request, 'komunalno/reports/index.html')


@login_required
def daily_report(request):
    """Dnevni izvještaj za odabrani datum."""
    report_date = request.GET.get('date', timezone.localdate().isoformat())
    try:
        report_date = date.fromisoformat(report_date)
    except ValueError:
        report_date = timezone.localdate()

    deliveries = WasteDelivery.objects.filter(
        company=request.company,
        delivery_date__date=report_date,
        status='confirmed'
    ).select_related('citizen__partner', 'category', 'station')

    # Agregate po kategoriji
    by_category = deliveries.values(
        'category__key_number', 'category__name'
    ).annotate(
        total_qty=Sum('quantity'),
        count=Count('id'),
        total_charge=Sum('charge_amount'),
    ).order_by('category__key_number')

    total_weight = deliveries.aggregate(t=Sum('quantity'))['t'] or 0
    total_count = deliveries.count()
    total_charges = deliveries.aggregate(t=Sum('charge_amount'))['t'] or 0

    context = {
        'report_date': report_date,
        'deliveries': deliveries,
        'by_category': by_category,
        'total_weight': total_weight,
        'total_count': total_count,
        'total_charges': total_charges,
    }
    return render(request, 'komunalno/reports/daily.html', context)


# ─── MANAGEMENT ─────────────────────────────────────────────────────

@login_required
def station_list(request):
    stations = WasteStation.objects.filter(company=request.company)
    return render(request, 'komunalno/station_list.html', {'stations': stations})


@login_required
def citizen_list(request):
    q = request.GET.get('q', '')
    cards = CitizenCard.objects.filter(company=request.company).select_related('partner')
    if q:
        cards = cards.filter(
            Q(card_number__icontains=q) | Q(partner__name__icontains=q) | Q(address__icontains=q)
        )
    return render(request, 'komunalno/citizen_list.html', {'cards': cards[:100], 'q': q})


@login_required
def citizen_detail(request, card_id):
    card = get_object_or_404(CitizenCard, pk=card_id, company=request.company)
    year = timezone.localdate().year

    deliveries = WasteDelivery.objects.filter(
        citizen=card, delivery_date__year=year, status='confirmed'
    ).select_related('category', 'station').order_by('-delivery_date')

    # Kvote
    categories = WasteCategory.objects.all()
    quota_data = []
    for cat in categories:
        used = card.get_quota_usage(cat, year)
        remaining = card.get_remaining_quota(cat)
        quota = card._get_quota(cat)
        if used > 0 or (quota and quota > 0):
            quota_data.append({
                'category': cat,
                'used': used,
                'remaining': remaining,
                'quota': quota,
                'percent': int(used / quota * 100) if quota and quota > 0 else 0,
            })

    context = {
        'card': card,
        'deliveries': deliveries,
        'quota_data': quota_data,
        'year': year,
    }
    return render(request, 'komunalno/citizen_detail.html', context)


@login_required
def category_list(request):
    categories = WasteCategory.objects.all()
    return render(request, 'komunalno/category_list.html', {'categories': categories})


@login_required
def quota_management(request):
    year = timezone.localdate().year
    quotas = AnnualQuota.objects.filter(
        company=request.company, year=year
    ).select_related('category')
    categories = WasteCategory.objects.all()

    context = {
        'quotas': quotas,
        'categories': categories,
        'year': year,
    }
    return render(request, 'komunalno/quota_management.html', context)


# ─── HELPERS ────────────────────────────────────────────────────────

def _create_overage_receipt(request, delivery):
    """
    Kreira POS račun za prekoračenje kvote.
    Automatski — operater ne mora ništa raditi.
    """
    try:
        from pos.models import POSReceipt, POSPaymentLine, POSSession

        # Pronađi aktivnu POS sesiju za ovu lokaciju
        session = POSSession.objects.filter(
            terminal__company=request.company,
            is_active=True
        ).first()

        if not session:
            return  # Nema aktivne sesije — naplata se rješava offline

        receipt = POSReceipt.objects.create(
            company=request.company,
            session=session,
            status='paid',
            total_amount=delivery.charge_amount,
            notes=f'Prekoračenje kvote: {delivery.category.name} — '
                  f'{delivery.over_quota} {delivery.unit} × '
                  f'{delivery.category.price_per_unit_over_quota} EUR',
        )

        delivery.pos_receipt = receipt
        delivery.status = 'invoiced'
        delivery.save(update_fields=['pos_receipt', 'status'])

    except (IntegrityError, DatabaseError):
        import logging
        logging.getLogger('komunalno').warning(
            'POS receipt kreiranje failed za delivery %s', delivery.pk, exc_info=True
        )
