import json
import logging
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse, JsonResponse, Http404
from django.conf import settings
from django.db import models
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import get_template
from django.utils.timezone import now
from django.views.decorators.http import require_POST

from core.company_utils import get_user_company
from core.tenant import get_current_company
from inventory.models import InventoryItem

from .models import POSPaymentLine, POSReceipt, POSReceiptItem, POSSession, POSTerminal, Voucher

logger = logging.getLogger(__name__)


def _recalculate(receipt):
    items = list(receipt.items.all())
    subtotal = Decimal('0')
    tax_total = Decimal('0')
    for item in items:
        net = item.quantity * item.unit_price * (1 - item.discount_percent / 100)
        tax = net * item.tax_rate / 100
        subtotal += net
        tax_total += tax
    receipt.subtotal   = round(subtotal, 2)
    receipt.tax_amount = round(tax_total, 2)
    receipt.total      = round(subtotal + tax_total - receipt.discount, 2)
    receipt.save(update_fields=['subtotal', 'tax_amount', 'total'])


# ── Tenant Isolation Helper ─────────────────────────────────────────
def _check_tenant(request, obj):
    """
    Verify that obj belongs to the requesting user's company.
    Works with POSTerminal, POSSession, POSReceipt.
    Returns (company, None) on success, or (None, HttpResponse) on failure.
    """
    company = get_user_company(request)
    if not company:
        return None, JsonResponse({'ok': False, 'error': 'No company context'}, status=400)
    # Determine obj's company
    obj_company = None
    if hasattr(obj, 'company_id'):
        obj_company = obj.company
    elif hasattr(obj, 'terminal'):
        obj_company = obj.terminal.company
    elif hasattr(obj, 'session'):
        obj_company = obj.session.terminal.company
    if obj_company and obj_company.pk != company.pk:
        raise Http404
    return company, None
# ────────────────────────────────────────────────────────────────────


@login_required
def dashboard(request):
    company = get_user_company(request)
    if company:
        # Otvorena smjena prvo
        open_sess = POSSession.objects.filter(
            terminal__company=company, status='open'
        ).select_related('terminal').first()
        if open_sess:
            return redirect('pos:pos_joker', terminal_id=open_sess.terminal_id)
        # Inače prvi aktivni terminal
        t = POSTerminal.objects.filter(company=company, is_active=True).order_by('id').first()
        if t:
            return redirect('pos:pos_joker', terminal_id=t.pk)
    terminals = POSTerminal.objects.filter(company=company, is_active=True) if company else POSTerminal.objects.none()
    for t in terminals:
        t.active_session = t.sessions.filter(status=POSSession.Status.OPEN).first()
    return render(request, 'pos/dashboard.html', {'terminals': terminals})


@login_required
def terminal_detail(request, terminal_id):
    terminal = get_object_or_404(POSTerminal, pk=terminal_id)
    company, err = _check_tenant(request, terminal)
    if err: return err
    active_session = terminal.sessions.filter(status=POSSession.Status.OPEN).first()
    recent_sessions = terminal.sessions.order_by('-opened_at')[:15]
    return render(request, 'pos/terminal.html', {
        'terminal': terminal, 'active_session': active_session, 'recent_sessions': recent_sessions,
    })


@login_required
@require_POST
@transaction.atomic
def open_session(request, terminal_id):
    # select_for_update: serializes session creation per terminal (race condition fix)
    terminal = get_object_or_404(POSTerminal.objects.select_for_update(), pk=terminal_id)
    company, err = _check_tenant(request, terminal)
    if err: return err
    if terminal.sessions.filter(status=POSSession.Status.OPEN).exists():
        messages.warning(request, 'Terminal already has an open session.')
        return redirect('pos:terminal_detail', terminal_id=terminal_id)
    from django.db.models import Max
    max_num = terminal.sessions.aggregate(m=Max('session_number'))['m'] or 0
    next_num = max_num + 1
    opening_cash = Decimal(request.POST.get('opening_cash', '0') or '0')
    session = POSSession.objects.create(
        terminal=terminal, operator=request.user,
        session_number=next_num, opening_cash=opening_cash,
        status=POSSession.Status.OPEN,
    )
    messages.success(request, f'Session #{session.session_number} opened.')
    return redirect('pos:session_detail', session_id=session.pk)


@login_required
def session_detail(request, session_id):
    session = get_object_or_404(POSSession, pk=session_id)
    company, err = _check_tenant(request, session)
    if err: return err
    open_receipts = session.receipts.filter(status__in=[POSReceipt.Status.OPEN, 'ISSUED']).order_by('-created_at')

    # Auto-redirect: ako je session open i ima tocno 1 otvoren bon, idi direktno na njega
    if session.status == POSSession.Status.OPEN and open_receipts.count() == 1:
        return redirect('pos:receipt_detail', receipt_id=open_receipts.first().pk)

    paid_receipts = session.receipts.filter(status=POSReceipt.Status.PAID).order_by('-paid_at')[:30]
    return render(request, 'pos/session.html', {
        'session': session, 'open_receipts': open_receipts, 'paid_receipts': paid_receipts,
    })


@login_required
@require_POST
@transaction.atomic
def close_session(request, session_id):
    session = get_object_or_404(POSSession, pk=session_id)
    company, err = _check_tenant(request, session)
    if err: return err
    if session.status != POSSession.Status.OPEN:
        messages.warning(request, 'Session is already closed.')
        return redirect('pos:session_detail', session_id=session_id)
    open_count = session.receipts.filter(status__in=[POSReceipt.Status.OPEN, 'ISSUED']).count()
    if open_count:
        messages.error(request, f'Cannot close: {open_count} open receipt(s) pending.')
        return redirect('pos:session_detail', session_id=session_id)
    # Provjera: prazna smjena?
    paid_count = session.receipts.filter(status=POSReceipt.Status.PAID).count()
    force = request.POST.get('force_close', '')
    if paid_count == 0 and not force:
        messages.warning(request, 'Zatvarate smjenu bez ijednog bona. Ako ste sigurni, kliknite ponovo.')
        # Set flag da sljedeći PUT prolazi
        from django.shortcuts import render
        return render(request, 'pos/session.html', {
            'session': session,
            'open_receipts': session.receipts.filter(status__in=[POSReceipt.Status.OPEN, 'ISSUED']),
            'paid_receipts': session.receipts.filter(status=POSReceipt.Status.PAID).order_by('-paid_at')[:30],
            'confirm_empty_close': True,
        })

    closing_cash = Decimal(request.POST.get('closing_cash', '0') or '0')
    session.closing_cash = closing_cash; session.closed_at = now()
    session.status = POSSession.Status.CLOSED; session.save()

    # Auto clock-out svih blagajnika u smjeni
    try:
        from pos.worktime_bridge import session_close_all_cashiers
        session_close_all_cashiers(session)
    except Exception:
        pass
    messages.success(request, f'Session #{session.session_number} closed.')
    # POS Pulse — analyze session close
    try:
        from pos.pulse import analyze_session_close
        analyze_session_close(session)
    except Exception:
        pass
    return redirect('pos:session_detail', session_id=session.pk)


@login_required
@require_POST
@transaction.atomic
def new_receipt(request, session_id):
    # select_for_update: serializes receipt creation per session (race condition fix)
    session = get_object_or_404(POSSession.objects.select_for_update(), pk=session_id)
    if session.status != POSSession.Status.OPEN:
        messages.error(request, 'Session is closed.')
        return redirect('pos:session_detail', session_id=session_id)
    from django.db.models import Max
    max_num = session.receipts.aggregate(m=Max('receipt_number'))['m'] or 0
    next_num = max_num + 1
    receipt = POSReceipt.objects.create(
        session=session, receipt_number=next_num,
        table_number=request.POST.get('table_number', ''),
        note=request.POST.get('note', ''),
    )
    return redirect('pos:receipt_detail', receipt_id=receipt.pk)


@login_required
def receipt_detail(request, receipt_id):
    receipt = get_object_or_404(POSReceipt, pk=receipt_id)
    items = receipt.items.select_related('inventory_item', 'tax_rate_obj').all()
    company = receipt.session.terminal.company  # Fix: koristi company iz terminala
    inventory_items = InventoryItem.objects.filter(company=company, is_active=True).order_by('name')[:300] if company else InventoryItem.objects.none()

    # Top 12 najprodavanijih artikala za brze tipke
    from django.db.models import Count
    top_item_ids = (
        POSReceiptItem.objects
        .filter(receipt__session__terminal__company=company)
        .values('inventory_item_id')
        .annotate(cnt=Count('id'))
        .order_by('-cnt')
        .values_list('inventory_item_id', flat=True)[:12]
    )
    quick_items = []
    if top_item_ids:
        id_list = list(top_item_ids)
        items_map = {i.pk: i for i in InventoryItem.objects.filter(pk__in=id_list, is_active=True)}
        quick_items = [items_map[pk] for pk in id_list if pk in items_map]

    # Ako nema dovoljno prodanih, dopuni abecedno
    if len(quick_items) < 12:
        existing_ids = {i.pk for i in quick_items}
        filler = InventoryItem.objects.filter(company=company, is_active=True).exclude(pk__in=existing_ids).order_by('name')[:12 - len(quick_items)]
        quick_items.extend(filler)

    return render(request, 'pos/receipt.html', {
        'receipt': receipt, 'items': items,
        'inventory_items': inventory_items,
        'quick_items': quick_items,
        'payment_methods': POSPaymentLine.Method.choices,
    })


@login_required
@require_POST
def add_item(request, receipt_id):
    receipt = get_object_or_404(POSReceipt, pk=receipt_id)
    if receipt.status != POSReceipt.Status.OPEN:
        messages.error(request, 'Receipt is closed.')
        return redirect('pos:receipt_detail', receipt_id=receipt_id)
    try:
        quantity = Decimal(request.POST.get('quantity', '1') or '1')
        unit_price = Decimal(request.POST.get('unit_price', '0') or '0')
        tax_rate = Decimal(request.POST.get('tax_rate', '25') or '25')
        discount_pct = Decimal(request.POST.get('discount_percent', '0') or '0')
    except Exception:
        logger.warning("Suppressed error", exc_info=True)
        messages.error(request, 'Invalid numeric values.')
        return redirect('pos:receipt_detail', receipt_id=receipt_id)
    description = request.POST.get('description', '').strip()
    barcode = request.POST.get('barcode', '').strip()
    inventory_id = request.POST.get('inventory_item_id', '').strip()
    kwargs = dict(receipt=receipt, description=description, quantity=quantity,
                  unit_price=unit_price, tax_rate=tax_rate, discount_percent=discount_pct, barcode=barcode)
    if inventory_id:
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

            # ── KARENCA HARD BLOCK (LOT-level preciznost) ───────────
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
                return redirect('pos:receipt_detail', receipt_id=receipt_id)
        except InventoryItem.DoesNotExist:
            pass
    if not kwargs.get('description'):
        messages.error(request, 'Item description is required.')
        return redirect('pos:receipt_detail', receipt_id=receipt_id)
    item = POSReceiptItem.objects.create(**kwargs)
    _recalculate(receipt)

    # ── Korisnicke poruke ──
    desc = kwargs.get('description', 'Artikl')
    messages.success(request, f'{desc} x{quantity} dodan na bon.')

    # ── Stock upozorenje ──
    if inventory_id:
        try:
            inv_item = InventoryItem.objects.get(pk=inventory_id)
            stock = inv_item.quantity or 0
            min_qty = inv_item.min_quantity or 0
            if stock <= 0:
                messages.warning(request, f'Upozorenje: {desc} — zaliha je 0! Nastavite samo ako imate robu.')
            elif min_qty > 0 and stock <= min_qty:
                messages.warning(request, f'Niska zaliha: {desc} — preostalo {stock} {inv_item.unit}. Minimalna kolicina: {min_qty}.')
            # Upozorenje za visok rabat
            if discount_pct > 20:
                messages.info(request, f'Info: Popust {discount_pct}% na {desc}. Provjerite je li ispravan.')
            # Upozorenje za 0 cijenu
            if kwargs.get('unit_price', 0) == 0:
                messages.warning(request, f'Cijena za {desc} je 0.00 EUR — jeste li sigurni?')
        except Exception:
            pass

    return redirect('pos:receipt_detail', receipt_id=receipt_id)


@login_required
@require_POST
def remove_item(request, receipt_id, item_id):
    receipt = get_object_or_404(POSReceipt, pk=receipt_id)
    item = get_object_or_404(POSReceiptItem, pk=item_id, receipt=receipt)
    if receipt.status != POSReceipt.Status.OPEN:
        messages.error(request, 'Receipt is closed.')
        return redirect('pos:receipt_detail', receipt_id=receipt_id)
    item_name = item.description or 'Artikl'
    item.delete(); _recalculate(receipt)
    messages.success(request, f'{item_name} uklonjen s bona.')
    return redirect('pos:receipt_detail', receipt_id=receipt_id)


@login_required
@require_POST
@transaction.atomic
def process_payment(request, receipt_id):
    receipt = get_object_or_404(POSReceipt, pk=receipt_id)
    if receipt.status not in [POSReceipt.Status.OPEN, 'ISSUED']:
        messages.error(request, 'Receipt is already closed.')
        return redirect('pos:receipt_detail', receipt_id=receipt_id)
    if not receipt.items.exists():
        messages.error(request, 'Bon je prazan — dodajte artikle prije naplate.')
        return redirect('pos:receipt_detail', receipt_id=receipt_id)
    if receipt.total <= 0:
        messages.warning(request, 'Ukupan iznos je 0.00 EUR. Provjerite stavke na bonu.')
    # Multi-cashier
    cashier_id = request.POST.get('cashier_id')
    if cashier_id and not receipt.cashier_id:
        from pos.models import POSCashier
        company = receipt.session.terminal.company
        cashier_obj = POSCashier.objects.filter(id=cashier_id, company=company, is_active=True).first()
        if cashier_obj:
            receipt.cashier = cashier_obj
            receipt.save(update_fields=['cashier'])
            receipt.session.active_cashiers.add(cashier_obj)

    method = request.POST.get('payment_method', POSPaymentLine.Method.CASH)
    try:
        amount_paid = Decimal(request.POST.get('amount_paid', str(receipt.total)) or str(receipt.total))
    except Exception:
        logger.warning("Suppressed error", exc_info=True)
        amount_paid = receipt.total
    amount_paid = max(amount_paid, receipt.total)  # never less than total
    change = max(Decimal('0'), amount_paid - receipt.total)
    with transaction.atomic():
        POSPaymentLine.objects.create(receipt=receipt, method=method, amount=receipt.total, change_given=change)
        receipt.status = POSReceipt.Status.PAID
        receipt.paid_at = now()
        receipt.save(update_fields=['status', 'paid_at'])
        # Smanji zalihu (direktan artikl)
        from inventory.models import StockMovement as _SM
        for _pitem in receipt.items.select_related('inventory_item').all():
            if _pitem.inventory_item_id:
                _SM.objects.create(
                    item_id=_pitem.inventory_item_id,
                    movement_type='out',
                    quantity=_pitem.quantity,
                    unit_price=_pitem.unit_price,
                    reason=f'POS bon #{receipt.receipt_number}',
                    performed_by=request.user,
                )
                # BOM auto-deduction: ako artikl ima aktivnu sastavnicu
                try:
                    from calculator.models import BOM as _BOM
                    _boms = _BOM.objects.filter(company=receipt.session.terminal.company,
                        article_id=_pitem.inventory_item_id,
                        is_active=True,
                    ).prefetch_related('items__material')
                    for _bom in _boms:
                        _sold_qty = _pitem.quantity / (_bom.yield_quantity or 1)
                        for _bi in _bom.items.select_related('material').all():
                            _deduct = _bi.net_quantity * _sold_qty
                            _SM.objects.create(
                                item=_bi.material,
                                movement_type='out',
                                quantity=_deduct,
                                unit_price=_bi.material.purchase_price,
                                reason=f'BOM — POS bon #{receipt.receipt_number}',
                                performed_by=request.user,
                            )
                except Exception:
                    logger.warning("Suppressed error", exc_info=True)

    # ── Fiskalizacija (ne blokira plaćanje ako FINA ne odgovori) ──────────────
    try:
        from fiscal.service import fiscalize_pos_receipt
        jir = fiscalize_pos_receipt(receipt)
        if jir:
            messages.success(request,
                f'Bon #{receipt.receipt_number} plaćen i fiskaliziran. '
                f'JIR: {jir[:8]}… | Kusur: €{change:.2f}')
        else:
            messages.success(request, f'Bon #{receipt.receipt_number} plaćen — kusur: €{change:.2f}')
    except Exception as _fisk_err:
        logger.warning(f'Fiskalizacija bon #{receipt.receipt_number}: {_fisk_err}')
        messages.success(request, f'Bon #{receipt.receipt_number} plaćen — kusur: €{change:.2f}')
        messages.warning(request, f'Fiskalizacija nije uspjela: {str(_fisk_err)[:120]}')

    return redirect('pos:session_detail', session_id=receipt.session_id)


@login_required
@require_POST
def cancel_receipt(request, receipt_id):
    receipt = get_object_or_404(POSReceipt, pk=receipt_id)
    if receipt.status == POSReceipt.Status.PAID:
        messages.error(request, 'Plaćeni bon se ne može stornirati.')
        return redirect('pos:receipt_detail', receipt_id=receipt_id)
    reason = request.POST.get('cancel_reason', '').strip()[:200]
    receipt.status = POSReceipt.Status.CANCELLED
    receipt.cancel_reason = reason
    receipt.save(update_fields=['status', 'cancel_reason'])
    messages.warning(request, f'Bon #{receipt.receipt_number} storniran.' + (f' Razlog: {reason}' if reason else ''))
    return redirect('pos:session_detail', session_id=receipt.session_id)


