from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from rest_framework import viewsets

from core.company_utils import get_user_company
from partners.models import Partner
from permissions.decorators import require_permission

from .models import Transaction
from .serializers import TransactionSerializer


@login_required
def transaction_list(request):
    q = request.GET.get("q", "")
    direction = request.GET.get("direction", "")
    company_id = request.GET.get("company", "")

    qs = Transaction.objects.select_related("partner", "company", "document").order_by("-date")
    if q:
        qs = qs.filter(Q(description__icontains=q)|Q(partner__name__icontains=q))
    if direction:
        qs = qs.filter(direction=direction)
    if company_id:
        qs = qs.filter(company_id=company_id)

    total_in  = qs.filter(direction="income").aggregate(s=Sum("amount"))["s"] or 0
    total_out = qs.filter(direction="expense").aggregate(s=Sum("amount"))["s"] or 0
    balance   = total_in - total_out

    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get("page"))

    return render(request, "finance/transaction_list.html", {
        "page_obj": page, "q": q, "direction": direction, "company_id": company_id,
        "total_in": total_in, "total_out": total_out, "balance": balance,
        "companies": [get_user_company(request)] if get_user_company(request) else [],
        "total": qs.count(),
    })


@require_permission("finance.create")
@login_required
def transaction_create(request):
    if request.method == "POST":
        try:
            company = get_user_company(request)
            if not company:
                messages.error(request, 'Nema aktivne firme.')
                return redirect('finance:list')
            partner = Partner.objects.get(pk=request.POST["partner"])
            t = Transaction(
                company=company,
                partner=partner,
                amount=request.POST["amount"],
                direction=request.POST["direction"],
                date=request.POST["date"],
                description=request.POST.get("description", ""),
            )
            t.save()
            partner.update_balance()
            messages.success(request, "Transakcija kreirana.")
            return redirect("finance:list")
        except Exception as e:
            messages.error(request, str(e))
    return render(request, "finance/transaction_form.html", {
        "companies": [get_user_company(request)] if get_user_company(request) else [],
        "partners": Partner.objects.filter(is_active=True).order_by("name"),
        "action": "Nova transakcija",
    })


@require_permission("finance.delete")
@login_required
def transaction_delete(request, pk):
    t = get_object_or_404(Transaction, pk=pk)
    if request.method == "POST":
        partner = t.partner
        t.delete()
        try:
            partner.update_balance()
        except Exception:
            pass
        messages.success(request, "Transakcija obrisana.")
        return redirect("finance:list")
    return redirect("finance:list")


class TransactionViewSet(viewsets.ModelViewSet):
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer


