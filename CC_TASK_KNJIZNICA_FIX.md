# CC_TASK_KNJIZNICA_FIX.md
# Dodijeljen: CC Code
# Prioritet: VISOKO — bez ovog fix-a knjiznica se ne može demonstrirati
# Procjena: 2-3 sata
# Datum: 2026-03-29
# Autor: Sonnet (koordinacija)
#
# KONTEKST:
# Postoje DVA paralelna knjiznicna app-a:
#
#   knjiznica/  — MVP po CC_TASK_KNJIZNICA_MVP.md
#                 ima portal, gamifikaciju, FSM posudbe, NSK export
#                 DB tablice: sve kreirane, 10 BadgeDefinition seedanih, ostalo 0 redaka
#
#   library/    — naprednija verzija nastala paralelno
#                 ima ISBN auto-lookup, QR iskaznica, BookCopy fizicni primjerak
#                 DB seeded: 20 knjiga, 18 autora, 40 primjeraka, 8 kategorija
#
# TRI PROBLEMA:
#   P0: URL konflikt — oba na /knjiznica/, library wins (linija 75 < 83)
#   P1: Nema seed data u knjiznica app-u (nema cega pokazati na demo)
#   P1: knjiznica.daily_overdue_check nije u CELERY_BEAT_SCHEDULE
#
# VAZNO — provjereno na serveru:
#   - partners.Partner: nema first_name/last_name, samo 'name' CharField
#   - inventory.InventoryItem: nema item_type, ima 'category' s choices,
#     'sku' je required CharField (nije blank=True)
#   - knjiznica.LibraryMember FK: partners.Partner (ne auth.User)

---

## KORAK 1 — Fix URL konflikta

### 1a. Promijeni library admin URL u core/urls.py

Linija ~75:
```python
# STARO:
path('knjiznica/', include('library.urls', namespace='library')),
# NOVO:
path('lib/staff/', include('library.urls', namespace='library')),
```

Javni portal `lib/<slug>/` ostaje — ne dirati (linija ~59).

### 1b. Fix duplikat sidebar u templates/base.html (linije ~629-630)

```html
<!-- UKLONI (library, bez dijakritika): -->
{% if 'library' in sidebar_enabled_ids or request.user.is_superuser %}<a href="/knjiznica/" onclick="closeSidebar()"><i class="fas fa-book-reader"></i> <span>Knjiznica</span></a>{% endif %}

<!-- ZADRZI (knjiznica, s dijakriticima — jedini link): -->
{% if 'knjiznica' in sidebar_enabled_ids or request.user.is_superuser %}<a href="/knjiznica/" onclick="closeSidebar()"><i class="fas fa-book-reader"></i> <span>Knjižnica</span></a>{% endif %}
```

### 1c. Verifikacija

```bash
cd /var/www/fina-connect && venv/bin/python manage.py shell -c "
from django.urls import reverse
print('knjiznica dashboard:', reverse('knjiznica:dashboard'))
print('library dashboard:  ', reverse('library:dashboard'))
"
```

Ocekivano:
- knjiznica dashboard: /knjiznica/
- library dashboard:   /lib/staff/

---

## KORAK 2 — Celery Beat: daily_overdue_check

Dodati na kraj core/settings.py (u zadnji CELERY_BEAT_SCHEDULE.update() blok
ili novi):

```python
CELERY_BEAT_SCHEDULE.update({
    'knjiznica-daily-overdue': {
        'task': 'knjiznica.daily_overdue_check',
        'schedule': crontab(hour=8, minute=15),
    },
})
```

Provjeri je li crontab importiran: `grep "from celery.schedules" core/settings.py`

---

## KORAK 3 — Seed data za knjiznica app

Kreiraj management command. Tocna imena fielda (provjereno na serveru):
- `partners.Partner.name` (CharField, nema first_name/last_name)
- `inventory.InventoryItem.category` (CharField, choices='other','product',...)
- `inventory.InventoryItem.sku` (CharField, required — nije blank=True)

