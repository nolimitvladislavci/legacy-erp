# CC_TASK_MEMIO_GTM.md
# Cilj: memio.pet GTM — direktorij uzgajivača + oglas ljubimaca
# Prioritet: P1 | Rok: što prije | Dodjeljeno: CC Code
# Sesija: 05.04.2026.

PRAVILO: READ models.py PRIJE svakog WRITE.
PRAVILO: sve DB operacije s `.using('memio_pets')`.
PRAVILO: templates idu u `templates/memio_pet/`.
PRAVILO: venv/bin/python manage.py check 2>&1 | tail -3 — mora biti 0 grešaka.
PRAVILO: venv/bin/python manage.py makemigrations memio_pet + migrate --database=memio_pets.

---

## KONTEKST

memio.pet je live (200 OK, nginx servis /var/www/memio-pet/ → static landing).
Django memio_pet app postoji i radi na `memio_pets` bazi.
Trenutni URL-ovi: /pas/<chip>/, /uzgajivac/<uuid>/, /barf/, /hotel/, /dresura/
Problem: nema direktorija uzgajivača ni oglasa ljubimaca — bez toga nema GTM.

Relevantni modeli (pročitaj models.py prije pisanja koda):
  - BreederProfile: id(UUID), name, city, country, account_type, trust_score,
                    is_cro_validated, is_no_limit_partner, verified_badge (property),
                    latitude, longitude, website, phone, animals (related_name)
  - AnimalProfile: id(UUID), ear_tag, chip_number, name, vrsta, breed, spol,
                   status, photo, date_of_birth, breeder(FK), breeder_name_snapshot
  - STATUS_CHOICES AnimalProfile: aktivno | rezerviran | prodano | udomljen | u_azilu | karantena | uginulo
  - VRSTA_CHOICES: pas | macka | konj | zec | ovca | koza | svinja | ptica | ostalo_ljubimac
  - ACCOUNT_TYPE_CHOICES BreederProfile: breeder | shelter | owner | trainer | hotel | sheep_farmer | pig_farmer | poultry | horse

---

## KORAK 1 — Novi model: PetListing (oglas za prodaju/udomljavanje)

READ: memio_pet/models.py (zadnjih 20 linija + importsi)

DODAJ na kraj memio_pet/models.py:

```python
class PetListing(models.Model):
    """
    Oglas uzgajivača za prodaju ili udomljavanje ljubimca.
    Isto kao Njuškalo oglas, ali s verifikacijom i strukturiranim podacima.
    """
    LISTING_TYPE_CHOICES = [
        ('prodaja',      'Prodaja'),
        ('udomljavanje', 'Udomljavanje / Azil'),
        ('rezerviran',   'Rezerviran'),
    ]

    id             = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    breeder        = models.ForeignKey(
        BreederProfile, on_delete=models.CASCADE, related_name='listings'
    )
    animal         = models.ForeignKey(
        AnimalProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='listings'
    )

    # Ako animal nije u bazi — tekstualni opis
    title          = models.CharField(max_length=200, validators=[validate_name_field])
    vrsta          = models.CharField(max_length=20, choices=AnimalProfile.VRSTA_CHOICES, default='pas')
    breed          = models.CharField(max_length=100, blank=True)
    spol           = models.CharField(max_length=1, choices=AnimalProfile.SPOL_CHOICES, default='N')
    date_of_birth  = models.DateField(null=True, blank=True)
    description    = models.TextField(blank=True, validators=[validate_free_text])
    photo          = models.ImageField(upload_to='memio_pet/listings/', null=True, blank=True)

    listing_type   = models.CharField(max_length=20, choices=LISTING_TYPE_CHOICES, default='prodaja')
    price_eur      = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True,
                                         help_text='Prazno = cijena na upit / besplatno')
    city           = models.CharField(max_length=100, blank=True)

    is_active      = models.BooleanField(default=True, db_index=True)
    expires_at     = models.DateField(null=True, blank=True)

    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'memio_pet'
        ordering  = ['-created_at']
        verbose_name = 'Oglas ljubimca'

    def __str__(self):
        return f"{self.title} — {self.breeder.name}"

    def save(self, *args, **kwargs):
        if not self.city and self.breeder_id:
            self.city = self.breeder.city
        super().save(*args, **kwargs)
```

MIGRACIJA:
```bash
venv/bin/python manage.py makemigrations memio_pet --name="add_pet_listing" 2>&1
venv/bin/python manage.py migrate --database=memio_pets 2>&1 | tail -5
```

---

## KORAK 2 — Admin registracija PetListing

READ: memio_pet/admin.py (zadnjih 30 linija)

DODAJ na kraj admin.py:

```python
@admin.register(PetListing)
class PetListingAdmin(admin.ModelAdmin):
    using = 'memio_pets'
    list_display = ('title', 'breeder', 'vrsta', 'breed', 'listing_type', 'price_eur', 'is_active', 'created_at')
    list_filter  = ('listing_type', 'vrsta', 'is_active')
    search_fields = ('title', 'breed', 'breeder__name')
    raw_id_fields = ('breeder', 'animal')

    def save_model(self, request, obj, form, change):
        obj.save(using=self.using)

    def get_queryset(self, request):
        return super().get_queryset(request).using(self.using)
```

