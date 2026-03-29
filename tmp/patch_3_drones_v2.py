"""
Patch v2: 3 Drona — LOT karenca, BOM normativi, Storno+Konačni račun
═══════════════════════════════════════════════════════════════════════
Dron #1: LOT-based karenca (ne po imenu artikla nego po StockBatch→Flock)
Dron #2: BOM normativi na ExperienceInclusion (validacija + admin)
Dron #3: Predujam invoice → Storno + Konačni račun za no-show
"""
import os
BASE = '/var/www/fina-connect'


# ══════════════════════════════════════════════════════════════════════
# DRON #1: LOT-based Karenca — StockBatch.source_flock + POS LOT check
# ══════════════════════════════════════════════════════════════════════

# 1a. Dodaj source_flock FK na StockBatch
path = os.path.join(BASE, 'inventory/models.py')
with open(path) as f:
    c = f.read()

old_batch_fields = """    batch_number = models.CharField(max_length=100, blank=True, verbose_name=_('Broj sarze / LOT'))
    expected_weight = models.DecimalField("""

new_batch_fields = """    batch_number = models.CharField(max_length=100, blank=True, verbose_name=_('Broj sarze / LOT'))

    # Slijedivost — iz kojeg jata dolazi ova šarža
    source_flock = models.ForeignKey(
        'udruge.Flock', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='stock_batches',
        verbose_name=_('Izvorno jato'),
        help_text=_('LOT-level karencija: blokira samo OVU šaržu, ne sve artikle'),
    )

    expected_weight = models.DecimalField("""

c = c.replace(old_batch_fields, new_batch_fields)

with open(path, 'w') as f:
    f.write(c)
print("[OK] inventory/models.py — StockBatch.source_flock FK")


# 1b. POS add_item: karenca check na LOT/StockBatch razini (ne na artikl razini)
path = os.path.join(BASE, 'pos/views.py')
with open(path) as f:
    c = f.read()

# Zamijeni grubi InventoryItem-level karenca check s preciznim LOT-level checkom
old_karenca_block = """            # ── KARENCA HARD BLOCK ──────────────────────────────────
            # Zakon o higijeni hrane: proizvodi iz jata pod aktivnom
            # karencom (antibiotik/lijek) NE SMIJU se prodavati.
            # ────────────────────────────────────────────────────────
            if inv.source_flock_id:
                try:
                    flock = inv.source_flock
                    if flock and flock.has_active_karenca:
                        karenca_end = flock.karenca_end_date
                        end_str = karenca_end.strftime('%d.%m.%Y') if karenca_end else '?'
                        messages.error(
                            request,
                            f'ZABRANJENO: Jato "{flock.naziv}" je pod aktivnom karencom '
                            f'(zdravstveni tretman). Prodaja proizvoda iz ovog jata '
                            f'nije dozvoljena do {end_str}. '
                            f'Zakon o higijeni hrane — prekršaj može rezultirati '
                            f'zatvaranjem objekta.'
                        )
                        return redirect('pos:receipt_detail', receipt_id=receipt_id)
                except Exception:
                    pass  # Flock deleted ili FK broken — ne blokiraj POS"""

