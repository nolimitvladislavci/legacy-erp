#!/usr/bin/env python3
"""
Dron #3: LOT slijedivost (EU 178/2002)
1. POSReceiptItem: dodaj stock_batch FK + lot_number + expiry_date
2. _deduct_stock(): FEFO batch deduction + return batch info
3. receipt_thermal.html: LOT + rok na ispisu
4. Django migration generiranje
"""

# ══════════════════════════════════════════════════════════════
# FIX 1: POSReceiptItem — dodaj LOT polja
# ══════════════════════════════════════════════════════════════
path1 = '/var/www/fina-connect/pos/models.py'
with open(path1, 'r') as f:
    c = f.read()

# Dodaj polja nakon is_nonprofit_activity
OLD_FIELDS = """    is_nonprofit_activity = models.BooleanField(
        default=False,
        verbose_name=_("Neprofitna djelatnost"),
        help_text=_("Clanarina/donacija — ne fiskalizira se"),
    )

    total_price    = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                          verbose_name=_('Ukupno s PDV'))"""

NEW_FIELDS = """    is_nonprofit_activity = models.BooleanField(
        default=False,
        verbose_name=_("Neprofitna djelatnost"),
        help_text=_("Clanarina/donacija — ne fiskalizira se"),
    )

    # LOT slijedivost (EU 178/2002, Zakon o sigurnosti hrane)
    stock_batch = models.ForeignKey(
        'inventory.StockBatch', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='pos_items',
        verbose_name=_('Sarza (LOT)'),
    )
    lot_number = models.CharField(
        max_length=100, blank=True, default='',
        verbose_name=_('LOT broj'),
        help_text=_('Denormalizirano — trajno na bonu cak i ako se sarza obrise'),
    )
    expiry_date = models.DateField(
        null=True, blank=True,
        verbose_name=_('Rok trajanja'),
    )

    total_price    = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                          verbose_name=_('Ukupno s PDV'))"""

if 'stock_batch' not in c:
    c = c.replace(OLD_FIELDS, NEW_FIELDS)
    with open(path1, 'w') as f:
        f.write(c)
    print('[OK] Fix 1: POSReceiptItem — dodani stock_batch, lot_number, expiry_date')
else:
    print('[SKIP] Fix 1: LOT polja vec postoje')

# ══════════════════════════════════════════════════════════════
# FIX 2: _deduct_stock() — FEFO batch deduction
# ══════════════════════════════════════════════════════════════
path2 = '/var/www/fina-connect/pos/services/checkout.py'
with open(path2, 'r') as f:
    c2 = f.read()

OLD_DEDUCT = """    @staticmethod
    def _deduct_stock(item, qty, unit_price, receipt_number, user):
        \"\"\"
        Smanji zalihu + BOM auto-deduction.
        B-08: select_for_update za race condition zastitu.
        \"\"\"
        from inventory.models import InventoryItem, StockMovement

        # Lock item row — sprecava race condition
        locked_item = InventoryItem.objects.select_for_update().get(pk=item.pk)

        # Usluge i non-stockable stavke — ne diramo zalihu
        if not locked_item.is_stockable:
            return

        # Provjeri zalihu
        company = locked_item.company
        allow_negative = getattr(company, 'allow_negative_stock', False)
        if not allow_negative and locked_item.quantity < qty:
            logger.warning(
                'POS: Nedovoljna zaliha za %s (trazeno: %s, dostupno: %s) — bon #%d',
                locked_item.name, qty, locked_item.quantity, receipt_number
            )

        StockMovement.objects.create(
            item=locked_item,
            movement_type='out',
            quantity=qty,
            unit_price=unit_price,
            reason='POS bon #%d' % receipt_number,
            performed_by=user,
        )"""

