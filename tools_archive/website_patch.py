"""
Dodaje HitnaIntervencija i VideoGallery modele u website/models.py
"""

MODELS_FILE = '/var/www/fina-connect/website/models.py'

NEW_MODELS = '''

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
        m = re.search(r'(?:v=|youtu\.be/)([\\w-]{11})', self.embed_url)
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
            m = re.search(r'vimeo\\.com/(\\d+)', self.embed_url)
            if m:
                return f'https://player.vimeo.com/video/{m.group(1)}'
        return None
'''

with open(MODELS_FILE) as f:
    content = f.read()

if 'class HitnaIntervencija' not in content:
    content += NEW_MODELS
    with open(MODELS_FILE, 'w') as f:
        f.write(content)
    print('OK: HitnaIntervencija + VideoGallery added to website/models.py')
else:
    print('SKIP: already exists')
