# CC_TASK_EXPERIENCES_TEMPLATES.md
# Dodijeljen: CC Code (server + lokalno)
# Prioritet: KRITIČNO — Krater #1
# Datum: 2026-03-28
# Procjena: 3-4h
#
# KONTEKST: experiences/ app ima 23 viewa, 9 modela, 19 URL-ova — sve radi.
# Problem: /var/www/fina-connect/templates/experiences/ DIR NE POSTOJI.
# Nijedan korisnik ne može pristupiti ičemu. Ovo je top prioritet.
#
# PRAVILO 1: Sve template nasljeđuje base.html ({% extends "base.html" %})
# PRAVILO 2: Bootstrap 5.3 dark theme — tablica table-dark, kartice bg-dark border-secondary
# PRAVILO 3: Font Awesome 6.5 ikone
# PRAVILO 4: Konzistentan pattern: header (naslov + CTA btn) → filter bar → stats row → sadržaj
# PRAVILO 5: Stvori dir: mkdir -p /var/www/fina-connect/templates/experiences/

---

## KORAK 0 — Priprema direktorija

```bash
mkdir -p /var/www/fina-connect/templates/experiences/
```

---

## TEMPLATE 1: experiences/experience_list.html

Context varijable iz views.py:
- `page` — Page objekt (Experience queryset, 25/stranici)
- `q` — string, search query
- `exp_type` — string, filter po tipu
- `stats` — dict: {ukupno, aktivnih, avg_rating}
- `type_choices` — Experience.TYPE_CHOICES lista

Što prikazati:
1. Header: "Iskustva / Aktivnosti" + ikona fas fa-mountain + btn "Novo iskustvo" (link experiences:experience_create)
2. Stats row (3 karte): Ukupno iskustava | Aktivnih | Prosječna ocjena (zvjezdice)
3. Filter form (GET): input q, select type (type_choices), btn Filtriraj, link Resetiraj
4. Tablica: Naziv (link na detail), Tip (badge), Trajanje (min), Max gostiju, Cijena/os (€), Status (is_active badge), Akcije (Uredi, Uredi raspored)
5. Paginacija standardna Bootstrap

Ikone po tipu iskustva:
- degustacija: fa-wine-glass-alt (gold)
- radionica: fa-chalkboard-teacher (blue)
- berba: fa-seedling (green)
- tura: fa-map-marked-alt (cyan)
- jahanje: fa-horse (brown/amber)
- promatranje: fa-binoculars (purple)
- muznja: fa-cow (light)
- kulinarska: fa-utensils (orange)
- wellness: fa-spa (pink)
- ostalo: fa-star (secondary)

Empty state: fa-mountain-sun, "Još nema iskustava — kreirajte prvo!"

---

## TEMPLATE 2: experiences/experience_detail.html

Context varijable:
- `experience` — Experience objekt (sva polja)
- Relacioni: schedules (budući), recent bookings, reviews

Layout (2-stupac):
LIJEVO (col-lg-4):
  - Karta s info: Tip, Trajanje, Kapacitet (min/max pax), Težina, Vodič, Jezici, GPS (ako postoje)
  - Karta Cijena: price_per_person, child_discount_pct, deposit_pct (deposit_amount property), cancellation_hours, tax_rate
  - Karta Sezona: seasonal_from/until ili "Cijelu godinu"

DESNO (col-lg-8):
  - Tab navigacija: Opis | Raspored | Rezervacije | Recenzije
  - Tab Opis: description + what_to_bring
  - Tab Raspored: lista schedules (datum, vrijeme, spots available, status badge) + btn "Dodaj termin"
  - Tab Rezervacije: tablica bookings (gost, termin, pax, status, cijena, akcije check-in/complete)
  - Tab Recenzije: prosječna ocjena (zvjezdice) + lista reviews

Action buttons (header):
  - "Uredi" → experiences:experience_edit
  - "Novi termin" → experiences:schedule_create
  - "BOM Normativ" → experiences:normativ_preview (nova kartica, target=_blank)
  - "Natrag" → experiences:experience_list

---

## TEMPLATE 3: experiences/experience_form.html

