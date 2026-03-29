# CC_TASK_BEAUTY_BOOKING.md
# Kreirao: Sonnet (koordinator) | Datum: 2026-03-29
# Prioritet: 🟡 SREDNJI — post go-live (poslije 15.4.2026)
# Pilot klijent: House of Hair, Ul. kralja Zvonimira 91a, Čepin | +385 91 563 4793
# Kontakt: Karmela + gospođa Burduš

---

## KONTEKST — Zašto ovo radimo

House of Hair je frizerski salon kod pošte u Čepinu. Ocjena 5.0 na Googleu.
Ivan ih osobno poznaje. Radno vrijeme: pon–sub 08:00–20:00.

Ovo je trojanski konj za Beauty/Wellness vertikalu u HR.
Jedna sretna Karmela → word-of-mouth → 5 salona u Osijeku → Beauty SaaS tier.

U MASTER_PLAN_2026.md ovaj modul planiran pod "Beauty Instagram booking widget" Q2-Q3 2026.
Počinjemo odmah s jednostavnim MVP-om — web stranica + termini.

---

## ŠTO GRADIMO

### Faza 1 — MVP (2 tjedna CC Code rada)
Web stranica + booking sustav za House of Hair, deployano na:
`house-of-hair.limit-connect.com` (ili vlastita domena ako žele)

### Faza 2 — SaaS Beauty Tier (post-pilota)
Isti kod, white-label za bilo koji salon. Plaćanje 29-49 EUR/mj.

---

## ARHITEKTURA

### Nova Django app: `beauty/`

```
beauty/
├── __init__.py
├── models.py          # Service, Staff, Appointment, WorkingHours, Break
├── views.py           # Booking flow, staff dashboard, admin
├── urls.py
├── forms.py           # BookingForm (ime, tel, usluga, frizer, datum/sat)
├── templates/
│   └── beauty/
│       ├── landing.html          # Javna stranica salona
│       ├── booking_step1.html    # Odabir usluge
│       ├── booking_step2.html    # Odabir frizera + termina
│       ├── booking_step3.html    # Kontakt podaci + potvrda
│       ├── booking_confirm.html  # Hvala stranica + iCal link
│       ├── dashboard.html        # Frizer vidi svoje termine danas
│       └── admin_calendar.html   # Vlasnik vidi sve frizere
├── tasks.py           # Celery: WhatsApp podsjetnik 24h i 2h prije
├── admin.py
└── tests.py           # Min. 15 testova
```

---

## MODELI — pročitaj models.py PRIJE pisanja koda

### `beauty/models.py`

