CC TASK: UDRUGE + KONTO SIMBIOZA — DVOJNO KNJIGOVODSTVO
Datum: 04.04.2026. | Rok: 12.04.2026.
Prioritet: VISOK — zatvara rupe PR-RAS-NPF → Bilanca → JournalEntry

PRAVILO: READ svaki fajl PRIJE pisanja. Nikad ne pretpostavljaj field name.
PRAVILO: base.html, .env NE DIRAS. core/urls.py samo append.
PRAVILO: CompanyManager() na svaki novi model s company FK.
PRAVILO: JournalEntry.clean() provjerava period lock — hvati ValidationError.
PRAVILO: Nakon svake migracije: venv/bin/python manage.py check 2>&1 | tail -3

---

KORAK 1: Provjeri teren

EXEC: grep -n "uses_double_entry\|double_entry" /var/www/fina-connect/companies/models.py | head -5
EXEC: grep -n "SOURCE_TYPES\|membership\|donation" /var/www/fina-connect/konto/models.py | head -10
EXEC: cat /var/www/fina-connect/konto/nonprofit_setup.py | grep -n "def \|111\|112\|321\|322\|35"  | head -20
EXEC: grep -n "def setup_nonprofit\|def " /var/www/fina-connect/konto/nonprofit_setup.py | head -10
EXEC: grep -n "booking_engine\|auto_book\|auto_knjizi" /var/www/fina-connect/konto/booking_engine.py | head -15
EXEC: grep -n "def " /var/www/fina-connect/konto/booking_engine.py | head -20

Zapamti: postoje li konta 111, 112, 321, 332, 352 u nonprofit_setup.py?

---

KORAK 2: uses_double_entry na Company modelu

READ: /var/www/fina-connect/companies/models.py (grep za is_shelter, is_umbrella — naci poziciju za insert)

U Company modelu, ODMAH ISPOD is_shelter boolean polja, dodaj:

    uses_double_entry = models.BooleanField(
        default=False,
        verbose_name='Dvojno knjigovodstvo',
        help_text='Ako True: Clanarina i Donacija automatski kreiraju JournalEntry. '
                  'Obvezno za udruge s prihodima > 30.000 EUR (Uredba o racunovodstvu neprofitnih organizacija).'
    )

EXEC: cd /var/www/fina-connect && venv/bin/python manage.py makemigrations companies --name uses_double_entry
EXEC: venv/bin/python manage.py migrate companies
EXEC: venv/bin/python manage.py check 2>&1 | tail -3

---

KORAK 3: SOURCE_TYPES nadopuna u JournalEntry

READ: /var/www/fina-connect/konto/models.py (klasa JournalEntry, SOURCE_TYPES lista, cca linija 195)

U SOURCE_TYPES listi dodaj dva nova tipa (APPEND na listu, ne zamjena):
    ('membership', 'Clanarina'),
    ('donation',   'Donacija'),

NAPOMENA: Ovo je samo choices lista, ne treba migracija za CharField promjenu choices.
Ali ako je CharField max_length premali — provjeri i povecaj ako treba.
EXEC: grep -n "source_type.*CharField\|max_length" /var/www/fina-connect/konto/models.py | grep -i source | head -3

---

KORAK 4: auto_knjizi_clanarina funkcija

READ: /var/www/fina-connect/konto/booking_engine.py (CIJELI — provjeri importse i postojece funkcije)
READ: /var/www/fina-connect/konto/nonprofit_setup.py (provjeri tocne sifre konta)

Dodaj novu funkciju na kraj konto/booking_engine.py:

def auto_knjizi_clanarina(clanarina):
    Automatski kreira JournalEntry za placenu clanarine.
    Poziva se iz Clanarina.mark_paid() ako company.uses_double_entry == True.
    Siguran: hvata sve greske, ne baci iznimku gore.

    Kontni plan (nonprofit):
      Primitak gotovinom: D 112 (Blagajna) / C 321 (Prihodi od clanarina)
      Primitak virmanom/online/pos: D 111 (Ziro racun) / C 321 (Prihodi od clanarina)

    Logika:
    1. Provjeri clanarina.company.uses_double_entry. Ako False: return None.
    2. Provjeri je li clanarina.status == 'placena'. Ako nije: return None.
    3. Provjeri ne postoji li vec JournalEntry za ovu clanarinu:
       JournalEntry.objects.filter(company=company, description__contains=f'CL-{clanarina.pk}').exists()
       Ako postoji: return None (idempotentnost).
    4. Odredi debitni konto prema payment_method:
       gotovina → KontoAccount.objects.filter(company=company, code='112').first()
       ostalo   → KontoAccount.objects.filter(company=company, code='111').first()
    5. Odredi kreditni konto: KontoAccount.objects.filter(company=company, code='321').first()
    6. Ako bilo koji konto ne postoji: pokusaj setup_nonprofit_accounts(company) i ponovi.
       Ako opet ne postoji: logger.warning i return None.
    7. Generiraj entry_number: f'CL-{clanarina.pk}-{datetime.date.today().strftime("%Y%m%d")}'
    8. Kreiraj JournalEntry:
       entry = JournalEntry.objects.create(
           company=company,
           entry_number=entry_number,
           date=clanarina.paid_at.date() if clanarina.paid_at else datetime.date.today(),
           description=f'Clanarina: {clanarina.clan} ({clanarina.period_start} - {clanarina.period_end})',
           source_type='membership',
           is_posted=True,
       )
    9. Kreiraj 2 LedgerLine:
       LedgerLine.objects.create(entry=entry, account=debit_account, side='debit', amount=clanarina.amount, description='Uplata clanarine')
       LedgerLine.objects.create(entry=entry, account=credit_account, side='credit', amount=clanarina.amount, description='Prihod od clanarine')
    10. return entry

    Sve unutar try/except Exception as e: logger.error('auto_knjizi_clanarina: %s', e); return None

NAPOMENA: Provjeri tocne importse — datetime, Decimal, logger postoje li u booking_engine.py.
Provjeri postoji li LedgerLine u importima; ako ne, uvezi iz konto.models.

---

KORAK 5: auto_knjizi_donacija funkcija

Dodaj na kraj konto/booking_engine.py (ODMAH ISPOD auto_knjizi_clanarina):

def auto_knjizi_donacija(donacija):
    Automatski kreira JournalEntry za donaciju.
    Poziva se iz donacija_create view ako company.uses_double_entry == True.

    Kontni plan (nonprofit):
      Novacana donacija pravne osobe: D 111 / C 352 (Prihodi od donacija pravnih)
      Novacana donacija fizicke osobe: D 111 / C 351 (Prihodi od donacija fizickih)
      Materijalna donacija:           D 022 (Oprema) / C 352
      Anonimna:                       D 111 / C 352

    Logika (ista struktura kao auto_knjizi_clanarina):
    1. Provjeri company.uses_double_entry. Ako False: return None.
    2. Idempotentnost: provjeri postoji li JournalEntry s f'DON-{donacija.pk}'.
    3. Debitni konto:
       is_material=True → KontoAccount code='022' (Postrojenja i oprema, fallback '04')
       ostalo          → KontoAccount code='111'
    4. Kreditni konto:
       donor_type='fizicka' → code='351'
       ostalo              → code='352'
    5. Iznos: donacija.amount ako novacana, donacija.material_fair_value ako materijalna
    6. entry_number: f'DON-{donacija.pk}-{datum}'
    7. description: f'Donacija: {donacija.donor_name} — {donacija.purpose or "Opca donacija"}'
    8. source_type='donation', is_posted=True
    9. Kreiraj 2 LedgerLine (isti pattern kao gore)
    10. return entry

    Sve u try/except — nikad ne baci gore.

---

KORAK 6: Infuzija u Clanarina.mark_paid()

READ: /var/www/fina-connect/udruge/models.py (metoda mark_paid klase Clanarina, cca linija 200-210)

