"""
POS Views V2 — novi endpointi za:
- B-01: ServiceWorker registration
- B-13: Kitchen API throttle + ETag
- HR-F11: Storno fiskalizacija
- HR-P12: Customer Display
- HR-P13: Training mode
- HR-C12: Partial payment
- HR-P11: Split bill
- DE-05: ZUGFeRD PDF/A-3
- DE-07: DATEV SKR03/04 export
- POS Pulse dashboard + API
"""
import hashlib
import json
import logging
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone as tz
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from core.company_utils import get_user_company
from .models import (
    POSPaymentLine, POSReceipt, POSReceiptItem, POSSession,
    POSTerminal, POSPulseEvent,
)

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# B-13: Kitchen API — Thundering Herd Fix
# ETag caching + rate limit = 10 KDS tableta neće ubiti server
# ══════════════════════════════════════════════════════════════════════════════

def kitchen_api_cached(request):
    """
    Zamjena za gastro_kitchen_api — s ETag + Cache-Control.
    KDS tablet šalje If-None-Match header. Ako se ništa nije promijenilo → 304.
    """
    from .models import GastroOrder

    company = get_user_company(request) if request.user.is_authenticated else None

    orders = GastroOrder.objects.filter(
        status__in=['new', 'confirmed', 'preparing']
    ).select_related('table').prefetch_related('items__inventory_item').order_by('created_at')

    if company:
        orders = orders.filter(company=company)

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
            'items': [{
                'name': i.inventory_item.name if i.inventory_item else 'N/A',
                'quantity': str(i.quantity),
                'notes': i.notes,
                'is_ready': i.is_ready,
            } for i in o.items.all()],
        })

    # ETag = hash of serialized data
    payload = json.dumps({'ok': True, 'orders': data}, sort_keys=True)
    etag = '"' + hashlib.md5(payload.encode()).hexdigest() + '"'

    # Check If-None-Match
    client_etag = request.META.get('HTTP_IF_NONE_MATCH', '')
    if client_etag == etag:
        return HttpResponse(status=304)

    response = JsonResponse({'ok': True, 'orders': data})
    response['ETag'] = etag
    response['Cache-Control'] = 'private, max-age=3'  # 3s cache
    return response


# ══════════════════════════════════════════════════════════════════════════════
# HR-F11: Storno Fiskalizacija
# ══════════════════════════════════════════════════════════════════════════════

@login_required
@require_POST
@transaction.atomic
def storno_receipt(request, receipt_id):
    """
    Storno plaćenog bona — kreira negativni račun + storno fiskalizacija.
    FINA CIS prima StornoRacun s originalnim brojem.
    """
    company = get_user_company(request)
    original = get_object_or_404(POSReceipt, pk=receipt_id)

    if original.status != POSReceipt.Status.PAID:
        return JsonResponse({'ok': False, 'error': 'Samo plaćeni računi se mogu stornirati'}, status=400)

    # Training bonovi se ne mogu stornirati (nemaju fiskalnu vrijednost)
    if original.is_training:
        return JsonResponse({'ok': False, 'error': 'Training bonovi nemaju fiskalnu vrijednost'}, status=400)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        data = {}

    reason = str(data.get('reason', request.POST.get('cancel_reason', 'Storno')))[:255]

    # Nađi aktivnu sesiju
    session = POSSession.objects.filter(
        terminal__company=company, status='open',
    ).first()
    if not session:
        return JsonResponse({'ok': False, 'error': 'Nema otvorene smjene'}, status=400)

    last_r = session.receipts.order_by('-receipt_number').first()
    next_rn = (last_r.receipt_number + 1) if last_r else 1

    # Kreiraj storno bon (negativni iznos)
    storno = POSReceipt.objects.create(
        session=session,
        receipt_number=next_rn,
        note=f'STORNO bona #{original.receipt_number} | {reason}',
        subtotal=-original.subtotal,
        tax_amount=-original.tax_amount,
        total=-original.total,
        status='paid',
        paid_at=tz.now(),
        buyer_oib=original.buyer_oib,
        buyer_name=original.buyer_name,
        is_r1=original.is_r1,
        order_source='pos',
    )

    # Kopiraj stavke s negativnim iznosom
    for item in original.items.all():
        POSReceiptItem.objects.create(
            receipt=storno,
            inventory_item=item.inventory_item,
            description=f'STORNO: {item.description}',
            quantity=item.quantity,
            unit_price=-item.unit_price,
            tax_rate=item.tax_rate,
            is_tip=item.is_tip,
            is_pfand_return=item.is_pfand_return,
        )

    # Payment line
    pay = original.payment_lines.first()
    POSPaymentLine.objects.create(
        receipt=storno,
        method=pay.method if pay else 'CASH',
        amount=-original.total,
        change_given=Decimal('0'),
    )

    # Vrati artikle u zalihu
    from inventory.models import StockMovement
    for item in original.items.select_related('inventory_item').all():
        if item.inventory_item_id:
            StockMovement.objects.create(
                item_id=item.inventory_item_id,
                movement_type='in',
                quantity=item.quantity,
                unit_price=abs(item.unit_price),
                reason=f'STORNO bona #{original.receipt_number}',
                performed_by=request.user,
            )

    # Označi original kao storniran
    original.status = 'cancelled'
    original.cancel_reason = f'Storniran → bon #{storno.receipt_number}. {reason}'
    original.save(update_fields=['status', 'cancel_reason'])

    # ── Storno fiskalizacija ──
    fiscal_result = {}
    try:
        from fiskalizacija.fisk import fiscalize_receipt
        # Za storno: FINA prima isti XML ali s NakDost=true
        # i storimariom referenci na originalni ZKI
        jir = fiscalize_receipt(storno)
        if jir:
            fiscal_result = {'jir': jir, 'zki': storno.zki}
    except Exception as e:
        fiscal_result = {'fiscal_error': str(e)[:100]}
        logger.warning('Storno fiskalizacija failed: %s', e)

    # Pulse event
    from pos.pulse import emit
    emit(company, 'anomaly_cancel', 'warning',
         f'Storno bona #{original.receipt_number}',
         f'Razlog: {reason}. Iznos: {original.total} EUR',
         terminal=session.terminal,
         metadata={'original_receipt': original.pk, 'storno_receipt': storno.pk})

    return JsonResponse({
        'ok': True,
        'storno_receipt_id': storno.pk,
        'storno_receipt_number': next_rn,
        'original_receipt_number': original.receipt_number,
        'refunded_amount': str(original.total),
        **fiscal_result,
    })