Context varijable:
- `type_choices` — Experience.TYPE_CHOICES
- `difficulty_choices` — Experience.DIFFICULTY_CHOICES
- `experience` — (opcijsko, za edit mode)

Layout forma (2-kolone):
SEKCIJA 1 "Osnovno":
  - name (text, required)
  - experience_type (select, TYPE_CHOICES, required)
  - description (textarea, 4 reda)
  - what_to_bring (textarea, 3 reda)

SEKCIJA 2 "Logistika":
  - duration_minutes (number, required, placeholder "90")
  - capacity (number, required)
  - min_pax (number, default 1)
  - difficulty (select, DIFFICULTY_CHOICES)
  - meeting_point (text)
  - guide_languages (text, placeholder "hr,en,de")

SEKCIJA 3 "Cijena & Porez":
  - price_per_person (decimal, required, addon "€")
  - child_discount_pct (number, addon "%", default 50)
  - deposit_pct (number, addon "%", default 30)
  - cancellation_hours (number, addon "sati", default 12)
  - tax_rate (select: 25% PDV, 13% ugostiteljstvo, 5% povlaštena, 0% oslobođeno)

SEKCIJA 4 "Sezona" (opcionalna):
  - seasonal_from (date)
  - seasonal_until (date)

Submit: "Spremi iskustvo" (btn-warning) | "Odustani" (btn-outline-secondary → list)

---

## TEMPLATE 4: experiences/booking_form.html

Context varijable:
- `schedule` — ExperienceSchedule objekt
- `schedule.experience` — Experience

Header: "Rezervacija: {schedule.experience.name}" + datum/vrijeme termina

Info karta termina (readonly):
  - Datum i vrijeme, dostupnih mjesta (available_spots), status badge

Forma:
  - guest_name (text, required)
  - guest_email (email)
  - guest_phone (tel)
  - guest_country (text, placeholder "HR / DE / AT")
  - pax_count (number, 1..schedule.max_pax, required)
  - children_count (number, 0..pax_count)
  - payment_method (select: card/cash/transfer/online)
  - notes (textarea, 2 reda)

Kalkulacija cijene (JS, live update):
  - Odrasli × price_per_person
  - Djeca × (price_per_person × child_discount/100)
  - Ukupno, Depozit (deposit_pct%)
  - Prikaži u info boks: "Depozit za plaćanje: X,XX €"

Submit: "Potvrdi rezervaciju" (btn-success)

---

## TEMPLATE 5: experiences/schedule_form.html

Context varijable:
- `experience` — Experience objekt

Header: "Novi termin — {experience.name}"

Forma:
  - date (date, required)
  - time_from (time, required)
  - time_to (time, required — auto-fill: time_from + duration_minutes)
  - max_pax (number, default experience.capacity)
  - weather_note (text, placeholder "Otkazuje se u slučaju kiše")

Info hint: "Min gostiju za održavanje: {experience.min_pax}"

Submit: "Dodaj termin" (btn-primary) | "Natrag na iskustvo" (outline)

JS: auto-fill time_to = time_from + duration_minutes

---

## TEMPLATE 6: experiences/package_list.html

Context varijable:
- `packages` — AgroPackage queryset
- `stats` — dict

Header: "Agro Paketi" + ikona fa-box-open + btn "Novi paket"

Stats (2 karte): Ukupno paketa | Aktivnih paketa

Tablica: Naziv paketa, Broj komponenti, Osnovna cijena (€), Status badge, Akcije (Detalji, Uredi)

Empty state: "Kreirajte prvi agro-turistički paket — kombinirajte smještaj, aktivnosti i proizvode."

---

## TEMPLATE 7: experiences/package_detail.html

Context varijable:
- `package` — AgroPackage objekt
- `components` — PackageComponent lista (FK na package)

Layout (2-stupac):
LIJEVO: Karta s opisom paketa, ukupna cijena, PDV breakdown
DESNO: Lista komponenti (tip, naziv, količina, cijena, PDV stopa) + Tax Splitter info

Akcija "PDV Razdvajanje" → HTMX ili link na package_tax_breakdown (prikaz u modalu)

---

## TEMPLATE 8: experiences/package_form.html