new_karenca_block = """            # ── KARENCA HARD BLOCK (LOT-level preciznost) ───────────
            # Zakon o higijeni hrane: proizvodi iz jata pod aktivnom
            # karencom (antibiotik/lijek) NE SMIJU se prodavati.
            # Blokada ide po StockBatch (LOT), NE po cijelom artiklu.
            # Jato A pod karencom ≠ blokada jaja iz Jata B.
            # ────────────────────────────────────────────────────────
            batch_id = request.POST.get('stock_batch_id', '').strip()
            karenca_blocked = False

            # Provjera 1: Ako je odabran specifični LOT/batch
            if batch_id:
                try:
                    from inventory.models import StockBatch
                    batch = StockBatch.objects.select_related('source_flock').get(pk=int(batch_id))
                    if batch.source_flock and batch.source_flock.has_active_karenca:
                        flock = batch.source_flock
                        karenca_end = flock.karenca_end_date
                        end_str = karenca_end.strftime('%d.%m.%Y') if karenca_end else '?'
                        messages.error(
                            request,
                            f'ZABRANJENO: LOT {batch.batch_number} dolazi iz jata '
                            f'"{flock.naziv}" koje je pod aktivnom karencom do {end_str}. '
                            f'Odaberite LOT iz drugog jata ili pričekajte istek karence. '
                            f'(Zakon o higijeni hrane)'
                        )
                        karenca_blocked = True
                except Exception:
                    pass

            # Provjera 2: Fallback na InventoryItem.source_flock (ako nema LOT sustava)
            if not karenca_blocked and not batch_id and inv.source_flock_id:
                try:
                    flock = inv.source_flock
                    if flock and flock.has_active_karenca:
                        karenca_end = flock.karenca_end_date
                        end_str = karenca_end.strftime('%d.%m.%Y') if karenca_end else '?'
                        # Provjeri ima li DRUGIH LOT-ova koji NISU pod karencom
                        from inventory.models import StockBatch
                        safe_lots = StockBatch.objects.filter(
                            item=inv, quarantine_status='active', quantity__gt=0
                        ).exclude(
                            source_flock__in=flock.__class__.objects.filter(
                                pk=flock.pk
                            )
                        )
                        if safe_lots.exists():
                            lot_names = ', '.join(safe_lots.values_list('batch_number', flat=True)[:5])
                            messages.warning(
                                request,
                                f'UPOZORENJE: Jato "{flock.naziv}" pod karencom do {end_str}. '
                                f'Ali postoje LOT-ovi iz drugih jata: {lot_names}. '
                                f'Odaberite ispravan LOT pri prodaji.'
                            )
                        else:
                            messages.error(
                                request,
                                f'ZABRANJENO: Svi LOT-ovi artikla "{inv.name}" dolaze iz '
                                f'jata pod karencom (do {end_str}). Prodaja nije dozvoljena.'
                            )
                            karenca_blocked = True
                except Exception:
                    pass

            if karenca_blocked:
                return redirect('pos:receipt_detail', receipt_id=receipt_id)"""

c = c.replace(old_karenca_block, new_karenca_block)

with open(path, 'w') as f:
    f.write(c)
print("[OK] pos/views.py — LOT-level karenca check (precizno po šarži)")


# 1c. Ukloni grubi auto-link po imenu iz bridge_publish
path = os.path.join(BASE, 'udruge/views.py')
with open(path) as f:
    c = f.read()

old_autolink = """            # Auto-link source_flock na InventoryItem-e iste kompanije
            if source_model == 'EggRecord':
                try:
                    from .models import EggRecord as ER
                    from inventory.models import InventoryItem
                    egg = ER.objects.select_related('flock').get(pk=int(source_id))
                    flock = egg.flock
                    # Nađi sve jajčane artikle bez source_flock u istoj firmi
                    egg_items = InventoryItem.objects.filter(
                        company=company,
                        source_flock__isnull=True,
                        name__icontains='jaj',
                    )
                    linked = egg_items.update(source_flock=flock)
                    if linked:
                        messages.info(
                            request,
                            f'Auto-link: {linked} artikl(a) povezano s jatom "{flock.naziv}" '
                            f'za karencija enforcement na POS-u.'
                        )
                except Exception:
                    pass"""

