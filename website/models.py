from django.db import models
from django.utils.translation import gettext_lazy as _
from core.managers import CompanyManager


class SitePage(models.Model):
    SLUG_CHOICES = [
        ('home', 'Početna (viskovic-group.de)'),
        ('about', 'O nama'),
        ('contact', 'Kontakt'),
    ]
    slug = models.CharField(max_length=50, choices=SLUG_CHOICES, unique=True)
    is_active = models.BooleanField(default=True, verbose_name=_('Aktivno'))
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Stranica')
        verbose_name_plural = _('Stranice')

    def __str__(self):
        return self.get_slug_display()


class HeroSection(models.Model):
    page = models.OneToOneField(SitePage, on_delete=models.CASCADE, related_name='hero')
    title_hr = models.CharField(max_length=200, verbose_name='Naslov (HR)')
    title_de = models.CharField(max_length=200, blank=True, verbose_name='Naslov (DE)')
    title_en = models.CharField(max_length=200, blank=True, verbose_name='Naslov (EN)')
    subtitle_hr = models.TextField(blank=True, verbose_name='Podnaslov (HR)')
    subtitle_de = models.TextField(blank=True, verbose_name='Podnaslov (DE)')
    subtitle_en = models.TextField(blank=True, verbose_name='Podnaslov (EN)')
    background_image = models.ImageField(upload_to='website/hero/', null=True, blank=True,
                                          verbose_name=_('Pozadinska slika'))
    background_video = models.FileField(upload_to='website/hero/', null=True, blank=True,
                                         verbose_name=_('Video pozadina'))
    cta_text_hr = models.CharField(max_length=100, blank=True, verbose_name='CTA gumb (HR)')
    cta_text_de = models.CharField(max_length=100, blank=True, verbose_name='CTA gumb (DE)')
    cta_text_en = models.CharField(max_length=100, blank=True, verbose_name='CTA gumb (EN)')
    cta_url = models.CharField(max_length=255, blank=True, verbose_name='CTA link')

    class Meta:
        verbose_name = _('Hero sekcija')
        verbose_name_plural = _('Hero sekcije')

    def __str__(self):
        return f"Hero – {self.page}"


class Brand(models.Model):
    name = models.CharField(max_length=100, verbose_name=_('Naziv brenda'))
    slug = models.SlugField(unique=True)
    icon = models.CharField(max_length=10, default='🏢', verbose_name=_('Emoji ikona'))
    logo = models.ImageField(upload_to='website/brands/', null=True, blank=True,
                              verbose_name=_('Logo'))
    tagline_hr = models.CharField(max_length=200, blank=True, verbose_name='Tagline (HR)')
    tagline_de = models.CharField(max_length=200, blank=True, verbose_name='Tagline (DE)')
    tagline_en = models.CharField(max_length=200, blank=True, verbose_name='Tagline (EN)')
    desc_hr = models.TextField(blank=True, verbose_name='Opis (HR)')
    desc_de = models.TextField(blank=True, verbose_name='Opis (DE)')
    desc_en = models.TextField(blank=True, verbose_name='Opis (EN)')
    url = models.URLField(blank=True, verbose_name=_('Web stranica'))
    order = models.PositiveIntegerField(default=0, verbose_name=_('Redoslijed'))
    is_active = models.BooleanField(default=True, verbose_name=_('Aktivno'))

    class Meta:
        verbose_name = _('Brend')
        verbose_name_plural = _('Brendovi')
        ordering = ['order']

    def __str__(self):
        return self.name


class GalleryImage(models.Model):
    CATEGORY = [
        ('bau', 'Visković BAU'),
        ('wildberg', 'Wildberg'),
        ('najam', 'VG Najam'),
        ('webshop', 'VG Shop'),
        ('team', 'Tim'),
        ('product', 'Proizvod'),
        ('hero', 'Naslovna'),
        ('interior', 'Interijer'),
        ('logo', 'Logo'),
        ('promo', 'Promocija'),
        ('other', 'Ostalo'),
    ]
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                                 null=True, blank=True, related_name='gallery_images', verbose_name='Tvrtka')
    image = models.ImageField(upload_to='website/gallery/', verbose_name=_('Slika'))
    title = models.CharField(max_length=100, blank=True, verbose_name='Naslov')
    caption_hr = models.CharField(max_length=200, blank=True, verbose_name='Opis (HR)')
    caption_de = models.CharField(max_length=200, blank=True, verbose_name='Opis (DE)')
    caption_en = models.CharField(max_length=200, blank=True, verbose_name='Opis (EN)')
    category = models.CharField(max_length=20, choices=CATEGORY, default='other')
    order = models.PositiveIntegerField(default=0)
    sort_order = models.IntegerField(default=0, verbose_name='Redoslijed')
    is_active = models.BooleanField(default=True)
    uploaded_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True, null=True)
    objects = CompanyManager()

    class Meta:
        verbose_name = _('Galerijska slika')
        verbose_name_plural = _('Galerija')
        ordering = ['order']

    def __str__(self):
        return self.caption_hr or f"Slika {self.id}"


