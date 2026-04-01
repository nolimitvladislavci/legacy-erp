"""
POS Checkout Service — centralna logika naplate.

Pravila:
- Nema HTTP, nema request, nema JsonResponse — cista poslovna logika
- @transaction.atomic stiti cijelu transakciju
- CheckoutValidationError = greska poslovne logike (400)
- Sve promjene zaliha, fiskalizacija i placanje u jednoj atomarnoj transakciji
"""
import logging
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from django.db import models, transaction
from django.utils import timezone as tz

logger = logging.getLogger('pos_checkout')


class CheckoutValidationError(Exception):
    """Greska poslovne logike — salje se korisniku kao 400."""
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(message)


class CheckoutService:
    """Centralni servis za POS naplatu."""

    @staticmethod
    def _resolve_cashier(cashier_id, company, session):
        """Resolve cashier i dodaj u session.active_cashiers."""
        if not cashier_id:
            return None
        from pos.models import POSCashier
        cashier = POSCashier.objects.filter(
            pk=cashier_id, company=company, is_active=True
        ).first()
        if cashier:
            session.active_cashiers.add(cashier)
        return cashier

    @staticmethod
    def _next_receipt_number(session):
        # select_for_update on session: serializes receipt_number per session (race condition fix)
        from django.db.models import Max
        from pos.models import POSSession
        POSSession.objects.select_for_update().filter(pk=session.pk).first()
        max_num = session.receipts.aggregate(m=Max('receipt_number'))['m'] or 0
        return max_num + 1

    @staticmethod
    def _deduct_stock(item, qty, unit_price, receipt_number, user):
        """
        Smanji zalihu + BOM auto-deduction + FEFO batch tracking.
        B-08: select_for_update za race condition zastitu.
        Vraca: (lot_number, expiry_date, stock_batch_id) ili (None, None, None)
        """
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

        # ── BOM auto-deduction ──
        # Ako artikl ima aktivnu sastavnicu, oduzmi komponente
        try:
            from calculator.models import BOM
            boms = BOM.objects.filter(
                company=locked_item.company, article=locked_item, is_active=True,
            ).prefetch_related('items__material')
            for bom in boms:
                sold_qty = qty / (bom.yield_quantity or 1)
                for bi in bom.items.select_related('material').all():
                    deduct_qty = bi.net_quantity * sold_qty
                    StockMovement.objects.create(
                        item=bi.material,
                        movement_type='out',
                        quantity=deduct_qty,
                        unit_price=bi.material.purchase_price,
                        reason='BOM - POS bon #%d' % receipt_number,
                        performed_by=user,
                    )
        except Exception:
            logger.warning('BOM deduction failed for item %s', item.pk, exc_info=True)

        return lot_number, expiry_date, batch_id

    @staticmethod
    def _fiscalize(receipt):
        """
        Tri-Routing fiskalizacija:
        1. fiscal_exempt -> bypass (udruge bez PDV-a)
        2. DE (KassenSichV) -> TSE adapter (Fiskaly Cloud)
        3. HR (FINA CIS) -> standardna fiskalizacija
        Ne blokira naplatu ako padne.
        """
        company = receipt.session.terminal.company

        # Route 1: Nonprofit guard (item-level)
        if not CheckoutService._should_fiscalize(receipt):
            logger.info(
                'FISCAL BYPASS: Bon #%d preskocen (nonprofit mode: %s)',
                receipt.receipt_number, company.nonprofit_fiscal_mode,
            )
            return '', '', ''

        # Route 2: DE — KassenSichV / TSE
        fiscal_system = getattr(company, 'fiscal_system', 'hr_fiscal')
        if fiscal_system == 'de_gobd' or getattr(company, 'country', 'HR') == 'DE':
            return CheckoutService._fiscalize_tse(receipt)

        # Route 3: HR — FINA CIS (default)
        zki, jir, error = '', '', ''
        try:
            from fiscal.service import fiscalize_pos_receipt
            jir_result = fiscalize_pos_receipt(receipt)
            if jir_result:
                jir = str(jir_result)
                receipt.refresh_from_db()
                zki = receipt.zki or ''
        except Exception as e:
            error = str(e)[:100]
            logger.warning('Fiskalizacija bon #%s: %s', receipt.receipt_number, e)
        return zki, jir, error

    @staticmethod
    def _should_fiscalize(receipt):
        company = receipt.session.terminal.company
        # Training mode = NIKAD fiskaliziraj
        if getattr(receipt, "is_training", False):
            return False
        mode = company.nonprofit_fiscal_mode
        if mode == 'none':
            return False
        if mode == 'full':
            return True
        has_commercial = receipt.items.filter(
            is_nonprofit_activity=False, is_tip=False,
        ).exists()
        return has_commercial

    @staticmethod
    def _resolve_member_discount(company, payload):
        from decimal import Decimal
        card_uid = (payload.get('member_card') or '').strip()
        member_id = payload.get('member_id')
        if not card_uid and not member_id:
            return Decimal('0'), None
        try:
            from udruge.models import Clan, MemberSubscription
            if card_uid:
                clan = Clan.objects.get(access_card_uid=card_uid, company=company, status='aktivan')
            else:
                clan = Clan.objects.get(pk=member_id, company=company, status='aktivan')
            sub = MemberSubscription.objects.filter(
                clan=clan, status__in=['active', 'grace'],
                plan__discount_percent__gt=0,
            ).select_related('plan').first()
            if sub:
                return sub.plan.discount_percent, clan.full_name
            return Decimal('0'), clan.full_name
        except Exception:
            return Decimal('0'), None

    @staticmethod
    def _fiscalize_tse(receipt):
        """
        DE Route: Fiskaly Cloud TSE — KassenSichV compliant.
        Bei TSE-Ausfall: Bon mit 'TSE ausgefallen' Klausel,
        Nacherfassung per Celery retry.
        """
        zki, jir, error = '', '', ''
        try:
            from pos.tse_adapter import FiskalyTSEAdapter
            company = receipt.session.terminal.company
            adapter = FiskalyTSEAdapter.from_company(company)
            result = adapter.sign_transaction(receipt)

            # sign_transaction vraca dict s tse_ prefixed keys
            receipt.tse_transaction_number = str(result.get('tse_transaction_number', ''))
            receipt.tse_signature_counter = result.get('tse_signature_counter')
            receipt.tse_hash = result.get('tse_hash', '')
            receipt.tse_serial_number = result.get('tse_serial_number', '')
            receipt.tse_start_time = result.get('tse_start_time')
            receipt.tse_end_time = result.get('tse_end_time')
            receipt.tse_error = ''
            receipt.save(update_fields=[
                'tse_transaction_number', 'tse_signature_counter',
                'tse_hash', 'tse_serial_number',
                'tse_start_time', 'tse_end_time', 'tse_error',
            ])
            zki = receipt.tse_hash[:32] if receipt.tse_hash else ''
            jir = receipt.tse_transaction_number or ''
            logger.info('TSE OK: Bon #%s, TxNr=%s', receipt.receipt_number, jir)

        except Exception as e:
            error = str(e)[:100]
            # TSE Ausfall — KassenSichV erlaubt Offline mit Klausel
            receipt.tse_error = 'TSE_AUSFALL: %s' % error
            receipt.save(update_fields=['tse_error'])
            logger.warning(
                'TSE AUSFALL Bon #%s: %s — Nacherfassung per retry task',
                receipt.receipt_number, error,
            )
        return zki, jir, error

    @classmethod
    @transaction.atomic
    def process_receipt(cls, company, user, payload):
        """
        Glavni motor naplate za api_pos_checkout i quick_pay (non-gastro).

        payload:
            session_id, items[], payment_method, amount_paid,
            cashier_id, tip_amount, note, voucher_code, voucher_amount
        """
        from pos.models import POSSession, POSReceipt, POSReceiptItem, POSPaymentLine
        from inventory.models import InventoryItem

        # ── 1. PARSE ──
        session_id = payload.get('session_id')
        items_data = payload.get('items', [])
        payment_method = str(payload.get('payment_method') or payload.get('method') or 'CASH').upper()

        try:
            amount_paid = Decimal(str(payload.get('amount_paid', 0) or 0))
        except (InvalidOperation, ValueError):
            amount_paid = Decimal('0')

        try:
            tip_amount = Decimal(str(payload.get('tip_amount', 0) or 0))
        except (InvalidOperation, ValueError):
            tip_amount = Decimal('0')

        cashier_id = payload.get('cashier_id')
        note = payload.get('note') or payload.get('cashier') or ''
        voucher_code = str(payload.get('voucher_code', '') or '').strip()
        try:
            voucher_amount = Decimal(str(payload.get('voucher_amount', 0) or 0))
        except (InvalidOperation, ValueError):
            voucher_amount = Decimal('0')

        # ── 1b. DE 250 EUR KLEINBETRAGSRECHNUNG LIMIT ──
        # §33 UStDV: Bon > 250 EUR bruto MORA imati podatke kupca
        if (company.country in ('DE', 'AT')
                and not payload.get('buyer_oib', '').strip()
                and not payload.get('buyer_name', '').strip()):
            est_total = sum(
                float(i.get('unit_price', i.get('price', 0))) *
                float(i.get('quantity', i.get('qty', 1)))
                for i in payload.get('items', [])
            )
            if est_total > 250:
                raise CheckoutValidationError(
                    'DE_BUYER_REQUIRED',
                    'Rechnungsbetrag ueber 250 EUR: Kaeuferangaben (Name, Adresse, USt-IdNr) '
                    'sind gemaess Paragraph 14 Abs. 4 UStG erforderlich. Bitte Kaeufer eingeben.'
                )

        # ── 1c. KARENCIJA GUARD (livestock) ──
        for item_data in payload.get('items', []):
            item_id = item_data.get('item_id') or item_data.get('id')
            if item_id:
                try:
                    from inventory.models import InventoryItem
                    inv_item = InventoryItem.objects.select_related('livestock_animal').get(pk=item_id)
                    if inv_item.livestock_animal and inv_item.livestock_animal.is_in_karencija:
                        animal = inv_item.livestock_animal
                        raise CheckoutValidationError(
                            'KARENCIJA_BLOCKED',
                            'BLOKIRANO: %s je u karenciji do %s (%s). '
                            'Prodaja mlijeka/mesa ovog grla je zakonom zabranjena.' % (
                                animal.ear_tag, animal.karencija_end, animal.karencija_reason,
                            )
                        )
                except InventoryItem.DoesNotExist:
                    pass
                except CheckoutValidationError:
                    raise
                except Exception:
                    pass

        # ── 2. VALIDACIJA ──
        if not session_id:
            raise CheckoutValidationError('NO_SESSION', 'session_id je obavezan')
        if not items_data:
            raise CheckoutValidationError('EMPTY_CART', 'Kosarica je prazna')

        session = POSSession.objects.filter(pk=session_id, status='open').first()
        if not session:
            raise CheckoutValidationError('SESSION_CLOSED', 'Smjena nije otvorena ili ne postoji')
        if session.terminal.company_id != company.pk:
            raise CheckoutValidationError('WRONG_COMPANY', 'Smjena ne pripada ovoj tvrtki')

        # ── 2b. VALIDACIJA MIJEŠANJA (nonprofit vs commercial) ──
        item_ids = [d.get('item_id') or d.get('id') for d in items_data if d.get('item_id') or d.get('id')]
        if item_ids:
            inv_items = list(InventoryItem.objects.filter(pk__in=item_ids, company=company).only(
                'pk', 'is_nonprofit_activity'
            ))
            has_nonprofit = any(getattr(i, 'is_nonprofit_activity', False) for i in inv_items)
            has_commercial = any(not getattr(i, 'is_nonprofit_activity', False) for i in inv_items)
            if has_nonprofit and has_commercial:
                raise CheckoutValidationError(
                    'MIXED_NONPROFIT_COMMERCIAL',
                    'Zabranjeno mijesanje! Komercijalne stavke i neprofitne stavke '
                    '(clanarine, donacije) moraju se naplatiti na odvojene racune.'
                )

        # ── 3. PRIPREMA ──
        cashier_obj = cls._resolve_cashier(cashier_id, company, session)
        member_discount, member_name = cls._resolve_member_discount(company, payload)
        next_number = cls._next_receipt_number(session)

        # Retry on duplicate receipt_number (race condition with multiple devices)
        for _attempt in range(5):
            try:
                next_number = cls._next_receipt_number(session)
                receipt = POSReceipt.objects.create(
                    session=session,
                    receipt_number=next_number,
                    cashier=cashier_obj,
                    client_ip=payload.get('client_ip', ''),
                    client_ua=str(payload.get('client_ua', ''))[:300],
                    buyer_oib=str(payload.get('buyer_oib', ''))[:20],
                    buyer_name=str(payload.get('buyer_name', ''))[:200],
                    buyer_address=str(payload.get('buyer_address', ''))[:255],
                    is_r1=bool(payload.get('buyer_oib')),
                    note=str(note)[:255] if note else (cashier_obj.name if cashier_obj else ''),
                    is_training=getattr(session.terminal, 'is_training', False) or session.is_training,
                    member_name=member_name or '',
                    member_discount_applied=member_discount,
                )
                break  # Success — exit retry loop
            except Exception as _dup_err:
                if 'unique' in str(_dup_err).lower() and _attempt < 4:
                    continue
                raise

        # ── 4. STAVKE ──
        for item_data in items_data:
            item_id = item_data.get('item_id') or item_data.get('id')
            is_tip = bool(item_data.get('is_tip', False))
            is_pfand = bool(item_data.get('is_pfand_return', False))

            try:
                qty = Decimal(str(item_data.get('quantity') or item_data.get('qty') or 1))
            except (InvalidOperation, ValueError):
                qty = Decimal('1')

            if is_tip:
                try:
                    price = Decimal(str(item_data.get('unit_price') or item_data.get('price') or 0))
                except (InvalidOperation, ValueError):
                    price = Decimal('0')
                POSReceiptItem.objects.create(
                    receipt=receipt,
                    description=item_data.get('name', 'Napojnica'),
                    quantity=qty, unit_price=price,
                    tax_rate=Decimal('0'), is_tip=True,
                )
                continue

            if not item_id and not is_pfand:
                try:
                    price = Decimal(str(item_data.get('unit_price') or item_data.get('price') or 0))
                except (InvalidOperation, ValueError):
                    price = Decimal('0')
                tax = Decimal(str(item_data.get('tax_rate') or item_data.get('tax') or 25))
                POSReceiptItem.objects.create(
                    receipt=receipt,
                    description=str(item_data.get('name', 'Artikl'))[:200],
                    quantity=qty, unit_price=price, tax_rate=tax,
                    is_pfand_return=is_pfand,
                )
                continue

            try:
                inv = InventoryItem.objects.select_related('tax_rate').get(
                    pk=item_id, company=company
                )
            except InventoryItem.DoesNotExist:
                logger.warning('POS: InventoryItem %s ne postoji za company %s', item_id, company.pk)
                continue

            try:
                unit_price = Decimal(str(
                    item_data.get('unit_price') or item_data.get('price') or inv.unit_price
                ))
            except (InvalidOperation, ValueError):
                unit_price = inv.unit_price or Decimal('0')

            tax_rate = Decimal(str(item_data.get('tax_rate') or item_data.get('tax') or (
                inv.tax_rate.rate if inv.tax_rate else 25
            )))

            # Apply member discount if active subscription exists
            item_discount = Decimal('0')
            if member_discount > 0 and not getattr(inv, 'is_nonprofit_activity', False):
                item_discount = member_discount

            POSReceiptItem.objects.create(
                receipt=receipt,
                inventory_item=inv,
                description=inv.name,
                quantity=qty,
                unit_price=unit_price,
                tax_rate=tax_rate,
                discount_percent=item_discount,
                is_pfand_return=is_pfand,
                is_nonprofit_activity=getattr(inv, 'is_nonprofit_activity', False),
            )

            # Stock deduction
            try:
                lot_num, exp_date, batch_pk = cls._deduct_stock(inv, qty, unit_price, next_number, user) or (None, None, None)
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
                        pass
            except Exception as stock_err:
                logger.warning('POS: StockMovement greska za item %s: %s', item_id, stock_err)

            # ── CLANARINA AUTO-LINK ──
            if getattr(inv, 'is_nonprofit_activity', False):
                try:
                    from udruge.models import MembershipPlan, Clanarina, Clan
                    mp = MembershipPlan.objects.filter(linked_item=inv, company=company, is_active=True).first()
                    if mp and member_name:
                        card_uid = (payload.get('member_card') or '').strip()
                        m_id = payload.get('member_id')
                        clan = None
                        if card_uid:
                            clan = Clan.objects.filter(access_card_uid=card_uid, company=company).first()
                        elif m_id:
                            clan = Clan.objects.filter(pk=m_id, company=company).first()
                        if clan:
                            receipt.member_clan_id = clan.pk
                            from datetime import timedelta
                            today = tz.now().date()
                            existing = Clanarina.objects.filter(
                                company=company, clan=clan,
                                period_start=today,
                            ).exists()
                            if not existing:
                                cl = Clanarina.objects.create(
                                    company=company, clan=clan,
                                    period_start=today,
                                    period_end=today + timedelta(days=mp.duration_days),
                                    amount=unit_price * qty,
                                    payment_method='pos',
                                    status='placena',
                                    paid_at=tz.now(),
                                    receipt_number='POS-%d' % next_number,
                                )
                                logger.info('AUTO-CLANARINA: Clan %s, plan %s, bon #%d -> Clanarina %d',
                                           clan.full_name, mp.name, next_number, cl.pk)
                except Exception as clan_err:
                    logger.warning('Clanarina auto-link: %s', clan_err)

        # ── 5. NAPOJNICA (zasebna stavka) ──
        if tip_amount < 0:
            tip_amount = Decimal('0')
            logger.warning('Negativna napojnica odbacena za bon #%d', receipt.pk)
        if tip_amount > 0 and receipt.total > 0 and tip_amount > receipt.total * 3:
            logger.warning(
                'Napojnica %.2f EUR > 3x iznos bona %.2f EUR — moguca greska, bon #%d',
                tip_amount, receipt.total, receipt.pk,
            )
        if tip_amount > 0:
            POSReceiptItem.objects.create(
                receipt=receipt,
                description='Napojnica',
                quantity=Decimal('1'),
                unit_price=tip_amount,
                tax_rate=Decimal('0'),
                is_tip=True,
            )

        # ── 5b. TIP LIMIT CHECK (HR 3.360 EUR godisnji limit) ──
        if tip_amount > 0:
            try:
                from pos.tip_service import TipTracker
                operator = session.operator
                if operator:
                    ok, msg = TipTracker.check_tip_limit(operator, tip_amount)
                    if not ok:
                        logger.warning('TIP LIMIT: %s — %s', operator, msg)
            except Exception:
                pass

        # ── 6. RECALCULATE (koristi model metodu) ──
        receipt.recalculate()
        receipt.save()

        # ── 6a. POREZ NA POTROŠNJU (čl.20 Zakon o lokalnim porezima) ──
        try:
            pos_settings = company.pos_settings
            if pos_settings.consumption_tax_active and pos_settings.consumption_tax_rate > 0:
                # Osnovica = prihod bez PDV-a (subtotal), stopa do 3%
                ct_rate = pos_settings.consumption_tax_rate / Decimal('100')
                receipt.consumption_tax_amount = (receipt.subtotal * ct_rate).quantize(
                    Decimal('0.01'), rounding=ROUND_HALF_UP
                )
                receipt.save(update_fields=['consumption_tax_amount'])
        except Exception:
            pass  # POSSettings ne postoji ili nema PP

        # ── 6b. BLAGAJNICKI MAKSIMUM (cash_register_limit) ──
        if payment_method == 'CASH':
            limit = getattr(company, 'cash_register_limit', None)
            if limit and limit > 0:
                from django.db.models import Sum
                from pos.models import POSPaymentLine
                current_cash = session.receipts.filter(
                    status='paid',
                ).aggregate(
                    cash_in=Sum('payments__amount', filter=models.Q(payments__method='CASH')),
                )['cash_in'] or Decimal('0')
                if current_cash + receipt.total > limit:
                    logger.warning(
                        'CASH LIMIT: Smjena %s — %s + %s > %s EUR limit',
                        session.pk, current_cash, receipt.total, limit,
                    )

        # ── 7. PLACANJE ──
        change = Decimal('0')

        if payment_method == 'VOUCHER' or voucher_amount > 0:
            try:
                from pos.models import Voucher
                voucher = Voucher.objects.get(code=voucher_code, is_active=True)
                if not voucher.is_usable:
                    raise CheckoutValidationError('VOUCHER_INVALID', 'Vaucer nije valjan ili je istekao.')

                is_multi = getattr(voucher, 'voucher_type', 'multi') == 'multi'
                if not is_multi:
                    logger.info('Einzweck voucher %s — PDV vec obracunat', voucher.code)
                use_amount = min(voucher.remaining, receipt.total if not voucher_amount else voucher_amount)
                voucher.remaining = max(Decimal('0'), voucher.remaining - use_amount)
                if voucher.remaining == 0:
                    voucher.is_active = False
                voucher.save(update_fields=['remaining', 'is_active'])
                POSPaymentLine.objects.create(
                    receipt=receipt, method='VOUCHER', amount=use_amount,
                    change_given=Decimal('0'), card_reference=voucher_code,
                )
                remainder = receipt.total - use_amount
                if remainder > Decimal('0.001'):
                    rem_method = str(payload.get('remainder_method', 'CASH')).upper()
                    POSPaymentLine.objects.create(
                        receipt=receipt, method=rem_method, amount=remainder,
                        change_given=Decimal('0'),
                    )
            except CheckoutValidationError:
                raise
            except Voucher.DoesNotExist:
                raise CheckoutValidationError('VOUCHER_NOT_FOUND', 'Vaucer nije pronaden')
            except Exception as e:
                raise CheckoutValidationError('VOUCHER_ERROR', 'Greska vaucera: %s' % str(e)[:80])
        else:
            if payment_method != 'CASH':
                amount_paid = receipt.total
            amount_paid = max(amount_paid, receipt.total)
            change = max(Decimal('0'), amount_paid - receipt.total)
            POSPaymentLine.objects.create(
                receipt=receipt, method=payment_method,
                amount=receipt.total, change_given=change,
            )

        # ── 8. FINALIZE ──
        receipt.status = POSReceipt.Status.PAID
        receipt.paid_at = tz.now()
        receipt.save(update_fields=['status', 'paid_at', 'total', 'subtotal', 'tax_amount', 'consumption_tax_amount'])

        # ── 9. FISKALIZACIJA ──
        # Hard timeout: fiskalizacija NIKAD ne smije blokirati vise od 5s
        import concurrent.futures
        try:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(cls._fiscalize, receipt)
                zki, jir, fiscal_error = future.result(timeout=5)
        except concurrent.futures.TimeoutError:
            zki, jir, fiscal_error = '', '', 'Fiscal timeout (5s) — retry later'
            logger.warning('Fiscal HARD TIMEOUT for receipt #%s', receipt.receipt_number)
        except Exception as e:
            zki, jir, fiscal_error = '', '', str(e)[:100]

        # ── 10. RESULT ──
        terminal_pk = session.terminal.pk
        result = {
            'receipt_id': receipt.pk,
            'receipt_number': next_number,
            'invoice_number': 'RAC-%d/%d/%d' % (tz.now().year, terminal_pk, next_number),
            'total': str(receipt.total),
            'change': str(change),
            'payment_method': payment_method,
            'zki': zki,
            'jir': jir,
            'pdf_url': '/pos/receipt/%d/pdf/' % receipt.pk,
            'print_url': '/pos/receipt/%d/pdf/?format=thermal' % receipt.pk,
            'items_count': len(items_data),
            'consumption_tax': str(receipt.consumption_tax_amount) if receipt.consumption_tax_amount else '0',
        }
        if fiscal_error:
            result['fiscal_warning'] = fiscal_error
            result['not_fiscalized'] = True
            result['fiscal_message'] = (
                'Racun je izdan ali NIJE fiskaliziran. '
                'Automatski retry ce pokusati ponovo u pozadini.'
            )

        # Pulse analytics (non-blocking)
        try:
            from pos.pulse import analyze_receipt
            analyze_receipt(receipt)
        except Exception:
            pass

        return result