```python
class BeautySalon(models.Model):
    """Jedan salon = jedan tenant (company FK pattern kao u ostatku sustava)"""
    company = models.OneToOneField('core.Company', on_delete=models.CASCADE)
    name = models.CharField(max_length=200)           # "House of Hair"
    slug = models.SlugField(unique=True)              # "house-of-hair"
    address = models.TextField()
    phone = models.CharField(max_length=50)
    whatsapp_number = models.CharField(max_length=50, blank=True)  # za WAHA notifikacije
    instagram_handle = models.CharField(max_length=100, blank=True)
    facebook_url = models.URLField(blank=True)
    logo = models.ImageField(upload_to='beauty/logos/', blank=True)
    cover_image = models.ImageField(upload_to='beauty/covers/', blank=True)
    primary_color = models.CharField(max_length=7, default='#1B3A6B')  # CSS hex
    description = models.TextField(blank=True)
    booking_advance_days = models.IntegerField(default=30)  # koliko dana unaprijed
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def get_absolute_url(self):
        return f"/beauty/{self.slug}/"

    def __str__(self):
        return self.name


class BeautyService(models.Model):
    """Usluge salona: šišanje, bojanje, pramenovi..."""
    salon = models.ForeignKey(BeautySalon, on_delete=models.CASCADE, related_name='services')
    name = models.CharField(max_length=200)           # "Šišanje + fen"
    name_en = models.CharField(max_length=200, blank=True)
    duration_minutes = models.IntegerField(default=60)  # trajanje usluge
    price = models.DecimalField(max_digits=8, decimal_places=2)  # u EUR
    category = models.CharField(max_length=50, choices=[
        ('haircut', 'Šišanje'),
        ('color', 'Bojanje'),
        ('treatment', 'Tretman'),
        ('styling', 'Styling'),
        ('other', 'Ostalo'),
    ], default='haircut')
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'name']

    def __str__(self):
        return f"{self.name} ({self.duration_minutes}min — {self.price}€)"


class BeautyStaff(models.Model):
    """Frizeri/e u salonu"""
    salon = models.ForeignKey(BeautySalon, on_delete=models.CASCADE, related_name='staff')
    user = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=200)            # "Karmela"
    role = models.CharField(max_length=100, default='Frizer/ka')
    bio = models.TextField(blank=True)
    photo = models.ImageField(upload_to='beauty/staff/', blank=True)
    services = models.ManyToManyField(BeautyService, blank=True)  # koje usluge radi
    whatsapp_number = models.CharField(max_length=50, blank=True)  # osobni WA
    is_active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'name']

    def __str__(self):
        return f"{self.name} @ {self.salon.name}"


class WorkingHours(models.Model):
    """Radno vrijeme frizera po danu"""
    staff = models.ForeignKey(BeautyStaff, on_delete=models.CASCADE, related_name='working_hours')
    day_of_week = models.IntegerField(choices=[
        (0, 'Ponedjeljak'), (1, 'Utorak'), (2, 'Srijeda'),
        (3, 'Četvrtak'), (4, 'Petak'), (5, 'Subota'), (6, 'Nedjelja'),
    ])
    start_time = models.TimeField()    # 08:00
    end_time = models.TimeField()      # 20:00
    is_working = models.BooleanField(default=True)

    class Meta:
        unique_together = ['staff', 'day_of_week']


class StaffBreak(models.Model):
    """Pauze frizera (ručak, odmor...)"""
    staff = models.ForeignKey(BeautyStaff, on_delete=models.CASCADE, related_name='breaks')
    day_of_week = models.IntegerField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    label = models.CharField(max_length=100, default='Pauza')


class Appointment(models.Model):
    """Termin — srce sustava"""
    STATUS_CHOICES = [
        ('pending', 'Čeka potvrdu'),
        ('confirmed', 'Potvrđen'),
        ('completed', 'Završen'),
        ('cancelled', 'Otkazan'),
        ('no_show', 'Nije došao/la'),
    ]

    salon = models.ForeignKey(BeautySalon, on_delete=models.CASCADE, related_name='appointments')
    staff = models.ForeignKey(BeautyStaff, on_delete=models.CASCADE, related_name='appointments')
    service = models.ForeignKey(BeautyService, on_delete=models.CASCADE)

    # Klijent (ne mora biti user — walk-in booking)
    client_name = models.CharField(max_length=200)
    client_phone = models.CharField(max_length=50)
    client_email = models.EmailField(blank=True)
    client_note = models.TextField(blank=True)       # "alergija na boju X"

    # Termin
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()                    # auto = start + service.duration_minutes

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='confirmed')
    booking_ref = models.CharField(max_length=12, unique=True)  # npr. "HOH-2026-A4B2"
    created_at = models.DateTimeField(auto_now_add=True)

    # Notifikacije
    reminder_24h_sent = models.BooleanField(default=False)
    reminder_2h_sent = models.BooleanField(default=False)
    confirmation_sent = models.BooleanField(default=False)

    # Plaćanje — 4 metode (Revolut, kartica, Aircash, gotovina)
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Gotovina'),
        ('card', 'Kreditna kartica'),
        ('revolut', 'Revolut'),
        ('aircash', 'Aircash'),
    ]
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHOD_CHOICES,
                                       default='cash', blank=True)
    price_charged = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    paid = models.BooleanField(default=False)
    payment_ref = models.CharField(max_length=100, blank=True)  # Revolut/Aircash txn ID

    class Meta:
        ordering = ['date', 'start_time']
        indexes = [
            models.Index(fields=['staff', 'date']),
            models.Index(fields=['date', 'status']),
        ]

    def save(self, *args, **kwargs):
        if not self.booking_ref:
            import random, string
            prefix = self.salon.slug[:3].upper()
            rand = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            self.booking_ref = f"{prefix}-{rand}"
        if not self.end_time:
            from datetime import datetime, timedelta
            start_dt = datetime.combine(self.date, self.start_time)
            end_dt = start_dt + timedelta(minutes=self.service.duration_minutes)
            self.end_time = end_dt.time()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.booking_ref} | {self.client_name} | {self.date} {self.start_time}"
```