class CompanyInfo(models.Model):
    """Kontakt podaci za footer/kontakt stranicu"""
    company = models.OneToOneField('companies.Company', on_delete=models.CASCADE,
                                    related_name='website_info')
    show_on_homepage = models.BooleanField(default=True)
    contact_person = models.CharField(max_length=100, blank=True)
    contact_phone = models.CharField(max_length=50, blank=True)
    contact_email = models.EmailField(blank=True)
    about_hr = models.TextField(blank=True, verbose_name='O tvrtki (HR)')
    about_de = models.TextField(blank=True, verbose_name='O tvrtki (DE)')
    about_en = models.TextField(blank=True, verbose_name='O tvrtki (EN)')

    class Meta:
        verbose_name = _('Info o tvrtki (web)')
        verbose_name_plural = _('Info o tvrtkama (web)')

    def __str__(self):
        return f"Web info – {self.company.name}"


# ── Hitne intervencije ───────────────────────────────────────────────────────

class HitnaIntervencija(models.Model):
    """
    Zahtjev za hitnu intervenciju (Notfall) s javne stranice viskovic-group.de
    """
    VRSTA_CHOICES = [
        ('voda',      'Voda / Poplave'),
        ('elektrika', 'Elektrika'),
        ('grijanje',  'Grijanje / Klima'),
        ('fasada',    'Fasada / Krov'),
        ('ostalo',    'Ostalo'),
    ]
    STATUS_CHOICES = [
        ('novo',       'Novi zahtjev'),
        ('kontaktiran','Kontaktiran'),
        ('u_radu',     'U radu'),
        ('zavrseno',   'Završeno'),
        ('otkazano',   'Otkazano'),
    ]

    # Podaci podnositelja
    ime         = models.CharField(max_length=120, verbose_name=_('Ime i prezime'))
    telefon     = models.CharField(max_length=50, verbose_name=_('Telefon'))
    email       = models.EmailField(blank=True, verbose_name=_('E-mail'))
    adresa      = models.CharField(max_length=255, blank=True, verbose_name=_('Adresa'))
    grad        = models.CharField(max_length=100, blank=True, verbose_name=_('Grad'))
    drzava      = models.CharField(max_length=10, default='DE', verbose_name=_('Država'))

    # Problem
    vrsta       = models.CharField(max_length=20, choices=VRSTA_CHOICES, default='ostalo',
                                   verbose_name=_('Vrsta intervencije'))
    opis        = models.TextField(verbose_name=_('Opis problema'))
    hitnost     = models.BooleanField(default=True, verbose_name=_('Hitan slučaj (odmah)'))

    # Interni status
    status      = models.CharField(max_length=20, choices=STATUS_CHOICES, default='novo',
                                   verbose_name=_('Status'))
    napomena    = models.TextField(blank=True, verbose_name=_('Interna napomena'))
    dodijeljeno = models.ForeignKey(
        'auth.User', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='hitne_intervencije', verbose_name=_('Dodijeljeno')
    )

    # Metapodaci
    ip_adresa   = models.GenericIPAddressField(null=True, blank=True)
    jezik       = models.CharField(max_length=5, default='de', verbose_name=_('Jezik'))
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = _('Hitna intervencija')
        verbose_name_plural = _('Hitne intervencije')
        ordering            = ['-created_at']

    def __str__(self):
        return f'{self.ime} — {self.get_vrsta_display()} ({self.created_at:%d.%m.%Y %H:%M})'


# ── Video galerija ───────────────────────────────────────────────────────────

