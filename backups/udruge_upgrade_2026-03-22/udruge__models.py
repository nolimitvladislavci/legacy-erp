"""
Udruge modul - evidencija clanova braniteljskih, sportskih i OPG udruga.
Cross-sell: clan udruge -> potencijalni OPG/obrt korisnik LC-a.
"""
from django.conf import settings
from django.db import models
from django.utils import timezone


class Clan(models.Model):
    """Clan udruge - osnovna evidencija + cross-sell polja."""

    MEMBERSHIP_CHOICES = [
        ('redovni', 'Redovni clan'),
        ('pocasni', 'Pocasni clan'),
        ('pridruzeni', 'Pridruzeni clan'),
        ('osnivac', 'Osnivacki clan'),
        ('branitelj', 'Branitelj'),
    ]
    STATUS_CHOICES = [
        ('aktivan', 'Aktivan'),
        ('neaktivan', 'Neaktivan'),
        ('istupio', 'Istupio'),
        ('iskljucen', 'Iskljucen'),
    ]
    INTEREST_CHOICES = [
        ('opg', 'OPG / Poljoprivreda'),
        ('obrt', 'Obrt'),
        ('ugostiteljstvo', 'Ugostiteljstvo'),
        ('trgovina', 'Trgovina'),
        ('usluge', 'Usluge'),
        ('', 'Nije navedeno'),
    ]

    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='udruga_clanovi'
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    oib = models.CharField(max_length=11, blank=True, db_index=True)
    date_of_birth = models.DateField(null=True, blank=True)

    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)

    membership_type = models.CharField(max_length=20, choices=MEMBERSHIP_CHOICES, default='redovni')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='aktivan')
    date_joined = models.DateField(default=timezone.now)
    membership_number = models.CharField(max_length=50, blank=True)
    membership_expires = models.DateField(null=True, blank=True)

    business_interest = models.CharField(max_length=20, choices=INTEREST_CHOICES, blank=True)
    has_opg = models.BooleanField(default=False)
    opg_oib = models.CharField(max_length=11, blank=True)
    has_obrt = models.BooleanField(default=False)

    ai_profile = models.JSONField(default=dict, blank=True)
    ai_last_analyzed = models.DateTimeField(null=True, blank=True)
    oib_lookup_result = models.JSONField(default=dict, blank=True)
    oib_last_checked = models.DateTimeField(null=True, blank=True)

    whatsapp_phone = models.CharField(max_length=50, blank=True)
    whatsapp_opt_in = models.BooleanField(default=False)

    # Kisobran naplata: tko placa clanarinu za ovog clana?
    paying_sponsor = models.ForeignKey(
        'partners.Partner', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='sponsored_members',
        verbose_name='Sponzor/Platitelj',
        help_text='Npr. otac placa za 3 djece, firma za zaposlenike',
    )
    # IoT/pristup: UID kartice za kontrolu pristupa
    access_card_uid = models.CharField(
        max_length=100, blank=True, db_index=True,
        verbose_name='UID pristupne kartice',
        help_text='NFC/RFID UID za kontrolu pristupa dvorani',
    )

    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'udruge_clan'
        ordering = ['last_name', 'first_name']
        indexes = [
            models.Index(fields=['company', 'status']),
            models.Index(fields=['company', 'membership_expires']),
        ]

    def __str__(self):
        return '%s %s' % (self.last_name, self.first_name)

    @property
    def full_name(self):
        return '%s %s' % (self.first_name, self.last_name)

    @property
    def billing_target(self):
        """Tko prima uplatnicu — sponzor ili sam clan."""
        if self.paying_sponsor:
            return self.paying_sponsor
        return self

    @property
    def is_sponsored(self):
        return self.paying_sponsor is not None

    @property
    def is_expired(self):
        if not self.membership_expires:
            return False
        return self.membership_expires < timezone.now().date()

    @property
    def days_until_expiry(self):
        if not self.membership_expires:
            return None
        return (self.membership_expires - timezone.now().date()).days


class ClanBiljeska(models.Model):
    """Biljeske o clanu."""
    clan = models.ForeignKey(Clan, on_delete=models.CASCADE, related_name='biljeske')
    text = models.TextField()
    tip = models.CharField(max_length=10, choices=[
        ('rucno', 'Rucno'), ('ai', 'AI'), ('sistem', 'Sistem'),
    ], default='rucno')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'udruge_clan_biljeska'
        ordering = ['-created_at']



