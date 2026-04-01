import logging

from django.db import transaction

logger = logging.getLogger(__name__)
import json
from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_date
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from rest_framework import permissions, viewsets

from core.company_utils import get_user_company
from partners.models import Partner

from .forms import AppointmentForm
from .models import BRANCH_TYPES, Appointment, BookingResource, BookingService, WorkingHours
from .serializers import AppointmentSerializer


class AppointmentViewSet(viewsets.ModelViewSet):
    serializer_class = AppointmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        from core.company_utils import get_user_company
        company = get_user_company(self.request)
        return Appointment.objects.filter(company=company) if company else Appointment.objects.none()


# ── INTERNI KALENDAR ────────────────────────────────────────

@login_required
def calendar_view(request):
    company = get_user_company(request)
    clients = Partner.objects.filter(company=company, is_active=True).order_by("name") if company else Partner.objects.none()
    resources = BookingResource.objects.filter(company=company, is_active=True).order_by("name") if company else BookingResource.objects.none()
    services = BookingService.objects.filter(is_active=True, company=company).order_by("name") if company else BookingService.objects.none()
    users = __import__("django.contrib.auth", fromlist=["get_user_model"]).get_user_model().objects.filter(is_active=True)
    return render(request, "appointments/calendar.html", {
        "clients": clients,
        "resources": resources,
        "services": services,
        "users": users,
        "status_choices": Appointment.STATUS_CHOICES,
        "type_choices": Appointment.TYPE_CHOICES,
        "color_choices": [
            ("#3b82f6", "Plava"), ("#10b981", "Zelena"), ("#f59e0b", "Žuta"),
            ("#ef4444", "Crvena"), ("#8b5cf6", "Ljubičasta"), ("#c9a84c", "Zlatna"),
        ],
    })


@login_required
@require_GET
def api_events(request):
    start = request.GET.get("start")
    end = request.GET.get("end")
    company = get_user_company(request)
    qs = Appointment.objects.filter(company=company).select_related("client", "resource", "service") if company else Appointment.objects.none()
    if start:
        qs = qs.filter(end_time__gte=start)
    if end:
        qs = qs.filter(start_time__lte=end)
    events = []
    for app in qs:
        client_name = app.client.name if app.client else "Interno"
        events.append({
            "id": app.id,
            "title": f"{app.title} ({client_name})",
            "start": app.start_time.isoformat() if app.start_time else None,
            "end": app.end_time.isoformat() if app.end_time else None,
            "allDay": app.is_all_day,
            "backgroundColor": app.color or "#3b82f6",
            "borderColor": app.color or "#3b82f6",
            "extendedProps": {
                "type": app.get_appointment_type_display(),
                "status": app.get_status_display(),
                "status_code": app.status,
                "resource_id": app.resource_id,
                "client": client_name,
                "description": app.description,
            },
        })
    return JsonResponse(events, safe=False)


@login_required
def appointment_list(request):
    q = request.GET.get("q", "")
    status = request.GET.get("status", "")
    date_from = request.GET.get("date_from", "")
    date_to = request.GET.get("date_to", "")

    company = get_user_company(request)
    qs = Appointment.objects.filter(company=company).select_related("client", "resource", "employee").order_by("-start_time") if company else Appointment.objects.none()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(client__name__icontains=q) | Q(description__icontains=q))
    if status:
        qs = qs.filter(status=status)
    if date_from:
        qs = qs.filter(start_time__date__gte=date_from)
    if date_to:
        qs = qs.filter(start_time__date__lte=date_to)

    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get("page"))
    return render(request, "appointments/appointment_list.html", {
        "page_obj": page,
        "q": q, "status": status, "date_from": date_from, "date_to": date_to,
        "total": qs.count(),
        "status_choices": Appointment.STATUS_CHOICES,
    })


@login_required
def appointment_create(request):
    if request.method == "POST":
        form = AppointmentForm(request.POST)
        if form.is_valid():
            appt = form.save(commit=False)
            if not appt.employee_id:
                appt.employee = request.user
            if not appt.company_id:
                from core.company_utils import get_user_company
                company = get_user_company(request)
                if company:
                    appt.company = company
            appt.save()
            messages.success(request, "Termin kreiran.")
            return redirect("appointments:list")
        else:
            messages.error(request, str(form.errors))
    else:
        form = AppointmentForm()
    return render(request, "appointments/appointment_form.html", {
        "form": form,
        "clients": Partner.objects.filter(is_active=True, company=get_user_company(request)).order_by("name"),
        "resources": BookingResource.objects.filter(is_active=True, company=get_user_company(request)),
        "services": BookingService.objects.filter(is_active=True, company=get_user_company(request)),
        "users": __import__("django.contrib.auth", fromlist=["get_user_model"]).get_user_model().objects.filter(is_active=True),
        "status_choices": Appointment.STATUS_CHOICES,
        "type_choices": Appointment.TYPE_CHOICES,
        "action": "Novi termin",
    })


@login_required
def appointment_edit(request, pk):
    appt = get_object_or_404(Appointment, pk=pk)
    if request.method == "POST":
        form = AppointmentForm(request.POST, instance=appt)
        if form.is_valid():
            form.save()
            messages.success(request, "Termin ažuriran.")
            return redirect("appointments:list")
        else:
            messages.error(request, str(form.errors))
    else:
        form = AppointmentForm(instance=appt)
    return render(request, "appointments/appointment_form.html", {
        "form": form,
        "appt": appt,
        "clients": Partner.objects.filter(is_active=True, company=get_user_company(request)).order_by("name"),
        "resources": BookingResource.objects.filter(is_active=True, company=get_user_company(request)),
        "services": BookingService.objects.filter(is_active=True, company=get_user_company(request)),
        "users": __import__("django.contrib.auth", fromlist=["get_user_model"]).get_user_model().objects.filter(is_active=True),
        "status_choices": Appointment.STATUS_CHOICES,
        "type_choices": Appointment.TYPE_CHOICES,
        "action": "Uredi termin",
    })


@login_required
def appointment_delete(request, pk):
    appt = get_object_or_404(Appointment, pk=pk)
    if request.method == "POST":
        appt.delete()
        messages.success(request, "Termin obrisan.")
    return redirect("appointments:list")


@login_required
def appointment_status(request, pk):
    appt = get_object_or_404(Appointment, pk=pk)
    new_status = request.POST.get("status")
    if new_status in dict(Appointment.STATUS_CHOICES):
        old_st = appt.status
        appt.status = new_status
        appt.save()
        messages.success(request, f"Status promijenjen u: {appt.get_status_display()}")
        if new_status != old_st and new_status in ("confirmed", "cancelled", "completed", "no_show"):
            try:
                from appointments.tasks import notify_appointment_status_change
                notify_appointment_status_change.delay(appt.id, new_status)
            except Exception:
                pass
    return redirect("appointments:list")


@csrf_exempt
@login_required
def api_appointments(request, pk=None):
    if request.method in ["POST", "PUT"]:
        try:
            data = json.loads(request.body) if request.content_type == "application/json" else request.POST
        except Exception:
            data = request.POST
        if pk:
            appointment = get_object_or_404(Appointment, pk=pk)
            form = AppointmentForm(data, instance=appointment)
        else:
            form = AppointmentForm(data)
        if form.is_valid():
            appointment = form.save(commit=False)
            if not getattr(appointment, "employee_id", None):
                appointment.employee = request.user
            appointment.save()
            return JsonResponse({"status": "success", "id": appointment.id})
        return JsonResponse({"status": "error", "errors": form.errors}, status=400)
    elif request.method == "DELETE" and pk:
        appointment = get_object_or_404(Appointment, pk=pk)
        appointment.delete()
        return JsonResponse({"status": "success"})
    return JsonResponse({"status": "invalid method"}, status=405)


# ── JAVNI BOOKING PORTAL ────────────────────────────────────

def public_booking_index(request):
    from companies.models import Company
    platform_company = Company.objects.filter(is_platform_owner=True).first()
    services = BookingService.objects.filter(is_active=True, company=platform_company) if platform_company else BookingService.objects.none()
    return render(request, "appointments/public/index.html", {"services": services})


def public_booking_calendar(request, service_id):
    service = get_object_or_404(BookingService, id=service_id, is_active=True)
    return render(request, "appointments/public/calendar.html", {"service": service})


