from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from decimal import Decimal
from core.managers import CompanyManager
from borg_ops.mixins import FSMMixin


class BookMeta(models.Model):
    """
    Proširenje Inventory Item-a s knjižničnim podacima.
    Veza: 1:1 s inventory.Item
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

    class Meta:
        verbose_name = _('Podaci knjige')
        verbose_name_plural = _('Podaci knjiga')

    def __str__(self):
        return f'{self.item.name} — {self.author} ({self.isbn or "bez ISBN"})'


class LibraryMember(models.Model):
    """
    Član knjižnice — wrapper oko Partners.Partner.
    Svaka knjižnica ima svoje članove odvojene po company.
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
        """Izračunaj kaznu na temelju dana kašnjenja."""
        end = self.returned_date or timezone.localdate()
        if end > self.due_date:
            days = (end - self.due_date).days
            self.fine_total = Decimal(str(days)) * self.fine_per_day
        else:
            self.fine_total = Decimal('0.00')
        self.save(update_fields=['fine_total'])
        return self.fine_total

    def _on_transition(self, old_status, new_status, user=None):
        """Hook — WhatsApp obavijest na ključne tranzicije."""
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
                send_text(
                    phone=phone,
                    message=(
                        f'Podsjetnik knjiznice\n'
                        f'Knjiga "{self.item.name}" je trebala biti vracena {self.due_date}.\n'
                        f'Kazna: {self.fine_per_day} EUR/dan. Molimo vratite sto prije.'
                    )
                )
        except Exception:
            pass

    def _notify_fine(self):
        try:
            from core.whatsapp import send_text
            phone = self.member.partner.phone
            if phone:
                send_text(
                    phone=phone,
                    message=(
                        f'Knjiga vracena\n'
                        f'"{self.item.name}" vracena. Kazna za kasnjenje: {self.fine_total} EUR.\n'
                        f'Kaznu mozete platiti u knjiznici.'
                    )
                )
        except Exception:
            pass


class BookReservation(models.Model):
    """
    Rezervacija knjige dok je posuđena.
    """
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
