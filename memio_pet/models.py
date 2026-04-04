"""
memio_pet/models.py — Standalone baza za memio.pet

Pravilo: NULA Django FK prema LIMIT Connect modelima.
Sve veze prema ERP-u su API pozivi, ne ORM JOIN-ovi.
Baza: memio_pets (PostgreSQL, odvojena od fina_erp)
"""
import uuid
from django.db import models
from memio_pet.encrypted_fields import MemioEncryptedField
from memio_pet.validators import (
    validate_no_scripts, validate_no_sql, validate_oib_format,
    validate_chip_number, validate_name_field, validate_free_text,
)


class BreederProfile(models.Model):
    """
    Verificirani uzgajivač / azil — populira se pushom iz LIMIT Connect.
    Svaki breeder ima API ključ za autorizaciju pusha.
    """
    ACCOUNT_TYPE_CHOICES = [
        ('breeder',      'Uzgajivač'),
        ('shelter',      'Azil / Sklonište'),
        ('owner',        'Vlasnik ljubimca'),
        ('trainer',      'Kinolog / Dresura pasa'),
        ('hotel',        'Pet Hotel / Pansion'),
        ('sheep_farmer', 'Uzgajivač ovaca i koza'),
        ('pig_farmer',   'Uzgajivač svinja'),
        ('poultry',      'Peradarstvo'),
        ('horse',        'Konjički sport / Uzgoj konja'),
    ]

    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    api_key         = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    account_type    = models.CharField(max_length=20, choices=ACCOUNT_TYPE_CHOICES, default='breeder')

    # Identitet (denormalizirano — bez FK prema Company)
    oib             = MemioEncryptedField(blank=True, db_index=False, validators=[validate_oib_format])  # AES encrypted, bez indeksa
    name            = models.CharField(max_length=200, validators=[validate_name_field])
    city            = models.CharField(max_length=100, blank=True)
    country         = models.CharField(max_length=5, default='HR')
    email           = MemioEncryptedField(blank=True)  # AES encrypted
    phone           = models.CharField(max_length=30, blank=True)
    website         = models.URLField(blank=True)

    # Verifikacija
    is_cro_validated   = models.BooleanField(default=False)
    validated_name     = models.CharField(max_length=200, blank=True)
    validated_at       = models.DateTimeField(null=True, blank=True)
    is_no_limit_partner = models.BooleanField(default=False)  # Azili sponzorirani od No Limit
    shelter_sponsor    = models.CharField(max_length=100, blank=True)

    # Referenca prema LIMIT Connect (nije FK — samo integer za dedup)
    limit_company_id   = models.CharField(max_length=36, blank=True, db_index=True)

    trust_score     = models.IntegerField(default=0, verbose_name='Trust Score',
                                          help_text='0-100: OIB(+20), Vet(+25), Health(+15), Ownership(+15), Photo(+10), Reviews(+15)')
    trust_breakdown = models.JSONField(default=dict, blank=True)
    trust_updated   = models.DateTimeField(null=True, blank=True)

    # BARF + Njuškalo (Sprint BARF)
    njuskalo_ad_url = models.URLField(blank=True, verbose_name='Njuškalo oglas URL')
    barf_partner = models.BooleanField(default=False, verbose_name='BARF partner')
    barf_radius_km = models.PositiveIntegerField(default=50, verbose_name='BARF radius (km)')
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'memio_pet'
        ordering  = ['name']
        verbose_name = 'Breeder / Azil profil'

    def __str__(self):
        verified = ' ✓' if self.is_cro_validated else ''
        return f"{self.name}{verified} ({self.get_account_type_display()})"

    @property
    def verified_badge(self):
        return self.is_cro_validated or self.is_no_limit_partner


