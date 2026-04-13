"""
Patch: 3 Drona — SplitAllocation, No-Show Accounting, Karenca POS Block
────────────────────────────────────────────────────────────────────────
Dron #1: SplitAllocation → auto StockMovement (interna izdatnica)
Dron #2: No-Show → auto Invoice za zadržani depozit
Dron #3: Karenca → POS Hard Block + source_flock FK na InventoryItem
"""
import os
BASE = '/var/www/fina-connect'

# ══════════════════════════════════════════════════════════════════════
# DRON #1: StockMovement 'internal_use' tip + SplitAllocation service
# ══════════════════════════════════════════════════════════════════════

# 1a. Dodaj 'internal_use' u StockMovement.TYPE_CHOICES
path = os.path.join(BASE, 'inventory/models.py')
with open(path) as f:
    content = f.read()

old_types = """    TYPE_CHOICES = [
        ('in',          _('Ulaz (nabava)')),
        ('out',         _('Izlaz (prodaja/upotreba)')),
        ('adjustment',  _('Korekcija zalihe')),
        ('transfer',    _('Prijenos na drugu lokaciju')),
        ('return',      _('Povrat dobavljaču')),
        ('donation_in', _('Ulaz (materijalna donacija)')),
        ('writeoff',    _('Otpis / Kalo')),
    ]"""

new_types = """    TYPE_CHOICES = [
        ('in',           _('Ulaz (nabava)')),
        ('out',          _('Izlaz (prodaja/upotreba)')),
        ('internal_use', _('Interna upotreba (repromaterijal)')),
        ('adjustment',   _('Korekcija zalihe')),
        ('transfer',     _('Prijenos na drugu lokaciju')),
        ('return',       _('Povrat dobavljaču')),
        ('donation_in',  _('Ulaz (materijalna donacija)')),
        ('writeoff',     _('Otpis / Kalo')),
    ]"""

content = content.replace(old_types, new_types)

# 1b. internal_use skida zalihu kao i 'out'
old_save = """        elif self.movement_type in ('out', 'return'):"""
new_save = """        elif self.movement_type in ('out', 'internal_use', 'return'):"""
content = content.replace(old_save, new_save)

# 1c. Dodaj source_flock FK na InventoryItem (Dron #3 priprema)
old_livestock = """    livestock_animal = models.ForeignKey(
        'livestock.Livestock', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='products',
        verbose_name='Vezano grlo',
        help_text='Za pracenje karencije — blokira prodaju ako grlo u karenciji',
    )"""

new_livestock = """    livestock_animal = models.ForeignKey(
        'livestock.Livestock', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='products',
        verbose_name='Vezano grlo',
        help_text='Za pracenje karencije — blokira prodaju ako grlo u karenciji',
    )

    # Flock link — za jaja/perad iz udruge modula
    source_flock = models.ForeignKey(
        'udruge.Flock', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='inventory_products',
        verbose_name=_('Izvorno jato'),
        help_text=_('Za karencija enforcement — blokira POS prodaju dok je jato pod lijekovima'),
    )"""

content = content.replace(old_livestock, new_livestock)

with open(path, 'w') as f:
    f.write(content)
print("[OK] inventory/models.py — internal_use tip + source_flock FK")


# 1d. Kreiraj SplitAllocation servis
svc_path = os.path.join(BASE, 'inventory/services')
os.makedirs(svc_path, exist_ok=True)

# Provjeri __init__.py
init_path = os.path.join(svc_path, '__init__.py')
if not os.path.exists(init_path):
    with open(init_path, 'w') as f:
        f.write('')