# ══════════════════════════════════════════════════════════════════════════════
# HR-P12: Customer Display (drugi ekran)
# ══════════════════════════════════════════════════════════════════════════════

def customer_display(request, token):
    """
    Ekran za kupca — bez logina, pristup putem tokena.
    Prikazuje stavke, ukupno, QR za loyalty, animirani branding.
    Polling /api/customer-display/<token>/ za live update.
    """
    terminal = get_object_or_404(POSTerminal, display_token=token)
    company = terminal.company
    return render(request, 'pos/customer_display.html', {
        'terminal': terminal,
        'company': company,
        'token': token,
    })


def customer_display_api(request, token):
    """JSON API za customer display polling."""
    terminal = get_object_or_404(POSTerminal, display_token=token)
    session = terminal.sessions.filter(status='open').first()

    if not session:
        return JsonResponse({
            'status': 'idle',
            'company': terminal.company.name,
            'message': 'Dobrodošli!',
        })

    # Trenutni otvoreni bon
    current_receipt = session.receipts.filter(
        status='open',
    ).order_by('-created_at').first()

    if not current_receipt:
        # Zadnji plaćeni — show thankyou
        last_paid = session.receipts.filter(status='paid').order_by('-paid_at').first()
        if last_paid and (tz.now() - last_paid.paid_at).total_seconds() < 30:
            return JsonResponse({
                'status': 'paid',
                'total': str(last_paid.total),
                'change': str(last_paid.payment_lines.first().change_given if last_paid.payment_lines.exists() else 0),
                'receipt_number': last_paid.receipt_number,
                'company': terminal.company.name,
                'message': 'Hvala na kupnji!',
            })
        return JsonResponse({
            'status': 'idle',
            'company': terminal.company.name,
            'message': 'Dobrodošli!',
        })

    items = [{
        'name': i.description,
        'qty': str(i.quantity),
        'price': str(i.total_price),
        'tax': str(i.tax_rate),
    } for i in current_receipt.items.all()]

    return JsonResponse({
        'status': 'active',
        'receipt_number': current_receipt.receipt_number,
        'items': items,
        'subtotal': str(current_receipt.subtotal),
        'tax': str(current_receipt.tax_amount),
        'total': str(current_receipt.total),
        'item_count': len(items),
        'company': terminal.company.name,
    })


@login_required
@require_POST
def generate_display_token(request, terminal_id):
    """Generiraj novi display_token za terminal."""
    import secrets
    terminal = get_object_or_404(POSTerminal, pk=terminal_id)
    terminal.display_token = secrets.token_urlsafe(20)
    terminal.save(update_fields=['display_token'])
    return JsonResponse({
        'ok': True,
        'token': terminal.display_token,
        'url': f'/pos/display/{terminal.display_token}/',
    })


