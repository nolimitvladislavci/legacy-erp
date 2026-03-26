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
        ('senior', 'Senior'),
        ('junior', 'Junior / Omladinac'),
        ('kadeti', 'Kadet'),
        ('sportski', 'Sportski clan'),
        ('rekreativac', 'Rekreativac'),
        ('zena', 'Clan - zena'),
        ('umirovljenik', 'Umirovljenik'),
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


# ═══════════════════════════════════════════════════════════════════════════
# VOLONTERSKE AKTIVNOSTI
# ═══════════════════════════════════════════════════════════════════════════

class VolunteerActivity(models.Model):
    """Evidencija volonterskih aktivnosti — Zakon o volonterstvu (NN 58/07, 22/13)."""
    STATUS_CHOICES = [
        ('planned', 'Planirana'), ('in_progress', 'U tijeku'),
        ('completed', 'Zavrsena'), ('cancelled', 'Otkazana'),
    ]
    CATEGORY_CHOICES = [
        ('admin', 'Administrativno'), ('field', 'Terenski rad'),
        ('event', 'Organizacija eventi'), ('education', 'Edukacija / Mentoring'),
        ('fundraising', 'Fundraising'), ('it', 'IT / Digitalizacija'),
        ('legal', 'Pravna pomoc'), ('social', 'Socijalni rad'),
        ('sports', 'Sport / Rekreacija'), ('culture', 'Kultura / Umjetnost'),
        ('environment', 'Zastita okolisa'), ('other', 'Ostalo'),
    ]

    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='volunteer_activities')
    clan = models.ForeignKey(Clan, on_delete=models.CASCADE, related_name='volunteer_activities', verbose_name='Volonter')
    dogadjaj = models.ForeignKey(Dogadjaj, on_delete=models.SET_NULL, null=True, blank=True, related_name='volunteer_activities')
    kampanja = models.ForeignKey(Kampanja, on_delete=models.SET_NULL, null=True, blank=True, related_name='volunteer_activities')

    title = models.CharField(max_length=200, verbose_name='Naziv aktivnosti')
    description = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')
    date = models.DateField(verbose_name='Datum')
    hours = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='Broj sati')
    location = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planned')
    eu_project_code = models.CharField(max_length=100, blank=True)
    inkind_rate_eur = models.DecimalField(max_digits=8, decimal_places=2, default=0,
        verbose_name='In-kind satnica (EUR)',
        help_text='Fer trzisna vrijednost sata volonterskog rada za EU izvjestaj')
    verified_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'udruge_volunteer_activity'
        ordering = ['-date']
        indexes = [
            models.Index(fields=['company', 'date'], name='udruge_vol_comp_date_idx'),
            models.Index(fields=['company', 'clan', 'date'], name='udruge_vol_comp_clan_idx'),
        ]

    def __str__(self):
        return '%s — %s (%s sati)' % (self.clan.full_name, self.title[:30], self.hours)

    @property
    def inkind_value(self):
        return self.hours * self.inkind_rate_eur


# ═══════════════════════════════════════════════════════════════
#  Sekcije + Dozvole — KUD, Ribolov, Lov, Sport
# ═══════════════════════════════════════════════════════════════

class Sekcija(models.Model):
    """Sekcija/skupina unutar udruge (KUD: tamburaši, pjevači; Ribolov: seniori, juniori)."""
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE,
        related_name='sekcije',
    )
    name = models.CharField(max_length=100, verbose_name='Naziv sekcije')
    description = models.TextField(blank=True)
    leader = models.ForeignKey(
        'Clan', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='led_sections',
        verbose_name='Voditelj sekcije',
    )
    max_members = models.PositiveIntegerField(default=0, help_text='0=neograničeno')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Sekcija'
        verbose_name_plural = 'Sekcije'
        unique_together = [('company', 'name')]

    def __str__(self):
        return self.name

    @property
    def member_count(self):
        return self.members.filter(clan__status='aktivan').count()


class ClanSekcija(models.Model):
    """Članstvo u sekciji (M2M through)."""
    clan = models.ForeignKey('Clan', on_delete=models.CASCADE, related_name='section_memberships')
    sekcija = models.ForeignKey(Sekcija, on_delete=models.CASCADE, related_name='members')
    role = models.CharField(max_length=30, blank=True, help_text='Npr. solist, bubnjač, kapetan')
    joined_at = models.DateField(auto_now_add=True)

    class Meta:
        unique_together = [('clan', 'sekcija')]
        verbose_name = 'Član sekcije'
        verbose_name_plural = 'Članovi sekcija'

    def __str__(self):
        return f'{self.clan} → {self.sekcija} ({self.role})'


class ClanskiDokument(models.Model):
    """Dozvola/licenca člana — ribolovna, lovačka, oružni list, zdravstvena potvrda."""
    DOC_TYPES = [
        ('ribolovna', 'Ribolovna dozvola'),
        ('lovacka', 'Lovačka dozvola'),
        ('oruzni_list', 'Oružni list'),
        ('zdravstvena', 'Zdravstvena potvrda'),
        ('osiguranje', 'Polica osiguranja'),
        ('iskaznica', 'Članska iskaznica'),
        ('certifikat', 'Certifikat / licenca'),
        ('other', 'Ostalo'),
    ]

    clan = models.ForeignKey('Clan', on_delete=models.CASCADE, related_name='dokumenti')
    doc_type = models.CharField(max_length=20, choices=DOC_TYPES)
    doc_number = models.CharField(max_length=50, blank=True, verbose_name='Broj dokumenta')
    issued_by = models.CharField(max_length=100, blank=True, verbose_name='Izdao')
    issue_date = models.DateField(null=True, blank=True)
    valid_until = models.DateField(null=True, blank=True)
    file = models.FileField(upload_to='clan_docs/%Y/', blank=True)
    notes = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-valid_until']
        verbose_name = 'Članski dokument'
        verbose_name_plural = 'Članski dokumenti'

    def __str__(self):
        return f'{self.get_doc_type_display()} — {self.clan} (do {self.valid_until})'

    @property
    def is_expired(self):
        if not self.valid_until:
            return False
        return self.valid_until < timezone.now().date()

    @property
    def expires_soon(self):
        """Ističe u sljedećih 30 dana."""
        if not self.valid_until:
            return False
        from datetime import timedelta
        return self.valid_until <= (timezone.now().date() + timedelta(days=30))


class NatjecanjeRezultat(models.Model):
    """Rezultat natjecanja/nastupa — vezano na Dogadjaj."""
    dogadjaj = models.ForeignKey('Dogadjaj', on_delete=models.CASCADE, related_name='rezultati')
    clan = models.ForeignKey('Clan', on_delete=models.CASCADE, related_name='rezultati',
                             null=True, blank=True, help_text='Individualni rezultat')
    sekcija = models.ForeignKey(Sekcija, on_delete=models.SET_NULL,
                                null=True, blank=True, help_text='Ekipni rezultat')
    placement = models.PositiveIntegerField(null=True, blank=True, verbose_name='Plasman')
    score = models.CharField(max_length=50, blank=True, verbose_name='Rezultat/bodovi')
    category = models.CharField(max_length=100, blank=True, verbose_name='Kategorija')
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['placement']
        verbose_name = 'Rezultat natjecanja'
        verbose_name_plural = 'Rezultati natjecanja'

    def __str__(self):
        who = self.clan or self.sekcija or '?'
        return f'{who} — #{self.placement} ({self.dogadjaj})'


# ═══════════════════════════════════════════════════════════════════════════
# DVD — DOBROVOLJNO VATROGASNO DRUŠTVO
# Zakon o vatrogastvu (NN 125/19, 114/22)
# Pravilnik o evidencijama vatrogasnih postrojbi (NN 47/20)
# ═══════════════════════════════════════════════════════════════════════════

