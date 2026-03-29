# CC_TASK_KNJIZNICA_MVP.md
# Dodijeljen: CC Code
# Prioritet: VISOKO — konkretan kupac, ravnatelj poznat, demo ove sedmice
# Procjena: 5-7 dana
# Kontakt: Marija Čačić — Čepinska knjižnica / ravnatelj poznat Ivanu
# Ref: MASTER_PLAN_2026.md → H1 add-on segment
#
# FILOZOFIJA:
# Ne gradimo knjižnični softver koji se natječe sa ZAKI/CROLIST.
# Gradimo "Knjižnični modul za LIMIT Connect" — upravljanje,
# ne katalogizacija. Marija ne treba MARC21. Treba:
# 1. Tko je član, 2. Koja knjiga je gdje, 3. Tko što duguje.
#
# DEPLOYMENT: knjiznica.limit-connect.com (subdomena) ili
# integracija u glavni sustav kao nova app.

---

## ARHITEKTURA — što koristimo, što gradimo

### KORISTIMO (postoji, adaptiraj):
- `partners/` → Član knjižnice (Partner s book_member=True flag)
- `inventory/` → Katalog knjiga (Item s item_type='book')
- `pos/` → Naplata kazni i članarina
- `experiences/` → Događanja (čitaonice, radionice)
- `core/whatsapp.py` → Obavijesti članu (rok istječe, knjiga dostupna)
- `borg_ops/mixins.py` → FSM za status posudbe

### GRADIMO (novi app `knjiznica/`):
- `Posudba` model (tko, što, od-do, status)
- `Rezervacija` model (čeka da se knjiga vrati)
- `Kazna` model (izračun, naplata)
- Views + templates
- NSK statistika export (CSV format koji NSK prihvaća)

---

## KORAK 1 — Provjeri strukture koje koristimo

```bash
# Provjeri Partners model - što ima, što fali za člana knjižnice
grep -n "class Partner\|email\|phone\|address\|member" /var/www/fina-connect/partners/models.py | head -20

# Provjeri Inventory Item - što ima za knjige
grep -n "class Item\|isbn\|author\|title\|barcode\|item_type" /var/www/fina-connect/inventory/models.py | head -20
```

---

## KORAK 2 — Model: Knjiga (proširenje Inventory Item)

Ako `inventory.Item` nema ISBN/autor/naslov, dodati BookMeta model:

```python
# knjiznica/models.py

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
        'inventory.Item',
        on_delete=models.CASCADE,
        related_name='book_meta',
        verbose_name=_('Artikl')
    )
    isbn = models.CharField(max_length=20, blank=True, verbose_name='ISBN')
    author = models.CharField(max_length=300, blank=True, verbose_name=_('Autor'))
    publisher = models.CharField(max_length=200, blank=True, verbose_name=_('Nakladnik'))
    pub_year = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name=_('Godina'))
    shelf_location = models.CharField(max_length=50, blank=True,
        verbose_name=_('Polica'),
        help_text=_('npr. A-02-3 (ormar A, polica 2, pozicija 3)'))
    is_reference = models.BooleanField(default=False,
        verbose_name=_('Referentna građa'),
        help_text=_('Ako True, knjiga se ne posuđuje (enciklopedije, rječnici)'))
    copy_number = models.PositiveSmallIntegerField(default=1,
        verbose_name=_('Primjerak br.'))

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
    max_concurrent_loans = models.PositiveSmallIntegerField(default=3,
        verbose_name=_('Max istovremenih posudbi'))
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
        if self.status != 'active':
            return False, f'Status: {self.get_status_display()}'
        if self.total_fines_outstanding > 0:
            return False, f'Duguje {self.total_fines_outstanding}€ kazni'
        active_loans = self.loans.filter(status='borrowed').count()
        if active_loans >= self.max_concurrent_loans:
            return False, f'Dostignut limit ({self.max_concurrent_loans} posudbi)'
        if self.membership_until < timezone.localdate():
            return False, 'Iskaznica istekla'
        return True, 'OK'


class BookLoan(FSMMixin, models.Model):
    """
    Posudba knjige.
    FSM: reserved → borrowed → returned | overdue → returned
    """
    TRANSITIONS = {
        'reserved': ['borrowed', 'cancelled'],
        'borrowed': ['returned', 'overdue'],
        'overdue':  ['returned'],
        'returned': [],    # terminal
        'cancelled': [],   # terminal
    }
    STATUS_CHOICES = [
        ('reserved', _('Rezervirano')),
        ('borrowed', _('Posuđeno')),
        ('overdue',  _('Kasni')),
        ('returned', _('Vraćeno')),
        ('cancelled', _('Otkazano')),
    ]

    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE)
    member = models.ForeignKey(LibraryMember, on_delete=models.CASCADE,
        related_name='loans', verbose_name=_('Član'))
    item = models.ForeignKey('inventory.Item', on_delete=models.CASCADE,
        related_name='loans', verbose_name=_('Knjiga'))
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='borrowed')

    loan_date = models.DateField(default=timezone.localdate, verbose_name=_('Datum posudbe'))
    due_date = models.DateField(verbose_name=_('Rok povratka'))
    returned_date = models.DateField(null=True, blank=True, verbose_name=_('Vraćeno'))

    # Kazna
    fine_per_day = models.DecimalField(max_digits=5, decimal_places=2,
        default=Decimal('0.50'), verbose_name=_('Kazna/dan (€)'))
    fine_total = models.DecimalField(max_digits=8, decimal_places=2,
        default=0, verbose_name=_('Ukupna kazna'))
    fine_paid = models.BooleanField(default=False)

    librarian = models.ForeignKey('auth.User', on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name=_('Knjižničar'))
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
        days = self.days_overdue
        if days > 0:
            self.fine_total = Decimal(str(days)) * self.fine_per_day
            self.save(update_fields=['fine_total'])
        return self.fine_total

    def _on_transition(self, old_status, new_status, user=None):
        """Hook — WhatsApp obavijest na ključne tranzicije."""
        if new_status == 'overdue':
            self._notify_overdue()
        elif new_status == 'returned':
            self.returned_date = timezone.localdate()
            self.calculate_fine()
            self.save(update_fields=['returned_date'])
            if self.fine_total > 0:
                self._notify_fine()

    def _notify_overdue(self):
        try:
            from core.whatsapp import send_text
            phone = getattr(self.member.partner, 'mobile', None)
            if phone:
                send_text(
                    phone=phone,
                    message=(
                        f'📚 Podsjetnik knjižnice\n'
                        f'Knjiga "{self.item.name}" je trebala biti vraćena {self.due_date}.\n'
                        f'Kazna: {self.fine_per_day}€/dan. Molimo vratite što prije.'
                    )
                )
        except Exception:
            pass

    def _notify_fine(self):
        try:
            from core.whatsapp import send_text
            phone = getattr(self.member.partner, 'mobile', None)
            if phone:
                send_text(
                    phone=phone,
                    message=(
                        f'📚 Knjiga vraćena\n'
                        f'"{self.item.name}" vraćena. Kazna za kašnjenje: {self.fine_total}€.\n'
                        f'Kaznu možete platiti u knjižnici.'
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
    member = models.ForeignKey(LibraryMember, on_delete=models.CASCADE,
        related_name='reservations')
    item = models.ForeignKey('inventory.Item', on_delete=models.CASCADE,
        related_name='reservations')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='waiting')
    reserved_at = models.DateTimeField(auto_now_add=True)
    notified_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateField(null=True, blank=True,
        help_text=_('Rezervacija istječe ako se ne preuzme do ovog datuma'))
    objects = CompanyManager()

    class Meta:
        verbose_name = _('Rezervacija')
        verbose_name_plural = _('Rezervacije')
        ordering = ['reserved_at']

    def __str__(self):
        return f'{self.member} čeka: {self.item.name}'
```

