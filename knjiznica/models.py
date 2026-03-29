from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from decimal import Decimal
from core.managers import CompanyManager
from borg_ops.mixins import FSMMixin


# ═══════════════════════════════════════════════════════
# CORE MODELS (MVP)
# ═══════════════════════════════════════════════════════

class BookMeta(models.Model):
    """
    Proširenje Inventory Item-a s knjižničnim podacima.
    Veza: 1:1 s inventory.InventoryItem
    """
    item = models.OneToOneField(
        'inventory.InventoryItem',
        on_delete=models.CASCADE,
        related_name='book_meta',
        verbose_name=_('Artikl')
    )
    isbn = models.CharField(max_length=20, blank=True, verbose_name='ISBN')
    author = models.CharField(max_length=300, blank=True, verbose_name=_('Autor'))
    publisher = models.CharField(max_length=200, blank=True, verbose_name=_('Nakladnik'))
    pub_year = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name=_('Godina'))
    shelf_location = models.CharField(
        max_length=50, blank=True,
        verbose_name=_('Polica'),
        help_text=_('npr. A-02-3 (ormar A, polica 2, pozicija 3)')
    )
    is_reference = models.BooleanField(
        default=False,
        verbose_name=_('Referentna građa'),
        help_text=_('Ako True, knjiga se ne posuđuje (enciklopedije, rječnici)')
    )
    copy_number = models.PositiveSmallIntegerField(default=1, verbose_name=_('Primjerak br.'))
    # Gamifikacija / portal
    cover_image = models.ImageField(
        upload_to='knjiznica/covers/', blank=True,
        verbose_name=_('Naslovna slika')
    )
    age_tier = models.CharField(max_length=15, blank=True, choices=[
        ('mrvice', 'Mrvice (0-5)'),
        ('explorer', 'Istraživači (6-9)'),
        ('navigator', 'Navigatori (10-14)'),
        ('voyager', 'Putnici (15-18)'),
        ('adult', 'Odrasli (18+)'),
    ], verbose_name=_('Dobna grupa'))
    genre = models.CharField(max_length=50, blank=True, verbose_name=_('Žanr'),
        help_text=_('krimic, sf, bajka, povijesni, priroda, poezija...'))
    description = models.TextField(blank=True, verbose_name=_('Kratki opis'))

    class Meta:
        verbose_name = _('Podaci knjige')
        verbose_name_plural = _('Podaci knjiga')

    def __str__(self):
        return f'{self.item.name} — {self.author} ({self.isbn or "bez ISBN"})'


class LibraryMember(models.Model):
    """
    Član knjižnice — wrapper oko Partners.Partner.
    """
    STATUS_CHOICES = [
        ('active',    _('Aktivan')),
        ('expired',   _('Isteklo članstvo')),
        ('suspended', _('Suspendiran (duguje kazne)')),
        ('junior',    _('Junior (do 18 god.)')),
    ]
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='library_members'
    )
    partner = models.ForeignKey(
        'partners.Partner', on_delete=models.CASCADE,
        related_name='library_memberships',
        verbose_name=_('Partner')
    )
    member_number = models.CharField(max_length=20, verbose_name=_('Broj iskaznice'))
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='active')
    membership_from = models.DateField(default=timezone.localdate, verbose_name=_('Član od'))
    membership_until = models.DateField(verbose_name=_('Vrijedi do'))
    max_concurrent_loans = models.PositiveSmallIntegerField(
        default=3, verbose_name=_('Max istovremenih posudbi')
    )
    total_fines_paid = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    total_fines_outstanding = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    # Portal pristup
    portal_pin = models.CharField(max_length=6, blank=True,
        verbose_name=_('PIN za portal'),
        help_text=_('4-6 znamenki za pristup roditeljskom portalu'))
    objects = CompanyManager()

    class Meta:
        verbose_name = _('Član knjižnice')
        verbose_name_plural = _('Članovi knjižnice')
        unique_together = [('company', 'member_number')]

    def __str__(self):
        return f'{self.partner.name} [{self.member_number}]'

    @property
    def can_borrow(self):
        if self.status not in ('active', 'junior'):
            return False, f'Status: {self.get_status_display()}'
        if self.total_fines_outstanding > 0:
            return False, f'Duguje {self.total_fines_outstanding}€ kazni'
        active_loans = self.loans.filter(status__in=['borrowed', 'overdue']).count()
        if active_loans >= self.max_concurrent_loans:
            return False, f'Dostignut limit ({self.max_concurrent_loans} posudbi)'
        if self.membership_until < timezone.localdate():
            return False, 'Iskaznica istekla'
        return True, 'OK'


