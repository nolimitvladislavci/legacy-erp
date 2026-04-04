# CC_TASK: BARF MARKETPLACE 10/10
# Datum: 04.04.2026. | Rok: 05.04.2026. | Prioritet: P0
# Views postoje. Templates postoje ali su ~6/10. Idemo 10/10.

PRAVILO: READ models.py PRVO. base.html, .env NE DIRAS.

## KORAK 1 — PROVJERI
```bash
wc -l templates/memio_pet/barf_listings.html templates/memio_pet/barf_create.html templates/memio_pet/pet_hotel_booking.html templates/memio_pet/training_list.html
grep -n "def barf\|def pet_hotel\|def training\|def dog_training" memio_pet/views.py | head -20
grep -n "^    path" memio_pet/urls.py | head -20
grep -n "class RawFoodListing\|class PetBoardingReservation\|class DogTrainingSession" memio_pet/models.py
```

## KORAK 2 — BARF LISTINGS 10/10
READ: templates/memio_pet/barf_listings.html (komplet)
READ: memio_pet/models.py (RawFoodListing fields + PRODUCT_CHOICES)

Nadogradi template — dodaj:
- Hero header: "🥩 BARF Marketplace — Sirova hrana direktno od OPG-a"
- Filter bar: vrsta proizvoda (select), lokacija (text), cijena max (range)
  → HTMX ili simple JS filter na client side
- Svaka kartica: emoji po vrsti (🐔 pilić, 🐑 janjetina, 🐟 riba, 🐄 govedina...)
- Badge: K3 certifikat ✓, Bez antibiotika ✓, Slobodan uzgoj ✓
- "Kontaktiraj OPG" button → WhatsApp link (wa.me/{phone}) ili email
- Prazna lista: "Nema ponuda. Jeste li OPG? Dodajte svoju." → /memio/barf/nova/
- Map hint: "Prikazujem ponude u radijusu 50km" (samo tekst, bez API-ja)

## KORAK 3 — BARF CREATE 10/10
READ: templates/memio_pet/barf_create.html
READ: memio_pet/views.py (barf_create view, ~linija 228)

Nadogradi:
- Hero: "Prodajte sirovu hranu direktno uzgajivačima ljubimaca"
- Form: product_type select s emoji labelama iz PRODUCT_CHOICES
- Quantity + price → live kalkulator: "Prihod: X EUR"
- K3 cert broj + tooltip (što je K3 = sanitarni certifikat)
- Submit → success page s "Vaša ponuda je živa! Podijelite link:"
  + copy link button + WhatsApp share button

## KORAK 4 — PET HOTEL BOOKING 10/10
READ: templates/memio_pet/pet_hotel_booking.html (182 linije — provjeri što piše)
READ: memio_pet/models.py (PetBoardingReservation fields)
READ: memio_pet/views.py (pet_hotel_booking view)

Nadogradi:
- Hero: "🏨 Pet Hotel — Sigurno čuvanje vašeg ljubimca"
- Lista hotela: kartica po hotelu s ocjenom, grad, cijena/noć, kapacitet
- Forma: datum_in/datum_out → live calc broja noći i ukupne cijene
- Posebne napomene: prehrana, lijekovi, karakter (3 textarea)
- Submit → potvrda na email + WhatsApp vlasniku
- GDPR notice: "Vaši podaci koriste se samo za ovu rezervaciju"

## KORAK 5 — TRAINING LIST 10/10
READ: templates/memio_pet/training_list.html
READ: memio_pet/views.py (postoji li dog_training_list view? ako ne — kreiraj)

Nadogradi/kreiraj:
- Lista kinologa: kartica s imenom, gradom, tipovima treninga, cijenom/sat
- Filter: tip treninga (agility, osnovna, zaštitar...)
- Svaki kinolog: "Rezerviraj termin" → Appointments link ili forma

Ako view ne postoji, dodaj u memio_pet/views.py:
```python
def dog_training_list(request):
    from memio_pet.models import BreederProfile
    trainers = BreederProfile.objects.filter(
        account_type='trainer', is_cro_validated=True
    ).order_by('city', 'name')
    return render(request, 'memio_pet/training_list.html', {
        'trainers': trainers,
        'page_title': 'Kinolozi i dresura pasa',
    })
```
I dodaj URL u memio_pet/urls.py:
```python
path("dresura/", views.dog_training_list, name="dog_training_list"),
```

## KORAK 6 — SIDEBAR/NAV LINKOVI
READ: templates/base.html ili sidebar partial
Provjeri postoji li BARF / Pet Hotel u navigaciji.
Ako ne — dodaj pod "memio.pet" sekciju:
  🥩 BARF Marketplace | 🏨 Pet Hotel | 🐕 Dresura

## KORAK 7 — VERIFY
```bash
venv/bin/python manage.py check 2>&1 | tail -3
systemctl restart gunicorn-fina && sleep 2
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/hr/memio/barf/
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/hr/memio/dresura/ 2>/dev/null || echo "URL ne postoji"
git add -A && git commit -m "feat(barf-10-10): BARF, Pet Hotel, Dresura templates upgrade"
```

DONE: [ ] barf_listings 10/10 [ ] barf_create 10/10 [ ] pet_hotel_booking 10/10 [ ] training_list 10/10 [ ] nav linkovi