@csrf_exempt
def ai_barcode_lookup(request):
    """AI Vision za prepoznavanje barkoda i proizvoda sa slike."""
    import json, os

    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)

    try:
        data = json.loads(request.body)
    except Exception as e:  # BORG: was bare except
        logger.debug("Exception in pos.views:%d: %s", 447, e)  # BORG
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    code = data.get('code', '').strip()
    image = data.get('image', '')

    if not image:
        return JsonResponse({'code': '', 'name': '', 'note': 'Nema slike'})

    # Gemini Vision — bolji za barkodove i prepoznavanje proizvoda
    api_key = os.environ.get('GEMINI_API_KEY', '')
    if api_key:
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[{
                    'role': 'user',
                    'parts': [
                        {'text': (
                            'Analiziraj ovu sliku proizvoda iz trgovine. '
                            'Trebam:\n'
                            '1. BARKOD — procitaj EAN/UPC barkod ako je vidljiv (brojevi ispod crta)\n'
                            '2. NAZIV — prepoznaj koji je proizvod (proizvodac + naziv + gramaza)\n'
                            '3. CIJENA — procijeni maloprodajnu cijenu u EUR ako mozes\n'
                            '4. KATEGORIJA — food, drink, dessert ili special\n'
                            '\n'
                            'Odgovori SAMO u JSON formatu:\n'
                            '{"code": "1234567890123", "name": "Proizvod 500g", "price": 2.50, "category": "food"}\n'
                            '\n'
                            'Ako ne vidis barkod, ostavi code prazan ali svejedno prepoznaj proizvod.\n'
                            'Ako ne mozes nista prepoznati, vrati: {"code": "", "name": "", "price": 0, "category": "food"}'
                        )},
                        {'inline_data': {'mime_type': 'image/jpeg', 'data': image}},
                    ],
                }],
            )
            text = response.text.strip()
            if text.startswith('```'):
                text = text.split('\n', 1)[1].rsplit('```', 1)[0].strip()
            result = json.loads(text)

            ai_code = str(result.get('code', '')).strip()
            ai_name = str(result.get('name', '')).strip()
            ai_price = result.get('price', 0)
            ai_category = result.get('category', 'food')

            # Ako je AI procitao barkod, probaj naci u bazi
            if ai_code:
                company = get_user_company(request)
                if company:
                    from inventory.models import InventoryItem
                    try:
                        item = InventoryItem.objects.get(barcode=ai_code, company=company, is_active=True)
                        tax_val = 25
                        if item.tax_rate_id:
                            try: tax_val = float(item.tax_rate.rate)
                            except Exception as e:  # BORG: was bare except pass
                                logger.debug("Exception in pos.views:%d: %s", 505, e)  # BORG
                        return JsonResponse({
                            'found': True, 'code': ai_code, 'name': item.name,
                            'id': str(item.pk), 'price': str(item.unit_price), 'tax_rate': tax_val
                        })
                    except InventoryItem.DoesNotExist:
                        pass

            return JsonResponse({
                'code': ai_code, 'name': ai_name,
                'price': ai_price, 'category': ai_category,
            })

        except Exception as e:
            logger.warning('Gemini barcode failed: %s', e)

    # Fallback Claude Haiku
    anthropic_key = os.environ.get('ANTHROPIC_API_KEY', '')
    if anthropic_key and image:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=anthropic_key)
            resp = client.messages.create(
                model='claude-haiku-4-5-20251001',
                max_tokens=300,
                messages=[{
                    'role': 'user',
                    'content': [
                        {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': image}},
                        {'type': 'text', 'text': (
                            'Prepoznaj proizvod na slici. Vrati JSON: '
                            '{"code": "barkod ako vidis", "name": "naziv proizvoda", "price": cijena, "category": "food/drink/dessert/special"}'
                        )}
                    ]
                }]
            )
            text = resp.content[0].text.strip()
            if text.startswith('```'):
                text = text.split('\n', 1)[1].rsplit('```', 1)[0].strip()
            return JsonResponse(json.loads(text))
        except Exception as e:
            logger.warning('Claude barcode failed: %s', e)

    return JsonResponse({'code': '', 'name': '', 'price': 0, 'category': 'food'})


def barcode_lookup(request):
    barcode = request.GET.get('barcode', '').strip()
    if not barcode:
        return JsonResponse({'found': False})
    try:
        item = InventoryItem.objects.get(barcode=barcode, is_active=True)
        tax_rate_val = 25
        if item.tax_rate_id:
            try: tax_rate_val = float(item.tax_rate.rate)
            except Exception: pass
        return JsonResponse({'found': True, 'id': str(item.pk), 'name': item.name,
                             'unit': item.unit, 'price': str(item.unit_price), 'tax_rate': str(tax_rate_val)})
    except InventoryItem.DoesNotExist:
        return JsonResponse({'found': False})

@login_required
def new_terminal(request):
    """Create a new POS terminal — 3-step wizard: Tax rates → Cashier → Type = GO."""
    company = get_user_company(request)
    if not company:
        messages.error(request, 'Nema konteksta tvrtke.')
        return redirect('pos:dashboard')

    if request.method == 'POST':
        import secrets
        from decimal import Decimal

        pos_type = request.POST.get('pos_type', 'quick').strip()
        if pos_type not in ('quick', 'retail', 'restaurant', 'field', 'service', 'reception'):
            pos_type = 'quick'

        # Cashier
        cashier_first = request.POST.get('cashier_first', '').strip()
        cashier_last = request.POST.get('cashier_last', '').strip()
        cashier_name = f'{cashier_first} {cashier_last}'.strip() or 'Blagajnik'
        cashier_oib = request.POST.get('cashier_oib', '').strip()
        cashier_pin = request.POST.get('cashier_pin', '').strip()
        opening_cash = Decimal(request.POST.get('opening_cash', '0') or '0')

        cashier = POSCashier.objects.create(
            company=company, name=cashier_name, oib=cashier_oib,
        )
        if cashier_pin and hasattr(cashier, 'set_pin'):
            cashier.set_pin(cashier_pin)
            cashier.save()

        # Terminal
        type_labels = {'quick': 'Brza blagajna', 'retail': 'Maloprodaja', 'restaurant': 'Restoran',
                      'field': 'Terenska', 'service': 'Usluge', 'reception': 'Recepcija'}
        terminal_code = f'{pos_type[:3].upper()}{secrets.token_hex(2).upper()}'
        count = POSTerminal.objects.filter(company=company).count() + 1
        terminal = POSTerminal.objects.create(
            company=company,
            name=f'{type_labels.get(pos_type, "Blagajna")} {count}',
            terminal_code=terminal_code,
            pos_type=pos_type, is_active=True,
        )

        # Open session
        session = POSSession.objects.create(
            terminal=terminal, operator=request.user,
            session_number=1, opening_cash=opening_cash,
            status='open',
        )
        session.active_cashiers.add(cashier)

        messages.success(request, f'POS "{terminal.name}" spreman!')

        if pos_type == 'restaurant':
            return redirect('pos:restaurant_pos', terminal_id=terminal.pk)
        else:
            return redirect('pos:quick_pos', terminal_id=terminal.pk)

    # GET — prepare wizard context
    from companies.models import TaxRate
    country = getattr(company, 'country', 'HR') or 'HR'

    # Auto-seed tax rates if missing
    if not TaxRate.objects.filter(country=country).exists():
        if country in ('DE', 'AT'):
            for name, rate in [('Standard 19%', 19), ('Ermäßigt 7%', 7), ('Steuerfrei', 0)]:
                TaxRate.objects.get_or_create(country=country, rate=rate, defaults={'name': name})
        elif country == 'SI':
            for name, rate in [('DDV 22%', 22), ('DDV 9.5%', 9.5), ('Oproščeno', 0)]:
                TaxRate.objects.get_or_create(country=country, rate=rate, defaults={'name': name})
        else:
            for name, rate in [('PDV 25%', 25), ('PDV 13%', 13), ('PDV 5%', 5), ('Oslobođeno 0%', 0)]:
                TaxRate.objects.get_or_create(country=country, rate=rate, defaults={'name': name})

    tax_rates = TaxRate.objects.filter(country=country).order_by('-rate')

    pos_types = [
        {'value': 'quick', 'label': 'Brza blagajna', 'icon': '⚡', 'color': '#c9a84c',
         'desc': 'Najbrzi put do naplate. Idealno za pekare, kioske, market.'},
        {'value': 'retail', 'label': 'Maloprodaja', 'icon': '🏪', 'color': '#60a5fa',
         'desc': 'Barkod skener, kategorije, inventura. Za ducane i trgovine.'},
        {'value': 'restaurant', 'label': 'Restoran', 'icon': '🍽️', 'color': '#f97316',
         'desc': 'Stolovi, narudzbe, kuhinja (KDS). Za ugostitelje.'},
        {'value': 'field', 'label': 'Terenska', 'icon': '🚚', 'color': '#22c55e',
         'desc': 'Utovar, ruta, prodaja na terenu, povratnica.'},
        {'value': 'service', 'label': 'Usluge', 'icon': '🔧', 'color': '#a78bfa',
         'desc': 'Za servise, frizere, trenere. Satnica + usluga.'},
        {'value': 'reception', 'label': 'Recepcija', 'icon': '🏨', 'color': '#f472b6',
         'desc': 'Za hotele, apartmane, kampove.'},
    ]

    return render(request, 'pos/new_terminal.html', {
        'company': company,
        'pos_types': pos_types,
        'tax_rates': tax_rates,
        'country': country,
    })


@login_required
def session_zreport(request, session_id):
    """Generate Z-report PDF for a closed session."""
    session = get_object_or_404(POSSession, pk=session_id)
    company, err = _check_tenant(request, session)
    if err: return err
    if session.status == POSSession.Status.OPEN:
        messages.error(request, 'Smjena mora biti zatvorena prije generiranja Z-reporta.')
        return redirect('pos:session_detail', session_id=session_id)

    paid_receipts = list(session.receipts.filter(status=POSReceipt.Status.PAID).prefetch_related('items', 'payment_lines'))
    cancelled_receipts = session.receipts.filter(status=POSReceipt.Status.CANCELLED)

    # Payment method breakdown
    payment_breakdown = {}
    for r in paid_receipts:
        for line in r.payment_lines.all():
            m = line.method
            payment_breakdown[m] = payment_breakdown.get(m, Decimal('0')) + line.amount
    method_labels = dict(POSPaymentLine.Method.choices)
    payment_rows = [(method_labels.get(m, m), amt) for m, amt in payment_breakdown.items()]

    # Tax breakdown
    tax_breakdown = {}
    for r in paid_receipts:
        for item in r.items.all():
            rate = item.tax_rate if item.tax_rate is not None else Decimal("0")
            if rate not in tax_breakdown:
                tax_breakdown[rate] = {'base': Decimal('0'), 'tax': Decimal('0'), 'total': Decimal('0')}
            net = item.quantity * item.unit_price * (1 - item.discount_percent / 100)
            tax = net * rate / 100
            tax_breakdown[rate]['base'] += net
            tax_breakdown[rate]['tax'] += tax
            tax_breakdown[rate]['total'] += net + tax
    tax_rows = sorted(tax_breakdown.items(), key=lambda x: x[0] if x[0] is not None else 0)

    # Mark as Z_DONE
    if session.status == POSSession.Status.CLOSED:
        session.status = POSSession.Status.Z_DONE
        session.save(update_fields=['status'])

    # Cash deposits/withdrawals
    from .models import CashDeposit
    deposits = CashDeposit.objects.filter(session=session).order_by('created_at')
    total_deposits    = sum(d.amount for d in deposits if d.deposit_type == 'deposit')
    total_withdrawals = sum(d.amount for d in deposits if d.deposit_type == 'withdrawal')

    ctx = {
        'session': session,
        'paid_count': len(paid_receipts),
        'cancelled_count': cancelled_receipts.count(),
        'payment_rows': payment_rows,
        'tax_rows': tax_rows,
        'company': session.terminal.company,
        'deposits': deposits,
        'total_deposits': total_deposits,
        'total_withdrawals': total_withdrawals,
    }
    template = get_template('pos/zreport_pdf.html')
    html = template.render(ctx)
    result = BytesIO()
    try:
        import weasyprint
        pdf_bytes = weasyprint.HTML(string=html, base_url=settings.BASE_DIR).write_pdf()
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="Z-report-S{session.session_number}.pdf"'
        return response
        messages.error(request, 'Greska pri generiranju PDF-a.')
    except Exception as e:
        logger.exception("Unexpected error", exc_info=True)
        messages.error(request, f'PDF greska: {e}')
    return redirect('pos:session_detail', session_id=session_id)


@login_required
def receipt_pdf(request, receipt_id):
    """Generate receipt output.
    ?format=thermal  → HTML page with auto window.print() (80mm layout)
    ?format=a4       → xhtml2pdf A4 PDF download
    (default)        → xhtml2pdf thermal PDF (legacy)
    """
    receipt = get_object_or_404(POSReceipt, pk=receipt_id)
    company, err = _check_tenant(request, receipt)
    if err: return err
    fmt = request.GET.get('format', '')
    items = receipt.items.all()

    # FINA QR kod (zakonski obavezan)
    from pos.utils import generate_receipt_qr_base64
    fina_qr_b64 = generate_receipt_qr_base64(receipt)

    # BusinessLocation za PP oznaku
    bl = receipt.session.terminal.business_location

    # PDV razrada po stopama (zakonski obavezna na računu)
    from decimal import Decimal
    tax_breakdown = {}
    for item in items:
        rate = item.tax_rate if item.tax_rate is not None else Decimal('0')
        rate_str = '%s%%' % rate
        if rate_str not in tax_breakdown:
            tax_breakdown[rate_str] = {'base': Decimal('0'), 'tax': Decimal('0'), 'total': Decimal('0')}
        if rate > 0:
            net = item.total_price / (1 + rate / 100)
            tax_amt = item.total_price - net
        else:
            net = item.total_price
            tax_amt = Decimal('0')
        tax_breakdown[rate_str]['base'] += net
        tax_breakdown[rate_str]['tax'] += tax_amt
        tax_breakdown[rate_str]['total'] += item.total_price

    ctx = {
        'receipt': receipt,
        'items': items,
        'company': receipt.session.terminal.company,
        'payment_lines': receipt.payment_lines.all(),
        'terminal': receipt.session.terminal,
        'fina_qr_b64': fina_qr_b64,
        'business_location': bl,
        'tax_breakdown': tax_breakdown,
        'consumption_tax': receipt.consumption_tax_amount if receipt.consumption_tax_amount else None,
    }

    if fmt == 'thermal':
        # Browser-based thermal view — auto window.print() fires on load
        return render(request, 'pos/receipt_thermal.html', ctx)

    elif fmt == 'a4':
        # A4 PDF via xhtml2pdf
        from django.template.loader import get_template as _gt
        tmpl = _gt('pos/receipt_a4_pdf.html')
        html = tmpl.render(ctx)
        try:
            import weasyprint
            pdf_bytes = weasyprint.HTML(string=html, base_url=settings.BASE_DIR).write_pdf()
            response = HttpResponse(pdf_bytes, content_type='application/pdf')
            response['Content-Disposition'] = (
                f'inline; filename="bon-{receipt.receipt_number}-a4.pdf"'
            )
            return response
            messages.error(request, 'Greška pri generiranju A4 PDF-a.')
        except Exception as e:
            logger.exception("Unexpected error", exc_info=True)
            messages.error(request, f'PDF greška: {e}')
        return redirect('pos:receipt_detail', receipt_id=receipt_id)

    else:
        # Legacy: thermal PDF via xhtml2pdf
        template = get_template('pos/receipt_pdf.html')
        html = template.render(ctx)
        try:
            import weasyprint
            pdf_bytes = weasyprint.HTML(string=html, base_url=settings.BASE_DIR).write_pdf()
            response = HttpResponse(pdf_bytes, content_type='application/pdf')
            response['Content-Disposition'] = (
                f'inline; filename="bon-{receipt.receipt_number}.pdf"'
            )
            return response
        except Exception as e:
            logger.exception("Unexpected error", exc_info=True)
            messages.error(request, f'PDF greška: {e}')
        return redirect('pos:receipt_detail', receipt_id=receipt_id)
import json
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.conf import settings
from django.db import models
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import POSPaymentLine, POSReceipt, POSReceiptItem, POSSession, POSTerminal

# ── QUICK POS ─────────────────────────────────────────────────────────────────

POS_TYPE_META = [
    {'value': 'quick',      'label': 'Brza blagajna', 'icon': '⚡', 'desc': 'Najbrži put do naplate. Pekare, kiosci, marketi.', 'recommended': True},
    {'value': 'retail',     'label': 'Maloprodaja',   'icon': '🏪', 'desc': 'Barkod, kategorije, inventura. Dućani.', 'recommended': False},
    {'value': 'restaurant', 'label': 'Restoran',      'icon': '🍽', 'desc': 'Stolovi, narudžbe, kuhinja (KDS).', 'recommended': False},
    {'value': 'field',      'label': 'Terenska',      'icon': '🚚', 'desc': 'Utovar, ruta, prodaja na terenu.', 'recommended': False},
    {'value': 'service',    'label': 'Usluge',        'icon': '🔧', 'desc': 'Satnica, usluge, frizerski saloni.', 'recommended': False},
    {'value': 'reception',  'label': 'Recepcija',     'icon': '🏨', 'desc': 'Hoteli, apartmani, kampovi.', 'recommended': False},
]

_POS_ICON = {t['value']: t['icon'] for t in POS_TYPE_META}


@login_required
def quick_pos_redirect(request):
    """
    FENIX ENTRY POINT — jedan klik do blagajne.

    Logika:
    1. Jedan terminal → direktno na Joker POS (Cashier Gate otvara se automatski)
    2. Jedan terminal s otvorenom smjenom → direktno
    3. Više terminala → smart selector (ne dashboard)
    """
    company = get_user_company(request)
    if not company:
        return redirect('pos:dashboard')

    terminals = list(POSTerminal.objects.filter(
        company=company, is_active=True
    ).order_by('name'))

    if not terminals:
        return redirect('pos:dashboard')

    # ── Slučaj 1: Točno jedan terminal → direktno bez pitanja ──
    if len(terminals) == 1:
        return redirect('pos:pos_joker', terminal_id=terminals[0].pk)

    # ── Slučaj 2: Ima otvorena smjena → idi tamo odmah ──
    for t in terminals:
        if t.sessions.filter(status=POSSession.Status.OPEN).exists():
            return redirect('pos:pos_joker', terminal_id=t.pk)

    # ── Slučaj 3: Više terminala bez sesije → smart selector ──
    for t in terminals:
        t.icon = _POS_ICON.get(t.pos_type, '🖥')
        t.active_session = t.sessions.filter(status=POSSession.Status.OPEN).first()

    return render(request, 'pos/selector.html', {
        'company': company,
        'terminals': terminals,
        'pos_types': POS_TYPE_META,
    })


@login_required
def quick_pos(request, terminal_id):
    """Legacy view — redirects to unified Joker POS."""
    return redirect('pos:pos_joker', terminal_id=terminal_id)


def _quick_pos_legacy(request, terminal_id):
    """Original quick_pos — kept for reference, not called."""
    terminal = get_object_or_404(POSTerminal, pk=terminal_id)
    company = terminal.company
    session  = POSSession.objects.filter(terminal=terminal, status='open').first()

    # ── STROGA PROVJERA: samo 1 aktivan POS (besplatni plan) ──
    # Knjigovođa (role=bookkeeper/superadmin) može svugdje bez limita
    is_bookkeeper = False
    try:
        role = request.user.userprofile.role if hasattr(request.user, 'userprofile') else ''
        is_bookkeeper = role in ('superadmin', 'bookkeeper') or request.user.is_superuser
    except Exception:
        pass

    if not session and not is_bookkeeper:
        other_open = POSSession.objects.filter(
            terminal__company=company, status='open'
        ).exclude(terminal=terminal).select_related('terminal').first()

        if other_open:
            try:
                sub = company.subscriptions.filter(is_active=True).order_by('-valid_from').first()
                max_terminals = 1
                if sub and sub.pricing_plan:
                    max_terminals = sub.pricing_plan.max_locations or 1
            except Exception:
                max_terminals = 1

            open_count = POSSession.objects.filter(
                terminal__company=company, status='open'
            ).count()

            if open_count >= max_terminals:
                return render(request, 'pos/upgrade_terminal.html', {
                    'current_terminal': other_open.terminal,
                    'current_session': other_open,
                    'wanted_terminal': terminal,
                    'max_terminals': max_terminals,
                    'company': company,
                })

    # Auto-otvori sesiju ako ne postoji — redirect na terminal za unos pologa
    if not session and request.user.is_authenticated:
        messages.warning(request, 'Unesite početnu gotovinu prije otvaranja blagajne.')
        return redirect('pos:terminal_detail', terminal_id=terminal.pk)

    try:
        from inventory.models import InventoryItem
        qs = InventoryItem.objects.filter(company=company, is_active=True)
        # Terminal category filter (optika vidi product+service, restoran food+drink itd.)
        if terminal.category_filter:
            cats = [c.strip() for c in terminal.category_filter.split(',') if c.strip()]
            if cats:
                qs = qs.filter(category__in=cats)
        inventory_items = list(
            qs.select_related('tax_rate')
            .order_by('name')[:300]
        )
    except Exception:
        logger.warning("Suppressed error", exc_info=True)
        inventory_items = []

    # Build categories list
    cats = sorted(set(
        getattr(i, 'category', '') or 'Ostalo'
        for i in inventory_items
    ))

    from pos.models import POSCashier
    cashiers = list(
        POSCashier.objects.filter(company=company, is_active=True).order_by('name')
    )

    try:
        from django.urls import reverse
        # reverse() uz i18n_patterns vec vraca /hr/pos/... ne treba dodavati lang prefix
        report_url = reverse('pos:cashier_report_html', args=[session.id]) if session else '#'
    except Exception:
        report_url = '#'

    # Top 12 najprodavanijih = brze tipke
    quick_items = []
    try:
        from django.db.models import Count
        top_ids = list(
            POSReceiptItem.objects
            .filter(receipt__session__terminal__company=company, receipt__status='paid')
            .exclude(is_tip=True)
            .values('inventory_item_id')
            .annotate(cnt=Count('id'))
            .order_by('-cnt')
            .values_list('inventory_item_id', flat=True)[:12]
        )
        if top_ids:
            items_map = {i.pk: i for i in InventoryItem.objects.filter(pk__in=top_ids, is_active=True).select_related('tax_rate')}
            quick_items = [items_map[pk] for pk in top_ids if pk in items_map]
        if len(quick_items) < 12:
            existing = {i.pk for i in quick_items}
            # Filler - filtriraj po category_filter terminala
            filler_qs = InventoryItem.objects.filter(company=company, is_active=True).exclude(pk__in=existing)
            if terminal.category_filter:
                cat_list = [c2.strip() for c2 in terminal.category_filter.split(',') if c2.strip()]
                if cat_list:
                    filler_qs = filler_qs.filter(category__in=cat_list)
            filler = list(filler_qs.select_related('tax_rate').order_by('name')[:12 - len(quick_items)])
            quick_items.extend(filler)
    except Exception:
        pass

    # TASK 1: Terminal limit banner za besplatni plan
    show_upgrade_banner = False
    try:
        from registration.models import CompanySubscription
        sub = CompanySubscription.objects.filter(company=company, is_active=True).first()
        if sub and sub.plan in ('starter', 'micro'):
            active_terms = POSTerminal.objects.filter(company=company, is_active=True).count()
            if active_terms > 1:
                show_upgrade_banner = True
    except Exception:
        pass

    return render(request, 'pos/quick.html', {
        'terminal':           terminal,
        'session':            session,
        'inventory_items':    inventory_items,
        'quick_items':        quick_items,
        'categories':         cats,
        'cashiers':           cashiers,
        'session_report_url': report_url,
        'show_upgrade_banner': show_upgrade_banner,
        'quick_actions_json':  json.dumps(terminal.get_quick_actions()),
    })

# ── POS JOKER — Unified Interface ─────────────────────────────────────────────

POS_TITLE_MAP = {
    'quick': 'Brza blagajna',
    'retail': 'Maloprodaja',
    'restaurant': 'Restoran',
    'field': 'Terenska prodaja',
    'service': 'Usluge',
    'reception': 'Recepcija',
}


@login_required
def pos_joker(request, terminal_id):
    """
    Unified POS view — jedan template za sve pos_type-ove.
    Gastro mod (restaurant) dodaje table grid.
    """
    terminal = get_object_or_404(POSTerminal, pk=terminal_id)
    company = terminal.company
    session = POSSession.objects.filter(terminal=terminal, status='open').first()
    is_gastro = terminal.pos_type == 'restaurant'

    # ── STROGA PROVJERA: samo N aktivnih POS-ova po planu ──
    is_bookkeeper = False
    try:
        role = request.user.userprofile.role if hasattr(request.user, 'userprofile') else ''
        is_bookkeeper = role in ('superadmin', 'bookkeeper') or request.user.is_superuser
    except Exception:
        pass

    if not session and not is_bookkeeper:
        other_open = POSSession.objects.filter(
            terminal__company=company, status='open'
        ).exclude(terminal=terminal).select_related('terminal').first()

        if other_open:
            try:
                sub = company.subscriptions.filter(is_active=True).order_by('-valid_from').first()
                max_terminals = 1
                if sub and sub.pricing_plan:
                    max_terminals = sub.pricing_plan.max_locations or 1
            except Exception:
                max_terminals = 1

            open_count = POSSession.objects.filter(
                terminal__company=company, status='open'
            ).count()

            if open_count >= max_terminals:
                return render(request, 'pos/upgrade_terminal.html', {
                    'current_terminal': other_open.terminal,
                    'current_session': other_open,
                    'wanted_terminal': terminal,
                    'max_terminals': max_terminals,
                    'company': company,
                })

    # Cashier Gate handles session opening — ne redirectamo više
    # Gate modal se otvara na JS strani kad nema aktivne smjene
    # (stari redirect uklonjen: 2026-03-31 — pos/includes/cashier_gate.html)

    # ── Inventory ──
    try:
        from inventory.models import InventoryItem
        qs = InventoryItem.objects.filter(company=company, is_active=True)
        if terminal.category_filter:
            cat_list = [c.strip() for c in terminal.category_filter.split(',') if c.strip()]
            if cat_list:
                qs = qs.filter(category__in=cat_list)
        inventory_items = list(qs.select_related('tax_rate').order_by('name')[:300])
    except Exception:
        logger.warning("Suppressed error", exc_info=True)
        inventory_items = []

    cats = sorted(set(getattr(i, 'category', '') or 'Ostalo' for i in inventory_items))

    from pos.models import POSCashier
    cashiers = list(POSCashier.objects.filter(company=company, is_active=True).order_by('name'))

    try:
        from django.urls import reverse
        report_url = reverse('pos:cashier_report_html', args=[session.id]) if session else '#'
    except Exception:
        report_url = '#'

    # Top 12 najprodavanijih = brze tipke
    quick_items = []
    try:
        from django.db.models import Count
        top_ids = list(
            POSReceiptItem.objects
            .filter(receipt__session__terminal__company=company, receipt__status='paid')
            .exclude(is_tip=True)
            .values('inventory_item_id')
            .annotate(cnt=Count('id'))
            .order_by('-cnt')
            .values_list('inventory_item_id', flat=True)[:12]
        )
        if top_ids:
            items_map = {i.pk: i for i in InventoryItem.objects.filter(pk__in=top_ids, is_active=True).select_related('tax_rate')}
            quick_items = [items_map[pk] for pk in top_ids if pk in items_map]
        if len(quick_items) < 12:
            existing = {i.pk for i in quick_items}
            filler = list(InventoryItem.objects.filter(company=company, is_active=True)
                         .exclude(pk__in=existing).select_related('tax_rate').order_by('name')[:12 - len(quick_items)])
            quick_items.extend(filler)
    except Exception:
        pass

    # Upgrade banner
    show_upgrade_banner = False
    try:
        from registration.models import CompanySubscription
        sub = CompanySubscription.objects.filter(company=company, is_active=True).first()
        if sub and sub.plan in ('starter', 'micro'):
            active_terms = POSTerminal.objects.filter(company=company, is_active=True).count()
            if active_terms > 1:
                show_upgrade_banner = True
    except Exception:
        pass

    ctx = {
        'terminal':           terminal,
        'session':            session,
        'inventory_items':    inventory_items,
        'quick_items':        quick_items,
        'categories':         cats,
        'cashiers':           cashiers,
        'session_report_url': report_url,
        'show_upgrade_banner': show_upgrade_banner,
        'quick_actions_json':  json.dumps(terminal.get_quick_actions()),
        'is_gastro':          is_gastro,
        'pos_title':          POS_TITLE_MAP.get(terminal.pos_type, 'POS'),
    }

    # ── Gastro: tables + open receipts ──
    if is_gastro and session:
        open_receipts = list(
            session.receipts
            .filter(status='open')
            .prefetch_related('items')
            .order_by('table_number', 'receipt_number')
        )
        receipt_by_num = {}
        for r in open_receipts:
            if r.table_number:
                try:
                    n = int(r.table_number)
                    receipt_by_num[n] = r
                except ValueError:
                    pass
        tables = [{'num': i, 'receipt': receipt_by_num.get(i)} for i in range(1, 21)]
        ctx['open_receipts'] = open_receipts
        ctx['tables'] = tables

    return render(request, 'pos/joker.html', ctx)




@csrf_exempt
@require_POST
def quick_pay(request, session_id):
    """AJAX: quick checkout — Thin view, logika u CheckoutService."""
    from pos.services.checkout import CheckoutService, CheckoutValidationError

    # Support both logged-in users and QR sessions
    qr_session_id = request.session.get("qr_session_id")
    is_qr = qr_session_id == session_id

    if not is_qr and not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'error': 'Login required'}, status=403)

    if is_qr:
        sess = get_object_or_404(POSSession, pk=session_id, status="open")
        company = sess.terminal.company
        user = sess.operator
    else:
        company = get_user_company(request)
        user = request.user

    if not company:
        return JsonResponse({'ok': False, 'error': 'Nema konteksta tvrtke'}, status=400)

    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Invalid JSON'}, status=400)

    # Inject session_id from URL
    data['session_id'] = session_id

    try:
        result = CheckoutService.process_receipt(company=company, user=user, payload=data)
        return JsonResponse({
            'ok': True,
            'receipt_id': result['receipt_id'],
            'receipt_number': result['receipt_number'],
            'total': result['total'],
            'change': result['change'],
            'print_url': result.get('print_url', ''),
            'public_url': receipt_public_url(result['receipt_id']),
        })
    except CheckoutValidationError as e:
        return JsonResponse({'ok': False, 'error': e.message, 'code': e.code}, status=400)
    except Exception as e:
        logger.error('quick_pay greska: %s', e, exc_info=True)
        return JsonResponse({'ok': False, 'error': 'Sistemska greska pri naplati'}, status=500)