class VatrogasnaOprema(models.Model):
    """Vatrogasna oprema — aparati, cijevi, pumpe, dišni aparati, ljestve."""
    KATEGORIJA_CHOICES = [
        ('aparat', 'Aparat za gašenje'),
        ('cijev', 'Vatrogasna cijev'),
        ('pumpa', 'Pumpa'),
        ('disni', 'Dišni aparat'),
        ('ljestve', 'Ljestve'),
        ('alat', 'Ručni alat'),
        ('zasticna', 'Zaštitna oprema'),
        ('komunikacija', 'Komunikacijska oprema'),
        ('prva_pomoc', 'Prva pomoć'),
        ('ostalo', 'Ostalo'),
    ]
    STATUS_CHOICES = [
        ('ispravno', 'Ispravno'),
        ('servis', 'Na servisu'),
        ('neispravno', 'Neispravno'),
        ('otpisano', 'Otpisano'),
    ]

    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='vatrogasna_oprema')
    naziv = models.CharField(max_length=200, verbose_name='Naziv opreme')
    kategorija = models.CharField(max_length=20, choices=KATEGORIJA_CHOICES)
    serijski_broj = models.CharField(max_length=100, blank=True, verbose_name='Serijski broj')
    proizvodac = models.CharField(max_length=100, blank=True, verbose_name='Proizvođač')
    godina_nabave = models.PositiveSmallIntegerField(null=True, blank=True)
    nabavna_vrijednost = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Nabavna vrijednost (EUR)')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ispravno')
    # Atesti — KRITIČNO za sigurnost
    atest_datum = models.DateField(null=True, blank=True, verbose_name='Datum zadnjeg atesta')
    atest_vrijedi_do = models.DateField(null=True, blank=True, verbose_name='Atest vrijedi do')
    atest_izdavac = models.CharField(max_length=100, blank=True, verbose_name='Atest izdao')
    sljedeci_servis = models.DateField(null=True, blank=True, verbose_name='Sljedeći servis')
    lokacija = models.CharField(max_length=100, blank=True, verbose_name='Lokacija (spremište/vozilo)')
    qr_code = models.CharField(max_length=100, blank=True, db_index=True, verbose_name='QR kod opreme')
    photo = models.ImageField(upload_to='vatrogasci/oprema/%Y/', blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'udruge_vatrogasna_oprema'
        ordering = ['kategorija', 'naziv']
        verbose_name = 'Vatrogasna oprema'
        verbose_name_plural = 'Vatrogasna oprema'

    def __str__(self):
        return '%s — %s (%s)' % (self.naziv, self.get_kategorija_display(), self.get_status_display())

    @property
    def atest_istekao(self):
        if not self.atest_vrijedi_do:
            return False
        return self.atest_vrijedi_do < timezone.now().date()

    @property
    def atest_istice_uskoro(self):
        if not self.atest_vrijedi_do:
            return False
        from datetime import timedelta
        return self.atest_vrijedi_do <= (timezone.now().date() + timedelta(days=30))


class VatrogasnoVozilo(models.Model):
    """Vatrogasno vozilo — navalno, autocisterna, ljestvača, kombi."""
    TIP_CHOICES = [
        ('navalno', 'Navalno vozilo'),
        ('autocisterna', 'Autocisterna'),
        ('ljestve', 'Auto-ljestve'),
        ('kombi', 'Kombi / Pick-up'),
        ('zapovjedno', 'Zapovjedno vozilo'),
        ('tehnicko', 'Tehničko vozilo'),
        ('ostalo', 'Ostalo'),
    ]

    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='vatrogasna_vozila')
    naziv = models.CharField(max_length=100, verbose_name='Naziv vozila')
    tip = models.CharField(max_length=20, choices=TIP_CHOICES, default='navalno')
    reg_oznaka = models.CharField(max_length=20, verbose_name='Registarska oznaka')
    marka = models.CharField(max_length=50, blank=True, verbose_name='Marka / Model')
    godina_proizvodnje = models.PositiveSmallIntegerField(null=True, blank=True)
    sasija_broj = models.CharField(max_length=50, blank=True)
    kapacitet_vode_l = models.PositiveIntegerField(default=0, verbose_name='Kapacitet vode (L)')
    # Registracija i tehnički
    reg_vrijedi_do = models.DateField(null=True, blank=True, verbose_name='Registracija do')
    tehnicki_do = models.DateField(null=True, blank=True, verbose_name='Tehnički pregled do')
    osiguranje_do = models.DateField(null=True, blank=True, verbose_name='Osiguranje do')
    # Gorivo
    zadnje_tocenje_km = models.PositiveIntegerField(default=0, verbose_name='Km zadnjeg točenja')
    ukupni_km = models.PositiveIntegerField(default=0, verbose_name='Ukupni km')
    status = models.CharField(max_length=20, choices=[
        ('aktivno', 'Aktivno'), ('servis', 'Na servisu'), ('rashodovano', 'Rashodovano'),
    ], default='aktivno')
    photo = models.ImageField(upload_to='vatrogasci/vozila/%Y/', blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'udruge_vatrogasno_vozilo'
        ordering = ['naziv']
        verbose_name = 'Vatrogasno vozilo'

    def __str__(self):
        return '%s (%s) — %s' % (self.naziv, self.reg_oznaka, self.get_tip_display())


class Intervencija(models.Model):
    """Vatrogasna intervencija — Obrazac INT-1 (NN 47/20)."""
    TIP_CHOICES = [
        ('pozar', 'Požar'),
        ('tehnicka', 'Tehnička intervencija'),
        ('prometna', 'Prometna nesreća'),
        ('poplava', 'Poplava / Izlijevanje'),
        ('potraga', 'Potraga i spašavanje'),
        ('opasne_tvari', 'Opasne tvari (HAZMAT)'),
        ('vjezba', 'Vježba (terenska)'),
        ('dezurstvo', 'Dežurstvo'),
        ('ostalo', 'Ostalo'),
    ]

    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='intervencije')
    evidencijski_broj = models.CharField(max_length=50, verbose_name='Evidencijski broj (INT-1)')
    tip = models.CharField(max_length=20, choices=TIP_CHOICES)
    opis = models.TextField(verbose_name='Opis intervencije')
    # Vrijeme
    alarm_primljen = models.DateTimeField(verbose_name='Alarm primljen')
    izlazak = models.DateTimeField(null=True, blank=True, verbose_name='Izlazak')
    dolazak = models.DateTimeField(null=True, blank=True, verbose_name='Dolazak na mjesto')
    zavrsetak = models.DateTimeField(null=True, blank=True, verbose_name='Završetak')
    povratak = models.DateTimeField(null=True, blank=True, verbose_name='Povratak u postaju')
    # Lokacija
    lokacija = models.CharField(max_length=255, verbose_name='Lokacija')
    geo_lat = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    geo_lon = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    # Osoblje
    voditelj = models.ForeignKey(Clan, on_delete=models.SET_NULL, null=True, blank=True, related_name='vodio_intervencije')
    sudionici = models.ManyToManyField(Clan, blank=True, related_name='intervencije')
    broj_sudionika = models.PositiveSmallIntegerField(default=0)
    # Vozila i oprema
    vozila = models.ManyToManyField(VatrogasnoVozilo, blank=True, related_name='intervencije')
    oprema_koristena = models.ManyToManyField(VatrogasnaOprema, blank=True, related_name='intervencije')
    voda_utrosena_l = models.PositiveIntegerField(default=0, verbose_name='Voda utrošena (L)')
    pjena_utrosena_l = models.PositiveIntegerField(default=0, verbose_name='Pjena utrošena (L)')
    # Rezultat
    steta_eur = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Procijenjena šteta (EUR)')
    spaseno_osoba = models.PositiveSmallIntegerField(default=0)
    spaseno_zivotinja = models.PositiveSmallIntegerField(default=0)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'udruge_intervencija'
        ordering = ['-alarm_primljen']
        verbose_name = 'Intervencija'

    def __str__(self):
        return '%s — %s (%s)' % (self.evidencijski_broj, self.get_tip_display(), self.alarm_primljen.strftime('%d.%m.%Y'))

    @property
    def trajanje_minuta(self):
        if not self.zavrsetak:
            return None
        return int((self.zavrsetak - self.alarm_primljen).total_seconds() / 60)

    @property
    def vrijeme_odziva_min(self):
        if not self.dolazak or not self.alarm_primljen:
            return None
        return int((self.dolazak - self.alarm_primljen).total_seconds() / 60)


