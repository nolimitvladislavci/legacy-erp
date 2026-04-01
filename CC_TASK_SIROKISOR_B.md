# CC_TASK_SIROKISOR_B — Delivery + Unified Ordering + Distributer arhitektura
**Dodjeljeno:** CC Code Instance B
**Ne dira:** gastro_menu/views.py, setup_sirokisor.py, TableQR, MenuItem (to je zadatak A)
**Čeka:** CC Task A mora biti DONE (trebaju kreirati DigitalMenu, TableQR zapisi) prije B3
**Status:** TODO
**Datum:** 01.04.2026

---

## KONTEKST

Delivery app postoji na `/var/www/fina-connect/delivery/`.
Marketplace/Burza postoji ali je zasebna cjelina.
Company model je u `companies/models.py` — provjeri polja prije pisanja.
Cilj B taska: infrastruktura koja spaja gastro + OPG + dostava u jedan flow.

**PROČITAJ PRIJE PISANJA KODA:**
- `/var/www/fina-connect/delivery/models.py` — što već postoji
- `/var/www/fina-connect/companies/models.py` — Company polja, parent/child relacije
- `/var/www/fina-connect/gastro_menu/models.py` — TableOrder model (FK za delivery)
- `/var/www/fina-connect/marketplace/models.py` — MarketplaceProduct, MarketplaceOrder

---

## ZADATAK B1 — DeliveryZone + DeliveryTask modeli

### Fajl: `delivery/models.py` — DODATI (ne brisati postojeće):

```python
class DeliveryZone(models.Model):
    DELIVERY_TYPE_CHOICES = [
        ('gepek', 'Gepek (osobni automobil)'),
        ('taxi', 'Taxi'),
        ('bus', 'Autobusna linija'),
        ('personal', 'Osobno preuzimanje'),
        ('courier', 'Kurirska služba'),
    ]
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                                related_name='delivery_zones')
    name = models.CharField(max_length=100)       # "Vladislavci", "Osijek centar"
    delivery_type = models.CharField(max_length=20, choices=DELIVERY_TYPE_CHOICES)
    base_price = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    price_per_km = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    max_distance_km = models.PositiveIntegerField(default=30)
    estimated_minutes = models.PositiveIntegerField(default=45)
    is_active = models.BooleanField(default=True)
    partner_driver = models.ForeignKey('partners.Partner', on_delete=models.SET_NULL,
                                       null=True, blank=True)
    # Bus specifično
    bus_departure_times = models.JSONField(default=list, blank=True)
    # ["08:00", "12:00", "16:00", "20:00"]
    bus_line_name = models.CharField(max_length=100, blank=True)

    objects = CompanyManager()

    class Meta:
        verbose_name = 'Zona dostave'
        verbose_name_plural = 'Zone dostave'

    def __str__(self):
        return f"{self.name} ({self.get_delivery_type_display()}) — {self.base_price}€"

    def next_bus_departure(self):
        """Vraća sljedeći polazak busa. None ako nije bus tip."""
        if self.delivery_type != 'bus' or not self.bus_departure_times:
            return None
        from django.utils import timezone
        now = timezone.localtime()
        current_time = now.strftime('%H:%M')
        for t in sorted(self.bus_departure_times):
            if t > current_time:
                return t
        return self.bus_departure_times[0] + ' (sutra)'


class DeliveryTask(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Čeka potvrdu'),
        ('confirmed', 'Potvrđeno'),
        ('preparing', 'Priprema se'),
        ('in_transit', 'U dostavi'),
        ('delivered', 'Dostavljeno'),
        ('missed', 'Propušten (bus/rok)'),
        ('cancelled', 'Otkazano'),
    ]

    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE)
    zone = models.ForeignKey(DeliveryZone, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Što se dostavlja (može biti mixed — jelo + OPG proizvod)
    gastro_order = models.ForeignKey(
        'gastro_menu.TableOrder', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='delivery_tasks'
    )
    marketplace_order = models.ForeignKey(
        'marketplace.MarketplaceOrder', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='delivery_tasks'
    )

    # Primalac
    recipient_name = models.CharField(max_length=100)
    recipient_phone = models.CharField(max_length=20)
    recipient_address = models.TextField()
    recipient_notes = models.TextField(blank=True)

    # Vozač
    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='delivery_tasks'
    )

    # Timing
    scheduled_pickup_at = models.DateTimeField(null=True, blank=True)
    picked_up_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    delivery_proof = models.ImageField(upload_to='delivery/proof/', blank=True, null=True)

    # Financije
    delivery_fee = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    is_paid = models.BooleanField(default=False)
    paid_by = models.CharField(max_length=20, choices=[
        ('cash', 'Gotovina'), ('card', 'Kartica'), ('online', 'Online'), ('voucher', 'Voucher')
    ], default='cash')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = CompanyManager()

    class Meta:
        verbose_name = 'Zadatak dostave'
        verbose_name_plural = 'Zadaci dostave'
        ordering = ['-created_at']

    def __str__(self):
        return f"Dostava #{self.pk} — {self.recipient_name} — {self.get_status_display()}"

    def fsm_transition(self, new_status, user=None):
        """
        Validira FSM prijelaz. Vraća (True, '') ili (False, 'razlog').
        DOZVOLJENI PRIJELAZI:
        pending → confirmed, cancelled
        confirmed → preparing, cancelled
        preparing → in_transit, missed
        in_transit → delivered, missed
        missed → confirmed (retry), cancelled
        """
        TRANSITIONS = {
            'pending':    ['confirmed', 'cancelled'],
            'confirmed':  ['preparing', 'cancelled'],
            'preparing':  ['in_transit', 'missed'],
            'in_transit': ['delivered', 'missed'],
            'missed':     ['confirmed', 'cancelled'],
        }
        allowed = TRANSITIONS.get(self.status, [])
        if new_status not in allowed:
            return False, f"Prijelaz {self.status}→{new_status} nije dozvoljen"
        self.status = new_status
        if new_status == 'picked_up':
            from django.utils import timezone
            self.picked_up_at = timezone.now()
        if new_status == 'delivered':
            from django.utils import timezone
            self.delivered_at = timezone.now()
        self.save()
        return True, ''
```