new_autolink = """            # Auto-link: kreira/ažurira StockBatch s source_flock za LOT slijedivost
            if source_model == 'EggRecord':
                try:
                    from .models import EggRecord as ER
                    from inventory.models import InventoryItem, StockBatch
                    egg = ER.objects.select_related('flock').get(pk=int(source_id))
                    flock = egg.flock
                    # Nađi InventoryItem za jaja u istoj firmi (source_flock linked)
                    egg_items = InventoryItem.objects.filter(
                        company=company, source_flock=flock
                    )
                    for item in egg_items:
                        lot_num = f'FLOCK-{flock.pk}-{egg.datum.strftime("%y%m%d")}'
                        batch, created = StockBatch.objects.update_or_create(
                            company=company,
                            item=item,
                            batch_number=lot_num,
                            defaults={
                                'source_flock': flock,
                                'quantity': egg.broj_jaja - egg.broken,
                                'expiry_date': egg.datum + __import__('datetime').timedelta(days=28),
                            }
                        )
                        if created:
                            messages.info(
                                request,
                                f'LOT {lot_num} kreiran za "{item.name}" — '
                                f'{batch.quantity} kom, rok: {batch.expiry_date:%d.%m.%Y}.'
                            )
                except Exception:
                    pass"""

c = c.replace(old_autolink, new_autolink)

with open(path, 'w') as f:
    f.write(c)
print("[OK] udruge/views.py — bridge_publish: LOT-based auto-link (ne po imenu)")


# ══════════════════════════════════════════════════════════════════════
# DRON #2: BOM Normativi — validacija + admin + normativ_preview
# ══════════════════════════════════════════════════════════════════════

# 2a. ExperienceInclusion: validacija + helper
path = os.path.join(BASE, 'experiences/models.py')
with open(path) as f:
    c = f.read()

old_inclusion = """class ExperienceInclusion(models.Model):
    \"\"\"Što je uključeno u cijenu iskustva — linkovi na inventory.\"\"\"
    experience = models.ForeignKey(Experience, on_delete=models.CASCADE, related_name='inclusions')
    inventory_item = models.ForeignKey(
        'inventory.InventoryItem', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='experience_inclusions',
        verbose_name=_('Artikl iz skladišta')
    )
    description = models.CharField(max_length=200, verbose_name=_('Opis'),
                                    help_text=_('npr. \"1 boca Šljivovice 0.5L\"'))
    quantity_per_person = models.DecimalField(max_digits=8, decimal_places=2, default=1,
                                              verbose_name=_('Količina po osobi'))
    unit = models.CharField(max_length=20, default='kom', verbose_name=_('Jedinica'))

    class Meta:
        verbose_name = _('Uključeno u iskustvo')
        verbose_name_plural = _('Uključeno u iskustva')

    def __str__(self):
        return f'{self.experience.name}: {self.description}'"""

