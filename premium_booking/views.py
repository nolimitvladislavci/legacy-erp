import json
import time
from datetime import datetime, timedelta

from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from appointments.models import Appointment
from appointments.models import BookingResource as ERPResource
from companies.models import Company
from invoicing.models import Invoice, InvoiceItem
from partners.models import Partner

from .models import Addon, Booking, Resource


def index(request):
    resources = Resource.objects.filter(is_active=True)
    return render(request, 'premium_booking/index.html', {'resources': resources})


def detail(request, resource_id):
    resource = get_object_or_404(Resource, id=resource_id, is_active=True)
    addons = Addon.objects.filter(is_active=True)
    return render(request, 'premium_booking/detail.html', {'resource': resource, 'addons': addons})


def _check_rate_limit(request):
    """Simple IP-based rate limit: max 5 bookings per IP per hour."""
    from django.core.cache import cache
    ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
    if ',' in ip:
        ip = ip.split(',')[0].strip()
    key = f'booking_rate_{ip}'
    count = cache.get(key, 0)
    if count >= 5:
        return False
    cache.set(key, count + 1, 3600)
    return True


@require_POST
def api_submit(request):
    """
    Public booking API — secured:
    - CSRF via Django middleware (no @csrf_exempt)
    - Rate limiting: 5 bookings/IP/hour
    - select_for_update on overlap check (race-safe)
    - Input validation
    """
    if not _check_rate_limit(request):
        return JsonResponse({
            'status': 'error',
            'error': 'Previše zahtjeva. Pokušajte ponovno za nekoliko minuta.'
        }, status=429)

    try:
        data = json.loads(request.body)
    except (ValueError, json.JSONDecodeError):
        return JsonResponse({'status': 'error', 'error': 'Neispravan JSON.'}, status=400)

    # Input validation
    name = (data.get('name') or '').strip()
    email = (data.get('email') or '').strip()
    phone = (data.get('phone') or '').strip()
    resource_id = data.get('resource_id')
    date_str = data.get('date', '').strip()
    time_str = data.get('time', '').strip()

    if not name or not email or not resource_id or not date_str or not time_str:
        return JsonResponse({'status': 'error', 'error': 'Sva polja su obavezna.'}, status=400)

    if len(name) > 200 or len(email) > 254 or len(phone) > 20:
        return JsonResponse({'status': 'error', 'error': 'Prekoracena duljina polja.'}, status=400)

    # Basic email format check
    if '@' not in email or '.' not in email.split('@')[-1]:
        return JsonResponse({'status': 'error', 'error': 'Neispravna email adresa.'}, status=400)

    try:
        owner_company = Company.objects.first()
        if not owner_company:
            return JsonResponse({'status': 'error', 'error': 'Firma nije definirana.'}, status=400)

        try:
            res = Resource.objects.get(id=resource_id, is_active=True)
        except Resource.DoesNotExist:
            return JsonResponse({'status': 'error', 'error': 'Resurs ne postoji.'}, status=404)

        try:
            start = timezone.make_aware(
                datetime.strptime(f"{date_str} {time_str}", '%Y-%m-%d %H:%M')
            )
        except (ValueError, TypeError):
            return JsonResponse({'status': 'error', 'error': 'Neispravan format datuma/vremena.'}, status=400)

        # Don't allow bookings in the past
        if start < timezone.now():
            return JsonResponse({'status': 'error', 'error': 'Ne mozete rezervirati termin u proslosti.'}, status=400)

        end = start + timedelta(days=res.min_duration)

        # Atomic transaction with row-level locking
        with transaction.atomic():
            # Get or create ERP resource
            erp_res, _ = ERPResource.objects.get_or_create(
                name=res.name, defaults={'company': owner_company}
            )

            # Race-safe overlap check: lock overlapping rows first
            overlapping = Appointment.objects.select_for_update().filter(
                resource=erp_res,
                start_time__lt=end,
                end_time__gt=start,
                status__in=['scheduled', 'confirmed'],
            ).exists()

            if overlapping:
                return JsonResponse({
                    'status': 'error',
                    'error': 'Ovaj termin je u medjuvremenu zauzet. Molimo odaberite drugi.'
                }, status=409)

            # Resolve client
            client = Partner.objects.filter(email=email, company=owner_company).first()
            if not client:
                try:
                    dummy_oib = str(int(time.time())) + "1"
                    client = Partner.objects.create(
                        company=owner_company, name=name, email=email,
                        phone=phone, partner_type='KUPAC', oib=dummy_oib,
                    )
                except IntegrityError:
                    return JsonResponse({
                        'status': 'error', 'error': 'Greska prilikom registracije klijenta.'
                    }, status=400)

            # Create booking
            booking = Booking.objects.create(
                resource=res, guest_name=name, guest_email=email,
                guest_phone=phone, start_time=start, end_time=end,
                total_price=res.base_price,
            )

            # ERP Appointment
            Appointment.objects.create(
                title=f"PREMIUM: {res.name} - {name}",
                client=client, resource=erp_res,
                start_time=start, end_time=end,
                status='scheduled', color='#c9a84c',
                company=owner_company, whatsapp_number=phone,
            )

            # Invoice (predracun)
            invoice = Invoice.objects.create(
                doctype='P', number=f"PR-{int(time.time())}",
                client_name=client.name, client_email=email,
                date_issued=timezone.now(),
                subtotal=booking.total_price, total=booking.total_price,
                status='DRAFT',
                note=f"Automatska rezervacija s weba: {res.name}",
            )
            InvoiceItem.objects.create(
                invoice=invoice, description=f"Najam: {res.name}",
                quantity=1, unit_price=booking.total_price,
                total_price=booking.total_price,
            )

        # WhatsApp notification (outside transaction)
        if phone:
            try:
                from core.whatsapp_tasks import send_whatsapp_text_task
                msg = f"Poštovani {name}, Vaša rezervacija ({booking.booking_number}) je potvrđena."
                send_whatsapp_text_task.delay(phone, msg)
            except Exception:
                pass

        return JsonResponse({'status': 'success', 'booking_number': booking.booking_number})

    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Booking error: {e}", exc_info=True)
        return JsonResponse({'status': 'error', 'error': 'Interna greska servera.'}, status=500)