### Migracija:
```bash
venv/bin/python manage.py makemigrations delivery
venv/bin/python manage.py migrate delivery
```

### Seed data za Široki Šor:
```python
# U zasebnom seed scriptu ili management commandu
# Zone za Korpaš d.o.o.
DeliveryZone.objects.get_or_create(
    company=korpas, name='Vladislavci — Čepin', delivery_type='gepek',
    defaults={'base_price': 3, 'max_distance_km': 15, 'estimated_minutes': 25}
)
DeliveryZone.objects.get_or_create(
    company=korpas, name='Osijek centar', delivery_type='gepek',
    defaults={'base_price': 5, 'max_distance_km': 30, 'estimated_minutes': 45}
)
DeliveryZone.objects.get_or_create(
    company=korpas, name='Bus linija OS-ĐK', delivery_type='bus',
    defaults={'base_price': 2, 'bus_departure_times': ['08:00','12:00','16:00','20:00'],
              'bus_line_name': 'Osijek—Đakovo', 'estimated_minutes': 90}
)
DeliveryZone.objects.get_or_create(
    company=korpas, name='Osobno preuzimanje', delivery_type='personal',
    defaults={'base_price': 0, 'estimated_minutes': 0}
)
```

---

## ZADATAK B2 — Distributer arhitektura (Company hierarchy)

### Problem koji rješava:
Distributer iz Splita treba biti "umbrella" nad lokalnim OPG-ovima i restoranima.
OPG-ovi ostaju naši tenanti — distributer ih ne posjeduje.

### Provjeri companies/models.py — ako nema parent FK, dodati:

```python
# U Company modelu — ako već ne postoji:
parent_company = models.ForeignKey(
    'self', on_delete=models.SET_NULL,
    null=True, blank=True,
    related_name='subsidiaries',
    verbose_name='Umbrella kompanija'
)
company_role = models.CharField(max_length=20, choices=[
    ('standalone', 'Samostalna'),
    ('umbrella', 'Distributer/Umbrella'),
    ('subsidiary', 'Pod-kompanija'),
    ('franchise', 'Franšiza'),
], default='standalone')
```

Ako Company model već ima parent relaciju s drugim imenom — koristi to, ne dupliciraj.