class BookLoan(FSMMixin, models.Model):
    """
    Posudba knjige.
    FSM: borrowed → overdue → returned | cancelled
    """
    TRANSITIONS = {
        'borrowed':  ['returned', 'overdue'],
        'overdue':   ['returned'],
        'returned':  [],
        'cancelled': [],
    }
    STATUS_CHOICES = [
        ('borrowed',  _('Posuđeno')),
        ('overdue',   _('Kasni')),
        ('returned',  _('Vraćeno')),
        ('cancelled', _('Otkazano')),
    ]

    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE)
    member = models.ForeignKey(
        LibraryMember, on_delete=models.CASCADE,
        related_name='loans', verbose_name=_('Član')
    )
    item = models.ForeignKey(
        'inventory.InventoryItem', on_delete=models.CASCADE,
        related_name='loans', verbose_name=_('Knjiga')
    )
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='borrowed')

    loan_date = models.DateField(default=timezone.localdate, verbose_name=_('Datum posudbe'))
    due_date = models.DateField(verbose_name=_('Rok povratka'))
    returned_date = models.DateField(null=True, blank=True, verbose_name=_('Vraćeno'))

    fine_per_day = models.DecimalField(
        max_digits=5, decimal_places=2,
        default=Decimal('0.50'), verbose_name=_('Kazna/dan (€)')
    )
    fine_total = models.DecimalField(
        max_digits=8, decimal_places=2,
        default=0, verbose_name=_('Ukupna kazna')
    )
    fine_paid = models.BooleanField(default=False)

    librarian = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name=_('Knjižničar')
    )
    notes = models.CharField(max_length=500, blank=True)
    objects = CompanyManager()

    class Meta:
        verbose_name = _('Posudba')
        verbose_name_plural = _('Posudbe')
        ordering = ['-loan_date']

    def __str__(self):
        return f'{self.member} → {self.item.name} ({self.loan_date})'

    @property
    def days_overdue(self):
        if self.status in ('returned', 'cancelled'):
            return 0
        today = timezone.localdate()
        if today > self.due_date:
            return (today - self.due_date).days
        return 0

    def calculate_fine(self):
        end = self.returned_date or timezone.localdate()
        if end > self.due_date:
            days = (end - self.due_date).days
            self.fine_total = Decimal(str(days)) * self.fine_per_day
        else:
            self.fine_total = Decimal('0.00')
        self.save(update_fields=['fine_total'])
        return self.fine_total

    def _on_transition(self, old_status, new_status, user=None):
        if new_status == 'overdue':
            self.calculate_fine()
            self._notify_overdue()
        elif new_status == 'returned':
            self.returned_date = timezone.localdate()
            self.calculate_fine()
            self.save(update_fields=['returned_date'])
            if self.fine_total > 0:
                self.member.total_fines_outstanding += self.fine_total
                self.member.save(update_fields=['total_fines_outstanding'])
                self._notify_fine()

    def _notify_overdue(self):
        try:
            from core.whatsapp import send_text
            phone = self.member.partner.phone
            if phone:
                send_text(phone=phone, message=(
                    f'Podsjetnik knjiznice\n'
                    f'Knjiga "{self.item.name}" je trebala biti vracena {self.due_date}.\n'
                    f'Kazna: {self.fine_per_day} EUR/dan. Molimo vratite sto prije.'
                ))
        except Exception:
            pass

    def _notify_fine(self):
        try:
            from core.whatsapp import send_text
            phone = self.member.partner.phone
            if phone:
                send_text(phone=phone, message=(
                    f'Knjiga vracena\n'
                    f'"{self.item.name}" vracena. Kazna za kasnjenje: {self.fine_total} EUR.\n'
                    f'Kaznu mozete platiti u knjiznici.'
                ))
        except Exception:
            pass