### 3a. Kreiraj direktorij i fajlove

```bash
mkdir -p /var/www/fina-connect/knjiznica/management/commands
touch /var/www/fina-connect/knjiznica/management/__init__.py
touch /var/www/fina-connect/knjiznica/management/commands/__init__.py
```

### 3b. Kreiraj seed command

`/var/www/fina-connect/knjiznica/management/commands/seed_knjiznica.py`:

```python
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal


KNJIGE = [
    {"name": "Priče iz davnine",      "author": "Ivana Brlić-Mažuranić", "isbn": "9789531162081", "shelf": "B-01-1", "genre": "bajka",       "age_tier": "explorer"},
    {"name": "Mali princ",            "author": "Antoine de Saint-Exupéry","isbn": "9789531060899","shelf": "B-01-2", "genre": "filozofija",   "age_tier": "navigator"},
    {"name": "Šegrt Hlapić",          "author": "Ivana Brlić-Mažuranić", "isbn": "9789531163347", "shelf": "B-01-3", "genre": "pustolovine",  "age_tier": "explorer"},
    {"name": "Hobbit",                "author": "J.R.R. Tolkien",          "isbn": "9789531062602", "shelf": "B-02-1", "genre": "fantazija",    "age_tier": "navigator"},
    {"name": "Kiklop",                "author": "Ranko Marinković",        "isbn": "9789531062619", "shelf": "A-03-1", "genre": "roman",        "age_tier": "adult"},
    {"name": "Na rubu pameti",        "author": "Miroslav Krleža",         "isbn": "9789531062626", "shelf": "A-03-2", "genre": "roman",        "age_tier": "adult"},
    {"name": "Python za početnike",   "author": "Eric Matthes",            "isbn": "9781593279288", "shelf": "C-01-1", "genre": "informatika",  "age_tier": "voyager"},
    {"name": "Dnevnik Bridget Jones", "author": "Helen Fielding",          "isbn": "9789531062640", "shelf": "B-03-1", "genre": "komedija",     "age_tier": "adult"},
    {"name": "Harry Potter i kamen mudraca", "author": "J.K. Rowling",    "isbn": "9789531062657", "shelf": "B-02-2", "genre": "fantazija",    "age_tier": "navigator"},
    {"name": "Enciklopedija Hrvatske","author": "Leksikografski zavod",    "isbn": "9789531055123", "shelf": "REF-01", "genre": "referentna",   "age_tier": "adult", "is_reference": True},
]

CLANOVI = [
    {"name": "Ana Kovač",     "member_number": "K-001"},
    {"name": "Marko Horvat",  "member_number": "K-002"},
    {"name": "Ivana Perić",   "member_number": "K-003"},
    {"name": "Tomislav Babić","member_number": "K-004"},
    {"name": "Petra Novak",   "member_number": "K-005"},
]


class Command(BaseCommand):
    help = 'Seed knjiznica app s demo podacima (knjige, clanovi, posudbe)'

    def add_arguments(self, parser):
        parser.add_argument('--company-id', type=int, default=None)
        parser.add_argument('--flush', action='store_true',
            help='Obrisi sve knjiznica podatke ove tvrtke prije seeda')

    def handle(self, *args, **options):
        from companies.models import Company
        from inventory.models import InventoryItem
        from partners.models import Partner
        from knjiznica.models import BookMeta, LibraryMember, BookLoan

        # Dohvati tvrtku
        if options['company_id']:
            company = Company.objects.get(pk=options['company_id'])
        else:
            company = Company.objects.filter(is_active=True).order_by('id').first()
        if not company:
            self.stderr.write('Nema aktivnih tvrtki.')
            return
        self.stdout.write(f'Tvrtka: {company.name} (id={company.id})')

        if options['flush']:
            BookLoan.objects.filter(company=company).delete()
            LibraryMember.objects.filter(company=company).delete()
            BookMeta.objects.filter(item__company=company).delete()
            self.stdout.write('  Flush: ocisceno.')

        # KNJIGE — InventoryItem + BookMeta
        knjige_items = []
        for i, k in enumerate(KNJIGE):
            # Provjeri postoji li vec
            existing = BookMeta.objects.filter(
                isbn=k['isbn'], item__company=company
            ).select_related('item').first()
            if existing:
                knjige_items.append(existing.item)
                continue

            # SKU je required — generiramo iz ISBN-a
            sku = f"LIB-{k['isbn'][-5:]}" if k.get('isbn') else f"LIB-{i+1:03d}"

            item, created = InventoryItem.objects.get_or_create(
                company=company,
                name=k['name'],
                defaults={
                    'sku': sku,
                    'category': 'other',
                    'unit': 'kom',
                }
            )
            BookMeta.objects.get_or_create(
                item=item,
                defaults={
                    'isbn': k.get('isbn', ''),
                    'author': k.get('author', ''),
                    'shelf_location': k.get('shelf', ''),
                    'genre': k.get('genre', ''),
                    'age_tier': k.get('age_tier', 'adult'),
                    'is_reference': k.get('is_reference', False),
                }
            )
            knjige_items.append(item)

        self.stdout.write(f'  Knjige: {len(knjige_items)} OK')

        # CLANOVI — Partner + LibraryMember
        clan_objects = []
        today = timezone.localdate()
        for c in CLANOVI:
            partner, _ = Partner.objects.get_or_create(
                company=company,
                name=c['name'],
                defaults={'partner_type': 'client'}
            )
            member, _ = LibraryMember.objects.get_or_create(
                company=company,
                member_number=c['member_number'],
                defaults={
                    'partner': partner,
                    'status': 'active',
                    'membership_from': today - timedelta(days=90),
                    'membership_until': today + timedelta(days=275),
                    'max_concurrent_loans': 3,
                }
            )
            clan_objects.append(member)

        self.stdout.write(f'  Clanovi: {len(clan_objects)} OK')

        # POSUDBE — 3 aktivne, 1 overdue (s kaznom), 1 vracena
        scenarios = [
            # (clan_idx, knjiga_idx, loan_offset, due_offset, status)
            (0, 0, -10,  5, 'borrowed'),  # Ana: Priče iz davnine, rok za 5 dana
            (1, 3,  -5, 10, 'borrowed'),  # Marko: Hobbit, rok za 10 dana
            (2, 6, -20, -7, 'overdue'),   # Ivana: Python, kasni 7 dana — kazna 3.50 EUR
            (3, 1, -30,-15, 'returned'),  # Tomislav: Mali princ, vratio
            (4, 4,  -3, 18, 'borrowed'),  # Petra: Kiklop, rok za 18 dana
        ]

        for clan_idx, knjiga_idx, loan_offset, due_offset, status in scenarios:
            if clan_idx >= len(clan_objects) or knjiga_idx >= len(knjige_items):
                continue
            member = clan_objects[clan_idx]
            item = knjige_items[knjiga_idx]

            # Skip referentna gradja
            try:
                if item.book_meta.is_reference:
                    continue
            except Exception:
                pass

            loan_date = today + timedelta(days=loan_offset)
            due_date  = today + timedelta(days=due_offset)

            defaults = {
                'status': status,
                'due_date': due_date,
                'fine_per_day': Decimal('0.50'),
                'fine_total': Decimal('0.00'),
            }
            if status == 'returned':
                defaults['returned_date'] = due_date + timedelta(days=2)
            if status == 'overdue':
                days_late = abs(due_offset)
                defaults['fine_total'] = Decimal('0.50') * days_late

            BookLoan.objects.get_or_create(
                company=company,
                member=member,
                item=item,
                loan_date=loan_date,
                defaults=defaults,
            )

        active   = BookLoan.objects.filter(company=company, status='borrowed').count()
        overdue  = BookLoan.objects.filter(company=company, status='overdue').count()
        returned = BookLoan.objects.filter(company=company, status='returned').count()
        self.stdout.write(f'  Posudbe: {active} aktivnih, {overdue} kasni, {returned} vracenih')
        self.stdout.write(self.style.SUCCESS('seed_knjiznica DONE — demo-ready'))
```