Modificiraj mark_paid metodu:

    def mark_paid(self, method='gotovina'):
        self.status = 'placena'
        self.paid_at = timezone.now()
        self.payment_method = method
        self.save(update_fields=['status', 'paid_at', 'payment_method', 'updated_at'])
        # Auto dvojno knjizenje (samo ako uses_double_entry == True)
        try:
            from konto.booking_engine import auto_knjizi_clanarina
            auto_knjizi_clanarina(self)
        except Exception as _e:
            import logging
            logging.getLogger('udruge').warning('mark_paid auto_knjizi: %s', _e)

---

KORAK 7: Infuzija u donacija_create view

READ: /var/www/fina-connect/udruge/views.py (funkcija donacija_create, linije ~343-405)

Pronađi: donacija = Donacija.objects.create(...)
ODMAH NAKON te linije, dodaj:

    try:
        from konto.booking_engine import auto_knjizi_donacija
        auto_knjizi_donacija(donacija)
    except Exception as _e:
        import logging
        logging.getLogger('udruge').warning('donacija_create auto_knjizi: %s', _e)

---

KORAK 8: KnjigaPrimitaka → ArhivaEntry signal

READ: /var/www/fina-connect/udruge/models.py (klasa KnjigaPrimitaka __str__ i polja)
Provjeri postoji li /var/www/fina-connect/udruge/signals.py.
Ako ne postoji: kreiraj ga.

WRITE: /var/www/fina-connect/udruge/signals.py

Sadrzaj:

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger('udruge')