new_inclusion = """class ExperienceInclusion(models.Model):
    \"\"\"
    BOM (Bill of Materials / Normativ) za iskustvo.
    Definira TOČNU količinu svake sirovine po osobi.
    SplitAllocation koristi ove podatke za kirurško skidanje zaliha.
    
    Primjer: Degustacija sira i vina
    - Sir Paški: 0.05 kg/os
    - Vino Malvazija 0.5L: 0.2 L/os  
    - Jaja domaća: 1 kom/os
    - Kruh domaći: 0.1 kg/os
    \"\"\"
    experience = models.ForeignKey(Experience, on_delete=models.CASCADE, related_name='inclusions')
    inventory_item = models.ForeignKey(
        'inventory.InventoryItem', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='experience_inclusions',
        verbose_name=_('Artikl iz skladišta'),
        help_text=_('OBAVEZNO za auto-allocation pri check-inu'),
    )
    description = models.CharField(max_length=200, verbose_name=_('Opis'),
                                    help_text=_('npr. \"Sir Paški 50g\" — opis na računu'))
    quantity_per_person = models.DecimalField(
        max_digits=8, decimal_places=4, default=1,
        verbose_name=_('Normativ po osobi'),
        help_text=_('Točna količina po 1 osobi u jedinicama artikla (kg, L, kom...)'),
    )
    unit = models.CharField(max_length=20, default='kom', verbose_name=_('Jedinica'),
                             help_text=_('MORA odgovarati jedinici artikla u inventaru'))

    class Meta:
        verbose_name = _('Normativ (BOM stavka)')
        verbose_name_plural = _('Normativi (BOM)')

    def __str__(self):
        return f'{self.experience.name}: {self.description} ({self.quantity_per_person} {self.unit}/os)'

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.inventory_item and self.quantity_per_person <= 0:
            raise ValidationError({
                'quantity_per_person': 'Normativ mora biti > 0 ako je artikl povezan.'
            })
        if self.inventory_item and self.unit != self.inventory_item.unit:
            raise ValidationError({
                'unit': f'Jedinica "{self.unit}" ne odgovara artiklu '
                        f'"{self.inventory_item.name}" ({self.inventory_item.unit}). '
                        f'Uskladite jedinice za točnu alokaciju.'
            })

    def total_for_pax(self, pax_count):
        \"\"\"Ukupna količina za zadani broj gostiju.\"\"\"
        return self.quantity_per_person * pax_count

    def stock_sufficient(self, pax_count):
        \"\"\"Ima li dovoljno zalihe za zadani broj gostiju?\"\"\"
        if not self.inventory_item:
            return True
        needed = self.total_for_pax(pax_count)
        return self.inventory_item.quantity >= needed

    def stock_deficit(self, pax_count):
        \"\"\"Koliko fali? Negativan broj = manjak.\"\"\"
        if not self.inventory_item:
            return Decimal('0')
        needed = self.total_for_pax(pax_count)
        return self.inventory_item.quantity - needed"""

c = c.replace(old_inclusion, new_inclusion)

with open(path, 'w') as f:
    f.write(c)
print("[OK] experiences/models.py — ExperienceInclusion = BOM s validacijom")


# 2b. Experiences admin: InlineAdmin za normative s preview
path = os.path.join(BASE, 'experiences/admin.py')
with open(path) as f:
    c = f.read()

if 'ExperienceInclusionInline' not in c:
    # Dodaj inline i registriraj na Experience admin
    # Nađi import statement
    if 'from .models import' in c:
        old_import = c.split('from .models import')[0] + 'from .models import'
        models_line_end = c[len(old_import):].split('\n')[0]
        old_full_import = old_import + models_line_end
        new_full_import = old_full_import.rstrip().rstrip(')') 
        if 'ExperienceInclusion' not in new_full_import:
            new_full_import += ', ExperienceInclusion)'
            if not new_full_import.endswith(')'):
                new_full_import += ')'
            c = c.replace(old_full_import, new_full_import)
    
    # Dodaj inline definiciju prije ExperienceBookingAdmin
    inline_code = """

class ExperienceInclusionInline(admin.TabularInline):
    model = ExperienceInclusion
    extra = 1
    fields = ('inventory_item', 'description', 'quantity_per_person', 'unit')


"""
    if '@admin.register(ExperienceBooking)' in c:
        c = c.replace('@admin.register(ExperienceBooking)', 
                       inline_code + '@admin.register(ExperienceBooking)')
    else:
        c += inline_code

    # Registriraj ExperienceAdmin s inlineom ako ne postoji
    if 'ExperienceAdmin' not in c:
        c += """
from .models import Experience

@admin.register(Experience)
class ExperienceAdmin(admin.ModelAdmin):
    list_display = ('name', 'company', 'price_per_person', 'capacity', 'deposit_pct')
    inlines = [ExperienceInclusionInline]
    search_fields = ('name',)
    list_filter = ('company',)
"""

with open(path, 'w') as f:
    f.write(c)
print("[OK] experiences/admin.py — BOM inline na Experience admin")


# 2c. Normativ preview view (API endpoint za frontend)
path = os.path.join(BASE, 'experiences/views.py')
with open(path) as f:
    c = f.read()