---

## VIEWS — Booking flow

### Javni flow (bez logina):

```
GET  /beauty/<slug>/                    → landing page salona
GET  /beauty/<slug>/book/               → step 1: odabir usluge
GET  /beauty/<slug>/book/<service_id>/  → step 2: odabir frizera + slobodnog termina
POST /beauty/<slug>/book/confirm/       → step 3: kontakt + potvrda
GET  /beauty/<slug>/booking/<ref>/      → potvrda s iCal linkom
GET  /beauty/<slug>/booking/<ref>/cancel/ → otkazivanje
```

### Staff dashboard (login required):
```
GET  /beauty/dashboard/                 → dnevni pregled termina (danas + sutra)
GET  /beauty/dashboard/calendar/        → tjedni kalendar
POST /beauty/dashboard/appointment/<id>/status/ → promjena statusa (HTMX)
```

### Admin (vlasnik/ica salona):
```
GET  /beauty/admin/                     → pregled svih frizera, KPI
GET  /beauty/admin/settings/            → podešavanje salona, boje, opis
GET  /beauty/admin/services/            → CRUD usluga
GET  /beauty/admin/staff/               → CRUD frizera
```

---

## SLOBODNI TERMINI — algoritam

```python
def get_available_slots(staff: BeautyStaff, date: date, service: BeautyService) -> list[time]:
    """
    Vraća listu slobodnih početnih vremena za dani frizer, datum i uslugu.
    Korak: 30 minuta (konfigurabilan po salonu).
    """
    # 1. Dohvati radno vrijeme za taj dan tjedna
    day = date.weekday()  # 0=pon
    try:
        wh = WorkingHours.objects.get(staff=staff, day_of_week=day, is_working=True)
    except WorkingHours.DoesNotExist:
        return []  # ne radi taj dan

    # 2. Dohvati sve potvrđene termine tog dana
    busy = Appointment.objects.filter(
        staff=staff,
        date=date,
        status__in=['pending', 'confirmed']
    ).values_list('start_time', 'end_time')

    # 3. Dohvati pauze
    breaks = StaffBreak.objects.filter(
        staff=staff,
        day_of_week=day
    ).values_list('start_time', 'end_time')

    # 4. Generiraj slobodne slotove
    from datetime import datetime, timedelta
    duration = timedelta(minutes=service.duration_minutes)
    step = timedelta(minutes=30)
    slots = []
    current = datetime.combine(date, wh.start_time)
    end_of_day = datetime.combine(date, wh.end_time)

    while current + duration <= end_of_day:
        slot_start = current.time()
        slot_end = (current + duration).time()

        # Provjeri preklapanje s terminima
        overlap = False
        for b_start, b_end in list(busy) + list(breaks):
            if slot_start < b_end and slot_end > b_start:
                overlap = True
                break

        if not overlap:
            slots.append(slot_start)
        current += step

    return slots
```

---

---

## PLAĆANJE — 4 metode