class Clanarina(models.Model):
    """Evidencija placanja clanarine — NE fiskalizira se, ide na konto 32."""

    PAYMENT_METHOD_CHOICES = [
        ('gotovina', 'Gotovina'),
        ('virman', 'Virman / IBAN uplata'),
        ('pos', 'POS (neprofitni bon)'),
        ('online', 'Online'),
    ]
    STATUS_CHOICES = [
        ('placena', 'Placena'),
        ('ceka', 'Ceka uplatu'),
        ('kasni', 'Kasni'),
        ('otpisana', 'Otpisana'),
    ]

    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='clanarine',
    )
    clan = models.ForeignKey(
        Clan, on_delete=models.CASCADE,
        related_name='clanarine',
    )

    period_start = models.DateField(verbose_name='Pocetak perioda')
    period_end = models.DateField(verbose_name='Kraj perioda')
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Iznos (EUR)')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='gotovina')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ceka')

    paid_at = models.DateTimeField(null=True, blank=True, verbose_name='Datum uplate')
    receipt_number = models.CharField(max_length=50, blank=True, verbose_name='Broj priznanice')
    note = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'udruge_clanarina'
        ordering = ['-period_start']
        indexes = [
            models.Index(fields=['company', 'status']),
        ]

    def __str__(self):
        return '%s — %s (%s EUR)' % (self.clan, self.period_start, self.amount)

    def mark_paid(self, method='gotovina'):
        self.status = 'placena'
        self.paid_at = timezone.now()
        self.payment_method = method
        self.save(update_fields=['status', 'paid_at', 'payment_method', 'updated_at'])


class Donacija(models.Model):
    """Evidencija donacija — porezna potvrda za donatora, konto 35."""

    DONOR_TYPE_CHOICES = [
        ('fizicka', 'Fizicka osoba'),
        ('pravna', 'Pravna osoba'),
        ('anonimno', 'Anonimno'),
    ]

    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='donacije',
    )
    donor_name = models.CharField(max_length=200, verbose_name='Ime donatora')
    donor_oib = models.CharField(max_length=11, blank=True, verbose_name='OIB donatora')
    donor_type = models.CharField(max_length=20, choices=DONOR_TYPE_CHOICES, default='fizicka')
    donor_address = models.CharField(max_length=255, blank=True)

    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Iznos (EUR)')
    purpose = models.CharField(max_length=255, blank=True, verbose_name='Namjena donacije')
    date = models.DateField(default=timezone.now, verbose_name='Datum donacije')

    # Za poreznu potvrdu
    potvrda_number = models.CharField(max_length=50, blank=True, verbose_name='Broj potvrde')
    potvrda_issued = models.BooleanField(default=False, verbose_name='Potvrda izdana')
    potvrda_issued_at = models.DateTimeField(null=True, blank=True)

    note = models.CharField(max_length=255, blank=True)

    # AML Guard (ZSPNFT — Zakon o sprjecavanju pranja novca)
    AML_STATUS_CHOICES = [
        ('clear', 'Cisto'),
        ('review', 'Na pregledu'),
        ('kyc_pending', 'Ceka KYC provjeru'),
        ('blocked', 'Blokirano'),
        ('reported', 'Prijavljeno USKOK-u'),
    ]
    aml_status = models.CharField(max_length=20, choices=AML_STATUS_CHOICES, default='clear',
                                   verbose_name='AML status')
    aml_flag_reason = models.CharField(max_length=255, blank=True, verbose_name='AML razlog')
    aml_flagged_at = models.DateTimeField(null=True, blank=True)

    # Materijalna donacija
    is_material = models.BooleanField(default=False, verbose_name='Materijalna donacija',
                                       help_text='Roba/oprema umjesto novca')
    material_description = models.CharField(max_length=255, blank=True, verbose_name='Opis robe')
    material_fair_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
                                               verbose_name='Fer trzisna vrijednost (EUR)')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'udruge_donacija'
        ordering = ['-date']
        indexes = [
            models.Index(fields=['company', 'date']),
        ]

    def __str__(self):
        return '%s — %s EUR (%s)' % (self.donor_name, self.amount, self.date)