@login_required
def bank_import_csv(request):
    import csv, io, uuid, datetime as _dt
    from decimal import Decimal, InvalidOperation
    from django.contrib import messages
    from django.shortcuts import get_object_or_404
    from konto.models import BankAccount, BankTransaction
    from core.company_utils import get_user_company
    company = get_user_company(request)
    if not company:
        messages.error(request, 'Nema aktivne tvrtke.')
        return redirect('finance:list')
    banks = BankAccount.objects.filter(company=company, is_active=True)
    if request.method != 'POST':
        return render(request, 'konto/bank_import.html', {'banks': banks})
    bank_id = request.POST.get('bank_account')
    csvfile = request.FILES.get('csvfile')
    if not bank_id or not csvfile:
        messages.error(request, 'Odaberi ziro racun i CSV datoteku.')
        return render(request, 'konto/bank_import.html', {'banks': banks})
    ba = get_object_or_404(BankAccount, pk=bank_id, company=company)
    content = csvfile.read().decode('utf-8-sig', errors='replace')
    delim = ';' if content.count(';') > content.count(',') else ','
    reader = csv.DictReader(io.StringIO(content), delimiter=delim)
    hdrs = [h.strip().lower() for h in (reader.fieldnames or [])]
    if any('buchungstag' in h for h in hdrs) and any('beguenstigter' in h or 'auftraggeber' in h for h in hdrs):
        fmt = 'commerzbank'
    elif any('buchungsdatum' in h for h in hdrs):
        fmt = 'dkb'
    else:
        fmt = 'generic'
    def col(row, *keys):
        for k in keys:
            for rk in row:
                if rk.strip().lower() == k.lower(): return (row[rk] or '').strip()
        return ''
    def parse_amt(s):
        s = s.strip().replace(' ','').replace('\u20ac','').replace('EUR','')
        if ',' in s and '.' in s:
            s = s.replace('.','').replace(',','.') if s.rfind(',') > s.rfind('.') else s.replace(',','')
        elif ',' in s: s = s.replace(',','.')
        try: return Decimal(s)
        except Exception: return None
    DATE_FMTS = ['%d.%m.%Y','%Y-%m-%d','%d/%m/%Y','%d.%m.%y']
    def parse_date(s):
        for f in DATE_FMTS:
            try: return _dt.datetime.strptime(s.strip(), f).date()
            except Exception: pass
        return None
    batch_id = str(uuid.uuid4())[:8]
    created = skipped = errors = 0
    for row in reader:
        try:
            if fmt == 'commerzbank':
                d = col(row,'Buchungstag','buchungstag','Valutadatum')
                cp = col(row,'Auftraggeber / Beguenstigter','Beguenstigter/Auftraggeber')
                desc = col(row,'Verwendungszweck','verwendungszweck')
                amt_s = col(row,'Betrag','betrag')
                ref = col(row,'Referenz','Glaeubiger-ID')
            elif fmt == 'dkb':
                d = col(row,'Buchungsdatum','Buchungstag')
                cp = col(row,'Beguenstigter / Auftraggeber','Glaeubiger')
                desc = col(row,'Verwendungszweck')
                amt_s = col(row,'Betrag (EUR)','Betrag')
                ref = col(row,'Mandatsreferenz','Glaeubiger-ID')
            else:
                d = col(row,'Datum','Date','Buchungstag','Valutadatum','buchungsdatum')
                cp = col(row,'Name','Auftraggeber','Empfaenger','counterparty','Beguenstigter')
                desc = col(row,'Verwendungszweck','Betreff','description','memo','Buchungstext')
                amt_s = col(row,'Betrag','Amount','amount','Umsatz')
                ref = col(row,'Referenz','Reference')
            if not d or not amt_s: errors += 1; continue
            txn_date = parse_date(d)
            if not txn_date: errors += 1; continue
            amount = parse_amt(amt_s)
            if amount is None: errors += 1; continue
            txn_type = 'inflow' if amount >= 0 else 'outflow'
            amount = abs(amount)
            ext_id = '{}_{}_{}'.format(d, amt_s, cp[:20])
            if BankTransaction.objects.filter(bank_account=ba, external_id=ext_id).exists():
                skipped += 1; continue
            BankTransaction.objects.create(
                bank_account=ba, company=company,
                transaction_date=txn_date, value_date=txn_date,
                amount=amount, transaction_type=txn_type,
                counterparty_name=cp[:300], description=desc[:500] if desc else '',
                reference_number=ref[:100] if ref else '',
                import_batch=batch_id, external_id=ext_id,
            )
            created += 1
        except Exception: errors += 1
    ba.recalculate_balance()
    if created:
        messages.success(request, 'Importirano {} | Duplikati: {} | Greske: {}'.format(created, skipped, errors))
    else:
        messages.warning(request, 'Nema novih transakcija. Duplikati: {}, Greske: {}'.format(skipped, errors))
    return redirect('konto:transactions')


@login_required
def cashflow_api(request):
    import datetime as _dt
    from konto.models import BankTransaction
    from core.company_utils import get_user_company
    from django.db.models import Sum
    company = get_user_company(request)
    today = _dt.date.today()
    labels, inflows, outflows = [], [], []
    for i in range(5, -1, -1):
        m_start = (today.replace(day=1) - _dt.timedelta(days=i*28)).replace(day=1)
        m_end = (m_start.replace(day=28) + _dt.timedelta(days=4)).replace(day=1)
        qs = BankTransaction.objects.filter(company=company, transaction_date__gte=m_start, transaction_date__lt=m_end)
        inf = float(qs.filter(transaction_type='inflow').aggregate(s=Sum('amount'))['s'] or 0)
        out = float(qs.filter(transaction_type='outflow').aggregate(s=Sum('amount'))['s'] or 0)
        labels.append(m_start.strftime("%b '%y"))
        inflows.append(inf)
        outflows.append(out)
    from django.http import JsonResponse
    return JsonResponse({'labels': labels, 'inflows': inflows, 'outflows': outflows})


@login_required
def report_pnl_pdf(request):
    import datetime as _dt
    from django.http import HttpResponse
    from core.company_utils import get_user_company
    from konto import services
    from django.utils import timezone
    company = get_user_company(request)
    if not company:
        from django.contrib import messages
        messages.error(request, 'Nema aktivne tvrtke.')
        return redirect('konto:report_pnl')
    today = timezone.now().date()
    date_from = request.GET.get('from', str(_dt.date(today.year, 1, 1)))
    date_to = request.GET.get('to', str(today))
    try:
        df = _dt.date.fromisoformat(date_from)
        dt = _dt.date.fromisoformat(date_to)
    except ValueError:
        df = _dt.date(today.year, 1, 1)
        dt = today
    pnl = services.get_profit_loss(company, df, dt)
    html = render(request, 'konto/report_pnl_pdf.html', {
        'report': pnl, 'date_from': str(df), 'date_to': str(dt),
        'company': company, 'today': today,
    }).content.decode('utf-8')
    try:
        import weasyprint
        pdf = weasyprint.HTML(string=html, base_url=request.build_absolute_uri('/')).write_pdf()
        resp = HttpResponse(pdf, content_type='application/pdf')
        resp['Content-Disposition'] = 'attachment; filename="RDG_{}-{}.pdf"'.format(df, dt)
        return resp
    except Exception as e:
        from django.contrib import messages
        messages.error(request, 'PDF greska: {}'.format(e))
        return redirect('konto:report_pnl')