### Podržane metode:
| Metoda | Kako | Infrastruktura |
|---|---|---|
| **Gotovina** | Klijent plati na licu mjesta | Bez integracije — frizer označi "plaćeno" |
| **Kreditna kartica** | Revolut terminal ili POS terminal | `pos/revolut_service.py` — već radi |
| **Revolut** | QR kod ili link na checkout | `pos/revolut_service.py` — `create_payment_link()` |
| **Aircash** | Klijent skenira QR u Aircash appu | Aircash merchant API (novi) |

### Flow plaćanja (u booking_confirm view):
```python
# Step 3: klijent odabere metodu plaćanja
if payment_method == "revolut":
    # Kreiraj Revolut payment link
    from pos.revolut_service import create_payment_link
    link = create_payment_link(amount=service.price, description=f"Beauty: {service.name}")
    # Redirect klijenta na Revolut checkout
    return redirect(link)

elif payment_method == "card":
    # Isto kao revolut — Revolut Tap to Pay ili terminal
    from pos.revolut_service import create_payment_link
    link = create_payment_link(amount=service.price, description=f"Beauty: {service.name}")
    return redirect(link)

elif payment_method == "aircash":
    # Generiraj Aircash QR → klijent skenira → webhook potvrdi
    qr_data = generate_aircash_qr(amount=service.price, ref=appointment.booking_ref)
    return render(request, "beauty/aircash_qr.html", {"qr": qr_data})

elif payment_method == "cash":
    # Bez online plaćanja — termin odmah potvrđen
    appointment.status = "confirmed"
    appointment.save()
```

### Revolut webhook (već postoji):
`/pos/revolut/webhook/` → ažurira `appointment.paid = True, payment_ref = txn_id`

### Aircash integracija (nova):
- Aircash Merchant API: `POST /api/v1/payments` → vraća QR kod
- Webhook: `POST /beauty/aircash/webhook/` → potvrda plaćanja
- Potrebno: Aircash merchant account za House of Hair

### Payment UI u booking step 3:
```
┌─────────────────────────────────┐
│  Kako želite platiti?           │
│                                 │
│  💵  Gotovina (na licu mjesta) │
│  💳  Kreditna kartica          │
│  🔄  Revolut                   │
│  📱  Aircash                   │
│                                 │
│  [ Potvrdi termin ]            │
└─────────────────────────────────┘
```


## WHATSAPP NOTIFIKACIJE

### Celery taskovi u `beauty/tasks.py`:

```python
@shared_task
def send_booking_confirmation(appointment_id):
    """Šalje odmah po rezervaciji."""
    apt = Appointment.objects.get(pk=appointment_id)
    msg = (
        f"✅ *Termin potvrđen!*\n\n"
        f"📋 Ref: {apt.booking_ref}\n"
        f"💇 Usluga: {apt.service.name}\n"
        f"👤 Frizer/ka: {apt.staff.name}\n"
        f"📅 {apt.date.strftime('%d.%m.%Y.')} u {apt.start_time.strftime('%H:%M')}\n"
        f"📍 {apt.salon.address}\n\n"
        f"Za otkazivanje: {apt.salon.get_absolute_url()}booking/{apt.booking_ref}/cancel/"
    )
    send_whatsapp(apt.client_phone, msg)


@shared_task
def send_reminder_24h(appointment_id):
    """Podsjetnik 24h prije."""
    apt = Appointment.objects.get(pk=appointment_id)
    if apt.status != 'confirmed':
        return
    msg = (
        f"⏰ *Podsjetnik — sutra imate termin!*\n\n"
        f"💇 {apt.service.name} kod {apt.staff.name}\n"
        f"📅 {apt.date.strftime('%d.%m.%Y.')} u {apt.start_time.strftime('%H:%M')}\n"
        f"📍 House of Hair, Čepin\n\n"
        f"Vidimo se! 🌟"
    )
    send_whatsapp(apt.client_phone, msg)
    apt.reminder_24h_sent = True
    apt.save(update_fields=['reminder_24h_sent'])


@shared_task
def send_reminder_2h(appointment_id):
    """Podsjetnik 2h prije — samo za iste dan."""
    # Ista logika, kraća poruka
    pass


@shared_task
def schedule_reminders_daily():
    """Celery beat svaki dan u 09:00 — zakazuje remindere za sutra."""
    tomorrow = date.today() + timedelta(days=1)
    appointments = Appointment.objects.filter(
        date=tomorrow,
        status='confirmed',
        reminder_24h_sent=False
    )
    for apt in appointments:
        send_reminder_24h.apply_async(
            args=[apt.pk],
            eta=datetime.combine(tomorrow - timedelta(days=1), time(9, 0))
        )
```