class AnimalProfile(models.Model):
    """
    Javni digitalni profil ljubimca.
    Srce memio.pet baze — nema FK prema LIMIT Connect.
    """
    VRSTA_CHOICES = [
        ('pas',            'Pas'),
        ('macka',          'Mačka'),
        ('konj',           'Konj'),
        ('zec',            'Zec'),
        ('ovca',           'Ovca'),
        ('koza',           'Koza'),
        ('svinja',         'Svinja / Prasac'),
        ('ptica',          'Ptica / Peradar'),
        ('ostalo_ljubimac','Ostalo'),
    ]
    STATUS_CHOICES = [
        ('aktivno',    'Aktivno'),
        ('u_azilu',    'U azilu'),
        ('karantena',  'Karantena'),
        ('rezerviran', 'Rezerviran'),
        ('udomljen',   'Udomljen'),
        ('prodano',    'Prodano / Prenesen'),
        ('uginulo',    'Uginulo'),
    ]
    SPOL_CHOICES = [
        ('M', 'Mužjak'),
        ('F', 'Ženka'),
        ('N', 'Nepoznato'),
    ]

    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    public_id       = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)

    # Identifikatori (za QR / lookup)
    chip_number     = models.CharField(max_length=20, blank=True, db_index=True, validators=[validate_chip_number])
    ear_tag         = models.CharField(max_length=30, unique=True, db_index=True)
    pedigree_number = models.CharField(max_length=50, blank=True)

    # Osnovni podaci
    name            = models.CharField(max_length=100, blank=True, validators=[validate_name_field])
    vrsta           = models.CharField(max_length=20, choices=VRSTA_CHOICES, default='pas')
    breed           = models.CharField(max_length=100, blank=True)
    spol            = models.CharField(max_length=1, choices=SPOL_CHOICES, default='N')
    color_description = models.CharField(max_length=200, blank=True, validators=[validate_free_text])
    date_of_birth   = models.DateField(null=True, blank=True)
    weight_kg       = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)

    # Rodovnica
    father_name     = models.CharField(max_length=100, blank=True)
    mother_name     = models.CharField(max_length=100, blank=True)

    # Foto
    photo           = models.ImageField(upload_to='memio_pet/photos/', null=True, blank=True)

    # Status
    status          = models.CharField(max_length=15, choices=STATUS_CHOICES, default='aktivno')
    notes           = models.TextField(blank=True, validators=[validate_free_text])

    # Breeder referenca (denormalizirano — nije FK)
    breeder         = models.ForeignKey(
        BreederProfile,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='animals',
    )
    # Backup tekstualni podaci (čak i ako se breeder obriše)
    breeder_name_snapshot = models.CharField(max_length=200, blank=True)
    breeder_oib_snapshot  = models.CharField(max_length=11, blank=True)

    # Referenca prema LIMIT Connect (nije FK)
    limit_livestock_id = models.IntegerField(null=True, blank=True, db_index=True)

    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'memio_pet'
        ordering  = ['name', 'ear_tag']
        verbose_name = 'Profil ljubimca'

    def __str__(self):
        return f"{self.name or self.ear_tag} ({self.get_vrsta_display()})"

    @property
    def public_url(self):
        identifier = self.chip_number or self.ear_tag
        return f"https://memio.pet/pas/{identifier}"

    @property
    def is_verified(self):
        return bool(self.breeder and self.breeder.verified_badge)


class PetHealthRecord(models.Model):
    """Zdravstveni karton — vezan za AnimalProfile u istoj bazi."""
    TIP_CHOICES = [
        ('cijepljenje', 'Cijepljenje'),
        ('pregled',     'Veterinarski pregled'),
        ('lijek',       'Lijek / Terapija'),
        ('operacija',   'Operacija'),
        ('karantena',   'Karantena'),
        ('ostalo',      'Ostalo'),
    ]

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    animal      = models.ForeignKey(AnimalProfile, on_delete=models.CASCADE, related_name='health_records')
    datum       = models.DateField()
    tip         = models.CharField(max_length=20, choices=TIP_CHOICES, default='pregled')
    opis        = models.TextField(blank=True)
    veterinar   = models.CharField(max_length=100, blank=True)
    vet_profile = models.ForeignKey(
        'VeterinarProfile', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='health_records',
        verbose_name='Veterinar (verificiran)')
    lijek       = models.CharField(max_length=200, blank=True)
    trosak_eur  = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'memio_pet'
        ordering  = ['-datum']

    def __str__(self):
        return f"{self.get_tip_display()} — {self.animal.name or self.animal.ear_tag} ({self.datum})"