### Permission boundary za FINA certifikate:
U `core/permissions.py` ili gdje su definirani permissioni:
```python
def can_access_fina_cert(user, company):
    """
    Distributer (umbrella) NE SMIJE pristupiti FINA certifikatu
    pod-kompanija. Samo direktni company admin ili superadmin.
    """
    if user.is_superuser:
        return True
    profile = user.core_userprofile
    if profile.company == company:
        return True
    # Umbrella ima pristup podacima ali NE certifikatima
    return False
```

### Distributerski ugovor template (Markdown):
Kreirati fajl `/var/www/fina-connect/docs/distributer_ugovor_template.md`:
```markdown
# Ugovor o distribuciji LIMIT Connect platforme

## Članak 5. — Vlasništvo podataka i tenanci
Sve kompanije onboardane kroz Distributera ostaju isključivi tenanti
LIMIT Connect platforme (Konjik d.o.o.). Distributer nema vlasnička
ni pristupna prava na podatke, FINA certifikate ni financijske
zapise tih kompanija.

## Članak 6. — Zabrana konkurencije
U roku od 12 (dvanaest) mjeseci od prestanka ovog Ugovora,
Distributer se obvezuje da neće direktno ni indirektno nuditi
identičnu ili bitno sličnu SaaS uslugu onboardanim tenantima.

## Članak 7. — Provizija
Distributer zadržava [5-8]% od svake transakcije na Burzi i
[X]€ od svake dostave naplaćene krajnjem korisniku.
LIMIT Connect (Konjik d.o.o.) zadržava 2% od svake transakcije
+ fiksna pretplata [49]€/mj.
```

---

## ZADATAK B3 — Unified Ordering Page (čeka Task A DONE)

**Preduvjet:** Task A mora biti završen (DigitalMenu i TableQR moraju postojati u bazi).

### URL: `/gastro/order/<slug>/` ili `/naruci/<slug>/`

### Što prikazuje:
Jedna mobilna stranica koja agregira:
1. **Jela iz Gastro menija** (MenuItem.is_available = True) — iz gastro_menu
2. **OPG proizvodi dostupni za narudžbu** (MarketplaceProduct.is_available = True, company u istoj regiji) — iz marketplace

### View logika:
```python
def unified_order_view(request, slug):
    menu = get_object_or_404(DigitalMenu, slug=slug, is_active=True)
    company = menu.company

    # Gastro stavke
    gastro_items = MenuItem.objects.filter(
        category__menu=menu,
        is_available=True
    ).select_related('category').order_by('category__sort_order', 'sort_order')

    # OPG proizvodi (marketplace) — samo isti company ili partneri
    from marketplace.models import MarketplaceProduct
    opg_products = MarketplaceProduct.objects.filter(
        company=company,
        is_available=True
    ).order_by('category', 'name')[:20]  # limit za V1

    # Delivery zone za ovaj company
    delivery_zones = DeliveryZone.objects.filter(
        company=company, is_active=True
    ).order_by('base_price')

    return render(request, 'gastro/unified_order.html', {
        'menu': menu,
        'gastro_items': gastro_items,
        'opg_products': opg_products,
        'delivery_zones': delivery_zones,
    })
```

### POST /gastro/order/<slug>/submit/
Orkestrira narudžbu i RAZDVAJA:
```python
def submit_unified_order(request, slug):
    data = json.loads(request.body)
    gastro_items = data.get('gastro_items', [])
    opg_items = data.get('opg_items', [])
    delivery_zone_id = data.get('delivery_zone_id')
    recipient = data.get('recipient', {})

    # 1. Kreiraj GastroOrder ako ima gastro stavki
    gastro_order = None
    if gastro_items:
        gastro_order = TableOrder.objects.create(
            table_qr=...,  # ili None za takeaway
            company=company,
            items=gastro_items,
            total=sum(item['price'] * item['qty'] for item in gastro_items),
            status='new'
        )

    # 2. Kreiraj MarketplaceOrder ako ima OPG stavki
    marketplace_order = None
    if opg_items:
        # TODO: kreirati MarketplaceOrder — provjeri marketplace/models.py za točan model
        pass

    # 3. Kreiraj DeliveryTask koji spaja oboje
    if delivery_zone_id and (gastro_order or marketplace_order):
        zone = DeliveryZone.objects.get(id=delivery_zone_id, company=company)
        DeliveryTask.objects.create(
            company=company,
            zone=zone,
            gastro_order=gastro_order,
            marketplace_order=marketplace_order,
            recipient_name=recipient.get('name', 'Gost'),
            recipient_phone=recipient.get('phone', ''),
            recipient_address=recipient.get('address', 'Preuzimanje u lokalu'),
            delivery_fee=zone.base_price,
            status='pending'
        )

    return JsonResponse({
        'ok': True,
        'gastro_order_id': gastro_order.id if gastro_order else None,
        'message': 'Narudžba primljena!'
    })
```