class BookReservation(models.Model):
    STATUS_CHOICES = [
        ('waiting',   _('Čeka')),
        ('notified',  _('Obaviješten — čeka preuzimanje')),
        ('fulfilled', _('Preuzeto')),
        ('expired',   _('Isteklo')),
        ('cancelled', _('Otkazano')),
    ]
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE)
    member = models.ForeignKey(
        LibraryMember, on_delete=models.CASCADE,
        related_name='reservations'
    )
    item = models.ForeignKey(
        'inventory.InventoryItem', on_delete=models.CASCADE,
        related_name='reservations'
    )
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='waiting')
    reserved_at = models.DateTimeField(auto_now_add=True)
    notified_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateField(
        null=True, blank=True,
        help_text=_('Rezervacija istječe ako se ne preuzme do ovog datuma')
    )
    objects = CompanyManager()

    class Meta:
        verbose_name = _('Rezervacija')
        verbose_name_plural = _('Rezervacije')
        ordering = ['reserved_at']

    def __str__(self):
        return f'{self.member} čeka: {self.item.name}'


# ═══════════════════════════════════════════════════════
# GAMIFIKACIJA + JAVNI PORTAL
# ═══════════════════════════════════════════════════════

class ChildReader(models.Model):
    """
    Dijete člana knjižnice. Roditelj (LibraryMember) je gateway.
    Dijete NEMA vlastiti login — roditelj upravlja.
    GDPR čl. 8: pristanak roditelja za dijete do 16 god.
    """
    TIER_CHOICES = [
        ('mrvice',    'Mrvice (0-5)'),
        ('explorer',  'Istraživači (6-9)'),
        ('navigator', 'Navigatori (10-14)'),
        ('voyager',   'Putnici (15-18)'),
    ]
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE)
    parent = models.ForeignKey(
        LibraryMember, on_delete=models.CASCADE,
        related_name='children', verbose_name=_('Roditelj/skrbnik')
    )
    first_name = models.CharField(max_length=100, verbose_name=_('Ime'))
    birth_year = models.PositiveSmallIntegerField(verbose_name=_('Godina rođenja'))
    tier = models.CharField(max_length=15, choices=TIER_CHOICES, verbose_name=_('Dobna grupa'))
    avatar = models.CharField(max_length=50, default='book-open',
        verbose_name=_('Avatar ikona'),
        help_text=_('Font Awesome ikona bez fa- prefixa'))
    total_points = models.PositiveIntegerField(default=0, verbose_name=_('Ukupni bodovi'))
    books_read = models.PositiveIntegerField(default=0, verbose_name=_('Pročitano knjiga'))
    streak_days = models.PositiveIntegerField(default=0, verbose_name=_('Streak (dana zaredom)'))
    last_activity = models.DateField(null=True, blank=True)
    objects = CompanyManager()

    class Meta:
        verbose_name = _('Dijete čitač')
        verbose_name_plural = _('Djeca čitači')

    def __str__(self):
        return f'{self.first_name} ({self.get_tier_display()})'

    @property
    def age(self):
        return timezone.localdate().year - self.birth_year

    def auto_tier(self):
        a = self.age
        if a <= 5:
            return 'mrvice'
        elif a <= 9:
            return 'explorer'
        elif a <= 14:
            return 'navigator'
        return 'voyager'

    @property
    def level(self):
        if self.books_read < 3:
            return 'Početnik'
        elif self.books_read < 10:
            return 'Čitač'
        elif self.books_read < 25:
            return 'Knjigoljubac'
        elif self.books_read < 50:
            return 'Prvak čitanja'
        return 'Legenda knjižnice'

    @property
    def level_progress(self):
        thresholds = [3, 10, 25, 50, 100]
        for t in thresholds:
            if self.books_read < t:
                prev = thresholds[thresholds.index(t) - 1] if thresholds.index(t) > 0 else 0
                return int((self.books_read - prev) / (t - prev) * 100)
        return 100


