## PRVO PROCITAJ STATUS
```bash
cat /var/www/fina-connect/FENIX_STATUS.md
```

# Gemini Task — Fitness modul: implementacija 10/10

## Status
Prethodni task (GEMINI_TASK_FITNESS_10.md) nije završen — GEMINI_FITNESS_PLAN.md ne postoji.
Ovaj task je nastavak + konkretna implementacija.

## KORAK 0 — Pročitaj što postoji
```bash
cat /var/www/fina-connect/fitness/models.py
cat /var/www/fina-connect/fitness/views.py
cat /var/www/fina-connect/fitness/urls.py
ls /var/www/fina-connect/templates/fitness/
```

## Trenutno stanje
fitness/models.py ima samo:
- Member (basic polja + membership_type + RFID)
- MemberCheckIn

Nedostaje: MembershipPlan, MemberSubscription, Payment, WorkoutClass, ClassBooking, Equipment

## KORAK 1 — Napiši GEMINI_FITNESS_PLAN.md
Format:
```
# Fitness modul — plan za 10/10
## Trenutno: X/10
## Što dodajemo (P1/P2/P3)
## Integracije (Invoice, POS, WhatsApp)
## Procjena: X dana
```

## KORAK 2 — Dodaj modele u fitness/models.py

### MembershipPlan
- name, price (Decimal), duration_days, billing_period (monthly/quarterly/yearly)
- auto_renew (bool), grace_period_days, discount_percent
- company FK

### MemberSubscription
- clan FK na Member, plan FK
- valid_from, valid_until, status (draft/active/grace/suspended/cancelled)
- evaluate_status() metoda (state machine)
- payment_reference

### Payment
- member FK, amount, method (cash/card/transfer/pos), date
- invoice_number, note
- linked_subscription FK (nullable)

### WorkoutClass
- name, instructor, capacity, scheduled_at (DateTimeField)
- location, duration_minutes, class_type (yoga/crossfit/pilates/...)
- company FK

### ClassBooking
- member FK, workout_class FK, booked_at, status (booked/cancelled/attended)
- Unique together (member, workout_class)

### Equipment
- name, serial_number, purchase_date, last_service_date
- status (ok/needs_service/broken), location, company FK

## KORAK 3 — Migracije
```bash
cd /var/www/fina-connect
venv/bin/python manage.py makemigrations fitness
venv/bin/python manage.py migrate fitness
```

## KORAK 4 — Views za nove modele
Dodaj u fitness/views.py:
- subscription_list, subscription_create
- payment_list, payment_create  
- workout_class_list, workout_class_create, class_booking
- equipment_list

## KORAK 5 — Test simulacija
Napiši management command `fitness/management/commands/sim_fitness.py`:
- 1 Company (Fitness Centar Test)
- 2 MembershipPlan (Basic 30 EUR/mj, Premium 60 EUR/mj)
- 10 Member-a
- MemberSubscription za svakog
- 3 WorkoutClass (Yoga 9:00, CrossFit 18:00, Pilates 20:00)
- ClassBooking (nekoliko rezervacija)
- 5 Equipment stavki

## KORAK 6 — Testovi
Napiši fitness/tests.py s minimum 10 testova:
- Kreiranje Member, MembershipPlan, MemberSubscription
- evaluate_status() state machine
- WorkoutClass kapacitet + booking
- Equipment servisni status

## Definicija DONE
- [ ] GEMINI_FITNESS_PLAN.md postoji
- [ ] 6 novih modela u fitness/models.py
- [ ] Migracije uspješne
- [ ] sim_fitness command radi
- [ ] 10+ testova prolazi
- [ ] Napiši /tmp/fitness_done.txt s "DONE"
