CC TASK: BARF MARKETPLACE FAZA 1 + NJUSKALO BADGE
Datum: 04.04.2026. | Rok: 10.04.2026.
Prioritet: VISOK — circular economy OPG + memio.pet + uzgajivaci

PRAVILO: READ models.py PRIJE svakog WRITE.
PRAVILO: base.html, .env NE DIRAS.
PRAVILO: check 2>&1 | tail -3 nakon svake migracije.

---

KORAK 1: Provjeri teren

EXEC: grep -n "SOURCE_TYPES\|raw_food\|barf" /var/www/fina-connect/documents/models.py | head -10
EXEC: grep -n "^class BreederProfile\|njuskalo\|trust_score\|barf" /var/www/fina-connect/memio_pet/models.py | head -15
EXEC: grep -n "business_type.*OPG\|OPG\|opg" /var/www/fina-connect/companies/models.py | head -5
EXEC: ls /var/www/fina-connect/memio_pet/views.py | wc -l && grep -n "^def " /var/www/fina-connect/memio_pet/urls.py | head -10

---

KORAK 2: ArhivaEntry source_type nadopuna

READ: /var/www/fina-connect/documents/models.py (SOURCE_TYPES lista, klasa ArhivaEntry)

U SOURCE_TYPES listi dodaj (APPEND, ne zamjena):
    ('raw_food_input',   'Sirova hrana — primitak (BARF)'),
    ('raw_food_sale',    'Sirova hrana — prodaja OPG'),

Nema migracije potrebne (CharField choices).

---

KORAK 3: RawFoodListing model

READ: /var/www/fina-connect/memio_pet/models.py (zadnjih 30 linija i importse)

Na KRAJ memio_pet/models.py dodaj:

class RawFoodListing(models.Model):
    PRODUCT_CHOICES = [
        ('vrat_pileci',   'Pileći vrat'),
        ('nogice_pilece', 'Pileće nogice'),
        ('jetra',         'Jetra (piletina/svinjetina)'),
        ('srce',          'Srce'),
        ('bubrezi',       'Bubrezi'),
        ('kosti',         'Kosti za grickanje'),
        ('mijesano',      'Mješoviti paket'),
        ('ostalo',        'Ostalo'),
    ]
    STATUS_CHOICES = [
        ('available', 'Dostupno'),
        ('reserved',  'Rezervirano'),
        ('sold',      'Prodano'),
        ('expired',   'Isteklo'),
    ]

    company             = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                                             related_name='raw_food_listings')
    objects             = CompanyManager()

    product_type        = models.CharField(max_length=30, choices=PRODUCT_CHOICES)
    quantity_kg         = models.DecimalField(max_digits=8, decimal_places=2, verbose_name='Kolicina (kg)')
    price_eur_kg        = models.DecimalField(max_digits=6, decimal_places=2, verbose_name='Cijena EUR/kg')
    available_from      = models.DateField(verbose_name='Dostupno od')
    expires_at          = models.DateField(verbose_name='Rok (sirovina)')
    k3_cert_number      = models.CharField(max_length=100, blank=True, verbose_name='K3 veterinarska potvrda')
    is_antibiotic_free  = models.BooleanField(default=False, verbose_name='Bez antibiotika')
    is_free_range       = models.BooleanField(default=False, verbose_name='Slobodan uzgoj')
    description         = models.TextField(blank=True, verbose_name='Opis')
    status              = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    latitude            = models.FloatField(null=True, blank=True)
    longitude           = models.FloatField(null=True, blank=True)
    created_at          = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'BARF ponuda (sirova hrana)'
        verbose_name_plural = 'BARF ponude'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_product_type_display()} — {self.quantity_kg}kg | {self.company.name}'

    @property
    def total_eur(self):
        return self.quantity_kg * self.price_eur_kg

    def auto_fill_location(self):
        if not self.latitude and self.company:
            self.latitude  = getattr(self.company, 'latitude', None)
            self.longitude = getattr(self.company, 'longitude', None)

    def save(self, *args, **kwargs):
        self.auto_fill_location()
        super().save(*args, **kwargs)