# ── RESTAURANT POS ────────────────────────────────────────────────────────────

@login_required
def restaurant_pos(request, terminal_id):
    """Legacy view — redirects to unified Joker POS."""
    return redirect('pos:pos_joker', terminal_id=terminal_id)


def _restaurant_pos_legacy(request, terminal_id):
    """Original restaurant_pos — kept for reference, not called."""
    terminal = get_object_or_404(POSTerminal, pk=terminal_id)
    session  = POSSession.objects.filter(terminal=terminal, status='open').first()

    open_receipts = []
    if session:
        open_receipts = list(
            session.receipts
            .filter(status='open')
            .prefetch_related('items')
            .order_by('table_number', 'receipt_number')
        )

    # Build structured tables list (1-20 fixed + any extras)
    used_nums = set()
    receipt_by_num = {}
    for r in open_receipts:
        if r.table_number:
            try:
                n = int(r.table_number)
                receipt_by_num[n] = r
                used_nums.add(n)
            except ValueError:
                pass

    tables = []
    for i in range(1, 21):
        tables.append({'num': i, 'receipt': receipt_by_num.get(i)})

    # Inventory for autocomplete
    try:
        from inventory.models import InventoryItem
        company = get_user_company(request)
        inventory_items = list(
            InventoryItem.objects.filter(company=company, is_active=True)
            .select_related('tax_rate')
            .order_by('name')[:300]
        )
    except Exception:
        logger.warning("Suppressed error", exc_info=True)
        inventory_items = []

    return render(request, 'pos/restaurant.html', {
        'terminal':        terminal,
        'session':         session,
        'open_receipts':   open_receipts,
        'tables':          tables,
        'inventory_items': inventory_items,
    })


# ── RESTAURANT: JSON receipt detail ───────────────────────────────────────

@login_required
def receipt_json(request, receipt_id):
    """Return receipt data as JSON for restaurant panel."""
    from decimal import Decimal
    receipt = get_object_or_404(POSReceipt, pk=receipt_id)
    items = list(receipt.items.values(
        'id', 'description', 'quantity', 'unit_price', 'tax_rate', 'total_price'))
    # Convert Decimal to str for JSON
    def _d(v):
        return str(v) if isinstance(v, Decimal) else v
    items_out = [{k: _d(v) for k, v in it.items()} for it in items]
    return JsonResponse({
        'ok': True,
        'receipt_id': receipt.pk,
        'receipt_number': receipt.receipt_number,
        'total': str(receipt.total),
        'subtotal': str(getattr(receipt, 'subtotal', receipt.total)),
        'tax_amount': str(getattr(receipt, 'tax_amount', Decimal('0'))),
        'items': items_out,
    })


@login_required
@require_POST
def receipt_add_item(request, receipt_id):
    """AJAX: add one item to an open receipt (restaurant POS)."""
    from decimal import Decimal, InvalidOperation
    receipt = get_object_or_404(POSReceipt, pk=receipt_id, status='open')
    try:
        data = json.loads(request.body)
    except Exception:
        logger.warning("Suppressed error", exc_info=True)
        return JsonResponse({'ok': False, 'error': 'Invalid JSON'}, status=400)

    try:
        is_tip = bool(data.get('is_tip', False))
        is_tip_employer = bool(data.get('is_tip_employer', False))
        # Napojnica za radnika uvijek 0% PDV (neoporezivo)
        tax_for_item = Decimal('0') if is_tip else Decimal(str(data.get('tax_rate', 25)))
        item_obj = POSReceiptItem.objects.create(
            receipt=receipt,
            inventory_item_id=data.get('inventory_item_id') or None,
            description=str(data.get('description', ''))[:200],
            quantity=Decimal(str(data.get('quantity', 1))),
            unit='kom',
            unit_price=Decimal(str(data.get('unit_price', 0))),
            tax_rate=tax_for_item,
            is_tip=is_tip,
            is_tip_employer=is_tip_employer,
        )
    except (InvalidOperation, Exception) as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)

    # ── Auto-Pfand: ako artikl ima linked_pfand_item, dodaj kauciju ──────────
    try:
        pfand_inv = None
        inv_id = data.get('inventory_item_id')
        if inv_id:
            from inventory.models import InventoryItem
            try:
                inv = InventoryItem.objects.select_related('linked_pfand_item').get(pk=inv_id)
                pfand_inv = inv.linked_pfand_item
            except InventoryItem.DoesNotExist:
                pass
        if pfand_inv:
            pfand_qty   = item_obj.quantity
            pfand_tax   = pfand_inv.pfand_tax_override
            POSReceiptItem.objects.create(
                receipt=receipt,
                inventory_item=pfand_inv,
                description=pfand_inv.name,
                quantity=pfand_qty,
                unit='kom',
                unit_price=pfand_inv.unit_price,
                tax_rate=pfand_tax,
                is_pfand_return=False,
            )
    except Exception:
        logger.warning("Auto-pfand failed", exc_info=True)

    receipt.recalculate()
    items = list(receipt.items.values(
        'id', 'description', 'quantity', 'unit_price', 'tax_rate', 'total_price'))
    def _d(v):
        from decimal import Decimal
        return str(v) if isinstance(v, Decimal) else v
    items_out = [{k: _d(v) for k, v in it.items()} for it in items]
    return JsonResponse({
        'ok': True,
        'total': str(receipt.total),
        'subtotal': str(getattr(receipt, 'subtotal', receipt.total)),
        'tax_amount': str(getattr(receipt, 'tax_amount', Decimal('0'))),
        'items': items_out,
    })


@login_required
@require_POST
def receipt_pay(request, receipt_id):
    """AJAX: pay an existing open receipt (restaurant POS)."""
    from decimal import Decimal
    receipt = get_object_or_404(POSReceipt, pk=receipt_id, status='open')
    try:
        data = json.loads(request.body)
    except Exception:
        logger.warning("Suppressed error", exc_info=True)
        return JsonResponse({'ok': False, 'error': 'Invalid JSON'}, status=400)

    method      = data.get('method', 'CASH')
    amount_paid = Decimal(str(data.get('amount_paid', '0') or '0'))

    if method == 'CARD':
        amount_paid = receipt.total

    amount_paid = max(amount_paid, receipt.total)  # never less than total
    change = max(Decimal('0'), amount_paid - receipt.total)
    POSPaymentLine.objects.create(
        receipt=receipt,
        method=method,
        amount=amount_paid,
        change_given=change,
    )
    receipt.status  = POSReceipt.Status.PAID
    receipt.paid_at = timezone.now()
    receipt.save()

    try:
        from fiscal.service import fiscalize_pos_receipt
        fiscalize_pos_receipt(receipt)
    except Exception:
        logger.warning("Suppressed error", exc_info=True)

    return JsonResponse({
        'ok': True,
        'receipt_number': receipt.receipt_number,
        'total': str(receipt.total),
        'change': str(change),
        'print_url': f'/pos/receipt/{receipt.pk}/pdf/?format=thermal',
    })


@login_required
@require_POST
def new_receipt_ajax(request, session_id):
    """AJAX: open a new receipt for a table (restaurant POS)."""
    session = get_object_or_404(POSSession, pk=session_id, status='open')
    try:
        data = json.loads(request.body)
    except Exception:
        logger.warning("Suppressed error", exc_info=True)
        data = {}

    table_number = data.get('table_number') or None

    last = session.receipts.order_by('-receipt_number').first()
    receipt_number = (last.receipt_number + 1) if last else 1

    receipt = POSReceipt.objects.create(
        session=session,
        receipt_number=receipt_number,
        table_number=table_number,
    )
    return JsonResponse({'ok': True, 'receipt_id': receipt.pk, 'receipt_number': receipt.receipt_number})


# ══ POS SETTINGS VIEWS ══════════════════════════════════════════════════════════

@login_required
def pos_settings(request):
    """Main POS settings page with 5 tabs."""
    import json as _json
    from datetime import date, timedelta

    from django.db.models import Count, Sum
    from django.db.models.functions import TruncDate

    company = get_user_company(request)
    # Superadmin: koristi firmu iz URL ?company= ili iz zadnjeg terminala
    if request.user.is_superuser:
        from companies.models import Company
        cid = request.GET.get('company', '')
        if cid:
            try:
                company = Company.objects.get(pk=cid)
            except Company.DoesNotExist:
                pass
        if not company or not InventoryItem.objects.filter(company=company, is_active=True).exists():
            # Fallback: firma s najvise artikala
            from django.db.models import Count as _C
            top = (InventoryItem.objects.filter(is_active=True)
                   .values('company').annotate(cnt=_C('id')).order_by('-cnt').first())
            if top:
                company = Company.objects.get(pk=top['company'])
    if not company:
        from companies.models import Company
        company = Company.objects.filter(is_active=True).order_by('name').first()
    if not company:
        return redirect('pos:dashboard')

    from .models import POSCashier as _PC
    from .models import POSSettings as _PS
    settings_obj, _ = _PS.objects.get_or_create(company=company)
    cashiers = list(_PC.objects.filter(company=company, is_active=True))

    # Tax rates
    try:
        from companies.models import TaxRate
        tax_rates = list(TaxRate.objects.all().values('id', 'name', 'rate'))
    except Exception:
        logger.warning("Suppressed error", exc_info=True)
        tax_rates = []

    # Inventory items (first 200)
    try:
        from inventory.models import InventoryItem
        inv_items = list(
            InventoryItem.objects.filter(company=company, is_active=True)
            .select_related('tax_rate_obj')
            .order_by('name')[:200]
        )
        cat_choices = InventoryItem.CATEGORY_CHOICES
    except Exception:
        logger.warning("Suppressed error", exc_info=True)
        inv_items = []
        cat_choices = []

    # Reports: last 30 days
    thirty_ago = date.today() - timedelta(days=30)
    try:
        daily_rev = list(
            POSReceipt.objects
            .filter(session__terminal__company=company, status='paid',
                    paid_at__isnull=False, paid_at__date__gte=thirty_ago)
            .annotate(day=TruncDate('paid_at'))
            .values('day')
            .annotate(total=Sum('total'), count=Count('id'))
            .order_by('day')
        )
    except Exception:
        logger.warning("Suppressed error", exc_info=True)
        daily_rev = []

    try:
        top_items = list(
            POSReceiptItem.objects
            .filter(receipt__session__terminal__company=company, receipt__status='paid')
            .values('description')
            .annotate(qty=Sum('quantity'), revenue=Sum('total_price'))
            .order_by('-revenue')[:10]
        )
    except Exception:
        logger.warning("Suppressed error", exc_info=True)
        top_items = []

    try:
        cashier_rev = list(
            POSReceipt.objects
            .filter(session__terminal__company=company, status='paid')
            .values('session__operator__first_name', 'session__operator__last_name',
                    'session__operator__username')
            .annotate(revenue=Sum('total'), count=Count('id'))
            .order_by('-revenue')[:10]
        )
    except Exception:
        logger.warning("Suppressed error", exc_info=True)
        cashier_rev = []

    chart_labels = _json.dumps([str(r['day']) for r in daily_rev])
    chart_data   = _json.dumps([float(r['total']) for r in daily_rev])

    return render(request, 'pos/settings.html', {
        'settings_obj': settings_obj,
        'cashiers':     cashiers,
        'tax_rates':    tax_rates,
        'inv_items':    inv_items,
        'cat_choices':  cat_choices,
        'top_items':    top_items,
        'cashier_rev':  cashier_rev,
        'chart_labels': chart_labels,
        'chart_data':   chart_data,
    })


@login_required
@require_POST
def settings_save_printer(request):
    from .models import POSSettings as _PS
    company = get_current_company()
    s, _ = _PS.objects.get_or_create(company=company)
    s.printer_type = request.POST.get('printer_type', 'thermal_usb')
    s.printer_ip   = request.POST.get('printer_ip', '').strip()
    try:
        s.printer_port = int(request.POST.get('printer_port', 9100))
    except ValueError:
        s.printer_port = 9100
    # BEZ PAPIRA delivery fields
    rd = request.POST.get('receipt_delivery', '')
    if rd:
        s.receipt_delivery = rd
    ap = request.POST.get('auto_print', '')
    if ap:
        s.auto_print = ap == '1'
    dk = request.POST.get('drawer_kick', '')
    if dk:
        s.drawer_kick = dk == '1'
    wm = request.POST.get('whatsapp_msg', '')
    if wm:
        s.whatsapp_default_msg = wm
    es = request.POST.get('email_subject', '')
    if es:
        s.receipt_email_subject = es
    s.save()
    return JsonResponse({'ok': True, 'message': 'Postavke spremljene'})


@login_required
@require_POST
def settings_save_fiscal(request):
    from .models import POSSettings as _PS
    company = get_current_company()
    s, _ = _PS.objects.get_or_create(company=company)
    if 'fiscal_cert' in request.FILES:
        if s.fiscal_cert:
            try:
                s.fiscal_cert.delete(save=False)
            except Exception:
                logger.warning("Suppressed error", exc_info=True)
        s.fiscal_cert = request.FILES['fiscal_cert']
    pwd = request.POST.get('fiscal_cert_password', '').strip()
    if pwd:
        s.fiscal_cert_password = pwd
    s.fiscal_oib    = request.POST.get('fiscal_oib', '').strip()
    s.fiscal_active = request.POST.get('fiscal_active') == '1'
    s.save()
    return JsonResponse({
        'ok':       True,
        'message':  'Fiskalizacijske postavke spremljene',
        'has_cert': bool(s.fiscal_cert),
        'active':   s.fiscal_active,
    })


@login_required
@require_POST
def settings_test_fiscal(request):
    from .models import POSSettings as _PS
    company = get_current_company()
    s, _ = _PS.objects.get_or_create(company=company)
    if not s.fiscal_cert:
        return JsonResponse({'ok': False, 'error': 'Nije učitan certifikat (.p12)'})
    if not s.fiscal_oib or len(s.fiscal_oib) != 11:
        return JsonResponse({'ok': False, 'error': 'OIB mora imati točno 11 znamenki'})
    try:
        size = s.fiscal_cert.size
        name = s.fiscal_cert.name.split('/')[-1]
        # Try loading via fiskalizacija module
        try:
            from fiscal.service import fiscalize_pos_receipt as _fr  # noqa
            msg = f'Certifikat OK ({name}, {size} B). Fiskalizacija modul dostupan.'
        except ImportError:
            msg = f'Certifikat učitan ({name}, {size} B). Fiskalizacija modul nije konfiguriran.'
        return JsonResponse({'ok': True, 'message': msg})
    except Exception as e:
        logger.exception("Unexpected error", exc_info=True)
        return JsonResponse({'ok': False, 'error': str(e)})


@login_required
def settings_test_print(request):
    from django.utils import timezone as _tz
    company = get_current_company()
    return render(request, 'pos/test_print.html', {
        'company': company,
        'now':     _tz.now(),
    })


@login_required
@require_POST
def cashier_save(request):
    import hashlib
    from decimal import Decimal, InvalidOperation

    from .models import POSCashier as _PC
    company = get_current_company()
    cashier_id = request.POST.get('id') or None
    name = request.POST.get('name', '').strip()
    pin  = request.POST.get('pin', '').strip()
    if not name:
        return JsonResponse({'ok': False, 'error': 'Ime blagajnika je obavezno'})
    if cashier_id:
        cashier = get_object_or_404(_PC, pk=cashier_id, company=company)
    else:
        if not (pin and len(pin) == 4 and pin.isdigit()):
            return JsonResponse({'ok': False, 'error': 'PIN mora biti točno 4 znamenke'})
        cashier = _PC(company=company)
    cashier.name = name
    if pin and len(pin) == 4 and pin.isdigit():
        cashier.pin_hash = hashlib.sha256(pin.encode()).hexdigest()
    cashier.can_void     = request.POST.get('can_void') == '1'
    cashier.can_discount = request.POST.get('can_discount') == '1'
    try:
        cashier.max_discount_percent = Decimal(request.POST.get('max_discount_percent', '0'))
    except InvalidOperation:
        cashier.max_discount_percent = Decimal('0')
    cashier.save()
    return JsonResponse({
        'ok':   True,
        'id':   cashier.pk,
        'name': cashier.name,
        'can_void':     cashier.can_void,
        'can_discount': cashier.can_discount,
        'max_discount_percent': str(cashier.max_discount_percent),
    })


@login_required
@require_POST
def cashier_delete(request, cashier_id):
    from .models import POSCashier as _PC
    cashier = get_object_or_404(_PC, pk=cashier_id, company=get_current_company())
    cashier.is_active = False
    cashier.save()
    return JsonResponse({'ok': True})


@login_required
@require_POST
def inventory_item_save(request):
    from decimal import Decimal, InvalidOperation
    try:
        from inventory.models import InventoryItem
    except ImportError:
        return JsonResponse({'ok': False, 'error': 'Inventory modul nije dostupan'})
    company = get_current_company()
    item_id = request.POST.get('id') or None
    name = request.POST.get('name', '').strip()
    if not name:
        return JsonResponse({'ok': False, 'error': 'Naziv artikla je obavezan'})
    if item_id:
        item = get_object_or_404(InventoryItem, pk=item_id)
    else:
        item = InventoryItem(company=company)
    item.name     = name
    item.sku      = request.POST.get('sku', '').strip()
    item.barcode  = request.POST.get('barcode', '').strip()
    item.category = request.POST.get('category', 'other').strip()
    item.unit     = request.POST.get('unit', 'kom').strip() or 'kom'
    item.description = request.POST.get('description', '').strip()
    try:
        item.purchase_price = Decimal(request.POST.get('purchase_price', '0').replace(',', '.'))
    except InvalidOperation:
        item.purchase_price = Decimal('0')
    try:
        item.unit_price = Decimal(request.POST.get('unit_price', '0').replace(',', '.'))
    except InvalidOperation:
        item.unit_price = Decimal('0')
    tax_rate_id = request.POST.get('tax_rate_id')
    if tax_rate_id:
        try:
            item.tax_rate_obj_id = int(tax_rate_id)
        except (ValueError, TypeError):
            pass
    item.is_active = True
    item.save()
    return JsonResponse({
        'ok':       True,
        'id':       item.pk,
        'name':     item.name,
        'sku':      item.sku,
        'barcode':  item.barcode,
        'unit_price':     str(item.unit_price),
        'purchase_price': str(item.purchase_price),
    })


@login_required
@require_POST
def inventory_csv_import(request):
    import csv
    import io
    from decimal import Decimal, InvalidOperation
    try:
        from companies.models import TaxRate
        from inventory.models import InventoryItem
    except ImportError:
        return JsonResponse({'ok': False, 'error': 'Inventory modul nije dostupan'})
    company = get_current_company()
    csv_file = request.FILES.get('csv_file')
    if not csv_file:
        return JsonResponse({'ok': False, 'error': 'Nema datoteke'})
    try:
        raw = csv_file.read()
        try:
            content = raw.decode('utf-8-sig')
        except UnicodeDecodeError:
            content = raw.decode('latin-1')
        # Detect delimiter
        first_line = content.split('\n')[0]
        delimiter = ';' if first_line.count(';') > first_line.count(',') else ','
        reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
        created = updated = errors = 0
        for row in reader:
            try:
                name = (row.get('name') or row.get('naziv') or row.get('Naziv') or '').strip()
                if not name:
                    continue
                sku = (row.get('sku') or row.get('sifra') or row.get('SKU') or '').strip()
                if sku:
                    item, new = InventoryItem.objects.get_or_create(
                        company=company, sku=sku, defaults={'name': name}
                    )
                else:
                    item, new = InventoryItem.objects.get_or_create(
                        company=company, name=name
                    )
                item.name    = name
                item.sku     = sku
                item.barcode = (row.get('barcode') or row.get('barkod') or '').strip()
                item.category = (row.get('category') or row.get('kategorija') or 'other').strip() or 'other'
                item.unit    = (row.get('unit') or row.get('jmj') or 'kom').strip() or 'kom'
                def _dec(key_list, default='0'):
                    for k in key_list:
                        v = row.get(k, '').strip()
                        if v:
                            try:
                                return Decimal(v.replace(',', '.'))
                            except InvalidOperation:
                                pass
                    return Decimal(default)
                item.purchase_price = _dec(['purchase_price', 'nabavna_cijena', 'nabavna'])
                item.unit_price     = _dec(['unit_price', 'prodajna_cijena', 'prodajna'])
                # Tax rate
                tax_pct = _dec(['tax_rate', 'pdv', 'PDV'], '25')
                tax_obj = TaxRate.objects.filter(rate=tax_pct).first()
                if tax_obj:
                    item.tax_rate_obj = tax_obj
                item.is_active = True
                item.save()
                if new:
                    created += 1
                else:
                    updated += 1
            except Exception:
                logger.warning("Suppressed error", exc_info=True)
                errors += 1
        return JsonResponse({
            'ok':      True,
            'created': created,
            'updated': updated,
            'errors':  errors,
            'message': f'Uvoz završen: {created} novih, {updated} ažuriranih, {errors} grešaka',
        })
    except Exception as e:
        logger.exception("Unexpected error", exc_info=True)
        return JsonResponse({'ok': False, 'error': str(e)})