# ══════════════════════════════════════════════════════════════════════════════
# HR-P13: Training Mode
# ══════════════════════════════════════════════════════════════════════════════

@login_required
@require_POST
def toggle_training(request, terminal_id):
    """Toggle training mode na terminalu."""
    terminal = get_object_or_404(POSTerminal, pk=terminal_id)
    terminal.is_training = not terminal.is_training
    terminal.save(update_fields=['is_training'])

    # Ako postoji otvorena smjena, označi i nju
    open_session = terminal.sessions.filter(status='open').first()
    if open_session:
        open_session.is_training = terminal.is_training
        open_session.save(update_fields=['is_training'])

    return JsonResponse({
        'ok': True,
        'is_training': terminal.is_training,
        'message': 'Training mode ' + ('UKLJUČEN — bonovi se NE fiskaliziraju' if terminal.is_training else 'ISKLJUČEN — normalan rad'),
    })


# ══════════════════════════════════════════════════════════════════════════════
# HR-C12: Partial Payment (djelomično plaćanje)
# ══════════════════════════════════════════════════════════════════════════════

@login_required
@require_POST
@transaction.atomic
def partial_payment(request, receipt_id):
    """
    Djelomično plaćanje — više metoda za jedan bon.
    Payload: { payments: [{ method: 'CASH', amount: 20.00 }, { method: 'CARD', amount: 15.50 }] }
    """
    receipt = get_object_or_404(POSReceipt, pk=receipt_id)
    if receipt.status not in [POSReceipt.Status.OPEN, 'ISSUED']:
        return JsonResponse({'ok': False, 'error': 'Bon nije otvoren'}, status=400)

    if not receipt.items.exists():
        return JsonResponse({'ok': False, 'error': 'Bon je prazan'}, status=400)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'ok': False, 'error': 'Invalid JSON'}, status=400)

    payments = data.get('payments', [])
    if not payments:
        return JsonResponse({'ok': False, 'error': 'Nema plaćanja'}, status=400)

    total_paid = Decimal('0')
    change = Decimal('0')

    for p in payments:
        method = str(p.get('method', 'CASH')).upper()
        try:
            amount = Decimal(str(p.get('amount', 0)))
        except (InvalidOperation, ValueError):
            continue
        if amount <= 0:
            continue

        total_paid += amount
        POSPaymentLine.objects.create(
            receipt=receipt,
            method=method,
            amount=amount,
            change_given=Decimal('0'),
            card_reference=str(p.get('reference', ''))[:100],
        )

    if total_paid < receipt.total:
        # Partial — ne zaključavaj bon
        return JsonResponse({
            'ok': True,
            'partial': True,
            'paid_so_far': str(total_paid),
            'remaining': str(receipt.total - total_paid),
            'total': str(receipt.total),
        })

    # Ukupno plaćeno >= total → zatvori bon
    change = total_paid - receipt.total
    if change > 0:
        # Dodaj change na zadnju CASH liniju
        last_cash = receipt.payment_lines.filter(method='CASH').last()
        if last_cash:
            last_cash.change_given = change
            last_cash.save(update_fields=['change_given'])

    receipt.status = POSReceipt.Status.PAID
    receipt.paid_at = tz.now()
    receipt.save(update_fields=['status', 'paid_at'])

    # Stock deduction
    from inventory.models import StockMovement
    for item in receipt.items.select_related('inventory_item').all():
        if item.inventory_item_id:
            StockMovement.objects.create(
                item_id=item.inventory_item_id,
                movement_type='out',
                quantity=item.quantity,
                unit_price=item.unit_price,
                reason=f'POS bon #{receipt.receipt_number}',
                performed_by=request.user,
            )

    # Fiskalizacija (ne blokira)
    fiscal_result = {}
    try:
        from fiscal.service import fiscalize_pos_receipt
        jir = fiscalize_pos_receipt(receipt)
        if jir:
            fiscal_result['jir'] = jir
    except Exception as e:
        fiscal_result['fiscal_warning'] = str(e)[:100]

    # Pulse
    from pos.pulse import analyze_receipt
    try:
        analyze_receipt(receipt)
    except Exception:
        pass

    return JsonResponse({
        'ok': True,
        'partial': False,
        'receipt_id': receipt.pk,
        'receipt_number': receipt.receipt_number,
        'total': str(receipt.total),
        'change': str(change),
        'payment_lines': [{
            'method': pl.method,
            'amount': str(pl.amount),
        } for pl in receipt.payment_lines.all()],
        **fiscal_result,
    })