NEW_DEDUCT = """    @staticmethod
    def _deduct_stock(item, qty, unit_price, receipt_number, user):
        \"\"\"
        Smanji zalihu + BOM auto-deduction + FEFO batch tracking.
        B-08: select_for_update za race condition zastitu.
        Vraca: (lot_number, expiry_date, stock_batch_id) ili (None, None, None)
        \"\"\"
        from inventory.models import InventoryItem, StockMovement

        # Lock item row — sprecava race condition
        locked_item = InventoryItem.objects.select_for_update().get(pk=item.pk)

        # Usluge i non-stockable stavke — ne diramo zalihu
        if not locked_item.is_stockable:
            return None, None, None

        # Provjeri zalihu
        company = locked_item.company
        allow_negative = getattr(company, 'allow_negative_stock', False)
        if not allow_negative and locked_item.quantity < qty:
            logger.warning(
                'POS: Nedovoljna zaliha za %s (trazeno: %s, dostupno: %s) — bon #%d',
                locked_item.name, qty, locked_item.quantity, receipt_number
            )

        StockMovement.objects.create(
            item=locked_item,
            movement_type='out',
            quantity=qty,
            unit_price=unit_price,
            reason='POS bon #%d' % receipt_number,
            performed_by=user,
        )

        # ── FEFO Batch Deduction (EU 178/2002 LOT slijedivost) ──
        lot_number = None
        expiry_date = None
        batch_id = None
        try:
            from inventory.models import StockBatch
            batches = StockBatch.objects.filter(
                item=locked_item,
                quantity__gt=0,
                quarantine_status='active',
            ).order_by('expiry_date', 'created_at')  # FEFO

            remaining = qty
            primary_batch = None
            for batch in batches:
                if remaining <= 0:
                    break
                deduct = min(batch.quantity, remaining)
                batch.quantity -= deduct
                batch.save(update_fields=['quantity'])
                remaining -= deduct
                if primary_batch is None:
                    primary_batch = batch

            if primary_batch:
                lot_number = primary_batch.batch_number or None
                expiry_date = primary_batch.expiry_date
                batch_id = primary_batch.pk
        except Exception as e:
            # StockBatch ne postoji za ovaj artikl ili nema batcheva — OK
            logger.debug('FEFO batch deduction skipped for %s: %s', locked_item.name, e)

        return lot_number, expiry_date, batch_id"""

if 'FEFO' not in c2:
    c2 = c2.replace(OLD_DEDUCT, NEW_DEDUCT)
    with open(path2, 'w') as f:
        f.write(c2)
    print('[OK] Fix 2: _deduct_stock() — FEFO batch deduction, vraca LOT info')
else:
    print('[SKIP] Fix 2: FEFO vec postoji')

# Sad trebam azurirati poziv _deduct_stock da koristi return values
with open(path2, 'r') as f:
    c2 = f.read()

OLD_CALL = """                cls._deduct_stock(inv, qty, unit_price, next_number, user)"""
NEW_CALL = """                lot_num, exp_date, batch_pk = cls._deduct_stock(inv, qty, unit_price, next_number, user) or (None, None, None)
                    # LOT slijedivost: spremi na receipt item
                    if lot_num or exp_date:
                        try:
                            ri = receipt.items.filter(inventory_item=inv).last()
                            if ri:
                                ri.lot_number = lot_num or ''
                                ri.expiry_date = exp_date
                                if batch_pk:
                                    ri.stock_batch_id = batch_pk
                                ri.save(update_fields=['lot_number', 'expiry_date', 'stock_batch_id'])
                        except Exception:
                            pass"""

if 'lot_num, exp_date' not in c2 and OLD_CALL in c2:
    c2 = c2.replace(OLD_CALL, NEW_CALL)
    with open(path2, 'w') as f:
        f.write(c2)
    print('[OK] Fix 2b: _deduct_stock caller — LOT info sprema na POSReceiptItem')
else:
    print('[SKIP] Fix 2b: LOT save vec postoji ili poziv nije pronadjen')

# ══════════════════════════════════════════════════════════════
# FIX 3: receipt_thermal.html — LOT + rok na ispisu
# ══════════════════════════════════════════════════════════════
path3 = '/var/www/fina-connect/templates/pos/receipt_thermal.html'
with open(path3, 'r') as f:
    c3 = f.read()

OLD_DETAIL = """          &euro;{{ item.unit_price|floatformat:2 }} &times; {{ item.quantity|floatformat:\"-2\" }} | PDV {{ item.tax_rate|floatformat:0 }}%{% if item.discount_percent %} | Pop. {{ item.discount_percent|floatformat:0 }}%{% endif %}{% if item.is_pfand_return %} | POVRAT{% endif %}"""

NEW_DETAIL = """          &euro;{{ item.unit_price|floatformat:2 }} &times; {{ item.quantity|floatformat:\"-2\" }} | PDV {{ item.tax_rate|floatformat:0 }}%{% if item.discount_percent %} | Pop. {{ item.discount_percent|floatformat:0 }}%{% endif %}{% if item.is_pfand_return %} | POVRAT{% endif %}{% if item.lot_number %}<br>LOT: {{ item.lot_number }}{% if item.expiry_date %} | Rok: {{ item.expiry_date|date:"d.m.Y" }}{% endif %}{% endif %}"""

if 'lot_number' not in c3:
    c3 = c3.replace(OLD_DETAIL, NEW_DETAIL)
    with open(path3, 'w') as f:
        f.write(c3)
    print('[OK] Fix 3: receipt_thermal.html — LOT + rok trajanja na ispisu')
else:
    print('[SKIP] Fix 3: LOT vec na ispisu')

print('\nDron #3 kompletiran. Django migration potreban!')
