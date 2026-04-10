import json
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.utils import timezone

from .models import (
    MeasurementSession, Measurement,
    WindowProfile, GlassType, WindowOffer
)
from .voice_parser import parse_voice_input


# ─── HELPER ───────────────────────────────────────────────────────────────────

def _company(request):
    try:
        return request.user.profile.company
    except Exception:
        return None


# ─── 1. DASHBOARD — lista sesija mjerenja ────────────────────────────────────

@login_required
def dashboard(request):
    company = _company(request)
    sessions = MeasurementSession.objects.filter(company=company).order_by('-created_at')[:20]
    offers   = WindowOffer.objects.filter(company=company).order_by('-created_at')[:10]
    return render(request, 'stolarija/dashboard.html', {
        'sessions': sessions,
        'offers': offers,
        'page_title': 'Stolarija',
    })


# ─── 2. NOVA SESIJA MJERENJA ──────────────────────────────────────────────────

@login_required
def session_new(request):
    company = _company(request)
    if request.method == 'POST':
        session = MeasurementSession.objects.create(
            company=request.POST.get('company') and company or company,
            created_by=request.user,
            address=request.POST.get('address', '').strip(),
            notes=request.POST.get('notes', '').strip(),
        )
        messages.success(request, f'Sesija kreirana — možeš početi mjeriti.')
        return redirect('stolarija:measure', session_id=session.pk)

    return render(request, 'stolarija/session_new.html', {
        'page_title': 'Nova sesija mjerenja',
    })


# ─── 3. MJERENJE — glavni ekran na terenu ─────────────────────────────────────

@login_required
def measure(request, session_id):
    company = _company(request)
    session = get_object_or_404(MeasurementSession, pk=session_id, company=company)
    profiles = WindowProfile.objects.filter(company=company, is_active=True)
    glasses  = GlassType.objects.filter(company=company, is_active=True)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'add_measurement':
            width  = request.POST.get('width_mm', '').strip()
            height = request.POST.get('height_mm', '').strip()
            if not width or not height:
                messages.error(request, 'Širina i visina su obavezni.')
                return redirect('stolarija:measure', session_id=session_id)

            # Auto-assign position number
            next_pos = (session.measurements.order_by('-position_number')
                       .values_list('position_number', flat=True).first() or 0) + 1

            Measurement.objects.create(
                session=session,
                position_number=next_pos,
                width_mm=int(width),
                height_mm=int(height),
                depth_mm=int(request.POST.get('depth_mm') or 0),
                element_type=request.POST.get('element_type', 'window'),
                wing_config=request.POST.get('wing_config', 'double'),
                quantity=int(request.POST.get('quantity') or 1),
                location_note=request.POST.get('location_note', '').strip(),
                floor=int(request.POST.get('floor') or 0),
                profile_id=request.POST.get('profile') or None,
                glass_id=request.POST.get('glass') or None,
                voice_raw=request.POST.get('voice_raw', '').strip(),
                ai_parsed=json.loads(request.POST.get('ai_parsed', '{}')),
                photo_before=request.FILES.get('photo_before'),
                confirmed=True,  # Korisnik je vidio formu i kliknuo Dodaj
            )
            messages.success(request, 'Mjerenje dodano ✓')
            return redirect('stolarija:measure', session_id=session_id)

        elif action == 'finish':
            unconfirmed = session.measurements.filter(confirmed=False).count()
            if unconfirmed:
                messages.warning(request, f'{unconfirmed} mjerenja nisu potvrđena.')
            return redirect('stolarija:session_detail', session_id=session_id)

    measurements = session.measurements.all()
    return render(request, 'stolarija/measure.html', {
        'session': session,
        'measurements': measurements,
        'profiles': profiles,
        'glasses': glasses,
        'element_types': Measurement.ELEMENT_TYPES,
        'wing_configs': Measurement.WING_CONFIGS,
        'page_title': f'Mjerenje — {session.address or "Nova lokacija"}',
    })


# ─── 4. VOICE PARSE API ───────────────────────────────────────────────────────