@login_required
def reports_export(request):
    import csv as _csv
    from datetime import date, timedelta

    from django.db.models import Count, Sum
    from django.db.models.functions import TruncDate
    from django.http import HttpResponse
    fmt   = request.GET.get('format', 'csv')
    rtype = request.GET.get('type', 'daily')
    days  = max(1, min(365, int(request.GET.get('days', 30))))
    company    = get_current_company()
    start_date = date.today() - timedelta(days=days)
    if rtype == 'daily':
        qs = (
            POSReceipt.objects
            .filter(session__terminal__company=company, status='paid',
                    paid_at__isnull=False, paid_at__date__gte=start_date)
            .annotate(day=TruncDate('paid_at'))
            .values('day')
            .annotate(total=Sum('total'), count=Count('id'))
            .order_by('day')
        )
        headers = ['Datum', 'Broj bonova', 'Ukupno (EUR)']
        rows = [(str(r['day']), r['count'], f"{float(r['total']):.2f}") for r in qs]
        fname = f'pos_dnevni_{date.today()}'
    elif rtype == 'items':
        qs = (
            POSReceiptItem.objects
            .filter(receipt__session__terminal__company=company, receipt__status='paid',
                    receipt__paid_at__isnull=False, receipt__paid_at__date__gte=start_date)
            .values('description')
            .annotate(qty=Sum('quantity'), revenue=Sum('total_price'))
            .order_by('-revenue')[:100]
        )
        headers = ['Artikal', 'Količina', 'Prihod (EUR)']
        rows = [(r['description'], f"{float(r['qty']):.3f}", f"{float(r['revenue']):.2f}") for r in qs]
        fname = f'pos_artikli_{date.today()}'
    elif rtype == 'cashiers':
        qs = (
            POSReceipt.objects
            .filter(session__terminal__company=company, status='paid',
                    paid_at__isnull=False, paid_at__date__gte=start_date)
            .values('session__operator__first_name', 'session__operator__last_name',
                    'session__operator__username')
            .annotate(revenue=Sum('total'), count=Count('id'))
            .order_by('-revenue')
        )
        headers = ['Blagajnik', 'Broj bonova', 'Ukupni prihod (EUR)']
        rows = []
        for r in qs:
            name = f"{r.get('session__operator__first_name','')} {r.get('session__operator__last_name','')}".strip() or r.get('session__operator__username', '?')
            rows.append((name, r['count'], f"{float(r['revenue']):.2f}"))
        fname = f'pos_blagajnici_{date.today()}'
    else:
        return HttpResponse('Nepoznat tip izvještaja', status=400)
    if fmt == 'xlsx':
        try:
            from io import BytesIO

            import openpyxl
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = 'Izvještaj'
            # Header style
            from openpyxl.styles import Alignment, Font, PatternFill
            header_fill = PatternFill(start_color='1a1a1a', end_color='1a1a1a', fill_type='solid')
            for col, h in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col, value=h)
                cell.font      = Font(bold=True, color='C9A84C')
                cell.fill      = header_fill
                cell.alignment = Alignment(horizontal='center')
            for row in rows:
                ws.append(list(row))
            for col in ws.columns:
                ws.column_dimensions[col[0].column_letter].width = 20
            buf = BytesIO()
            wb.save(buf)
            buf.seek(0)
            resp = HttpResponse(
                buf.read(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            )
            resp['Content-Disposition'] = f'attachment; filename="{fname}.xlsx"'
            return resp
        except ImportError:
            pass  # fall through to CSV
    # CSV (default / fallback)
    resp = HttpResponse(content_type='text/csv; charset=utf-8')
    resp['Content-Disposition'] = f'attachment; filename="{fname}.csv"'
    resp.write('\ufeff')
    writer = _csv.writer(resp, delimiter=';')
    writer.writerow(headers)
    writer.writerows(rows)
    return resp


# ══════════════════════════════════════════════════════════════════════════════
# GASTRO POS — Dashboard, Kitchen Display, Orders
# ══════════════════════════════════════════════════════════════════════════════

@login_required
def gastro_dashboard(request):
    """Table grid + active orders. Annotates tables with active order for colour coding."""
    from .models import GastroOrder, Table
    tables = list(Table.objects.filter(is_active=True).order_by('floor', 'name'))
    active_orders = list(
        GastroOrder.objects.filter(
            status__in=['new', 'confirmed', 'preparing', 'ready', 'delivering']
        ).select_related('table').prefetch_related('items__inventory_item').order_by('created_at')
    )
    table_order_map = {}
    for o in active_orders:
        if o.table_id and o.table_id not in table_order_map:
            table_order_map[o.table_id] = o
    for t in tables:
        t.active_order = table_order_map.get(t.pk)
    return render(request, 'pos/gastro/dashboard.html', {
        'tables': tables,
        'active_orders': active_orders,
    })


@login_required
def gastro_table_order(request, table_id):
    """Manage order for a specific table."""
    from .models import GastroOrder, Table
    table = get_object_or_404(Table, pk=table_id)
    active_order = GastroOrder.objects.filter(
        table=table, status__in=['new', 'confirmed', 'preparing', 'ready']
    ).prefetch_related('items__inventory_item').first()
    company = get_user_company(request)
    items = InventoryItem.objects.filter(company=company, is_active=True).select_related('tax_rate').order_by('name')[:300]
    return render(request, 'pos/gastro/table_order.html', {
        'table': table,
        'order': active_order,
        'inventory_items': items,
    })


@login_required
def gastro_kitchen(request):
    """Kitchen Display System — renders the kitchen template."""
    return render(request, 'pos/gastro/kitchen.html')


@login_required
def gastro_kitchen_api(request):
    """JSON endpoint for kitchen auto-refresh."""
    from django.utils import timezone as tz

    from .models import GastroOrder
    orders = GastroOrder.objects.filter(
        status__in=['new', 'confirmed', 'preparing']
    ).select_related('table').prefetch_related('items__inventory_item').order_by('created_at')
    data = []
    for o in orders:
        data.append({
            'id': o.pk,
            'table': o.table.name if o.table else 'N/A',
            'floor': o.table.floor if o.table else '',
            'status': o.status,
            'status_display': o.get_status_display(),
            'notes': o.notes,
            'guest_name': o.guest_name,
            'created_at': o.created_at.isoformat(),
            'wait_minutes': int((tz.now() - o.created_at).total_seconds() / 60),
            'items': [
                {
                    'name': i.inventory_item.name if i.inventory_item else 'N/A',
                    'quantity': str(i.quantity),
                    'notes': i.notes,
                    'is_ready': i.is_ready,
                }
                for i in o.items.all()
            ],
        })
    return JsonResponse({'ok': True, 'orders': data})


@login_required
@require_POST
def gastro_order_update(request, order_id):
    """Change order status."""
    from .models import GastroOrder
    order = get_object_or_404(GastroOrder, pk=order_id)
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'ok': False, 'error': 'Invalid JSON'}, status=400)
    new_status = data.get('status')
    valid = dict(GastroOrder.STATUS_CHOICES)
    if new_status and new_status in valid:
        order.status = new_status
        order.save(update_fields=['status', 'updated_at'])
        if order.table and new_status in ('paid', 'cancelled'):
            order.table.is_occupied = False
            order.table.save(update_fields=['is_occupied'])
        elif order.table and new_status not in ('paid', 'cancelled', 'delivered'):
            order.table.is_occupied = True
            order.table.save(update_fields=['is_occupied'])
        return JsonResponse({'ok': True, 'status': order.get_status_display()})
    return JsonResponse({'ok': False, 'error': 'Invalid status'}, status=400)


@login_required
def table_checkout(request, table_id):
    """
    Table checkout — konobar vidi sve stavke za stol,
    može ih podijeliti na pojedinačne račune (split payment per guest).
    GET: prikaži stavke za podjelu
    POST: kreiraj račune i naplati
    """
    from .models import Table, GastroOrder, GastroOrderItem, POSSession, POSTerminal
    from .models import POSReceipt, POSReceiptItem, POSPaymentLine
    from decimal import Decimal

    company = get_user_company(request)
    table = get_object_or_404(Table, pk=table_id, company=company)

    # Sve aktivne narudžbe za stol
    orders = GastroOrder.objects.filter(
        table=table, status__in=['delivered', 'ready', 'confirmed', 'preparing', 'new']
    ).prefetch_related('items__inventory_item')

    # Skupi sve stavke u flat listu
    all_items = []
    for order in orders:
        for item in order.items.select_related('inventory_item'):
            inv = item.inventory_item
            price = inv.unit_price if inv else Decimal('0')
            tax = inv.tax_rate.rate if inv and inv.tax_rate else Decimal('25')
            all_items.append({
                'order_item_id': item.pk,
                'order_id': order.pk,
                'name': inv.name if inv else 'Artikl',
                'quantity': item.quantity,
                'unit_price': price,
                'tax_rate': tax,
                'notes': item.notes,
                'total': price * item.quantity,
            })

    grand_total = sum(i['total'] for i in all_items)

    if request.method == 'POST':
        """
        POST data format:
        {
          "bills": [
            {"guest": "Gost 1", "method": "CASH", "items": [order_item_id, ...]},
            {"guest": "Gost 2", "method": "CARD", "items": [order_item_id, ...]},
          ]
        }
        """
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        bills = data.get('bills', [])
        if not bills:
            return JsonResponse({'error': 'Nema računa za kreiranje'}, status=400)

        # Nađi aktivan terminal i sesiju
        terminal = POSTerminal.objects.filter(company=company, is_active=True).first()
        if not terminal:
            return JsonResponse({'error': 'Nema aktivnog terminala'}, status=400)
        session = POSSession.objects.filter(terminal=terminal, status='open').first()
        if not session:
            return JsonResponse({'error': 'Nema otvorene smjene'}, status=400)

        created_receipts = []
        for bill in bills:
            guest_name = bill.get('guest', 'Gost')
            method = bill.get('method', 'CASH')
            item_ids = bill.get('items', [])
            if not item_ids:
                continue

            # Kreiraj receipt
            from django.utils import timezone
            next_num = (session.receipts.count() or 0) + 1
            receipt = POSReceipt.objects.create(
                session=session,
                receipt_number=next_num,
                table_number=table.name,
                note='Stol %s — %s' % (table.name, guest_name),
                status='paid',
                paid_at=timezone.now(),
            )

            receipt_total = Decimal('0')
            for oi_id in item_ids:
                try:
                    oi = GastroOrderItem.objects.select_related('inventory_item', 'inventory_item__tax_rate').get(pk=oi_id)
                except GastroOrderItem.DoesNotExist:
                    continue
                inv = oi.inventory_item
                price = inv.unit_price if inv else Decimal('0')
                tax = inv.tax_rate.rate if inv and inv.tax_rate else Decimal('25')
                line_total = price * oi.quantity
                POSReceiptItem.objects.create(
                    receipt=receipt,
                    inventory_item=inv,
                    description=inv.name if inv else '',
                    quantity=oi.quantity,
                    unit_price=price,
                    tax_rate=tax,
                    total_price=line_total,
                )
                receipt_total += line_total

            # Update receipt totals
            tax_amount = receipt_total * Decimal('0.2')  # approx, real calc from items
            receipt.total = receipt_total
            receipt.subtotal = receipt_total - tax_amount
            receipt.tax_amount = tax_amount
            receipt.save()

            # Payment line
            POSPaymentLine.objects.create(
                receipt=receipt,
                method=method,
                amount=receipt_total,
            )

            created_receipts.append({
                'receipt_id': receipt.pk,
                'guest': guest_name,
                'total': str(receipt_total),
                'method': method,
            })

        # Fiskalizacija svih racuna
        for cr in created_receipts:
            try:
                from fiscal.service import fiscalize_pos_receipt
                r = POSReceipt.objects.get(pk=cr['receipt_id'])
                jir = fiscalize_pos_receipt(r)
                if jir:
                    cr['jir'] = jir[:12]
            except Exception as e:
                import logging
                logging.getLogger('pos').warning('Fiskalizacija table checkout: %s' % e)
                cr['jir'] = None

        # Zatvori narudžbe i oslobodi stol
        for order in orders:
            order.status = 'paid'
            order.save(update_fields=['status', 'updated_at'])
        table.is_occupied = False
        table.save(update_fields=['is_occupied'])

        return JsonResponse({
            'ok': True,
            'receipts': created_receipts,
            'table': table.name,
        })

    # GET — renderaj checkout stranicu
    return render(request, 'pos/gastro/table_checkout.html', {
        'table': table,
        'orders': orders,
        'all_items': all_items,
        'grand_total': grand_total,
    })


@login_required
@require_POST
def gastro_order_add_item(request, order_id):
    """Add item to a gastro order."""
    from .models import GastroOrder, GastroOrderItem
    order = get_object_or_404(GastroOrder, pk=order_id)
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'ok': False, 'error': 'Invalid JSON'}, status=400)
    inv_id = data.get('inventory_item_id')
    qty = Decimal(str(data.get('quantity', 1)))
    notes = data.get('notes', '')
    item = GastroOrderItem.objects.create(
        order=order,
        inventory_item_id=inv_id,
        quantity=qty,
        notes=notes,
    )
    return JsonResponse({
        'ok': True,
        'item_id': item.pk,
        'name': item.inventory_item.name if item.inventory_item else '',
    })


def gastro_order_public(request, token):
    """Public tracking page for guest (no login)."""
    from .models import GastroOrder
    order = get_object_or_404(GastroOrder, tracking_token=token)
    items = order.items.select_related('inventory_item').all()
    return render(request, 'pos/gastro/public_tracking.html', {
        'order': order,
        'items': items,
    })


def gastro_qr(request, qr_code):
    """QR code menu + ordering (no login required)."""
    from .models import Table, GastroOrder, GastroOrderItem
    table = get_object_or_404(Table.objects.unscoped(), qr_code=qr_code, is_active=True)
    items = InventoryItem.objects.unscoped().filter(
        company=table.company, is_active=True, category__in=["food","drink","dessert","special"]
    ).select_related('tax_rate').order_by('category', 'name')

    if request.method == 'POST':
        import json
        try:
            cart = json.loads(request.POST.get('cart', '[]'))
            guest_name = request.POST.get('guest_name', '').strip()
            guest_email = request.POST.get('guest_email', '').strip()
            notes = request.POST.get('notes', '').strip()

            if not cart:
                return JsonResponse({'error': 'Kosara je prazna.'}, status=400)
            if not guest_name:
                return JsonResponse({'error': 'Ime je obavezno.'}, status=400)

            # B-08 FIX: transaction.atomic + select_for_update za race condition
            with transaction.atomic():
                order = GastroOrder.objects.create(
                    company=table.company,
                    table=table,
                    guest_name=guest_name,
                    guest_email=guest_email,
                    notes=notes,
                    status='new',
                )
                table.is_occupied = True
                table.save(update_fields=['is_occupied'])

                for item in cart:
                    inv_item = InventoryItem.objects.unscoped().filter(
                        pk=item['id'], company=table.company, is_active=True, category__in=["food","drink","dessert","special"]
                    ).first()
                    if inv_item:
                        qty = int(item.get('qty', 1))
                        is_gastro = inv_item.category in ('food', 'drink', 'dessert', 'special')
                        allow_neg = getattr(table.company, 'allow_negative_stock', True)
                        if is_gastro and not allow_neg:
                            # B-08: Lock row to prevent race condition
                            locked = InventoryItem.objects.select_for_update().get(pk=inv_item.pk)
                            if locked.quantity < qty:
                                raise ValueError(f'{locked.name} nije dostupan (dostupno: {locked.quantity})')
                            locked.quantity = locked.quantity - qty
                            locked.save(update_fields=['quantity'])
                        elif is_gastro:
                            # Allow negative stock — still lock to prevent inconsistency
                            locked = InventoryItem.objects.select_for_update().get(pk=inv_item.pk)
                            locked.quantity = locked.quantity - qty
                            locked.save(update_fields=['quantity'])
                        GastroOrderItem.objects.create(
                            order=order,
                            inventory_item=inv_item,
                            quantity=qty,
                            notes=item.get('notes', ''),
                        )
                        # Auto-pfand: add deposit item if linked
                        if inv_item.linked_pfand_item:
                            GastroOrderItem.objects.create(
                                order=order,
                                inventory_item=inv_item.linked_pfand_item,
                                quantity=qty,
                                notes='Povratna ambalaza',
                            )

            # Payment processing
            payment_method = request.POST.get('payment_method', 'cash')
            payment_url = None
            if payment_method in ('stripe', 'btcpay'):
                try:
                    from payments.services import create_payment
                    from decimal import Decimal
                    total = sum(
                        (i.inventory_item.unit_price or 0) * i.quantity
                        for i in order.items.select_related('inventory_item').all()
                    )
                    base_url = request.build_absolute_uri('/').rstrip('/')
                    payment = create_payment(
                        company=table.company,
                        source='gastro_qr',
                        source_id=str(order.pk),
                        amount=Decimal(str(total)),
                        method=payment_method,
                        customer_email=guest_email,
                        customer_name=guest_name,
                        description=f'Narudzba #{order.pk} - {table.name}',
                        success_url=base_url + f'/pos/gastro/order/{order.tracking_token}/',
                        cancel_url=base_url + request.path,
                    )
                    if payment.external_url:
                        payment_url = payment.external_url
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).warning("Payment init failed: %s", e)

            # Loyalty: increment stamps
            if guest_email:
                try:
                    from .models import LoyaltyProgram, GuestLoyalty
                    programs = LoyaltyProgram.objects.filter(company=table.company, is_active=True, category__in=["food","drink","dessert","special"])
                    for prog in programs:
                        loyalty, _ = GuestLoyalty.objects.get_or_create(
                            company=table.company, program=prog, guest_email=guest_email,
                            defaults={'guest_name': guest_name}
                        )
                        loyalty.stamps += 1
                        loyalty.total_spent += sum(
                            (i.inventory_item.unit_price or 0) * i.quantity
                            for i in order.items.select_related('inventory_item').all()
                        )
                        loyalty.save()
                except Exception:
                    pass
            resp_data = {
                'ok': True,
                'tracking_url': f'/pos/gastro/order/{order.tracking_token}/',
                'order_id': order.pk,
            }
            if payment_url:
                resp_data['payment_url'] = payment_url
            return JsonResponse(resp_data)
        except ValueError as e:
            return JsonResponse({'error': str(e)}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return render(request, 'pos/gastro/qr_menu.html', {
        'table': table,
        'inventory_items': items,
    })


# ══════════════════════════════════════════════════════════════════════════════
# EXPIRY TRACKING — Dashboard, Add, API
# ══════════════════════════════════════════════════════════════════════════════

@login_required
def expiry_dashboard(request):
    """Dashboard sorted: expired (red) > today (orange) > warning (gold) > ok."""
    from datetime import date

    from .models import ExpiryBatch
    batches = ExpiryBatch.objects.filter(is_removed=False).select_related(
        'inventory_item'
    ).order_by('expiry_date')
    today = date.today()
    expired = [b for b in batches if b.is_expired]
    today_exp = [b for b in batches if b.expiry_date == today]
    warning = [b for b in batches if b.is_warning and not b.is_expired and b.expiry_date != today]
    ok_items = [b for b in batches if b.days_until_expiry > b.alert_days_before]
    return render(request, 'pos/expiry/dashboard.html', {
        'expired': expired,
        'today_exp': today_exp,
        'warning': warning,
        'ok_items': ok_items,
    })


@login_required
def expiry_add(request):
    """Add a batch with expiry date."""
    from .models import ExpiryBatch
    company = get_current_company()
    if request.method == 'POST':
        inv_id = request.POST.get('inventory_item_id')
        batch_number = request.POST.get('batch_number', '')
        qty = Decimal(request.POST.get('quantity', '0') or '0')
        expiry_date = request.POST.get('expiry_date')
        alert_days = int(request.POST.get('alert_days_before', '3') or '3')
        ExpiryBatch.objects.create(
            company=company,
            inventory_item_id=inv_id,
            batch_number=batch_number,
            quantity=qty,
            expiry_date=expiry_date,
            alert_days_before=alert_days,
        )
        messages.success(request, 'Sarzni rok dodan.')
        return redirect('pos:expiry_dashboard')
    company = get_user_company(request)
    items = InventoryItem.objects.filter(company=company, is_active=True).order_by('name')
    return render(request, 'pos/expiry/add.html', {'items': items})


@login_required
def expiry_alerts_api(request):
    """JSON alerts for notification badge."""
    from .models import ExpiryBatch
    batches = ExpiryBatch.objects.filter(is_removed=False).select_related('inventory_item')
    alerts = []
    for b in batches:
        if b.is_expired or b.is_warning:
            alerts.append({
                'id': b.pk,
                'item_name': b.inventory_item.name,
                'batch_number': b.batch_number,
                'expiry_date': str(b.expiry_date),
                'days_until_expiry': b.days_until_expiry,
                'is_expired': b.is_expired,
                'quantity': str(b.quantity),
            })
    return JsonResponse({'ok': True, 'alerts': alerts, 'count': len(alerts)})


@login_required
@require_POST
def article_quick_create(request):
    import json
    from decimal import Decimal, InvalidOperation
    try:
        data = json.loads(request.body)
    except Exception:
        logger.warning("Suppressed error", exc_info=True)
        data = request.POST

    name = (data.get('name') or '').strip()
    if not name:
        return JsonResponse({'ok': False, 'error': 'Naziv je obavezan.'}, status=400)

    company = get_current_company()
    if not company:
        return JsonResponse({'ok': False, 'error': 'Nema aktivne firme.'}, status=403)

    try:
        from companies.models import TaxRate
        from inventory.models import InventoryItem
    except ImportError:
        return JsonResponse({'ok': False, 'error': 'Inventory modul nije dostupan.'}, status=500)

    # Generate SKU from name if not provided
    sku = (data.get('sku') or '').strip()
    if not sku:
        import re
        base_sku = re.sub(r'[^A-Z0-9]', '', name.upper())[:10] or 'ART'
        sku = base_sku
        counter = 1
        while InventoryItem.objects.filter(company=company, sku=sku).exists():
            sku = f'{base_sku}{counter}'
            counter += 1

    try:
        unit_price = Decimal(str(data.get('price') or '0').replace(',', '.'))
    except InvalidOperation:
        unit_price = Decimal('0')

    tax_rate = None
    tax_rate_id = data.get('tax_rate_id')
    if tax_rate_id:
        try:
            tax_rate = TaxRate.objects.get(pk=int(tax_rate_id))
        except (TaxRate.DoesNotExist, ValueError, TypeError):
            pass

    item = InventoryItem(
        company=company,
        name=name,
        sku=sku,
        category=(data.get('category') or 'other'),
        unit=(data.get('unit') or 'kom'),
        unit_price=unit_price,
        tax_rate=tax_rate,
        is_active=True,
    )
    item.save()

    return JsonResponse({
        'ok': True,
        'id': item.pk,
        'name': item.name,
        'sku': item.sku,
        'unit': item.unit,
        'unit_price': str(item.unit_price),
        'tax_rate': str(tax_rate.rate) if tax_rate else None,
        'created': True,
    }, status=201)


@login_required
def article_search(request):
    """GET /pos/api/articles/search/?q= — search InventoryItem by company"""
    from django.db.models import Q

    from inventory.models import InventoryItem
    q = request.GET.get('q', '').strip()
    company = get_current_company()
    if not company:
        # Superusers don't have thread-local company — fall back to profile
        try:
            company = request.user.profile.company
        except Exception:
            logger.warning("Suppressed error", exc_info=True)
    if not company:
        return JsonResponse({'articles': []})
    qs = InventoryItem.objects.filter(company=company, is_active=True)
    if q:
        qs = qs.filter(
            Q(name__icontains=q) | Q(sku__icontains=q) | Q(barcode__icontains=q)
        )
    articles = []
    for item in qs.select_related('tax_rate')[:50]:
        articles.append({
            'id':             item.pk,
            'name':           item.name,
            'sku':            item.sku,
            'barcode':        item.barcode,
            'price':          str(item.unit_price),
            'purchase_price': str(item.purchase_price),
            'tax_rate':       str(item.tax_rate.rate) if item.tax_rate else '25',
            'unit':           item.unit,
            'category':       item.get_category_display(),
            'stock_qty':      str(item.quantity),
        })
    return JsonResponse({'articles': articles})


# ══════════════════════════════════════════════════════════════
# STANDARDIZIRANI API ENDPOINTI (Gemini JSON Ugovor A/B/C)
# Paralelni s postojećim — ne dira stari kod
# ══════════════════════════════════════════════════════════════

@login_required
def api_pos_items(request):
    """
    Ugovor A: GET /api/pos/items/?page=1&search=naocale&category=food
    Paginirani artikli za POS — lazy load, ne učitava 4798 odjednom.
    """
    company = get_user_company(request)
    if not company:
        return JsonResponse({'status': 'error', 'error': {'code': 'NO_COMPANY', 'message': 'Nema konteksta tvrtke'}}, status=400)

    from django.core.paginator import Paginator
    q = request.GET.get('search', '').strip()
    category = request.GET.get('category', '').strip()
    page_num = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 50))
    per_page = min(per_page, 100)  # Max 100

    qs = InventoryItem.objects.filter(company=company, is_active=True).select_related('tax_rate')
    if q:
        from django.db.models import Q as _Q
        qs = qs.filter(_Q(name__icontains=q) | _Q(sku__icontains=q) | _Q(barcode__icontains=q))
    if category:
        qs = qs.filter(category=category)
    qs = qs.order_by('name')

    paginator = Paginator(qs, per_page)
    page = paginator.get_page(page_num)

    items = []
    for item in page:
        items.append({
            'id': item.pk,
            'name': item.name,
            'sku': item.sku,
            'barcode': item.barcode or '',
            'price': float(item.unit_price),
            'purchase_price': float(item.purchase_price),
            'tax_rate': float(item.tax_rate.rate) if item.tax_rate else 25.0,
            'unit': item.unit,
            'category': item.category,
            'category_display': item.get_category_display(),
            'stock_qty': float(item.quantity),
            'is_weighable': item.is_weighable,
            'is_low_stock': item.is_low_stock,
            'image_url': item.image.url if item.image else '',
        })

    return JsonResponse({
        'status': 'success',
        'data': {
            'items': items,
            'pagination': {
                'current_page': page.number,
                'total_pages': paginator.num_pages,
                'has_next': page.has_next(),
                'has_previous': page.has_previous(),
                'total_items': paginator.count,
                'per_page': per_page,
            },
        },
    })