class VideoGallery(models.Model):
    """
    Video galerija za viskovic-group.de.
    Podržava YouTube/Vimeo embed i direktni upload .mp4
    """
    KATEGORIJA_CHOICES = [
        ('bau',       'Visković BAU'),
        ('wildberg',  'Wildberg'),
        ('najam',     'VG Najam'),
        ('webshop',   'VG Shop'),
        ('projekt',   'Projekt reference'),
        ('tim',       'Tim / Ekipa'),
        ('ostalo',    'Ostalo'),
    ]

    naslov_hr   = models.CharField(max_length=200, verbose_name=_('Naslov (HR)'))
    naslov_de   = models.CharField(max_length=200, blank=True, verbose_name=_('Naslov (DE)'))
    naslov_en   = models.CharField(max_length=200, blank=True, verbose_name=_('Naslov (EN)'))
    opis_hr     = models.TextField(blank=True, verbose_name=_('Opis (HR)'))
    opis_de     = models.TextField(blank=True, verbose_name=_('Opis (DE)'))
    opis_en     = models.TextField(blank=True, verbose_name=_('Opis (EN)'))

    # Video izvor — embed URL ili upload
    embed_url   = models.URLField(blank=True, verbose_name=_('YouTube / Vimeo URL'),
                                  help_text=_('Npr. https://www.youtube.com/watch?v=...'))
    video_file  = models.FileField(upload_to='website/videos/', null=True, blank=True,
                                   verbose_name=_('Video datoteka (.mp4)'))
    thumbnail   = models.ImageField(upload_to='website/video_thumbs/', null=True, blank=True,
                                    verbose_name=_('Thumbnail'))

    kategorija  = models.CharField(max_length=20, choices=KATEGORIJA_CHOICES, default='ostalo',
                                   verbose_name=_('Kategorija'))
    trajanje    = models.CharField(max_length=20, blank=True, verbose_name=_('Trajanje'),
                                   help_text=_('Npr. 2:34'))
    redoslijed  = models.PositiveIntegerField(default=0, verbose_name=_('Redoslijed'))
    is_active   = models.BooleanField(default=True, verbose_name=_('Aktivno'))
    is_featured = models.BooleanField(default=False, verbose_name=_('Istaknuto'))
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = _('Video')
        verbose_name_plural = _('Video galerija')
        ordering            = ['redoslijed', '-created_at']

    def __str__(self):
        return self.naslov_hr or self.naslov_de or f'Video {self.id}'

    @property
    def embed_id(self):
        """Izvuče YouTube video ID iz URL-a"""
        import re
        if not self.embed_url:
            return None
        m = re.search(r'(?:v=|youtu\.be/)([\w-]{11})', self.embed_url)
        return m.group(1) if m else None

    @property
    def is_youtube(self):
        return 'youtube' in (self.embed_url or '') or 'youtu.be' in (self.embed_url or '')

    @property
    def is_vimeo(self):
        return 'vimeo' in (self.embed_url or '')

    @property
    def embed_src(self):
        """Vraća src za <iframe>"""
        if self.is_youtube and self.embed_id:
            return f'https://www.youtube.com/embed/{self.embed_id}'
        if self.is_vimeo:
            import re
            m = re.search(r'vimeo\.com/(\d+)', self.embed_url)
            if m:
                return f'https://player.vimeo.com/video/{m.group(1)}'
        return None

class SiteSettings(models.Model):
    """Globalne postavke javne web stranice (Kontakt, Godina, itd.)"""
    company_name = models.CharField(max_length=100, default="Visković Group", verbose_name="Naziv tvrtke")
    founded_year = models.IntegerField(default=2018, verbose_name="Godina osnivanja (DE)")
    phone_1_name = models.CharField(max_length=50, default="Dragan", verbose_name="Kontakt 1 Ime")
    phone_1_number = models.CharField(max_length=30, default="+4917684397173", verbose_name="Kontakt 1 Broj")
    phone_2_name = models.CharField(max_length=50, default="Nikša", verbose_name="Kontakt 2 Ime")
    phone_2_number = models.CharField(max_length=30, default="+4915234209056", verbose_name="Kontakt 2 Broj")
    email = models.EmailField(default="viskovic.bau@gmail.com", verbose_name="Glavni E-mail")

    class Meta:
        verbose_name = "Postavke Weba"
        verbose_name_plural = "Postavke Weba"

    def __str__(self):
        return f"Postavke: {self.company_name}"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MULTI-TENANT WEBSITE BUILDER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class CompanyWebsite(models.Model):
    THEME_CHOICES = [
        ('generic',      'Generički'),
        ('construction', 'Građevina'),
        ('gastro',       'Gastro'),
        ('retail',       'Prodaja'),
        ('services',     'Usluge'),
    ]
    company      = models.OneToOneField(
        'companies.Company', on_delete=models.CASCADE, related_name='website'
    )
    slug         = models.SlugField(unique=True, help_text='URL: /site/<slug>/')
    theme        = models.CharField(max_length=20, choices=THEME_CHOICES, default='generic')
    is_published = models.BooleanField(default=False)
    site_title   = models.CharField(max_length=200, blank=True)
    tagline      = models.CharField(max_length=300, blank=True)
    logo         = models.ImageField(upload_to='website/company_sites/', null=True, blank=True)
    hero_image   = models.ImageField(upload_to='website/company_sites/', null=True, blank=True)
    hero_text    = models.TextField(blank=True)
    about_text   = models.TextField(blank=True)
    contact_phone   = models.CharField(max_length=50, blank=True)
    contact_email   = models.EmailField(blank=True)
    contact_address = models.CharField(max_length=300, blank=True)
    facebook_url  = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)
    primary_color = models.CharField(max_length=7, default='#2563eb')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = _('Web stranica tvrtke')
        verbose_name_plural = _('Web stranice tvrtki')

    def __str__(self):
        return f"{self.company.name} -- /site/{self.slug}/"

    @property
    def public_url(self):
        return f"/site/{self.slug}/"