class Vjezba(models.Model):
    """Vatrogasna vježba — evidencija obuke i osposobljavanja."""
    TIP_CHOICES = [
        ('teorijska', 'Teorijska nastava'),
        ('prakticna', 'Praktična vježba'),
        ('natjecanje', 'Natjecanje / Olimpijada'),
        ('tecaj', 'Tečaj osposobljavanja'),
        ('ispit', 'Ispit'),
        ('terenska', 'Terenska vježba'),
    ]

    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='vjezbe')
    naziv = models.CharField(max_length=200, verbose_name='Naziv vježbe')
    tip = models.CharField(max_length=20, choices=TIP_CHOICES, default='prakticna')
    datum = models.DateField(verbose_name='Datum')
    trajanje_sati = models.DecimalField(max_digits=4, decimal_places=1, default=2, verbose_name='Trajanje (sati)')
    lokacija = models.CharField(max_length=200, blank=True)
    voditelj = models.ForeignKey(Clan, on_delete=models.SET_NULL, null=True, blank=True, related_name='vodio_vjezbe')
    sudionici = models.ManyToManyField(Clan, blank=True, related_name='vjezbe')
    opis = models.TextField(blank=True)
    ocjena = models.CharField(max_length=50, blank=True, verbose_name='Ocjena/Rezultat')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'udruge_vjezba'
        ordering = ['-datum']
        verbose_name = 'Vježba'

    def __str__(self):
        return '%s (%s)' % (self.naziv, self.datum.strftime('%d.%m.%Y'))


class VatrogasnoZvanje(models.Model):
    """Vatrogasno zvanje člana — razine prema Zakonu o vatrogastvu."""
    RAZINA_CHOICES = [
        ('podmladak', 'Vatrogasni podmladak'),
        ('A', 'Razina A — Vatrogasac'),
        ('B', 'Razina B — Dočasnik'),
        ('C', 'Razina C — Časnik'),
        ('D', 'Razina D — Viši časnik'),
        ('E', 'Razina E — Zapovjednik'),
        ('veteran', 'Vatrogasni veteran'),
    ]

    clan = models.ForeignKey(Clan, on_delete=models.CASCADE, related_name='vatrogasna_zvanja')
    razina = models.CharField(max_length=20, choices=RAZINA_CHOICES)
    naziv_zvanja = models.CharField(max_length=100, verbose_name='Naziv zvanja')
    datum_stjecanja = models.DateField(verbose_name='Datum stjecanja')
    certifikat_broj = models.CharField(max_length=50, blank=True)
    izdavac = models.CharField(max_length=100, blank=True, verbose_name='Izdao (VZG/VZŽ/HVZ)')
    notes = models.CharField(max_length=200, blank=True)

    class Meta:
        db_table = 'udruge_vatrogasno_zvanje'
        ordering = ['-datum_stjecanja']
        verbose_name = 'Vatrogasno zvanje'

    def __str__(self):
        return '%s — %s (%s)' % (self.clan, self.naziv_zvanja, self.get_razina_display())


# ═══════════════════════════════════════════════════════════════════════════
# KUD — KULTURNO-UMJETNIČKO DRUŠTVO
# Zakon o kulturnim vijećima (NN 83/22)
# ═══════════════════════════════════════════════════════════════════════════

class Repertoar(models.Model):
    """Repertoar KUD-a — pjesme, plesovi, drame, koreografije."""
    TIP_CHOICES = [
        ('pjesma', 'Pjesma'),
        ('ples', 'Ples / Koreografija'),
        ('drama', 'Drama / Igrokaz'),
        ('instrumentalna', 'Instrumentalna kompozicija'),
        ('recital', 'Recital / Recitacija'),
        ('ostalo', 'Ostalo'),
    ]

    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='repertoar')
    sekcija = models.ForeignKey(Sekcija, on_delete=models.SET_NULL, null=True, blank=True, related_name='repertoar')
    naziv = models.CharField(max_length=200, verbose_name='Naziv')
    tip = models.CharField(max_length=20, choices=TIP_CHOICES)
    autor = models.CharField(max_length=200, blank=True, verbose_name='Autor / Koreograf')
    trajanje_min = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='Trajanje (min)')
    region = models.CharField(max_length=100, blank=True, verbose_name='Regija / Kraj podrijetla')
    opis = models.TextField(blank=True)
    # Digitalni materijali
    note_file = models.FileField(upload_to='kud/note/%Y/', blank=True, verbose_name='Notni zapis')
    audio_file = models.FileField(upload_to='kud/audio/%Y/', blank=True, verbose_name='Audio snimka')
    video_url = models.URLField(blank=True, verbose_name='Video link')
    koreografija_file = models.FileField(upload_to='kud/koreo/%Y/', blank=True, verbose_name='Koreografija (PDF)')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'udruge_repertoar'
        ordering = ['naziv']
        verbose_name = 'Repertoar'

    def __str__(self):
        return '%s (%s)' % (self.naziv, self.get_tip_display())


class ProbaLog(models.Model):
    """Evidencija probe — datum, sekcija, prisutnost, bilješka."""
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='probe')
    sekcija = models.ForeignKey(Sekcija, on_delete=models.CASCADE, related_name='probe')
    datum = models.DateField(verbose_name='Datum probe')
    pocetak = models.TimeField(null=True, blank=True, verbose_name='Početak')
    kraj = models.TimeField(null=True, blank=True, verbose_name='Kraj')
    lokacija = models.CharField(max_length=200, blank=True)
    prisutni = models.ManyToManyField(Clan, blank=True, related_name='probe_prisutan')
    voditelj = models.ForeignKey(Clan, on_delete=models.SET_NULL, null=True, blank=True, related_name='vodio_probe')
    repertoar_radjen = models.ManyToManyField(Repertoar, blank=True, related_name='probe', verbose_name='Repertoar rađen')
    biljeska = models.TextField(blank=True, verbose_name='Bilješka')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'udruge_proba_log'
        ordering = ['-datum']
        verbose_name = 'Proba'

    def __str__(self):
        return '%s — %s (%s)' % (self.sekcija.name, self.datum.strftime('%d.%m.%Y'), self.prisutni_count)

    @property
    def prisutni_count(self):
        return self.prisutni.count()

    @property
    def trajanje_min(self):
        if not self.pocetak or not self.kraj:
            return None
        from datetime import datetime, timedelta
        start = datetime.combine(self.datum, self.pocetak)
        end = datetime.combine(self.datum, self.kraj)
        if end < start:
            end += timedelta(days=1)
        return int((end - start).total_seconds() / 60)


class Kostim(models.Model):
    """Inventar nošnji/kostima — KILLER FEATURE za KUD-ove."""
    STANJE_CHOICES = [
        ('novo', 'Novo'),
        ('dobro', 'Dobro'),
        ('trosno', 'Trošno'),
        ('popravak', 'Na popravku'),
        ('otpisano', 'Otpisano'),
    ]

    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='kostimi')
    naziv = models.CharField(max_length=200, verbose_name='Naziv nošnje/kostima')
    sekcija = models.ForeignKey(Sekcija, on_delete=models.SET_NULL, null=True, blank=True, related_name='kostimi')
    region = models.CharField(max_length=100, blank=True, verbose_name='Regija / Kraj')
    spol = models.CharField(max_length=10, choices=[('M', 'Muški'), ('Z', 'Ženski'), ('U', 'Unisex')], default='U')
    velicina = models.CharField(max_length=20, blank=True, verbose_name='Veličina')
    inventarni_broj = models.CharField(max_length=50, blank=True, verbose_name='Inventarni broj')
    # Dodjela
    dodijeljen_clanu = models.ForeignKey(Clan, on_delete=models.SET_NULL, null=True, blank=True, related_name='kostimi', verbose_name='Dodijeljeno članu')
    dodijeljen_od = models.DateField(null=True, blank=True)
    stanje = models.CharField(max_length=20, choices=STANJE_CHOICES, default='dobro')
    nabavna_cijena = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Nabavna cijena (EUR)')
    photo = models.ImageField(upload_to='kud/kostimi/%Y/', blank=True)
    opis_dijelova = models.TextField(blank=True, verbose_name='Opis dijelova (košulja, prsluk, suknja...)')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'udruge_kostim'
        ordering = ['naziv', 'velicina']
        verbose_name = 'Kostim / Nošnja'

    def __str__(self):
        assigned = ' → %s' % self.dodijeljen_clanu if self.dodijeljen_clanu else ''
        return '%s (%s, %s)%s' % (self.naziv, self.velicina, self.get_stanje_display(), assigned)