class PetOwnership(models.Model):
    """
    Lanac vlasništva — tko je imao psa i kada.
    Omogućuje transfer: breeder → kupac → novi vlasnik.
    """
    TRANSFER_TYPE_CHOICES = [
        ('initial',   'Inicijalni upis (uzgajivač)'),
        ('sale',      'Prodaja'),
        ('adoption',  'Udomljavanje'),
        ('transfer',  'Prijenos vlasništva'),
        ('return',    'Povrat uzgajivaču'),
    ]

    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    animal          = models.ForeignKey(AnimalProfile, on_delete=models.CASCADE, related_name='ownership_chain')
    transfer_type   = models.CharField(max_length=20, choices=TRANSFER_TYPE_CHOICES)

    # Vlasnik (denormalizirano — fizičke osobe nisu u registrima)
    owner_name      = models.CharField(max_length=200)
    owner_email     = MemioEncryptedField(blank=True)  # AES encrypted
    owner_oib       = MemioEncryptedField(blank=True)  # AES encrypted
    owner_address   = MemioEncryptedField(blank=True)  # AES encrypted
    owner_city      = models.CharField(max_length=100, blank=True)

    acquired_at     = models.DateField()
    released_at     = models.DateField(null=True, blank=True)
    contract_ref    = models.CharField(max_length=100, blank=True)  # Broj ugovora

    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'memio_pet'
        ordering  = ['-acquired_at']

    def __str__(self):
        return f"{self.owner_name} → {self.animal.name or self.animal.ear_tag}"


class WaitlistEntry(models.Model):
    """
    Waiting lista — migrirana iz core.MemioPetWaitlist.
    Živi u memio_pets bazi.
    """
    PET_TYPE_CHOICES = [
        ('pas', 'Pas'), ('macka', 'Mačka'), ('konj', 'Konj'), ('ostalo', 'Ostalo'),
    ]
    USER_TYPE_CHOICES = [
        ('vlasnik', 'Vlasnik ljubimca'), ('uzgajivac', 'Uzgajivač / Kennel'),
    ]

    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name            = models.CharField(max_length=120, validators=[validate_name_field])
    email           = MemioEncryptedField(unique=False)  # AES encrypted (unique constraint na email_hash)
    email_hash      = models.CharField(max_length=64, unique=True, db_index=True, blank=True)  # SHA-256 za dedup
    pet_type        = models.CharField(max_length=20, choices=PET_TYPE_CHOICES, blank=True)
    user_type       = models.CharField(max_length=20, choices=USER_TYPE_CHOICES, blank=True)
    source          = models.CharField(max_length=50, default='memio.pet')
    ip              = models.GenericIPAddressField(null=True, blank=True)

    # OIB verifikacija (samo uzgajivači / pravne osobe)
    oib             = MemioEncryptedField(blank=True, validators=[validate_oib_format])  # AES encrypted
    is_cro_validated = models.BooleanField(default=False)
    validated_name  = models.CharField(max_length=200, blank=True)
    validated_city  = models.CharField(max_length=100, blank=True)
    validated_at    = models.DateTimeField(null=True, blank=True)

    notified        = models.BooleanField(default=False)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'memio_pet'
        ordering  = ['-created_at']
        verbose_name = 'Waiting lista'

    def save(self, *args, **kwargs):
        # SHA-256 hash emaila za dedup bez pohrane plaintexta u indeks
        import hashlib
        if self.email:
            self.email_hash = hashlib.sha256(
                self.email.strip().lower().encode()
            ).hexdigest()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} <****>"  # Ne logirati email u plaintextu


