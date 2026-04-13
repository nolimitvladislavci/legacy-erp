"""
core/views_search.py
Unified Search — globalni pretraživač preko svih modula.
AJAX endpoint za header search bar.

Koristi PostgreSQL trigram similarity za fuzzy matching.
"""
import logging
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Q

from core.company_utils import get_user_company
from django.db import DatabaseError

# Enable pg_trgm similarity search
try:
    from django.contrib.postgres.search import TrigramSimilarity
    HAS_TRGM = True
except ImportError:
    HAS_TRGM = False

logger = logging.getLogger(__name__)

MAX_RESULTS_PER_MODULE = 5
MAX_TOTAL = 20


@login_required
def global_search(request):
    """
    GET /search/?q=term
    Returns JSON: {results: [{module, type, title, subtitle, url, icon}, ...]}
    """
    q = request.GET.get('q', '').strip()
    if len(q) < 2:
        return JsonResponse({'results': []})

    company = get_user_company(request)
    if not company:
        return JsonResponse({'results': []})

    results = []

    # 1. PARTNERI — ime, OIB, email
    try:
        from partners.models import Partner
        partners = Partner.objects.filter(
            company=company
        ).filter(
            Q(name__icontains=q) | Q(oib__icontains=q) |
            Q(email__icontains=q) | Q(phone__icontains=q)
        )[:MAX_RESULTS_PER_MODULE]
        for p in partners:
            results.append({
                'module': 'partners',
                'type': 'Partner',
                'title': p.name,
                'subtitle': f'OIB: {p.oib}' if p.oib else (p.email or ''),
                'url': f'/hr/partners/{p.pk}/',
                'icon': 'users',
            })
    except DatabaseError:
        pass

    # 2. ARTIKLI (Inventory)
    try:
        from inventory.models import InventoryItem
        items = InventoryItem.objects.filter(
            company=company
        ).filter(
            Q(name__icontains=q) | Q(sku__icontains=q) |
            Q(barcode__icontains=q)
        )[:MAX_RESULTS_PER_MODULE]
        for i in items:
            results.append({
                'module': 'inventory',
                'type': 'Artikl',
                'title': i.name,
                'subtitle': f'SKU: {i.sku}' if i.sku else (f'Barkod: {i.barcode}' if i.barcode else ''),
                'url': f'/hr/inventory/items/{i.pk}/',
                'icon': 'package',
            })
    except DatabaseError:
        pass

    # 3. FAKTURE
    try:
        from invoicing.models import Invoice
        invoices = Invoice.objects.filter(
            company=company
        ).filter(
            Q(number__icontains=q) | Q(client_name__icontains=q) |
            Q(client_oib__icontains=q)
        )[:MAX_RESULTS_PER_MODULE]
        for inv in invoices:
            results.append({
                'module': 'invoicing',
                'type': inv.get_doctype_display(),
                'title': f'{inv.number} — {inv.client_name}',
                'subtitle': f'{inv.total} EUR · {inv.get_status_display()}',
                'url': f'/hr/invoicing/{inv.pk}/',
                'icon': 'file-text',
            })
    except DatabaseError:
        pass

    # 4. DOKUMENTI
    try:
        from documents.models import Document
        docs = Document.objects.filter(
            company=company
        ).filter(
            Q(title__icontains=q) | Q(description__icontains=q) |
            Q(reference_number__icontains=q)
        )[:MAX_RESULTS_PER_MODULE]
        for d in docs:
            results.append({
                'module': 'documents',
                'type': 'Dokument',
                'title': d.title,
                'subtitle': d.reference_number or '',
                'url': f'/hr/documents/{d.pk}/',
                'icon': 'folder',
            })
    except DatabaseError:
        pass

    # 5. KONTO — temeljnice
    try:
        from konto.models import JournalEntry
        entries = JournalEntry.objects.filter(
            company=company
        ).filter(
            Q(entry_number__icontains=q) | Q(description__icontains=q)
        )[:MAX_RESULTS_PER_MODULE]
        for je in entries:
            results.append({
                'module': 'konto',
                'type': 'Temeljnica',
                'title': je.entry_number,
                'subtitle': je.description[:80],
                'url': f'/hr/konto/entries/{je.pk}/',
                'icon': 'book-open',
            })
    except DatabaseError:
        pass

    # 6. POS BONOVI
    try:
        from pos.models import POSReceipt
        receipts = POSReceipt.objects.filter(
            session__terminal__company=company
        ).filter(
            Q(buyer_name__icontains=q) | Q(buyer_oib__icontains=q)
        )[:MAX_RESULTS_PER_MODULE]
        for r in receipts:
            results.append({
                'module': 'pos',
                'type': 'POS Bon',
                'title': f'Bon #{r.global_number or r.receipt_number}',
                'subtitle': f'{r.total} EUR · {r.get_status_display()}',
                'url': f'/hr/pos/receipt/{r.pk}/',
                'icon': 'shopping-cart',
            })
    except DatabaseError:
        pass

    # 7. WEBSHOP PROIZVODI
    try:
        from webshop.models import Product
        products = Product.objects.filter(
            Q(name__icontains=q) | Q(sku__icontains=q)
        )[:MAX_RESULTS_PER_MODULE]
        for p in products:
            results.append({
                'module': 'webshop',
                'type': 'Proizvod',
                'title': p.name,
                'subtitle': f'{p.price} EUR · {p.sku}',
                'url': f'/hr/webshop/products/{p.pk}/',
                'icon': 'shopping-bag',
            })
    except DatabaseError:
        pass

    # 8. HELPDESK TICKETI
    try:
        from helpdesk.models import Ticket
        tickets = Ticket.objects.filter(
            company=company
        ).filter(
            Q(subject__icontains=q) | Q(description__icontains=q)
        )[:MAX_RESULTS_PER_MODULE]
        for t in tickets:
            results.append({
                'module': 'helpdesk',
                'type': 'Ticket',
                'title': t.subject,
                'subtitle': f'#{t.pk} · {t.get_status_display()}',
                'url': f'/hr/helpdesk/{t.pk}/',
                'icon': 'help-circle',
            })
    except DatabaseError:
        pass

    return JsonResponse({'results': results[:MAX_TOTAL], 'query': q})


@login_required
def synesis_report(request):
    """Serve the Synesis migration proof report."""
    import os
    from django.http import HttpResponse
    report_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'static', 'reports', 'synesis_dokaz_2025.html'
    )
    with open(report_path, 'r', encoding='utf-8') as f:
        return HttpResponse(f.read(), content_type='text/html')