---

## KORAK 3 — Views: 3 nova viewa

READ: memio_pet/views.py (cijeli fajl — provjeri importse i pattern .using('memio_pets'))

DODAJ na kraj memio_pet/views.py:

### 3A — Direktorij uzgajivača

```python
def breeder_directory(request):
    """
    Javni direktorij verificiranih uzgajivača.
    Filter: account_type, vrsta ljubimca, grad.
    """
    from django.db.models import Count, Avg

    account_type = request.GET.get('tip', '')
    city_filter  = request.GET.get('grad', '').strip()
    verified_only = request.GET.get('verified', '')

    qs = BreederProfile.objects.using('memio_pets').annotate(
        animal_count=Count('animals'),
        avg_rating=Avg('reviews__rating'),
    ).filter(animal_count__gt=0)  # samo uzgajivači s barem jednim ljubimcem

    if account_type:
        qs = qs.filter(account_type=account_type)
    if city_filter:
        qs = qs.filter(city__icontains=city_filter)
    if verified_only:
        qs = qs.filter(is_cro_validated=True)

    qs = qs.order_by('-trust_score', 'name')

    return render(request, 'memio_pet/breeder_directory.html', {
        'breeders': qs[:60],
        'account_type': account_type,
        'city_filter': city_filter,
        'verified_only': verified_only,
        'account_type_choices': BreederProfile.ACCOUNT_TYPE_CHOICES,
        'total': qs.count(),
    })
```

### 3B — Listing oglasa

```python
def pet_listings(request):
    """
    Javni oglasi: štenadi, mačića, konja — prodaja i udomljavanje.
    """
    from datetime import date
    from memio_pet.models import PetListing

    vrsta_filter   = request.GET.get('vrsta', '')
    tip_filter     = request.GET.get('tip', '')
    city_filter    = request.GET.get('grad', '').strip()

    today = date.today()
    qs = PetListing.objects.using('memio_pets').select_related('breeder').filter(
        is_active=True,
    ).filter(
        models.Q(expires_at__isnull=True) | models.Q(expires_at__gte=today)
    )

    if vrsta_filter:
        qs = qs.filter(vrsta=vrsta_filter)
    if tip_filter:
        qs = qs.filter(listing_type=tip_filter)
    if city_filter:
        qs = qs.filter(city__icontains=city_filter)

    qs = qs.order_by('-breeder__trust_score', '-created_at')

    return render(request, 'memio_pet/pet_listings.html', {
        'listings': qs[:80],
        'vrsta_filter': vrsta_filter,
        'tip_filter': tip_filter,
        'city_filter': city_filter,
        'vrsta_choices': AnimalProfile.VRSTA_CHOICES,
        'tip_choices': PetListing.LISTING_TYPE_CHOICES,
        'total': qs.count(),
    })
```

### 3C — Kreiranje oglasa (jednostavan POST)

```python
def pet_listing_create(request):
    """
    Uzgajivač kreira oglas. Auth via api_key parametar (GET ili POST).
    """
    from memio_pet.models import PetListing

    api_key = request.GET.get('api_key') or request.POST.get('api_key', '')
    breeder = None
    if api_key:
        try:
            breeder = BreederProfile.objects.using('memio_pets').get(api_key=api_key)
        except (BreederProfile.DoesNotExist, ValueError):
            pass

    error = None
    if request.method == 'POST' and breeder:
        title        = request.POST.get('title', '').strip()
        vrsta        = request.POST.get('vrsta', 'pas')
        breed        = request.POST.get('breed', '').strip()
        spol         = request.POST.get('spol', 'N')
        listing_type = request.POST.get('listing_type', 'prodaja')
        price_raw    = request.POST.get('price_eur', '').strip()
        description  = request.POST.get('description', '').strip()
        city         = request.POST.get('city', breeder.city).strip()

        if not title:
            error = 'Naziv oglasa je obavezan.'
        else:
            price = None
            if price_raw:
                try:
                    price = float(price_raw.replace(',', '.'))
                except ValueError:
                    error = 'Cijena mora biti broj (npr. 250.00).'

            if not error:
                listing = PetListing.objects.using('memio_pets').create(
                    breeder=breeder,
                    title=title,
                    vrsta=vrsta,
                    breed=breed,
                    spol=spol,
                    listing_type=listing_type,
                    price_eur=price,
                    description=description,
                    city=city,
                )
                return redirect(f'/oglasi/?novi={listing.id}')

    return render(request, 'memio_pet/listing_create.html', {
        'breeder': breeder,
        'api_key': api_key,
        'error': error,
        'vrsta_choices': AnimalProfile.VRSTA_CHOICES,
        'spol_choices': AnimalProfile.SPOL_CHOICES,
        'tip_choices': PetListing.LISTING_TYPE_CHOICES,
    })
```

---

## KORAK 4 — URL-ovi

READ: memio_pet/urls.py

DODAJ u urlpatterns listu (append, ne brisanje):