@login_required
def report_vat_pdf(request, pk):
    import datetime as _dt
    from django.http import HttpResponse
    from django.utils import timezone
    from konto.models import TaxPeriod
    from core.company_utils import get_user_company
    company = get_user_company(request)
    period = get_object_or_404(TaxPeriod, pk=pk, company=company)
    html = render(request, 'konto/report_vat_pdf.html', {
        'period': period,
        'lines': period.line_details.all().order_by('-tax_rate'),
        'company': company,
        'today': timezone.now().date(),
    }).content.decode('utf-8')
    try:
        import weasyprint
        pdf = weasyprint.HTML(string=html, base_url=request.build_absolute_uri('/')).write_pdf()
        resp = HttpResponse(pdf, content_type='application/pdf')
        resp['Content-Disposition'] = 'attachment; filename="PDV_{}.pdf"'.format(period)
        return resp
    except Exception as e:
        from django.contrib import messages
        messages.error(request, 'PDF greska: {}'.format(e))
        return redirect('konto:report_vat')


# Dodati u finance/views.py — novi view za XML import (camt.053)
# + novi view za pain.001 download
# + novi view za discrepancies lista

@login_required
def bank_import_xml(request):
    """
    camt.053 XML import — zamjena za ručni CSV unos.
    Podržava ZABA, PBZ, Erste, OTP (sve .02 i .08 namespace varijante).
    Nakon importa poziva auto_match_transactions().
    """
    from konto.models import BankAccount
    from konto import services as konto_services
    from core.company_utils import get_user_company
    from .bank_parsers import SEPACamtParser
    import uuid

    company = get_user_company(request)
    if not company:
        messages.error(request, 'Nema aktivne tvrtke.')
        return redirect('finance:list')

    banks = BankAccount.objects.filter(company=company, is_active=True)

    if request.method != 'POST':
        return render(request, 'konto/bank_import_xml.html', {'banks': banks})

    xmlfile = request.FILES.get('xmlfile')
    if not xmlfile:
        messages.error(request, 'Odaberi XML datoteku.')
        return render(request, 'konto/bank_import_xml.html', {'banks': banks})

    # Validacija: max 10 MB
    if xmlfile.size > 10 * 1024 * 1024:
        messages.error(request, 'Datoteka je prevelika (max 10 MB).')
        return render(request, 'konto/bank_import_xml.html', {'banks': banks})

    try:
        xml_content = xmlfile.read()
        parser = SEPACamtParser(xml_content)
        import_batch = str(uuid.uuid4())[:8]
        stats = parser.parse(company=company, import_batch=import_batch)
    except Exception as e:
        messages.error(request, f'Greška pri parsiranju XML-a: {e}')
        return render(request, 'konto/bank_import_xml.html', {'banks': banks})

    # Auto-match nakon importa
    matched_pairs = []
    if stats['created'] > 0:
        try:
            matched_pairs = konto_services.auto_match_transactions(company)
        except Exception:
            pass

    # Izvještaj
    if stats['created'] > 0:
        msg = (
            f"Importirano {stats['created']} transakcija | "
            f"Duplikati: {stats['skipped']} | "
            f"Greške: {stats['errors']} | "
            f"Auto-pariranih: {len(matched_pairs)}"
        )
        if stats['unresolved_ibans']:
            msg += f" | ⚠ Nepoznati IBAN-ovi: {', '.join(stats['unresolved_ibans'])}"
        messages.success(request, msg)
    else:
        messages.warning(
            request,
            f'Nema novih transakcija. '
            f'Duplikati: {stats["skipped"]}, Greške: {stats["errors"]}'
        )

    return redirect('konto:transactions')