@login_required
@require_POST
def api_pos_checkout(request):
    """POST /api/pos/checkout/ — Thin view, logika u CheckoutService."""
    from pos.services.checkout import CheckoutService, CheckoutValidationError

    company = get_user_company(request)
    if not company:
        return JsonResponse({'status': 'error', 'error': {'code': 'NO_COMPANY', 'message': 'Nema konteksta tvrtke'}}, status=400)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'status': 'error', 'error': {'code': 'INVALID_JSON', 'message': 'Neispravan JSON'}}, status=400)

    try:
        result = CheckoutService.process_receipt(company=company, user=request.user, payload=data)
        return JsonResponse({'status': 'success', 'data': result})
    except CheckoutValidationError as e:
        return JsonResponse({'status': 'error', 'error': {'code': e.code, 'message': e.message}}, status=400)
    except Exception as e:
        logger.error('POS checkout greska: %s', e, exc_info=True)
        return JsonResponse({'status': 'error', 'error': {'code': 'SYS_ERROR', 'message': 'Sistemska greska pri naplati'}}, status=500)


@login_required
def cash_deposit(request, session_id):
    """Upiši polog ili isplatu gotovine za aktivnu smjenu."""
    from .models import CashDeposit
    session = get_object_or_404(POSSession, pk=session_id)
    if session.status != POSSession.Status.OPEN:
        messages.error(request, 'Polog/isplata je moguća samo na otvorenoj smjeni.')
        return redirect('pos:session_detail', session_id=session_id)

    if request.method == 'POST':
        try:
            from decimal import Decimal
            amount = Decimal(request.POST.get('amount', '0'))
            dtype  = request.POST.get('deposit_type', 'deposit')
            note   = request.POST.get('note', '')
            if amount <= 0:
                messages.error(request, 'Iznos mora biti pozitivan.')
            else:
                CashDeposit.objects.create(
                    session=session,
                    operator=request.user,
                    deposit_type=dtype,
                    amount=amount,
                    note=note,
                )
                label = 'Polog' if dtype == 'deposit' else 'Isplata'
                messages.success(request, f'{label} {amount:.2f} EUR evidentiran.')
        except Exception as e:
            logger.exception("Unexpected error", exc_info=True)
            messages.error(request, f'Greška: {e}')
        return redirect('pos:session_detail', session_id=session_id)

    deposits = CashDeposit.objects.filter(session=session).order_by('-created_at')
    return render(request, 'pos/cash_deposit.html', {
        'session': session,
        'deposits': deposits,
    })


# ══════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════
# BLAGAJNIČKI IZVJEŠTAJ — Globalni, sa svim zakonskim info
# HR: Pravilnik o fiskalizaciji, Zakon o PDV-u
# ══════════════════════════════════════════════════════════════

@login_required
def cashier_full_report(request, session_id):
    """
    Kompletni blagajnički izvještaj — zakonski propisan format.
    Sva logika u ReportingService, view je tanka ljuska za HTTP.
    Dostupan kao: HTML, PDF, JSON
    """
    from pos.services.reporting import ReportingService, ReportingError

    company = get_user_company(request)
    session = get_object_or_404(POSSession, pk=session_id)

    try:
        context = ReportingService.generate_cashier_report(session, company)
    except ReportingError:
        messages.warning(request, 'Smjena mora biti zatvorena za generiranje izvještaja.')
        return redirect('pos:session_detail', session_id=session_id)

    fmt = request.GET.get('format', 'html')
    if fmt == 'json':
        return JsonResponse(ReportingService.to_json(context))

    if fmt == 'pdf':
        from django.template.loader import render_to_string
        html = render_to_string('pos/cashier_full_report_pdf.html', context)
        try:
            from xhtml2pdf import pisa
            from io import BytesIO
            buf = BytesIO()
            pisa.CreatePDF(html, dest=buf)
            buf.seek(0)
            response = HttpResponse(buf.read(), content_type='application/pdf')
            response['Content-Disposition'] = 'inline; filename="blagajnicki_izvjestaj_S%d.pdf"' % session.session_number
            return response
        except ImportError:
            return HttpResponse(html)

    return render(request, 'pos/cashier_full_report.html', context)


# REFUND — Povrat novca gostu (vraća robu, dobiva novac)
# ══════════════════════════════════════════════════════════════

@login_required
def refund_receipt(request, receipt_id):
    """
    Event-Sourced Partial Storno — kreira NOVI negativni bon koji referencira originalni.
    GET: prikaži stavke originalnog računa za odabir (s preostalom količinom)
    POST: {items: [{item_id, quantity}], reason: "..."} → kreira refund receipt
    Immutable: originalni bon se NIKAD ne mijenja.
    """
    company = get_user_company(request)
    original = get_object_or_404(POSReceipt, pk=receipt_id)
    company_chk, err = _check_tenant(request, original)
    if err: return err

    if original.status not in ('paid',):
        return JsonResponse({'error': 'Samo plaćeni računi se mogu refundirati'}, status=400)
    if original.parent_receipt_id:
        return JsonResponse({'error': 'Storno bona se ne može ponovo stornirati'}, status=400)

    # Izračunaj već refundirane količine (double-refund guard)
    from django.db.models import Sum
    already_refunded = {}
    for ref_receipt in original.refund_receipts.exclude(status='cancelled'):
        for ri in ref_receipt.items.all():
            key = ri.description.replace('POVRAT: ', '')
            already_refunded[key] = already_refunded.get(key, Decimal('0')) + abs(ri.quantity)

    if request.method == 'GET':
        items = []
        for ri in original.items.select_related('inventory_item'):
            desc = ri.description or (ri.inventory_item.name if ri.inventory_item else '')
            refunded_qty = already_refunded.get(desc, Decimal('0'))
            remaining_qty = ri.quantity - refunded_qty
            if remaining_qty <= 0:
                continue  # Već potpuno refundirano
            items.append({
                'id': ri.pk,
                'name': desc,
                'quantity': float(ri.quantity),
                'refunded': float(refunded_qty),
                'remaining': float(remaining_qty),
                'unit_price': float(ri.unit_price),
                'total': float(ri.total_price),
                'is_tip': ri.is_tip,
                'is_pfand': ri.is_pfand_return,
            })
        return JsonResponse({
            'ok': True,
            'receipt_number': original.receipt_number,
            'total': float(original.total),
            'paid_at': original.paid_at.isoformat() if original.paid_at else '',
            'items': items,
            'is_fully_refunded': len(items) == 0,
        })

    # POST — kreira refund
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    refund_items = data.get('items', [])
    reason = data.get('reason', 'Povrat robe')[:255]
    if not refund_items:
        return JsonResponse({'error': 'Odaberi stavke za povrat'}, status=400)

    # Nađi aktivnu sesiju
    session = POSSession.objects.filter(
        terminal__company=company, status='open'
    ).first()
    if not session:
        return JsonResponse({'error': 'Nema otvorene smjene'}, status=400)

    from django.utils import timezone as tz
    last_r = session.receipts.order_by('-receipt_number').first()
    next_rn = (last_r.receipt_number + 1) if last_r else 1

    refund_receipt = POSReceipt.objects.create(
        session=session,
        receipt_number=next_rn,
        note='STORNO — Originalni bon #%d | %s' % (original.receipt_number, reason),
        status='refunded',
        paid_at=tz.now(),
        parent_receipt=original,  # Event-sourced link
        cancel_reason=reason,
    )

    from inventory.models import StockMovement as _SM
    _Q = Decimal('0.01')
    refund_total = Decimal('0')
    items_returned = 0
    for ri_data in refund_items:
        try:
            orig_item = original.items.get(pk=ri_data.get('item_id'))
        except POSReceiptItem.DoesNotExist:
            continue
        req_qty = Decimal(str(ri_data.get('quantity', 0)))
        if req_qty <= 0:
            continue

        # Double-refund guard: provjeri preostalu količinu
        desc = orig_item.description or ''
        already = already_refunded.get(desc, Decimal('0'))
        max_qty = orig_item.quantity - already
        qty = min(req_qty, max_qty)
        if qty <= 0:
            continue

        net = (qty * orig_item.unit_price * (1 - orig_item.discount_percent / 100))
        tax = net * orig_item.tax_rate / 100
        total_price = -(net + tax).quantize(_Q, rounding=ROUND_HALF_UP)

        POSReceiptItem.objects.create(
            receipt=refund_receipt,
            inventory_item=orig_item.inventory_item,
            description='POVRAT: %s' % desc,
            quantity=qty,
            unit_price=-orig_item.unit_price,
            discount_percent=orig_item.discount_percent,
            tax_rate=orig_item.tax_rate,
            total_price=total_price,
        )
        refund_total += total_price
        items_returned += 1

        # Vrati u zalihu — ali samo za stockable items!
        if orig_item.inventory_item and orig_item.inventory_item.is_stockable:
            _SM.objects.create(
                item=orig_item.inventory_item,
                movement_type='in',
                quantity=qty,
                unit_price=orig_item.unit_price,
                reason='Storno gosta — POS bon #%d' % original.receipt_number,
                performed_by=request.user,
            )

    refund_receipt.subtotal = refund_total
    refund_receipt.tax_amount = Decimal('0')  # Already included in negative total
    refund_receipt.total = refund_total
    refund_receipt.save(update_fields=['subtotal', 'tax_amount', 'total'])

    # Recalculate properly
    refund_receipt.recalculate()
    refund_receipt.save(update_fields=['subtotal', 'tax_amount', 'total'])

    # Payment line negativna — istim načinom kao originalni
    orig_method = original.payment_lines.first()
    method = orig_method.method if orig_method else 'CASH'
    POSPaymentLine.objects.create(
        receipt=refund_receipt, method=method, amount=refund_receipt.total,
    )

    # Hash chain — storno bon ulazi u lanac kao i svaki drugi
    try:
        from pos.hashchain import append_receipt
        append_receipt(refund_receipt)
    except Exception as e:
        logger.warning('Hash chain append failed for refund #%d: %s', refund_receipt.pk, e)

    return JsonResponse({
        'ok': True,
        'refund_receipt_id': refund_receipt.pk,
        'refund_receipt_number': refund_receipt.receipt_number,
        'parent_receipt_id': original.pk,
        'parent_receipt_number': original.receipt_number,
        'refund_total': str(refund_receipt.total),
        'items_returned': items_returned,
    })


# ══════════════════════════════════════════════════════════════
# PFAND RETURN — Gost vraća ambalažu, dobiva novac natrag
# ══════════════════════════════════════════════════════════════

@login_required
@require_POST
def pfand_return(request):
    """
    Povrat ambalaže — kreira negativnu stavku na aktivnom računu ili novi račun.
    POST {pfand_item_id, quantity, session_id}
    """
    company = get_user_company(request)
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    pfand_id = data.get('pfand_item_id')
    qty = Decimal(str(data.get('quantity', 1)))
    session_id = data.get('session_id')

    pfand_item = InventoryItem.objects.filter(
        pk=pfand_id, company=company, is_pfand=True
    ).first()
    if not pfand_item:
        return JsonResponse({'error': 'Pfand artikl ne postoji'}, status=404)

    session = POSSession.objects.filter(pk=session_id, status='open').first()
    if not session:
        return JsonResponse({'error': 'Nema otvorene smjene'}, status=400)

    from django.utils import timezone as tz
    # Kreiraj "povrat ambalaže" račun
    last_r = session.receipts.order_by('-receipt_number').first()
    next_rn = (last_r.receipt_number + 1) if last_r else 1

    receipt = POSReceipt.objects.create(
        session=session, receipt_number=next_rn,
        note='Povrat ambalaže: %s x%s' % (pfand_item.name, qty),
        status='paid', paid_at=tz.now(),
    )
    amount = -(pfand_item.unit_price * qty)  # Negativan
    POSReceiptItem.objects.create(
        receipt=receipt,
        inventory_item=pfand_item,
        description='POVRAT: %s' % pfand_item.name,
        quantity=qty,
        unit_price=-pfand_item.unit_price,
        tax_rate=pfand_item.pfand_tax_override or Decimal('25'),
        total_price=amount,
        is_pfand_return=True,
    )
    receipt.total = amount
    receipt.save()
    POSPaymentLine.objects.create(receipt=receipt, method='CASH', amount=amount)
    # Vrati u zalihu
    # Vrati u zalihu (in = ambalaža se vraća na skladište)
    from inventory.models import StockMovement as _SM2
    _SM2.objects.create(
        item=pfand_item, movement_type='in', quantity=qty,
        unit_price=pfand_item.unit_price,
        reason='Pfand povrat od gosta', performed_by=request.user,
    )

    return JsonResponse({
        'ok': True,
        'receipt_id': receipt.pk,
        'amount': str(amount),
        'item': pfand_item.name,
    })


# ══════════════════════════════════════════════════════════════
# NAPOJNICA IZVJEŠTAJ — po konobaru
# ══════════════════════════════════════════════════════════════

@login_required
def tip_report(request):
    """Izvještaj napojnica po konobaru/blagajniku."""
    company = get_user_company(request)
    from django.db.models import Sum, Count
    from datetime import date, timedelta

    date_from = request.GET.get('from', '')
    date_to = request.GET.get('to', '')
    try:
        d_from = date.fromisoformat(date_from) if date_from else date.today() - timedelta(days=30)
        d_to = date.fromisoformat(date_to) if date_to else date.today()
    except ValueError:
        d_from = date.today() - timedelta(days=30)
        d_to = date.today()

    # Sve napojnice u periodu
    tips = POSReceiptItem.objects.filter(
        is_tip=True,
        receipt__session__terminal__company=company,
        receipt__status='paid',
        receipt__paid_at__date__gte=d_from,
        receipt__paid_at__date__lte=d_to,
    ).select_related('receipt', 'receipt__cashier')

    # Grupiraj po blagajniku
    by_cashier = {}
    total_tips = Decimal('0')
    for tip in tips:
        cashier_name = tip.receipt.cashier.name if tip.receipt.cashier else tip.receipt.note or 'Nepoznat'
        if cashier_name not in by_cashier:
            by_cashier[cashier_name] = {'count': 0, 'total': Decimal('0'), 'receipts': []}
        by_cashier[cashier_name]['count'] += 1
        by_cashier[cashier_name]['total'] += tip.total_price
        by_cashier[cashier_name]['receipts'].append({
            'receipt_id': tip.receipt.pk,
            'date': tip.receipt.paid_at.strftime('%d.%m.%Y %H:%M') if tip.receipt.paid_at else '',
            'amount': str(tip.total_price),
        })
        total_tips += tip.total_price

    if request.GET.get('format') == 'json':
        result = {}
        for name, data in by_cashier.items():
            result[name] = {'count': data['count'], 'total': str(data['total'])}
        return JsonResponse({
            'ok': True,
            'period': '%s — %s' % (d_from.isoformat(), d_to.isoformat()),
            'total_tips': str(total_tips),
            'by_cashier': result,
        })

    return render(request, 'pos/tip_report.html', {
        'by_cashier': by_cashier,
        'total_tips': total_tips,
        'date_from': d_from.isoformat(),
        'date_to': d_to.isoformat(),
    })


# ── PFAND ITEMS API ──────────────────────────────────────────────────────────

@login_required
def pfand_items_api(request):
    """Return list of pfand (returnable deposit) items for this company."""
    company = get_user_company(request)
    if not company:
        return JsonResponse({'ok': False, 'items': []})
    items = list(
        InventoryItem.objects.filter(company=company, is_pfand=True, is_active=True)
        .values('id', 'name', 'unit_price')
    )
    for it in items:
        it['unit_price'] = str(it['unit_price'])
    return JsonResponse({'ok': True, 'items': items})


# ── VOUCHER VIEWS ─────────────────────────────────────────────────────────────

@login_required
def voucher_list(request):
    """List and create vouchers."""
    from .models import Voucher
    import uuid as _uuid
    from datetime import date

    company = get_user_company(request)
    if not company:
        messages.error(request, 'Nema konteksta tvrtke.')
        return redirect('pos:dashboard')

    if request.method == 'POST':
        amount_str = request.POST.get('amount', '').strip()
        expiry_str = request.POST.get('expiry_date', '').strip()
        notes      = request.POST.get('notes', '').strip()[:200]
        try:
            amount = Decimal(amount_str)
            if amount <= 0:
                raise ValueError('Iznos mora biti > 0')
        except Exception:
            messages.error(request, 'Nevažeći iznos.')
            return redirect('pos:voucher_list')

        expiry = None
        if expiry_str:
            try:
                from datetime import datetime
                expiry = datetime.strptime(expiry_str, '%Y-%m-%d').date()
            except ValueError:
                messages.error(request, 'Nevažeći datum isteka.')
                return redirect('pos:voucher_list')

        year = date.today().year
        code = f'BON-{year}-{_uuid.uuid4().hex[:6].upper()}'
        Voucher.objects.create(
            company=company,
            code=code,
            original_amount=amount,
            remaining=amount,
            expiry_date=expiry,
            notes=notes,
            created_by=request.user,
        )
        messages.success(request, f'Vaučer {code} kreiran ({amount:.2f} EUR).')
        return redirect('pos:voucher_list')

    vouchers = Voucher.objects.filter(company=company).order_by('-created_at')
    return render(request, 'pos/vouchers.html', {'vouchers': vouchers})


@login_required
def voucher_check_api(request):
    """AJAX: check voucher balance by code."""
    from .models import Voucher
    code = request.GET.get('code', '').strip().upper()
    if not code:
        return JsonResponse({'ok': False, 'error': 'Nema koda'})
    company = get_user_company(request)
    try:
        v = Voucher.objects.get(code=code, company=company)
        return JsonResponse({
            'ok': True,
            'code': v.code,
            'remaining': str(v.remaining),
            'original_amount': str(v.original_amount),
            'is_active': v.is_active,
            'is_expired': v.is_expired,
            'is_usable': v.is_usable,
            'expiry_date': str(v.expiry_date) if v.expiry_date else None,
        })
    except Voucher.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Vaučer nije pronađen'})


# ── FISKALNA SOBA ─────────────────────────────────────────────────────────────

@login_required
def fiscal_room(request):
    """Pregled i ručna sinkronizacija nefiskaliziranih računa."""
    from django.db.models import Q
    from django.utils.timezone import now
    from datetime import timedelta
    from fiscal.models import FiscalLog

    company = get_user_company(request)
    threshold = now() - timedelta(hours=36)
    pending_qs = POSReceipt.objects.filter(
        session__terminal__company=company,
        status='paid'
    ).filter(Q(jir__isnull=True) | Q(jir=''))

    last_logs = FiscalLog.objects.filter(config__company=company).order_by('-created_at')[:20] if company else FiscalLog.objects.none()

    return render(request, 'fiscal/room.html', {
        'pending_count':  pending_qs.count(),
        'critical_count': pending_qs.filter(created_at__lt=threshold).count(),
        'pending_list':   pending_qs.order_by('created_at')[:50],
        'last_logs':      last_logs,
    })


@login_required
@require_POST
def fiscal_room_sync(request):
    """AJAX: pokušaj fiskalizacije svih nefiskaliziranih PAID računa."""
    from django.db.models import Q
    from pos.services import _attempt_fiscalization

    company = get_user_company(request)
    pending = POSReceipt.objects.filter(
        session__terminal__company=company,
        status='paid'
    ).filter(Q(jir__isnull=True) | Q(jir=''))

    ok = fail = 0
    for r in pending:
        jir = _attempt_fiscalization(r)
        if jir:
            ok += 1
        else:
            fail += 1

    return JsonResponse({
        'ok': True,
        'synced': ok,
        'failed': fail,
        'message': f'Uspješno: {ok}, Neuspješno: {fail}',
    })


@login_required
def fiscal_status_api(request):
    """AJAX: broj PAID računa koji čekaju fiskalizaciju — per company."""
    from django.db.models import Q
    company = get_user_company(request)
    pending = POSReceipt.objects.filter(
        session__terminal__company=company,
        status='paid'
    ).filter(Q(jir__isnull=True) | Q(jir='')).count()
    return JsonResponse({'pending': pending})


# ══════════════════════════════════════════════════════════════════════════════
# WAITER SYSTEM — Shift, Heartbeat, Claim, Deliver
# ══════════════════════════════════════════════════════════════════════════════

@login_required
def waiter_app(request):
    """Waiter PWA dashboard — shows active orders, claim/deliver buttons."""
    from .models import GastroOrder, WaiterShift
    company = get_user_company(request)
    if not company:
        return render(request, 'pos/waiter/app.html', {'error': 'Nema tvrtke'})

    # Get or check active shift
    active_shift = WaiterShift.objects.filter(
        user=request.user, company=company, is_active=True
    ).first()

    # Active orders
    orders = GastroOrder.objects.filter(
        company=company,
        status__in=['new', 'confirmed', 'preparing', 'ready']
    ).select_related('table', 'claimed_by').prefetch_related('items__inventory_item').order_by('created_at')

    my_orders = [o for o in orders if o.claimed_by == request.user]
    available_orders = [o for o in orders if o.status == 'ready' and not o.claimed_by]
    kitchen_orders = [o for o in orders if o.status in ('new', 'confirmed', 'preparing')]

    # Tables for QR display
    from .models import Table
    tables = Table.objects.filter(company=company, is_active=True).order_by('floor', 'name')

    return render(request, 'pos/waiter/app.html', {
        'active_shift': active_shift,
        'my_orders': my_orders,
        'available_orders': available_orders,
        'kitchen_orders': kitchen_orders,
        'company': company,
        'tables': tables,
    })