Context varijable:
- `package` — (opcijsko za edit)
- `experience_list` — dostupni Experience objekti iste kompanije

Forma:
  - name (text, required)
  - description (textarea)
  - is_active (checkbox)

Komponente (dinamično dodavanje JS-om):
  - component_type (select: experience/accommodation/product/service)
  - quantity (number)
  - unit_price (decimal)
  - tax_rate (number)
  - notes (text)
  - [+ Dodaj komponentu] gumb

Prikaži running total dok se dodaju komponente.

---

## TEMPLATE 9: experiences/recall_list.html

Context varijable:
- `recalls` — RecallEvent queryset
- `stats` — dict (ukupno, aktivnih, riješenih)

HACCP kontekst — ovo je ozbiljan prikaz, ne igračka.

Header: "HACCP Recall — Povlačenje proizvoda" + ikona fa-exclamation-triangle (text-danger)

Alert banner ako postoje aktivni recalls: "⚠️ AKTIVNIH POVLAČENJA: {N}" — crveni alert

Stats (3 karte s bojama): Ukupno | Aktivnih (danger) | Riješenih (success)

Tablica: Datum, Naziv recall-a, Razlog, Status badge (danger/warning/success), Broj obavijesti, Akcije (Detalji, Traceability, Obavijesti)

---

## TEMPLATE 10: experiences/recall_detail.html

Context varijable:
- `recall` — RecallEvent objekt
- `notifications` — RecallNotification queryset

Layout:
Lijevo: Info o recall-u (razlog, datum, opis, status, pogođeni artikl)
Desno: Lista obavijesti (gost, kanal, sent_at, status)

Akcije:
  - "Trace (Traceability)" → recall:recall_trace
  - "Pošalji obavijesti" → recall:recall_notify (POST form s potvrdom)
  - "Zatvori recall" (ako je open)

---

## TEMPLATE 11: experiences/recall_form.html

Header: "Novi HACCP Recall"

Forma:
  - title (text, required)
  - reason (textarea, required)
  - affected_date_from (date)
  - affected_date_to (date)
  - description (textarea)
  - severity (select: low/medium/high/critical)

Warning box: "Pokretanjem recall-a aktivira se HACCP reverse traceability. Sustav će identificirati sve goste koji su konzumirali pogođeni proizvod u navedenom periodu."

Submit: "Pokreni Recall" (btn-danger, s confirm dijalogom)

---

## TEMPLATE 12: experiences/review_form.html

Context varijable:
- `booking` — ExperienceBooking objekt (sa schedule.experience)

Header: "Ocjenite vaše iskustvo: {booking.schedule.experience.name}"

Info karta: termin, datum posjeta, vaše ime

Forma:
  - rating (1-5 zvjezdica — CSS star picker, ne select)
  - title (text, placeholder "Kratki naslov recenzije")
  - comment (textarea, 4 reda)

CSS star rating:
  - 5 radio buttona stiliziranih kao zvjezdice (fa-star)
  - Hover efekt — zlatno oboji
  - Readonly ako je već ispunjen review

Submit: "Pošalji recenziju" (btn-warning)

---

## VERIFIKACIJA PO ZAVRŠETKU

```bash
# Provjeri sve fajlove
ls -la /var/www/fina-connect/templates/experiences/

# Test svaki URL (mora returnati 200, ne 500)
cd /var/www/fina-connect && source venv/bin/activate
python manage.py shell -c "
from django.test import RequestFactory, Client
c = Client()
# Login kao superuser pa testiraj URL-ove
print('Templates created:', __import__('os').listdir('templates/experiences/'))
"

# Git commit
cd /var/www/fina-connect
git add templates/experiences/
git commit -m "feat(experiences): create all 12 missing templates — Agro-Turizam 360 visible"
git log --oneline -3
```

## AŽURIRAJ FENIX_STATUS.md

Nakon commita dodaj u sekciju "DEPLOYAN DANAS":
| Experiences Templates | (hash) | 12 templatea kreirana — Agro-Turizam 360 operative |

---
# STATUS: READY_FOR_CC_CODE
# Sljedeći task: CC_TASK_DESIGN_SYSTEM.md