@login_required
def bank_pain001_suppliers(request):
    """
    Generira pain.001 XML za plaćanje dobavljača.
    GET: forma za odabir faktura
    POST: download XML datoteke
    """
    from django.http import HttpResponse
    from konto.models import BankAccount
    from core.company_utils import get_user_company
    from .bank_parsers import Pain001Generator
    from invoicing.models import Invoice
    from partners.models import Partner

    company = get_user_company(request)
    if not company:
        messages.error(request, 'Nema aktivne tvrtke.')
        return redirect('finance:list')

    banks = BankAccount.objects.filter(company=company, is_active=True)

    # Dohvati neplaćene dobavljačke fakture s IBAN-om
    supplier_ids = Partner.objects.filter(
        company=company, partner_type='supplier',
    ).exclude(iban='').values_list('pk', flat=True)

    pending_invoices = Invoice.objects.filter(
        company=company,
        status__in=['UNPAID', 'OVERDUE'],
        doctype='R',
        partner__in=supplier_ids,
    ).select_related('partner').order_by('-date_due')

    if request.method == 'GET':
        return render(request, 'konto/pain001_suppliers.html', {
            'banks': banks,
            'pending_invoices': pending_invoices,
        })

    # POST — generiraj XML
    bank_id = request.POST.get('bank_account')
    invoice_ids = request.POST.getlist('invoice_ids')

    if not bank_id:
        messages.error(request, 'Odaberi žiro račun.')
        return redirect(request.path)

    try:
        bank_account = BankAccount.objects.get(pk=bank_id, company=company)
        gen = Pain001Generator(
            company=company,
            bank_account=bank_account,
            initiating_user=request.user,
        )
        xml_bytes = gen.generate_supplier_payments(
            invoice_ids=[int(i) for i in invoice_ids] if invoice_ids else None
        )
    except ValueError as e:
        messages.error(request, str(e))
        return redirect(request.path)
    except Exception as e:
        messages.error(request, f'Greška pri generiranju XML-a: {e}')
        return redirect(request.path)

    from django.utils import timezone
    filename = f"pain001_dobavljaci_{timezone.now().strftime('%Y%m%d_%H%M')}.xml"
    resp = HttpResponse(xml_bytes, content_type='application/xml')
    resp['Content-Disposition'] = f'attachment; filename="{filename}"'
    return resp


@login_required
def bank_pain001_salaries(request):
    """
    Generira pain.001 XML za isplatu plaća za odabrani obračunski period.
    """
    from django.http import HttpResponse
    import datetime
    from konto.models import BankAccount
    from core.company_utils import get_user_company
    from .bank_parsers import Pain001Generator

    company = get_user_company(request)
    if not company:
        return redirect('finance:list')

    banks = BankAccount.objects.filter(company=company, is_active=True)

    if request.method == 'GET':
        today = datetime.date.today()
        first = today.replace(day=1)
        return render(request, 'konto/pain001_salaries.html', {
            'banks': banks,
            'default_from': first.isoformat(),
            'default_to': today.isoformat(),
        })

    bank_id = request.POST.get('bank_account')
    period_from = request.POST.get('period_from')
    period_to   = request.POST.get('period_to')

    try:
        bank_account = BankAccount.objects.get(pk=bank_id, company=company)
        d_from = datetime.date.fromisoformat(period_from)
        d_to   = datetime.date.fromisoformat(period_to)
        gen = Pain001Generator(
            company=company,
            bank_account=bank_account,
            initiating_user=request.user,
        )
        xml_bytes = gen.generate_salary_payments(d_from, d_to)
    except ValueError as e:
        messages.error(request, str(e))
        return redirect(request.path)
    except Exception as e:
        messages.error(request, f'Greška: {e}')
        return redirect(request.path)

    filename = f"pain001_place_{period_from}_{period_to}.xml"
    resp = HttpResponse(xml_bytes, content_type='application/xml')
    resp['Content-Disposition'] = f'attachment; filename="{filename}"'
    return resp


@login_required
def bank_discrepancies(request):
    """
    Lista parcijalnih uplata i financijskih odstupanja.
    Destinacija klika s Kontrolnog Tornja — widget 'Financijska odstupanja'.
    """
    from core.company_utils import get_user_company
    from .bank_parsers import get_partial_payment_discrepancies

    company = get_user_company(request)
    if not company:
        return redirect('finance:list')

    discrepancies = get_partial_payment_discrepancies(company)
    total_gap = sum(d['gap'] for d in discrepancies)

    return render(request, 'konto/bank_discrepancies.html', {
        'discrepancies': discrepancies,
        'total_gap': total_gap,
        'count': len(discrepancies),
    })


# ══════════════════════════════════════════════════════════════════════════════
# Discrepancies — Clean read-only view (works on any browser)
# ══════════════════════════════════════════════════════════════════════════════

@login_required
def bank_discrepancies_legacy(request):
    """
    Server-rendered discrepancy table — no JS, works everywhere.
    Uses get_partial_payment_discrepancies() from bank_parsers.
    """
    from core.company_utils import get_user_company
    from .bank_parsers import get_partial_payment_discrepancies

    company = get_user_company(request)
    discrepancies = get_partial_payment_discrepancies(company) if company else []
    total_gap = sum(d['gap'] for d in discrepancies)

    return render(request, 'finance/discrepancies_legacy.html', {
        'discrepancies': discrepancies,
        'total_gap': total_gap,
        'count': len(discrepancies),
    })