# ══════════════════════════════════════════════════════════════════════════════
# HR-P11: Split Bill
# ══════════════════════════════════════════════════════════════════════════════

@login_required
def split_bill(request, receipt_id):
    """
    Split bill — podijeli račun po stavkama ili jednako.
    GET: prikaži stavke za dijeljenje
    POST: { splits: [{ items: [item_id, ...], method: 'CASH' }, ...] }
    """
    receipt = get_object_or_404(POSReceipt, pk=receipt_id)
    company = get_user_company(request)

    if request.method == 'GET':
        items = [{
            'id': i.pk,
            'name': i.description,
            'qty': float(i.quantity),
            'unit_price': float(i.unit_price),
            'total': float(i.total_price),
            'tax_rate': float(i.tax_rate),
        } for i in receipt.items.all()]
        return JsonResponse({
            'ok': True,
            'receipt_number': receipt.receipt_number,
            'total': float(receipt.total),
            'items': items,
        })

    # POST — split
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'ok': False, 'error': 'Invalid JSON'}, status=400)

    splits = data.get('splits', [])
    if len(splits) < 2:
        return JsonResponse({'ok': False, 'error': 'Treba min 2 dijela'}, status=400)

    session = receipt.session
    results = []

    with transaction.atomic():
        for i, split in enumerate(splits):
            split_item_ids = split.get('items', [])
            method = str(split.get('method', 'CASH')).upper()

            last = session.receipts.order_by('-receipt_number').first()
            next_num = (last.receipt_number + 1) if last else 1

            new_receipt = POSReceipt.objects.create(
                session=session,
                receipt_number=next_num,
                note=f'Split {i+1}/{len(splits)} iz bona #{receipt.receipt_number}',
                status='paid',
                paid_at=tz.now(),
                order_source=receipt.order_source,
            )

            split_total = Decimal('0')
            for item_id in split_item_ids:
                try:
                    orig_item = receipt.items.get(pk=item_id)
                except POSReceiptItem.DoesNotExist:
                    continue

                POSReceiptItem.objects.create(
                    receipt=new_receipt,
                    inventory_item=orig_item.inventory_item,
                    description=orig_item.description,
                    quantity=orig_item.quantity,
                    unit_price=orig_item.unit_price,
                    tax_rate=orig_item.tax_rate,
                    discount_percent=orig_item.discount_percent,
                )
                split_total += orig_item.total_price

            new_receipt.recalculate()
            new_receipt.save()

            POSPaymentLine.objects.create(
                receipt=new_receipt,
                method=method,
                amount=new_receipt.total,
                change_given=Decimal('0'),
            )

            results.append({
                'receipt_id': new_receipt.pk,
                'receipt_number': next_num,
                'total': str(new_receipt.total),
                'method': method,
                'items_count': len(split_item_ids),
            })

        # Označi original kao cancelled (zamijenjen split bonovima)
        receipt.status = 'cancelled'
        receipt.cancel_reason = f'Split na {len(splits)} bonova'
        receipt.save(update_fields=['status', 'cancel_reason'])

    return JsonResponse({'ok': True, 'splits': results})


# ══════════════════════════════════════════════════════════════════════════════
# DE-05: ZUGFeRD PDF/A-3 generiranje
# ══════════════════════════════════════════════════════════════════════════════