class KnjigaPrimitaka(models.Model):
    """
    Knjiga primitaka i izdataka — jednostavno racunovodstvo za male udruge.
    Zamjena za Dnevnik/Glavnu knjigu kad je prihod < 30.000 EUR.
    """

    VRSTA_CHOICES = [
        ('primitak', 'Primitak'),
        ('izdatak', 'Izdatak'),
    ]
    IZVOR_CHOICES = [
        ('clanarina', 'Clanarina'),
        ('donacija', 'Donacija'),
        ('dotacija', 'Dotacija / Grant'),
        ('prodaja', 'Prodaja (gospodarska)'),
        ('placa', 'Placa'),
        ('materijal', 'Materijalni troskovi'),
        ('rezije', 'Rezije'),
        ('ostalo', 'Ostalo'),
    ]

    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='knjiga_primitaka',
    )
    redni_broj = models.PositiveIntegerField(verbose_name='R.br.')
    datum = models.DateField(verbose_name='Datum')
    opis = models.CharField(max_length=255, verbose_name='Opis primitka/izdatka')
    vrsta = models.CharField(max_length=10, choices=VRSTA_CHOICES)
    izvor = models.CharField(max_length=20, choices=IZVOR_CHOICES, default='ostalo')
    iznos = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Iznos (EUR)')

    # Veze (opcionalno)
    clanarina = models.ForeignKey(Clanarina, on_delete=models.SET_NULL, null=True, blank=True)
    donacija = models.ForeignKey(Donacija, on_delete=models.SET_NULL, null=True, blank=True)

    dokument = models.CharField(max_length=100, blank=True, verbose_name='Broj dokumenta')
    napomena = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'udruge_knjiga_primitaka'
        ordering = ['datum', 'redni_broj']
        unique_together = [('company', 'redni_broj', 'datum')]

    def __str__(self):
        return '#%d %s %s EUR' % (self.redni_broj, self.opis[:30], self.iznos)



class MembershipPlan(models.Model):
    """
    Plan clanarine s automatikom: trajanje, cijena, grace period, popust.
    Vezan na InventoryItem za POS integraciju.
    """
    BILLING_PERIOD_CHOICES = [
        ('monthly', 'Mjesecno'),
        ('quarterly', 'Kvartalno'),
        ('yearly', 'Godisnje'),
        ('lifetime', 'Dozivotno'),
    ]

    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='membership_plans',
    )
    name = models.CharField(max_length=100, verbose_name='Naziv plana')
    description = models.TextField(blank=True)

    # Veza na inventar — clanarina kao artikl za POS/fakturiranje
    linked_item = models.ForeignKey(
        'inventory.InventoryItem', on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name='Povezani artikl',
        help_text='Artikl za POS naplatu (is_nonprofit_activity=True)',
    )

    billing_period = models.CharField(max_length=20, choices=BILLING_PERIOD_CHOICES, default='yearly')
    duration_days = models.PositiveIntegerField(default=365, verbose_name='Trajanje (dana)')
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Cijena (EUR)')

    # Automatika
    auto_renew = models.BooleanField(
        default=True,
        verbose_name='Automatska obnova',
        help_text='Sustav kreira novu clanarinu prije isteka',
    )
    grace_period_days = models.PositiveIntegerField(
        default=7,
        verbose_name='Grace period (dana)',
        help_text='Tolerancija prije suspenzije',
    )

    # Povlastice — postotak popusta na POS-u za aktivne clanove
    discount_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        verbose_name='Popust za clanove (%)',
        help_text='Automatski popust na POS-u dok je clanarina aktivna',
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'udruge_membership_plan'
        unique_together = [('company', 'name')]
        ordering = ['name']

    def __str__(self):
        return '%s — %s EUR/%s' % (self.name, self.price, self.billing_period)