@login_required
@require_POST
def waiter_shift_toggle(request):
    """Start or end a waiter shift."""
    from django.utils import timezone
    from .models import WaiterShift
    company = get_user_company(request)
    if not company:
        return JsonResponse({'error': 'Nema tvrtke'}, status=400)

    active = WaiterShift.objects.filter(user=request.user, company=company, is_active=True).first()
    if active:
        active.is_active = False
        active.ended_at = timezone.now()
        active.save(update_fields=['is_active', 'ended_at'])
        return JsonResponse({'ok': True, 'action': 'ended', 'duration': active.duration_display})
    else:
        shift = WaiterShift.objects.create(user=request.user, company=company)
        return JsonResponse({'ok': True, 'action': 'started', 'shift_id': shift.pk})


@login_required
@require_POST
def waiter_heartbeat(request):
    """Heartbeat ping every 5 min from waiter phone."""
    from django.utils import timezone
    from .models import WaiterShift
    company = get_user_company(request)
    if not company:
        return JsonResponse({'ok': False}, status=400)

    shift = WaiterShift.objects.filter(user=request.user, company=company, is_active=True).first()
    if shift:
        shift.last_heartbeat = timezone.now()
        shift.heartbeat_count += 1
        shift.save(update_fields=['last_heartbeat', 'heartbeat_count'])
        return JsonResponse({'ok': True, 'count': shift.heartbeat_count})
    return JsonResponse({'ok': False, 'error': 'Nema aktivne smjene'}, status=400)


@login_required
@require_POST
def waiter_claim_order(request, order_id):
    """Waiter claims a ready order for delivery."""
    from django.utils import timezone
    from .models import GastroOrder, WaiterShift
    order = get_object_or_404(GastroOrder, pk=order_id)

    if order.claimed_by and order.claimed_by != request.user:
        return JsonResponse({'error': 'Narudzba je vec preuzeta.'}, status=400)

    order.claimed_by = request.user
    order.claimed_at = timezone.now()
    order.status = 'delivering'
    order.save(update_fields=['claimed_by', 'claimed_at', 'status', 'updated_at'])

    # Update shift stats
    WaiterShift.objects.filter(
        user=request.user, is_active=True
    ).update(total_orders_claimed=models.F('total_orders_claimed') + 1)

    name = request.user.get_full_name() or request.user.username
    return JsonResponse({'ok': True, 'waiter': name})


@login_required
@require_POST
def waiter_deliver_order(request, order_id):
    """Waiter marks order as delivered."""
    from django.utils import timezone
    from .models import GastroOrder, WaiterShift
    order = get_object_or_404(GastroOrder, pk=order_id)

    order.delivered_by = request.user
    order.delivered_at = timezone.now()
    order.status = 'delivered'
    order.save(update_fields=['delivered_by', 'delivered_at', 'status', 'updated_at'])

    # Update shift stats
    WaiterShift.objects.filter(
        user=request.user, is_active=True
    ).update(total_orders_delivered=models.F('total_orders_delivered') + 1)

    name = request.user.get_full_name() or request.user.username
    return JsonResponse({'ok': True, 'waiter': name})


@login_required
def waiter_shift_log(request):
    """Manager view: all waiter shifts with heartbeat status."""
    from .models import WaiterShift
    company = get_user_company(request)
    shifts = WaiterShift.objects.filter(company=company).select_related('user').order_by('-started_at')[:50]
    active_shifts = [s for s in shifts if s.is_active]
    past_shifts = [s for s in shifts if not s.is_active]
    return render(request, 'pos/waiter/shift_log.html', {
        'active_shifts': active_shifts,
        'past_shifts': past_shifts,
    })


def kitchen_tablet(request, token):
    """Kitchen display — NO LOGIN, accessed by company token.
    URL: /pos/gastro/kds/<company_token>/
    Always-on tablet screen showing orders."""
    from companies.models import Company
    from .models import Table
    company = Company.objects.filter(id=token).first()
    if not company:
        return render(request, 'pos/waiter/kds.html', {'error': 'Nepoznat token'})
    return render(request, 'pos/waiter/kds.html', {'company': company, 'token': token})


def kitchen_tablet_api(request, token):
    """JSON API for kitchen tablet — no login."""
    from django.utils import timezone as tz
    from companies.models import Company
    from .models import GastroOrder
    company = Company.objects.filter(id=token).first()
    if not company:
        return JsonResponse({'error': 'Invalid token'}, status=404)

    orders = GastroOrder.objects.filter(
        company=company,
        status__in=['new', 'confirmed', 'preparing', 'ready']
    ).select_related('table', 'claimed_by').prefetch_related('items__inventory_item').order_by('created_at')

    data = []
    for o in orders:
        waiter_name = ''
        if o.claimed_by:
            waiter_name = o.claimed_by.get_full_name() or o.claimed_by.username
        data.append({
            'id': o.pk,
            'table': o.table.name if o.table else 'N/A',
            'floor': o.table.floor if o.table else '',
            'status': o.status,
            'guest_name': o.guest_name,
            'notes': o.notes,
            'waiter': waiter_name,
            'created_at': o.created_at.isoformat(),
            'wait_minutes': int((tz.now() - o.created_at).total_seconds() / 60),
            'items': [
                {'name': i.inventory_item.name if i.inventory_item else '?', 'qty': str(i.quantity), 'notes': i.notes}
                for i in o.items.all()
            ],
        })
    return JsonResponse({'ok': True, 'orders': data})


@csrf_exempt
def kitchen_tablet_action(request, token, order_id):
    """Kitchen tablet changes order status (confirm/ready) — no login."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)
    from companies.models import Company
    from .models import GastroOrder
    company = Company.objects.filter(id=token).first()
    if not company:
        return JsonResponse({'error': 'Invalid'}, status=404)

    order = GastroOrder.objects.filter(pk=order_id, company=company).first()
    if not order:
        return JsonResponse({'error': 'Not found'}, status=404)

    try:
        data = json.loads(request.body)
    except Exception:
        data = {}

    new_status = data.get('status', '')
    # Tablet can only: confirm, start preparing, mark ready
    allowed = {'confirmed', 'preparing', 'ready'}
    if new_status not in allowed:
        return JsonResponse({'error': 'Nedozvoljeni status'}, status=400)

    # Track koji kuhar je obradio (ako je skenirao barcode)
    cook_name = data.get('cook_name', '')
    if cook_name:
        order.notes = ('%s | Kuhar: %s' % (order.notes or '', cook_name)).strip(' |')

    order.status = new_status
    order.save(update_fields=['status', 'updated_at', 'notes'])
    return JsonResponse({'ok': True, 'status': new_status, 'cook': cook_name})


@csrf_exempt
def kitchen_cook_scan(request, token):
    """
    KDS cook barcode scan — identificira kuhara, pokreće radno vrijeme.
    POST {barcode_data: "LC-DEV-XXXXXXXX"}
    Returns {ok, cook_name, shift_started}
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)
    from companies.models import Company
    from accounts.models import DeviceToken
    import json as _json

    company = Company.objects.filter(id=token).first()
    if not company:
        return JsonResponse({'error': 'Invalid token'}, status=404)

    try:
        data = _json.loads(request.body)
    except Exception:
        data = {}

    barcode = data.get('barcode_data', '').strip()
    if not barcode:
        return JsonResponse({'error': 'barcode_data obavezan'}, status=400)

    dt = DeviceToken.objects.filter(
        barcode_data=barcode, company=company, is_active=True
    ).select_related('user').first()
    if not dt:
        return JsonResponse({'error': 'Nepoznat barcode'}, status=404)

    # Pokreni radno vrijeme za kuhara
    from pos.worktime_bridge import device_login_start_all
    ip = request.META.get('HTTP_X_REAL_IP', request.META.get('REMOTE_ADDR', ''))
    result = device_login_start_all(dt, ip_address=ip)

    from django.utils import timezone
    dt.last_used_at = timezone.now()
    dt.last_ip = ip
    dt.save(update_fields=['last_used_at', 'last_ip'])

    return JsonResponse({
        'ok': True,
        'cook_name': dt.user.get_full_name() or dt.user.username,
        'started': result.get('started', []),
    })


# ── Gastro Reviews ──────────────────────────────────────────────────────────────

def gastro_order_review(request, tracking_token):
    """Guest submits review after order delivered/paid."""
    from .models import GastroOrder, GastroReview
    order = get_object_or_404(GastroOrder, tracking_token=tracking_token)

    # Check if already reviewed
    if hasattr(order, 'review'):
        return render(request, 'pos/gastro/review_thanks.html', {
            'order': order, 'review': order.review
        })

    if request.method == 'POST':
        rating = int(request.POST.get('rating', 5))
        rating = max(1, min(5, rating))

        review = GastroReview.objects.create(
            company=order.company,
            order=order,
            guest_name=order.guest_name or 'Gost',
            guest_email=order.guest_email or '',
            rating=rating,
            comment=request.POST.get('comment', '').strip(),
            food_rating=int(request.POST.get('food_rating') or 0) or None,
            service_rating=int(request.POST.get('service_rating') or 0) or None,
            ambience_rating=int(request.POST.get('ambience_rating') or 0) or None,
        )

        return render(request, 'pos/gastro/review_thanks.html', {
            'order': order, 'review': review
        })

    return render(request, 'pos/gastro/review_form.html', {'order': order})


def gastro_reviews_public(request, company_id):
    """Public reviews page for a company — embeddable on website."""
    from companies.models import Company
    from .models import GastroReview
    from django.db.models import Avg

    company = get_object_or_404(Company, pk=company_id)
    reviews = GastroReview.objects.filter(company=company, is_published=True)

    stats = reviews.aggregate(
        avg_rating=Avg('rating'),
        avg_food=Avg('food_rating'),
        avg_service=Avg('service_rating'),
        avg_ambience=Avg('ambience_rating'),
    )

    return render(request, 'pos/gastro/reviews_public.html', {
        'company': company,
        'reviews': reviews[:50],
        'stats': stats,
        'total': reviews.count(),
        'tv_mode': request.GET.get('tv') == '1',
    })


@login_required
@require_POST
def cashier_pin_verify(request):
    """Verificiraj blagajnikov PIN — vraca cashier_id i ime za frontend tracking."""
    from pos.models import POSCashier
    import json
    from django.core.cache import cache

    body = json.loads(request.body) if request.content_type == 'application/json' else request.POST
    pin = body.get('pin', '')
    session_id = body.get('session_id', '')

    if not pin:
        return JsonResponse({'ok': False, 'error': 'PIN je obavezan'})

    # Rate limiting: max 5 pokusaja po IP u 60 sekundi
    ip = request.META.get('HTTP_X_REAL_IP') or request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
    if ',' in ip:
        ip = ip.split(',')[0].strip()
    rate_key = 'pin_attempts:%s' % ip
    attempts = cache.get(rate_key, 0)
    if attempts >= 5:
        return JsonResponse({'ok': False, 'error': 'Previše pokušaja. Pričekajte 60 sekundi.'}, status=429)

    company = get_user_company(request)
    cashiers = POSCashier.objects.filter(company=company, is_active=True)

    for cashier in cashiers:
        if cashier.check_pin(pin):
            # Reset rate limit on success
            cache.delete(rate_key)

            # Track cashier in session
            if session_id:
                from pos.models import POSSession
                session = POSSession.objects.filter(id=session_id, status='open').first()
                if session:
                    session.active_cashiers.add(cashier)

            # Auto clock-in za worktime evidenciju
            from pos.worktime_bridge import cashier_clock_in
            cashier_clock_in(cashier)

            return JsonResponse({
                'ok': True,
                'cashier_id': cashier.id,
                'cashier_name': cashier.name,
                'can_void': cashier.can_void,
                'can_discount': cashier.can_discount,
                'max_discount': float(cashier.max_discount_percent),
            })

    # Increment rate limit on failure (atomski)
    try:
        cache.incr(rate_key)
    except ValueError:
        cache.set(rate_key, 1, 60)
    remaining = max(0, 4 - attempts)
    return JsonResponse({'ok': False, 'error': 'Neispravan PIN. Preostalo pokusaja: %d' % remaining})


# ════════════════════════════════════════════════════════════
# WEBSHOP — Roba od jučer + javna stranica
# ════════════════════════════════════════════════════════════

def webshop_public(request, slug):
    """Javna webshop stranica za firmu."""
    from companies.models import Company
    from inventory.models import InventoryItem
    company = Company.objects.filter(booking_slug=slug).first()
    if not company:
        company = Company.objects.filter(name__icontains=slug.replace('-',' ')[:20]).first()
    if not company:
        from django.http import Http404
        raise Http404

    items = InventoryItem.objects.filter(
        company=company, is_active=True, webshop_visible=True
    ).order_by('category', 'name')

    # Roba od jučer
    from datetime import date, timedelta
    today = date.today()
    from django.db import connection as _conn
    cursor = _conn.cursor()
    cursor.execute(
        'SELECT d.id, d.inventory_item_id, d.original_price, d.discount_price, d.discount_pct, '
        'd.quantity_available, d.production_date, d.expiry_date, d.is_vacuum_packed, d.storage_instructions, '
        'i.name, i.category, i.image '
        'FROM pos_dailydiscount d JOIN inventory_inventoryitem i ON d.inventory_item_id = i.id '
        'WHERE d.company_id = %s AND d.is_active = TRUE AND d.expiry_date >= %s '
        'ORDER BY d.expiry_date, i.name',
        [str(company.id), today]
    )
    columns = [col[0] for col in cursor.description]
    yesterday_items = [dict(zip(columns, row)) for row in cursor.fetchall()]

    categories = {}
    for item in items:
        cat = item.get_category_display() if hasattr(item, 'get_category_display') else (item.category or 'Ostalo')
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(item)

    return render(request, 'pos/webshop_public.html', {
        'company': company,
        'categories': categories,
        'yesterday_items': yesterday_items,
        'today': today,
    })


@login_required
def yesterday_manage(request):
    """Upravljanje robom od jučer — dodaj/makni artikle."""
    from core.company_utils import get_user_company
    from inventory.models import InventoryItem
    from datetime import date, timedelta
    from django.db import connection as _conn

    company = get_user_company(request)
    if not company:
        messages.error(request, 'Nema aktivne firme.')
        return redirect('/')

    today = date.today()
    yesterday = today - timedelta(days=1)

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'add':
            item_ids = request.POST.getlist('item_id')
            quantities = request.POST.getlist('quantity')
            discount = int(request.POST.get('discount_pct', 50))
            is_vacuum = 'vacuum' in request.POST
            shelf_days = int(request.POST.get('shelf_days', 2))

            cursor = _conn.cursor()
            added = 0
            for item_id, qty in zip(item_ids, quantities):
                if not item_id or not qty: continue
                try:
                    item = InventoryItem.objects.get(pk=int(item_id), company=company)
                    orig = float(item.unit_price or 0)
                    disc = round(orig * (1 - discount / 100), 2)
                    exp = yesterday + timedelta(days=shelf_days)

                    cursor.execute(
                        'INSERT INTO pos_dailydiscount '
                        '(company_id, inventory_item_id, original_price, discount_price, discount_pct, '
                        'quantity_available, production_date, expiry_date, is_vacuum_packed, '
                        'storage_instructions, is_active, created_by_id) '
                        'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE, %s)',
                        [str(company.id), item.pk, orig, disc, discount,
                         float(qty), yesterday, exp, is_vacuum,
                         'Vakumirano. Čuvati na hladnom.' if is_vacuum else 'Čuvati na suhom i hladnom mjestu. Potrošiti do %s.' % exp.strftime('%d.%m.%Y'),
                         request.user.pk]
                    )
                    added += 1
                except Exception as e:
                    messages.error(request, str(e)[:100])
            messages.success(request, '%d artikala dodano u "Roba od jučer".' % added)

        elif action == 'deactivate':
            dd_id = request.POST.get('dd_id')
            cursor = _conn.cursor()
            cursor.execute('UPDATE pos_dailydiscount SET is_active = FALSE WHERE id = %s AND company_id = %s',
                           [dd_id, str(company.id)])
            messages.success(request, 'Uklonjeno iz ponude.')

        return redirect('pos:yesterday_manage')

    # Active yesterday items
    cursor = _conn.cursor()
    cursor.execute(
        'SELECT d.id, i.name, i.category, d.original_price, d.discount_price, d.discount_pct, '
        'd.quantity_available, d.production_date, d.expiry_date, d.is_vacuum_packed, d.created_at '
        'FROM pos_dailydiscount d JOIN inventory_inventoryitem i ON d.inventory_item_id = i.id '
        'WHERE d.company_id = %s AND d.is_active = TRUE ORDER BY d.expiry_date',
        [str(company.id)]
    )
    cols = [c[0] for c in cursor.description]
    active_items = [dict(zip(cols, row)) for row in cursor.fetchall()]

    # All inventory items for adding
    all_items = InventoryItem.objects.filter(company=company, is_active=True, category='food').order_by('name')

    return render(request, 'pos/yesterday_manage.html', {
        'active_items': active_items,
        'all_items': all_items,
        'today': today,
        'yesterday': yesterday,
    })


@login_required
def cashier_report(request, session_id, cashier_id):
    """AJAX: Izvjestaj prometa za jednog blagajnika u smjeni."""
    from django.db import connection
    session = get_object_or_404(POSSession, pk=session_id)
    cashier = get_object_or_404(POSCashier, pk=cashier_id)

    with connection.cursor() as cur:
        cur.execute("""
            SELECT
                COUNT(DISTINCT r.id)                                          AS racuna,
                COALESCE(SUM(pl.amount) FILTER (WHERE pl.method='CASH'),  0) AS gotovina,
                COALESCE(SUM(pl.amount) FILTER (WHERE pl.method='CARD'),  0) AS kartica,
                COALESCE(SUM(pl.amount) FILTER (WHERE pl.method='VOUCHER'),0) AS vavceri,
                COALESCE(SUM(r.total), 0)                                     AS ukupno,
                MIN(r.paid_at)                                                AS prvi_racun,
                MAX(r.paid_at)                                                AS zadnji_racun
            FROM pos_posreceipt r
            LEFT JOIN pos_pospaymentline pl ON pl.receipt_id = r.id
            WHERE r.session_id = %s
              AND r.cashier_id  = %s
              AND r.status      = 'paid'
        """, [session_id, cashier_id])
        row = cur.fetchone()

    racuna, gotovina, kartica, vavceri, ukupno, prvi, zadnji = row

    # Zadnjih 10 računa ovog blagajnika
    receipts = (
        POSReceipt.objects
        .filter(session_id=session_id, cashier_id=cashier_id, status='paid')
        .order_by('-paid_at')[:10]
    )

    def fmt(dt):
        return dt.strftime('%H:%M') if dt else '-'

    return JsonResponse({
        'cashier':   cashier.name,
        'racuna':    racuna or 0,
        'gotovina':  str(gotovina or 0),
        'kartica':   str(kartica  or 0),
        'vavceri':   str(vavceri  or 0),
        'ukupno':    str(ukupno   or 0),
        'prvi':      fmt(prvi),
        'zadnji':    fmt(zadnji),
        'receipts':  [
            {
                'broj':    r.receipt_number,
                'ukupno':  str(r.total),
                'vrijeme': fmt(r.paid_at),
            }
            for r in receipts
        ],
    })


@login_required
def cashier_report_html(request, session_id):
    """HTML: Izvjestaj svih blagajnika u smjeni — za managera."""
    from django.db import connection
    session = get_object_or_404(POSSession, pk=session_id)

    with connection.cursor() as cur:
        cur.execute("""
            SELECT
                COALESCE(c.name, 'Nepoznat')                                   AS blagajnik,
                COUNT(DISTINCT r.id)                                           AS racuna,
                COALESCE(SUM(pl.amount) FILTER (WHERE pl.method='CASH'),  0)  AS gotovina,
                COALESCE(SUM(pl.amount) FILTER (WHERE pl.method='CARD'),  0)  AS kartica,
                COALESCE(SUM(pl.amount) FILTER (WHERE pl.method='VOUCHER'),0) AS vavceri,
                COALESCE(SUM(r.total), 0)                                      AS ukupno,
                MIN(r.paid_at)                                                 AS prvi,
                MAX(r.paid_at)                                                 AS zadnji,
                r.cashier_id
            FROM pos_posreceipt r
            LEFT JOIN pos_poscashier c ON c.id = r.cashier_id
            LEFT JOIN pos_pospaymentline pl ON pl.receipt_id = r.id
            WHERE r.session_id = %s AND r.status = 'paid'
            GROUP BY r.cashier_id, c.name
            ORDER BY ukupno DESC
        """, [session_id])
        rows = cur.fetchall()

    def fmt(dt):
        if not dt: return '-'
        import pytz
        from django.utils import timezone as tz
        if hasattr(dt, 'astimezone'):
            dt = dt.astimezone()
        return dt.strftime('%H:%M')

    cashiers = []
    total_gotovina = total_kartica = total_ukupno = 0
    for row in rows:
        cashiers.append({
            'name':      row[0],
            'racuna':    row[1],
            'gotovina':  float(row[2] or 0),
            'kartica':   float(row[3] or 0),
            'vavceri':   float(row[4] or 0),
            'ukupno':    float(row[5] or 0),
            'prvi':      fmt(row[6]),
            'zadnji':    fmt(row[7]),
        })
        total_gotovina += float(row[2] or 0)
        total_kartica  += float(row[3] or 0)
        total_ukupno   += float(row[5] or 0)

    return render(request, 'pos/cashier_report.html', {
        'session':         session,
        'cashiers':        cashiers,
        'total_gotovina':  total_gotovina,
        'total_kartica':   total_kartica,
        'total_ukupno':    total_ukupno,
    })


@login_required
@csrf_exempt
@login_required
def api_quick_add_item(request):
    """Brzo dodavanje novog artikla iz POS skenera."""
    import json
    from django.http import JsonResponse
    from core.company_utils import get_user_company
    from inventory.models import InventoryItem

    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)

    company = get_user_company(request)
    if not company:
        return JsonResponse({'error': 'Nema firme'}, status=400)

    try:
        data = json.loads(request.body)
    except Exception as e:  # BORG: was bare except
        logger.debug("Exception in pos.views:%d: %s", 3895, e)  # BORG
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    name = data.get('name', '').strip()
    price = data.get('price', 0)
    category = data.get('category', 'food')
    tax_rate_pct = data.get('tax_rate', 25)
    barcode = data.get('barcode', '').strip()

    if not name:
        return JsonResponse({'error': 'Naziv je obavezan'}, status=400)

    # Find or create tax rate
    tax_obj = None
    try:
        from companies.models import TaxRate
        tax_obj = TaxRate.objects.filter(rate=tax_rate_pct).first()
    except Exception:
        pass

    # Generiraj unikatan SKU: POS- + zadnjih 6 znakova barkoda ili random
    import uuid as _uuid
    if barcode:
        sku_suffix = barcode[-6:]
    else:
        sku_suffix = _uuid.uuid4().hex[:6].upper()
    base_sku = 'POS-' + sku_suffix
    sku = base_sku
    counter = 1
    while InventoryItem.objects.filter(company=company, sku=sku).exists():
        sku = base_sku + '-' + str(counter)
        counter += 1

    item = InventoryItem(
        company=company,
        name=name,
        sku=sku,
        unit_price=price,
        purchase_price=0,
        category=category,
        barcode=barcode if barcode else '',
        is_active=True,
        quantity=0,
        webshop_visible=True,
    )
    if tax_obj:
        item.tax_rate = tax_obj
    item.save()

    return JsonResponse({
        'id': item.pk,
        'name': item.name,
        'price': str(item.unit_price),
        'category': item.category,
        'barcode': barcode,
    })




# ═══ API: Dohvat pojedinacnog artikla (fallback za brze tipke) ═══
@login_required
def pos_item_api(request, item_id):
    from inventory.models import InventoryItem
    company = get_user_company(request)
    try:
        item = InventoryItem.objects.get(id=item_id, company=company, is_active=True)
        return JsonResponse({
            'id': str(item.id), 'name': item.name,
            'price': str(item.unit_price),
            'tax': str(item.tax_rate.rate) if item.tax_rate else '25',
            'sku': item.sku or '', 'bc': item.barcode or ''
        })
    except InventoryItem.DoesNotExist:
        return JsonResponse({'error': 'not found'}, status=404)