```python
    path("uzgajivaci/", views.breeder_directory, name="breeder_directory"),
    path("oglasi/", views.pet_listings, name="pet_listings"),
    path("oglasi/novi/", views.pet_listing_create, name="pet_listing_create"),
```

---

## KORAK 5 — Template: breeder_directory.html

READ: templates/memio_pet/breeder.html (prvih 30 linija — uzmi isti CSS stil / font stack)

Kreiraj `templates/memio_pet/breeder_directory.html`:

Standalone HTML (ne extends base.html — memio.pet je odvojeni frontend).
Isti dizajn kao breeder.html: --bg, --ink, --gold, Space Grotesk + Cormorant Garamond.
Dark mode toggle prisutan (data-theme).

Sadržaj stranice:
- Top bar: logo Memio.pet + link "→ Oglasi" + link "→ Početna"
- Hero: "Verificirani uzgajivači" + broj uzgajivača ukupno
- Filter forma (GET): tip (select account_type_choices), grad (text input), samo verificirani (checkbox)
- Grid uzgajivača: kartica za svakog breeder-a
  - Ime, grad, account_type badge
  - Trust Score traka (0-100)
  - Broj ljubimaca (animal_count)
  - Zelena kvačica ako verified_badge
  - Link: href="/uzgajivac/{{ breeder.id }}/"
- Footer: memio.pet · Konjik d.o.o. · limit-connect.com

---

## KORAK 6 — Template: pet_listings.html

Kreiraj `templates/memio_pet/pet_listings.html`:

Isti dizajn kao breeder_directory.html.

Sadržaj:
- Hero: "Ljubimci na dlan" + total oglasa
- Filter forma (GET): vrsta (select), tip prodaja/udomljavanje, grad
- Grid oglasa: kartica za svaki listing
  - Foto (ako postoji) ili placeholder ikona po vrsti (🐕 🐈 🐴 🐇)
  - Naziv, pasmina, spol
  - Cijena (ili "Cijena na upit" / "Besplatno/Udomljavanje")
  - Grad, datum
  - Trust badge uzgajivača: ime + ✓ ako verified
  - Listing type badge: Prodaja / Udomljavanje
- Link na breeder profil: /uzgajivac/{{ listing.breeder.id }}/
- Ako 0 oglasa: prazan state "Nema oglasa za odabrane filtre."
- Forma za kreiranje oglasa: gumb "Dodaj oglas →" → /oglasi/novi/?api_key=...

---

## KORAK 7 — Template: listing_create.html

Kreiraj `templates/memio_pet/listing_create.html`:

Isti dizajn.

Sadržaj:
- Ako breeder is None: poruka "Upiši api_key u URL parametar" + primjer URL-a
- Ako breeder postoji: prikaži naziv uzgajivača, forma s poljima:
  - title (text, required)
  - vrsta (select VRSTA_CHOICES)
  - breed (text)
  - spol (select M/F/N)
  - listing_type (select prodaja/udomljavanje)
  - price_eur (number, placeholder "Prazno = cijena na upit")
  - description (textarea)
  - city (text, default breeder.city)
  - hidden: api_key
- Submit gumb "Objavi oglas"
- Error prikaz ako error nije None

---

## KORAK 8 — Nginx rute za memio.pet

memio.pet je statičan landing na /var/www/memio-pet/index.html, ali Django
URL-ovi moraju biti dostupni pod memio.pet domenom za ove nove stranice.

READ: /etc/nginx/sites-enabled/memio-pet (ili ekvivalentni nginx config)

PROVJERI: postoje li već location blokovi koji prosljeđuju /uzgajivaci/, /oglasi/, itd. na Django.
Ako ne postoje, DODAJ location blokove (isto kao za /pas/, /uzgajivac/, /barf/):

```nginx
location ~ ^/(uzgajivaci|oglasi)(/|$) {
    proxy_pass http://unix:/run/gunicorn-fina.sock;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

Nakon editiranja:
```bash
nginx -t && nginx -s reload
```

---

## KORAK 9 — Verifikacija

```bash
# Migracijska provjera
venv/bin/python manage.py showmigrations memio_pet | tail -5

# System check
venv/bin/python manage.py check 2>&1 | tail -3

# HTTP test
curl -s -o /dev/null -w "%{http_code}" https://memio.pet/uzgajivaci/ && echo " /uzgajivaci/"
curl -s -o /dev/null -w "%{http_code}" https://memio.pet/oglasi/ && echo " /oglasi/"
curl -s -o /dev/null -w "%{http_code}" https://memio.pet/oglasi/novi/ && echo " /oglasi/novi/"
```

Sva tri moraju vratiti 200.

---

## DONE kriterij

✅ PetListing model + migracija na memio_pets bazi
✅ 3 nova viewa (directory, listings, create)  
✅ 3 URL-a registrirana u memio_pet/urls.py
✅ 3 template-a (breeder_directory, pet_listings, listing_create) — isti vizualni stil kao breeder.html
✅ Nginx rute /uzgajivaci/ i /oglasi/ → Django
✅ curl test: 200 na sva 3 URL-a

## Nakon završetka

Ažuriraj FENIX_STATUS.md — DONE sekcija + git HEAD hash.