class RawFoodOrder(models.Model):
    STATUS_CHOICES = [
        ('pending',   'Ceka potvrdu'),
        ('confirmed', 'Potvrdeno'),
        ('picked_up', 'Preuzeto'),
        ('cancelled', 'Otkazano'),
    ]

    listing         = models.ForeignKey(RawFoodListing, on_delete=models.CASCADE,
                                         related_name='orders')
    breeder         = models.ForeignKey('BreederProfile', on_delete=models.SET_NULL,
                                         null=True, blank=True, related_name='barf_orders')
    buyer_company   = models.ForeignKey('companies.Company', on_delete=models.SET_NULL,
                                         null=True, blank=True)
    quantity_kg     = models.DecimalField(max_digits=8, decimal_places=2)
    status          = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    invoice         = models.OneToOneField('invoicing.Invoice', on_delete=models.SET_NULL,
                                            null=True, blank=True, related_name='barf_order')
    arhiva_entry    = models.OneToOneField('documents.ArhivaEntry', on_delete=models.SET_NULL,
                                            null=True, blank=True)
    batch_id        = models.CharField(max_length=50, blank=True,
                                        help_text='RF-YYYY-NNNN — sljedivost od OPG do zdjelice')
    note            = models.TextField(blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'BARF narudzba'
        verbose_name_plural = 'BARF narudzbe'

    def __str__(self):
        return f'{self.batch_id or self.pk} — {self.quantity_kg}kg | {self.status}'

    def generate_batch_id(self):
        import datetime
        seq = RawFoodOrder.objects.filter(
            created_at__year=datetime.date.today().year
        ).count() + 1
        return f'RF-{datetime.date.today().year}-{seq:04d}'

    def save(self, *args, **kwargs):
        if not self.batch_id:
            self.batch_id = self.generate_batch_id()
        super().save(*args, **kwargs)

EXEC: cd /var/www/fina-connect && venv/bin/python manage.py makemigrations memio_pet --name barf_marketplace
EXEC: venv/bin/python manage.py migrate memio_pet
EXEC: venv/bin/python manage.py check 2>&1 | tail -3

---

KORAK 4: BreederProfile nadopuna (Njuškalo Badge)

READ: /var/www/fina-connect/memio_pet/models.py (klasa BreederProfile — provjeri polja i zadnju liniju)

U klasi BreederProfile, dodaj polja (ODMAH ISPOD trust_score ili slicnog):

    njuskalo_ad_url = models.URLField(blank=True, verbose_name='Njuškalo oglas URL',
                                       help_text='Link oglasa na Njuškalo — za generiranje Trust Badge')
    barf_partner    = models.BooleanField(default=False, verbose_name='BARF partner',
                                           help_text='Ima pristup BARF marketplace ponudama')
    barf_radius_km  = models.PositiveIntegerField(default=50,
                                                   verbose_name='BARF radius (km)',
                                                   help_text='Max udaljenost OPG-a za notifikacije')

EXEC: venv/bin/python manage.py makemigrations memio_pet --name breeder_njuskalo_barf
EXEC: venv/bin/python manage.py migrate memio_pet
EXEC: venv/bin/python manage.py check 2>&1 | tail -3

---

KORAK 5: Admin registracija

READ: /var/www/fina-connect/memio_pet/admin.py (zadnjih 20 linija)

Dodaj:

from memio_pet.models import RawFoodListing, RawFoodOrder

@admin.register(RawFoodListing)
class RawFoodListingAdmin(admin.ModelAdmin):
    list_display = ('company', 'product_type', 'quantity_kg', 'price_eur_kg',
                    'available_from', 'expires_at', 'status', 'is_free_range')
    list_filter  = ('product_type', 'status', 'is_antibiotic_free', 'is_free_range')
    search_fields = ('company__name', 'k3_cert_number')
    date_hierarchy = 'created_at'

@admin.register(RawFoodOrder)
class RawFoodOrderAdmin(admin.ModelAdmin):
    list_display = ('batch_id', 'listing', 'quantity_kg', 'status', 'created_at')
    list_filter  = ('status',)
    search_fields = ('batch_id',)

---

KORAK 6: Njuškalo Badge Generator endpoint

READ: /var/www/fina-connect/memio_pet/views.py (prvih 20 linija — importse i URL pattern)
READ: /var/www/fina-connect/memio_pet/urls.py

Dodaj view na kraj memio_pet/views.py:

def njuskalo_badge(request, breeder_id):
    Generira Trust Badge SVG za uzgajivaca.
    Javno dostupan bez prijave — koristi se kao slika u Njuškalo oglasima.
    URL: /memio/badge/{breeder_id}/

    from memio_pet.models import BreederProfile
    from django.http import HttpResponse
    from django.utils import timezone

    try:
        breeder = BreederProfile.objects.unscoped().get(pk=breeder_id, is_published=True)
    except BreederProfile.DoesNotExist:
        return HttpResponse('Not Found', status=404)

    trust = getattr(breeder, 'trust_score', 0) or 0
    name  = breeder.name[:20] if breeder.name else 'Uzgajivac'
    verified = getattr(breeder, 'is_cro_validated', False)

    colour_bar = '#4caf7d' if trust >= 80 else '#c9a84c' if trust >= 50 else '#888'
    check = '✓' if verified else '?'

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="340" height="90" viewBox="0 0 340 90">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#1a1a2e"/>
      <stop offset="100%" stop-color="#2d2d4a"/>
    </linearGradient>
  </defs>
  <rect width="340" height="90" rx="10" fill="url(#bg)"/>
  <rect x="0" y="0" width="6" height="90" rx="3" fill="{colour_bar}"/>
  <text x="24" y="28" font-family="Arial,sans-serif" font-size="11"
        fill="#888" letter-spacing="2" text-anchor="start">MEMIO.PET VERIFICIRANO</text>
  <text x="24" y="54" font-family="Arial,sans-serif" font-size="18"
        font-weight="bold" fill="#e8e8e8">{check} {name}</text>
  <text x="24" y="75" font-family="Arial,sans-serif" font-size="12"
        fill="{colour_bar}" font-weight="600">TRUST SCORE {trust}/100</text>
  <text x="320" y="75" font-family="Arial,sans-serif" font-size="9"
        fill="#555" text-anchor="end">memio.pet/uzgajivaci/{breeder_id}</text>
</svg>'''

    response = HttpResponse(svg, content_type='image/svg+xml')
    response['Cache-Control'] = 'public, max-age=3600'
    response['X-Robots-Tag'] = 'noindex'
    return response


def barf_listings(request):
    Javni popis dostupnih BARF ponuda (bez prijave — browseable).

    from memio_pet.models import RawFoodListing
    from django.utils import timezone

    today = timezone.now().date()
    listings = (RawFoodListing.objects.unscoped()
                .filter(status='available', expires_at__gte=today)
                .select_related('company')
                .order_by('-created_at')[:50])

    return render(request, 'memio_pet/barf_listings.html', {
        'listings': listings,
        'page_title': 'BARF Marketplace — svježa sirova hrana',
    })

Dodaj URL-ove u memio_pet/urls.py (append):
path('badge/<int:breeder_id>/', views.njuskalo_badge, name='njuskalo_badge'),
path('barf/', views.barf_listings, name='barf_listings'),

---

KORAK 7: BARF Smart Matching Celery task

READ: /var/www/fina-connect/memio_pet/tasks.py 2>/dev/null ili
EXEC: ls /var/www/fina-connect/memio_pet/

Ako tasks.py ne postoji: kreiraj ga.
Ako postoji: dodaj na kraj.

WRITE ili APPEND /var/www/fina-connect/memio_pet/tasks.py

Sadrzaj (ako novi fajl):

import logging
import math
from celery import shared_task

logger = logging.getLogger('memio_pet')

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat/2)**2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon/2)**2)
    return R * 2 * math.asin(math.sqrt(a))


@shared_task(name='memio_pet.notify_barf_breeders')
def notify_barf_breeders(listing_id):
    Kad OPG doda novu ponudu — notifikacija uzgajivacima u radijusu.
    Max 1 WhatsApp po uzgajivacu dnevno (rate limit kljuc u Redis).

    from memio_pet.models import RawFoodListing, BreederProfile
    from django.core.cache import cache
    import os

    try:
        listing = RawFoodListing.objects.unscoped().get(pk=listing_id, status='available')
    except RawFoodListing.DoesNotExist:
        return

    if not listing.latitude or not listing.longitude:
        logger.warning('notify_barf_breeders: listing %s nema GPS', listing_id)
        return

    breeders = BreederProfile.objects.unscoped().filter(
        barf_partner=True,
    ).exclude(contact_phone='')

    notified = 0
    for br in breeders:
        # Provjeri radius
        if br.latitude and br.longitude:
            km = haversine_km(listing.latitude, listing.longitude,
                              br.latitude, br.longitude)
            if km > (br.barf_radius_km or 50):
                continue

        # Rate limit: 1 poruka po uzgajivacu dnevno po tipu
        cache_key = f'barf_notif:{br.pk}:{listing.product_type}:{listing.available_from}'
        if cache.get(cache_key):
            continue

        # Pripremi poruku
        msg = (f'BARF ponuda dostupna:\n'
               f'{listing.get_product_type_display()} — {listing.quantity_kg}kg\n'
               f'{listing.price_eur_kg} EUR/kg | {listing.available_from}\n'
               f'OPG: {listing.company.name}\n'
               f'memio.pet/barf/')

        try:
            from core.whatsapp import send_whatsapp
            phone = getattr(br, 'contact_phone', '') or ''
            if phone:
                send_whatsapp(phone, msg)
                cache.set(cache_key, 1, 86400)  # 24h
                notified += 1
        except Exception as e:
            logger.warning('notify_barf_breeders WA: %s', e)

    logger.info('notify_barf_breeders: %s notifikacija poslano za listing %s', notified, listing_id)

Ako tasks.py vec postoji — samo dodaj import i funkcije na kraj.

---

KORAK 8: BARF signal — auto notifikacija pri kreiranju ponude

READ: /var/www/fina-connect/memio_pet/apps.py

U MemioPetConfig.ready() dodaj:
    import memio_pet.signals

Ako signals.py ne postoji: kreiraj
WRITE (ili APPEND): /var/www/fina-connect/memio_pet/signals.py

Dodaj na kraj:

from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender='memio_pet.RawFoodListing')
def on_listing_created(sender, instance, created, **kwargs):
    if created and instance.status == 'available':
        try:
            from memio_pet.tasks import notify_barf_breeders
            notify_barf_breeders.delay(instance.pk)
        except Exception as e:
            import logging
            logging.getLogger('memio_pet').warning('BARF signal: %s', e)

---

KORAK 9: BARF listings template

WRITE: /var/www/fina-connect/templates/memio_pet/barf_listings.html

Template extenda base.html.
Prikazuje listu RawFoodListing kartica (grid, 3 kolone).
Svaka kartica:
  - Naziv proizvoda (get_product_type_display)
  - Kolicina i cijena
  - OPG naziv + grad
  - Bedževi: is_free_range (zeleno "Slobodan uzgoj"), is_antibiotic_free (plavo "Bez antibiotika")
  - Expires_at (istice za X dana)
  - Gumb "Kontaktiraj OPG" (mailto ili WhatsApp link)

Bez filtara u ovoj fazi — samo lista, cisto.

---

KORAK 10: Breedera Dashboard — Njuškalo Badge sekcija

READ: /var/www/fina-connect/templates/memio_pet/breeder.html
Pronadi gdje su akcijski gumbi ili profil sekcija.

Dodaj sekciju "Njuškalo oglas":
  Input: njuskalo_ad_url (URL polje)
  Gumb: "Spremi oglas URL"
  Prikaz Badge-a:
    <img src="/memio/badge/{{ breeder.pk }}/"
         alt="Memio Trust Badge"
         style="max-width:340px;border-radius:8px;margin-top:12px">
  Upute (kopiraj badge):
    "Desni klik → Spremi sliku → Uploadaj kao prvu sliku na Njuškalu"
    "Ili kopiraj link i stavi u opis oglasa:"
    <code>https://memio.pet/memio/badge/{{ breeder.pk }}/</code>

CSS badge box:
  Tamna pozadina, zlatni border, padding 1rem, border-radius 8px.

---

KORAK 11: Finalna provjera

EXEC: cd /var/www/fina-connect && venv/bin/python manage.py check 2>&1 | tail -5
EXEC: systemctl restart gunicorn-fina
EXEC: sleep 5 && curl -s -o /dev/null -w "HTTP %{http_code}" https://limit-connect.com/
EXEC: curl -s -o /dev/null -w "BARF: %{http_code}\n" https://limit-connect.com/memio/barf/
EXEC: curl -s -H "Accept: image/svg+xml" "https://limit-connect.com/memio/badge/1/" | head -3

EXEC: cd /var/www/fina-connect && git add -A && git commit -m "feat(barf+badge): BARF marketplace Faza 1 — RawFoodListing, Haversine matching, Njuškalo Trust Badge SVG"

DONE kriterij:
- RawFoodListing i RawFoodOrder modeli + migracije OK
- BreederProfile.njuskalo_ad_url i barf_partner polja postoje
- /memio/badge/{pk}/ vraca SVG (Content-Type: image/svg+xml)
- /memio/barf/ vraca 200
- notify_barf_breeders Celery task registriran
- on_listing_created signal okida task
- manage.py check: 0 errors
- git commit postoji

NAPOMENA ZA IVANA:
- OPG Kruljac Slađana (vec klijent) — aktivirati barf_partner=True na njenom BreederProfile
- Za BreederProfile koji su OPG-ovi, postaviti company.latitude/longitude (GPS)
- K3 veterinarska potvrda: OPG treba ishoditi od Veterinarske inspekcije HR
  (Ministarstvo poljoprivrede — registracija objekta za rukovanje K3 nusproizvodima)
  To je jednokratna registracija, besplatna za male OPG-ove