class WebsiteService(models.Model):
    website     = models.ForeignKey(CompanyWebsite, on_delete=models.CASCADE,
                                    related_name='services')
    title       = models.CharField(max_length=200, verbose_name=_('Naziv usluge'))
    description = models.TextField(blank=True, verbose_name=_('Opis'))
    icon        = models.CharField(max_length=60, blank=True,
                                   help_text='Font Awesome klasa, npr. fa-wrench')
    price_display = models.CharField(max_length=100, blank=True)
    order       = models.PositiveIntegerField(default=0)
    is_active   = models.BooleanField(default=True)

    class Meta:
        ordering            = ['order']
        verbose_name        = _('Usluga (web)')
        verbose_name_plural = _('Usluge (web)')

    def __str__(self):
        return self.title


class WebsiteGalleryImage(models.Model):
    website   = models.ForeignKey(CompanyWebsite, on_delete=models.CASCADE,
                                  related_name='gallery')
    image     = models.ImageField(upload_to='website/company_gallery/')
    caption   = models.CharField(max_length=200, blank=True)
    order     = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering            = ['order', '-id']
        verbose_name        = _('Galerijska slika (web)')
        verbose_name_plural = _('Galerija (web)')

    def __str__(self):
        return self.caption or "Slika " + str(self.id)


class WebsiteReview(models.Model):
    website     = models.ForeignKey(CompanyWebsite, on_delete=models.CASCADE,
                                    related_name='reviews')
    author_name = models.CharField(max_length=100)
    rating      = models.PositiveSmallIntegerField(
        default=5,
        choices=[(i, str(i)) for i in range(1, 6)],
    )
    text        = models.TextField()
    is_approved = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering            = ['-created_at']
        verbose_name        = _('Recenzija (web)')
        verbose_name_plural = _('Recenzije (web)')

    def __str__(self):
        return f"{self.author_name} -- {self.rating}*"


class WebsiteContactMessage(models.Model):
    website    = models.ForeignKey(CompanyWebsite, on_delete=models.CASCADE,
                                   related_name='contact_messages')
    name       = models.CharField(max_length=100)
    email      = models.EmailField()
    phone      = models.CharField(max_length=50, blank=True)
    message    = models.TextField()
    is_read    = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering            = ['-created_at']
        verbose_name        = _('Kontakt poruka (web)')
        verbose_name_plural = _('Kontakt poruke (web)')

    def __str__(self):
        return f"{self.name}"



class GrosmarktAnfrage(models.Model):
    """Demo-Anfrage s grosmarkt-online.eu"""
    STATUS_CHOICES = [
        ('new',        'Nova / Neu'),
        ('contacted',  'Kontaktiran / Kontaktiert'),
        ('demo_done',  'Demo odrađen / Demo durchgeführt'),
        ('converted',  'Pretvoren u klijenta / Konvertiert'),
        ('declined',   'Odbio / Abgelehnt'),
    ]
    name        = models.CharField(max_length=200, verbose_name='Ime i prezime')
    company     = models.CharField(max_length=200, verbose_name='Firma / Unternehmen')
    email       = models.EmailField(verbose_name='E-Mail')
    phone       = models.CharField(max_length=50, blank=True, verbose_name='Telefon')
    message     = models.TextField(blank=True, verbose_name='Poruka / Nachricht')
    status      = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    ip_address  = models.GenericIPAddressField(null=True, blank=True)
    user_agent  = models.CharField(max_length=300, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    contacted_at = models.DateTimeField(null=True, blank=True)
    notes       = models.TextField(blank=True, verbose_name='Interne Notizen')

    class Meta:
        verbose_name = 'Grosmarkt Anfrage'
        verbose_name_plural = 'Grosmarkt Anfragen'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.company} — {self.name} ({self.created_at.strftime('%d.%m.%Y')})"