@login_required
@require_POST
def voice_parse_api(request):
    """
    POST /stolarija/voice-parse/
    Body: {"text": "prozor sto dvadeset puta sto četrdeset bijeli dvokrilni"}
    """
    try:
        data   = json.loads(request.body)
        text   = data.get('text', '').strip()
        if not text:
            return JsonResponse({'error': 'Nema teksta'}, status=400)

        parsed = parse_voice_input(text)
        return JsonResponse({
            'ok': True,
            'parsed': parsed,
            'warnings': parsed['warnings'],
            'confidence': parsed['confidence'],
            'display': {
                'width':  f"{parsed['width_mm']} mm"  if parsed['width_mm']  else '?',
                'height': f"{parsed['height_mm']} mm" if parsed['height_mm'] else '?',
                'type':   dict(Measurement.ELEMENT_TYPES).get(parsed['element_type'], ''),
                'qty':    parsed['quantity'],
                'wing':   dict(Measurement.WING_CONFIGS).get(parsed['wing_config'], ''),
            }
        })
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


# ─── 5. SESSION DETAIL ────────────────────────────────────────────────────────

@login_required
def session_detail(request, session_id):
    company  = _company(request)
    session  = get_object_or_404(MeasurementSession, pk=session_id, company=company)
    measurements = session.measurements.all()
    total_area   = sum(m.total_area_m2 for m in measurements)
    can_offer    = measurements.filter(confirmed=True).exists()

    return render(request, 'stolarija/session_detail.html', {
        'session': session,
        'measurements': measurements,
        'total_area': total_area,
        'can_offer': can_offer,
        'page_title': f'Sesija — {session.address or session.pk}',
    })


# ─── 6. DELETE MEASUREMENT ───────────────────────────────────────────────────

@login_required
@require_POST
def measurement_delete(request, pk):
    company = _company(request)
    m = get_object_or_404(Measurement, pk=pk, session__company=company)
    session_id = m.session_id
    m.delete()
    messages.success(request, 'Mjerenje obrisano.')
    return redirect('stolarija:measure', session_id=session_id)


# ─── 7. GENERIRAJ PONUDU ─────────────────────────────────────────────────────

@login_required
@require_POST
def generate_offer(request, session_id):
    company = _company(request)
    session = get_object_or_404(MeasurementSession, pk=session_id, company=company)

    confirmed = session.measurements.filter(confirmed=True)
    if not confirmed.exists():
        messages.error(request, 'Nema potvrđenih mjerenja za generiranje ponude.')
        return redirect('stolarija:session_detail', session_id=session_id)

    offer = WindowOffer.objects.create(
        company=company,
        session=session,
        valid_days=30,
        notes=request.POST.get('notes', ''),
    )
    offer.recalculate()
    messages.success(request, f'Ponuda {offer.offer_number} generirana ✓')
    return redirect('stolarija:offer_detail', offer_id=offer.pk)


# ─── 8. PONUDA DETAIL ────────────────────────────────────────────────────────

@login_required
def offer_detail(request, offer_id):
    company = _company(request)
    offer   = get_object_or_404(WindowOffer, pk=offer_id, company=company)
    measurements = offer.session.measurements.filter(confirmed=True)

    return render(request, 'stolarija/offer_detail.html', {
        'offer': offer,
        'measurements': measurements,
        'advance_amount': round(offer.total_gross * offer.advance_pct / 100, 2),
        'page_title': f'Ponuda {offer.offer_number}',
    })


# ═══════════════════════════════════════════════════════════════════════════
# FAZA 4: Narudžba → Proizvodnja
# ═══════════════════════════════════════════════════════════════════════════