### 3c. Pokreni seed

```bash
cd /var/www/fina-connect
venv/bin/python manage.py seed_knjiznica
```

Za reset: `venv/bin/python manage.py seed_knjiznica --flush`

---

## KORAK 4 — Verifikacija

```bash
cd /var/www/fina-connect && venv/bin/python manage.py shell -c "
from knjiznica.models import BookMeta, LibraryMember, BookLoan

print('=== knjiznica status ===')
print(f'Knjige (BookMeta): {BookMeta.objects.count()}')
print(f'Clanovi: {LibraryMember.objects.count()}')
print(f'Aktivnih posudbi: {BookLoan.objects.filter(status=\"borrowed\").count()}')
print(f'Overdue: {BookLoan.objects.filter(status=\"overdue\").count()}')
print(f'Vracenih: {BookLoan.objects.filter(status=\"returned\").count()}')

# FSM provjera
loan = BookLoan.objects.filter(status='overdue').first()
if loan:
    print(f'Overdue loan: {loan.member} — {loan.item.name}')
    print(f'  Kazna: {loan.fine_total} EUR ({loan.days_overdue} dana)')

# can_borrow provjera
m = LibraryMember.objects.filter(status='active').first()
if m:
    ok, reason = m.can_borrow
    print(f'can_borrow ({m.partner.name}): {ok} — {reason}')

# URL provjera
from django.urls import reverse
print()
print('=== URL provjera ===')
print('knjiznica:dashboard  ->', reverse('knjiznica:dashboard'))
print('library:dashboard    ->', reverse('library:dashboard'))
print('knjiznica:nsk_export ->', reverse('knjiznica:nsk_export'))
"
```