@receiver(post_save, sender='udruge.KnjigaPrimitaka')
def archive_knjiga_primitaka(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        from documents.models import ArhivaEntry
        source_type = 'document'
        source_id = str(instance.pk)
        exists = ArhivaEntry.objects.unscoped().filter(
            source_type=source_type, source_id=source_id
        ).exists()
        if exists:
            return
        ArhivaEntry.objects.create(
            company=instance.company,
            source_type=source_type,
            source_id=source_id,
            doc_number=f'KP-{instance.redni_broj}',
            partner_name=instance.opis[:100],
            amount=instance.iznos,
            currency='EUR',
            doc_date=instance.datum,
            archived_by=None,
            ai_summary=f'Knjiga primitaka #{instance.redni_broj}: {instance.get_vrsta_display()} — {instance.get_izvor_display()}',
        )
        logger.debug('ArhivaEntry kreiran za KnjigaPrimitaka #%s', instance.pk)
    except Exception as e:
        logger.error('archive_knjiga_primitaka signal: %s', e)

@receiver(post_save, sender='udruge.Donacija')
def archive_donacija(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        from documents.models import ArhivaEntry
        exists = ArhivaEntry.objects.unscoped().filter(
            source_type='document', source_id=f'don-{instance.pk}'
        ).exists()
        if exists:
            return
        ArhivaEntry.objects.create(
            company=instance.company,
            source_type='document',
            source_id=f'don-{instance.pk}',
            doc_number=instance.potvrda_number or f'DON-{instance.pk}',
            partner_name=instance.donor_name,
            amount=instance.amount,
            currency='EUR',
            doc_date=instance.date,
            ai_summary=f'Donacija: {instance.donor_name} {instance.amount} EUR',
        )
    except Exception as e:
        logger.error('archive_donacija signal: %s', e)

---

KORAK 9: Registriraj signals u udruge/apps.py

READ: /var/www/fina-connect/udruge/apps.py

U ready() metodi UdrugeConfig klase, dodaj:
    def ready(self):
        import udruge.signals  # noqa

Ako ready() vec postoji: samo dodaj import liniju unutra.
Ako UdrugeConfig nema ready(): dodaj ga.

---

KORAK 10: Company settings UI — uses_double_entry checkbox

READ: /var/www/fina-connect/udruge/views.py (pronađi funkciju koja upravlja podesavanjima udruge)
EXEC: grep -n "def.*setting\|def.*config\|def.*admin\|def.*postavk" /var/www/fina-connect/udruge/views.py | head -10

Pronađi view za udruge settings (vjerojatno company_settings ili udruge_settings).
Ako ne postoji, provjeri:
EXEC: grep -rn "uses_double_entry\|dvojno" /var/www/fina-connect/templates/ | head -5

Dodaj uses_double_entry checkbox u relevantan template.
Ako nema dedicated settings templatea za udruge:
READ: /var/www/fina-connect/templates/udruge/ (ls)
Dodaj u najprikladniji postojeci template (npr. fina_reports.html ili dashboard).

HTML element za dodati:
U formi koja sprema company settings:
  label: Dvojno knjigovodstvo
  input type=checkbox name=uses_double_entry value=1
  checked ako company.uses_double_entry
  help text: Aktiviraj za udruge s prihodima > 30.000 EUR

Endpoint koji prima POST i sprema:
  company.uses_double_entry = bool(request.POST.get('uses_double_entry'))
  company.save(update_fields=['uses_double_entry'])

---

KORAK 11: TaxPeriod deadline WhatsApp notifikacija

READ: /var/www/fina-connect/konto/tasks.py (grep za def, shared_task)
READ: /var/www/fina-connect/konto/tasks_vat.py (grep za def)

Dodaj novi Celery task na kraj konto/tasks.py (ili tasks_vat.py, ovisno gdje su slicni taskovi):

@shared_task(name='konto.tax_deadline_notifier')
def tax_deadline_notifier():
    Upozorenje Mariji za rokove poreznih prijava.
    Okida se jednom dnevno u 08:00.
    Salje WhatsApp ako rok istice za 3 dana ili je danas.

    import os
    from django.utils import timezone
    from konto.models import TaxPeriod

    marija = os.environ.get('MARIJA_WHATSAPP', '')
    if not marija:
        return

    today = timezone.now().date()
    alert_dates = [today, today + timezone.timedelta(days=1),
                   today + timezone.timedelta(days=3)]

    periods = (TaxPeriod.objects.unscoped()
               .filter(filing_deadline__in=alert_dates, is_filed=False)
               .select_related('company')
               .order_by('filing_deadline'))

    if not periods.exists():
        return

    lines = ['POREZNI ROKOVI:']
    for p in periods:
        days_left = (p.filing_deadline - today).days
        if days_left == 0:
            urgency = 'DANAS'
        elif days_left == 1:
            urgency = 'SUTRA'
        else:
            urgency = f'za {days_left} dana'
        lines.append(
            f'{urgency}: {p.company.name} — {p.period_label} '
            f'({p.vat_payable:.0f} EUR PDV)'
        )
    lines.append('limit-connect.com/konto/porez/')

    try:
        from core.whatsapp import send_whatsapp
        send_whatsapp(marija, '\n'.join(lines))
    except Exception as e:
        import logging
        logging.getLogger('konto').warning('tax_deadline_notifier WA: %s', e)

Registriraj u CELERY_BEAT_SCHEDULE (core/settings.py ili core/celery.py):
    'tax-deadline-notifier': {
        'task': 'konto.tax_deadline_notifier',
        'schedule': 86400,
    },

NAPOMENA: 86400 sekundi = jednom dnevno. Pokreni u 08:00 ako koristis crontab.
Ako koristis samo schedule (sekunde): 86400 radi ali ne garantira tocno 08:00.

---

KORAK 12: Udruge KPI widget

READ: /var/www/fina-connect/udruge/views.py (prva dostupna dashboard funkcija)
EXEC: grep -n "def.*dashboard\|def.*pregled\|def.*index" /var/www/fina-connect/udruge/views.py | head -5

Pronađi dashboard view za udruge.
Dodaj u context:

    from django.db.models import Sum, Count
    from django.utils import timezone
    today = timezone.now().date()
    month_start = today.replace(day=1)
    year_start = today.replace(month=1, day=1)

    # KPI 1: Aktivni clanovi
    aktivni_clanovi = Clan.objects.filter(company=company, status='aktivan').count()

    # KPI 2: MRR od clanarina (ovaj mjesec)
    mrr_clanarina = (Clanarina.objects
                     .filter(company=company, status='placena',
                             paid_at__date__gte=month_start)
                     .aggregate(s=Sum('amount'))['s'] or 0)

    # KPI 3: Donacije YTD
    donacije_ytd = (Donacija.objects
                    .filter(company=company, date__gte=year_start)
                    .aggregate(s=Sum('amount'), n=Count('id')))

    # KPI 4: Dospjele clanarine
    dospjele_clanarine = Clanarina.objects.filter(
        company=company, status__in=['ceka', 'kasni'],
        period_end__lt=today
    ).count()

    # KPI 5: Proknjizano vs neproknjizano (samo ako uses_double_entry)
    neproknjizano_eur = 0
    if getattr(company, 'uses_double_entry', False):
        from konto.models import JournalEntry
        proknjizane_clanarine = set(
            JournalEntry.objects.filter(company=company, source_type='membership')
            .values_list('description', flat=True)
        )
        ukupne_placene = Clanarina.objects.filter(company=company, status='placena')
        neproknjizano_eur = (ukupne_placene
                             .exclude(pk__in=[
                                 int(d.split('-')[1]) for d in proknjizane_clanarine
                                 if d.startswith('Clanarina:') or 'CL-' in d
                             ])
                             .aggregate(s=Sum('amount'))['s'] or 0)

    context['kpi'] = {
        'aktivni_clanovi': aktivni_clanovi,
        'mrr_clanarina': mrr_clanarina,
        'donacije_ytd_eur': donacije_ytd['s'] or 0,
        'donacije_ytd_n': donacije_ytd['n'] or 0,
        'dospjele_clanarine': dospjele_clanarine,
        'neproknjizano_eur': neproknjizano_eur,
        'uses_double_entry': getattr(company, 'uses_double_entry', False),
    }

U dashboard template (ili HTML na vrhu stranice), dodaj 4-5 KPI kartica:
  Zlatna: aktivni_clanovi "Aktivnih članova"
  Zelena: mrr_clanarina|floatformat:2 EUR "Clanarine ovaj mj."
  Plava: donacije_ytd_eur|floatformat:2 EUR "Donacije YTD (donacije_ytd_n donatora)"
  Crvena (samo ako > 0): dospjele_clanarine "Dospjelih clanarina"
  Narancasta (samo ako uses_double_entry i neproknjizano_eur > 0): "Neproknjizano EUR"

---

KORAK 13: Finalna provjera

EXEC: cd /var/www/fina-connect && venv/bin/python manage.py check 2>&1 | tail -5

EXEC: venv/bin/python manage.py shell -c "
from udruge.models import Clanarina, Donacija
from konto.booking_engine import auto_knjizi_clanarina, auto_knjizi_donacija
print('Import OK')
" 2>/dev/null | grep -v Warning

EXEC: systemctl restart gunicorn-fina
EXEC: sleep 5 && curl -s -o /dev/null -w "HTTP %{http_code}" https://limit-connect.com/

EXEC: cd /var/www/fina-connect && git add -A && git commit -m "feat(udruge-konto): dvojno knjizenje, auto JournalEntry za clanarine/donacije, KPI widget, tax deadline WhatsApp"

DONE kriterij:
- Company.uses_double_entry polje i migracija OK
- auto_knjizi_clanarina i auto_knjizi_donacija funkcije u konto/booking_engine.py
- Clanarina.mark_paid() poziva auto_knjizi_clanarina
- donacija_create view poziva auto_knjizi_donacija
- udruge/signals.py kreira ArhivaEntry za KnjigaPrimitaka i Donacija
- udruge/apps.py importa signals u ready()
- tax_deadline_notifier Celery task registriran
- KPI context u udruge dashboard view
- manage.py check: 0 errors
- git commit postoji

NAPOMENA ZA IVANA:
- Aktivirati uses_double_entry = True u Company admin za udruge koje trebaju dvojno knjizenje
- U .env: MARIJA_WHATSAPP mora biti postavljen za tax deadline notifikacije
- Konta 111, 112, 321, 351, 352 moraju postojati u KontoAccount za kompaniju
  (Automatski se kreiraju ako pozovemo setup_nonprofit_accounts(company))
  CC Code provjerava i poziva setup_nonprofit_accounts ako konta nedostaju.