if 'normativ_preview' not in c:
    # Dodaj na kraj
    normativ_view = """

@login_required
def normativ_preview(request, pk):
    \"\"\"
    GET /experiences/<pk>/normativ/?pax=10
    Vraća JSON s normativom za zadani broj gostiju + stock status.
    \"\"\"
    from .models import Experience, ExperienceInclusion
    from django.http import JsonResponse

    exp = get_object_or_404(Experience, pk=pk)
    pax = int(request.GET.get('pax', 1))

    items = []
    total_cost = 0
    all_sufficient = True

    for incl in exp.inclusions.select_related('inventory_item').all():
        needed = float(incl.total_for_pax(pax))
        available = float(incl.inventory_item.quantity) if incl.inventory_item else None
        sufficient = incl.stock_sufficient(pax)
        deficit = float(incl.stock_deficit(pax)) if incl.inventory_item else 0

        if not sufficient:
            all_sufficient = False

        cost = 0
        if incl.inventory_item and incl.inventory_item.purchase_price:
            cost = float(incl.inventory_item.purchase_price) * needed

        items.append({
            'description': incl.description,
            'per_person': float(incl.quantity_per_person),
            'unit': incl.unit,
            'total_needed': needed,
            'available': available,
            'sufficient': sufficient,
            'deficit': deficit,
            'cost': round(cost, 2),
        })
        total_cost += cost

    return JsonResponse({
        'experience': exp.name,
        'pax': pax,
        'items': items,
        'all_sufficient': all_sufficient,
        'total_material_cost': round(total_cost, 2),
    })
"""
    c += normativ_view

with open(path, 'w') as f:
    f.write(c)
print("[OK] experiences/views.py — normativ_preview API endpoint")


# 2d. URL za normativ preview
path = os.path.join(BASE, 'experiences/urls.py')
with open(path) as f:
    c = f.read()

if 'normativ' not in c:
    old_edit = "    path('<int:pk>/edit/', views.experience_edit, name='experience_edit'),"
    new_edit = """    path('<int:pk>/edit/', views.experience_edit, name='experience_edit'),
    path('<int:pk>/normativ/', views.normativ_preview, name='normativ_preview'),"""
    c = c.replace(old_edit, new_edit)

with open(path, 'w') as f:
    f.write(c)
print("[OK] experiences/urls.py — /normativ/ endpoint")


# ══════════════════════════════════════════════════════════════════════
# DRON #3: Predujam → Storno + Konačni račun
# ══════════════════════════════════════════════════════════════════════

path = os.path.join(BASE, 'experiences/models.py')
with open(path) as f:
    c = f.read()

# 3a. Dodaj deposit_invoice FK (račun za predujam pri potvrdi depozita)
if 'deposit_invoice' not in c:
    old_forfeited_fk = """    forfeited_invoice = models.ForeignKey(
        'invoicing.Invoice', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='forfeited_bookings',
        verbose_name=_('Račun za zadržani depozit'),
    )"""

    new_forfeited_fk = """    deposit_invoice = models.ForeignKey(
        'invoicing.Invoice', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='deposit_bookings',
        verbose_name=_('Avansni račun (predujam)'),
        help_text=_('Izdaje se pri potvrdi depozita — čl.79 ZPDV'),
    )
    forfeited_invoice = models.ForeignKey(
        'invoicing.Invoice', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='forfeited_bookings',
        verbose_name=_('Konačni račun (no-show)'),
        help_text=_('Izdaje se nakon storna predujma — naknada za otkazivanje'),
    )"""

    c = c.replace(old_forfeited_fk, new_forfeited_fk)


# 3b. confirm_deposit: izdaje Avansni račun
old_confirm = """    def confirm_deposit(self, method='card'):
        \"\"\"Potvrdi uplatu depozita.\"\"\"
        self.deposit_paid = True
        self.deposit_paid_at = timezone.now()
        self.payment_method = method
        self.status = 'confirmed'
        self.save()
        # Ažuriraj schedule
        sched = self.schedule
        sched.booked_pax += self.pax_count
        if sched.booked_pax >= sched.max_pax:
            sched.status = 'full'
        sched.save(update_fields=['booked_pax', 'status'])"""