# ═══ POSDailyReport — lista + mjesecni summary ═══
@login_required
def daily_reports_list(request):
    from pos.models import POSDailyReport
    from django.db.models import Sum

    company = get_user_company(request)
    qs = POSDailyReport.objects.filter(company=company).select_related('terminal', 'session')

    month_str = request.GET.get('month', '')
    if month_str:
        try:
            year, month = month_str.split('-')
            qs = qs.filter(date__year=int(year), date__month=int(month))
        except (ValueError, TypeError):
            pass

    reports = qs.order_by('-date')[:100]

    monthly = (
        POSDailyReport.objects.filter(company=company)
        .extra(select={'month': "to_char(date, 'YYYY-MM')"})
        .values('month')
        .annotate(
            total_revenue=Sum('total_revenue'),
            total_cash=Sum('cash_total'),
            total_card=Sum('card_total'),
            receipt_count=Sum('receipt_count'),
        )
        .order_by('-month')[:12]
    )

    return render(request, 'pos/daily_reports.html', {
        'reports': reports,
        'monthly': monthly,
        'current_month': month_str,
    })


# ═══ KDS Cook Logout ═══
@csrf_exempt
def kitchen_cook_logout(request, token):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)
    from companies.models import Company
    from accounts.models import DeviceToken
    import json as _json

    company = Company.objects.filter(id=token).first()
    if not company:
        return JsonResponse({'error': 'Invalid token'}, status=404)

    try:
        data = _json.loads(request.body)
    except Exception:
        data = {}

    barcode = data.get('barcode_data', '').strip()
    if not barcode:
        return JsonResponse({'error': 'barcode_data obavezan'}, status=400)

    dt = DeviceToken.objects.filter(
        barcode_data=barcode, company=company, is_active=True
    ).select_related('user').first()
    if not dt:
        return JsonResponse({'error': 'Nepoznat barcode'}, status=404)

    from pos.worktime_bridge import device_logout_stop_all
    result = device_logout_stop_all(dt.user, dt.company)

    return JsonResponse({
        'ok': True,
        'cook_name': dt.user.get_full_name() or dt.user.username,
        'stopped': result.get('stopped', []),
    })


# ═══ DeviceToken: Create ═══
@login_required
def device_token_create(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)
    from accounts.models import DeviceToken
    company = get_user_company(request)
    if not company:
        return JsonResponse({'error': 'Nema tvrtke'}, status=400)

    device_name = request.POST.get('device_name', 'Test uredaj')
    dt = DeviceToken.objects.create(
        user=request.user,
        company=company,
        device_name=device_name,
    )
    return JsonResponse({
        'ok': True,
        'token': str(dt.token),
        'barcode_data': dt.barcode_data,
        'device_name': dt.device_name,
    })


# ═══ DeviceToken: Panic deactivate ═══
@login_required
def device_token_panic(request, token_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)
    from accounts.models import DeviceToken
    company = get_user_company(request)
    try:
        dt = DeviceToken.objects.get(pk=token_id, company=company)
        dt.is_active = False
        dt.save(update_fields=['is_active'])
        return JsonResponse({'ok': True, 'deactivated': str(dt.token)})
    except DeviceToken.DoesNotExist:
        return JsonResponse({'error': 'Token ne postoji'}, status=404)


# ═══ DeviceToken: Lista s expiry ═══
@login_required
def device_token_list(request):
    from accounts.models import DeviceToken
    from django.utils import timezone

    company = get_user_company(request)
    tokens = DeviceToken.objects.filter(company=company).select_related('user', 'cashier')

    token_data = []
    now = timezone.now()
    for dt in tokens:
        days_since_use = (now - dt.last_used_at).days if dt.last_used_at else None
        is_expired = days_since_use is not None and days_since_use > 90
        token_data.append({
            'id': dt.pk,
            'user': dt.user.get_full_name() or dt.user.username,
            'device_name': dt.device_name,
            'barcode_data': dt.barcode_data,
            'is_active': dt.is_active,
            'is_expired': is_expired,
            'days_since_use': days_since_use,
            'last_used': dt.last_used_at.isoformat() if dt.last_used_at else None,
            'created': dt.created_at.isoformat(),
        })

    return JsonResponse({'tokens': token_data})



# ═══ Knjiga boljitaka ═══
@login_required
def improvement_list(request):
    from pos.models import ImprovementSuggestion
    company = get_user_company(request)
    suggestions = ImprovementSuggestion.objects.filter(company=company)

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        desc = request.POST.get('description', '').strip()
        category = request.POST.get('category', 'other')
        priority = int(request.POST.get('priority', '3') or '3')
        if title and desc:
            ImprovementSuggestion.objects.create(
                company=company, author=request.user,
                title=title, description=desc,
                category=category, priority=priority,
            )
            messages.success(request, 'Prijedlog spremljen!')
            return redirect('pos:improvement_list')

    return render(request, 'pos/improvement_list.html', {
        'suggestions': suggestions,
    })


@login_required
def improvement_update(request, pk):
    from pos.models import ImprovementSuggestion
    company = get_user_company(request)
    s = get_object_or_404(ImprovementSuggestion, pk=pk, company=company)
    if request.method == 'POST':
        s.status = request.POST.get('status', s.status)
        s.admin_note = request.POST.get('admin_note', s.admin_note)
        s.save(update_fields=['status', 'admin_note', 'updated_at'])
        return JsonResponse({'ok': True})
    return JsonResponse({'error': 'POST only'}, status=405)


# ═══ Onboarding Wizard ═══
@login_required
def onboarding_wizard(request):
    """
    Onboarding wizard — vodi novog korisnika kroz setup:
    1. Company info (ime, OIB, adresa)
    2. POS terminal setup
    3. Artikli import
    4. Blagajnik setup
    5. Fiskalizacija
    """
    company = get_user_company(request)
    if not company:
        messages.error(request, 'Nema tvrtke.')
        return redirect('core:dashboard')

    from inventory.models import InventoryItem
    from pos.models import POSTerminal, POSCashier, POSSettings

    steps = [
        {
            'name': 'Tvrtka',
            'done': bool(company.oib and company.address),
            'url': '/hr/companies/edit/',
            'desc': 'Unesite OIB, adresu i podatke tvrtke',
        },
        {
            'name': 'POS terminal',
            'done': POSTerminal.objects.filter(company=company).exists(),
            'url': '/hr/pos/terminal/new/',
            'desc': 'Kreirajte prvi POS terminal (blagajna)',
        },
        {
            'name': 'Artikli',
            'done': InventoryItem.objects.filter(company=company).count() >= 5,
            'url': '/hr/pos/settings/',
            'desc': 'Dodajte artikle (rucno ili CSV import)',
        },
        {
            'name': 'Blagajnik',
            'done': POSCashier.objects.filter(company=company).exists(),
            'url': '/hr/pos/cashier/setup/',
            'desc': 'Dodajte blagajnika s PIN-om i OIB-om (zakonska obaveza)',
        },
        {
            'name': 'Fiskalizacija',
            'done': bool(getattr(POSSettings.objects.filter(company=company).first(), 'fiscal_active', False)),
            'url': '/hr/pos/settings/',
            'desc': 'Postavite FINA certifikat za fiskalizaciju',
        },
    ]

    completed = sum(1 for s in steps if s['done'])
    total = len(steps)

    return render(request, 'pos/onboarding.html', {
        'steps': steps,
        'completed': completed,
        'total': total,
        'progress': int(completed / total * 100) if total else 0,
    })


# ══════════════════════════════════════════════════════════════
# BLAGAJNIK SETUP — Onboarding wizard korak
# ══════════════════════════════════════════════════════════════

@login_required
def cashier_setup(request):
    """Dedicated view za kreaciju blagajnika s PIN-om i OIB-om.
    Koristi se iz onboarding wizarda i POS settings."""
    company = get_user_company(request)
    if not company:
        messages.error(request, 'Nema tvrtke.')
        return redirect('core:dashboard')

    error = None
    if request.method == 'POST':
        name = request.POST.get('cashier_name', '').strip()
        oib = request.POST.get('cashier_oib', '').strip()
        pin = request.POST.get('cashier_pin', '').strip()
        pin2 = request.POST.get('cashier_pin2', '').strip()

        if not name:
            error = 'Unesite ime blagajnika.'
        elif oib and len(oib) != 11:
            error = 'OIB mora imati točno 11 znamenki.'
        elif not pin or len(pin) < 4:
            error = 'PIN mora imati najmanje 4 znamenke.'
        elif pin != pin2:
            error = 'PIN-ovi se ne podudaraju.'
        else:
            cashier = POSCashier(company=company, name=name, oib=oib, is_active=True)
            cashier.save()
            if hasattr(cashier, 'set_pin'):
                cashier.set_pin(pin)
                cashier.save(update_fields=['pin_hash'])
            messages.success(request, f'Blagajnik {name} kreiran.')
            next_url = request.POST.get('next') or request.GET.get('next') or '/hr/pos/onboarding/'
            return redirect(next_url)

    return render(request, 'pos/cashier_setup.html', {
        'error': error,
        'next': request.GET.get('next', '/hr/pos/onboarding/'),
    })


# ══════════════════════════════════════════════════════════════
# KNJIGA PRIGOVORA — Zakonska evidencija (čl. 10 ZZP)
# ══════════════════════════════════════════════════════════════

@login_required
def prigovori_list(request):
    """Knjiga boljitaka — HTML prikaz + modal za unos."""
    company = get_user_company(request)
    from .models import KnjigaPrigovora
    prigovori = KnjigaPrigovora.objects.filter(company=company)
    return render(request, 'pos/prigovori.html', {'prigovori': prigovori, 'company': company})


@login_required
def prigovori_api(request):
    """AJAX CRUD za prigovore."""
    company = get_user_company(request)
    from .models import KnjigaPrigovora

    if request.method == 'GET':
        data = []
        for p in KnjigaPrigovora.objects.filter(company=company):
            data.append({
                'id': p.pk,
                'redni_broj': p.redni_broj,
                'record_type': p.record_type,
                'datum_primitka': p.datum_primitka.isoformat(),
                'ime': p.ime_potrosaca,
                'kontakt': p.kontakt,
                'consumer_email': p.consumer_email,
                'consumer_phone': p.consumer_phone,
                'opis': p.opis_prigovora,
                'odgovor': p.odgovor,
                'datum_odgovora': p.datum_odgovora.isoformat() if p.datum_odgovora else None,
                'needs_response': p.needs_response,
                'rok_istekao': p.rok_istekao,
                'dana_do_roka': p.dana_do_roka,
                'star_rating': p.star_rating,
                'source_module': p.source_module,
                'language': p.language,
                'ai_category': p.ai_category,
                'ai_sentiment': p.ai_sentiment,
                'ai_priority': p.ai_priority,
                'ai_suggested_response': p.ai_suggested_response,
                'has_audio': bool(p.audio_recording),
                'has_signature': bool(p.signature),
                'is_escalated': p.is_escalated,
                'response_channel': p.response_channel,
                'integrity_hash': p.integrity_hash[:16] if p.integrity_hash else '',
                'integrity_valid': p.verify_integrity() if p.integrity_hash else None,
                'ses_metadata': p.ses_metadata,
                'whatsapp_consent': p.whatsapp_consent,
                'moderation_passed': p.moderation_passed,
                'moderation_note': p.moderation_note,
            })
        return JsonResponse({'status': 'success', 'data': data})

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({'status': 'error', 'error': {'message': 'Invalid JSON'}}, status=400)

        action = data.get('action', '')

        if action == 'create':
            ime = data.get('ime', '').strip()
            opis = data.get('opis', '').strip()
            if not ime or not opis:
                return JsonResponse({'status': 'error', 'error': {'message': 'Ime i opis su obavezni'}}, status=400)
            p = KnjigaPrigovora.objects.create(
                company=company,
                ime_potrosaca=ime[:200],
                kontakt=data.get('kontakt', '')[:200],
                opis_prigovora=opis,
                id_photo=data.get('id_photo', '') or '',
                signature=data.get('signature', '') or '',
                voice_input=bool(data.get('voice_input', False)),
                created_by=request.user,
            )

            # Audio recording (base64 WebM → file)
            audio_b64 = data.get('audio_recording', '')
            if audio_b64:
                import base64
                from django.core.files.base import ContentFile
                try:
                    audio_data = base64.b64decode(audio_b64.split(',')[-1])
                    p.audio_recording.save(
                        'prigovor_%d.webm' % p.redni_broj,
                        ContentFile(audio_data), save=True,
                    )
                except Exception:
                    pass

            # Trigger AI analysis (async Celery)
            try:
                from pos.tasks import ai_analyze_prigovor
                ai_analyze_prigovor.delay(p.pk)
            except Exception:
                pass

            return JsonResponse({
                'status': 'success',
                'message': 'Prigovor #%d zaprimljen. AI analiza u tijeku.' % p.redni_broj,
                'integrity_hash': p.integrity_hash,
            })

        elif action == 'odgovori':
            from django.utils import timezone as tz
            try:
                p = KnjigaPrigovora.objects.get(pk=data.get('id'), company=company)
            except KnjigaPrigovora.DoesNotExist:
                return JsonResponse({'status': 'error', 'error': {'message': 'Prigovor ne postoji'}}, status=404)
            p.odgovor = data.get('odgovor', '')
            p.datum_odgovora = tz.now().date()
            p.save()
            return JsonResponse({'status': 'success', 'message': 'Odgovor evidentiran na prigovor #%d.' % p.redni_broj})

        return JsonResponse({'status': 'error', 'error': {'message': 'Nepoznata akcija'}}, status=400)


@login_required
def knjiga_prigovora_pdf(request):
    """Službeni PDF Knjige prigovora i utisaka za inspekciju. HR + DE."""
    company = get_user_company(request)
    from .models import KnjigaPrigovora

    all_records = KnjigaPrigovora.objects.filter(company=company).order_by('redni_broj')
    prigovori = all_records.filter(record_type__in=['prigovor', 'reklamacija'])
    pohvale = all_records.filter(record_type__in=['pohvala', 'utisak', 'prijedlog'])

    # Detect language
    lang = request.GET.get('lang', '')
    if not lang:
        lang = 'de' if getattr(company, 'country', '') == 'DE' else 'hr'

    from django.template.loader import render_to_string
    html = render_to_string('pos/knjiga_prigovora_pdf.html', {
        'prigovori': prigovori,
        'pohvale': pohvale,
        'prigovori_count': prigovori.count(),
        'pohvale_count': pohvale.count(),
        'company': company,
        'lang': lang,
    })
    try:
        from xhtml2pdf import pisa
        from io import BytesIO
        buf = BytesIO()
        pisa.CreatePDF(html, dest=buf)
        buf.seek(0)
        response = HttpResponse(buf.read(), content_type='application/pdf')
        response['Content-Disposition'] = 'inline; filename="Knjiga_Prigovora_%s.pdf"' % (company.name or 'firma')
        return response
    except ImportError:
        return HttpResponse(html)



# ═══════════════════════════════════════════════════════════════
# BEZ PAPIRA — Receipt delivery system
# ═══════════════════════════════════════════════════════════════

@login_required
def receipt_list(request):
    """Lista svih racuna za ispis/pregled/naknadni WhatsApp."""
    company = get_user_company(request)
    if not company:
        messages.error(request, 'Nema konteksta tvrtke.')
        return redirect('pos:dashboard')

    receipts = POSReceipt.objects.filter(
        session__terminal__company=company
    ).select_related('session__terminal', 'cashier').order_by('-created_at')[:200]

    return render(request, 'pos/receipt_list.html', {
        'receipts': receipts,
        'company': company,
    })


@login_required
def receipt_deliver(request, receipt_id):
    """
    Unified receipt delivery — poziva se nakon naplate.
    Vraca JSON s URL-ovima za svaki delivery kanal.
    """
    receipt = get_object_or_404(POSReceipt, pk=receipt_id)
    company = receipt.session.terminal.company
    settings = getattr(company, 'pos_settings', None)

    result = {
        'receipt_id': receipt.pk,
        'receipt_number': receipt.receipt_number,
        'delivery_mode': settings.receipt_delivery if settings else 'thermal',
        'urls': {},
    }

    base = f'/hr/pos/receipt/{receipt.pk}'

    # Thermal print URL
    result['urls']['thermal'] = f'{base}/pdf/?format=thermal'

    # A4 PDF URL
    result['urls']['a4'] = f'{base}/pdf/?format=a4'

    # WhatsApp share URL
    result['urls']['whatsapp'] = f'{base}/whatsapp/'

    # Email URL
    result['urls']['email'] = f'{base}/email/'

    # QR kod za gosta (public link)
    result['urls']['qr'] = receipt_public_url(receipt.pk)

    # Drawer kick
    if settings and settings.drawer_kick:
        result['drawer_kick'] = True
        result['urls']['drawer'] = f'{base}/drawer-kick/'

    result['public_url'] = receipt_public_url(receipt.pk)
    return JsonResponse(result)


@login_required
def receipt_whatsapp(request, receipt_id):
    """
    WhatsApp share — generira wa.me link s racunom.
    GET: vraca share URL
    POST {phone}: salje direktno
    """
    receipt = get_object_or_404(POSReceipt, pk=receipt_id)
    company = receipt.session.terminal.company
    # Security: provjeri da korisnik pripada istoj tvrtki
    user_company = get_user_company(request)
    if user_company and user_company.pk != company.pk:
        return JsonResponse({'error': 'Nemate pristup ovom racunu'}, status=403)
    settings = getattr(company, 'pos_settings', None)

    items_text = []
    for item in receipt.items.all():
        items_text.append(f'{item.description} x{item.quantity} = EUR{item.total_price:.2f}')

    msg_header = settings.whatsapp_default_msg if settings else 'Hvala na posjetu! Evo Vas racun:'
    receipt_url = request.build_absolute_uri(receipt_public_url(receipt.pk))

    msg = f"""{msg_header}

{chr(9989)} *{company.name}*
Racun #{receipt.receipt_number}
Datum: {receipt.created_at.strftime('%d.%m.%Y %H:%M')}

{'%0A'.join(items_text) if len(items_text) <= 10 else f'{len(items_text)} stavki'}

*UKUPNO: EUR{receipt.total:.2f}*
Placeno: {receipt.payment_lines.first().get_method_display() if receipt.payment_lines.exists() else 'N/A'}

{f'ZKI: {receipt.zki[:16]}...' if receipt.zki else ''}
{f'JIR: {receipt.jir[:16]}...' if receipt.jir else ''}

{chr(128279)} Digitalni racun: {receipt_url}"""

    if request.method == 'POST':
        phone = request.POST.get('phone', '').strip()
        if phone:
            # Clean phone number — preserve international prefix
            phone = phone.replace(' ', '').replace('-', '')
            if phone.startswith('+'):
                phone = phone[1:]  # strip + but keep country code
            elif phone.startswith('00'):
                phone = phone[2:]  # 00385 → 385
            elif phone.startswith('0'):
                phone = '385' + phone[1:]  # 091... → 38591...
            # Only add 385 if it looks like a local HR number (no country code)
            if len(phone) <= 10 and not phone.startswith(('385', '49', '43', '386', '44', '39', '33')):
                phone = '385' + phone.lstrip('0')
            import urllib.parse
            wa_url = f'https://wa.me/{phone}?text={urllib.parse.quote(msg)}'
            return JsonResponse({'ok': True, 'wa_url': wa_url, 'phone': phone})
        return JsonResponse({'error': 'phone required'}, status=400)

    # GET: return message for copy/share
    import urllib.parse
    return JsonResponse({
        'message': msg,
        'share_url': f'https://wa.me/?text={urllib.parse.quote(msg)}',
        'receipt_url': receipt_url,
    })


@login_required
def receipt_email(request, receipt_id):
    """
    Posalji racun na email.
    POST {email}: salje PDF A4 racun na email.
    """
    receipt = get_object_or_404(POSReceipt, pk=receipt_id)
    company = receipt.session.terminal.company
    # Security: provjeri da korisnik pripada istoj tvrtki
    user_company = get_user_company(request)
    if user_company and user_company.pk != company.pk:
        return JsonResponse({'error': 'Nemate pristup ovom racunu'}, status=403)
    settings = getattr(company, 'pos_settings', None)

    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)

    email_to = request.POST.get('email', '').strip()
    if not email_to or '@' not in email_to:
        return JsonResponse({'error': 'Valid email required'}, status=400)

    try:
        from django.core.mail import EmailMessage
        from django.template.loader import get_template as _gt

        items = receipt.items.all()
        from pos.utils import generate_receipt_qr_base64
        fina_qr = generate_receipt_qr_base64(receipt)
        bl = receipt.session.terminal.business_location

        ctx = {
            'receipt': receipt, 'items': items, 'company': company,
            'payment_lines': receipt.payment_lines.all(),
            'terminal': receipt.session.terminal,
            'fina_qr_b64': fina_qr, 'business_location': bl,
        }

        subject = (settings.receipt_email_subject if settings else 'Vas racun - {company}')
        subject = subject.replace('{company}', company.name)
        subject = subject.replace('{number}', str(receipt.receipt_number))

        # Render A4 HTML
        tmpl = _gt('pos/receipt_a4_pdf.html')
        html_body = tmpl.render(ctx)

        # Try to generate PDF attachment
        pdf_bytes = None
        try:
            import weasyprint
            pdf_bytes = weasyprint.HTML(string=html_body).write_pdf()
        except Exception:
            pass

        email = EmailMessage(
            subject=subject,
            body=f'Postovani,\n\nU prilogu je Vas racun #{receipt.receipt_number} iz {company.name}.\n\nUkupno: EUR{receipt.total:.2f}\n\nHvala na posjetu!\n\n--\n{company.name}',
            from_email=None,  # uses DEFAULT_FROM_EMAIL
            to=[email_to],
        )

        if pdf_bytes:
            email.attach(f'racun-{receipt.receipt_number}.pdf', pdf_bytes, 'application/pdf')

        email.send()
        return JsonResponse({'ok': True, 'sent_to': email_to})

    except Exception as e:
        import logging
        logging.getLogger('pos').error(f'Email send failed: {e}')
        return JsonResponse({'error': str(e)[:200]}, status=500)


def receipt_public(request, receipt_id, token=None):
    """
    Public receipt view — gost skenira QR na stolu.
    Mobile-friendly, BEZ PAPIRA. Bez logina.
    Token moze biti u path-u ili query stringu.
    """
    import hashlib, hmac
    from django.conf import settings as _s
    expected = hmac.new(_s.SECRET_KEY[:32].encode(), str(receipt_id).encode(), hashlib.sha256).hexdigest()[:12]
    token = (token or request.GET.get('t', '')).strip().rstrip('/').strip()
    # Strip any junk scanners might append
    import re as _re
    token = _re.sub(r'[^a-f0-9]', '', token)
    if token != expected:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden('Neispravan link. Skenirajte QR kod ponovo.')
    receipt = get_object_or_404(POSReceipt, pk=receipt_id)
    items = receipt.items.all()
    company = receipt.session.terminal.company

    from pos.utils import generate_receipt_qr_base64
    fina_qr = generate_receipt_qr_base64(receipt)

    return render(request, 'pos/receipt_public.html', {
        'receipt': receipt, 'items': items, 'company': company,
        'payment_lines': receipt.payment_lines.all(),
        'terminal': receipt.session.terminal,
        'fina_qr_b64': fina_qr,
    })