---

## KORAK 3 — Settings, URLs, Migracije

```python
# core/settings.py — u INSTALLED_APPS:
'knjiznica',

# knjiznica/urls.py
from django.urls import path
from . import views

app_name = 'knjiznica'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),

    # Katalog
    path('katalog/', views.catalog_list, name='catalog_list'),
    path('katalog/<int:pk>/', views.catalog_detail, name='catalog_detail'),
    path('katalog/nova-knjiga/', views.catalog_create, name='catalog_create'),

    # Članovi
    path('clanovi/', views.member_list, name='member_list'),
    path('clanovi/novi/', views.member_create, name='member_create'),
    path('clanovi/<int:pk>/', views.member_detail, name='member_detail'),

    # Posudba
    path('posudba/nova/', views.loan_create, name='loan_create'),
    path('posudba/<int:pk>/vrati/', views.loan_return, name='loan_return'),
    path('posudba/<int:pk>/kazna/', views.loan_fine, name='loan_fine'),

    # Statistika
    path('statistika/', views.statistics, name='statistics'),
    path('statistika/nsk-export/', views.nsk_export, name='nsk_export'),
]

# core/urls.py — dodati:
path('knjiznica/', include('knjiznica.urls', namespace='knjiznica')),
```

```bash
cd /var/www/fina-connect
/var/www/fina-connect/venv/bin/python manage.py makemigrations knjiznica
/var/www/fina-connect/venv/bin/python manage.py migrate
```

---

## KORAK 4 — Views (minimum za demo)