---

## LANDING PAGE — House of Hair vizualni identitet

Landing page mora izgledati **profesionalno i lokalno** — nije generički SaaS template.
Koristiti House of Hair ime, adresu, radno vrijeme koje smo našli.

### Sekcije (u redoslijedu):

1. **Hero** — naziv salona + tagline + CTA gumb "Rezerviraj termin"
   - Boje: tamna pozadina, zlatni naglasci (premium osjećaj)
   - Radno vrijeme: pon–sub 08:00–20:00

2. **Usluge** — kartice s cijenom i trajanjem
   - Šišanje + fen, Bojanje, Pramenovi, Tretman, Styling...

3. **Tim** — Karmela + gospođa Burduš + foto (ako daju)

4. **Kako rezervirati** — 3 koraka s ikonama (odaberi → potvrdi → dođi)

5. **Recenzije** — statične (s Googlea, uz dozvolu)

6. **Kontakt + Lokacija** — adresa, telefon, Google Maps embed

7. **Footer** — powered by LIMIT Connect (discreetno)

### Booking widget (embeddable):
```html
<!-- Embed kod koji Karmela može staviti na bilo koji site -->
<script src="https://limit-connect.com/beauty/widget.js"
        data-salon="house-of-hair"
        data-color="#1B3A6B">
</script>
```

---

## iCAL INTEGRACIJA

```python
def generate_ical(appointment: Appointment) -> str:
    """Generira .ics fajl za dodavanje u kalendar."""
    from icalendar import Calendar, Event
    from datetime import datetime

    cal = Calendar()
    cal.add('prodid', '-//LIMIT Connect Beauty//HR')
    cal.add('version', '2.0')

    event = Event()
    event.add('summary', f"{appointment.service.name} @ {appointment.salon.name}")
    event.add('dtstart', datetime.combine(appointment.date, appointment.start_time))
    event.add('dtend', datetime.combine(appointment.date, appointment.end_time))
    event.add('location', appointment.salon.address)
    event.add('description',
        f"Frizer/ka: {appointment.staff.name}\n"
        f"Ref: {appointment.booking_ref}\n"
        f"Tel: {appointment.salon.phone}"
    )
    event.add('uid', f"{appointment.booking_ref}@limit-connect.com")
    cal.add_component(event)

    return cal.to_ical()
```

---

## TESTOVI — minimum 15

```python
# beauty/tests.py

class TestAvailableSlots(TestCase):
    """Provjeri da algoritam slobodnih termina radi ispravno."""
    # Test 1: prazan dan → svi slotovi slobodni
    # Test 2: jedan termin → taj slot zauzet
    # Test 3: pauza isključuje slotove
    # Test 4: kraj dana → nema slota koji prelazi radno vrijeme
    # Test 5: ne radi taj dan → prazna lista

class TestAppointmentModel(TestCase):
    """Provjeri model."""
    # Test 6: booking_ref auto-generiran
    # Test 7: end_time auto-kalkuliran iz start + duration
    # Test 8: unique booking_ref
    # Test 9: status default = 'confirmed'

class TestBookingFlow(TestCase):
    """E2E booking flow bez logina."""
    # Test 10: GET landing page → 200
    # Test 11: GET book/ → lista usluga
    # Test 12: POST book/confirm/ s validnim podacima → Appointment kreiran
    # Test 13: POST book/confirm/ s nevažećim datumom → 400
    # Test 14: otkazivanje → status='cancelled'
    # Test 15: dupli booking iste osobe u isti termin → greška

class TestWhatsAppNotifications(TestCase):
    """Provjeri da se WA šalje."""
    # Test 16: potvrda booking-a → send_whatsapp pozvan
    # Test 17: otkazivanje → WA notifikacija s cancellation porukom
```