class NastupPlan(models.Model):
    """Plan nastupa — set lista, raspored, logistika."""
    dogadjaj = models.OneToOneField(Dogadjaj, on_delete=models.CASCADE, related_name='nastup_plan')
    set_lista = models.JSONField(default=list, blank=True, verbose_name='Set lista',
        help_text='[{"redni_broj":1, "repertoar_id":5, "napomena":""}]')
    raspored_dolaska = models.DateTimeField(null=True, blank=True, verbose_name='Dolazak na lokaciju')
    proba_prije_nastupa = models.BooleanField(default=False, verbose_name='Proba prije nastupa')
    garderoba = models.CharField(max_length=200, blank=True, verbose_name='Garderoba / Prostor')
    prijevoz = models.CharField(max_length=200, blank=True, verbose_name='Prijevoz')
    smjestaj = models.CharField(max_length=200, blank=True, verbose_name='Smještaj')
    troskovi = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Procijenjeni troškovi (EUR)')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'udruge_nastup_plan'
        verbose_name = 'Plan nastupa'

    def __str__(self):
        return 'Nastup plan: %s' % self.dogadjaj.name


# ═══════════════════════════════════════════════════════════════════════════
# RIBOLOV — ŠPORTSKI RIBOLOV
# Zakon o slatkovodnom ribarstvu (NN 63/19)
# Pravilnik o športskom ribolovu (NN 122/19, 15/21)
# ═══════════════════════════════════════════════════════════════════════════

class Revir(models.Model):
    """Ribolovni revir / voda — rijeka, jezero, akumulacija."""
    TIP_CHOICES = [
        ('rijeka', 'Rijeka'),
        ('jezero', 'Jezero'),
        ('akumulacija', 'Akumulacija'),
        ('kanal', 'Kanal'),
        ('potok', 'Potok'),
        ('bare', 'Bare / Mrtvice'),
    ]

    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='reviri')
    naziv = models.CharField(max_length=200, verbose_name='Naziv vode')
    tip = models.CharField(max_length=20, choices=TIP_CHOICES, default='rijeka')
    lokacija = models.CharField(max_length=255, blank=True, verbose_name='Lokacija / Dionica')
    geo_lat = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    geo_lon = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    povrsina_ha = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, verbose_name='Površina (ha)')
    duljina_km = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, verbose_name='Duljina (km)')
    # Riblje vrste
    glavne_vrste = models.JSONField(default=list, blank=True, verbose_name='Glavne riblje vrste',
        help_text='["šaran", "som", "štuka", "smuđ"]')
    max_dnevni_ulov_kg = models.DecimalField(max_digits=5, decimal_places=2, default=5, verbose_name='Max dnevni ulov (kg)')
    zabrana_ribolova = models.BooleanField(default=False, verbose_name='Zabrana ribolova (aktivna)')
    zabrana_razlog = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'udruge_revir'
        ordering = ['naziv']
        verbose_name = 'Ribolovni revir'

    def __str__(self):
        return '%s (%s)' % (self.naziv, self.get_tip_display())


class RibolovnaDozvola(models.Model):
    """Ribolovna dozvola — izdaje društvo, kategorije A-D."""
    KATEGORIJA_CHOICES = [
        ('A', 'Kategorija A — godišnja'),
        ('B', 'Kategorija B — višednevna'),
        ('C', 'Kategorija C — dnevna'),
        ('D', 'Kategorija D — podmladak'),
        ('turisticka', 'Turistička dozvola'),
    ]

    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='ribolovne_dozvole')
    clan = models.ForeignKey(Clan, on_delete=models.CASCADE, related_name='ribolovne_dozvole')
    kategorija = models.CharField(max_length=20, choices=KATEGORIJA_CHOICES)
    broj_dozvole = models.CharField(max_length=50, verbose_name='Broj dozvole')
    valid_from = models.DateField(verbose_name='Vrijedi od')
    valid_until = models.DateField(verbose_name='Vrijedi do')
    reviri = models.ManyToManyField(Revir, blank=True, related_name='dozvole', verbose_name='Dozvoljeni reviri')
    cijena = models.DecimalField(max_digits=8, decimal_places=2, default=0, verbose_name='Cijena (EUR)')
    placena = models.BooleanField(default=False)
    placeno_putem = models.CharField(max_length=20, blank=True, choices=[
        ('gotovina', 'Gotovina'), ('pos', 'POS'), ('virman', 'Virman'), ('online', 'Online'),
    ])
    issued_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'udruge_ribolovna_dozvola'
        ordering = ['-valid_from']
        verbose_name = 'Ribolovna dozvola'

    def __str__(self):
        return '%s — %s %s' % (self.clan, self.get_kategorija_display(), self.broj_dozvole)

    @property
    def is_valid(self):
        today = timezone.now().date()
        return self.valid_from <= today <= self.valid_until and self.placena


class UlovEvidencija(models.Model):
    """Evidencija ulova — zakonska obveza (Obrazac UL)."""
    METODA_CHOICES = [
        ('stap', 'Štap'),
        ('fly', 'Mušičarenje (fly)'),
        ('feeder', 'Feeder'),
        ('spinning', 'Spinning'),
        ('ostalo', 'Ostalo'),
    ]

    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='ulovi')
    clan = models.ForeignKey(Clan, on_delete=models.CASCADE, related_name='ulovi')
    revir = models.ForeignKey(Revir, on_delete=models.CASCADE, related_name='ulovi')
    datum = models.DateField(verbose_name='Datum')
    vrsta_ribe = models.CharField(max_length=100, verbose_name='Vrsta ribe')
    tezina_kg = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, verbose_name='Težina (kg)')
    duzina_cm = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='Dužina (cm)')
    komada = models.PositiveSmallIntegerField(default=1, verbose_name='Komada')
    catch_and_release = models.BooleanField(default=False, verbose_name='Catch & Release')
    metoda = models.CharField(max_length=20, choices=METODA_CHOICES, default='stap')
    photo = models.ImageField(upload_to='ribolov/ulovi/%Y/', blank=True)
    notes = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'udruge_ulov'
        ordering = ['-datum']
        verbose_name = 'Evidencija ulova'
        indexes = [
            models.Index(fields=['company', 'datum']),
            models.Index(fields=['clan', 'datum']),
        ]

    def __str__(self):
        return '%s — %s %s kg (%s)' % (self.clan, self.vrsta_ribe, self.tezina_kg or '?', self.datum)


class Poribljavanje(models.Model):
    """Evidencija poribljanja — plan i izvršenje."""
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='poribljavanja')
    revir = models.ForeignKey(Revir, on_delete=models.CASCADE, related_name='poribljavanja')
    datum = models.DateField(verbose_name='Datum')
    vrsta_ribe = models.CharField(max_length=100, verbose_name='Vrsta ribe')
    kolicina_kg = models.DecimalField(max_digits=8, decimal_places=2, verbose_name='Količina (kg)')
    komada = models.PositiveIntegerField(default=0, verbose_name='Komada')
    dobavljac = models.CharField(max_length=200, blank=True, verbose_name='Dobavljač / Ribnjak')
    cijena_eur = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Cijena (EUR)')
    financirano_iz = models.CharField(max_length=100, blank=True, verbose_name='Financirano iz',
        help_text='članarine, proračun, HSR, EU fond...')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'udruge_poribljavanje'
        ordering = ['-datum']
        verbose_name = 'Poribljavanje'

    def __str__(self):
        return '%s — %s %s kg (%s)' % (self.revir, self.vrsta_ribe, self.kolicina_kg, self.datum)