def receipt_public_token(receipt_id):
    """Generiraj HMAC token za public receipt URL."""
    import hashlib, hmac
    from django.conf import settings as _s
    return hmac.new(_s.SECRET_KEY[:32].encode(), str(receipt_id).encode(), hashlib.sha256).hexdigest()[:12]


def receipt_public_url(receipt_id):
    """Puni URL za public receipt s tokenom u path-u (Google Lens compatible)."""
    token = receipt_public_token(receipt_id)
    return f'/pos/r/{receipt_id}/{token}/'



@login_required
def receipt_drawer_kick(request, receipt_id):
    """
    ESC/POS drawer kick — otvori ladicu za novac.
    Salje raw ESC/POS komandu na mrezni printer.
    """
    receipt = get_object_or_404(POSReceipt, pk=receipt_id)
    company = receipt.session.terminal.company
    settings = getattr(company, 'pos_settings', None)

    if not settings or not settings.drawer_kick:
        return JsonResponse({'error': 'Drawer kick disabled'}, status=400)

    ip = settings.printer_ip
    port = settings.printer_port or 9100

    if not ip:
        return JsonResponse({'error': 'Printer IP not configured'}, status=400)

    try:
        import socket
        # ESC/POS drawer kick command: ESC p 0 25 250
        cmd = b'\x1b\x70\x00\x19\xfa'
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        sock.connect((ip, port))
        sock.send(cmd)
        sock.close()
        return JsonResponse({'ok': True, 'message': 'Ladica otvorena'})
    except Exception as e:
        return JsonResponse({'error': f'Drawer kick failed: {e}'}, status=500)


@login_required
def pos_delivery_settings(request):
    """API za dohvat delivery postavki za trenutnu tvrtku."""
    company = get_user_company(request)
    if not company:
        return JsonResponse({'error': 'No company'}, status=400)
    settings = getattr(company, 'pos_settings', None)
    if not settings:
        return JsonResponse({
            'delivery_mode': 'thermal',
            'auto_print': True,
            'drawer_kick': False,
        })
    return JsonResponse({
        'delivery_mode': settings.receipt_delivery,
        'auto_print': settings.auto_print,
        'drawer_kick': settings.drawer_kick,
        'printer_type': settings.printer_type,
        'whatsapp_msg': settings.whatsapp_default_msg,
    })


# ══════════════════════════════════════════════════════════════
# REVOLUT — Kartično plaćanje putem mobitela
# ══════════════════════════════════════════════════════════════

@login_required
@require_POST
def revolut_pay(request, receipt_id):
    """
    Kreiraj Revolut payment link za račun.
    POST → vraća {checkout_url, qr_data} za prikaz gostu.
    """
    from pos.revolut_service import create_payment_link, is_configured
    if not is_configured():
        return JsonResponse({'ok': False, 'error': 'Revolut nije konfiguriran. Dodaj REVOLUT_API_KEY u .env'}, status=400)

    company = get_user_company(request)
    receipt = get_object_or_404(POSReceipt, pk=receipt_id)

    callback = request.build_absolute_uri('/pos/revolut/success/')
    result = create_payment_link(receipt, company, callback_url=callback)

    if result.get('ok'):
        # Spremi payment_id na receipt za tracking
        receipt.card_reference = result.get('payment_id', '')[:100] if hasattr(receipt, 'card_reference') else ''
        receipt.note = (receipt.note or '') + ' | Revolut: ' + result.get('payment_id', '')[:20]
        receipt.save(update_fields=['note'])

    return JsonResponse(result)


@login_required
def revolut_status(request, receipt_id):
    """
    Poll status Revolut plaćanja.
    GET → {status: 'pending'|'completed'|'failed'}
    Frontend polira svake 2s dok gost plaća.
    """
    from pos.revolut_service import check_payment_status

    receipt = get_object_or_404(POSReceipt, pk=receipt_id)
    # Izvuci payment_id iz note
    payment_id = ''
    if receipt.note and 'Revolut:' in receipt.note:
        payment_id = receipt.note.split('Revolut:')[-1].strip().split()[0]

    if not payment_id:
        return JsonResponse({'status': 'error', 'error': 'Nema Revolut payment ID'})

    result = check_payment_status(payment_id)

    # Ako je completed — zatvori bon
    if result.get('status') == 'completed' and receipt.status != 'paid':
        from django.utils import timezone as tz
        receipt.status = 'paid'
        receipt.paid_at = tz.now()
        receipt.save()
        POSPaymentLine.objects.get_or_create(
            receipt=receipt, method='REVOLUT',
            defaults={'amount': receipt.total},
        )
        result['receipt_closed'] = True

    return JsonResponse(result)


@csrf_exempt
def revolut_webhook(request):
    """
    Revolut webhook — prima notifikaciju o plaćanju.
    POST od Revolut servera kad gost plati.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)

    from pos.revolut_service import verify_webhook_signature
    sig = request.headers.get('Revolut-Signature', '')

    if not verify_webhook_signature(request.body, sig):
        return JsonResponse({'error': 'Invalid signature'}, status=403)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    event_type = data.get('event', '')
    order_data = data.get('order', {})
    order_id = order_data.get('id', '')
    state = order_data.get('state', '')
    ext_ref = order_data.get('merchant_order_ext_ref', '')

    logger.info('Revolut webhook: event=%s order=%s state=%s ref=%s', event_type, order_id, state, ext_ref)

    if state == 'COMPLETED' and ext_ref.startswith('POS-'):
        receipt_id = int(ext_ref.replace('POS-', ''))
        try:
            from django.utils import timezone as tz
            receipt = POSReceipt.objects.get(pk=receipt_id)
            if receipt.status != 'paid':
                receipt.status = 'paid'
                receipt.paid_at = tz.now()
                receipt.save()
                POSPaymentLine.objects.get_or_create(
                    receipt=receipt, method='REVOLUT',
                    defaults={'amount': receipt.total},
                )
                logger.info('Revolut webhook: receipt #%d paid via Revolut', receipt_id)
        except POSReceipt.DoesNotExist:
            logger.warning('Revolut webhook: receipt #%d not found', receipt_id)

    return JsonResponse({'ok': True})


@login_required
def revolut_qr(request, receipt_id):
    """Generiraj QR kod za Revolut payment link."""
    receipt = get_object_or_404(POSReceipt, pk=receipt_id)
    # Izvuci checkout_url
    payment_id = ''
    if receipt.note and 'Revolut:' in receipt.note:
        payment_id = receipt.note.split('Revolut:')[-1].strip().split()[0]

    if not payment_id:
        return JsonResponse({'error': 'Nema payment linka'}, status=400)

    checkout_url = 'https://checkout.revolut.com/pay/%s' % payment_id

    import qrcode, base64
    from io import BytesIO
    qr = qrcode.make(checkout_url, box_size=6, border=2)
    buf = BytesIO()
    qr.save(buf, format='PNG')
    buf.seek(0)
    qr_b64 = base64.b64encode(buf.read()).decode()

    return JsonResponse({
        'ok': True,
        'qr_b64': qr_b64,
        'checkout_url': checkout_url,
    })



@login_required
def session_report_json(request, session_id):
    """Z-report za cijelu sesiju (svi blagajnici)."""
    from django.db import connection
    session = get_object_or_404(POSSession, pk=session_id)
    company, err = _check_tenant(request, session)
    if err: return err

    with connection.cursor() as cur:
        cur.execute("""
            SELECT
                COUNT(DISTINCT r.id)                                          AS racuna,
                COALESCE(SUM(pl.amount) FILTER (WHERE pl.method='CASH'),  0) AS gotovina,
                COALESCE(SUM(pl.amount) FILTER (WHERE pl.method='CARD'),  0) AS kartica,
                COALESCE(SUM(pl.amount) FILTER (WHERE pl.method='VOUCHER'),0) AS vavceri,
                COALESCE(SUM(pl.amount) FILTER (WHERE pl.method NOT IN ('CASH','CARD','VOUCHER')),0) AS ostalo,
                COALESCE(SUM(r.total), 0)                                     AS ukupno,
                MIN(r.paid_at)                                                AS prvi_racun,
                MAX(r.paid_at)                                                AS zadnji_racun
            FROM pos_posreceipt r
            LEFT JOIN pos_pospaymentline pl ON pl.receipt_id = r.id
            WHERE r.session_id = %s
              AND r.status      = 'paid'
        """, [session_id])
        row = cur.fetchone()

    racuna, gotovina, kartica, vavceri, ostalo, ukupno, prvi, zadnji = row

    receipts = (
        POSReceipt.objects
        .filter(session_id=session_id, status='paid')
        .order_by('-paid_at')[:15]
    )

    def fmt(dt):
        return dt.strftime('%H:%M') if dt else '-'

    terminal = session.terminal
    return JsonResponse({
        'cashier':   'Svi blagajnici',
        'terminal':  terminal.name,
        'racuna':    racuna or 0,
        'gotovina':  str(gotovina or 0),
        'kartica':   str(kartica  or 0),
        'vavceri':   str(vavceri  or 0),
        'ostalo':    str(ostalo   or 0),
        'ukupno':    str(ukupno   or 0),
        'prvi':      fmt(prvi),
        'zadnji':    fmt(zadnji),
        'receipts':  [
            {
                'broj':    r.receipt_number,
                'ukupno':  str(r.total),
                'vrijeme': fmt(r.paid_at),
            }
            for r in receipts
        ],
    })



@login_required
def dsfinvk_export(request):
    """DSFinV-K Export Download — ZIP fuer Finanzamt."""
    from datetime import date, timedelta
    from django.http import HttpResponse
    company = get_user_company(request)
    if not company:
        return JsonResponse({'error': 'Keine Firma'}, status=400)

    # Only for DE companies
    if company.country not in ('DE', 'AT'):
        return JsonResponse({'error': 'DSFinV-K ist nur fuer DE/AT Firmen'}, status=400)

    date_from = request.GET.get('from', '')
    date_to = request.GET.get('to', '')

    if date_from:
        date_from = date.fromisoformat(date_from)
    else:
        today = date.today()
        date_from = today.replace(day=1) - timedelta(days=1)
        date_from = date_from.replace(day=1)

    if date_to:
        date_to = date.fromisoformat(date_to)
    else:
        date_to = date.today()

    from pos.dsfinvk_export import generate_dsfinvk_export
    zip_bytes = generate_dsfinvk_export(company, date_from, date_to)

    filename = 'DSFinV-K_%s_%s_%s.zip' % (company.oib, date_from.isoformat(), date_to.isoformat())
    response = HttpResponse(zip_bytes, content_type='application/zip')
    response['Content-Disposition'] = 'attachment; filename="%s"' % filename
    return response



@login_required
def kassenbuch_download(request):
    """Blagajnicki dnevnik / Kassenbuch XLSX download."""
    from django.http import HttpResponse
    from datetime import date, timedelta
    company = get_user_company(request)
    if not company:
        return JsonResponse({'error': 'Nema firme'}, status=400)

    date_from = request.GET.get('from', '')
    date_to = request.GET.get('to', '')

    if date_from:
        date_from = date.fromisoformat(date_from)
    else:
        date_from = date.today().replace(day=1)
    if date_to:
        date_to = date.fromisoformat(date_to)
    else:
        date_to = date.today()

    from pos.kassenbuch import generate_kassenbuch
    xlsx = generate_kassenbuch(company, date_from, date_to)

    is_de = company.country in ('DE', 'AT')
    prefix = 'Kassenbuch' if is_de else 'Blagajnicki_dnevnik'
    filename = '%s_%s_%s_%s.xlsx' % (prefix, company.oib, date_from.isoformat(), date_to.isoformat())
    response = HttpResponse(xlsx, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="%s"' % filename
    return response


# ── QR INSTANT OPEN — zero-login terminal activation ──────────────────────────

@csrf_exempt
def pos_qr_open(request, token):
    """
    QR pristup blagajni — bez logina.
    Skenira QR, otvara/nastavlja sesiju, redirect na POS.
    Rate limit: max 10 pokusaja / IP / sat.
    """
    from django.core.cache import cache

    terminal = get_object_or_404(POSTerminal, access_token=token, is_active=True)
    company = terminal.company

    # Rate limit: 10 per IP per hour
    ip = request.META.get("HTTP_X_REAL_IP", request.META.get("REMOTE_ADDR", ""))
    cache_key = f"qr_open_{ip}"
    hits = cache.get(cache_key, 0)
    if hits >= 10:
        return HttpResponse("Previse pokusaja. Pokusajte ponovo za sat vremena.", status=429)
    cache.set(cache_key, hits + 1, 3600)

    # Find or create qr_operator user
    from django.contrib.auth.models import User
    qr_user, _ = User.objects.get_or_create(
        username=f"qr_operator_{company.pk}",
        defaults={
            "first_name": "QR",
            "last_name": "Operator",
            "is_active": True,
            "is_staff": False,
        },
    )

    # Find open session or create new one
    session = POSSession.objects.filter(terminal=terminal, status="open").first()
    if not session:
        last = terminal.sessions.order_by("-session_number").first()
        next_num = (last.session_number + 1) if last else 1
        session = POSSession.objects.create(
            terminal=terminal,
            operator=qr_user,
            session_number=next_num,
            opening_cash=Decimal("0"),
            status="open",
        )

    # Log access
    try:
        from superadmin_ai.models import AIActionLog
        AIActionLog.objects.create(
            company=company,
            module="pos",
            action_type="qr_open",
            access_level=1,
            outcome="executed",
            ip_address=ip if ip else None,
            details={
                "terminal": terminal.name,
                "terminal_id": terminal.pk,
                "token": token[:8] + "...",
                "session_id": str(session.pk),
            },
        )
    except Exception:
        logger.warning("QR open log failed", exc_info=True)

    # Store QR context in Django session
    request.session["qr_terminal_id"] = terminal.pk
    request.session["qr_session_id"] = session.pk
    request.session["qr_company_id"] = str(company.pk)

    return redirect("pos:qr_session", session_id=session.pk)


@ensure_csrf_cookie
def qr_session(request, session_id):
    """
    POS sucelje za QR pristup — bez @login_required.
    Validira da session pripada QR kontekstu.
    Renderira isti template kao quick_pos.
    """
    session = get_object_or_404(POSSession, pk=session_id, status="open")
    terminal = session.terminal

    # Validate QR context
    qr_session_id = request.session.get("qr_session_id")
    if qr_session_id != session.pk:
        return HttpResponse("Pristup odbijen. Skenirajte QR kod ponovo.", status=403)

    company = terminal.company

    try:
        qs = InventoryItem.objects.filter(company=company, is_active=True)
        if terminal.category_filter:
            cats = [c.strip() for c in terminal.category_filter.split(",") if c.strip()]
            if cats:
                qs = qs.filter(category__in=cats)
        inventory_items = list(qs.select_related("tax_rate").order_by("name")[:300])
    except Exception:
        logger.warning("Suppressed error", exc_info=True)
        inventory_items = []

    cats = sorted(set(getattr(i, "category", "") or "Ostalo" for i in inventory_items))

    from pos.models import POSCashier
    cashiers = list(POSCashier.objects.filter(company=company, is_active=True).order_by("name"))

    try:
        from django.urls import reverse
        report_url = reverse("pos:cashier_report_html", args=[session.id])
    except Exception:
        report_url = "#"

    # Top 12 quick items
    quick_items = []
    try:
        from django.db.models import Count
        top_ids = list(
            POSReceiptItem.objects
            .filter(receipt__session__terminal__company=company, receipt__status="paid")
            .exclude(is_tip=True)
            .values("inventory_item_id")
            .annotate(cnt=Count("id"))
            .order_by("-cnt")
            .values_list("inventory_item_id", flat=True)[:12]
        )
        if top_ids:
            items_map = {i.pk: i for i in InventoryItem.objects.filter(pk__in=top_ids, is_active=True).select_related("tax_rate")}
            quick_items = [items_map[pk] for pk in top_ids if pk in items_map]
        if len(quick_items) < 12:
            existing = {i.pk for i in quick_items}
            filler = list(
                InventoryItem.objects.filter(company=company, is_active=True)
                .exclude(pk__in=existing)
                .select_related("tax_rate")
                .order_by("name")[: 12 - len(quick_items)]
            )
            quick_items.extend(filler)
    except Exception:
        pass

    return render(request, "pos/quick.html", {
        "terminal": terminal,
        "session": session,
        "inventory_items": inventory_items,
        "quick_items": quick_items,
        "categories": cats,
        "cashiers": cashiers,
        "session_report_url": report_url,
        "qr_mode": True,
    })


@csrf_exempt
@require_POST
def qr_quick_pay(request, session_id):
    """AJAX quick checkout for QR sessions — no login required."""
    from pos.services.checkout import CheckoutService, CheckoutValidationError

    # Validate QR context
    qr_session_id = request.session.get("qr_session_id")
    if qr_session_id != session_id:
        return JsonResponse({"ok": False, "error": "QR pristup istekao"}, status=403)

    session = get_object_or_404(POSSession, pk=session_id, status="open")
    company = session.terminal.company

    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)

    data["session_id"] = session_id

    try:
        result = CheckoutService.process_receipt(
            company=company, user=session.operator, payload=data
        )
        return JsonResponse({
            "ok": True,
            "receipt_id": result["receipt_id"],
            "receipt_number": result["receipt_number"],
            "total": result["total"],
            "change": result["change"],
            "print_url": result.get("print_url", ""),
            "public_url": receipt_public_url(result["receipt_id"]),
        })
    except CheckoutValidationError as e:
        return JsonResponse({"ok": False, "error": e.message, "code": e.code}, status=400)
    except Exception as e:
        logger.error("qr_quick_pay error: %s", e, exc_info=True)
        return JsonResponse({"ok": False, "error": "Sistemska greska pri naplati"}, status=500)


# ═══════════════════════════════════════════════════════
#  KIOSK — Robot prodavač (touchscreen 15")
# ═══════════════════════════════════════════════════════

def kiosk_view(request, token):
    """
    Kiosk mode — touchscreen 15", full-screen, bez logina.
    Koristi access_token za identifikaciju terminala.
    """
    terminal = get_object_or_404(POSTerminal, access_token=token, is_active=True)
    company = terminal.company

    from inventory.models import InventoryItem
    items = InventoryItem.objects.filter(
        company=company, is_active=True, webshop_visible=True
    ).order_by('category', 'name')

    categories = sorted(set(i.category or 'ostalo' for i in items))

    return render(request, 'pos/kiosk.html', {
        'company': company,
        'terminal': terminal,
        'items': items,
        'categories': categories,
    })


# ── Cashier Gate API ──────────────────────────────────────────────────────────

@login_required
@require_POST
def verify_cashier_pin(request):
    """Verify cashier PIN for Cashier Gate modal."""
    import json
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'ok': False, 'error': 'Invalid JSON'}, status=400)
    cashier_id = data.get('cashier_id')
    pin = str(data.get('pin', '')).strip()
    if not cashier_id or not pin:
        return JsonResponse({'ok': False, 'error': 'Missing cashier_id or pin'})
    from pos.models import POSCashier
    company = get_user_company(request)
    try:
        cashier = POSCashier.objects.get(pk=cashier_id, company=company, is_active=True)
    except POSCashier.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Cashier not found'})
    if cashier.check_pin(pin):
        return JsonResponse({'ok': True, 'name': cashier.name, 'oib': cashier.oib})
    return JsonResponse({'ok': False, 'error': 'Invalid PIN'})


@login_required
@require_POST
def update_cashier_oib(request):
    """Update cashier OIB from Cashier Gate (inline fix for missing OIB)."""
    import json
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'ok': False, 'error': 'Invalid JSON'}, status=400)
    cashier_id = data.get('cashier_id')
    oib = str(data.get('oib', '')).strip()
    if not cashier_id or len(oib) != 11 or not oib.isdigit():
        return JsonResponse({'ok': False, 'error': 'Invalid OIB (must be 11 digits)'})
    from pos.models import POSCashier
    company = get_user_company(request)
    try:
        cashier = POSCashier.objects.get(pk=cashier_id, company=company)
    except POSCashier.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Cashier not found'})
    cashier.oib = oib
    cashier.save(update_fields=['oib'])
    return JsonResponse({'ok': True})


# ═══════════════════════════════════════════════════════════════════════════
# PP-MI-PO — Mjesečni izvještaj poreza na potrošnju
# Zakon o lokalnim porezima (NN 115/16, čl.20-22)
# Predaje se JLS-u do 20. u mjesecu za prethodni mjesec
# ═══════════════════════════════════════════════════════════════════════════

@login_required
def pp_mi_po_report(request):
    """Mjesečni obrazac PP-MI-PO za porez na potrošnju."""
    from decimal import Decimal
    from django.db.models import Sum, Count
    import calendar

    company = get_user_company(request)

    # Provjeri ima li PP aktiviran
    try:
        pos_settings = company.pos_settings
        if not pos_settings.consumption_tax_active:
            messages.warning(request, 'Porez na potrošnju nije aktiviran za ovu tvrtku.')
            return redirect('pos_dashboard')
    except Exception:
        messages.error(request, 'POS postavke nisu konfigurirane.')
        return redirect('pos_dashboard')

    # Mjesec/godina iz parametara (default: prethodni mjesec)
    now = timezone.now()
    year = int(request.GET.get('year', now.year if now.month > 1 else now.year - 1))
    month = int(request.GET.get('month', now.month - 1 if now.month > 1 else 12))

    _, last_day = calendar.monthrange(year, month)
    period_start = timezone.datetime(year, month, 1, tzinfo=timezone.utc)
    period_end = timezone.datetime(year, month, last_day, 23, 59, 59, tzinfo=timezone.utc)

    # Dohvati sve plaćene račune s PP u tom periodu
    receipts = POSReceipt.objects.filter(
        session__terminal__company=company,
        status='paid',
        paid_at__gte=period_start,
        paid_at__lte=period_end,
        consumption_tax_amount__gt=0,
    )

    # Agregati
    agg = receipts.aggregate(
        total_consumption_tax=Sum('consumption_tax_amount'),
        total_subtotal=Sum('subtotal'),
        receipt_count=Count('id'),
    )

    total_ct = agg['total_consumption_tax'] or Decimal('0')
    total_base = agg['total_subtotal'] or Decimal('0')
    receipt_count = agg['receipt_count'] or 0

    # Dnevni breakdown za tablicu
    daily = (
        receipts
        .extra(select={'day': "DATE(paid_at)"})
        .values('day')
        .annotate(
            daily_base=Sum('subtotal'),
            daily_tax=Sum('consumption_tax_amount'),
            daily_count=Count('id'),
        )
        .order_by('day')
    )

    # Deadline: 20. sljedećeg mjeseca
    if month == 12:
        deadline_month, deadline_year = 1, year + 1
    else:
        deadline_month, deadline_year = month + 1, year
    deadline = f'{deadline_year}-{deadline_month:02d}-20'

    # Mjeseci za navigaciju
    months = []
    for m in range(1, 13):
        months.append({'num': m, 'name': calendar.month_name[m]})

    ctx = {
        'company': company,
        'pos_settings': pos_settings,
        'year': year,
        'month': month,
        'month_name': calendar.month_name[month],
        'period_start': period_start,
        'period_end': period_end,
        'total_base': total_base,
        'total_consumption_tax': total_ct,
        'receipt_count': receipt_count,
        'tax_rate': pos_settings.consumption_tax_rate,
        'jls_name': pos_settings.consumption_tax_jls_name,
        'daily_breakdown': list(daily),
        'deadline': deadline,
        'months': months,
        'years': list(range(2024, now.year + 1)),
    }

    return render(request, 'pos/pp_mi_po_report.html', ctx)