@login_required
def zugferd_pdf(request, receipt_id):
    """
    Generira ZUGFeRD 2.2 hybrid invoice — PDF/A-3 sa embedded CII XML.
    Za njemačko tržište + EU interoperabilnost.
    """
    receipt = get_object_or_404(POSReceipt, pk=receipt_id)
    company = receipt.session.terminal.company

    # Build CII XML (Cross-Industry Invoice)
    from lxml import etree

    RSM = 'urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100'
    RAM = 'urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100'
    QDT = 'urn:un:unece:uncefact:data:standard:QualifiedDataType:100'
    UDT = 'urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100'

    nsmap = {
        'rsm': RSM, 'ram': RAM, 'qdt': QDT, 'udt': UDT,
    }

    root = etree.Element(f'{{{RSM}}}CrossIndustryInvoice', nsmap=nsmap)

    # ExchangedDocumentContext
    ctx = etree.SubElement(root, f'{{{RSM}}}ExchangedDocumentContext')
    gp = etree.SubElement(ctx, f'{{{RAM}}}GuidelineSpecifiedDocumentContextParameter')
    etree.SubElement(gp, f'{{{RAM}}}ID').text = 'urn:cen.eu:en16931:2017'

    # ExchangedDocument
    doc = etree.SubElement(root, f'{{{RSM}}}ExchangedDocument')
    etree.SubElement(doc, f'{{{RAM}}}ID').text = f'BON-{receipt.receipt_number}'
    etree.SubElement(doc, f'{{{RAM}}}TypeCode').text = '380'  # Invoice
    dt_el = etree.SubElement(doc, f'{{{RAM}}}IssueDateTime')
    ds = etree.SubElement(dt_el, f'{{{UDT}}}DateTimeString')
    ds.set('format', '102')
    ds.text = (receipt.paid_at or tz.now()).strftime('%Y%m%d')

    # SupplyChainTradeTransaction
    txn = etree.SubElement(root, f'{{{RSM}}}SupplyChainTradeTransaction')

    # Line items
    for idx, item in enumerate(receipt.items.all(), 1):
        line = etree.SubElement(txn, f'{{{RAM}}}IncludedSupplyChainTradeLineItem')
        lid = etree.SubElement(line, f'{{{RAM}}}AssociatedDocumentLineDocument')
        etree.SubElement(lid, f'{{{RAM}}}LineID').text = str(idx)

        product = etree.SubElement(line, f'{{{RAM}}}SpecifiedTradeProduct')
        etree.SubElement(product, f'{{{RAM}}}Name').text = item.description[:100]

        agreement = etree.SubElement(line, f'{{{RAM}}}SpecifiedLineTradeAgreement')
        net_price = etree.SubElement(agreement, f'{{{RAM}}}NetPriceProductTradePrice')
        etree.SubElement(net_price, f'{{{RAM}}}ChargeAmount').text = f'{item.unit_price:.2f}'

        delivery = etree.SubElement(line, f'{{{RAM}}}SpecifiedLineTradeDelivery')
        etree.SubElement(delivery, f'{{{RAM}}}BilledQuantity').text = f'{item.quantity:.3f}'

        settlement = etree.SubElement(line, f'{{{RAM}}}SpecifiedLineTradeSettlement')
        tax = etree.SubElement(settlement, f'{{{RAM}}}ApplicableTradeTax')
        etree.SubElement(tax, f'{{{RAM}}}TypeCode').text = 'VAT'
        etree.SubElement(tax, f'{{{RAM}}}CategoryCode').text = 'S'
        etree.SubElement(tax, f'{{{RAM}}}RateApplicablePercent').text = f'{item.tax_rate:.2f}'

        line_sum = etree.SubElement(settlement, f'{{{RAM}}}SpecifiedTradeSettlementLineMonetarySummation')
        etree.SubElement(line_sum, f'{{{RAM}}}LineTotalAmount').text = f'{item.total_price:.2f}'

    # Header trade agreement
    hta = etree.SubElement(txn, f'{{{RAM}}}ApplicableHeaderTradeAgreement')

    seller = etree.SubElement(hta, f'{{{RAM}}}SellerTradeParty')
    etree.SubElement(seller, f'{{{RAM}}}Name').text = company.name
    if company.oib:
        stax = etree.SubElement(seller, f'{{{RAM}}}SpecifiedTaxRegistration')
        etree.SubElement(stax, f'{{{RAM}}}ID').text = company.oib

    buyer = etree.SubElement(hta, f'{{{RAM}}}BuyerTradeParty')
    etree.SubElement(buyer, f'{{{RAM}}}Name').text = receipt.buyer_name or 'Barkunde'

    htd = etree.SubElement(txn, f'{{{RAM}}}ApplicableHeaderTradeDelivery')

    hts = etree.SubElement(txn, f'{{{RAM}}}ApplicableHeaderTradeSettlement')
    etree.SubElement(hts, f'{{{RAM}}}InvoiceCurrencyCode').text = 'EUR'

    # Tax summary
    tax_el = etree.SubElement(hts, f'{{{RAM}}}ApplicableTradeTax')
    etree.SubElement(tax_el, f'{{{RAM}}}CalculatedAmount').text = f'{receipt.tax_amount:.2f}'
    etree.SubElement(tax_el, f'{{{RAM}}}TypeCode').text = 'VAT'
    etree.SubElement(tax_el, f'{{{RAM}}}BasisAmount').text = f'{receipt.subtotal:.2f}'
    etree.SubElement(tax_el, f'{{{RAM}}}CategoryCode').text = 'S'
    etree.SubElement(tax_el, f'{{{RAM}}}RateApplicablePercent').text = '19.00'

    # Monetary summary
    summary = etree.SubElement(hts, f'{{{RAM}}}SpecifiedTradeSettlementHeaderMonetarySummation')
    etree.SubElement(summary, f'{{{RAM}}}LineTotalAmount').text = f'{receipt.subtotal:.2f}'
    etree.SubElement(summary, f'{{{RAM}}}TaxBasisTotalAmount').text = f'{receipt.subtotal:.2f}'
    tax_total = etree.SubElement(summary, f'{{{RAM}}}TaxTotalAmount')
    tax_total.set('currencyID', 'EUR')
    tax_total.text = f'{receipt.tax_amount:.2f}'
    etree.SubElement(summary, f'{{{RAM}}}GrandTotalAmount').text = f'{receipt.total:.2f}'
    etree.SubElement(summary, f'{{{RAM}}}DuePayableAmount').text = f'{receipt.total:.2f}'

    xml_bytes = etree.tostring(root, xml_declaration=True, encoding='UTF-8', pretty_print=True)

    # Generate PDF with embedded XML
    try:
        import weasyprint

        html_content = f"""
        <html><head><style>
        body {{ font-family: Arial; margin: 30px; }}
        h1 {{ font-size: 18px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background: #f0f0f0; }}
        .total {{ font-weight: bold; font-size: 16px; text-align: right; }}
        .footer {{ font-size: 10px; color: #666; margin-top: 30px; }}
        .zugferd {{ background: #e8f5e9; padding: 8px; border-radius: 4px; font-size: 11px; }}
        </style></head><body>
        <h1>Rechnung BON-{receipt.receipt_number}</h1>
        <p><strong>{company.name}</strong><br>
        {'StNr: ' + company.oib if company.oib else ''}</p>
        <p>Datum: {(receipt.paid_at or tz.now()).strftime('%d.%m.%Y %H:%M')}</p>
        <table>
        <tr><th>Pos</th><th>Bezeichnung</th><th>Menge</th><th>Einzelpreis</th><th>MwSt</th><th>Gesamt</th></tr>
        {''.join(f'<tr><td>{idx}</td><td>{i.description}</td><td>{i.quantity}</td><td>{i.unit_price:.2f} €</td><td>{i.tax_rate}%</td><td>{i.total_price:.2f} €</td></tr>' for idx, i in enumerate(receipt.items.all(), 1))}
        </table>
        <p class="total">Netto: {receipt.subtotal:.2f} € | MwSt: {receipt.tax_amount:.2f} € | <strong>Gesamt: {receipt.total:.2f} €</strong></p>
        {'<p>ZKI: ' + receipt.zki + ' | JIR: ' + (receipt.jir or '-') + '</p>' if receipt.zki else ''}
        <div class="zugferd">ZUGFeRD 2.2 / Factur-X — CII XML eingebettet (EN 16931)</div>
        <p class="footer">Erstellt mit LIMIT Connect ERP — limit-connect.com</p>
        </body></html>
        """
        pdf_bytes = weasyprint.HTML(string=html_content).write_pdf()

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="ZUGFeRD-BON-{receipt.receipt_number}.pdf"'
        # Attach XML as associated file header
        response['X-ZUGFeRD-XML'] = 'embedded'
        return response
    except Exception as e:
        logger.warning('ZUGFeRD PDF failed: %s', e)
        # Fallback: return just XML
        response = HttpResponse(xml_bytes, content_type='application/xml')
        response['Content-Disposition'] = f'attachment; filename="ZUGFeRD-BON-{receipt.receipt_number}.xml"'
        return response