@require_GET
def api_available_slots(request):
    date_str = request.GET.get("date")
    service_id = request.GET.get("service_id")
    if not date_str or not service_id:
        return JsonResponse({"error": "Nedostaju parametri"}, status=400)
    target_date = parse_date(date_str)
    if not target_date or target_date < datetime.now().date():
        return JsonResponse({"available": [], "unavailable": [], "slots": []})
    service = get_object_or_404(BookingService, id=service_id)
    weekday = target_date.weekday()
    resources = BookingResource.objects.filter(resource_type=service.resource_type, is_active=True, company=service.company)
    available_slots = set()
    unavailable_slots = set()
    service_duration = service.duration.total_seconds() / 60
    for resource in resources:
        wh = WorkingHours.objects.filter(resource=resource, day_of_week=weekday, is_day_off=False).first()
        if not wh:
            continue
        start_dt = datetime.combine(target_date, wh.start_time)
        end_dt = datetime.combine(target_date, wh.end_time)
        existing_apps = list(Appointment.objects.filter(
            resource=resource, start_time__date=target_date, status__in=["scheduled", "confirmed"]
        ))
        current_slot = start_dt
        while current_slot + timedelta(minutes=service_duration) <= end_dt:
            slot_end = current_slot + timedelta(minutes=service_duration)
            overlap = any(
                current_slot < a.end_time.replace(tzinfo=None) and slot_end > a.start_time.replace(tzinfo=None)
                for a in existing_apps
            )
            if target_date == datetime.now().date() and current_slot.time() < datetime.now().time():
                overlap = True
            slot_str = current_slot.strftime("%H:%M")
            if not overlap:
                available_slots.add(slot_str)
            else:
                unavailable_slots.add(slot_str)
            current_slot += timedelta(minutes=service.slot_duration_minutes)
    avail = sorted(list(available_slots))
    unavail = sorted(list(unavailable_slots - available_slots))
    return JsonResponse({"available": avail, "unavailable": unavail, "slots": avail})


