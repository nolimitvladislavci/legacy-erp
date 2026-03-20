"""
Patch appointments/views.py:
- api_available_slots: returns both 'available' and 'unavailable' slots
- api_submit_public_booking: requires auth, sends confirmation email
- api_booking_auth_check: new endpoint returns auth status + user info
"""

VIEWS_FILE = '/var/www/fina-connect/appointments/views.py'
URLS_FILE  = '/var/www/fina-connect/appointments/urls.py'

with open(VIEWS_FILE) as f:
    content = f.read()

# ── 1. Replace api_available_slots ──────────────────────────────────────────
OLD_SLOTS = '''@require_GET
def api_available_slots(request):
    date_str = request.GET.get("date")
    service_id = request.GET.get("service_id")
    if not date_str or not service_id:
        return JsonResponse({"error": "Nedostaju parametri"}, status=400)
    target_date = parse_date(date_str)
    if not target_date or target_date < datetime.now().date():
        return JsonResponse({"slots": []})
    service = get_object_or_404(BookingService, id=service_id)
    weekday = target_date.weekday()
    resources = BookingResource.objects.filter(resource_type=service.resource_type, is_active=True)
    available_slots = set()
    service_duration = service.duration.total_seconds() / 60
    for resource in resources:
        wh = WorkingHours.objects.filter(resource=resource, day_of_week=weekday, is_day_off=False).first()
        if not wh:
            continue
        start_dt = datetime.combine(target_date, wh.start_time)
        end_dt = datetime.combine(target_date, wh.end_time)
        existing_apps = Appointment.objects.filter(
            resource=resource, start_time__date=target_date, status__in=["scheduled", "confirmed"]
        )
        current_slot = start_dt
        while current_slot + timedelta(minutes=service_duration) <= end_dt:
            slot_end = current_slot + timedelta(minutes=service_duration)
            overlap = any(
                current_slot < a.end_time.replace(tzinfo=None) and slot_end > a.start_time.replace(tzinfo=None)
                for a in existing_apps
            )
            if target_date == datetime.now().date() and current_slot.time() < datetime.now().time():
                overlap = True
            if not overlap:
                available_slots.add(current_slot.strftime("%H:%M"))
            current_slot += timedelta(minutes=30)
    return JsonResponse({"slots": sorted(list(available_slots))})'''

NEW_SLOTS = '''@require_GET
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
    resources = BookingResource.objects.filter(resource_type=service.resource_type, is_active=True)
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
            current_slot += timedelta(minutes=30)
    avail = sorted(list(available_slots))
    unavail = sorted(list(unavailable_slots - available_slots))
    return JsonResponse({"available": avail, "unavailable": unavail, "slots": avail})'''

if OLD_SLOTS in content:
    content = content.replace(OLD_SLOTS, NEW_SLOTS)
    print('OK: api_available_slots updated')
else:
    print('WARN: api_available_slots pattern not found - check manually')


# ── 2. Replace api_submit_public_booking ────────────────────────────────────
OLD_SUBMIT = '''@csrf_exempt
def api_submit_public_booking(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)
    try:
        data = json.loads(request.body)
        service = get_object_or_404(BookingService, id=data["service_id"])
        target_date = parse_date(data["date"])
        start_time = datetime.strptime(f"{data['date']} {data['time']}", "%Y-%m-%d %H:%M")
        end_time = start_time + timedelta(minutes=service.duration.total_seconds() / 60)
        client, _ = Partner.objects.get_or_create(
            email=data["email"],
            defaults={"name": data["name"], "phone": data.get("phone", ""), "partner_type": "KUPAC"},
        )
        resources = BookingResource.objects.filter(resource_type=service.resource_type, is_active=True)
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
            title=f"Online: {service.name}", client=client, service=service,
            resource=assigned_resource, start_time=start_time, end_time=end_time,
            appointment_type="service", status="scheduled", color="#10b981",
            total_price=service.price or 0,
            payment_method=data.get("payment_method", "invoice"),
            whatsapp_number=data.get("whatsapp", ""),
        )
        return JsonResponse({"status": "success", "booking_id": appointment.id, "total_price": float(appointment.total_price or 0)})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)'''