class CuvarskaStraza(models.Model):
    """Čuvarska služba — raspored, zapisnici."""
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='cuvarske_straze')
    cuvar = models.ForeignKey(Clan, on_delete=models.CASCADE, related_name='straze')
    revir = models.ForeignKey(Revir, on_delete=models.CASCADE, related_name='straze')
    datum_od = models.DateTimeField(verbose_name='Od')
    datum_do = models.DateTimeField(verbose_name='Do')
    prekrsaji = models.PositiveSmallIntegerField(default=0, verbose_name='Broj prekršaja')
    zapisnik = models.TextField(blank=True, verbose_name='Zapisnik')
    notes = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'udruge_cuvarska_straza'
        ordering = ['-datum_od']
        verbose_name = 'Čuvarska straža'

    def __str__(self):
        return '%s — %s (%s)' % (self.cuvar, self.revir, self.datum_od.strftime('%d.%m.%Y'))


# ═══════════════════════════════════════════════════════════════════════════
# PČELARI — PČELARSKA DRUŠTVA
# Zakon o pčelarstvu (NN 63/22)
# Pravilnik o držanju pčela (NN 11/23)
# ═══════════════════════════════════════════════════════════════════════════

class Pcelinjak(models.Model):
    """Pčelinjak — lokacija s košnicama, vezan za člana-pčelara."""
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='pcelinjaci')
    vlasnik = models.ForeignKey(Clan, on_delete=models.CASCADE, related_name='pcelinjaci', verbose_name='Vlasnik (pčelar)')
    naziv = models.CharField(max_length=200, verbose_name='Naziv pčelinjaka')
    lokacija = models.CharField(max_length=255, verbose_name='Adresa / Lokacija')
    katastarska_cestica = models.CharField(max_length=50, blank=True, verbose_name='Katastarska čestica')
    geo_lat = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    geo_lon = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    jrdz_broj = models.CharField(max_length=50, blank=True, verbose_name='JRDŽ broj', db_index=True)
    stacionarni = models.BooleanField(default=True, verbose_name='Stacionarni (ne seli)')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'udruge_pcelinjak'
        ordering = ['naziv']
        verbose_name = 'Pčelinjak'

    def __str__(self):
        return '%s — %s (%s)' % (self.naziv, self.vlasnik, self.lokacija[:30])

    @property
    def broj_kosnica(self):
        return self.kosnice.filter(status='aktivna').count()


class Kosnica(models.Model):
    """Pojedinačna košnica u pčelinjaku."""
    TIP_CHOICES = [
        ('lr', 'Langstroth-Root (LR)'),
        ('db', 'Dadant-Blatt (DB)'),
        ('az', 'AŽ (Albert-Žnideršič)'),
        ('polunastavak', 'Polunastavak'),
        ('ostalo', 'Ostalo'),
    ]
    STATUS_CHOICES = [
        ('aktivna', 'Aktivna'),
        ('prazna', 'Prazna'),
        ('bolesna', 'Bolesna'),
        ('rojila', 'Rojila se'),
        ('uginula', 'Zajednica uginula'),
        ('spojena', 'Spojena'),
    ]

    pcelinjak = models.ForeignKey(Pcelinjak, on_delete=models.CASCADE, related_name='kosnice')
    oznaka = models.CharField(max_length=50, verbose_name='Oznaka košnice')
    tip = models.CharField(max_length=20, choices=TIP_CHOICES, default='lr')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='aktivna')
    godina_matice = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='Godina matice')
    boja_matice = models.CharField(max_length=20, blank=True, verbose_name='Boja matice')
    snaga_zajednice = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='Snaga zajednice (1-5)',
        help_text='1=slaba, 5=jaka')
    notes = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'udruge_kosnica'
        ordering = ['oznaka']
        unique_together = [('pcelinjak', 'oznaka')]
        verbose_name = 'Košnica'

    def __str__(self):
        return '%s/%s (%s)' % (self.pcelinjak.naziv[:20], self.oznaka, self.get_status_display())


class TretmanKosnice(models.Model):
    """Veterinarski tretman košnice — varroa, AFB, EFB, nosema."""
    TIP_CHOICES = [
        ('varroa', 'Varroa tretman'),
        ('afb', 'AFB (Američka gnjiloća)'),
        ('efb', 'EFB (Europska gnjiloća)'),
        ('nosema', 'Nosema'),
        ('pregled', 'Veterinarski pregled'),
        ('hranjenje', 'Prihranjivanje'),
        ('ostalo', 'Ostalo'),
    ]

    kosnica = models.ForeignKey(Kosnica, on_delete=models.CASCADE, related_name='tretmani')
    datum = models.DateField(verbose_name='Datum')
    tip = models.CharField(max_length=20, choices=TIP_CHOICES)
    lijek = models.CharField(max_length=100, blank=True, verbose_name='Lijek / Sredstvo')
    doza = models.CharField(max_length=50, blank=True, verbose_name='Doza / Količina')
    veterinar = models.CharField(max_length=100, blank=True)
    karencija_do = models.DateField(null=True, blank=True, verbose_name='Karencija do (zabrana vrcanja)')
    rezultat = models.CharField(max_length=200, blank=True)
    notes = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'udruge_tretman_kosnice'
        ordering = ['-datum']
        verbose_name = 'Tretman košnice'

    def __str__(self):
        return '%s — %s (%s)' % (self.kosnica, self.get_tip_display(), self.datum)


class MedProizvodnja(models.Model):
    """Evidencija proizvodnje meda — vrcanje, količina, vrsta."""
    VRSTA_CHOICES = [
        ('bagrem', 'Bagremov med'),
        ('lipa', 'Lipov med'),
        ('livada', 'Livadni med'),
        ('suncokret', 'Suncokretov med'),
        ('kesten', 'Kestenov med'),
        ('kadulja', 'Med od kadulje'),
        ('vresina', 'Vrištinov med'),
        ('medljikovac', 'Medljikovac'),
        ('mijesani', 'Miješani cvjetni'),
        ('ostalo', 'Ostalo'),
    ]

    pcelinjak = models.ForeignKey(Pcelinjak, on_delete=models.CASCADE, related_name='proizvodnja_meda')
    datum_vrcanja = models.DateField(verbose_name='Datum vrcanja')
    vrsta = models.CharField(max_length=20, choices=VRSTA_CHOICES)
    kolicina_kg = models.DecimalField(max_digits=8, decimal_places=2, verbose_name='Količina (kg)')
    vlaga_posto = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, verbose_name='Vlaga (%)')
    broj_kosnica_vrcano = models.PositiveSmallIntegerField(default=0, verbose_name='Košnica vrcano')
    za_prodaju = models.BooleanField(default=False)
    cijena_eur_kg = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, verbose_name='Cijena (EUR/kg)')
    serija = models.CharField(max_length=50, blank=True, verbose_name='Serija / Lot')
    notes = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'udruge_med_proizvodnja'
        ordering = ['-datum_vrcanja']
        verbose_name = 'Proizvodnja meda'

    def __str__(self):
        return '%s — %s %s kg (%s)' % (self.pcelinjak, self.get_vrsta_display(), self.kolicina_kg, self.datum_vrcanja)


class SelidbaLog(models.Model):
    """Selidba pčelinjaka — zakonska prijava, lokacija."""
    pcelinjak = models.ForeignKey(Pcelinjak, on_delete=models.CASCADE, related_name='selidbe')
    datum = models.DateField(verbose_name='Datum selidbe')
    odrediste = models.CharField(max_length=255, verbose_name='Odredište')
    odrediste_lat = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    odrediste_lon = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    broj_kosnica = models.PositiveSmallIntegerField(verbose_name='Broj košnica')
    razlog = models.CharField(max_length=200, blank=True, verbose_name='Razlog (paša, tretman...)')
    prijavljeno_veterinaru = models.BooleanField(default=False, verbose_name='Prijavljeno veterinaru')
    vracanje_datum = models.DateField(null=True, blank=True, verbose_name='Datum povratka')
    notes = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'udruge_selidba_log'
        ordering = ['-datum']
        verbose_name = 'Selidba pčelinjaka'

    def __str__(self):
        return '%s → %s (%s)' % (self.pcelinjak, self.odrediste[:30], self.datum)