@csrf_exempt
@transaction.atomic
def api_submit_public_booking(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)
    try:
        data = json.loads(request.body)

        # ── VALIDACIJA ────────────────────────────────────────────────────────
        import re as _re
        errors = {}

        name = (data.get("name") or "").strip()
        phone = (data.get("phone") or "").strip()
        email = (data.get("email") or "").strip()

        # Ime: min 3 znaka, mora imati barem 2 rijeci (ime + prezime)
        if len(name) < 3:
            errors["name"] = "Ime mora imati najmanje 3 znaka."
        elif len(name.split()) < 2:
            errors["name"] = "Unesite ime i prezime."

        # Telefon: min 8 znamenki (bez razmaka i +)
        phone_digits = _re.sub(r"[^0-9]", "", phone)
        if len(phone_digits) < 8:
            errors["phone"] = "Unesite ispravan broj telefona (min. 8 znamenki)."

        # Email: ako je upisan, mora biti valjan
        if email and not _re.match(r"^[^@]+@[^@]+\.[^@]+$", email):
            errors["email"] = "Email adresa nije ispravna."

        # Datum: ne smije biti u prošlosti
        from django.utils import timezone as _tz
        target_date = parse_date(data.get("date", ""))
        if not target_date:
            errors["date"] = "Datum nije ispravan."
        elif target_date < _tz.localdate():
            errors["date"] = "Ne možete rezervirati termin u prošlosti."

        if errors:
            return JsonResponse({"error": "Greška u unosu.", "fields": errors}, status=400)
        # ─────────────────────────────────────────────────────────────────────

        service = get_object_or_404(BookingService, id=data["service_id"])
        start_time = datetime.strptime(f"{data['date']} {data['time']}", "%Y-%m-%d %H:%M")
        end_time = start_time + timedelta(minutes=service.duration.total_seconds() / 60)
        # Klijent — gost ili prijavljeni korisnik (validacija je gore odradena)
        email = email or (request.user.email if request.user.is_authenticated else "")
        name  = name  or (request.user.get_full_name() or request.user.username if request.user.is_authenticated else "Gost")
        # Get company from the booked service
        import uuid as _uuid

        from companies.models import Company
        booking_company = service.company or Company.objects.filter(is_platform_owner=True).first() or Company.objects.first()
        # Try existing partner by email first, then create
        client = Partner.objects.filter(email=email, company=booking_company).first()
        if not client:
            client = Partner.objects.filter(email=email).first()
        if not client:
            # Generate unique placeholder OIB to avoid unique_together constraint
            placeholder_oib = f"B{_uuid.uuid4().hex[:10].upper()}"
            client = Partner(
                name=name, email=email, company=booking_company,
                phone=data.get("phone", ""), partner_type="KUPAC",
                oib=placeholder_oib,
            )
            client.save()
        resources = BookingResource.objects.filter(resource_type=service.resource_type, is_active=True, company=booking_company)
        assigned_resource = None
        for resource in resources:
            if not Appointment.objects.filter(
                resource=resource, start_time__lt=end_time, end_time__gt=start_time,
                status__in=["scheduled", "confirmed"]
            ).exists():
                assigned_resource = resource
                break
        if not assigned_resource:
            return JsonResponse({"error": "Termin je zauzet. Odaberite drugi."}, status=400)
        appointment = Appointment.objects.create(
            company=booking_company,
            title=f"Online: {service.name}", client=client, service=service,
            resource=assigned_resource, start_time=start_time, end_time=end_time,
            appointment_type="service", status="scheduled", color="#10b981",
            total_price=service.price or 0,
            payment_method=data.get("payment_method", "invoice"),
            whatsapp_number=data.get("phone", "") or data.get("whatsapp", ""),
        )
        # ── Potvrda emailom ───────────────────────────────────────────────────
        try:
            from django.conf import settings

            from core.email_tasks import send_email_task
            dt_fmt = start_time.strftime("%d.%m.%Y u %H:%M")
            subject = f"Potvrda rezervacije — {service.name}"
            body = (
                f"Poštovani/a {name},\n\n"
                f"Vaša rezervacija je uspješno kreirana.\n\n"
                f"  Usluga:  {service.name}\n"
                f"  Termin:  {dt_fmt}\n"
                f"  Trajanje:{int(service.duration.total_seconds()//60)} min\n"
            )
            if service.price:
                body += f"  Cijena:  {service.price} EUR\n"
            body += (
                f"\nAko trebate otkazati ili promijeniti termin, kontaktirajte nas.\n\n"
                f"Hvala na povjerenju!\n"
            )
            send_email_task.delay(
                subject, body,
                getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com'),
                [email],
                # async via celery
            )
        except Exception:
            pass
        ics_url = f"/appointments/booking/ics/{appointment.id}/"
        # Notify staff about new booking
        try:
            from django.contrib.auth.models import User as _U

            from notifications.services import notify_bulk
            staff = _U.objects.filter(is_staff=True)
            notify_bulk(
                recipients=staff,
                notification_type='appointment_confirmed',
                title='Nova online rezervacija',
                message=f'{service.name} - {start_time.strftime("%d.%m.%Y %H:%M")} ({name})',
                url='/appointments/',
            )
        except Exception:
            pass
        # WhatsApp potvrda s detaljima + tracking link
        wa_phone = data.get("phone", "") or appointment.whatsapp_number
        if wa_phone:
            try:
                from core.whatsapp_tasks import send_whatsapp_text_task
                dt_fmt = start_time.strftime("%d.%m.%Y u %H:%M")
                track_url = "https://limit-connect.com/appointments/booking/track/%s/" % appointment.id
                wa_msg = (
                    "Rezervacija potvrdjena!\n\n"
                    "Usluga: %s\n"
                    "Termin: %s\n"
                    "Trajanje: %d min\n"
                ) % (service.name, dt_fmt, int(service.duration.total_seconds() // 60))
                if service.price:
                    wa_msg += "Cijena: %s EUR\n" % service.price
                wa_msg += (
                    "\nPratite status:\n%s\n\n"
                    "Za otkazivanje odgovorite OTKAZI.\n"
                    "Hvala na povjerenju!"
                ) % track_url
                send_whatsapp_text_task.delay(wa_phone, wa_msg)
                appointment.whatsapp_number = wa_phone
                appointment.save(update_fields=["whatsapp_number"])
            except Exception:
                pass
        return JsonResponse({"status": "success", "booking_id": appointment.id, "total_price": float(appointment.total_price or 0), "ics_url": ics_url})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@require_GET




# ════════════════════════════════════════════════════════════
# BAKING FLOW — Prijemni formular + status + limeni broj
# ════════════════════════════════════════════════════════════

@login_required
def baking_board(request):
    """Tabla za pekaru — sve aktivne narudzbe za pecenje."""
    from core.company_utils import get_user_company
    company = get_user_company(request)
    if not company:
        from django.shortcuts import redirect
        return redirect('/')
    today = timezone.now().date()
    orders = Appointment.objects.filter(
        company=company,
        service__branch_type='bakery',
        start_time__date__gte=today,
        status__in=['scheduled', 'confirmed', 'in_progress'],
    ).select_related('service', 'client', 'resource').order_by('start_time')

    completed_today = Appointment.objects.filter(
        company=company,
        service__branch_type='bakery',
        start_time__date=today,
        status='completed',
    ).count()

    return render(request, 'appointments/baking_board.html', {
        'orders': orders,
        'completed_today': completed_today,
    })


@login_required
def baking_intake(request, pk):
    """Prijemni formular — kupac donosi sirovinu."""
    appointment = get_object_or_404(Appointment, pk=pk)
    from django.contrib import messages

    if request.method == 'POST':
        appointment.token_number = int(request.POST.get('token_number', 0))
        appointment.weight_kg = request.POST.get('weight_kg', 0) or 0
        salt_val = request.POST.get('should_salt', '')
        if salt_val == 'yes':
            appointment.should_salt = True
        elif salt_val == 'no':
            appointment.should_salt = False
        else:
            appointment.should_salt = None
        appointment.intake_notes = request.POST.get('intake_notes', '')
        appointment.intake_at = timezone.now()
        appointment.intake_by = request.user
        appointment.status = 'confirmed'
        appointment.save()

        # WhatsApp — sirovinu zaprimili
        _send_status_wa(appointment, 'Zaprimljeno! Limeni broj: %d. Javimo vam kad bude gotovo.' % appointment.token_number)

        messages.success(request, 'Zaprimljeno — limeni broj %d' % appointment.token_number)
        return redirect('appointments:baking_board')

    # Suggest next token number
    from django.db.models import Max
    last_token = Appointment.objects.filter(
        company=appointment.company,
        start_time__date=timezone.now().date(),
        token_number__gt=0,
    ).aggregate(Max('token_number'))['token_number__max'] or 0

    needs_salt = appointment.service.name.lower() in ['usluzno pecenje janjetine', 'usluzno pecenje odojka',
                                                        'pecenje janjetine', 'pecenje odojka', 'janjetina', 'odojak']

    return render(request, 'appointments/baking_intake.html', {
        'appointment': appointment,
        'next_token': last_token + 1,
        'needs_salt': needs_salt,
    })


@login_required
def baking_status_update(request, pk):
    """Promjena statusa pecenja + WA obavijest."""
    appointment = get_object_or_404(Appointment, pk=pk)
    new_status = request.POST.get('status', '')
    from django.contrib import messages

    status_messages = {
        'in_progress': ('U peci! Pratite status na linku.', 'U pecenju'),
        'completed': ('Gotovo! Mozete doci po preuzimanje. Limeni broj: %d.' % appointment.token_number, 'Gotovo za preuzimanje'),
        'picked_up': ('Hvala na posjeti! Dodjite opet.', 'Preuzeto — zavrseno'),
    }

    if new_status == 'picked_up':
        appointment.status = 'completed'
        appointment.picked_up_at = timezone.now()
    elif new_status in ('in_progress', 'completed'):
        appointment.status = new_status
        if new_status == 'completed':
            appointment.ready_at = timezone.now()

    appointment.save()

    wa_msg, flash_msg = status_messages.get(new_status, ('', 'Status azuriran'))
    if wa_msg:
        _send_status_wa(appointment, wa_msg)

    messages.success(request, flash_msg)
    return redirect('appointments:baking_board')


def _send_status_wa(appointment, message):
    """Posalji WhatsApp status update kupcu."""
    phone = appointment.whatsapp_number
    if not phone:
        return
    try:
        from core.whatsapp_tasks import send_whatsapp_text_task
        track_url = 'https://limit-connect.com/appointments/booking/track/%d/' % appointment.pk
        full_msg = '%s\n\nPratite: %s' % (message, track_url)
        send_whatsapp_text_task.delay(phone, full_msg)
    except Exception:
        pass


def booking_track(request, pk):
    """Public tracking page za rezervaciju — bez login-a."""
    appointment = get_object_or_404(Appointment, pk=pk)
    return render(request, 'appointments/public/booking_track.html', {
        'appointment': appointment,
    })

def api_booking_auth_check(request):
    """Vraća auth status i basic info o korisniku"""
    if request.user.is_authenticated:
        return JsonResponse({
            "authenticated": True,
            "username": request.user.username,
            "email": request.user.email,
            "full_name": request.user.get_full_name() or request.user.username,
        })
    return JsonResponse({"authenticated": False})


@csrf_exempt
def api_booking_register(request):
    """AJAX registracija novog korisnika za booking portal"""
    if request.method != 'POST':
        return JsonResponse({"error": "Invalid method"}, status=405)
    try:
        from django.contrib.auth import get_user_model, login
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError
        User = get_user_model()
        data = json.loads(request.body)
        username  = data.get('username', '').strip()
        email     = data.get('email', '').strip()
        password  = data.get('password', '')
        first     = data.get('first_name', '').strip()
        last      = data.get('last_name', '').strip()

        if not username or not password:
            return JsonResponse({"success": False, "error": "Korisničko ime i lozinka su obavezni."})
        if User.objects.filter(username=username).exists():
            return JsonResponse({"success": False, "error": "Korisničko ime je zauzeto."})
        if email and User.objects.filter(email=email).exists():
            return JsonResponse({"success": False, "error": "Email je već registriran."})
        # Password validation
        try:
            validate_password(password)
        except ValidationError as ve:
            return JsonResponse({"success": False, "error": " ".join(ve.messages)})

        user = User.objects.create_user(
            username=username, email=email, password=password,
            first_name=first, last_name=last
        )
        login(request, user)
        return JsonResponse({
            "success": True,
            "email": user.email,
            "full_name": user.get_full_name() or user.username
        })
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


# ── ICS EXPORT ────────────────────────────────────────────────

def download_ics(request, appointment_id):
    """Download .ics file for an appointment."""
    appointment = get_object_or_404(Appointment, id=appointment_id)
    from .ics_utils import generate_ics
    ics_content = generate_ics(appointment)
    response = HttpResponse(ics_content, content_type="text/calendar; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="termin-{appointment.id}.ics"'
    return response



# ── TJEDNI RASPORED SLOBODNIH TERMINA ──────────────────────────────────────────

@require_GET
def api_slots_week(request):
    service_id = request.GET.get("service_id")
    week_start_str = request.GET.get("week_start")
    if not service_id:
        return JsonResponse({"error": "service_id obavezan"}, status=400)
    service = get_object_or_404(BookingService, id=service_id, is_active=True)
    step = service.slot_duration_minutes
    dur  = service.duration_minutes
    from datetime import timedelta
    today = datetime.now().date()
    now_time = datetime.now().time()
    if week_start_str:
        try:
            week_start = parse_date(week_start_str)
        except Exception:
            week_start = today - timedelta(days=today.weekday())
    else:
        week_start = today - timedelta(days=today.weekday())
    DAYS_HR = ["Pon", "Uto", "Sri", "Čet", "Pet", "Sub", "Ned"]
    DAYS_FULL = ["Ponedjeljak", "Utorak", "Srijeda", "Četvrtak", "Petak", "Subota", "Nedjelja"]
    resources = BookingResource.objects.filter(resource_type=service.resource_type, is_active=True, company=service.company)
    days_data = []
    for day_offset in range(7):
        target_date = week_start + timedelta(days=day_offset)
        weekday = target_date.weekday()
        is_today = (target_date == today)
        is_past  = (target_date < today)
        all_available = set()
        all_unavailable = set()
        for resource in resources:
            wh = WorkingHours.objects.filter(
                resource=resource, day_of_week=weekday, is_day_off=False
            ).first()
            if not wh:
                continue
            start_dt = datetime.combine(target_date, wh.start_time)
            end_dt   = datetime.combine(target_date, wh.end_time)
            existing = list(Appointment.objects.filter(
                resource=resource, start_time__date=target_date,
                status__in=["scheduled", "confirmed"]
            ))
            current = start_dt
            while current + timedelta(minutes=dur) <= end_dt:
                slot_end = current + timedelta(minutes=dur)
                overlap = any(
                    current < a.end_time.replace(tzinfo=None) and slot_end > a.start_time.replace(tzinfo=None)
                    for a in existing
                )
                slot_str = current.strftime("%H:%M")
                if is_today and current.time() <= now_time:
                    overlap = True
                if not overlap:
                    all_available.add(slot_str)
                else:
                    all_unavailable.add(slot_str)
                current += timedelta(minutes=step)
        avail = sorted(all_available)
        unavail = sorted(all_unavailable - all_available)
        all_slots = sorted(set(avail) | set(unavail))
        slots = [{"time": s, "available": s in avail, "label": s} for s in all_slots]
        days_data.append({
            "date": target_date.strftime("%Y-%m-%d"),
            "weekday_short": DAYS_HR[weekday],
            "weekday_full": DAYS_FULL[weekday],
            "is_today": is_today,
            "is_past": is_past,
            "slots": slots,
            "has_available": len(avail) > 0,
        })
    return JsonResponse({
        "service_id": service.id,
        "service_name": service.name,
        "step_minutes": step,
        "duration_min": dur,
        "week_start": week_start.strftime("%Y-%m-%d"),
        "days": days_data,
    })


# ── BOOKING WIZARD (javni) ──────────────────────────────────────────

def public_booking_wizard(request, service_id):
    service = get_object_or_404(BookingService, id=service_id, is_active=True)
    return render(request, "appointments/public/wizard.html", {
        "service": service,
    })


# ── KLIJENTSKI KARTON (FASCIKL) ──────────────────────────────────────────

@login_required
def dossier_list(request):
    from core.company_utils import get_user_company
    company = get_user_company(request)
    qs = __import__("appointments.models", fromlist=["ClientDossier"]).ClientDossier.objects.select_related("client").filter(company=company)
    q = request.GET.get("q", "")
    if q:
        from django.db.models import Q as _Q
        qs = qs.filter(_Q(client__name__icontains=q))
    from django.core.paginator import Paginator as _Pag
    page = _Pag(qs, 30).get_page(request.GET.get("page"))
    return render(request, "appointments/dossier_list.html", {"page_obj": page, "q": q})


@login_required
def dossier_detail(request, partner_id):
    from appointments.models import ClientDossier
    from appointments.models import DossierEntry as DE
    from core.company_utils import get_user_company
    from partners.models import Partner
    client = get_object_or_404(Partner, pk=partner_id)
    company = get_user_company(request)
    dossier, created = ClientDossier.objects.get_or_create(
        company=company, client=client,
        defaults={"created_by": request.user}
    )
    entries = dossier.entries.select_related("appointment", "created_by").all()
    recent_appointments = Appointment.objects.filter(client=client).order_by("-start_time")[:10]
    entry_type_filter = request.GET.get("type", "")
    if entry_type_filter:
        entries = entries.filter(entry_type=entry_type_filter)
    return render(request, "appointments/dossier_detail.html", {
        "dossier":             dossier,
        "client":              client,
        "entries":             entries,
        "recent_appointments": recent_appointments,
        "entry_type_filter":   entry_type_filter,
        "entry_types":         DE.ENTRY_TYPES,
        "created":             created,
    })


@login_required
def dossier_entry_create(request, partner_id):
    from appointments.models import ClientDossier
    from appointments.models import DossierEntry as DE
    from core.company_utils import get_user_company
    from partners.models import Partner
    client  = get_object_or_404(Partner, pk=partner_id)
    company = get_user_company(request)
    dossier, _ = ClientDossier.objects.get_or_create(
        company=company, client=client,
        defaults={"created_by": request.user}
    )
    if request.method == "POST":
        import json as _json
        entry_type = request.POST.get("entry_type", "note")
        title      = request.POST.get("title", "").strip()
        content    = request.POST.get("content", "")
        sd_raw     = request.POST.get("structured_data", "{}")
        appt_id    = request.POST.get("appointment_id")
        try:
            structured = _json.loads(sd_raw) if sd_raw else {}
        except Exception:
            structured = {}
        entry = DE(
            dossier=dossier,
            entry_type=entry_type,
            title=title or "{}".format(dict(DE.ENTRY_TYPES).get(entry_type, "Unos")),
            content=content,
            structured_data=structured,
            created_by=request.user,
        )
        if appt_id:
            try:
                entry.appointment_id = int(appt_id)
            except Exception:
                pass
        if request.FILES.get("file"):
            entry.file = request.FILES["file"]
        entry.save()
        messages.success(request, "Unos u karton spremljen.")
        return redirect("appointments:dossier_detail", partner_id=partner_id)
    appointment_id = request.GET.get("appointment_id")
    prefill_type   = request.GET.get("type", "note")
    return render(request, "appointments/dossier_entry_form.html", {
        "dossier":        dossier,
        "client":         client,
        "entry_types":    DE.ENTRY_TYPES,
        "entry_type_icons": DE.ENTRY_ICONS,
        "prefill_type":   prefill_type,
        "appointment_id": appointment_id,
        "appointments":   Appointment.objects.filter(client=client).order_by("-start_time")[:20],
    })


@login_required
def dossier_entry_edit(request, partner_id, entry_id):
    from appointments.models import ClientDossier
    from appointments.models import DossierEntry as DE
    from core.company_utils import get_user_company
    from partners.models import Partner
    client  = get_object_or_404(Partner, pk=partner_id)
    company = get_user_company(request)
    dossier = get_object_or_404(ClientDossier, company=company, client=client)
    entry   = get_object_or_404(DE, pk=entry_id, dossier=dossier)
    if request.method == "POST":
        import json as _json
        entry.entry_type = request.POST.get("entry_type", entry.entry_type)
        entry.title      = request.POST.get("title", entry.title)
        entry.content    = request.POST.get("content", entry.content)
        sd_raw = request.POST.get("structured_data", "{}")
        try:
            entry.structured_data = _json.loads(sd_raw)
        except Exception:
            pass
        if request.FILES.get("file"):
            entry.file = request.FILES["file"]
        entry.save()
        messages.success(request, "Unos ažuriran.")
        return redirect("appointments:dossier_detail", partner_id=partner_id)
    import json as _json
    return render(request, "appointments/dossier_entry_form.html", {
        "dossier":        dossier,
        "client":         client,
        "entry":          entry,
        "entry_types":    DE.ENTRY_TYPES,
        "entry_type_icons": DE.ENTRY_ICONS,
        "prefill_type":   entry.entry_type,
        "sd_json":        _json.dumps(entry.structured_data, ensure_ascii=False),
        "appointments":   Appointment.objects.filter(client=client).order_by("-start_time")[:20],
    })


@login_required
@require_POST
def dossier_entry_delete(request, partner_id, entry_id):
    from appointments.models import ClientDossier
    from appointments.models import DossierEntry as DE
    from core.company_utils import get_user_company
    from partners.models import Partner
    client  = get_object_or_404(Partner, pk=partner_id)
    dossier = get_object_or_404(ClientDossier, company=get_user_company(request), client=client)
    entry   = get_object_or_404(DE, pk=entry_id, dossier=dossier)
    entry.delete()
    messages.success(request, "Unos obrisan.")
    return redirect("appointments:dossier_detail", partner_id=partner_id)


@login_required
def service_list(request):
    company = get_user_company(request)
    if company:
        services = BookingService.objects.filter(is_active=True, company=company).order_by("branch_type", "name")
    else:
        services = BookingService.objects.none()
    return render(request, "appointments/service_list.html", {
        "services": services,
        "branch_types": dict(BRANCH_TYPES),
    })


@login_required
def service_create(request):
    from .forms import BookingServiceForm
    if request.method == "POST":
        form = BookingServiceForm(request.POST)
        if form.is_valid():
            svc = form.save(commit=False)
            if not svc.company_id:
                svc.company = get_user_company(request)
            svc.save()
            messages.success(request, "Usluga kreirana: " + svc.name)
            return redirect("appointments:service_list")
        else:
            messages.error(request, str(form.errors))
    else:
        form = BookingServiceForm()
    return render(request, "appointments/service_form.html", {
        "form": form, "action": "Nova usluga",
    })


@login_required
def service_edit(request, pk):
    from .forms import BookingServiceForm
    svc = get_object_or_404(BookingService, pk=pk)
    if request.method == "POST":
        form = BookingServiceForm(request.POST, instance=svc)
        if form.is_valid():
            form.save()
            messages.success(request, "Usluga ažurirana: " + svc.name)
            return redirect("appointments:service_list")
        else:
            messages.error(request, str(form.errors))
    else:
        form = BookingServiceForm(instance=svc)
    return render(request, "appointments/service_form.html", {
        "form": form, "svc": svc, "action": "Uredi uslugu",
    })


# ── TJEDNI RASPORED SLOBODNIH TERMINA ──────────────────────────────────────────

@require_GET
def api_slots_week(request):
    service_id = request.GET.get("service_id")
    week_start_str = request.GET.get("week_start")
    if not service_id:
        return JsonResponse({"error": "service_id obavezan"}, status=400)
    service = get_object_or_404(BookingService, id=service_id, is_active=True)
    step = service.slot_duration_minutes
    dur  = service.duration_minutes
    from datetime import date, timedelta
    today = datetime.now().date()
    now_time = datetime.now().time()
    if week_start_str:
        try:
            week_start = parse_date(week_start_str)
        except Exception:
            week_start = today - timedelta(days=today.weekday())
    else:
        week_start = today - timedelta(days=today.weekday())
    DAYS_HR = ["Pon", "Uto", "Sri", "Čet", "Pet", "Sub", "Ned"]
    DAYS_FULL = ["Ponedjeljak", "Utorak", "Srijeda", "Četvrtak", "Petak", "Subota", "Nedjelja"]
    resources = BookingResource.objects.filter(resource_type=service.resource_type, is_active=True, company=service.company)
    days_data = []
    for day_offset in range(7):
        target_date = week_start + timedelta(days=day_offset)
        weekday = target_date.weekday()
        is_today = (target_date == today)
        is_past  = (target_date < today)
        all_available = set()
        all_unavailable = set()
        for resource in resources:
            wh = WorkingHours.objects.filter(
                resource=resource, day_of_week=weekday, is_day_off=False
            ).first()
            if not wh:
                continue
            start_dt = datetime.combine(target_date, wh.start_time)
            end_dt   = datetime.combine(target_date, wh.end_time)
            existing = list(Appointment.objects.filter(
                resource=resource, start_time__date=target_date,
                status__in=["scheduled", "confirmed"]
            ))
            current = start_dt
            while current + timedelta(minutes=dur) <= end_dt:
                slot_end = current + timedelta(minutes=dur)
                overlap = any(
                    current < a.end_time.replace(tzinfo=None) and slot_end > a.start_time.replace(tzinfo=None)
                    for a in existing
                )
                slot_str = current.strftime("%H:%M")
                if is_today and current.time() <= now_time:
                    overlap = True
                if not overlap:
                    all_available.add(slot_str)
                else:
                    all_unavailable.add(slot_str)
                current += timedelta(minutes=step)
        avail = sorted(all_available)
        unavail = sorted(all_unavailable - all_available)
        all_slots = sorted(set(avail) | set(unavail))
        slots = [{"time": s, "available": s in avail, "label": s} for s in all_slots]
        days_data.append({
            "date": target_date.strftime("%Y-%m-%d"),
            "weekday_short": DAYS_HR[weekday],
            "weekday_full": DAYS_FULL[weekday],
            "is_today": is_today,
            "is_past": is_past,
            "slots": slots,
            "has_available": len(avail) > 0,
        })
    return JsonResponse({
        "service_id": service.id,
        "service_name": service.name,
        "step_minutes": step,
        "duration_min": dur,
        "week_start": week_start.strftime("%Y-%m-%d"),
        "days": days_data,
    })


# ── BOOKING WIZARD (javni) ──────────────────────────────────────────

def public_booking_wizard(request, service_id):
    service = get_object_or_404(BookingService, id=service_id, is_active=True)
    return render(request, "appointments/public/wizard.html", {
        "service": service,
    })


# ── KLIJENTSKI KARTON (FASCIKL) ──────────────────────────────────────────

@login_required
def dossier_list(request):
    from core.company_utils import get_user_company
    company = get_user_company(request)
    qs = __import__("appointments.models", fromlist=["ClientDossier"]).ClientDossier.objects.select_related("client").filter(company=company)
    q = request.GET.get("q", "")
    if q:
        from django.db.models import Q as _Q
        qs = qs.filter(_Q(client__name__icontains=q))
    from django.core.paginator import Paginator as _Pag
    page = _Pag(qs, 30).get_page(request.GET.get("page"))
    return render(request, "appointments/dossier_list.html", {"page_obj": page, "q": q})


@login_required
def dossier_detail(request, partner_id):
    from appointments.models import ClientDossier, DossierEntry as DE
    from partners.models import Partner
    from core.company_utils import get_user_company
    client = get_object_or_404(Partner, pk=partner_id)
    company = get_user_company(request)
    dossier, created = ClientDossier.objects.get_or_create(
        company=company, client=client,
        defaults={"created_by": request.user}
    )
    entries = dossier.entries.select_related("appointment", "created_by").all()
    recent_appointments = Appointment.objects.filter(client=client).order_by("-start_time")[:10]
    entry_type_filter = request.GET.get("type", "")
    if entry_type_filter:
        entries = entries.filter(entry_type=entry_type_filter)
    return render(request, "appointments/dossier_detail.html", {
        "dossier":             dossier,
        "client":              client,
        "entries":             entries,
        "recent_appointments": recent_appointments,
        "entry_type_filter":   entry_type_filter,
        "entry_types":         DE.ENTRY_TYPES,
        "created":             created,
    })


@login_required
def dossier_entry_create(request, partner_id):
    from appointments.models import ClientDossier, DossierEntry as DE
    from partners.models import Partner
    from core.company_utils import get_user_company
    client  = get_object_or_404(Partner, pk=partner_id)
    company = get_user_company(request)
    dossier, _ = ClientDossier.objects.get_or_create(
        company=company, client=client,
        defaults={"created_by": request.user}
    )
    if request.method == "POST":
        import json as _json
        entry_type = request.POST.get("entry_type", "note")
        title      = request.POST.get("title", "").strip()
        content    = request.POST.get("content", "")
        sd_raw     = request.POST.get("structured_data", "{}")
        appt_id    = request.POST.get("appointment_id")
        try:
            structured = _json.loads(sd_raw) if sd_raw else {}
        except Exception:
            structured = {}
        entry = DE(
            dossier=dossier,
            entry_type=entry_type,
            title=title or "{}".format(dict(DE.ENTRY_TYPES).get(entry_type, "Unos")),
            content=content,
            structured_data=structured,
            created_by=request.user,
        )
        if appt_id:
            try:
                entry.appointment_id = int(appt_id)
            except Exception:
                pass
        if request.FILES.get("file"):
            entry.file = request.FILES["file"]
        entry.save()
        messages.success(request, "Unos u karton spremljen.")
        return redirect("appointments:dossier_detail", partner_id=partner_id)
    appointment_id = request.GET.get("appointment_id")
    prefill_type   = request.GET.get("type", "note")
    return render(request, "appointments/dossier_entry_form.html", {
        "dossier":        dossier,
        "client":         client,
        "entry_types":    DE.ENTRY_TYPES,
        "entry_type_icons": DE.ENTRY_ICONS,
        "prefill_type":   prefill_type,
        "appointment_id": appointment_id,
        "appointments":   Appointment.objects.filter(client=client).order_by("-start_time")[:20],
    })


@login_required
def dossier_entry_edit(request, partner_id, entry_id):
    from appointments.models import ClientDossier, DossierEntry as DE
    from partners.models import Partner
    from core.company_utils import get_user_company
    client  = get_object_or_404(Partner, pk=partner_id)
    company = get_user_company(request)
    dossier = get_object_or_404(ClientDossier, company=company, client=client)
    entry   = get_object_or_404(DE, pk=entry_id, dossier=dossier)
    if request.method == "POST":
        import json as _json
        entry.entry_type = request.POST.get("entry_type", entry.entry_type)
        entry.title      = request.POST.get("title", entry.title)
        entry.content    = request.POST.get("content", entry.content)
        sd_raw = request.POST.get("structured_data", "{}")
        try:
            entry.structured_data = _json.loads(sd_raw)
        except Exception:
            pass
        if request.FILES.get("file"):
            entry.file = request.FILES["file"]
        entry.save()
        messages.success(request, "Unos ažuriran.")
        return redirect("appointments:dossier_detail", partner_id=partner_id)
    import json as _json
    return render(request, "appointments/dossier_entry_form.html", {
        "dossier":        dossier,
        "client":         client,
        "entry":          entry,
        "entry_types":    DE.ENTRY_TYPES,
        "entry_type_icons": DE.ENTRY_ICONS,
        "prefill_type":   entry.entry_type,
        "sd_json":        _json.dumps(entry.structured_data, ensure_ascii=False),
        "appointments":   Appointment.objects.filter(client=client).order_by("-start_time")[:20],
    })


@login_required
@require_POST
def dossier_entry_delete(request, partner_id, entry_id):
    from appointments.models import ClientDossier, DossierEntry as DE
    from partners.models import Partner
    from core.company_utils import get_user_company
    client  = get_object_or_404(Partner, pk=partner_id)
    dossier = get_object_or_404(ClientDossier, company=get_user_company(request), client=client)
    entry   = get_object_or_404(DE, pk=entry_id, dossier=dossier)
    entry.delete()
    messages.success(request, "Unos obrisan.")
    return redirect("appointments:dossier_detail", partner_id=partner_id)


@login_required
def service_list(request):
    company = get_user_company(request)
    services = BookingService.objects.filter(company=company).order_by("branch_type", "name") if company else BookingService.objects.none()
    return render(request, "appointments/service_list.html", {
        "services": services,
        "branch_types": dict(__import__("appointments.models", fromlist=["BRANCH_TYPES"]).BRANCH_TYPES),
    })


@login_required
def service_create(request):
    from .forms import BookingServiceForm
    if request.method == "POST":
        form = BookingServiceForm(request.POST)
        if form.is_valid():
            svc = form.save(commit=False)
            if not svc.company_id:
                svc.company = get_user_company(request)
            svc.save()
            messages.success(request, "Usluga kreirana: " + svc.name)
            return redirect("appointments:service_list")
        else:
            messages.error(request, str(form.errors))
    else:
        form = BookingServiceForm()
    return render(request, "appointments/service_form.html", {
        "form": form, "action": "Nova usluga",
    })


@login_required
def service_edit(request, pk):
    from .forms import BookingServiceForm
    svc = get_object_or_404(BookingService, pk=pk)
    if request.method == "POST":
        form = BookingServiceForm(request.POST, instance=svc)
        if form.is_valid():
            form.save()
            messages.success(request, "Usluga ažurirana: " + svc.name)
            return redirect("appointments:service_list")
        else:
            messages.error(request, str(form.errors))
    else:
        form = BookingServiceForm(instance=svc)
    return render(request, "appointments/service_form.html", {
        "form": form, "svc": svc, "action": "Uredi uslugu",
    })

# ── COMPANY-SCOPED PUBLIC BOOKING ─────────────────────────────

def public_booking_by_slug(request, company_slug):
    """Public booking page scoped to a company via slug."""
    from companies.models import Company
    company = get_object_or_404(Company, booking_slug=company_slug)
    # Filter services by company FK (ORM migration applied)
    services = BookingService.objects.filter(company=company, is_active=True)
    return render(request, "appointments/public/index.html", {
        "services":        services,
        "company":         company,
        "booking_company": company,   # za booking_base.html brand
    })


@login_required
def send_reminder(request, pk):
    from django.contrib import messages
    from django.shortcuts import redirect
    from appointments.tasks import _send_reminder_whatsapp, _send_reminder_email
    from appointments.models import Appointment
    appt = get_object_or_404(Appointment, pk=pk)
    sent = []
    wa = appt.whatsapp_number or (appt.client.phone if appt.client else '')
    if wa:
        try:
            _send_reminder_whatsapp(appt, wa)
            appt.whatsapp_reminder_sent = True
            sent.append('WhatsApp')
        except Exception as e:
            messages.error(request, 'WA greska: {}'.format(e))
    if appt.client and appt.client.email:
        try:
            _send_reminder_email(appt)
            appt.email_reminder_sent = True
            sent.append('Email')
        except Exception as e:
            messages.error(request, 'Email greska: {}'.format(e))
    if sent:
        from django.utils import timezone
        appt.reminder_sent_at = timezone.now()
        appt.save(update_fields=['whatsapp_reminder_sent','email_reminder_sent','reminder_sent_at'])
        messages.success(request, 'Podsjetnik poslan: {}'.format(', '.join(sent)))
    elif not sent and not wa and not (appt.client and appt.client.email):
        messages.warning(request, 'Nema telefona ni emaila za slanje.')
    return redirect(request.META.get('HTTP_REFERER', '/appointments/'))


@login_required
def send_reminders_now(request):
    from django.contrib import messages
    from django.shortcuts import redirect
    from appointments.tasks import send_appointment_reminders
    result = send_appointment_reminders()
    messages.success(request, 'Podsjetnici: {} email + {} WhatsApp (od {} termina)'.format(
        result['email'], result['whatsapp'], result['total']))
    return redirect(request.META.get('HTTP_REFERER', '/appointments/calendar/'))


# ══════════════════════════════════════════════════════════════════════════════
# POLYMORPHIC SCHEDULING — Double-Lock API
# ══════════════════════════════════════════════════════════════════════════════

@csrf_exempt
@transaction.atomic
def api_book_double_lock(request):
    """
    POST /appointments/api/book/
    Double-Lock booking: checks Actor AND Resource before confirming.
    Race-condition safe via select_for_update().

    Body: {
        service_id: int,
        date: "YYYY-MM-DD",
        time: "HH:MM",
        name: str,
        email: str (optional),
        phone: str (optional),
        payment_method: str (optional),
    }
    Returns:
        200: {status: "success", booking_id: int}
        409: {error: str, code: "NO_ACTOR"|"NO_RESOURCE"}
        400: {error: str}
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Neispravan JSON.'}, status=400)

    service_id = data.get('service_id')
    date_str = data.get('date')
    time_str = data.get('time')
    client_name = data.get('name', '').strip()

    if not all([service_id, date_str, time_str]):
        return JsonResponse({'error': 'Nedostaju parametri: service_id, date, time.'}, status=400)

    from appointments.scheduling import SchedulingError, book_slot
    from companies.models import Company

    service = get_object_or_404(BookingService, id=service_id)
    target_date = parse_date(date_str)
    if not target_date:
        return JsonResponse({'error': 'Neispravan datum.'}, status=400)

    try:
        start_dt = timezone.make_aware(
            __import__('datetime').datetime.strptime(f'{date_str} {time_str}', '%Y-%m-%d %H:%M')
        )
    except ValueError:
        return JsonResponse({'error': 'Neispravan format vremena.'}, status=400)

    duration_min = service.duration.total_seconds() / 60
    end_dt = start_dt + __import__('datetime').timedelta(minutes=duration_min)

    # Determine company from the service being booked
    company = service.company
    if not company:
        if request.user.is_authenticated:
            try:
                company = request.user.profile.company
            except Exception:
                pass
    if not company:
        company = Company.objects.filter(is_platform_owner=True).first() or Company.objects.first()

    # Find or create client partner
    client = None
    email = data.get('email', '').strip()
    if email:
        from partners.models import Partner
        client = Partner.objects.filter(email=email, company=company).first()
        if not client:
            import uuid as _uuid
            client = Partner.objects.create(
                name=client_name or email,
                email=email,
                phone=data.get('phone', ''),
                company=company,
                partner_type='client',
                oib=f'B{_uuid.uuid4().hex[:10].upper()}',
            )

    try:
        appointment = book_slot(
            company=company,
            service=service,
            start_dt=start_dt,
            end_dt=end_dt,
            client=client,
            client_name=client_name,
            client_data=data,
        )
        return JsonResponse({
            'status': 'success',
            'booking_id': appointment.pk,
            'message': f'Termin zakazan: {service.name} u {time_str}.',
            'total_price': float(appointment.total_price or 0),
        })
    except SchedulingError as e:
        return JsonResponse({
            'error': e.message,
            'code': e.code,
            'detail': e.detail,
        }, status=409)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def api_check_double_lock(request):
    """
    GET /appointments/api/check-availability/?service_id=X&date=YYYY-MM-DD&time=HH:MM
    Quick availability check (non-locking).
    """
    service_id = request.GET.get('service_id')
    date_str = request.GET.get('date')
    time_str = request.GET.get('time')

    if not all([service_id, date_str, time_str]):
        return JsonResponse({'error': 'Nedostaju parametri.'}, status=400)

    from appointments.scheduling import check_availability
    from companies.models import Company

    service = get_object_or_404(BookingService, id=service_id)
    target_date = parse_date(date_str)
    if not target_date:
        return JsonResponse({'available': False, 'reason': 'BAD_DATE'})

    try:
        start_dt = timezone.make_aware(
            __import__('datetime').datetime.strptime(f'{date_str} {time_str}', '%Y-%m-%d %H:%M')
        )
    except ValueError:
        return JsonResponse({'available': False, 'reason': 'BAD_TIME'})

    duration_min = service.duration.total_seconds() / 60
    end_dt = start_dt + __import__('datetime').timedelta(minutes=duration_min)

    company = service.company or Company.objects.filter(is_platform_owner=True).first() or Company.objects.first()

    available, reason = check_availability(company, service, start_dt, end_dt)
    return JsonResponse({'available': available, 'reason': reason})


# ══════════════════════════════════════════════════════════════════════════════
# POLYMORPHIC CALENDAR — Double-Lock Slot Generation
# ══════════════════════════════════════════════════════════════════════════════

@require_GET
def api_double_lock_slots(request):
    """
    GET /appointments/api/dl-slots/?service_id=X&date=YYYY-MM-DD
    Returns all time slots with Double-Lock availability check.
    Response: {slots: [{time: "08:00", available: true}, ...], service_name: str}
    """
    from datetime import datetime as dt_class, timedelta as td
    from appointments.scheduling import check_availability
    from companies.models import Company

    service_id = request.GET.get("service_id")
    date_str = request.GET.get("date")
    if not service_id or not date_str:
        return JsonResponse({"error": "Nedostaju parametri: service_id, date."}, status=400)

    service = get_object_or_404(BookingService, id=service_id)
    target_date = parse_date(date_str)
    if not target_date:
        return JsonResponse({"slots": [], "error": "Neispravan datum."})

    now = timezone.now()
    if target_date < now.date():
        return JsonResponse({"slots": [], "service_name": service.name})

    company = service.company
    if not company:
        if request.user.is_authenticated:
            try:
                company = request.user.profile.company
            except Exception:
                pass
    if not company:
        company = Company.objects.filter(is_platform_owner=True).first() or Company.objects.first()
    if not company:
        return JsonResponse({"slots": [], "error": "Nema konfiguriranog poduzeca."})

    # Gather working hours from ALL relevant resources
    weekday = target_date.weekday()
    wh_entries = WorkingHours.objects.filter(
        day_of_week=weekday, is_day_off=False,
        resource__is_active=True,
    )
    if company:
        wh_entries = wh_entries.filter(resource__company=company)

    if not wh_entries.exists():
        return JsonResponse({"slots": [], "service_name": service.name, "message": "Nema radnog vremena za taj dan."})

    # Find earliest start, latest end across all resources
    from datetime import time as time_class
    earliest = min(wh.start_time for wh in wh_entries)
    latest = max(wh.end_time for wh in wh_entries)

    duration_min = int(service.duration.total_seconds() // 60)
    step = service.slot_duration_minutes or 15

    slots = []
    current = dt_class.combine(target_date, earliest)
    end_boundary = dt_class.combine(target_date, latest)

    while current + td(minutes=duration_min) <= end_boundary:
        slot_time = current.strftime("%H:%M")
        start_aware = timezone.make_aware(current)
        end_aware = start_aware + td(minutes=duration_min)

        # Skip past slots for today
        if target_date == now.date() and start_aware <= now:
            current += td(minutes=step)
            continue

        available, reason = check_availability(company, service, start_aware, end_aware)
        slots.append({
            "time": slot_time,
            "available": available,
            "reason": reason if not available else "",
        })
        current += td(minutes=step)

    return JsonResponse({
        "slots": slots,
        "service_name": service.name,
        "duration_minutes": duration_min,
        "date": date_str,
    })


@login_required
def booking_calendar_view(request):
    """Internal booking calendar with Double-Lock slot visualization."""
    from core.company_utils import get_user_company
    company = get_user_company(request)
    services = BookingService.objects.filter(is_active=True, company=company) if company else BookingService.objects.none()
    return render(request, "appointments/booking_calendar.html", {
        "services": services,
    })


# ══════════════════════════════════════════════════════════════════════════════
# BOOKING GUEST VERIFICATION — email + WhatsApp PIN + QR kod
# ══════════════════════════════════════════════════════════════════════════════

@csrf_exempt
@require_POST
@csrf_exempt
def api_booking_guest_register(request):
    """Korak 1: Gost unese ime+email+telefon → šalje email verify link + WA PIN."""
    import secrets, hashlib
    from django.core.cache import cache
    from django.core.validators import validate_email
    from django.core.exceptions import ValidationError

    try:
        data   = json.loads(request.body)
        name   = data.get('name', '').strip()
        email  = data.get('email', '').strip().lower()
        phone  = data.get('phone', '').strip()
        company_slug = data.get('company_slug', '')
    except Exception:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    if not name or not email:
        return JsonResponse({'error': 'Ime i email su obavezni.'}, status=400)

    try:
        validate_email(email)
    except ValidationError:
        return JsonResponse({'error': 'Email adresa nije ispravna.'}, status=400)

    # Nađi ili kreiraj gosta u bazi
    from django.db import connection as _conn
    from companies.models import Company

    company = None
    if company_slug:
        try:
            company = Company.objects.get(booking_slug=company_slug)
        except Company.DoesNotExist:
            pass

    cursor = _conn.cursor()

    # Provjeri postoji li već verificirani gost s tim emailom
    cursor.execute(
        "SELECT id, qr_token, is_verified FROM appointments_bookingguesttoken WHERE email=%s AND company_id=%s",
        [email, str(company.id) if company else None]
    )
    row = cursor.fetchone()

    if row and row[2]:  # is_verified=True
        guest_id = str(row[0])
        qr_token = row[1]
        # Već verificiran — vrati QR token direktno
        return JsonResponse({'status': 'already_verified', 'qr_token': qr_token, 'guest_id': guest_id})

    # Kreiraj ili ažuriraj gosta
    qr_token = secrets.token_urlsafe(32)
    if row:
        guest_id = str(row[0])
        cursor.execute(
            "UPDATE appointments_bookingguesttoken SET name=%s, phone=%s WHERE id=%s",
            [name, phone, guest_id]
        )
    else:
        import uuid as _uuid
        guest_id = str(_uuid.uuid4())
        cursor.execute(
            """INSERT INTO appointments_bookingguesttoken
               (id, name, email, phone, company_id, qr_token, is_verified, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, FALSE, NOW())""",
            [guest_id, name, email, phone,
             str(company.id) if company else None, qr_token]
        )
    _conn.connection.commit()

    # Generiraj kratki PIN za email verifikaciju (6 znakova)
    email_token = secrets.token_urlsafe(24)
    wa_pin      = str(secrets.randbelow(9000) + 1000)  # 4-znamenkasti PIN

    # Spremi u Redis cache (24h za email, 10min za WA PIN)
    cache.set(f'bguest_email_{email_token}', guest_id, 60 * 60 * 24)
    cache.set(f'bguest_wa_{guest_id}', wa_pin, 60 * 10)

    # ── Email verification link ────────────────────────────────────────────────
    base_url = 'https://limit-connect.com'
    lang = data.get('lang', 'hr')
    verify_url = f"{base_url}/{lang}/appointments/api/booking/verify-email/?t={email_token}"

    try:
        from core.email_tasks import send_email_task
        subject = f"Potvrdite rezervaciju — {company.name if company else 'Online booking'}"
        body_html = f"""
        <div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;padding:24px">
          <h2 style="color:#c9a84c">Potvrda email adrese</h2>
          <p>Poštovani/a <strong>{name}</strong>,</p>
          <p>Kliknite gumb za potvrdu vaše rezervacije:</p>
          <a href="{verify_url}" style="display:inline-block;background:#c9a84c;color:#000;
             padding:12px 28px;text-decoration:none;font-weight:700;border-radius:4px;margin:16px 0">
            ✓ Potvrdi rezervaciju
          </a>
          <p style="color:#888;font-size:.85rem">Link vrijedi 24 sata.<br>
          Ako niste zatražili rezervaciju, ignorirajte ovaj email.</p>
          <hr style="border:none;border-top:1px solid #eee;margin:20px 0">
          <p style="color:#888;font-size:.8rem">{company.name if company else ''}</p>
        </div>
        """
        send_email_task.delay(subject, '', 'noreply@limit-connect.com', [email], html_message=body_html)
    except Exception as e:
        logger.warning('Email send failed: %s', e)

    # ── WhatsApp PIN ───────────────────────────────────────────────────────────
    wa_sent = False
    if phone:
        try:
            from django.conf import settings as _s
            if getattr(_s, 'WAHA_ENABLED', False):
                from core.whatsapp_tasks import send_whatsapp_text_task
                company_name = company.name if company else 'Online booking'
                wa_msg = "PIN za rezervaciju\n\nVas PIN: " + str(wa_pin) + "\n\nVrijedi 10 minuta. - " + company_name
                send_whatsapp_text_task.delay(phone, wa_msg)
                wa_sent = True
        except Exception as e:
            logger.warning('WA PIN send failed: %s', e)

    return JsonResponse({
        'status': 'verification_sent',
        'email_sent': True,
        'wa_sent': wa_sent,
        'guest_id': guest_id,
        'has_phone': bool(phone),
    })


@csrf_exempt
@csrf_exempt
def api_booking_verify_email(request):
    """Korak 2a: Gost klikne email link → verificiran → redirect na booking."""
    from django.core.cache import cache
    from django.db import connection as _conn

    token = request.GET.get('t', '').strip()
    if not token:
        return HttpResponse('<h2>Nevažeći link.</h2>', status=400)

    guest_id = cache.get(f'bguest_email_{token}')
    if not guest_id:
        return HttpResponse('<h2>Link je istekao ili već iskorišten.</h2>', status=400)

    # Markiraj kao verificiranog
    cursor = _conn.cursor()
    cursor.execute(
        "UPDATE appointments_bookingguesttoken SET is_verified=TRUE, last_used=NOW() WHERE id=%s RETURNING qr_token, name, company_id",
        [guest_id]
    )
    row = cursor.fetchone()
    _conn.connection.commit()
    cache.delete(f'bguest_email_{token}')

    if not row:
        return HttpResponse('<h2>Gost nije pronađen.</h2>', status=404)

    qr_token, guest_name, company_id = row

    # Nađi booking_slug za redirect
    slug = ''
    if company_id:
        cursor.execute("SELECT booking_slug FROM companies_company WHERE id=%s", [str(company_id)])
        r = cursor.fetchone()
        if r: slug = r[0] or ''

    lang = request.LANGUAGE_CODE if hasattr(request, 'LANGUAGE_CODE') else 'hr'
    redirect_url = f"/{lang}/appointments/booking/c/{slug}/?verified=1&guest={guest_id}&qr={qr_token}"

    return HttpResponse(f"""
    <!DOCTYPE html><html><head><meta charset="UTF-8">
    <meta http-equiv="refresh" content="2;url={redirect_url}">
    <title>Email potvrđen</title>
    <style>body{{font-family:Arial,sans-serif;text-align:center;padding:60px;background:#0a0a0a;color:#fff}}
    .gold{{color:#c9a84c}}</style></head><body>
    <h2>✅ Email potvrđen!</h2>
    <p>Hvala <span class="gold">{guest_name}</span>! Preusmjeravamo vas na rezervaciju...</p>
    </body></html>
    """)


@csrf_exempt
@require_POST
@csrf_exempt
def api_booking_verify_wa_pin(request):
    """Korak 2b: Gost unese WA PIN → verificiran."""
    from django.core.cache import cache
    from django.db import connection as _conn

    try:
        data     = json.loads(request.body)
        guest_id = data.get('guest_id', '').strip()
        pin      = data.get('pin', '').strip()
    except Exception:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    if not guest_id or not pin:
        return JsonResponse({'error': 'Nedostaju podaci.'}, status=400)

    cached_pin = cache.get(f'bguest_wa_{guest_id}')
    if not cached_pin:
        return JsonResponse({'error': 'PIN je istekao. Zatražite novi.'}, status=400)

    if str(cached_pin) != str(pin):
        return JsonResponse({'error': 'Pogrešan PIN.'}, status=400)

    # Verificiraj gosta
    cursor = _conn.cursor()
    cursor.execute(
        "UPDATE appointments_bookingguesttoken SET is_verified=TRUE, last_used=NOW() WHERE id=%s RETURNING qr_token, name",
        [guest_id]
    )
    row = cursor.fetchone()
    _conn.connection.commit()
    cache.delete(f'bguest_wa_{guest_id}')

    if not row:
        return JsonResponse({'error': 'Gost nije pronađen.'}, status=404)

    qr_token, guest_name = row
    return JsonResponse({'status': 'verified', 'qr_token': qr_token, 'name': guest_name})


@csrf_exempt
@csrf_exempt
def api_booking_qr_login(request):
    """QR skeniranje — automatska prijava gosta po qr_token."""
    from django.db import connection as _conn

    qr_token = request.GET.get('qr', '').strip()
    if not qr_token:
        return JsonResponse({'error': 'Nevažeći QR kod.'}, status=400)

    cursor = _conn.cursor()
    cursor.execute(
        """SELECT id, name, email, phone, is_verified, company_id
           FROM appointments_bookingguesttoken WHERE qr_token=%s""",
        [qr_token]
    )
    row = cursor.fetchone()

    if not row:
        return JsonResponse({'error': 'QR kod nije pronađen.'}, status=404)

    guest_id, name, email, phone, is_verified, company_id = row

    if not is_verified:
        return JsonResponse({'error': 'Profil nije verificiran.'}, status=403)

    # Ažuriraj last_used
    cursor.execute(
        "UPDATE appointments_bookingguesttoken SET last_used=NOW() WHERE id=%s",
        [guest_id]
    )
    _conn.connection.commit()

    # Nađi booking_slug
    slug = ''
    if company_id:
        cursor.execute("SELECT booking_slug FROM companies_company WHERE id=%s", [str(company_id)])
        r = cursor.fetchone()
        if r: slug = r[0] or ''

    return JsonResponse({
        'status': 'ok',
        'guest_id': str(guest_id),
        'name': name,
        'email': email,
        'phone': phone or '',
        'qr_token': qr_token,
        'booking_slug': slug,
    })


@csrf_exempt
def api_booking_generate_qr(request):
    """Generiraj QR kod sliku za gosta (PNG base64)."""
    import qrcode, io, base64 as _b64
    from django.db import connection as _conn

    guest_id = request.GET.get('guest', '').strip()
    if not guest_id:
        return JsonResponse({'error': 'Nedostaje guest_id.'}, status=400)

    cursor = _conn.cursor()
    cursor.execute(
        "SELECT qr_token, name, is_verified FROM appointments_bookingguesttoken WHERE id=%s",
        [guest_id]
    )
    row = cursor.fetchone()
    if not row or not row[2]:
        return JsonResponse({'error': 'Gost nije pronađen ili nije verificiran.'}, status=404)

    qr_token, name, _ = row
    base_url   = 'https://limit-connect.com'
    qr_url     = f"{base_url}/hr/appointments/api/booking/qr-login/?qr={qr_token}"

    qr = qrcode.QRCode(version=2, box_size=8, border=2)
    qr.add_data(qr_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color='#c9a84c', back_color='#0a0a0a')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    img_b64 = _b64.b64encode(buf.getvalue()).decode()

    return JsonResponse({'qr_image': img_b64, 'name': name, 'qr_url': qr_url})