class BadgeDefinition(models.Model):
    """Šablona bedža — definira uvjete za osvajanje."""
    CATEGORY_CHOICES = [
        ('genre',      _('Žanr')),
        ('endurance',  _('Ustrajnost')),
        ('community',  _('Zajednica')),
        ('special',    _('Posebni')),
        ('family',     _('Obitelj')),
    ]
    name = models.CharField(max_length=100, verbose_name=_('Naziv'))
    slug = models.SlugField(unique=True)
    description = models.CharField(max_length=300, verbose_name=_('Opis'))
    icon = models.CharField(max_length=50, default='fas fa-star', verbose_name=_('Ikona'))
    color = models.CharField(max_length=20, default='#c8a24e', verbose_name=_('Boja'))
    category = models.CharField(max_length=15, choices=CATEGORY_CHOICES)
    tier = models.CharField(max_length=15, blank=True,
        help_text=_('Prazan = svi tierovi'))
    # Uvjeti
    required_books = models.PositiveSmallIntegerField(default=0,
        help_text=_('Koliko knjiga treba pročitati'))
    required_genre = models.CharField(max_length=50, blank=True,
        help_text=_('Koji žanr (prazno = bilo koji)'))
    required_streak = models.PositiveSmallIntegerField(default=0,
        help_text=_('Minimalni streak u danima'))
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = _('Bedž — definicija')
        verbose_name_plural = _('Bedževi — definicije')
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name


class EarnedBadge(models.Model):
    """Dodijeljeni bedž djetetu."""
    child = models.ForeignKey(ChildReader, on_delete=models.CASCADE, related_name='badges')
    badge = models.ForeignKey(BadgeDefinition, on_delete=models.CASCADE)
    earned_at = models.DateTimeField(auto_now_add=True)
    triggered_by_book = models.ForeignKey(
        'inventory.InventoryItem', on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name=_('Knjiga koja je otključala bedž')
    )

    class Meta:
        verbose_name = _('Osvojeni bedž')
        verbose_name_plural = _('Osvojeni bedževi')
        unique_together = [('child', 'badge')]

    def __str__(self):
        return f'{self.child.first_name} → {self.badge.name}'


class ReadingLog(models.Model):
    """
    Zapis čitanja — dijete (ili roditelj) potvrdi pročitanu knjigu.
    Može biti vezano na posudbu ili samostalno (vlastita knjiga).
    """
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE)
    child = models.ForeignKey(ChildReader, on_delete=models.CASCADE, related_name='reading_logs')
    item = models.ForeignKey(
        'inventory.InventoryItem', on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name=_('Knjiga iz kataloga')
    )
    custom_title = models.CharField(max_length=200, blank=True,
        verbose_name=_('Naslov (ako nije iz kataloga)'))
    read_date = models.DateField(default=timezone.localdate)
    rating = models.PositiveSmallIntegerField(
        default=0, verbose_name=_('Ocjena (1-5 zvjezdica)'))
    short_review = models.CharField(max_length=500, blank=True,
        verbose_name=_('Kratka recenzija'))
    points_earned = models.PositiveSmallIntegerField(default=10)
    objects = CompanyManager()

    class Meta:
        verbose_name = _('Zapis čitanja')
        verbose_name_plural = _('Zapisi čitanja')
        ordering = ['-read_date']

    def __str__(self):
        title = self.item.name if self.item else self.custom_title
        return f'{self.child.first_name}: {title}'

    @property
    def book_title(self):
        return self.item.name if self.item else self.custom_title

    def save(self, **kwargs):
        is_new = self.pk is None
        super().save(**kwargs)
        if is_new:
            self.child.books_read += 1
            self.child.total_points += self.points_earned
            self.child.last_activity = self.read_date
            self.child.save(update_fields=[
                'books_read', 'total_points', 'last_activity'
            ])
            self._check_badges()

    def _check_badges(self):
        """Provjeri je li dijete otključalo novi bedž."""
        child = self.child
        for badge_def in BadgeDefinition.objects.filter(is_active=True):
            if EarnedBadge.objects.filter(child=child, badge=badge_def).exists():
                continue
            if badge_def.tier and badge_def.tier != child.tier:
                continue
            earned = False
            if badge_def.required_genre and badge_def.required_books > 0:
                genre_count = ReadingLog.objects.filter(
                    child=child,
                    item__book_meta__genre=badge_def.required_genre
                ).count()
                if genre_count >= badge_def.required_books:
                    earned = True
            elif badge_def.required_books > 0 and not badge_def.required_genre:
                if child.books_read >= badge_def.required_books:
                    earned = True
            elif badge_def.required_streak > 0:
                if child.streak_days >= badge_def.required_streak:
                    earned = True
            if earned:
                EarnedBadge.objects.create(
                    child=child, badge=badge_def,
                    triggered_by_book=self.item
                )