# ═══════════════════════════════════════════════════════════════════════════
# RAKIJA / DESTILACIJA
# Zakon o trošarinama (NN 106/18, 121/19)
# EU Uredba 2019/787 — jaka alkoholna pića
# ═══════════════════════════════════════════════════════════════════════════

class DestilacijaKotao(models.Model):
    """Registar destilacijskog kotla — zakonska prijava carinskom uredu."""
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='kotlovi')
    vlasnik = models.ForeignKey(Clan, on_delete=models.SET_NULL, null=True, blank=True, related_name='kotlovi',
        verbose_name='Vlasnik (pčelar/OPG)')
    registarski_broj = models.CharField(max_length=50, verbose_name='Registarski broj (Carina)')
    volumen_litara = models.PositiveIntegerField(verbose_name='Volumen kotla (L)')
    tip = models.CharField(max_length=50, blank=True, verbose_name='Tip kotla', help_text='Bakreni, inox...')
    lokacija = models.CharField(max_length=255, verbose_name='Lokacija kotla')
    carinski_ured = models.CharField(max_length=100, blank=True, verbose_name='Nadležni carinski ured')
    registriran_od = models.DateField(null=True, blank=True, verbose_name='Registriran od')
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'udruge_destilacija_kotao'
        ordering = ['registarski_broj']
        verbose_name = 'Destilacijski kotao'

    def __str__(self):
        return 'Kotao %s (%s L) — %s' % (self.registarski_broj, self.volumen_litara, self.lokacija[:30])


class DestilacijaLog(models.Model):
    """Dnevnik destilacije — svako pečenje rakije."""
    SIROVINA_CHOICES = [
        ('sljiva', 'Šljiva'),
        ('grozdje', 'Grožđe (lozovača)'),
        ('kruska', 'Kruška (viljamovka)'),
        ('jabuka', 'Jabuka'),
        ('tresnja', 'Trešnja'),
        ('visnja', 'Višnja'),
        ('marelica', 'Marelica'),
        ('dunja', 'Dunja'),
        ('med', 'Med (medica/medovina)'),
        ('smokva', 'Smokva'),
        ('orah', 'Orah (orahovac)'),
        ('ostalo', 'Ostalo'),
    ]

    kotao = models.ForeignKey(DestilacijaKotao, on_delete=models.CASCADE, related_name='destilacije')
    datum = models.DateField(verbose_name='Datum pečenja')
    sirovina = models.CharField(max_length=20, choices=SIROVINA_CHOICES)
    kg_sirovina = models.DecimalField(max_digits=8, decimal_places=2, verbose_name='Količina sirovina (kg)')
    litara_komine = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, verbose_name='Litara komine')
    # Rezultat
    litara_destilata = models.DecimalField(max_digits=8, decimal_places=2, verbose_name='Litara destilata (ukupno)')
    alkohol_posto = models.DecimalField(max_digits=4, decimal_places=1, verbose_name='Alkohol (%)')
    litara_cistog_alkohola = models.DecimalField(max_digits=8, decimal_places=2, default=0,
        verbose_name='Litara čistog alkohola', help_text='Auto: litara × %alc / 100')
    # Frakcije
    prvijenac_l = models.DecimalField(max_digits=6, decimal_places=2, default=0, verbose_name='Prvijenac (L)')
    srce_l = models.DecimalField(max_digits=6, decimal_places=2, default=0, verbose_name='Srce (L)')
    patoka_l = models.DecimalField(max_digits=6, decimal_places=2, default=0, verbose_name='Patoka (L)')
    temperatura_c = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, verbose_name='Max temp (°C)')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'udruge_destilacija_log'
        ordering = ['-datum']
        verbose_name = 'Destilacija (pečenje)'

    def save(self, *args, **kwargs):
        self.litara_cistog_alkohola = self.litara_destilata * self.alkohol_posto / 100
        super().save(*args, **kwargs)

    def __str__(self):
        return '%s — %s %s L (%s%%)' % (self.datum, self.get_sirovina_display(), self.litara_destilata, self.alkohol_posto)


class RakijaProizvodnja(models.Model):
    """Gotov proizvod — rakija spremna za konzumaciju/prodaju."""
    destilacija = models.ForeignKey(DestilacijaLog, on_delete=models.SET_NULL, null=True, blank=True, related_name='proizvodi')
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='rakije')
    naziv = models.CharField(max_length=100, verbose_name='Naziv proizvoda')
    tip_rakije = models.CharField(max_length=50, verbose_name='Tip rakije',
        help_text='Šljivovica, Lozovača, Viljamovka, Travarica, Medica...')
    litara = models.DecimalField(max_digits=8, decimal_places=2, verbose_name='Litara')
    alkohol_posto = models.DecimalField(max_digits=4, decimal_places=1, verbose_name='Alkohol (%)')
    serija = models.CharField(max_length=50, blank=True, verbose_name='Serija / Lot')
    godina = models.PositiveSmallIntegerField(verbose_name='Godina proizvodnje')
    za_prodaju = models.BooleanField(default=False)
    cijena_eur_l = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, verbose_name='Cijena (EUR/L)')
    notes = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'udruge_rakija_proizvodnja'
        ordering = ['-godina', 'naziv']
        verbose_name = 'Rakija (proizvod)'

    def __str__(self):
        return '%s %d — %s L (%s%%)' % (self.naziv, self.godina, self.litara, self.alkohol_posto)


class TrosarinaPrijava(models.Model):
    """Godišnja trošarinska prijava — mali proizvođač do 50L čistog alkohola."""
    STATUS_CHOICES = [
        ('draft', 'Nacrt'),
        ('submitted', 'Prijavljeno'),
        ('paid', 'Plaćeno'),
    ]

    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='trosarine')
    godina = models.PositiveSmallIntegerField(verbose_name='Godina')
    ukupno_litara_destilata = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    prosjecni_alkohol_posto = models.DecimalField(max_digits=4, decimal_places=1, default=40)
    ukupno_litara_cistog = models.DecimalField(max_digits=10, decimal_places=2, default=0,
        verbose_name='Ukupno litara čistog alkohola')
    # Trošarina
    mali_proizvodac = models.BooleanField(default=True, verbose_name='Mali proizvođač (≤50L č.a.)')
    stopa_eur_hl = models.DecimalField(max_digits=10, decimal_places=2, default=0,
        verbose_name='Stopa (EUR/hL čistog alkohola)',
        help_text='Puna stopa 2024: 1.047,27 EUR/hL. Mali proiz.: 0 ili snižena.')
    iznos_trosarine = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Iznos trošarine (EUR)')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    datum_prijave = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'udruge_trosarina_prijava'
        unique_together = [('company', 'godina')]
        ordering = ['-godina']
        verbose_name = 'Trošarinska prijava'

    def save(self, *args, **kwargs):
        self.mali_proizvodac = self.ukupno_litara_cistog <= 50
        self.iznos_trosarine = self.ukupno_litara_cistog / 100 * self.stopa_eur_hl
        super().save(*args, **kwargs)

    def __str__(self):
        return 'Trošarina %d — %s L č.a. (%s EUR)' % (self.godina, self.ukupno_litara_cistog, self.iznos_trosarine)


# ═══════════════════════════════════════════════════════════════════════════
# VOĆARI — VOĆARSKA UDRUŽENJA
# Zakon o poljoprivredi (NN 118/18), Pravilnik o integriranoj (NN 137/12)
# ═══════════════════════════════════════════════════════════════════════════