@login_required
def create_production_order(request, offer_id):
    """Prihvaćena ponuda → proizvodni nalog + BOM."""
    from stolarija.models import WindowOffer, ProductionOrder, BOMItem
    from core.models import BookingSignature
    from decimal import Decimal

    company = _company(request)
    offer = get_object_or_404(WindowOffer, pk=offer_id, company=company)

    if hasattr(offer, 'production_order'):
        messages.info(request, 'Proizvodni nalog već postoji.')
        return redirect('stolarija:production_detail', order_id=offer.production_order.pk)

    # Kreiraj proizvodni nalog
    order = ProductionOrder.objects.create(
        company=company,
        offer=offer,
        estimated_date=None,
    )

    # Generiraj BOM iz mjerenja
    for m in offer.session.measurements.filter(confirmed=True):
        area = m.total_area_m2
        perimeter_m = Decimal(2 * (m.width_mm + m.height_mm)) / Decimal('1000')

        # Profil metraža
        if m.profile:
            BOMItem.objects.create(
                production_order=order,
                measurement=m,
                category='profile',
                name=f'{m.profile.name} ({m.profile.get_material_display()})',
                quantity=perimeter_m * m.quantity,
                unit='m',
                unit_price=m.profile.price_per_m2 * area / perimeter_m if perimeter_m else 0,
            )

        # Staklo m²
        if m.glass:
            BOMItem.objects.create(
                production_order=order,
                measurement=m,
                category='glass',
                name=f'{m.glass.name} (U={m.glass.u_value})',
                quantity=area * m.quantity,
                unit='m2',
                unit_price=m.glass.price_per_m2,
            )

        # Okov (po konfiguraciji)
        hardware_name = {
            'fixed': 'Okov fiksni',
            'single': 'Okov jednokrilni',
            'double': 'Okov dvokrilni',
            'triple': 'Okov trokrilni',
            'sliding': 'Okov klizni',
            'tilt_turn': 'Okov kip-turn',
        }.get(m.wing_config, 'Okov standard')
        BOMItem.objects.create(
            production_order=order,
            measurement=m,
            category='hardware',
            name=hardware_name,
            quantity=m.quantity,
            unit='kom',
        )

        # Brtve
        BOMItem.objects.create(
            production_order=order,
            measurement=m,
            category='seal',
            name='Brtva (unutarnja + vanjska)',
            quantity=perimeter_m * 2 * m.quantity,
            unit='m',
        )

        # Ankeri (4 po otvoru)
        BOMItem.objects.create(
            production_order=order,
            measurement=m,
            category='anchor',
            name='Anker za montažu',
            quantity=4 * m.quantity,
            unit='kom',
        )

    # Izračunaj ukupnu cijenu materijala
    total_material = sum(b.total_price for b in order.bom_items.all())
    order.material_cost = total_material
    order.save(update_fields=['material_cost'])

    # Ažuriraj ponudu status
    offer.status = 'accepted'
    offer.save(update_fields=['status'])

    # Audit
    try:
        BookingSignature.log(request, 'create', target_obj=order,
            target_repr=f'Production: {order.order_number}',
            changes={'bom_items': order.bom_items.count(), 'material_cost': str(total_material)})
    except Exception:
        pass

    messages.success(request, f'Proizvodni nalog {order.order_number} kreiran s {order.bom_items.count()} BOM stavki.')
    return redirect('stolarija:production_detail', order_id=order.pk)


@login_required
def production_detail(request, order_id):
    """Detalj proizvodnog naloga s BOM-om."""
    from stolarija.models import ProductionOrder
    company = _company(request)
    order = get_object_or_404(ProductionOrder, pk=order_id, company=company)
    bom = order.bom_items.all()

    # Status update via POST
    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status and new_status in dict(ProductionOrder.STATUS):
            old_status = order.status
            order.status = new_status
            if new_status == 'ready':
                from django.utils.timezone import now
                order.actual_date = now().date()
            order.save(update_fields=['status', 'actual_date', 'updated_at'])

            try:
                from core.models import BookingSignature
                BookingSignature.log(request, 'update', target_obj=order,
                    changes={'status': {'old': old_status, 'new': new_status}})
            except Exception:
                pass

            messages.success(request, f'Status: {order.get_status_display()}')
            return redirect('stolarija:production_detail', order_id=order.pk)

    return render(request, 'stolarija/production_detail.html', {
        'order': order,
        'bom': bom,
        'bom_by_category': _group_bom(bom),
    })


def _group_bom(bom):
    """Grupiraj BOM stavke po kategoriji."""
    from collections import OrderedDict
    groups = OrderedDict()
    for item in bom:
        cat = item.get_category_display()
        if cat not in groups:
            groups[cat] = []
        groups[cat].append(item)
    return groups


# ═══════════════════════════════════════════════════════════════════════════
# FAZA 6: Ugradnja
# ═══════════════════════════════════════════════════════════════════════════