class VeterinarProfile(models.Model):
    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name            = models.CharField(max_length=200, verbose_name='Ime i prezime')
    clinic_name     = models.CharField(max_length=200, blank=True, verbose_name='Veterinarska ambulanta')
    oib             = MemioEncryptedField(blank=True, validators=[validate_oib_format], verbose_name='OIB')
    license_number  = models.CharField(max_length=50, blank=True, verbose_name='Broj licence HVK')
    email           = MemioEncryptedField(blank=True, verbose_name='Email')
    phone           = models.CharField(max_length=30, blank=True, verbose_name='Telefon')
    city            = models.CharField(max_length=100, blank=True, verbose_name='Grad')
    country         = models.CharField(max_length=5, default='HR')
    is_verified     = models.BooleanField(default=False, verbose_name='HVK verificiran')
    verified_at     = models.DateTimeField(null=True, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'memio_pet'
        ordering  = ['name']
        verbose_name = 'Veterinar'
        verbose_name_plural = 'Veterinari'

    def __str__(self):
        v = ' V' if self.is_verified else ''
        return f'dr. {self.name}{v}'


class VerificationLog(models.Model):
    VERIFICATION_TYPE_CHOICES = [
        ('breeder_oib',    'OIB verifikacija uzgajivaca'),
        ('vet_license',    'Verifikacija veterinarske licence'),
        ('health_cert',    'Zdravstvena potvrda'),
        ('pedigree',       'Rodovnica izdana'),
        ('ownership',      'Prijenos vlasnistva'),
        ('chip_register',  'Registracija mikrocipa'),
    ]

    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    animal          = models.ForeignKey(AnimalProfile, on_delete=models.CASCADE,
                                        related_name='verification_logs', null=True, blank=True)
    breeder         = models.ForeignKey(BreederProfile, on_delete=models.SET_NULL,
                                        null=True, blank=True, related_name='verification_logs')
    veterinar       = models.ForeignKey('VeterinarProfile', on_delete=models.SET_NULL,
                                        null=True, blank=True, related_name='verification_logs')
    verification_type = models.CharField(max_length=20, choices=VERIFICATION_TYPE_CHOICES)
    timestamp       = models.DateTimeField(auto_now_add=True)
    snapshot_data   = models.JSONField(default=dict, blank=True,
                                       help_text='JSON snapshot svih relevantnih podataka')
    sha256_hash     = models.CharField(max_length=64, blank=True, db_index=True)
    verified_by     = models.CharField(max_length=200, blank=True)
    notes           = models.TextField(blank=True)
    is_valid        = models.BooleanField(default=True)

    class Meta:
        app_label = 'memio_pet'
        ordering  = ['-timestamp']
        verbose_name = 'Verifikacijski zapis'
        verbose_name_plural = 'Verifikacijski zapisi'

    def save(self, *args, **kwargs):
        import hashlib, json
        if self.snapshot_data and not self.sha256_hash:
            raw = json.dumps(self.snapshot_data, sort_keys=True, ensure_ascii=False)
            self.sha256_hash = hashlib.sha256(raw.encode()).hexdigest()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.get_verification_type_display()} -- {self.timestamp}'


class BreederReview(models.Model):
    """
    Recenzija kupca — zatvara Trust Score petlju.
    Kupac koji je kupio/udomio zivotinju moze ocijeniti uzgajivaca.
    """
    RATING_CHOICES = [(i, str(i)) for i in range(1, 6)]

    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    breeder         = models.ForeignKey(BreederProfile, on_delete=models.CASCADE, related_name="reviews")
    animal          = models.ForeignKey(AnimalProfile, on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name="reviews")
    reviewer_name   = models.CharField(max_length=120, verbose_name="Ime kupca")
    reviewer_email  = MemioEncryptedField(blank=True, verbose_name="Email kupca")
    rating          = models.IntegerField(choices=RATING_CHOICES, verbose_name="Ocjena (1-5)")
    comment         = models.TextField(blank=True, verbose_name="Komentar", validators=[validate_free_text])
    is_verified_purchase = models.BooleanField(default=False,
                                                verbose_name="Verificirana kupnja",
                                                help_text="Potvrdjeno da je kupac zaista kupio/udomio zivotinju")
    is_published    = models.BooleanField(default=False, verbose_name="Objavljeno")
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "memio_pet"
        ordering  = ["-created_at"]
        verbose_name = "Recenzija kupca"
        verbose_name_plural = "Recenzije kupaca"
        unique_together = [("breeder", "reviewer_name")]

    def __str__(self):
        stars = "★" * self.rating + "☆" * (5 - self.rating)
        return f"{stars} {self.reviewer_name} -> {self.breeder.name}"