### Template: `templates/gastro/unified_order.html`
- Mobilni-first (max-width 420px, centrirano)
- Dvije sekcije: "Jela" + "OPG Proizvodi" (ako ima)
- Košarica u footeru s totalnom cijenom + dostava
- Odabir zone dostave (radio buttons)
- Submit button → fetch POST → redirect na potvrdu

---

## ZADATAK B4 — WhatsApp notifikacije za dostavu

### Kad se kreira DeliveryTask:
```python
# U delivery/signals.py ili u view odmah nakon save():
from core.whatsapp import send_whatsapp  # provjeri točan import

def notify_new_delivery(task):
    # Obavijest kuharu/blagajniku
    msg = (
        f"🛵 NOVA NARUDŽBA ZA DOSTAVU\n"
        f"#{task.pk} — {task.recipient_name}\n"
        f"Zona: {task.zone.name}\n"
        f"Dostava: {task.zone.base_price}€\n"
        f"Napomena: {task.recipient_notes or '—'}"
    )
    # Pošalji na WAHA broj kompanije
    send_whatsapp(task.company.whatsapp_number, msg)
```

### Kad se status promijeni u 'missed':
```python
def notify_missed_delivery(task):
    msg = (
        f"⚠️ PROPUŠTENA DOSTAVA #{task.pk}\n"
        f"Gost: {task.recipient_name} {task.recipient_phone}\n"
        f"Opcije: sljedeći bus ili otkazati?"
    )
    send_whatsapp(task.company.whatsapp_number, msg)
```

Provjeri `/var/www/fina-connect/core/` za točan WhatsApp utility modul.

---

## PROVJERA DOPO ZAVRŠETKU:

```bash
# Migracije OK
venv/bin/python manage.py migrate --check

# Modeli u bazi
venv/bin/python manage.py shell -c "
from delivery.models import DeliveryZone, DeliveryTask
print('DeliveryZone:', DeliveryZone.objects.count())
print('DeliveryTask:', DeliveryTask.objects.count())
"

# URL radi (čeka Task A)
# curl http://localhost:8000/gastro/order/sirokisor/

# Test FSM
venv/bin/python manage.py shell -c "
from delivery.models import DeliveryTask, DeliveryZone
from companies.models import Company
c = Company.objects.get(name='Korpaš d.o.o.')
z = DeliveryZone.objects.filter(company=c).first()
print('Zone:', z)
"
```

---

## GIT COMMIT NA KRAJU:
```bash
git add -A
git commit -m "feat(delivery): DeliveryZone + DeliveryTask FSM, unified ordering, distributer arhitektura"
git log --oneline -3
```
Zatim update FENIX_STATUS.md.

---

## KOORDINACIJA S TASK A:

Task A i B se ne smiju dirati u iste fajlove. Granica:

| Fajl | Task A | Task B |
|---|---|---|
| gastro_menu/models.py | READ ONLY | READ ONLY |
| gastro_menu/views.py | PIŠE (admin, QR page) | READ ONLY |
| gastro_menu/urls.py | PIŠE | PIŠE (unified_order URL) |
| delivery/models.py | NE DIRA | PIŠE |
| delivery/urls.py | NE DIRA | PIŠE |
| companies/models.py | NE DIRA | PIŠE (parent FK ako treba) |
| templates/gastro/ | PIŠE (admin.html, table.html) | PIŠE (unified_order.html) |
| setup_sirokisor.py | PIŠE | NE DIRA |

Ako Task B treba nešto iz Task A (npr. DigitalMenu slug) — čita iz baze, ne iz koda.