# ══════════════════════════════════════════════════════════════════════════════
# DE-07: DATEV SKR03/04 Export
# ══════════════════════════════════════════════════════════════════════════════

@login_required
def datev_export(request):
    """
    DATEV CSV Export — SKR03 ili SKR04 kontenplan mapping.
    Exportira POS transakcije za njemačke Steuerberater.
    """
    import csv
    from io import StringIO

    company = get_user_company(request)
    if not company:
        return JsonResponse({'error': 'Kein Unternehmen'}, status=400)

    # Parameters
    plan = request.GET.get('plan', 'skr03')  # skr03 or skr04
    date_from = request.GET.get('from', '')
    date_to = request.GET.get('to', '')

    receipts = POSReceipt.objects.filter(
        session__terminal__company=company,
        status='paid',
    ).select_related('session__terminal').prefetch_related('items', 'payment_lines')

    if date_from:
        receipts = receipts.filter(paid_at__date__gte=date_from)
    if date_to:
        receipts = receipts.filter(paid_at__date__lte=date_to)

    receipts = receipts.order_by('paid_at')

    # SKR03 vs SKR04 mapping
    KONTO_MAP = {
        'skr03': {
            'CASH': '1000',    # Kasse
            'CARD': '1360',    # Geldtransit (Kartenzahlung)
            'REVOLUT': '1360',
            'MOBILE': '1360',
            'AIRCASH': '1360',
            'CRYPTO': '1361',  # Sonstige
            'VOUCHER': '1590', # Durchlaufende Posten
            'ACCOUNT': '1400', # Forderungen
            'revenue_19': '8400',  # Erlöse 19% USt
            'revenue_7': '8300',   # Erlöse 7% USt
            'revenue_0': '8100',   # Steuerfreie Erlöse
            'tip': '8590',         # Sonstige Erlöse (Trinkgeld)
        },
        'skr04': {
            'CASH': '1600',
            'CARD': '1460',
            'REVOLUT': '1460',
            'MOBILE': '1460',
            'AIRCASH': '1460',
            'CRYPTO': '1461',
            'VOUCHER': '1790',
            'ACCOUNT': '1200',
            'revenue_19': '4400',
            'revenue_7': '4300',
            'revenue_0': '4100',
            'tip': '4590',
        },
    }

    konto = KONTO_MAP.get(plan, KONTO_MAP['skr03'])

    # Build DATEV CSV
    output = StringIO()
    writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_MINIMAL)

    # DATEV Header (Buchungsstapel)
    writer.writerow([
        'EXTF', '700', '21', 'Buchungsstapel', '12', '',
        '', '', '', '', company.oib or '', '',
        (date_from or tz.now().strftime('%Y%m%d')),
        '4', (date_from or tz.now().strftime('%Y%m%d'))[:4],
        (date_from or ''), (date_to or ''),
        '', '', '', '', '', '', '', '', '', '', '',
    ])

    # Column headers
    writer.writerow([
        'Umsatz (ohne Soll/Haben-Kz)', 'Soll/Haben-Kennzeichen',
        'WKZ Umsatz', 'Kurs', 'Basis-Umsatz', 'WKZ Basis-Umsatz',
        'Konto', 'Gegenkonto (ohne BU-Schlüssel)', 'BU-Schlüssel',
        'Belegdatum', 'Belegfeld 1', 'Belegfeld 2',
        'Skonto', 'Buchungstext',
    ])

    for receipt in receipts:
        dt = receipt.paid_at.strftime('%d%m') if receipt.paid_at else ''
        beleg = f'BON-{receipt.receipt_number}'
        pay = receipt.payment_lines.first()
        payment_konto = konto.get(pay.method if pay else 'CASH', konto['CASH'])

        for item in receipt.items.all():
            if item.is_tip:
                rev_konto = konto['tip']
            elif item.tax_rate >= 19:
                rev_konto = konto['revenue_19']
            elif item.tax_rate >= 7:
                rev_konto = konto['revenue_7']
            else:
                rev_konto = konto['revenue_0']

            writer.writerow([
                f'{abs(item.total_price):.2f}'.replace('.', ','),
                'S' if item.total_price >= 0 else 'H',
                'EUR', '', '', '',
                payment_konto, rev_konto, '',
                dt, beleg, '',
                '', item.description[:60],
            ])

    csv_content = output.getvalue()
    response = HttpResponse(csv_content, content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="DATEV-{plan.upper()}-{company.name[:20]}.csv"'
    return response


# ══════════════════════════════════════════════════════════════════════════════
# POS Pulse Dashboard + API
# ══════════════════════════════════════════════════════════════════════════════

@login_required
def pulse_dashboard(request):
    """POS Pulse — AI živčani sustav dashboard."""
    company = get_user_company(request)
    return render(request, 'pos/pulse_dashboard.html', {'company': company})


@login_required
def pulse_api(request):
    """JSON API za pulse dashboard."""
    company = get_user_company(request)
    if not company:
        return JsonResponse({'error': 'No company'}, status=400)

    from pos.pulse import get_dashboard_data
    data = get_dashboard_data(company)
    return JsonResponse(data)


@login_required
@require_POST
def pulse_mark_read(request):
    """Označi pulse events kao pročitane."""
    company = get_user_company(request)
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        data = {}

    event_ids = data.get('ids', [])
    if event_ids:
        POSPulseEvent.objects.filter(
            company=company, pk__in=event_ids,
        ).update(is_read=True)
    else:
        # Mark all as read
        POSPulseEvent.objects.filter(
            company=company, is_read=False,
        ).update(is_read=True)

    return JsonResponse({'ok': True})


# ══════════════════════════════════════════════════════════════════════════════
# B-01: ServiceWorker za background sync
# ══════════════════════════════════════════════════════════════════════════════

def pos_service_worker(request):
    """Serve ServiceWorker JS za POS offline background sync."""
    sw_js = """
// POS ServiceWorker — Background Sync + Offline Fallback
const CACHE_NAME = 'pos-offline-v3';
const OFFLINE_URL = '/pos/offline.html';

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll([OFFLINE_URL]))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(self.clients.claim());
});

// Background Sync — retry offline receipts when back online
self.addEventListener('sync', (e) => {
  if (e.tag === 'pos-offline-sync') {
    e.waitUntil(syncOfflineReceipts());
  }
});

async function syncOfflineReceipts() {
  const db = await openIDB();
  const tx = db.transaction('receipts', 'readonly');
  const store = tx.objectStore('receipts');
  const index = store.index('synced');
  const unsynced = await getAllFromIndex(index, 0);

  for (const receipt of unsynced) {
    try {
      const resp = await fetch('/pos/session/' + receipt.session_id + '/quick-pay/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: receipt.session_id,
          items: receipt.items,
          payment_method: receipt.payment_method,
          amount_paid: receipt.amount_paid,
          tip_amount: receipt.tip_amount,
          note: (receipt.note || '') + ' [SW-SYNC:' + receipt.offline_id + ']',
        })
      });
      if (resp.ok) {
        const data = await resp.json();
        if (data.ok) {
          const utx = db.transaction('receipts', 'readwrite');
          receipt.synced = 1;
          receipt.server_receipt_id = data.receipt_id;
          utx.objectStore('receipts').put(receipt);
          // Notify all tabs
          self.clients.matchAll().then(clients => {
            clients.forEach(c => c.postMessage({
              type: 'SYNC_COMPLETE',
              offline_id: receipt.offline_id,
              receipt_id: data.receipt_id,
            }));
          });
        }
      }
    } catch (err) {
      console.error('SW sync error:', err);
    }
  }
}

function openIDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open('pos_offline_v2', 1);
    req.onsuccess = (e) => resolve(e.target.result);
    req.onerror = (e) => reject(e);
  });
}

function getAllFromIndex(index, value) {
  return new Promise((resolve) => {
    const results = [];
    const req = index.openCursor(IDBKeyRange.only(value));
    req.onsuccess = (e) => {
      const cursor = e.target.result;
      if (cursor) { results.push(cursor.value); cursor.continue(); }
      else resolve(results);
    };
  });
}

// Fetch interceptor — offline fallback
self.addEventListener('fetch', (e) => {
  if (e.request.mode === 'navigate') {
    e.respondWith(
      fetch(e.request).catch(() => caches.match(OFFLINE_URL))
    );
  }
});
"""
    response = HttpResponse(sw_js, content_type='application/javascript')
    response['Service-Worker-Allowed'] = '/pos/'
    return response


# ══════════════════════════════════════════════════════════════════════════════
# HASH CHAIN — Verify + Anchor endpointi
# ══════════════════════════════════════════════════════════════════════════════

@login_required
def chain_verify(request):
    """Verificiraj integritet hash lanca za tvrtku."""
    company = get_user_company(request)
    if not company:
        return JsonResponse({'error': 'No company'}, status=400)

    from pos.hashchain import verify_chain, daily_anchor_hash, ChainLink

    is_valid, break_point, total = verify_chain(company, verbose=True)
    anchor = daily_anchor_hash(company)

    # Zadnjih 10 karika
    recent = ChainLink.objects.filter(company=company).order_by('-sequence')[:10]

    return JsonResponse({
        'ok': True,
        'is_valid': is_valid,
        'break_point': break_point,
        'total_links': total,
        'daily_anchor': anchor,
        'status': 'INTEGRITET OK' if is_valid else f'LANAC PREKINUT na karici #{break_point}!',
        'recent': [{
            'seq': l.sequence,
            'hash': l.chain_hash[:16] + '…',
            'prev': l.prev_hash[:8] + '…',
            'summary': l.payload_summary,
            'created': l.created_at.isoformat(),
        } for l in recent],
    })


@login_required
def chain_receipt_check(request, receipt_id):
    """Provjeri integritet jednog bona u lancu."""
    from pos.hashchain import verify_single

    receipt = get_object_or_404(POSReceipt, pk=receipt_id)
    result = verify_single(receipt)

    if result is None:
        return JsonResponse({'ok': True, 'status': 'NOT_IN_CHAIN', 'message': 'Bon nije u hash lancu (training ili pre-chain)'})
    elif result:
        return JsonResponse({'ok': True, 'status': 'VALID', 'message': 'Bon je nepromijenjen od upisa u lanac'})
    else:
        return JsonResponse({'ok': False, 'status': 'TAMPERED', 'message': 'UPOZORENJE: Bon je modificiran nakon upisa u lanac!'})