new_confirm = """    def confirm_deposit(self, method='card'):
        \"\"\"
        Potvrdi uplatu depozita.
        Izdaje Avansni račun (doctype='A') — čl.79 ZPDV.
        \"\"\"
        self.deposit_paid = True
        self.deposit_paid_at = timezone.now()
        self.payment_method = method
        self.status = 'confirmed'
        self.save()

        # Ažuriraj schedule
        sched = self.schedule
        sched.booked_pax += self.pax_count
        if sched.booked_pax >= sched.max_pax:
            sched.status = 'full'
        sched.save(update_fields=['booked_pax', 'status'])

        # Izdaj Avansni račun za depozit (čl.79 ZPDV)
        self._generate_deposit_invoice()

    def _generate_deposit_invoice(self):
        \"\"\"Avansni račun za primljeni predujam.\"\"\"
        import logging
        logger = logging.getLogger('experiences.deposit')
        try:
            from invoicing.services.invoice_service import create_invoice
            from invoicing.models import InvoiceItem

            experience = self.schedule.experience
            company = experience.company

            invoice = create_invoice(
                company=company,
                doctype='A',  # Avansni račun
                client_name=self.guest_name,
                client_email=self.guest_email or '',
                client_phone=self.guest_phone or '',
                notes=(
                    f'Avansni račun — depozit za "{experience.name}" '
                    f'({self.schedule.date} {self.schedule.time_slot}). '
                    f'Rezervacija #{self.pk}, gostiju: {self.pax_count}.'
                ),
            )

            InvoiceItem.objects.create(
                invoice=invoice,
                description=f'Predujam: {experience.name} — {self.guest_name} ({self.pax_count} os.)',
                quantity=1,
                unit_price=self.deposit_amount,
                tax_rate=Decimal('25.00'),
            )

            self.deposit_invoice = invoice
            self.save(update_fields=['deposit_invoice'])

            logger.info(
                'Deposit invoice A-%s kreiran za booking #%d — %s EUR',
                invoice.number or invoice.pk, self.pk, self.deposit_amount,
            )
        except Exception as e:
            logger.error('Deposit invoice FAILED za booking #%d: %s', self.pk, e)"""

c = c.replace(old_confirm, new_confirm)


# 3c. mark_no_show: Storno predujma + Konačni račun za naknadu
old_noshow = """    def mark_no_show(self):
        \"\"\"
        Gost se nije pojavio — depozit se zadržava.
        Ako postoji plaćeni depozit, generira račun za zadržani predujam
        (zakonska obveza — neopravdan priljev na žiro-računu).
        \"\"\"
        self.status = 'no_show'
        self.deposit_forfeited = True
        self.refund_amount = Decimal('0')
        self.save(update_fields=['status', 'deposit_forfeited', 'refund_amount'])

        # Generiraj račun za zadržani depozit ako je uplata postojala
        if self.deposit_paid and self.deposit_amount and self.deposit_amount > 0:
            self._generate_forfeited_deposit_invoice()

    def _generate_forfeited_deposit_invoice(self):
        \"\"\"
        Generira račun za zadržani predujam (no-show).
        Zakonska podloga: čl. 78. Zakona o PDV-u — zadržani predujam
        je oporezivi događaj koji zahtijeva izdavanje računa.
        \"\"\"
        import logging
        logger = logging.getLogger('experiences.no_show')
        try:
            from invoicing.services.invoice_service import create_invoice
            from invoicing.models import InvoiceItem

            experience = self.schedule.experience
            company = experience.company

            invoice = create_invoice(
                company=company,
                doctype='INVOICE',
                client_name=self.guest_name,
                client_email=self.guest_email or '',
                client_phone=self.guest_phone or '',
                notes=(
                    f'Zadržani predujam — no-show za "{experience.name}" '
                    f'({self.schedule.date} {self.schedule.time_slot}). '
                    f'Rezervacija #{self.pk}, gostiju: {self.pax_count}.'
                ),
            )

            InvoiceItem.objects.create(
                invoice=invoice,
                description=f'Zadržani predujam: {experience.name} — no-show {self.guest_name}',
                quantity=1,
                unit_price=self.deposit_amount,
                tax_rate=Decimal('25.00'),
            )

            # Spremi referencu na račun
            self.forfeited_invoice = invoice
            self.save(update_fields=['forfeited_invoice'])

            logger.info(
                'No-show invoice #%s kreiran za booking #%d — %s EUR',
                invoice.number or invoice.pk, self.pk, self.deposit_amount,
            )
        except Exception as e:
            logger.error(
                'No-show invoice FAILED za booking #%d: %s — '
                'UPOZORENJE: zadržani depozit %s EUR nema računovodstveni dokument!',
                self.pk, e, self.deposit_amount,
            )"""