Ocekivano:
- knjiznica:dashboard  -> /knjiznica/
- library:dashboard    -> /lib/staff/
- 9 BookMeta, 5 clanova, 3 aktivnih, 1 overdue (3.50 EUR), 1 vracena

---

## KORAK 5 — Restart i smoke test

```bash
sudo systemctl restart gunicorn

# Smoke test — ocekivano 302 (redirect na login)
curl -s -o /dev/null -w "knjiznica: %{http_code}\n" http://localhost:8000/knjiznica/
curl -s -o /dev/null -w "lib/staff: %{http_code}\n" http://localhost:8000/lib/staff/
curl -s -o /dev/null -w "lib/public: %{http_code}\n" http://localhost:8000/lib/test/
```

---

## COMMIT

```bash
git add core/urls.py core/settings.py templates/base.html \
        knjiznica/management/

git commit -m "fix(knjiznica): URL konflikt + Celery beat + seed data

FIXES:
- library admin premješten /knjiznica/ → /lib/staff/ (bio u konfliktu)
- sidebar: uklonjen duplikat link (library vs knjiznica)
- Celery: knjiznica.daily_overdue_check u CELERY_BEAT_SCHEDULE 08:15

ADD:
- seed_knjiznica management command
- 9 knjiga + BookMeta, 5 clanova, 5 posudbi (demo-ready)
- 1 overdue loan: Ivana Perić, Python za početnike, 3.50 EUR kazna

TARGET: Čepinska knjižnica demo — Marija Čačić"
```

---
# STATUS: READY_FOR_CC_CODE
# Blokira: demo za Čepin (Marija Čačić, ravnatelj)
# Rok: što prije — april 15 proximity