class MediaContent(models.Model):
    """
    Multimedijski sadržaj — video/audio za portal.
    Knjižničarke snimaju, mi hostamo u sigurnoj zoni.
    """
    TYPE_CHOICES = [
        ('audio_story', _('Audio bajka')),
        ('video_read',  _('Video čitanje')),
        ('book_trailer', _('Book trailer')),
        ('workshop',    _('Radionica')),
        ('quiz',        _('Kviz')),
        ('debate',      _('Debata')),
    ]
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE)
    title = models.CharField(max_length=200, verbose_name=_('Naslov'))
    content_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    tier = models.CharField(max_length=15, choices=ChildReader.TIER_CHOICES, blank=True,
        help_text=_('Prazno = za sve'))
    description = models.TextField(blank=True)
    # File
    media_file = models.FileField(upload_to='knjiznica/media/%Y/%m/', blank=True)
    thumbnail = models.ImageField(upload_to='knjiznica/thumbs/', blank=True)
    duration_minutes = models.PositiveSmallIntegerField(default=0, verbose_name=_('Trajanje (min)'))
    # Linked book
    related_book = models.ForeignKey(
        'inventory.InventoryItem', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='media_contents'
    )
    # Meta
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True
    )
    view_count = models.PositiveIntegerField(default=0)
    objects = CompanyManager()

    class Meta:
        verbose_name = _('Medijski sadržaj')
        verbose_name_plural = _('Medijski sadržaji')
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_content_type_display()}: {self.title}'


class FamilyChallenge(models.Model):
    """
    Obiteljski izazov — roditelj + dijete čitaju zajedno.
    """
    TYPE_CHOICES = [
        ('read_together', _('Čitamo zajedno')),
        ('same_book', _('Ista knjiga')),
        ('weekend', _('Čitateljski vikend')),
        ('summer', _('Ljetni izazov')),
        ('monthly', _('Mjesečni maraton')),
    ]
    STATUS_CHOICES = [
        ('active', _('Aktivan')),
        ('completed', _('Završen')),
        ('expired', _('Istekao')),
    ]
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE)
    parent = models.ForeignKey(LibraryMember, on_delete=models.CASCADE, related_name='challenges')
    children = models.ManyToManyField(ChildReader, related_name='challenges', blank=True)
    challenge_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='active')
    title = models.CharField(max_length=200)
    target_books = models.PositiveSmallIntegerField(default=5,
        verbose_name=_('Cilj (knjiga)'))
    progress = models.PositiveSmallIntegerField(default=0,
        verbose_name=_('Napredak (knjiga)'))
    started_at = models.DateField(default=timezone.localdate)
    ends_at = models.DateField()
    completed_at = models.DateField(null=True, blank=True)
    objects = CompanyManager()

    class Meta:
        verbose_name = _('Obiteljski izazov')
        verbose_name_plural = _('Obiteljski izazovi')

    def __str__(self):
        return f'{self.title} ({self.parent.partner.name})'

    @property
    def progress_pct(self):
        if self.target_books == 0:
            return 100
        return min(100, int(self.progress / self.target_books * 100))