class Vocnjak(models.Model):
    """Voćnjak — ARKOD čestica sa sadnim materijalom."""
    VRSTA_CHOICES = [
        ('jabuka', 'Jabuka'),
        ('kruska', 'Kruška'),
        ('sljiva', 'Šljiva'),
        ('tresnja', 'Trešnja'),
        ('visnja', 'Višnja'),
        ('breskva', 'Breskva'),
        ('marelica', 'Marelica'),
        ('orah', 'Orah'),
        ('lijeska', 'Lijeska'),
        ('smokva', 'Smokva'),
        ('maslina', 'Maslina'),
        ('vinova_loza', 'Vinova loza'),
        ('borovnica', 'Borovnica'),
        ('malina', 'Malina'),
        ('jagoda', 'Jagoda'),
        ('ostalo', 'Ostalo'),
    ]
    SUSTAV_CHOICES = [
        ('spalir', 'Špalir'),
        ('piramida', 'Piramida'),
        ('vretenast', 'Vretenast'),
        ('slobodan', 'Slobodan uzgoj'),
        ('pergola', 'Pergola'),
        ('ostalo', 'Ostalo'),
    ]

    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='vocnjaci')
    vlasnik = models.ForeignKey(Clan, on_delete=models.SET_NULL, null=True, blank=True, related_name='vocnjaci')
    field = models.ForeignKey('livestock.Field', on_delete=models.SET_NULL, null=True, blank=True, related_name='vocnjaci',
        verbose_name='ARKOD parcela')
    naziv = models.CharField(max_length=200, verbose_name='Naziv voćnjaka')
    vrsta = models.CharField(max_length=20, choices=VRSTA_CHOICES)
    sorta = models.CharField(max_length=100, blank=True, verbose_name='Sorta')
    podloga = models.CharField(max_length=100, blank=True, verbose_name='Podloga (rootstock)')
    sustav_uzgoja = models.CharField(max_length=20, choices=SUSTAV_CHOICES, default='spalir')
    broj_stabala = models.PositiveIntegerField(default=0, verbose_name='Broj stabala/sadnica')
    razmak_red_m = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, verbose_name='Razmak red (m)')
    razmak_stablo_m = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, verbose_name='Razmak stablo (m)')
    godina_sadnje = models.PositiveSmallIntegerField(null=True, blank=True)
    povrsina_ha = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, verbose_name='Površina (ha)')
    is_organic = models.BooleanField(default=False, verbose_name='Ekološki uzgoj')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'udruge_vocnjak'
        ordering = ['naziv']
        verbose_name = 'Voćnjak'

    def __str__(self):
        return '%s — %s %s (%s st.)' % (self.naziv, self.get_vrsta_display(), self.sorta, self.broj_stabala)

    @property
    def starost_godina(self):
        if not self.godina_sadnje:
            return None
        return timezone.now().year - self.godina_sadnje


class BerbaLog(models.Model):
    """Evidencija berbe voća."""
    vocnjak = models.ForeignKey(Vocnjak, on_delete=models.CASCADE, related_name='berbe')
    datum = models.DateField(verbose_name='Datum berbe')
    kolicina_kg = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Količina (kg)')
    kvaliteta = models.CharField(max_length=20, choices=[
        ('I', 'I. klasa'), ('II', 'II. klasa'), ('III', 'III. klasa / prerađevina'),
        ('ekstra', 'Ekstra klasa'),
    ], default='I')
    broj_radnika = models.PositiveSmallIntegerField(default=1)
    sati_berbe = models.DecimalField(max_digits=4, decimal_places=1, default=0, verbose_name='Sati berbe')
    za_prodaju = models.BooleanField(default=True)
    za_preradu = models.BooleanField(default=False, verbose_name='Za preradu (rakija, sok, džem)')
    cijena_eur_kg = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    notes = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'udruge_berba_log'
        ordering = ['-datum']
        verbose_name = 'Berba'

    def __str__(self):
        return '%s — %s kg (%s)' % (self.vocnjak, self.kolicina_kg, self.datum)


class TretmanVocnjaka(models.Model):
    """Tretman voćnjaka — prskanje, đubrenje (zakonska evidencija za integrirane)."""
    TIP_CHOICES = [
        ('fungicid', 'Fungicid'),
        ('insekticid', 'Insekticid'),
        ('herbicid', 'Herbicid'),
        ('gnojidba', 'Gnojidba'),
        ('rezidba', 'Rezidba'),
        ('navodnjavanje', 'Navodnjavanje'),
        ('ostalo', 'Ostalo'),
    ]

    vocnjak = models.ForeignKey(Vocnjak, on_delete=models.CASCADE, related_name='tretmani')
    datum = models.DateField(verbose_name='Datum')
    tip = models.CharField(max_length=20, choices=TIP_CHOICES)
    sredstvo = models.CharField(max_length=200, verbose_name='Sredstvo / Preparat')
    doza = models.CharField(max_length=100, blank=True, verbose_name='Doza (L/ha ili kg/ha)')
    kolicina_ukupno = models.CharField(max_length=100, blank=True, verbose_name='Ukupna količina')
    karencija_dana = models.PositiveSmallIntegerField(default=0, verbose_name='Karencija (dana)')
    karencija_do = models.DateField(null=True, blank=True, verbose_name='Karencija do')
    tretirao = models.CharField(max_length=100, blank=True, verbose_name='Tretirao (osoba)')
    vremenske_prilike = models.CharField(max_length=100, blank=True, verbose_name='Vremenske prilike')
    notes = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'udruge_tretman_vocnjaka'
        ordering = ['-datum']
        verbose_name = 'Tretman voćnjaka'

    def __str__(self):
        return '%s — %s: %s (%s)' % (self.vocnjak, self.get_tip_display(), self.sredstvo, self.datum)

    def save(self, *args, **kwargs):
        if self.karencija_dana and self.datum and not self.karencija_do:
            from datetime import timedelta
            self.karencija_do = self.datum + timedelta(days=self.karencija_dana)
        super().save(*args, **kwargs)


# ═══════════════════════════════════════════════════════════════════
# BRANITELJI — Zakon NN 121/17, 98/19, 84/21, 156/23
# ═══════════════════════════════════════════════════════════════════

class StatusBranitelja(models.Model):
    VRSTA_STATUSA = [
        ('branitelj',      'Hrvatski branitelj iz DR'),
        ('dragovoljac',    'Dragovoljac iz DR'),
        ('hrvi_1',         'HRVI — I. skupina (80-100%)'),
        ('hrvi_2',         'HRVI — II. skupina (60-79%)'),
        ('hrvi_3',         'HRVI — III. skupina (40-59%)'),
        ('hrvi_4',         'HRVI — IV. skupina (20-39%)'),
        ('civilni_invalid','Civilni invalid rata'),
        ('smrtno_stradali','Smrtno stradali (nasljednici)'),
        ('nestali',        'Nestali (obitelj)'),
    ]
    POSTROJBA_CHOICES = [
        ('HV',   'Hrvatska vojska'),
        ('MUP',  'MUP'),
        ('ZNG',  'Zbor narodne garde'),
        ('HOS',  'Hrvatske obrambene snage'),
        ('NZ',   'Narodna zaštita'),
        ('HVO',  'HVO (BiH)'),
        ('ostalo','Ostalo'),
    ]
    clan = models.OneToOneField('Clan', on_delete=models.CASCADE, related_name='status_branitelja')
    vrsta_statusa = models.CharField(max_length=20, choices=VRSTA_STATUSA, default='branitelj')
    postrojba = models.CharField(max_length=10, choices=POSTROJBA_CHOICES, blank=True)
    naziv_postrojbe = models.CharField(max_length=200, blank=True)
    od_datuma = models.DateField(null=True, blank=True, verbose_name='Sudjelovanje od')
    do_datuma = models.DateField(null=True, blank=True, verbose_name='Sudjelovanje do')
    dana_sudjelovanja = models.PositiveIntegerField(default=0)
    borbeni_sektor = models.BooleanField(default=False)
    broj_potvrde_ministarstva = models.CharField(max_length=50, blank=True)
    datum_potvrde = models.DateField(null=True, blank=True)
    postotak_invalidnosti = models.PositiveSmallIntegerField(null=True, blank=True)
    ima_njegovatelja = models.BooleanField(default=False)
    fond_udjeli = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    fond_nasljednici = models.CharField(max_length=500, blank=True)
    ostvarena_prava = models.JSONField(default=dict, blank=True)
    odlikovanja = models.TextField(blank=True)
    napomena = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'udruge_status_branitelja'
        verbose_name = 'Status branitelja'
        verbose_name_plural = 'Statusi branitelja'

    def __str__(self):
        return '%s — %s' % (self.clan, self.get_vrsta_statusa_display())

    @property
    def je_hrvi(self):
        return self.vrsta_statusa.startswith('hrvi_')