class MemberSubscription(models.Model):
    """
    State-machine zivotnog ciklusa clanarine.
    draft -> active -> grace -> suspended -> cancelled
    Celery evaluate_status() svake noci u 02:00.
    """
    STATUS_CHOICES = [
        ('draft', 'U pripremi'),
        ('active', 'Aktivno'),
        ('grace', 'Pocek (isteklo ali tolerirano)'),
        ('suspended', 'Suspendirano'),
        ('cancelled', 'Otkazano'),
    ]

    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='member_subscriptions',
    )
    clan = models.ForeignKey(
        Clan, on_delete=models.CASCADE,
        related_name='subscriptions',
    )
    plan = models.ForeignKey(
        MembershipPlan, on_delete=models.RESTRICT,
        related_name='subscriptions',
    )

    valid_from = models.DateField(default=timezone.now)
    valid_until = models.DateField()

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    status_changed_at = models.DateTimeField(auto_now=True)

    # Veza na naplatu
    clanarina = models.ForeignKey(
        Clanarina, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='subscription',
    )
    payment_reference = models.CharField(
        max_length=100, blank=True,
        verbose_name='Referenca placanja',
        help_text='Broj POS bona, uplatnice ili fakture',
    )

    # Dunning tracking
    reminder_sent_at = models.DateTimeField(null=True, blank=True)
    reminders_count = models.PositiveSmallIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'udruge_member_subscription'
        indexes = [
            models.Index(fields=['status', 'valid_until']),
            models.Index(fields=['company', 'status']),
        ]
        ordering = ['-valid_from']

    def __str__(self):
        return '%s — %s (%s)' % (self.clan, self.plan.name, self.status)

    def evaluate_status(self):
        """
        State machine — poziva Celery svake noci.
        active -> grace (isteklo, unutar grace perioda)
        grace -> suspended (istekao grace period)
        Ne dira draft/cancelled.
        """
        today = timezone.now().date()

        if self.status in ('cancelled', 'draft'):
            return self.status

        old_status = self.status
        grace_end = self.valid_until + timezone.timedelta(days=self.plan.grace_period_days)

        if self.valid_until >= today:
            self.status = 'active'
        elif grace_end >= today:
            self.status = 'grace'
        else:
            self.status = 'suspended'

        if self.status != old_status:
            self.save(update_fields=['status', 'status_changed_at'])

        return self.status

    def activate(self, payment_ref=''):
        self.status = 'active'
        self.payment_reference = payment_ref
        self.save(update_fields=['status', 'payment_reference', 'status_changed_at'])

    def cancel(self):
        self.status = 'cancelled'
        self.save(update_fields=['status', 'status_changed_at'])

    @property
    def is_active_or_grace(self):
        return self.status in ('active', 'grace')

    @property
    def days_remaining(self):
        if not self.valid_until:
            return None
        return (self.valid_until - timezone.now().date()).days



# ═══════════════════════════════════════════════════════════════════════════
# DOGADJAJI / EVENTI
# ═══════════════════════════════════════════════════════════════════════════

class Dogadjaj(models.Model):
    """Dogadjaj udruge — koncert, skupstina, humanitarna akcija, radionica."""

    STATUS_CHOICES = [
        ('draft', 'Nacrt'),
        ('planned', 'Planiran'),
        ('active', 'U tijeku'),
        ('completed', 'Zavrsen'),
        ('cancelled', 'Otkazan'),
    ]
    TYPE_CHOICES = [
        ('skupstina', 'Skupstina'),
        ('koncert', 'Koncert / Nastup'),
        ('radionica', 'Radionica / Seminar'),
        ('humanitarna', 'Humanitarna akcija'),
        ('sportski', 'Sportski dogadjaj'),
        ('druzenje', 'Druzenje / Teambuilding'),
        ('fundraising', 'Fundraising event'),
        ('festival', 'Festival'),
        ('ostalo', 'Ostalo'),
    ]

    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='dogadjaji',
    )
    name = models.CharField(max_length=200, verbose_name='Naziv dogadjaja')
    event_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='ostalo')
    description = models.TextField(blank=True, verbose_name='Opis')

    # Kad i gdje
    start_date = models.DateTimeField(verbose_name='Pocetak')
    end_date = models.DateTimeField(null=True, blank=True, verbose_name='Kraj')
    location = models.CharField(max_length=255, blank=True, verbose_name='Lokacija')
    online_url = models.URLField(blank=True, verbose_name='Online link (Zoom/Teams)')

    # Kapacitet i prijave
    max_attendees = models.PositiveIntegerField(default=0, verbose_name='Max polaznika (0=neograniceno)')
    registration_required = models.BooleanField(default=False, verbose_name='Prijava obavezna')
    registration_deadline = models.DateTimeField(null=True, blank=True)
    ticket_price = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Cijena ulaznice (EUR)')
    is_free = models.BooleanField(default=True, verbose_name='Besplatan')

    # Status i organizacija
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    organizer = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='Organizator',
    )
    budget = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Budzet (EUR)')
    actual_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Stvarni trosak (EUR)')
    revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Prihod (EUR)')

    # Veza s kampanjom
    kampanja = models.ForeignKey(
        'Kampanja', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='dogadjaji', verbose_name='Povezana kampanja',
    )

    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'udruge_dogadjaj'
        ordering = ['-start_date']

    def __str__(self):
        return '%s (%s)' % (self.name, self.start_date.strftime('%d.%m.%Y'))

    @property
    def attendee_count(self):
        return self.prijave.filter(status='confirmed').count()

    @property
    def spots_left(self):
        if not self.max_attendees:
            return 999
        return max(0, self.max_attendees - self.attendee_count)

    @property
    def is_full(self):
        return self.max_attendees > 0 and self.attendee_count >= self.max_attendees

    @property
    def profit(self):
        return self.revenue - self.actual_cost