# ════════════════════════════════════════════════════════════
# BARF Marketplace — circular economy OPG ↔ uzgajivač
# ════════════════════════════════════════════════════════════

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

    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                                 related_name='raw_food_listings')
    product_type = models.CharField(max_length=30, choices=PRODUCT_CHOICES)
    quantity_kg = models.DecimalField(max_digits=8, decimal_places=2, verbose_name='Količina (kg)')
    price_eur_kg = models.DecimalField(max_digits=6, decimal_places=2, verbose_name='Cijena EUR/kg')
    available_from = models.DateField(verbose_name='Dostupno od')
    expires_at = models.DateField(verbose_name='Rok (sirovina)')
    k3_cert_number = models.CharField(max_length=100, blank=True, verbose_name='K3 veterinarska potvrda')
    is_antibiotic_free = models.BooleanField(default=False, verbose_name='Bez antibiotika')
    is_free_range = models.BooleanField(default=False, verbose_name='Slobodan uzgoj')
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'BARF ponuda'
        verbose_name_plural = 'BARF ponude'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_product_type_display()} — {self.quantity_kg}kg | {self.company.name}"

    @property
    def total_eur(self):
        return self.quantity_kg * self.price_eur_kg

    def save(self, *args, **kwargs):
        if not self.latitude and self.company:
            self.latitude = getattr(self.company, 'latitude', None)
            self.longitude = getattr(self.company, 'longitude', None)
        super().save(*args, **kwargs)


class RawFoodOrder(models.Model):
    STATUS_CHOICES = [
        ('pending',   'Čeka potvrdu'),
        ('confirmed', 'Potvrđeno'),
        ('picked_up', 'Preuzeto'),
        ('cancelled', 'Otkazano'),
    ]

    listing = models.ForeignKey(RawFoodListing, on_delete=models.CASCADE, related_name='orders')
    breeder = models.ForeignKey('BreederProfile', on_delete=models.SET_NULL,
                                 null=True, blank=True, related_name='barf_orders')
    buyer_company = models.ForeignKey('companies.Company', on_delete=models.SET_NULL,
                                       null=True, blank=True)
    quantity_kg = models.DecimalField(max_digits=8, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    batch_id = models.CharField(max_length=50, blank=True,
                                 help_text='RF-YYYY-NNNN — sljedivost od OPG do zdjelice')
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'BARF narudžba'
        verbose_name_plural = 'BARF narudžbe'

    def __str__(self):
        return f"{self.batch_id or self.pk} — {self.quantity_kg}kg | {self.status}"

    def save(self, *args, **kwargs):
        if not self.batch_id:
            import datetime
            seq = RawFoodOrder.objects.filter(created_at__year=datetime.date.today().year).count() + 1
            self.batch_id = f"RF-{datetime.date.today().year}-{seq:04d}"
        super().save(*args, **kwargs)


class DogTrainingSession(models.Model):
    """Evidencija dresure / treninga psa."""

    TRAINING_TYPES = [
        ('osnovna',        'Osnovna poslušnost'),
        ('napredna',       'Napredna poslušnost'),
        ('agility',        'Agility / Prepreke'),
        ('zastita',        'Zaštitarska dresura'),
        ('terapijski',     'Terapijski rad'),
        ('socijalizacija', 'Socijalizacija'),
        ('modificiranje',  'Modifikacija ponašanja'),
        ('ostalo',         'Ostalo'),
    ]
    STATUS_CHOICES = [
        ('zakazano',   'Zakazano'),
        ('u_tijeku',   'U tijeku'),
        ('zavrseno',   'Završeno'),
        ('otkazano',   'Otkazano'),
    ]

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    animal      = models.ForeignKey(AnimalProfile, on_delete=models.CASCADE, related_name='training_sessions')
    trainer     = models.ForeignKey(BreederProfile, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='training_sessions', limit_choices_to={'account_type': 'trainer'})

    training_type = models.CharField(max_length=20, choices=TRAINING_TYPES, default='osnovna')
    datum         = models.DateField()
    vrijeme_od    = models.TimeField(null=True, blank=True)
    vrijeme_do    = models.TimeField(null=True, blank=True)
    trajanje_min  = models.PositiveIntegerField(default=60, verbose_name='Trajanje (min)')

    lokacija      = models.CharField(max_length=200, blank=True, verbose_name='Lokacija treninga')
    biljeske      = models.TextField(blank=True, verbose_name='Bilješke trenera')
    ocjena        = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='Ocjena (1-10)',
                                                      help_text='Napredak psa na sesiji')

    cijena_eur    = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    status        = models.CharField(max_length=15, choices=STATUS_CHOICES, default='zakazano')

    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'memio_pet'
        ordering = ['-datum', '-vrijeme_od']
        verbose_name = 'Trening sesija'
        verbose_name_plural = 'Trening sesije'

    def __str__(self):
        return f"{self.get_training_type_display()} — {self.animal.name or self.animal.ear_tag} ({self.datum})"