new_noshow = """    def mark_no_show(self):
        \"\"\"
        Gost se nije pojavio — depozit se zadržava.
        Zakonski ispravan tok (čl.79 ZPDV):
          1. Storniraj Avansni račun (predujam)
          2. Izdaj Konačni račun za "Naknadu za nedolazak" 
        Ovo sprečava dvostruko oporezivanje istog iznosa.
        \"\"\"
        self.status = 'no_show'
        self.deposit_forfeited = True
        self.refund_amount = Decimal('0')
        self.save(update_fields=['status', 'deposit_forfeited', 'refund_amount'])

        # Zakonski tok: storno predujma + konačni račun
        if self.deposit_paid and self.deposit_amount and self.deposit_amount > 0:
            self._storno_and_final_invoice()

    def _storno_and_final_invoice(self):
        \"\"\"
        Zakonski ispravan no-show flow:
        1. Storno Avansnog računa (poništava PDV obvezu iz predujma)
        2. Konačni račun s stavkom "Naknada za otkazivanje / zadržani predujam"
           (novi oporezivi događaj — čl.33 ZPDV, čl.78 ZPDV)
        \"\"\"
        import logging
        logger = logging.getLogger('experiences.no_show')

        experience = self.schedule.experience
        company = experience.company

        # KORAK 1: Storno avansnog računa
        storno_result = None
        if self.deposit_invoice_id:
            try:
                from invoicing.services.storno import create_storno
                storno_result = create_storno(
                    original=self.deposit_invoice,
                    cancel_reason=(
                        f'No-show: {self.guest_name} se nije pojavio na '
                        f'"{experience.name}" ({self.schedule.date}). '
                        f'Depozit zadržan — storno predujma, slijedi konačni račun.'
                    ),
                )
                if storno_result.get('success'):
                    logger.info(
                        'Storno predujma %s kreiran za booking #%d',
                        storno_result['storno_invoice'].number, self.pk,
                    )
                else:
                    logger.warning(
                        'Storno predujma FAILED za booking #%d: %s',
                        self.pk, storno_result.get('message', ''),
                    )
            except Exception as e:
                logger.error('Storno predujma ERROR za booking #%d: %s', self.pk, e)
        else:
            logger.warning(
                'Booking #%d nema deposit_invoice — predujam nije bio fiskaliziran. '
                'Generira se samo konačni račun.',
                self.pk,
            )

        # KORAK 2: Konačni račun za naknadu nedolaska
        try:
            from invoicing.services.invoice_service import create_invoice
            from invoicing.models import InvoiceItem

            storno_ref = ''
            if storno_result and storno_result.get('success'):
                storno_ref = f' Storno predujma: {storno_result["storno_invoice"].number}.'

            invoice = create_invoice(
                company=company,
                doctype='R',  # Redovni račun (ne avansni!)
                client_name=self.guest_name,
                client_email=self.guest_email or '',
                client_phone=self.guest_phone or '',
                notes=(
                    f'Naknada za nedolazak (no-show) — "{experience.name}" '
                    f'({self.schedule.date}).{storno_ref} '
                    f'Rezervacija #{self.pk}.'
                ),
            )

            InvoiceItem.objects.create(
                invoice=invoice,
                description=(
                    f'Naknada za nedolazak: {experience.name} — '
                    f'{self.guest_name} ({self.pax_count} os.)'
                ),
                quantity=1,
                unit_price=self.deposit_amount,
                tax_rate=Decimal('25.00'),
            )

            self.forfeited_invoice = invoice
            self.save(update_fields=['forfeited_invoice'])

            logger.info(
                'Konačni no-show račun %s kreiran za booking #%d — %s EUR',
                invoice.number or invoice.pk, self.pk, self.deposit_amount,
            )
        except Exception as e:
            logger.error(
                'Konačni no-show račun FAILED za booking #%d: %s — '
                'KRITIČNO: depozit %s EUR bez dokumenta!',
                self.pk, e, self.deposit_amount,
            )"""