```python
# knjiznica/views.py

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.contrib import messages
from django.http import HttpResponse
import csv

from core.company_utils import get_user_company
from .models import BookLoan, LibraryMember, BookReservation


@login_required
def dashboard(request):
    company = get_user_company(request)
    today = timezone.localdate()

    overdue = BookLoan.objects.filter(
        company=company, status='borrowed',
        due_date__lt=today
    ).select_related('member__partner', 'item')

    # Auto-tranzicija kasnih posudbi u overdue
    for loan in overdue:
        if loan.status == 'borrowed':
            loan.transition_to('overdue', user=request.user)

    stats = {
        'active_members': LibraryMember.objects.filter(
            company=company, status='active').count(),
        'books_borrowed': BookLoan.objects.filter(
            company=company, status='borrowed').count(),
        'overdue_count': BookLoan.objects.filter(
            company=company, status='overdue').count(),
        'waiting_reservations': BookReservation.objects.filter(
            company=company, status='waiting').count(),
    }

    recent_loans = BookLoan.objects.filter(
        company=company
    ).select_related('member__partner', 'item').order_by('-loan_date')[:10]

    return render(request, 'knjiznica/dashboard.html', {
        'stats': stats,
        'recent_loans': recent_loans,
        'overdue_loans': overdue,
    })


@login_required
def loan_create(request):
    """Nova posudba — skeniranje iskaznice + knjige."""
    company = get_user_company(request)

    if request.method == 'POST':
        member_id = request.POST.get('member_id')
        item_id = request.POST.get('item_id')
        due_days = int(request.POST.get('due_days', 15))

        member = get_object_or_404(LibraryMember, pk=member_id, company=company)
        from inventory.models import Item
        item = get_object_or_404(Item, pk=item_id, company=company)

        can_borrow, reason = member.can_borrow
        if not can_borrow:
            messages.error(request, f'Ne može posuditi: {reason}')
            return redirect('knjiznica:dashboard')

        # Provjeri dostupnost
        active_loan = BookLoan.objects.filter(
            item=item, company=company,
            status__in=['borrowed', 'overdue']
        ).first()

        if active_loan:
            messages.error(request,
                f'Knjiga je posuđena do {active_loan.due_date}.')
            return redirect('knjiznica:dashboard')

        due_date = timezone.localdate() + timezone.timedelta(days=due_days)
        loan = BookLoan.objects.create(
            company=company,
            member=member,
            item=item,
            due_date=due_date,
            status='borrowed',
            librarian=request.user,
        )
        messages.success(request,
            f'Posudba OK: {item.name} → {member.partner.name}, rok {due_date}')
        return redirect('knjiznica:dashboard')

    # GET — forma
    members = LibraryMember.objects.filter(
        company=company, status='active'
    ).select_related('partner').order_by('partner__name')

    from inventory.models import Item
    available_books = Item.objects.filter(company=company)

    return render(request, 'knjiznica/loan_form.html', {
        'members': members,
        'books': available_books,
    })


@login_required
def loan_return(request, pk):
    """Povrat knjige."""
    company = get_user_company(request)
    loan = get_object_or_404(BookLoan, pk=pk, company=company)

    if loan.status not in ('borrowed', 'overdue'):
        messages.error(request, 'Ova posudba nije aktivna.')
        return redirect('knjiznica:dashboard')

    if request.method == 'POST':
        loan.transition_to('returned', user=request.user)
        if loan.fine_total > 0:
            messages.warning(request,
                f'Knjiga vraćena s kaznama: {loan.fine_total}€')
        else:
            messages.success(request, 'Knjiga vraćena. Nema kazni.')

        # Provjeri čeka li netko rezervaciju
        reservation = BookReservation.objects.filter(
            item=loan.item, company=company, status='waiting'
        ).order_by('reserved_at').first()
        if reservation:
            reservation.status = 'notified'
            reservation.notified_at = timezone.now()
            reservation.expires_at = timezone.localdate() + timezone.timedelta(days=3)
            reservation.save()
            try:
                from core.whatsapp import send_text
                phone = getattr(reservation.member.partner, 'mobile', None)
                if phone:
                    send_text(phone=phone, message=(
                        f'📚 Vaša rezervacija\n'
                        f'Knjiga "{loan.item.name}" je dostupna!\n'
                        f'Preuzeti do: {reservation.expires_at}'
                    ))
            except Exception:
                pass
            messages.info(request,
                f'Obaviješten je {reservation.member.partner.name} — čekao ovu knjigu.')

        return redirect('knjiznica:dashboard')

    return render(request, 'knjiznica/loan_return_confirm.html', {'loan': loan})


@login_required
def nsk_export(request):
    """
    NSK statistički export — godišnji CSV.
    Format: NSK Matična knjižnica standard (prilagoditi ako NSK traži Excel).
    """
    company = get_user_company(request)
    year = int(request.GET.get('year', timezone.localdate().year))

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="nsk_statistika_{year}.csv"'
    response.write('\ufeff')  # BOM za Excel

    writer = csv.writer(response, delimiter=';')
    writer.writerow([
        'Knjižnica', 'OIB', 'Godina',
        'Broj članova', 'Broj posudbi', 'Broj vraćenih',
        'Knjiga s kaznama', 'Ukupne kazne (EUR)',
        'Broj aktivnih naslova',
    ])

    from inventory.models import Item
    loans = BookLoan.objects.filter(
        company=company, loan_date__year=year
    )

    writer.writerow([
        company.name,
        company.oib or '',
        year,
        LibraryMember.objects.filter(company=company, status='active').count(),
        loans.filter(status__in=['borrowed', 'overdue', 'returned']).count(),
        loans.filter(status='returned').count(),
        loans.filter(fine_total__gt=0).count(),
        sum(l.fine_total for l in loans if l.fine_total),
        Item.objects.filter(company=company).count(),
    ])

    return response
```

---

## KORAK 5 — Templates (minimum za demo)

Kreirati direktorij: `templates/knjiznica/`

**5 templates:**
1. `dashboard.html` — statistike (stat_card partials) + overdue lista + recent posudbe
2. `loan_form.html` — forma: odaberi člana + knjigu + rok (15/30 dana)
3. `loan_return_confirm.html` — potvrda povratka + prikaz kazne
4. `catalog_list.html` — lista knjiga s dostupnošću (zeleno/crveno)
5. `member_list.html` — lista članova s brojem aktivnih posudbi

