"""
POS Checkout Service — centralna logika naplate.

Pravila:
- Nema HTTP, nema request, nema JsonResponse — cista poslovna logika
- @transaction.atomic stiti cijelu transakciju
- CheckoutValidationError = greska poslovne logike (400)
- Sve promjene zaliha, fiskalizacija i placanje u jednoj atomarnoj transakciji
"""
import logging
from decimal import Decimal, InvalidOperation
from django.db import transaction
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
        last = session.receipts.order_by('-receipt_number').first()
        return (last.receipt_number + 1) if last else 1

    @staticmethod
    def _deduct_stock(item, qty, unit_price, receipt_number, user):
        """
        Smanji zalihu + BOM auto-deduction.
        B-08: select_for_update za race condition zastitu.
        """
        from inventory.models import InventoryItem, StockMovement

        # Lock item row — sprecava race condition
        locked_item = InventoryItem.objects.select_for_update().get(pk=item.pk)

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
        # BOM auto-deduction
        try:
            from calculator.models import BOM
            boms = BOM.objects.filter(
                company=item.company, article=item, is_active=True,
            ).prefetch_related('items__material')
            for bom in boms:
                sold_qty = qty / (bom.yield_quantity or 1)
                for bi in bom.items.select_related('material').all():
                    deduct = bi.net_quantity * sold_qty
                    StockMovement.objects.create(
                        item=bi.material,
                        movement_type='out',
                        quantity=deduct,
                        unit_price=bi.material.purchase_price,
                        reason='BOM - POS bon #%d' % receipt_number,
                        performed_by=user,
                    )
        except Exception:
            logger.warning('BOM deduction failed for item %s', item.pk, exc_info=True)

    @staticmethod
    def _fiscalize(receipt):
        """
        Tri-Routing fiskalizacija:
        1. fiscal_exempt → bypass (udruge bez PDV-a)
        2. DE (KassenSichV) → TSE adapter (Fiskaly Cloud)
        3. HR (FINA CIS) → standardna fiskalizacija
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
            # Izracunaj ukupni iznos iz payloada
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
        # Blokira prodaju mlijeka/mesa od grla u karenciji (antibiotik/lijek)
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
        # Fail-fast: jedan batch query, ne N upita po stavci
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
                    'Zabranjeno miješanje! Komercijalne stavke i neprofitne stavke '
                    '(članarine, donacije) moraju se naplatiti na odvojene račune.'
                )

        # ── 3. PRIPREMA ──
        cashier_obj = cls._resolve_cashier(cashier_id, company, session)
        member_discount, member_name = cls._resolve_member_discount(company, payload)
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
        )

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
                # Napojnica stavka iz items arraya
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
                # Custom stavka bez inventory linka
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

            POSReceiptItem.objects.create(
                receipt=receipt,
                inventory_item=inv,
                description=inv.name,
                quantity=qty,
                unit_price=unit_price,
                tax_rate=tax_rate,
                is_pfand_return=is_pfand,
                is_nonprofit_activity=getattr(inv, 'is_nonprofit_activity', False),
            )

            # Stock deduction
            try:
                cls._deduct_stock(inv, qty, unit_price, next_number, user)
            except Exception as stock_err:
                logger.warning('POS: StockMovement greska za item %s: %s', item_id, stock_err)

        # ── 5. NAPOJNICA (zasebna stavka) ──
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
                        # Ne blokiramo — samo logiramo i dodajemo warning u result
            except Exception:
                pass

        # ── 6. RECALCULATE (koristi model metodu) ──
        receipt.recalculate()
        receipt.save()

        # ── 7. PLACANJE ──
        change = Decimal('0')

        if payment_method == 'VOUCHER' or voucher_amount > 0:
            # Voucher split payment — Mehrzweck vs Einzweck PDV logika
            try:
                from pos.models import Voucher
                voucher = Voucher.objects.get(code=voucher_code, is_active=True)
                if not voucher.is_usable:
                    raise CheckoutValidationError('VOUCHER_INVALID', 'Vaucer nije valjan ili je istekao.')

                # Mehrzweck (multi): PDV se obracunava TEK pri otkupu
                # Einzweck (single): PDV je vec obracunat pri prodaji bona
                is_multi = getattr(voucher, 'voucher_type', 'multi') == 'multi'
                if not is_multi:
                    # Einzweck: stavke placene ovim bonom idu s 0% PDV
                    # jer je PDV vec obracunat pri prodaji bona
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
        receipt.save(update_fields=['status', 'paid_at', 'total', 'subtotal', 'tax_amount'])

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
        }
        if fiscal_error:
            result['fiscal_warning'] = fiscal_error
            result['not_fiscalized'] = True
            result['fiscal_message'] = (
                'Racun je izdan ali NIJE fiskaliziran. '
                'Razlog: %s. '
                'Sustav ce automatski pokusati ponovo u roku 2 minute.'
            ) % fiscal_error[:80]
            logger.warning('NOT FISCALIZED: Bon #%s — %s', next_number, fiscal_error)

        # ── 10b. AUTO e-RACUN ZA B2B (R1) ──
        # Od 01.01.2026. B2B transakcije MORAJU imati e-Racun
        if receipt.buyer_oib and receipt.buyer_oib.strip():
            try:
                from eracun.models import ERacun
                # Kreiraj e-Racun u pozadini (Celery)
                from django.db import transaction as db_tx
                def _create_eracun():
                    try:
                        eracun = ERacun.objects.create(
                            company=company,
                            source_receipt=receipt,
                            invoice_number=result.get('invoice_number', ''),
                            # Izdavatelj = nasa firma
                            issuer_name=company.name,
                            issuer_oib=company.oib,
                            issuer_address=company.address or '',
                            issuer_city=company.city or '',
                            issuer_postal=company.zip_code or '',
                            issuer_country=company.country or 'HR',
                            issuer_iban=company.iban or '',
                            # Primatelj = kupac s POS-a
                            recipient_name=receipt.buyer_name or '',
                            recipient_oib=receipt.buyer_oib,
                            recipient_address=receipt.buyer_address or '',
                            # Iznosi
                            subtotal=receipt.subtotal,
                            tax_amount=receipt.tax_amount,
                            total=receipt.total,
                            issue_date=tz.now().date(),
                            # Fiskalni podaci s POS bona
                            zki=receipt.zki or result.get('zki', ''),
                            jir=receipt.jir or result.get('jir', ''),
                            # Status: vec fiskaliziran kroz POS
                            status='valid',
                            payment_means_code='10' if payment_method == 'CASH' else '48',
                            note='Auto-generirano iz POS R1 bona #%s' % receipt.receipt_number,
                        )
                        logger.info('Auto e-Racun kreiran za R1 bon #%s -> eRacun %s',
                                    receipt.receipt_number, eracun.pk)
                        # Auto-send kroz posrednika ako je konfiguriran
                        try:
                            from eracun.services.posrednik_service import PosrednikService
                            if PosrednikService.is_configured(company):
                                from django.db import transaction as db_tx2
                                db_tx2.on_commit(lambda: PosrednikService.send(eracun))
                                logger.info('e-Racun %s queued za slanje kroz posrednika', eracun.pk)
                        except Exception as pe:
                            logger.warning('Posrednik auto-send skip: %s', pe)
                    except Exception as e:
                        logger.warning('Auto e-Racun failed za bon #%s: %s', receipt.receipt_number, e)
                db_tx.on_commit(_create_eracun)
            except Exception:
                pass

        # ── 11. ACTIVITY EVENT ──
        from worktime.tracker import track
        track(user, 'POS', 'POS_CHECKOUT', ref='Bon #%s' % next_number,
              detail='%s stavki, %s EUR, %s' % (len(items_data), receipt.total, payment_method),
              metadata={'receipt_id': receipt.pk, 'total': str(receipt.total),
                        'payment_method': payment_method, 'items_count': len(items_data)},
              company=company)

        return result

        # ── 12. POS PULSE — AI Anomaly Detection ──
        try:
            from pos.pulse import analyze_receipt
            analyze_receipt(receipt)
        except Exception as _pulse_err:
            logger.warning('Pulse analyze failed: %s', _pulse_err)

        # ── 13. TRAINING MODE — skip fiscal if training ──
        if receipt.is_training:
            result['training'] = True
            result['fiscal_warning'] = 'TRAINING MODE — bon nije fiskaliziran'

        # ── 14. HASH CHAIN — kriptografski audit trail ──
        if not receipt.is_training:
            try:
                from pos.hashchain import append_receipt
                chain_link = append_receipt(receipt)
                result["chain_hash"] = chain_link.chain_hash[:16]
                result["chain_seq"] = chain_link.sequence
            except Exception as _chain_err:
                logger.warning("Hash chain append failed: %s", _chain_err)