c = c.replace(old_noshow, new_noshow)

with open(path, 'w') as f:
    f.write(c)
print("[OK] experiences/models.py — Storno predujma + Konačni račun za no-show")


# ══════════════════════════════════════════════════════════════════════
# MIGRACIJE
# ══════════════════════════════════════════════════════════════════════

# StockBatch.source_flock
mig = '''from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0022_source_flock'),
        ('udruge', '0013_flock_modul'),
    ]

    operations = [
        migrations.AddField(
            model_name='stockbatch',
            name='source_flock',
            field=models.ForeignKey(
                blank=True, null=True,
                help_text='LOT-level karencija: blokira samo OVU šaržu, ne sve artikle',
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='stock_batches',
                to='udruge.flock',
                verbose_name='Izvorno jato',
            ),
        ),
    ]
'''

with open(os.path.join(BASE, 'inventory/migrations/0023_stockbatch_source_flock.py'), 'w') as f:
    f.write(mig)
print("[OK] inventory/migrations/0023_stockbatch_source_flock.py")


# ExperienceBooking.deposit_invoice + quantity_per_person decimal_places change
# Check invoicing migration dependencies
inv_migs = sorted([m for m in os.listdir(os.path.join(BASE, 'invoicing/migrations'))
                   if m.endswith('.py') and m != '__init__.py'])
last_inv = inv_migs[-1].replace('.py', '') if inv_migs else '0001_initial'

mig2 = f'''from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('experiences', '0002_forfeited_invoice'),
        ('invoicing', '{last_inv}'),
    ]

    operations = [
        migrations.AddField(
            model_name='experiencebooking',
            name='deposit_invoice',
            field=models.ForeignKey(
                blank=True, null=True,
                help_text='Izdaje se pri potvrdi depozita — čl.79 ZPDV',
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='deposit_bookings',
                to='invoicing.invoice',
                verbose_name='Avansni račun (predujam)',
            ),
        ),
        migrations.AlterField(
            model_name='experienceinclusion',
            name='quantity_per_person',
            field=models.DecimalField(
                decimal_places=4, default=1, max_digits=8,
                help_text='Točna količina po 1 osobi u jedinicama artikla (kg, L, kom...)',
                verbose_name='Normativ po osobi',
            ),
        ),
    ]
'''

with open(os.path.join(BASE, 'experiences/migrations/0003_deposit_invoice_bom.py'), 'w') as f:
    f.write(mig2)
print("[OK] experiences/migrations/0003_deposit_invoice_bom.py")


print("\n════════════════════════════════════════════")
print("SVA 3 DRONA v2 PATCHANA.")
print("  Dron #1: LOT-based karenca (StockBatch.source_flock)")  
print("  Dron #2: BOM normativi (validation + admin inline)")
print("  Dron #3: Storno predujma + Konačni račun")
print("════════════════════════════════════════════")