@login_required
def create_installation(request, order_id):
    """Kreiraj nalog za ugradnju iz gotovog proizvodnog naloga."""
    from stolarija.models import ProductionOrder, InstallationOrder, InstallationChecklist

    company = _company(request)
    order = get_object_or_404(ProductionOrder, pk=order_id, company=company)

    if hasattr(order, 'installation'):
        return redirect('stolarija:installation_detail', install_id=order.installation.pk)

    if request.method == 'POST':
        from django.utils.dateparse import parse_date
        date_str = request.POST.get('date', '')
        scheduled = parse_date(date_str)
        if not scheduled:
            messages.error(request, 'Unesite datum ugradnje.')
            return redirect('stolarija:production_detail', order_id=order.pk)

        install = InstallationOrder.objects.create(
            company=company,
            production_order=order,
            scheduled_date=scheduled,
            team_lead=request.user,
        )

        # Kreiraj checklist za svako mjerenje
        for m in order.offer.session.measurements.filter(confirmed=True):
            InstallationChecklist.objects.create(
                installation=install,
                measurement=m,
            )

        try:
            from core.models import BookingSignature
            BookingSignature.log(request, 'create', target_obj=install,
                target_repr=f'Installation scheduled: {scheduled}')
        except Exception:
            pass

        messages.success(request, f'Ugradnja zakazana za {scheduled}.')
        return redirect('stolarija:installation_detail', install_id=install.pk)

    return redirect('stolarija:production_detail', order_id=order.pk)


@login_required
def installation_detail(request, install_id):
    """Terenski prikaz ugradnje s checklistom."""
    from stolarija.models import InstallationOrder

    company = _company(request)
    install = get_object_or_404(InstallationOrder, pk=install_id, company=company)
    checklist = install.checklist.all()

    if request.method == 'POST':
        # Update checklist items
        for item in checklist:
            for field in ['old_removed', 'opening_prepared', 'frame_mounted',
                         'glass_inserted', 'sealed', 'adjusted', 'cleaned']:
                val = request.POST.get(f'{field}_{item.pk}')
                setattr(item, field, bool(val))
            item.save()

        # Check if all complete
        all_done = all(item.is_complete for item in checklist)
        if all_done and install.status != 'completed':
            from django.utils.timezone import now
            install.status = 'completed'
            install.completed_at = now()
            install.save(update_fields=['status', 'completed_at'])
            messages.success(request, 'Ugradnja završena!')
        else:
            messages.success(request, 'Checklist ažuriran.')

        return redirect('stolarija:installation_detail', install_id=install.pk)

    return render(request, 'stolarija/installation_detail.html', {
        'install': install,
        'checklist': checklist,
        'all_complete': all(item.is_complete for item in checklist),
    })


# ═══════════════════════════════════════════════════════════════════════════
# FAZA 7: Primopredaja
# ═══════════════════════════════════════════════════════════════════════════

@login_required
def handover(request, install_id):
    """Kupac potpisuje primopredaju → garancija se generira."""
    from stolarija.models import InstallationOrder, HandoverProtocol, WindowWarranty
    import secrets

    company = _company(request)
    install = get_object_or_404(InstallationOrder, pk=install_id, company=company)

    if hasattr(install, 'handover'):
        return redirect('stolarija:handover_detail', handover_id=install.handover.pk)

    if request.method == 'POST':
        from django.utils.timezone import now

        client_name = request.POST.get('client_name', '')
        signature = request.POST.get('signature', '')
        remarks = request.POST.get('remarks', '')

        # Kreiraj garanciju
        warranty = WindowWarranty.objects.create(
            session=install.production_order.offer.session,
            valid_years=5,
            handover_date=now().date(),
            client_signature=signature,
            handover_notes=remarks,
        )
        # Fix warranty number (needs pk)
        warranty.warranty_number = f"GAR-{now().year}-{warranty.pk:05d}"
        warranty.save(update_fields=['warranty_number'])

        # Kreiraj primopredaju
        protocol = HandoverProtocol.objects.create(
            installation=install,
            client_name=client_name,
            client_signature=signature,
            signed_at=now(),
            remarks=remarks,
            accepted=True,
            warranty=warranty,
        )

        # Kreiraj prvi servisni pregled (6 mjeseci)
        from stolarija.models import ServiceVisit
        from datetime import timedelta
        ServiceVisit.objects.create(
            warranty=warranty,
            scheduled=now().date() + timedelta(days=180),
        )

        # Audit
        try:
            from core.models import BookingSignature
            BookingSignature.log(request, 'approve', target_obj=protocol,
                target_repr=f'Handover: {client_name}, Warranty: {warranty.warranty_number}')
        except Exception:
            pass

        messages.success(request, f'Primopredaja potpisana. Garancija: {warranty.warranty_number}')
        return redirect('stolarija:handover_detail', handover_id=protocol.pk)

    return render(request, 'stolarija/handover_form.html', {
        'install': install,
    })