class EventPrijava(models.Model):
    """Prijava clana na dogadjaj."""
    STATUS_CHOICES = [
        ('pending', 'Na cekanju'),
        ('confirmed', 'Potvrdjen'),
        ('cancelled', 'Otkazan'),
        ('attended', 'Prisustvovao'),
        ('no_show', 'Nije dosao'),
    ]

    dogadjaj = models.ForeignKey(Dogadjaj, on_delete=models.CASCADE, related_name='prijave')
    clan = models.ForeignKey(Clan, on_delete=models.CASCADE, related_name='event_prijave')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    registered_at = models.DateTimeField(auto_now_add=True)
    notes = models.CharField(max_length=255, blank=True)
    paid = models.BooleanField(default=False)

    class Meta:
        db_table = 'udruge_event_prijava'
        unique_together = [('dogadjaj', 'clan')]

    def __str__(self):
        return '%s -> %s (%s)' % (self.clan, self.dogadjaj.name, self.status)


# ═══════════════════════════════════════════════════════════════════════════
# KAMPANJE (Fundraising, EU fondovi, eventi)
# ═══════════════════════════════════════════════════════════════════════════

class Kampanja(models.Model):
    """Kampanja — fundraising, EU fond prijava, donacijska akcija."""

    TYPE_CHOICES = [
        ('fundraising', 'Fundraising'),
        ('eu_fond', 'EU Fond prijava'),
        ('donacijska', 'Donacijska akcija'),
        ('clanarinska', 'Clanarinska kampanja'),
        ('awareness', 'Awareness / PR'),
        ('event', 'Event kampanja'),
    ]
    STATUS_CHOICES = [
        ('draft', 'Nacrt'),
        ('active', 'Aktivna'),
        ('paused', 'Pauzirana'),
        ('completed', 'Zavrsena'),
        ('cancelled', 'Otkazana'),
    ]

    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='kampanje',
    )
    name = models.CharField(max_length=200, verbose_name='Naziv kampanje')
    campaign_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='fundraising')
    description = models.TextField(blank=True)

    # Vremenski okvir
    start_date = models.DateField(verbose_name='Pocetak')
    end_date = models.DateField(null=True, blank=True, verbose_name='Kraj')

    # Ciljevi
    goal_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Cilj (EUR)')
    raised_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Prikupljeno (EUR)')
    goal_members = models.PositiveIntegerField(default=0, verbose_name='Cilj clanova')
    acquired_members = models.PositiveIntegerField(default=0, verbose_name='Dobiveno clanova')

    # EU fond specifika
    eu_project_code = models.CharField(max_length=100, blank=True, verbose_name='Sifra EU projekta')
    eu_program = models.CharField(max_length=200, blank=True, verbose_name='EU program (ESF+, ERDF...)')
    eu_submitted_at = models.DateField(null=True, blank=True, verbose_name='Datum prijave')
    eu_decision_at = models.DateField(null=True, blank=True, verbose_name='Datum odluke')
    eu_status = models.CharField(max_length=20, blank=True, choices=[
        ('preparing', 'U pripremi'),
        ('submitted', 'Prijavljeno'),
        ('evaluation', 'Evaluacija'),
        ('approved', 'Odobreno'),
        ('rejected', 'Odbijeno'),
        ('implementation', 'Provedba'),
        ('reporting', 'Izvjestavanje'),
        ('closed', 'Zatvoreno'),
    ], verbose_name='EU status')

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    responsible = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='Odgovorna osoba',
    )

    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'udruge_kampanja'
        ordering = ['-start_date']

    def __str__(self):
        return '%s (%s)' % (self.name, self.get_campaign_type_display())

    @property
    def progress_percent(self):
        if not self.goal_amount:
            return 0
        return min(100, int(self.raised_amount / self.goal_amount * 100))

    @property
    def days_remaining(self):
        if not self.end_date:
            return None
        from django.utils import timezone
        return (self.end_date - timezone.now().date()).days


