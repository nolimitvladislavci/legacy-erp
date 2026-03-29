# CC_TASK_BEAUTY_INSTAGRAM_WIDGET.md
# Dodijeljen: CC Code
# Prioritet: VISOKO — H1.1 (Q2 2026)
# Tržište: 10.800 beauty salona/frizera u HR
# Procjena: 2-3 tjedna
# Ref: MASTER_PLAN_2026.md → H1.1

## INSIGHT

Beauty vlasnica ne kupuje ERP. Kupuje gumb koji stavlja u Instagram bio
koji njeni klijenti mogu kliknuti u 22:00 i rezervirati termin za sutra.

Loyalty, izvještaji, inventar — sve je sekundarno.
Widget je jedino što prodaje.

## ŠTO BUILDATI

### Faza 1: Public Booking Page (2-3 dana)

URL: `/beauty/book/<salon-slug>/`
- Bez autentifikacije — javna stranica
- Prikazuje dostupne termine za sljedećih 14 dana
- Mobile-first design (90% Beauty korisnika dolazi s mobitela)
- Tamni + svijetli mod (čita preferencu uređaja)
- Minimalistički — ime salona, slika, termini, forma

Forma:
- Ime klijenta
- Broj telefona (WhatsApp preferred)
- Usluga (dropdown iz salon konfiga)
- Datum + sat (calendar picker)
- Napomena (opcionalno)
- Submit → WhatsApp potvrda klijentu + notifikacija vlasniku

### Faza 2: Instagram Embed Widget (1-2 dana)

Embed kod za Instagram bio link:
```html
<!-- Vlasnica kopira ovo u Link in Bio builder (Linktree, etc.) -->
<a href="https://limit-connect.com/beauty/book/salon-naziv/">
  📅 Rezerviraj termin
</a>
```

Direktan link format: `https://limit-connect.com/beauty/book/<slug>/`
- Optimiziran za mobile (Instagram in-app browser)
- Brzo učitavanje (<2s) — Instagram korisnici nemaju strpljenja
- OG tags za share preview: "Rezerviraj u [Salon Naziv]"

### Faza 3: QR Print-Ready (1 dan)

URL: `/beauty/book/<slug>/qr.png`
- QR kod koji se može printati i zalijepiti na ogledalo, čekaonicu, stol
- Automatski generiran iz salon konfiga
- Veličine: A4, A5, sticker (10x10cm)

### Faza 4: Reminder System (1 dan)

- Automatski WhatsApp podsjetnik 2h prije termina
- Format: "Podsjetnik: Termin u [Salon Naziv] danas u 15:00. Otkaži: [link]"
- Koristi postojeći WAHA gateway

## TEHNIČKA IMPLEMENTACIJA

### Model: BeautyBooking (nova app beauty/ ili unutar appointments/)

```python
# PROVJERI PRVO je li appointments/models.py ima što možemo reusati
cat /var/www/fina-connect/appointments/models.py | head -100
```

Ako appointments nema beauty-specific polja, dodati:
```python
class BeautyService(models.Model):
    company = FK(Company)
    name = CharField(max_length=100)  # "Šišanje", "Bojanje", "Manikura"
    duration_minutes = PositiveIntegerField(default=60)
    price = DecimalField()
    is_active = BooleanField(default=True)

class BeautyBooking(models.Model):
    company = FK(Company)
    service = FK(BeautyService)
    client_name = CharField(max_length=200)
    client_phone = CharField(max_length=50)
    datetime = DateTimeField()
    status = CharField(choices=['pending','confirmed','cancelled','completed'])
    notes = TextField(blank=True)
    created_at = DateTimeField(auto_now_add=True)
    reminder_sent = BooleanField(default=False)
```

### Views

```python
# beauty/views.py
def booking_page(request, slug):
    """Javna booking stranica — bez auth"""
    company = get_object_or_404(Company, booking_slug=slug)
    # Dohvati slobodne termine...
    
def booking_submit(request, slug):
    """Kreiranje rezervacije + WhatsApp potvrda"""
    # POST handler
    
def booking_qr(request, slug):
    """QR kod kao PNG"""
    import qrcode
    # Generiraj QR za booking_page URL
```

### Template: templates/beauty/booking_page.html

```html
<!DOCTYPE html>
<html lang="hr">
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <!-- Optimiziran za Instagram in-app browser -->
  <title>Rezerviraj — {{ company.name }}</title>
  <!-- Bootstrap 5 + custom mobile-first CSS -->
</head>
<body>
  <!-- Minimalistički design -->
  <!-- Ime salona, logo, termini, forma -->
  <!-- Dark/light mode auto-detect -->
</body>
</html>
```

### URLs

```python
# beauty/urls.py ili dodati u core/urls.py
path('beauty/book/<slug:salon_slug>/', views.booking_page, name='beauty_book'),
path('beauty/book/<slug:salon_slug>/submit/', views.booking_submit, name='beauty_submit'),
path('beauty/book/<slug:salon_slug>/qr.png', views.booking_qr, name='beauty_qr'),
```

### Konfiguracija salona

Dodati BeautyConfig model ili proširiti Company.settings:
```python
# Minimalno što vlasnica treba konfigurirati:
{
  "working_hours": {"mon": "09:00-20:00", "tue": "09:00-20:00", ...},
  "slot_duration_minutes": 60,
  "services": [...],
  "booking_lead_time_hours": 2,  # min 2h unaprijed
  "max_advance_days": 14,
}
```

## TESTNI SCENARIJ

1. Vlasnica konfigurira salon (10 min)
2. Kopira link u Instagram bio
3. Klijent otvara Instagram, klika link, rezervira za sutra u 15:00
4. Vlasnica dobiva WhatsApp: "Nova rezervacija: Maja, Šišanje, sutra 15:00"
5. Klijent dobiva WhatsApp potvrdu: "Potvrđeno: Šišanje u [Salon] sutra 15:00"
6. Dan prije: Klijent dobiva podsjetnik 2h prije
7. Vlasnica može otkazati/potvrditi iz svog dashboarda

## PILOTNI SALON

Pronaći 1-3 frizera/beauty salona u Slavoniji za beta test.
Ivan ima kontakte — pitati.

## VERIFIKACIJA

```bash
# Test da public page radi bez auth
curl -s -o /dev/null -w "%{http_code}" https://limit-connect.com/beauty/book/test-salon/
# Očekivano: 200 (ne 302 redirect na login)

# Test QR generiranja  
curl -s -o /dev/null -w "%{http_code}" https://limit-connect.com/beauty/book/test-salon/qr.png
# Očekivano: 200
```

## COMMIT

```bash
git add beauty/ templates/beauty/ core/urls.py
git commit -m "feat(beauty): Instagram booking widget + QR print-ready

Public /beauty/book/<slug>/ bez autentifikacije.
Mobile-first, dark/light mode, WhatsApp potvrda i podsjetnik.
QR kod za print (A4, A5, sticker format).
Tržište: 10.800 beauty salona/frizera u HR."
```

---
# STATUS: PLANIRA SE — kreirati CC_TASK KADA je P0.1-P0.5 DONE
# Ovaj task ide NAKON go-live, ne prije
# Slijedi: CC_TASK_FSM_POLICY_EXPORT.md (H2.3)