class PetBoardingReservation(models.Model):
    """Rezervacija u pet hotelu / pansionu."""

    STATUS_CHOICES = [
        ('pending',    'Na čekanju'),
        ('confirmed',  'Potvrđeno'),
        ('checked_in', 'Prijavljen'),
        ('checked_out','Odjavljen'),
        ('cancelled',  'Otkazano'),
    ]
    ROOM_TYPES = [
        ('standard',  'Standardna soba'),
        ('premium',   'Premium soba'),
        ('suite',     'Suite (VIP)'),
        ('outdoor',   'Vanjski prostor'),
        ('shared',    'Zajednički prostor'),
    ]

    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    animal          = models.ForeignKey(AnimalProfile, on_delete=models.CASCADE, related_name='boarding_reservations')
    hotel           = models.ForeignKey(BreederProfile, on_delete=models.CASCADE,
                                        related_name='boarding_reservations', limit_choices_to={'account_type': 'hotel'})

    # Vlasnik kontakt (denormalizirano za brz pristup)
    owner_name      = models.CharField(max_length=200)
    owner_phone     = models.CharField(max_length=30)
    owner_email     = models.EmailField(blank=True)

    # Datumi
    check_in        = models.DateField(verbose_name='Prijava')
    check_out       = models.DateField(verbose_name='Odjava')
    room_type       = models.CharField(max_length=15, choices=ROOM_TYPES, default='standard')

    # Posebne potrebe
    special_diet    = models.TextField(blank=True, verbose_name='Posebna prehrana')
    medical_notes   = models.TextField(blank=True, verbose_name='Zdravstvene napomene')
    emergency_contact = models.CharField(max_length=100, blank=True, verbose_name='Hitni kontakt')

    # Cijena
    price_per_night = models.DecimalField(max_digits=8, decimal_places=2, default=60)
    total_price     = models.DecimalField(max_digits=10, decimal_places=2, default=0, editable=False)

    status          = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')
    notes           = models.TextField(blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'memio_pet'
        ordering = ['-check_in']
        verbose_name = 'Rezervacija (Pet Hotel)'
        verbose_name_plural = 'Rezervacije (Pet Hotel)'

    def __str__(self):
        return f"{self.animal.name or self.animal.ear_tag} @ {self.hotel.name} ({self.check_in} → {self.check_out})"

    def save(self, *args, **kwargs):
        if self.check_in and self.check_out:
            nights = (self.check_out - self.check_in).days
            self.total_price = self.price_per_night * max(nights, 1)
        super().save(*args, **kwargs)

    @property
    def nights(self):
        if self.check_in and self.check_out:
            return (self.check_out - self.check_in).days
        return 0