split_svc = '''"""
SplitAllocation Service — generira internu izdatnicu pri prebacivanju
robe iz "za prodaju" u "internu upotrebu" (repromaterijal).

Zakonska podloga: svaki prebacaj mora imati StockMovement dokument
da bi porezna inspekcija mogla pratiti tok robe.
"""
import logging
from decimal import Decimal
from django.utils import timezone

logger = logging.getLogger('inventory.split_allocation')


def allocate_to_inhouse(item, qty, reason='', user=None):
    """
    Prebaci qty s unreserved na reserved_inhouse.
    Generira StockMovement(internal_use) kao internu izdatnicu.
    
    Returns: StockMovement instance
    Raises: ValueError ako nema dovoljno unreserved zalihe
    """
    from inventory.models import StockMovement

    if qty <= 0:
        raise ValueError('Količina mora biti pozitivna.')

    available = item.unreserved_qty
    if qty > available:
        raise ValueError(
            f'Nedovoljna slobodna zaliha: traženo {qty}, dostupno {available}. '
            f'Ukupno: {item.quantity}, in-house: {item.reserved_inhouse}, '
            f'marketplace: {item.reserved_marketplace}.'
        )

    # 1. Kreiraj StockMovement kao internu izdatnicu
    movement = StockMovement.objects.create(
        item=item,
        movement_type='internal_use',
        quantity=qty,
        unit_price=item.unit_price or Decimal('0'),
        reason=reason or f'SplitAllocation: prebačeno u internu upotrebu (repromaterijal)',
        performed_by=user,
    )

    # 2. Ažuriraj reserved_inhouse (quantity se već smanjio kroz StockMovement.save)
    item.refresh_from_db()
    item.reserved_inhouse += qty
    item.save(update_fields=['reserved_inhouse'])

    logger.info(
        'SplitAllocation: %s — %s kom prebačeno u internu upotrebu. '
        'Izdatnica #%d. Preostala zaliha: %s',
        item.name, qty, movement.pk, item.quantity
    )

    return movement


def release_from_inhouse(item, qty, reason='', user=None):
    """
    Vrati qty iz reserved_inhouse natrag u unreserved.
    Generira StockMovement(in) kao korekciju.
    """
    from inventory.models import StockMovement

    if qty <= 0:
        raise ValueError('Količina mora biti pozitivna.')
    if qty > item.reserved_inhouse:
        raise ValueError(
            f'Ne može se osloboditi {qty} — samo {item.reserved_inhouse} rezervirano in-house.'
        )

    movement = StockMovement.objects.create(
        item=item,
        movement_type='in',
        quantity=qty,
        unit_price=item.unit_price or Decimal('0'),
        reason=reason or f'SplitAllocation: povrat iz interne upotrebe u slobodnu zalihu',
        performed_by=user,
    )

    item.refresh_from_db()
    item.reserved_inhouse = max(Decimal('0'), item.reserved_inhouse - qty)
    item.save(update_fields=['reserved_inhouse'])

    logger.info(
        'SplitAllocation release: %s — %s kom vraćeno. Preostala zaliha: %s',
        item.name, qty, item.quantity
    )

    return movement
'''

with open(os.path.join(svc_path, 'split_allocation.py'), 'w') as f:
    f.write(split_svc)
print("[OK] inventory/services/split_allocation.py — servis kreiran")


# ══════════════════════════════════════════════════════════════════════
# DRON #2: No-Show → auto Invoice za zadržani depozit
# ══════════════════════════════════════════════════════════════════════

path = os.path.join(BASE, 'experiences/models.py')
with open(path) as f:
    content = f.read()

old_no_show = """    def mark_no_show(self):
        \"\"\"Gost se nije pojavio — depozit se zadržava.\"\"\"
        self.status = 'no_show'
        self.deposit_forfeited = True
        self.refund_amount = Decimal('0')
        self.save(update_fields=['status', 'deposit_forfeited', 'refund_amount'])"""