# ═══════════════════════════════════════════════════════════════════════════
# EMAIL KAMPANJE (AI automatizacija)
# ═══════════════════════════════════════════════════════════════════════════

class EmailKampanja(models.Model):
    """Email kampanja — masovno slanje clanovima s AI personalizacijom."""

    STATUS_CHOICES = [
        ('draft', 'Nacrt'),
        ('scheduled', 'Zakazana'),
        ('sending', 'Salje se'),
        ('sent', 'Poslana'),
        ('cancelled', 'Otkazana'),
    ]
    TYPE_CHOICES = [
        ('newsletter', 'Newsletter'),
        ('clanarina_reminder', 'Podsjetnik za clanarinu'),
        ('event_invite', 'Pozivnica na dogadjaj'),
        ('fundraising', 'Fundraising apel'),
        ('thank_you', 'Zahvalnica donatorima'),
        ('report', 'Godisnji izvjestaj'),
        ('custom', 'Prilagodjeno'),
    ]

    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='email_kampanje',
    )
    name = models.CharField(max_length=200, verbose_name='Naziv')
    email_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='newsletter')
    subject = models.CharField(max_length=200, verbose_name='Predmet emaila')
    body_html = models.TextField(blank=True, verbose_name='Sadrzaj (HTML)')
    body_text = models.TextField(blank=True, verbose_name='Sadrzaj (tekst)')

    # AI personalizacija
    ai_generated = models.BooleanField(default=False, verbose_name='AI generirao sadrzaj')
    ai_prompt = models.TextField(blank=True, verbose_name='AI prompt za generiranje')

    # Targeting
    target_all_members = models.BooleanField(default=True, verbose_name='Svi clanovi')
    target_membership_types = models.JSONField(default=list, blank=True, verbose_name='Tipovi clanstva')
    target_statuses = models.JSONField(default=list, blank=True, verbose_name='Statusi')
    target_kampanja = models.ForeignKey(
        Kampanja, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='Vezana kampanja',
    )
    target_dogadjaj = models.ForeignKey(
        Dogadjaj, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='Vezani dogadjaj',
    )

    # Slanje
    scheduled_at = models.DateTimeField(null=True, blank=True, verbose_name='Zakazano slanje')
    sent_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    # Statistike
    total_recipients = models.PositiveIntegerField(default=0)
    total_sent = models.PositiveIntegerField(default=0)
    total_opened = models.PositiveIntegerField(default=0)
    total_clicked = models.PositiveIntegerField(default=0)
    total_bounced = models.PositiveIntegerField(default=0)

    created_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'udruge_email_kampanja'
        ordering = ['-created_at']

    def __str__(self):
        return '%s (%s)' % (self.name, self.get_status_display())

    @property
    def open_rate(self):
        if not self.total_sent:
            return 0
        return round(self.total_opened / self.total_sent * 100, 1)

    @property
    def click_rate(self):
        if not self.total_sent:
            return 0
        return round(self.total_clicked / self.total_sent * 100, 1)

    def get_recipients(self):
        """Dohvati listu clanova prema targeting pravilima."""
        qs = Clan.objects.filter(company=self.company, status='aktivan')
        if not self.target_all_members:
            if self.target_membership_types:
                qs = qs.filter(membership_type__in=self.target_membership_types)
            if self.target_statuses:
                qs = qs.filter(status__in=self.target_statuses)
        return qs.exclude(email='').exclude(email__isnull=True)


class EmailLog(models.Model):
    """Log pojedinacnog emaila iz kampanje."""
    kampanja = models.ForeignKey(EmailKampanja, on_delete=models.CASCADE, related_name='logs')
    clan = models.ForeignKey(Clan, on_delete=models.CASCADE)
    email = models.EmailField()
    status = models.CharField(max_length=20, choices=[
        ('queued', 'U redu'),
        ('sent', 'Poslan'),
        ('opened', 'Otvoren'),
        ('clicked', 'Kliknuo'),
        ('bounced', 'Odbijen'),
        ('error', 'Greska'),
    ], default='queued')
    sent_at = models.DateTimeField(null=True, blank=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    error_message = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = 'udruge_email_log'
        ordering = ['-sent_at']