---

## CELERY BEAT RASPORED

Dodaj u `core/settings.py` CELERY_BEAT_SCHEDULE:

```python
'beauty-schedule-reminders': {
    'task': 'beauty.tasks.schedule_reminders_daily',
    'schedule': crontab(hour=9, minute=0),  # svaki dan u 09:00
},
'beauty-check-2h-reminders': {
    'task': 'beauty.tasks.send_2h_reminders',
    'schedule': crontab(minute=0),  # svaki sat, task interno filtrira
},
```

---

## URLS

```python
# beauty/urls.py
urlpatterns = [
    # Javni booking
    path('<slug:salon_slug>/', views.salon_landing, name='beauty_landing'),
    path('<slug:salon_slug>/book/', views.booking_step1, name='beauty_book_step1'),
    path('<slug:salon_slug>/book/<int:service_id>/', views.booking_step2, name='beauty_book_step2'),
    path('<slug:salon_slug>/book/confirm/', views.booking_confirm, name='beauty_book_confirm'),
    path('<slug:salon_slug>/booking/<str:ref>/', views.booking_detail, name='beauty_booking_detail'),
    path('<slug:salon_slug>/booking/<str:ref>/cancel/', views.booking_cancel, name='beauty_booking_cancel'),
    path('<slug:salon_slug>/booking/<str:ref>/ical/', views.booking_ical, name='beauty_booking_ical'),

    # Staff dashboard
    path('dashboard/', views.staff_dashboard, name='beauty_dashboard'),
    path('dashboard/calendar/', views.staff_calendar, name='beauty_calendar'),
    path('dashboard/appointment/<int:pk>/status/', views.appointment_status, name='beauty_apt_status'),

    # Admin
    path('admin-panel/', views.salon_admin, name='beauty_admin'),
    path('admin-panel/services/', views.services_admin, name='beauty_services'),
    path('admin-panel/staff/', views.staff_admin, name='beauty_staff_admin'),
    path('admin-panel/settings/', views.salon_settings, name='beauty_settings'),

    # Widget (embed)
    path('widget.js', views.booking_widget_js, name='beauty_widget'),
]
```

Dodaj u `core/urls.py`:
```python
path('beauty/', include('beauty.urls', namespace='beauty')),
```

---

## SEED DATA — House of Hair

Kreiraj management command `manage.py seed_house_of_hair`:

```python
# Salon
salon = BeautySalon.objects.create(
    name='House of Hair',
    slug='house-of-hair',
    address='Ul. kralja Zvonimira 91a, 31431 Čepin',
    phone='+385 91 563 4793',
    primary_color='#2C2C2C',  # elegantna tamna
    booking_advance_days=30,
)

# Usluge (tipične za HR frizerski salon, cijene prilagoditi)
services = [
    ('Šišanje + fen', 60, 15.00, 'haircut'),
    ('Bojanje cijele kose', 120, 45.00, 'color'),
    ('Pramenovi', 90, 35.00, 'color'),
    ('Balayage', 150, 65.00, 'color'),
    ('Tretman za kosu', 45, 20.00, 'treatment'),
    ('Svečana frizura', 90, 40.00, 'styling'),
    ('Dječje šišanje', 30, 10.00, 'haircut'),
    ('Šišanje muško', 30, 12.00, 'haircut'),
]

# Frizerke
staff = [
    ('Karmela', 'Frizer/ka'),
    ('Burduš', 'Frizer/ka'),  # gospođa Burduš
]

# Radno vrijeme: pon–sub 08:00–20:00
for s in BeautyStaff.objects.filter(salon=salon):
    for day in range(6):  # pon=0 do sub=5
        WorkingHours.objects.create(
            staff=s, day_of_week=day,
            start_time=time(8, 0), end_time=time(20, 0)
        )
```