NEW_SUBMIT = '''@csrf_exempt
def api_submit_public_booking(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)
    # Zahtjeva autentikaciju
    if not request.user.is_authenticated:
        return JsonResponse({"error": "auth_required", "message": "Morate biti prijavljeni za rezervaciju."}, status=401)
    try:
        data = json.loads(request.body)
        service = get_object_or_404(BookingService, id=data["service_id"])
        target_date = parse_date(data["date"])
        start_time = datetime.strptime(f"{data['date']} {data['time']}", "%Y-%m-%d %H:%M")
        end_time = start_time + timedelta(minutes=service.duration.total_seconds() / 60)
        # Klijent — pokušaj vezati za korisnika ako postoji partner
        email = data.get("email") or request.user.email
        name  = data.get("name")  or request.user.get_full_name() or request.user.username
        client, _ = Partner.objects.get_or_create(
            email=email,
            defaults={"name": name, "phone": data.get("phone", ""), "partner_type": "KUPAC"},
        )
        resources = BookingResource.objects.filter(resource_type=service.resource_type, is_active=True)
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
            title=f"Online: {service.name}", client=client, service=service,
            resource=assigned_resource, start_time=start_time, end_time=end_time,
            appointment_type="service", status="scheduled", color="#10b981",
            total_price=service.price or 0,
            payment_method=data.get("payment_method", "invoice"),
            whatsapp_number=data.get("whatsapp", ""),
        )
        # ── Potvrda emailom ───────────────────────────────────────────────────
        try:
            from django.core.mail import send_mail
            from django.conf import settings
            dt_fmt = start_time.strftime("%d.%m.%Y u %H:%M")
            subject = f"Potvrda rezervacije — {service.name}"
            body = (
                f"Poštovani/a {name},\\n\\n"
                f"Vaša rezervacija je uspješno kreirana.\\n\\n"
                f"  Usluga:  {service.name}\\n"
                f"  Termin:  {dt_fmt}\\n"
                f"  Trajanje:{int(service.duration.total_seconds()//60)} min\\n"
            )
            if service.price:
                body += f"  Cijena:  {service.price} EUR\\n"
            body += (
                f"\\nAko trebate otkazati ili promijeniti termin, kontaktirajte nas.\\n\\n"
                f"Hvala na povjerenju!\\n"
            )
            send_mail(
                subject, body,
                getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com'),
                [email],
                fail_silently=True
            )
        except Exception:
            pass
        return JsonResponse({"status": "success", "booking_id": appointment.id, "total_price": float(appointment.total_price or 0)})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@require_GET
def api_booking_auth_check(request):
    """Vraća auth status i basic info o korisniku"""
    if request.user.is_authenticated:
        return JsonResponse({
            "authenticated": True,
            "username": request.user.username,
            "email": request.user.email,
            "full_name": request.user.get_full_name() or request.user.username,
        })
    return JsonResponse({"authenticated": False})'''

if OLD_SUBMIT in content:
    content = content.replace(OLD_SUBMIT, NEW_SUBMIT)
    print('OK: api_submit_public_booking updated + api_booking_auth_check added')
else:
    print('WARN: api_submit_public_booking pattern not found - check manually')
    # Try to append auth_check at end
    if 'api_booking_auth_check' not in content:
        content += '''

@require_GET
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
'''
        print('OK: api_booking_auth_check appended')

with open(VIEWS_FILE, 'w') as f:
    f.write(content)
print('OK: views.py written')


# ── 3. Update URLs ───────────────────────────────────────────────────────────
with open(URLS_FILE) as f:
    urls = f.read()

if 'api_booking_auth_check' not in urls:
    urls = urls.replace(
        "    path('api/booking/submit/', views.api_submit_public_booking, name='api_submit_public_booking'),",
        "    path('api/booking/submit/', views.api_submit_public_booking, name='api_submit_public_booking'),\n"
        "    path('api/booking/auth/', views.api_booking_auth_check, name='api_booking_auth_check'),"
    )
    with open(URLS_FILE, 'w') as f:
        f.write(urls)
    print('OK: urls.py updated with auth_check route')
else:
    print('SKIP: auth_check already in urls')