@login_required
def handover_detail(request, handover_id):
    """Pregled primopredaje i garancije."""
    from stolarija.models import HandoverProtocol
    company = _company(request)
    protocol = get_object_or_404(HandoverProtocol, pk=handover_id,
                                  installation__company=company)
    return render(request, 'stolarija/handover_detail.html', {
        'protocol': protocol,
        'warranty': protocol.warranty,
    })


# ─── 9. SIGN OFFER API ──────────────────────────────────────────────────────

@login_required
@require_POST
def sign_offer(request, offer_id):
    company = _company(request)
    offer = get_object_or_404(WindowOffer, pk=offer_id, company=company)

    data = json.loads(request.body)
    name = data.get('name', '').strip()
    signature = data.get('signature', '')

    if not name or not signature:
        return JsonResponse({'error': 'Ime i potpis su obavezni'}, status=400)

    offer.signed_by_name = name
    offer.client_signature = signature
    offer.signed_at = timezone.now()
    offer.status = 'accepted'
    offer.save(update_fields=['signed_by_name', 'client_signature', 'signed_at', 'status'])

    return JsonResponse({'ok': True, 'message': 'Ponuda potpisana i prihvacena!'})


# ─── 10. HANDOVER — primopredaja s garancijom ────────────────────────────────

@login_required
def session_handover(request, session_id):
    from .models import MeasurementSession, WindowWarranty
    company = _company(request)
    session = get_object_or_404(MeasurementSession, pk=session_id, company=company)

    warranty, created = WindowWarranty.objects.get_or_create(
        session=session,
        defaults={'valid_years': 5}
    )
    if created:
        warranty.warranty_number = f"GAR-{timezone.now().year}-{warranty.pk:04d}"
        warranty.save(update_fields=['warranty_number'])

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'complete_handover':
            warranty.handover_date = timezone.now().date()
            warranty.handover_notes = request.POST.get('notes', '')
            if request.FILES.get('photo'):
                warranty.handover_photo = request.FILES['photo']
            warranty.save()
            messages.success(request, f'Primopredaja završena! Garancija: {warranty.warranty_number}')
            return redirect('stolarija:session_detail', session_id=session_id)

    return render(request, 'stolarija/handover.html', {
        'session': session,
        'warranty': warranty,
        'measurements': session.measurements.filter(confirmed=True),
        'page_title': f'Primopredaja — {session.address}',
    })


# ═══════════════════════════════════════════════════════════════════════════
# FAZA 8: Servis — garancija portal, servisni nalozi, pregledi
# ═══════════════════════════════════════════════════════════════════════════

def warranty_public(request, qr_token):
    """Kupac portal — provjera garancije putem QR koda. Bez login-a."""
    from .models import WindowWarranty
    warranty = get_object_or_404(WindowWarranty, qr_token=qr_token)
    session = warranty.session
    visits = warranty.service_visits.order_by('scheduled')

    now = timezone.now().date()
    if warranty.handover_date:
        expiry = warranty.handover_date.replace(
            year=warranty.handover_date.year + warranty.valid_years
        )
        is_valid = now <= expiry
        days_left = (expiry - now).days if is_valid else 0
    else:
        expiry = None
        is_valid = False
        days_left = 0

    return render(request, 'stolarija/warranty_public.html', {
        'warranty': warranty,
        'session': session,
        'visits': visits,
        'is_valid': is_valid,
        'expiry': expiry,
        'days_left': days_left,
        'measurements': session.measurements.filter(confirmed=True) if session else [],
    })


