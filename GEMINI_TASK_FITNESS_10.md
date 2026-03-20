# Gemini Task — Fitness modul: audit i plan za 10/10

## Što postoji (pročitaj sve)
```bash
cat /var/www/fina-connect/fitness/models.py
cat /var/www/fina-connect/fitness/views.py
cat /var/www/fina-connect/fitness/urls.py
ls /var/www/fina-connect/templates/fitness/
cat /var/www/fina-connect/core/tests_fitness_data.py
```

## Što fitness centar STVARNO treba (10/10 standard)

### Modeli koji nedostaju
Pročitaj models.py pa dodaj što nedostaje:

1. **MembershipPlan** — planovi s cijenama, trajanjem, benefitima
2. **MembershipSubscription** — vezuje Member na Plan, datum početka/kraja, status plaćanja
3. **Payment** — uplata (gotovina/kartica/transfer), iznos, datum, za koji subscription
4. **WorkoutClass** — grupni treninzi (Yoga, CrossFit, Pilates...), instruktor, kapacitet, termin
5. **ClassBooking** — rezervacija klase od strane člana
6. **Equipment** — oprema (sprava), servis, stanje
7. **BodyMeasurement** — tjelesne mjere člana kroz vrijeme (težina, BMI, % masti)
8. **PersonalTrainer** — trener, specijalizacija, cijena/sat
9. **PTSession** — session s osobnim trenerom
10. **AccessLog** — RFID/QR pristup, terminal, ulaz/izlaz (prošireni CheckIn)

### Poslovne funkcije koje nedostaju
- **Automatsko upozorenje** kad membership ističe (3 dana, 1 dan)
- **Zamrzavanje** membership (npr. zbog ozljede) — extend expiry
- **QR kod** za člana (za brzi check-in bez kartice)
- **Statistike** — posjećenost po danu/satu, najpopularnije klase
- **Financijski izvještaj** — prihodi po planu, outstanding dugovi
- **Waitlist** za pune klase
- **Online booking** link (javna stranica za klase)

### Što Gemini treba napraviti

#### Korak 1 — Pročitaj sve postojeće fajlove
#### Korak 2 — Napiši plan (GEMINI_FITNESS_PLAN.md)

Format plana:
```
# Fitness modul — plan za 10/10

## Trenutno stanje: X/10
## Razlozi:

## Što dodajemo (prioritet):
### P1 — Kritično (bez toga ne funkcionira)
### P2 — Važno (značajno poboljšanje)
### P3 — Nice-to-have

## Arhitekturne odluke:
- Kako integrirati s postojećim Partners modulom
- Kako integrirati s Payment/Invoice modulom
- Kako integrirati s Notifications (WhatsApp)

## Procjena rada: X dana
```

#### Korak 3 — Implementiraj P1 stavke

**Minimalno P1:**

a) Dodaj u fitness/models.py:
```python
class MembershipPlan(models.Model):
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE)
    name = models.CharField(max_length=100)  # "Mjesečni Basic", "Godišnji Premium"
    duration_days = models.IntegerField(default=30)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    sessions_per_week = models.IntegerField(null=True, blank=True)  # None = unlimited
    includes_classes = models.BooleanField(default=False)
    includes_pt = models.IntegerField(default=0)  # broj PT sessiona
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['price']

class MembershipSubscription(models.Model):
    STATUS = [('active','Aktivna'),('expired','Istekla'),('frozen','Zamrznuta'),('cancelled','Otkazana')]
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='subscriptions')
    plan = models.ForeignKey(MembershipPlan, on_delete=models.PROTECT)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS, default='active')
    price_paid = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, default='cash')
    frozen_from = models.DateField(null=True, blank=True)
    frozen_days = models.IntegerField(default=0)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def is_valid(self):
        from django.utils import timezone
        return self.status == 'active' and self.end_date >= timezone.now().date()

    def freeze(self, from_date=None):
        from django.utils import timezone
        self.frozen_from = from_date or timezone.now().date()
        self.status = 'frozen'
        self.save()

    def unfreeze(self):
        from django.utils import timezone
        if self.frozen_from:
            days = (timezone.now().date() - self.frozen_from).days
            self.frozen_days += days
            from datetime import timedelta
            self.end_date += timedelta(days=days)
            self.frozen_from = None
        self.status = 'active'
        self.save()
```

b) Migracija:
```bash
cd /var/www/fina-connect
venv/bin/python manage.py makemigrations fitness --name fitness_plans_subscriptions
venv/bin/python manage.py migrate fitness
```

c) Dodaj view za novu pretplatu (fitness/views.py):
```python
@login_required
def subscription_create(request, member_pk):
    # Form za kreiranje pretplate za člana
    # Odabir plana, datum početka, način plaćanja
    pass
```

d) Dodaj URL:
```python
path('<int:pk>/subscription/new/', views.subscription_create, name='subscription_create'),
path('plans/', views.plan_list, name='plan_list'),
path('plans/new/', views.plan_create, name='plan_create'),
```

e) Dashboard statistike (checkin_dashboard view):
Dodaj u context:
- Aktivni članovi danas
- Checkini danas po satu (chart data)
- Membership koji ističu u 7 dana (upozorenje)
- Prihod ovaj mjesec

#### Korak 4 — Celery task za expiry upozorenja
U fitness/tasks.py (novi fajl):
```python
from celery import shared_task

@shared_task
def check_expiring_memberships():
    """Svaki dan u 09:00 — upozori za membership koji ističe za 3 dana."""
    from datetime import date, timedelta
    from fitness.models import MembershipSubscription
    from core.whatsapp import send_text  # ili email

    target = date.today() + timedelta(days=3)
    expiring = MembershipSubscription.objects.filter(
        end_date=target, status='active'
    ).select_related('member')

    for sub in expiring:
        member = sub.member
        if member.phone:
            send_text(member.phone,
                f"Podsjetnik: vaše članstvo ističe {sub.end_date.strftime('%d.%m.%Y')}. "
                f"Kontaktirajte nas za obnovu.")
```

Dodaj u celery beat schedule (settings.py):
```python
'fitness-expiry-check': {
    'task': 'fitness.tasks.check_expiring_memberships',
    'schedule': crontab(hour=9, minute=0),
},
```

#### Korak 5 — Provjere
```bash
cd /var/www/fina-connect
venv/bin/python manage.py check 2>&1 | tail -2
venv/bin/python manage.py showmigrations fitness 2>&1 | tail -5
grep -c "class " fitness/models.py
```

## Format javljanja
```
GEMINI_FITNESS_PLAN.md kreiran: DA/NE
Modeli dodani: MembershipPlan, MembershipSubscription (DA/NE)
Migracija aplicirana: DA/NE
Django check: 0 issues (DA/NE)
Ocjena nakon P1: X/10
```