**Sve koriste `{% include "partials/_stat_card.html" %}` i `{% include "partials/_page_header.html" %}`**

---

## KORAK 6 — Celery task: dnevni overdue check

```python
# knjiznica/tasks.py

from celery import shared_task

@shared_task(name='knjiznica.daily_overdue_check')
def daily_overdue_check():
    """
    Svaki dan u 08:00 — provjeri prekoračene rokove i pošalji podsjetnik.
    """
    from django.utils import timezone
    from .models import BookLoan

    today = timezone.localdate()
    overdue = BookLoan.objects.filter(
        status='borrowed', due_date__lt=today
    ).select_related('member__partner', 'item')

    count = 0
    for loan in overdue:
        loan.transition_to('overdue')
        count += 1

    return {'transitioned_to_overdue': count}
```

Dodati u `core/settings.py` CELERY_BEAT_SCHEDULE:
```python
'knjiznica-daily-overdue': {
    'task': 'knjiznica.daily_overdue_check',
    'schedule': crontab(hour=8, minute=0),
},
```

---

## KORAK 7 — Sidebar link

```bash
grep -n "udruge\|DVD\|golubar" /var/www/fina-connect/templates/base.html | head -5
```

Dodati u odgovarajuću sidebar sekciju:
```html
<a href="{% url 'knjiznica:dashboard' %}"
   class="{% if 'knjiznica' in request.path %}active{% endif %}">
  <i class="fas fa-book"></i> Knjižnica
</a>
```

---

## VERIFIKACIJA

```bash
cd /var/www/fina-connect && /var/www/fina-connect/venv/bin/python manage.py shell -c "
from knjiznica.models import BookLoan, LibraryMember, BookReservation, BookMeta
print('Models OK')
from django.urls import reverse
print('Dashboard URL:', reverse('knjiznica:dashboard'))
print('Loan create URL:', reverse('knjiznica:loan_create'))
print('NSK export URL:', reverse('knjiznica:nsk_export'))
"

# Simulate borg - dodati knjiznica modul
/var/www/fina-connect/venv/bin/python manage.py simulate_borg --modules knjiznica 2>&1 | tail -10
```

## COMMIT

```bash
git add knjiznica/ templates/knjiznica/ core/settings.py core/urls.py
git commit -m "feat(knjiznica): Library MVP — posudba, članovi, kazne, NSK export, WhatsApp podsjetnik

4 modela: BookMeta, LibraryMember, BookLoan (FSM), BookReservation
FSM tranzicije: reserved→borrowed→overdue→returned
Celery daily check: auto-overdue + WhatsApp obavijest
NSK statistika export (CSV, BOM za Excel)
Pilot: Čepinska knjižnica — Marija Čačić / Ravnatelj

Tržište: 312 narodnih knjižnica u HR, od 9,99€/mj"
```

---

## DEMO SCENARIJ za Mariju (10 minuta)

1. Otvoriti dashboard → statistike (X članova, Y posudbi, Z kasni)
2. "Dodajmo novu posudbu" → odaberi člana + knjigu → potvrdi
3. Prikazati rok povratka, WhatsApp potvrdu
4. "Ova knjiga kasni" → klik Vrati → prikaz kazne
5. "Pogledajmo NSK statistiku" → klik Export → CSV se preuzima
6. "Ovo je na telefonu, tabletu, laptopu — bez instalacije"

**Ključna rečenica za ravnatelja:**
*"Vaša knjižnica na Starter planu je 22€ godišnje od JLS-a.
To je manje od jednog dana manualnog upisa korisnika."*

---
# STATUS: READY_FOR_CC_CODE
# Rok demo: ove sedmice
# Tržište: 312 narodnih knjižnica × 22-100€/mj