@login_required
def service_list(request):
    """Lista servisnih posjeta za firmu — dashboard za servis."""
    from .models import ServiceVisit
    company = _company(request)

    tab = request.GET.get('tab', 'upcoming')
    today = timezone.now().date()

    if tab == 'completed':
        visits = ServiceVisit.objects.filter(
            warranty__session__company=company,
            completed__isnull=False,
        ).select_related('warranty', 'technician').order_by('-completed')
    elif tab == 'overdue':
        visits = ServiceVisit.objects.filter(
            warranty__session__company=company,
            completed__isnull=True,
            scheduled__lt=today,
        ).select_related('warranty', 'technician').order_by('scheduled')
    else:
        visits = ServiceVisit.objects.filter(
            warranty__session__company=company,
            completed__isnull=True,
            scheduled__gte=today,
        ).select_related('warranty', 'technician').order_by('scheduled')

    stats = {
        'upcoming': ServiceVisit.objects.filter(
            warranty__session__company=company, completed__isnull=True, scheduled__gte=today
        ).count(),
        'overdue': ServiceVisit.objects.filter(
            warranty__session__company=company, completed__isnull=True, scheduled__lt=today
        ).count(),
        'completed': ServiceVisit.objects.filter(
            warranty__session__company=company, completed__isnull=False
        ).count(),
    }

    return render(request, 'stolarija/service_list.html', {
        'visits': visits,
        'tab': tab,
        'stats': stats,
        'page_title': 'Servisni pregledi',
    })


@login_required
def service_detail(request, visit_id):
    """Servisni nalog — field mode za montera."""
    from .models import ServiceVisit
    company = _company(request)
    visit = get_object_or_404(
        ServiceVisit, pk=visit_id, warranty__session__company=company
    )
    warranty = visit.warranty
    session = warranty.session

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'complete':
            visit.completed = timezone.now().date()
            visit.technician = request.user
            visit.notes = request.POST.get('notes', '').strip()
            if request.FILES.get('photo'):
                visit.photo = request.FILES['photo']
            cost = request.POST.get('cost', '').strip()
            if cost:
                visit.cost = Decimal(cost)
            visit.save()

            # Auto-schedule next visit (6 months or 12 months)
            from .models import ServiceVisit as SV
            from datetime import timedelta
            next_date = visit.completed + timedelta(days=180)
            if not SV.objects.filter(warranty=warranty, scheduled=next_date).exists():
                SV.objects.create(warranty=warranty, scheduled=next_date)

            try:
                from core.models import BookingSignature
                BookingSignature.log(request, 'update', target_obj=visit,
                    target_repr=f'Service completed: {warranty.warranty_number}',
                    changes={'completed': str(visit.completed), 'technician': str(request.user)})
            except Exception:
                pass

            messages.success(request, 'Servisni pregled završen. Sljedeći zakazan.')
            return redirect('stolarija:service_list')

        elif action == 'reschedule':
            from django.utils.dateparse import parse_date
            new_date = parse_date(request.POST.get('new_date', ''))
            if new_date:
                visit.scheduled = new_date
                visit.save(update_fields=['scheduled'])
                messages.success(request, f'Pregled pomaknut na {new_date.strftime("%d.%m.%Y")}.')
            return redirect('stolarija:service_detail', visit_id=visit.pk)

    measurements = session.measurements.filter(confirmed=True) if session else []

    return render(request, 'stolarija/service_detail.html', {
        'visit': visit,
        'warranty': warranty,
        'session': session,
        'measurements': measurements,
        'page_title': f'Servis — {warranty.warranty_number}',
    })


@login_required
def warranty_list(request):
    """Lista svih garancija za firmu."""
    from .models import WindowWarranty
    company = _company(request)
    today = timezone.now().date()

    warranties = WindowWarranty.objects.filter(
        session__company=company
    ).select_related('session').order_by('-issued_at')

    for w in warranties:
        if w.handover_date:
            expiry = w.handover_date.replace(year=w.handover_date.year + w.valid_years)
            w.is_valid = today <= expiry
            w.expiry_date = expiry
            w.next_service = w.service_visits.filter(
                completed__isnull=True
            ).order_by('scheduled').first()
        else:
            w.is_valid = False
            w.expiry_date = None
            w.next_service = None

    return render(request, 'stolarija/warranty_list.html', {
        'warranties': warranties,
        'page_title': 'Garancije',
    })