class KorpasTermin(models.Model):
    VRSTA = [
        ('osobno', 'Osobno vozilo'),
        ('teretno', 'Teretno vozilo'),
        ('kombi', 'Kombi / Van'),
        ('ostalo', 'Ostalo'),
    ]
    USLUGE = [
        ('vulkanizacija', 'Vulkanizacija (zamjena / balansiranje)'),
        ('mehanika', 'Mehanička dijagnostika'),
        ('obd', 'OBD dijagnostika (skeniranje)'),
        ('ulje', 'Zamjena ulja i filtera'),
        ('registracija', 'Priprema za tehnički pregled'),
        ('ugradnja', 'Ugradnja opreme'),
        ('ostalo', 'Ostalo'),
    ]
    STATUS = [
        ('novi', 'Novi'),
        ('potvrdjen', 'Potvrđen'),
        ('obavljen', 'Obavljen'),
        ('otkazan', 'Otkazan'),
    ]
    ime            = models.CharField(max_length=100, verbose_name='Ime i prezime')
    telefon        = models.CharField(max_length=20, verbose_name='Telefon')
    vrsta_vozila   = models.CharField(max_length=20, choices=VRSTA, verbose_name='Vrsta vozila')
    usluga         = models.CharField(max_length=30, choices=USLUGE, verbose_name='Usluga')
    datum          = models.DateField(verbose_name='Željeni datum')
    vrijeme        = models.TimeField(verbose_name='Željeno vrijeme')
    napomena       = models.TextField(blank=True, verbose_name='Napomena')
    status         = models.CharField(max_length=20, choices=STATUS, default='novi')
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['datum', 'vrijeme']
        verbose_name = 'Korpaš — Termin'
        verbose_name_plural = 'Korpaš — Termini'

    def __str__(self):
        return f"{self.ime} | {self.get_usluga_display()} | {self.datum} {self.vrijeme}"


class KorpasRezervacija(models.Model):
    """Rezervacije za Široki Šor (stol, sala, kušaonica)"""
    VRSTA = [
        ('stol', 'Rezervacija stola'),
        ('sala', 'Najam sale (do 50 osoba)'),
        ('kusaonica', 'Kušaonica sira'),
    ]
    ime            = models.CharField(max_length=100, verbose_name='Ime i prezime')
    telefon        = models.CharField(max_length=20, verbose_name='Telefon')
    vrsta          = models.CharField(max_length=20, choices=VRSTA, verbose_name='Vrsta rezervacije')
    datum          = models.DateField(verbose_name='Datum')
    broj_gostiju   = models.PositiveIntegerField(default=1, verbose_name='Broj gostiju')
    napomena       = models.TextField(blank=True, verbose_name='Napomena / Posebni zahtjevi')
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['datum']
        verbose_name = 'Široki Šor — Rezervacija'
        verbose_name_plural = 'Široki Šor — Rezervacije'

    def __str__(self):
        return f"{self.ime} | {self.get_vrsta_display()} | {self.datum}"


class NoLimitPartner(models.Model):
    """Firme koje se prijavljuju za No Limit / AirCash mrežu"""
    naziv_firme    = models.CharField(max_length=200, verbose_name='Naziv firme')
    oib            = models.CharField(max_length=11, blank=True, verbose_name='OIB')
    kontakt_osoba  = models.CharField(max_length=100, verbose_name='Kontakt osoba')
    telefon        = models.CharField(max_length=20, verbose_name='Telefon')
    adresa         = models.CharField(max_length=200, verbose_name='Adresa')
    status         = models.CharField(max_length=20, default='prijava',
                        choices=[('prijava','Prijava'),('aktivan','Aktivan'),('odbijen','Odbijen')])
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'No Limit — Partner prijava'
        verbose_name_plural = 'No Limit — Partner prijave'

    def __str__(self):
        return f"{self.naziv_firme} | {self.kontakt_osoba}"