class OdlikovanjeBranitelja(models.Model):
    ODLIKOVANJE_VRSTA = [
        ('red_danice_hr', 'Red Danice Hrvatske'),
        ('domovinska_rat', 'Domovinska medalja — ratna'),
        ('domovinska_mir', 'Domovinska medalja — mirovna'),
        ('medalja_slobode', 'Medalja slobode'),
        ('ostalo', 'Ostalo odlikovanje'),
    ]
    clan = models.ForeignKey('Clan', on_delete=models.CASCADE, related_name='odlikovanja_bran')
    vrsta = models.CharField(max_length=30, choices=ODLIKOVANJE_VRSTA)
    naziv = models.CharField(max_length=200)
    datum_dodjeljivanja = models.DateField(null=True, blank=True)
    broj_odluke = models.CharField(max_length=100, blank=True)
    napomena = models.CharField(max_length=300, blank=True)

    class Meta:
        db_table = 'udruge_odlikovanje_branitelja'
        verbose_name = 'Odlikovanje'
        ordering = ['-datum_dodjeljivanja']


# ═══════════════════════════════════════════════════════════════════
# LOV — Zakon o lovstvu (NN), Pravilnik NN 48/22, SLE od 06/2025
# ═══════════════════════════════════════════════════════════════════

class Loviste(models.Model):
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='lovista')
    naziv = models.CharField(max_length=200)
    broj_lovista = models.CharField(max_length=30, blank=True)
    povrsina_ha = models.DecimalField(max_digits=10, decimal_places=2)
    vrsta = models.CharField(max_length=20, choices=[
        ('zajednicko', 'Zajedničko lovište'),
        ('privatno', 'Privatno lovište'),
        ('uzgajaliste', 'Uzgajalište divljači'),
    ], default='zajednicko')
    lovoovlastenik = models.CharField(max_length=200, blank=True)
    zakup_od = models.DateField(null=True, blank=True)
    zakup_do = models.DateField(null=True, blank=True)
    opis_granica = models.TextField(blank=True)
    napomena = models.CharField(max_length=300, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'udruge_loviste'
        verbose_name = 'Lovište'
        ordering = ['naziv']

    def __str__(self):
        return '%s (%s ha)' % (self.naziv, self.povrsina_ha)


class LovackaIskaznica(models.Model):
    KATEGORIJA_CHOICES = [
        ('hr_5god', 'HR državljanin (5 godina)'),
        ('inozemac', 'Strani državljanin (sezonska)'),
        ('pocasna', 'Počasna iskaznica'),
    ]
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='lovacke_iskaznice')
    clan = models.ForeignKey('Clan', on_delete=models.CASCADE, related_name='lovacke_iskaznice')
    broj_iskaznice = models.CharField(max_length=30)
    kategorija = models.CharField(max_length=15, choices=KATEGORIJA_CHOICES, default='hr_5god')
    datum_izdavanja = models.DateField()
    vrijedi_do = models.DateField()
    markica_godina = models.PositiveSmallIntegerField(null=True, blank=True)
    markica_datum = models.DateField(null=True, blank=True)
    uvjerenje_ispit = models.CharField(max_length=50, blank=True)
    datum_ispita = models.DateField(null=True, blank=True)
    napomena = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'udruge_lovacka_iskaznica'
        verbose_name = 'Lovačka iskaznica'
        ordering = ['-datum_izdavanja']

    def __str__(self):
        return 'Iskaznica %s — %s' % (self.broj_iskaznice, self.clan)

    @property
    def je_aktivna(self):
        from django.utils import timezone
        return self.vrijedi_do >= timezone.now().date()

    @property
    def treba_markicu(self):
        from django.utils import timezone
        today = timezone.now().date()
        lovna_god = today.year if today.month >= 4 else today.year - 1
        return self.markica_godina != lovna_god


class DopustenjeLova(models.Model):
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='dopustenja_lova')
    loviste = models.ForeignKey(Loviste, on_delete=models.PROTECT, related_name='dopustenja')
    clan = models.ForeignKey('Clan', on_delete=models.CASCADE, related_name='dopustenja_lova')
    broj_dopustenja = models.CharField(max_length=20)
    datum_lova = models.DateField()
    vrsta_divljaci = models.CharField(max_length=100)
    broj_komada = models.PositiveSmallIntegerField(default=1)
    sle_evidencija_br = models.CharField(max_length=50, blank=True)
    napomena = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'udruge_dopustenje_lova'
        verbose_name = 'Dopuštenje za lov'
        ordering = ['-datum_lova']

    def __str__(self):
        return 'Dopuštenje %s — %s' % (self.broj_dopustenja, self.vrsta_divljaci)


class ZapisnikLova(models.Model):
    NACIN_LOVA = [
        ('pojedinacni', 'Pojedinačni lov'),
        ('skupni', 'Skupni lov (hajka)'),
        ('tihacenje', 'Tihačenje'),
        ('iz_zasjede', 'Iz zasjede'),
    ]
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='zapisnici_lova')
    dopustenje = models.ForeignKey(DopustenjeLova, on_delete=models.SET_NULL, null=True, blank=True, related_name='zapisnici')
    loviste = models.ForeignKey(Loviste, on_delete=models.PROTECT, related_name='zapisnici')
    clan = models.ForeignKey('Clan', on_delete=models.CASCADE, related_name='zapisnici_lova')
    datum = models.DateField()
    nacin_lova = models.CharField(max_length=15, choices=NACIN_LOVA, default='pojedinacni')
    vrsta_divljaci = models.CharField(max_length=100)
    spol = models.CharField(max_length=10, choices=[('muz', 'Mužjak'), ('zen', 'Ženka'), ('mlado', 'Mlado')], blank=True)
    masa_kg = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    lokalitet = models.CharField(max_length=200, blank=True)
    sle_broj = models.CharField(max_length=50, blank=True)
    photo = models.ImageField(upload_to='lov/zapisnici/%Y/', blank=True)
    napomena = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'udruge_zapisnik_lova'
        verbose_name = 'Zapisnik o lovu'
        ordering = ['-datum']

    def __str__(self):
        return '%s — %s (%s)' % (self.vrsta_divljaci, self.clan, self.datum)


class Trofej(models.Model):
    VRSTA_TROFEJA = [
        ('jelen_paroske', 'Jelenje paroške'),
        ('srna_rogi', 'Srneće rogovlje'),
        ('vepar_kljove', 'Veprove kljove'),
        ('medvjed_lubanja', 'Medvjeđa lubanja'),
        ('muflon_rogi', 'Muflonovo rogovlje'),
        ('ostalo', 'Ostali trofej'),
    ]
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='trofeji')
    zapisnik = models.OneToOneField(ZapisnikLova, on_delete=models.CASCADE, related_name='trofej', null=True, blank=True)
    clan = models.ForeignKey('Clan', on_delete=models.CASCADE, related_name='trofeji')
    vrsta = models.CharField(max_length=20, choices=VRSTA_TROFEJA)
    rok_lista = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    teza_kg = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    cis_tockova = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, verbose_name='CIC točaka')
    medalja = models.CharField(max_length=10, blank=True, choices=[('zlato','Zlato'), ('srebro','Srebro'), ('bronca','Bronca')])
    datum_vrjednovanja = models.DateField(null=True, blank=True)
    photo = models.ImageField(upload_to='lov/trofeji/%Y/', blank=True)
    napomena = models.CharField(max_length=200, blank=True)

    class Meta:
        db_table = 'udruge_trofej'
        verbose_name = 'Trofej'
        ordering = ['-cis_tockova']

    def __str__(self):
        return '%s — %s' % (self.get_vrsta_display(), self.clan)