new_no_show = """    def mark_no_show(self):
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

content = content.replace(old_no_show, new_no_show)

# Dodaj forfeited_invoice FK ako ne postoji
if 'forfeited_invoice' not in content:
    old_deposit_forfeited = "    deposit_forfeited = models.BooleanField(default=False, verbose_name=_('Depozit zadržan (no-show)'))"
    new_deposit_forfeited = """    deposit_forfeited = models.BooleanField(default=False, verbose_name=_('Depozit zadržan (no-show)'))
    forfeited_invoice = models.ForeignKey(
        'invoicing.Invoice', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='forfeited_bookings',
        verbose_name=_('Račun za zadržani depozit'),
    )"""
    content = content.replace(old_deposit_forfeited, new_deposit_forfeited)

with open(path, 'w') as f:
    f.write(content)
print("[OK] experiences/models.py — no-show auto-invoice + forfeited_invoice FK")


# ══════════════════════════════════════════════════════════════════════
# DRON #3: POS Karenca Hard Block
# ══════════════════════════════════════════════════════════════════════

path = os.path.join(BASE, 'pos/views.py')
with open(path) as f:
    content = f.read()

# Inject karenca check u add_item nakon inventory lookup
old_add_item_block = """    if inventory_id:
        try:
            inv = InventoryItem.objects.get(pk=inventory_id)
            kwargs['inventory_item'] = inv
            if not description: kwargs['description'] = inv.name
            if not barcode: kwargs['barcode'] = inv.barcode or ''
            if unit_price == 0: kwargs['unit_price'] = inv.unit_price or Decimal('0')
            if inv.tax_rate_id:
                kwargs['tax_rate_obj_id'] = inv.tax_rate_id
                try: kwargs['tax_rate'] = inv.tax_rate.rate
                except Exception: pass
        except InventoryItem.DoesNotExist:
            pass"""

new_add_item_block = """    if inventory_id:
        try:
            inv = InventoryItem.objects.get(pk=inventory_id)
            kwargs['inventory_item'] = inv
            if not description: kwargs['description'] = inv.name
            if not barcode: kwargs['barcode'] = inv.barcode or ''
            if unit_price == 0: kwargs['unit_price'] = inv.unit_price or Decimal('0')
            if inv.tax_rate_id:
                kwargs['tax_rate_obj_id'] = inv.tax_rate_id
                try: kwargs['tax_rate'] = inv.tax_rate.rate
                except Exception: pass

            # ── KARENCA HARD BLOCK ──────────────────────────────────
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
                    pass  # Flock deleted ili FK broken — ne blokiraj POS
        except InventoryItem.DoesNotExist:
            pass"""

content = content.replace(old_add_item_block, new_add_item_block)

with open(path, 'w') as f:
    f.write(content)
print("[OK] pos/views.py — karenca hard block u POS add_item")


# ══════════════════════════════════════════════════════════════════════
# MIGRACIJE
# ══════════════════════════════════════════════════════════════════════

# Inventory migracija: source_flock FK
mig_inv = '''from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0021_split_allocation'),
        ('udruge', '0013_flock_modul'),
    ]

    operations = [
        migrations.AddField(
            model_name='inventoryitem',
            name='source_flock',
            field=models.ForeignKey(
                blank=True, null=True,
                help_text='Za karencija enforcement — blokira POS prodaju dok je jato pod lijekovima',
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='inventory_products',
                to='udruge.flock',
                verbose_name='Izvorno jato',
            ),
        ),
    ]
'''

inv_mig_path = os.path.join(BASE, 'inventory/migrations/0022_source_flock.py')
with open(inv_mig_path, 'w') as f:
    f.write(mig_inv)
print("[OK] inventory/migrations/0022_source_flock.py")

# Experiences migracija: forfeited_invoice FK
mig_exp = '''from django.db import migrations, models
import django.db.models.deletion
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist


class Migration(migrations.Migration):

    dependencies = [
        ('experiences', '0001_initial'),
        ('invoicing', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='experiencebooking',
            name='forfeited_invoice',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='forfeited_bookings',
                to='invoicing.invoice',
                verbose_name='Račun za zadržani depozit',
            ),
        ),
    ]
'''

# Check what invoicing migrations exist
inv_migs = os.listdir(os.path.join(BASE, 'invoicing/migrations'))
inv_migs = sorted([m for m in inv_migs if m.endswith('.py') and m != '__init__.py'])
last_inv_mig = inv_migs[-1].replace('.py', '') if inv_migs else '0001_initial'
mig_exp = mig_exp.replace("('invoicing', '0001_initial')", f"('invoicing', '{last_inv_mig}')")

exp_mig_path = os.path.join(BASE, 'experiences/migrations/0002_forfeited_invoice.py')
with open(exp_mig_path, 'w') as f:
    f.write(mig_exp)
print("[OK] experiences/migrations/0002_forfeited_invoice.py")


print("\n════════════════════════════════════════════")
print("SVA 3 DRONA PATCHANA. Preostaje:")
print("  1. python manage.py migrate")
print("  2. systemctl restart gunicorn-fina")
print("════════════════════════════════════════════")