---

## DEPLOYMENT CHECKLIST

Po završetku implementacije:

- [ ] `python manage.py makemigrations beauty`
- [ ] `python manage.py migrate`
- [ ] `python manage.py seed_house_of_hair`
- [ ] Celery beat restart: `supervisorctl restart celery-beat`
- [ ] Test booking end-to-end (Ivan testira od svog telefona)
- [ ] WhatsApp notifikacija testirana (WAHA TEST_MODE)
- [ ] Google Maps embed aktivan
- [ ] Subdomena: `house-of-hair.limit-connect.com` → Nginx config
- [ ] SSL certifikat za subdomenu (Certbot wildcard)
- [ ] Sve 15+ testova zeleno: `python manage.py test beauty`
- [ ] FENIX_STATUS.md ažuriran s DONE

---

## NGINX CONFIG (za subdomenu)

```nginx
server {
    listen 80;
    server_name house-of-hair.limit-connect.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl;
    server_name house-of-hair.limit-connect.com;

    # SSL — wildcard certifikat ako postoji, ili novi:
    # certbot certonly --nginx -d house-of-hair.limit-connect.com

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /var/www/fina-connect/static/;
    }

    location /media/ {
        alias /var/www/fina-connect/media/;
    }
}
```

---

## OVISNOSTI (pip)

```
icalendar>=5.0.0        # .ics generiranje
Pillow>=10.0.0          # ImageField (logo, cover, staff foto)
```

Dodaj u requirements.txt.

---

## NAPOMENE ZA CC CODE

1. **PROČITAJ models.py** u `core/`, `invoicing/`, `rental/` — Company, Partner, User FK pattern
2. **CompanyManager** — beauty app mora imati `objects = CompanyManager()` na svim modelima s company FK
3. **Stil templates** — koristi isti base.html, Tailwind klase kao ostatak sustava
4. **HTMX** — booking step 2 (odabir termina) radi HTMX reload bez page refresh
5. **Mobile-first** — 80% korisnica će bookirati s mobitela
6. **Plaćanje u MVP-u** — 4 metode: gotovina, kreditna kartica, Revolut, Aircash. Revolut već integriran u POS (pos/revolut_service.py). Fiskalizacija u Fazi 2.
7. **Subdomena** — svaki salon dobiva slug-based URL, ne path-based (bolje za SEO)

---

## NAKON PILOTA — SaaS Beauty Tier

Kad House of Hair bude živjelo 30 dana bez problema:

1. **Onboarding wizard** — novi salon se registrira sam (bez Ivana)
2. **Pricing tier** — Beauty Starter: 29 EUR/mj | Beauty Pro: 49 EUR/mj
3. **Instagram integracija** — "Rezerviraj" gumb direktno s Instagram profila
4. **Google My Business** — "Rezerviraj" gumb na Google karti
5. **Stripe plaćanje** — online naplata depozita (sprečava no-show)
6. **SMS podsjetnici** — alternativa WhatsAppu za klijente bez WA
7. **Loyalty program** — "10. termin gratis" (jednostavni counter)

---

## STATUS

- Kreiran: 2026-03-29 | Sonnet
- Implementacija: ⏳ CC Code (POSLIJE 15.4. go-live)
- Pilot kontakt: Ivan (osobno poznanstvo) — pitati Karmelu kad ide u Čepin
- Očekivani go-live pilota: Svibanj 2026
