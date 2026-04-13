"""Reports & Guide Views — knjiga_ura_ira, pdv_obrazac, revizija, label_manage,
arhiva_upute, arhiva_guide_pdf, verfahrensdokumentation, verfahren_sign."""
import csv
import io
import json
import logging
import os
import zipfile
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.db import DatabaseError, IntegrityError
from django.db.models import Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from core.company_utils import get_user_company

from .models import ArhivaEntry, ArhivaLabel

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════
# LABEL MANAGE
# ════════════════════════════════════════════════════════════

@login_required
def label_manage(request):
    """CRUD for ArhivaLabel via AJAX."""
    company = get_user_company(request)
    if not company:
        return JsonResponse({'error': 'No company'}, status=400)

    if request.method == 'GET':
        labels = ArhivaLabel.objects.filter(company=company).order_by('name')
        return JsonResponse({'labels': [
            {'id': l.id, 'name': l.name, 'color': l.color, 'icon': l.icon}
            for l in labels
        ]})

    elif request.method == 'POST':
        try:
            data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
        except (json.JSONDecodeError, ValueError):
            data = request.POST

        label_id = data.get('id', '')
        name = data.get('name', '').strip()
        color = data.get('color', '#c9a84c').strip()
        icon = data.get('icon', 'tag').strip()

        if not name:
            return JsonResponse({'error': 'Name is required'}, status=400)

        if label_id:
            try:
                label = ArhivaLabel.objects.get(pk=label_id, company=company)
                label.name = name
                label.color = color
                label.icon = icon
                label.save()
                return JsonResponse({'ok': True, 'id': label.id, 'message': f'Labela "{name}" azurirana.'})
            except ArhivaLabel.DoesNotExist:
                return JsonResponse({'error': 'Label not found'}, status=404)
        else:
            label, created = ArhivaLabel.objects.get_or_create(
                company=company, name=name,
                defaults={'color': color, 'icon': icon}
            )
            if not created:
                label.color = color
                label.icon = icon
                label.save()
            return JsonResponse({'ok': True, 'id': label.id, 'created': created, 'message': f'Labela "{name}" kreirana.'})

    elif request.method == 'DELETE':
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        label_id = data.get('id', '')
        if not label_id:
            return JsonResponse({'error': 'ID required'}, status=400)

        try:
            label = ArhivaLabel.objects.get(pk=label_id, company=company)
            label.delete()
            return JsonResponse({'ok': True, 'message': 'Labela obrisana.'})
        except ArhivaLabel.DoesNotExist:
            return JsonResponse({'error': 'Label not found'}, status=404)

    return JsonResponse({'error': 'Method not allowed'}, status=405)


# ════════════════════════════════════════════════════════════
# KNJIGA URA / IRA
# ════════════════════════════════════════════════════════════

@login_required
def knjiga_ura_ira(request):
    """Knjiga ulaznih (URA) i izlaznih (IRA) racuna."""
    from documents.models import ArhivaEntry, ConversionRecord

    company = get_user_company(request)

    # Superadmin/staff moze birati firmu
    company_id = request.GET.get('company', '')
    all_companies = []
    if request.user.is_superuser or request.user.is_staff:
        from companies.models import Company
        from documents.models import ArhivaEntry as _AE
        from invoicing.models import Invoice as _Inv
        has_ira = set(_Inv.objects.values_list('company_id', flat=True).distinct())
        has_ura = set(_AE.objects.filter(source_type__in=['invoice_in','eracun','fiscal_cert']).values_list('company_id', flat=True).distinct())
        active_ids = has_ira | has_ura
        if active_ids:
            all_companies = list(Company.objects.filter(pk__in=active_ids).order_by('name'))
        else:
            all_companies = list(Company.objects.all().order_by('name'))
        if company_id:
            try:
                company = Company.objects.get(pk=company_id)
            except Company.DoesNotExist:
                pass

    if not company:
        return render(request, 'documents/knjiga_ura_ira.html', {'entries': [], 'book_type': 'URA', 'all_companies': all_companies})

    book_type = request.GET.get('type', 'URA').upper()
    if book_type not in ('URA', 'IRA'):
        book_type = 'URA'

    # Period filter
    year = int(request.GET.get('year', date.today().year))
    month = request.GET.get('month', '')
    quarter = request.GET.get('quarter', '')

    date_from = date(year, 1, 1)
    date_to = date(year, 12, 31)
    period_label = str(year)

    if month and month.isdigit():
        m = int(month)
        if 1 <= m <= 12:
            date_from = date(year, m, 1)
            if m == 12:
                date_to = date(year, 12, 31)
            else:
                date_to = date(year, m + 1, 1) - timedelta(days=1)
            period_label = '%02d/%d' % (m, year)
    elif quarter and quarter.isdigit():
        q = int(quarter)
        if 1 <= q <= 4:
            date_from = date(year, (q - 1) * 3 + 1, 1)
            end_month = q * 3
            if end_month == 12:
                date_to = date(year, 12, 31)
            else:
                date_to = date(year, end_month + 1, 1) - timedelta(days=1)
            period_label = 'Q%d/%d' % (q, year)

    # Partner filter
    partner_q = request.GET.get('partner', '').strip()

    entries = []
    totals = {
        'base_0': Decimal('0'), 'base_5': Decimal('0'), 'base_13': Decimal('0'), 'base_25': Decimal('0'),
        'vat_5': Decimal('0'), 'vat_13': Decimal('0'), 'vat_25': Decimal('0'),
        'total_with_vat': Decimal('0'), 'total_vat': Decimal('0'), 'total_base': Decimal('0'),
        'count': 0,
    }

    if book_type == 'URA':
        # Ulazni racuni iz arhive
        qs = ArhivaEntry.objects.filter(
            company=company,
            source_type__in=['invoice_in', 'eracun', 'fiscal_cert'],
            doc_date__gte=date_from,
            doc_date__lte=date_to,
        ).order_by('doc_date', 'pk')

        if partner_q:
            qs = qs.filter(partner_name__icontains=partner_q)

        # Dohvati extracted_data iz ConversionRecord
        conv_map = {}
        conv_ids = []
        for a in qs:
            if a.source_id and a.source_id.startswith('conversion:'):
                conv_ids.append(a.source_id.replace('conversion:', ''))
        if conv_ids:
            for cr in ConversionRecord.objects.filter(id__in=conv_ids):
                conv_map[str(cr.id)] = cr.extracted_data or {}

        for idx, a in enumerate(qs, 1):
            conv_id = a.source_id.replace('conversion:', '') if a.source_id and a.source_id.startswith('conversion:') else ''
            data = conv_map.get(conv_id, {})

            # Izracunaj PDV po stopama iz extracted_data
            total = Decimal(str(data.get('total', 0) or a.amount or 0))
            subtotal = Decimal(str(data.get('subtotal', 0) or 0))
            vat_amount = Decimal(str(data.get('vat_amount', 0) or 0))

            # Razvrstaj po stopama
            b0 = b5 = b13 = b25 = Decimal('0')
            v5 = v13 = v25 = Decimal('0')

            items = data.get('items', [])
            if items:
                for item in items:
                    rate = int(item.get('vat_rate', 0) or 0)
                    line = Decimal(str(item.get('line_total', 0) or 0))
                    item_vat = Decimal(str(item.get('unit_price', 0) or 0)) * Decimal(str(item.get('quantity', 0) or 0))
                    # line_total moze biti s ili bez PDV-a, koristimo kao osnovicu
                    base = line
                    vat = (base * Decimal(str(rate)) / Decimal('100')).quantize(Decimal('0.01'))

                    if rate == 0:
                        b0 += base
                    elif rate == 5:
                        b5 += base; v5 += vat
                    elif rate in (10, 13):
                        b13 += base; v13 += vat
                    else:
                        b25 += base; v25 += vat
            elif subtotal:
                # Nema stavki, koristimo ukupne iznose
                b25 = subtotal
                v25 = vat_amount

            if not subtotal and not items:
                b25 = total
                v25 = Decimal('0')

            total_with = total if total else (b0 + b5 + b13 + b25 + v5 + v13 + v25)

            seller = data.get('seller', {})
            entry = {
                'seq': idx,
                'doc_number': data.get('invoice_number', '') or a.doc_number,
                'doc_date': a.doc_date,
                'partner_name': seller.get('name', '') or a.partner_name,
                'partner_address': (seller.get('address', '') + ' ' + seller.get('city', '')).strip() if seller else '',
                'partner_oib': seller.get('oib', '') or '',
                'oib_type': 2 if (seller.get('country', 'HR') != 'HR' and seller.get('oib', '')) else 1,
                'base_0': b0, 'base_5': b5, 'base_13': b13, 'base_25': b25,
                'vat_5': v5, 'vat_13': v13, 'vat_25': v25,
                'total_vat': v5 + v13 + v25,
                'total_with_vat': total_with,
                'archive_number': a.archive_number if hasattr(a, 'archive_number') else '',
                'pk': a.pk,
                'currency': data.get('currency', a.currency),
            }
            entries.append(entry)

            totals['base_0'] += b0; totals['base_5'] += b5; totals['base_13'] += b13; totals['base_25'] += b25
            totals['vat_5'] += v5; totals['vat_13'] += v13; totals['vat_25'] += v25
            totals['total_vat'] += entry['total_vat']
            totals['total_with_vat'] += total_with
            totals['count'] += 1

    else:  # IRA
        try:
            from invoicing.models import Invoice
            qs = Invoice.objects.filter(
                company=company,
                date_issued__year__gte=date_from.year,
                date_issued__year__lte=date_to.year,
                status__in=['confirmed','fiscalized','sent','paid','unpaid','overdue','CONFIRMED','FISCALIZED','SENT','PAID','UNPAID','OVERDUE'],
            ).select_related('partner').order_by('date_issued')
            # Dodatni filter po mjesecu/kvartalu ako je odabran
            if month and month.isdigit():
                qs = qs.filter(date_issued__month=int(month))
            elif quarter and quarter.isdigit():
                q = int(quarter)
                qs = qs.filter(date_issued__month__gte=(q-1)*3+1, date_issued__month__lte=q*3)

            if partner_q:
                qs = qs.filter(client_name__icontains=partner_q)

            for idx, inv in enumerate(qs, 1):
                subtotal = inv.subtotal or Decimal('0')
                tax_pct = inv.tax_percent or Decimal('0')
                tax_amt = inv.tax_amount or Decimal('0')
                total = inv.total or Decimal('0')

                b0 = b5 = b13 = b25 = Decimal('0')
                v5 = v13 = v25 = Decimal('0')

                if tax_pct == 5:
                    b5 = subtotal; v5 = tax_amt
                elif tax_pct in (10, 13):
                    b13 = subtotal; v13 = tax_amt
                elif tax_pct == 25:
                    b25 = subtotal; v25 = tax_amt
                elif tax_pct == 0:
                    b0 = subtotal
                else:
                    b25 = subtotal; v25 = tax_amt

                entry = {
                    'seq': idx,
                    'doc_number': inv.number,
                    'doc_date': inv.date_issued.date() if hasattr(inv.date_issued, 'date') else inv.date_issued,
                    'partner_name': inv.client_name or (inv.partner.name if inv.partner else ''),
                    'partner_address': inv.client_address or '',
                    'partner_oib': inv.client_oib or '',
                    'oib_type': 1,
                    'base_0': b0, 'base_5': b5, 'base_13': b13, 'base_25': b25,
                    'vat_5': v5, 'vat_13': v13, 'vat_25': v25,
                    'total_vat': v5 + v13 + v25,
                    'total_with_vat': total,
                    'archive_number': '',
                    'pk': inv.pk,
                    'currency': 'EUR',
                    'jir': getattr(inv, 'jir', ''),
                    'zki': getattr(inv, 'zki', ''),
                }
                entries.append(entry)

                totals['base_0'] += b0; totals['base_5'] += b5; totals['base_13'] += b13; totals['base_25'] += b25
                totals['vat_5'] += v5; totals['vat_13'] += v13; totals['vat_25'] += v25
                totals['total_vat'] += entry['total_vat']
                totals['total_with_vat'] += total
                totals['count'] += 1
        except ImportError:
            pass

    totals['total_base'] = totals['base_0'] + totals['base_5'] + totals['base_13'] + totals['base_25']

    # Export?
    fmt = request.GET.get('format', '')
    if fmt == 'xml':
        return _knjiga_xml(request, book_type, entries, totals, company, date_from, date_to, period_label)
    if fmt == 'pdf':
        return _knjiga_pdf(request, book_type, entries, totals, company, date_from, date_to, period_label)

    return render(request, 'documents/knjiga_ura_ira.html', {
        'entries': entries,
        'totals': totals,
        'book_type': book_type,
        'year': year,
        'month': month,
        'quarter': quarter,
        'period_label': period_label,
        'partner_q': partner_q,
        'company': company,
        'years': list(range(date.today().year, 2022, -1)),
        'all_companies': all_companies,
        'selected_company_id': str(company.pk) if company else '',
    })


def _knjiga_xml(request, book_type, entries, totals, company, date_from, date_to, period_label):
    """Generira URA/IRA XML za ePorezna."""
    from xml.etree.ElementTree import Element, SubElement, tostring

    ns = 'http://e-porezna.porezna-uprava.hr/sheme/zahtjevi/%s/v1-0' % book_type
    root = Element('{%s}Obrazac%s' % (ns, book_type))
    root.set('xmlns', ns)
    root.set('verzijaSheme', '1.0')

    # Zaglavlje
    meta = SubElement(root, 'Metapodaci')
    SubElement(meta, 'Naslov').text = 'Knjiga %s racuna' % ('primljenih (ulaznih)' if book_type == 'URA' else 'izdanih (izlaznih)')
    SubElement(meta, 'Autor').text = 'LIMIT Connect ERP'
    SubElement(meta, 'Datum').text = date_from.isoformat()
    SubElement(meta, 'Format').text = 'text/xml'

    # Zaglavlje s obveznikovim podacima
    zag = SubElement(root, 'Zaglavlje')
    razd = SubElement(zag, 'Razdoblje')
    SubElement(razd, 'DatumOd').text = date_from.isoformat()
    SubElement(razd, 'DatumDo').text = date_to.isoformat()

    obv = SubElement(zag, 'Obveznik')
    SubElement(obv, 'OIB').text = company.oib or ''
    SubElement(obv, 'Naziv').text = company.name or ''
    SubElement(obv, 'Adresa').text = company.address or ''
    SubElement(obv, 'Mjesto').text = company.city or ''

    # Tijelo - racuni
    tijelo = SubElement(root, 'Tijelo')
    for e in entries:
        r = SubElement(tijelo, 'Racun')
        SubElement(r, 'R1').text = str(e['seq'])
        SubElement(r, 'R2').text = e['doc_number']
        SubElement(r, 'R3').text = e['doc_date'].isoformat() if e['doc_date'] else ''
        SubElement(r, 'R4').text = e['partner_name']
        SubElement(r, 'R5').text = e.get('partner_address', '')
        SubElement(r, 'R6').text = str(e.get('oib_type', 1))
        SubElement(r, 'R7').text = e['partner_oib']

        if book_type == 'URA':
            SubElement(r, 'R8').text = str(e['base_5'])
            SubElement(r, 'R9').text = str(e['base_13'])
            SubElement(r, 'R10').text = str(e['base_25'])
            SubElement(r, 'R11').text = str(e['total_with_vat'])
            SubElement(r, 'R12').text = str(e['total_vat'])
            SubElement(r, 'R13').text = str(e['vat_5'])
            SubElement(r, 'R14').text = '0'
            SubElement(r, 'R15').text = str(e['vat_13'])
            SubElement(r, 'R16').text = '0'
            SubElement(r, 'R17').text = str(e['vat_25'])
            SubElement(r, 'R18').text = '0'
            SubElement(r, 'R19').text = str(e['base_0'])
        else:
            SubElement(r, 'R6col').text = str(e['total_with_vat'])
            SubElement(r, 'R17').text = str(e['base_5'])
            SubElement(r, 'R18').text = str(e['vat_5'])
            SubElement(r, 'R19').text = str(e['base_13'])
            SubElement(r, 'R20').text = str(e['vat_13'])
            SubElement(r, 'R21').text = str(e['base_25'])
            SubElement(r, 'R22').text = str(e['vat_25'])

    xml_bytes = tostring(root, encoding='utf-8', xml_declaration=True)
    response = HttpResponse(xml_bytes, content_type='application/xml')
    response['Content-Disposition'] = 'attachment; filename="%s_%s.xml"' % (book_type, period_label.replace('/', '-'))
    return response


def _knjiga_pdf(request, book_type, entries, totals, company, date_from, date_to, period_label):
    """Generira URA/IRA PDF — landscape A4."""
    html = render_to_string('documents/knjiga_ura_ira_pdf.html', {
        'entries': entries, 'totals': totals, 'book_type': book_type,
        'company': company, 'date_from': date_from, 'date_to': date_to,
        'period_label': period_label,
    })
    try:
        import weasyprint
        pdf_bytes = weasyprint.HTML(string=html, base_url=settings.BASE_DIR).write_pdf()
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = 'inline; filename="%s_%s.pdf"' % (book_type, period_label.replace('/', '-'))
        return response
    except AttributeError as e:
        logger.error('URA/IRA PDF error: %s', e)
        return HttpResponse('PDF error: %s' % str(e)[:100], status=500)


# ════════════════════════════════════════════════════════════
# PDV OBRAZAC
# ════════════════════════════════════════════════════════════

@login_required
def pdv_obrazac(request):
    """PDV obrazac — Sekcija II (izlaz iz IRA) + Sekcija III (pretporez iz URA)."""
    from documents.models import ArhivaEntry, ConversionRecord

    company = get_user_company(request)

    # Staff moze birati firmu
    company_id = request.GET.get('company', '')
    all_companies = []
    if request.user.is_superuser or request.user.is_staff:
        from companies.models import Company
        from invoicing.models import Invoice as _Inv
        has_data = set(_Inv.objects.values_list('company_id', flat=True).distinct())
        has_ura = set(ArhivaEntry.objects.filter(source_type__in=['invoice_in','eracun','fiscal_cert']).values_list('company_id', flat=True).distinct())
        all_companies = list(Company.objects.filter(pk__in=has_data | has_ura).order_by('name'))
        if company_id:
            try:
                company = Company.objects.get(pk=company_id)
            except ObjectDoesNotExist as e:
                logger.debug("Handled exception in documents.views:%d: %s", 1815, e)  # BORG

    if not company:
        return render(request, 'documents/pdv_obrazac.html', {'all_companies': all_companies})

    # Period
    year = int(request.GET.get('year', date.today().year))
    month = request.GET.get('month', '')
    quarter = request.GET.get('quarter', '')

    date_from = date(year, 1, 1)
    date_to = date(year, 12, 31)
    period_label = str(year)
    period_type = 'yearly'

    if month and month.isdigit():
        m = int(month)
        if 1 <= m <= 12:
            date_from = date(year, m, 1)
            date_to = date(year, m + 1, 1) - timedelta(days=1) if m < 12 else date(year, 12, 31)
            period_label = '%02d/%d' % (m, year)
            period_type = 'monthly'
    elif quarter and quarter.isdigit():
        q = int(quarter)
        if 1 <= q <= 4:
            date_from = date(year, (q-1)*3+1, 1)
            end_m = q * 3
            date_to = date(year, end_m + 1, 1) - timedelta(days=1) if end_m < 12 else date(year, 12, 31)
            period_label = 'Q%d/%d' % (q, year)
            period_type = 'quarterly'

    D = Decimal

    # ── SEKCIJA II — Izlazni PDV (iz Invoice/IRA) ──
    try:
        from invoicing.models import Invoice
        ira_qs = Invoice.objects.filter(
            company=company,
            date_issued__year__gte=date_from.year,
            date_issued__year__lte=date_to.year,
            status__in=['confirmed','fiscalized','sent','paid','unpaid','overdue',
                        'CONFIRMED','FISCALIZED','SENT','PAID','UNPAID','OVERDUE'],
        )
        if period_type == 'monthly' and month:
            ira_qs = ira_qs.filter(date_issued__month=int(month))
        elif period_type == 'quarterly' and quarter:
            q = int(quarter)
            ira_qs = ira_qs.filter(date_issued__month__gte=(q-1)*3+1, date_issued__month__lte=q*3)

        sec2 = {'base_5': D('0'), 'vat_5': D('0'), 'base_13': D('0'), 'vat_13': D('0'),
                'base_25': D('0'), 'vat_25': D('0'), 'base_0': D('0'),
                'total_base': D('0'), 'total_vat': D('0'), 'total': D('0'), 'count': 0}

        for inv in ira_qs:
            sub = inv.subtotal or D('0')
            tax_pct = float(inv.tax_percent or 0)
            tax_amt = inv.tax_amount or D('0')
            total = inv.total or D('0')

            if tax_pct >= 23:
                sec2['base_25'] += sub; sec2['vat_25'] += tax_amt
            elif tax_pct >= 10:
                sec2['base_13'] += sub; sec2['vat_13'] += tax_amt
            elif tax_pct >= 3:
                sec2['base_5'] += sub; sec2['vat_5'] += tax_amt
            else:
                sec2['base_0'] += sub

            sec2['total_base'] += sub
            sec2['total_vat'] += tax_amt
            sec2['total'] += total
            sec2['count'] += 1
    except ImportError:
        sec2 = {'base_5': D('0'), 'vat_5': D('0'), 'base_13': D('0'), 'vat_13': D('0'),
                'base_25': D('0'), 'vat_25': D('0'), 'base_0': D('0'),
                'total_base': D('0'), 'total_vat': D('0'), 'total': D('0'), 'count': 0}

    # ── SEKCIJA III — Pretporez (iz ArhivaEntry/URA) ──
    ura_qs = ArhivaEntry.objects.filter(
        company=company,
        source_type__in=['invoice_in', 'eracun', 'fiscal_cert'],
        doc_date__gte=date_from,
        doc_date__lte=date_to,
    )

    sec3 = {'base_5': D('0'), 'vat_5': D('0'), 'base_13': D('0'), 'vat_13': D('0'),
            'base_25': D('0'), 'vat_25': D('0'), 'base_0': D('0'),
            'total_base': D('0'), 'total_vat': D('0'), 'total': D('0'), 'count': 0}

    # Try to get extracted_data for VAT breakdown
    conv_map = {}
    conv_ids = [a.source_id.replace('conversion:','') for a in ura_qs if a.source_id and a.source_id.startswith('conversion:')]
    if conv_ids:
        for cr in ConversionRecord.objects.filter(id__in=conv_ids):
            conv_map[str(cr.id)] = cr.extracted_data or {}

    for a in ura_qs:
        amount = a.amount or D('0')
        if amount <= 0:
            continue

        # Try extracted_data for precise VAT
        conv_id = a.source_id.replace('conversion:','') if a.source_id and a.source_id.startswith('conversion:') else ''
        data = conv_map.get(conv_id, {})
        vat_bd = data.get('vat_breakdown', {})

        if vat_bd:
            sec3['base_25'] += D(str(vat_bd.get('base_25', 0)))
            sec3['vat_25'] += D(str(vat_bd.get('vat_25', 0)))
            sec3['base_13'] += D(str(vat_bd.get('base_13', 0)))
            sec3['vat_13'] += D(str(vat_bd.get('vat_13', 0)))
            sec3['base_5'] += D(str(vat_bd.get('base_5', 0)))
            sec3['vat_5'] += D(str(vat_bd.get('vat_5', 0)))
            sec3['base_0'] += D(str(vat_bd.get('base_0', 0)))
        else:
            # Default: assume 25% for Croatian invoices
            base = (amount / D('1.25')).quantize(D('0.01'))
            vat = amount - base
            sec3['base_25'] += base
            sec3['vat_25'] += vat

        sec3['total'] += amount
        sec3['count'] += 1

    sec3['total_base'] = sec3['base_0'] + sec3['base_5'] + sec3['base_13'] + sec3['base_25']
    sec3['total_vat'] = sec3['vat_5'] + sec3['vat_13'] + sec3['vat_25']

    # ── OBRACUN — razlika izlaz - ulaz ──
    vat_payable = sec2['total_vat'] - sec3['total_vat']

    ctx = {
        'company': company,
        'year': year, 'month': month, 'quarter': quarter,
        'period_label': period_label, 'period_type': period_type,
        'date_from': date_from, 'date_to': date_to,
        'sec2': sec2, 'sec3': sec3,
        'vat_payable': vat_payable,
        'is_refund': vat_payable < 0,
        'all_companies': all_companies,
        'selected_company_id': str(company.pk),
        'years': list(range(date.today().year, 2022, -1)),
    }

    fmt = request.GET.get('format', '')
    if fmt == 'pdf':
        return _pdv_pdf(request, ctx)
    if fmt == 'xml':
        return _pdv_xml(request, ctx)

    return render(request, 'documents/pdv_obrazac.html', ctx)


def _pdv_pdf(request, ctx):
    """PDF PDV obrasca."""
    try:
        from xhtml2pdf import pisa
    except ImportError:
        return HttpResponse('xhtml2pdf not installed', status=500)
    html = render_to_string('documents/pdv_obrazac_pdf.html', ctx)
    result = io.BytesIO()
    pdf = pisa.pisaDocument(io.BytesIO(html.encode('utf-8')), result)
    if pdf.err:
        return HttpResponse('PDF error', status=500)
    response = HttpResponse(result.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="PDV_%s.pdf"' % ctx['period_label'].replace('/', '-')
    return response


def _pdv_xml(request, ctx):
    """XML PDV obrasca za ePorezna."""
    from xml.etree.ElementTree import Element, SubElement, tostring

    ns = 'http://e-porezna.porezna-uprava.hr/sheme/zahtjevi/PDV/v2-0'
    root = Element('{%s}ObrazacPDV' % ns)
    root.set('verzijaSheme', '2.0')

    meta = SubElement(root, 'Metapodaci')
    SubElement(meta, 'Naslov').text = 'PDV obrazac'
    SubElement(meta, 'Autor').text = 'LIMIT Connect ERP'

    zag = SubElement(root, 'Zaglavlje')
    razd = SubElement(zag, 'Razdoblje')
    SubElement(razd, 'DatumOd').text = ctx['date_from'].isoformat()
    SubElement(razd, 'DatumDo').text = ctx['date_to'].isoformat()
    obv = SubElement(zag, 'Obveznik')
    co = ctx['company']
    SubElement(obv, 'OIB').text = co.oib or ''
    SubElement(obv, 'Naziv').text = co.name or ''

    # Sekcija II - Izlaz
    s2 = SubElement(root, 'Isporuke')
    for tag, key in [('II_1_Osnovica5', 'base_5'), ('II_1_PDV5', 'vat_5'),
                     ('II_2_Osnovica13', 'base_13'), ('II_2_PDV13', 'vat_13'),
                     ('II_3_Osnovica25', 'base_25'), ('II_3_PDV25', 'vat_25'),
                     ('II_Neoporezivo', 'base_0'), ('II_UkupnoIsporuke', 'total')]:
        SubElement(s2, tag).text = str(ctx['sec2'][key])

    # Sekcija III - Pretporez
    s3 = SubElement(root, 'Pretporez')
    for tag, key in [('III_1_Osnovica5', 'base_5'), ('III_1_Pretporez5', 'vat_5'),
                     ('III_2_Osnovica13', 'base_13'), ('III_2_Pretporez13', 'vat_13'),
                     ('III_3_Osnovica25', 'base_25'), ('III_3_Pretporez25', 'vat_25'),
                     ('III_UkupnoPretporez', 'total_vat')]:
        SubElement(s3, tag).text = str(ctx['sec3'][key])

    # Obveza
    obr = SubElement(root, 'Obracun')
    SubElement(obr, 'PDV_Obveza').text = str(max(ctx['vat_payable'], 0))
    SubElement(obr, 'PDV_Povrat').text = str(abs(min(ctx['vat_payable'], 0)))

    xml_bytes = tostring(root, encoding='utf-8', xml_declaration=True)
    response = HttpResponse(xml_bytes, content_type='application/xml')
    response['Content-Disposition'] = 'attachment; filename="PDV_%s.xml"' % ctx['period_label'].replace('/', '-')
    return response


# ════════════════════════════════════════════════════════════
# REVIZIJA
# ════════════════════════════════════════════════════════════

@login_required
def revizija_page(request):
    """Forma za generiranje revizorskog paketa."""
    from companies.models import Company
    if request.user.is_superuser:
        companies = Company.objects.all().order_by('name')
    else:
        company = get_user_company(request)
        companies = [company] if company else []
    return render(request, 'documents/revizija.html', {'companies': companies})


@login_required
@require_POST
def revizija_export(request):
    """Generiraj ZIP s kompletnim revizorskim paketom."""
    from companies.models import Company
    from invoicing.models import Invoice

    company_id = request.POST.get('company_id', '')
    date_from = request.POST.get('date_from', '')
    date_to = request.POST.get('date_to', '')

    if not company_id or not date_from or not date_to:
        messages.error(request, _('Sva polja su obavezna.'))
        return redirect('documents:revizija')

    company = get_object_or_404(Company, pk=company_id)

    # Security
    if not request.user.is_superuser:
        user_co = get_user_company(request)
        if not user_co or str(user_co.pk) != str(company_id):
            messages.error(request, _('Nemate ovlasti za ovu radnju. Obratite se administratoru.'))
            return redirect('documents:revizija')

    # Query entries
    entries = ArhivaEntry.objects.filter(
        company=company,
        doc_date__gte=date_from,
        doc_date__lte=date_to,
    ).order_by('doc_date', 'archive_number')

    # Build ZIP in memory
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:

        # 1. CSV Index
        csv_buf = io.StringIO()
        writer = csv.writer(csv_buf, delimiter=';')
        writer.writerow(['Arhivski broj', 'Vrsta', 'Broj dokumenta', 'Partner',
                         'Iznos', 'Valuta', 'Datum', 'ZKI', 'JIR', 'PDF'])
        for e in entries:
            writer.writerow([
                e.archive_number, e.source_type, e.doc_number,
                e.partner_name, str(e.amount), e.currency,
                e.doc_date.strftime('%d.%m.%Y') if e.doc_date else '',
                e.zki or '', e.jir or '',
                'DA' if e.has_pdf else 'NE',
            ])
        zf.writestr('INDEX.csv', csv_buf.getvalue())

        # 2. URA (ulazni racuni)
        ura = entries.filter(source_type__in=['invoice_in', 'eracun', 'purchase'])
        if ura.exists():
            ura_csv = io.StringIO()
            w = csv.writer(ura_csv, delimiter=';')
            w.writerow(['R.br.', 'Datum', 'Broj racuna', 'Dobavljac', 'Osnovica', 'PDV 25%', 'PDV 13%', 'PDV 5%', 'Ukupno'])
            for i, e in enumerate(ura, 1):
                total = float(e.amount or 0)
                pdv25 = pdv13 = pdv5 = 0.0
                base = total
                try:
                    inv = Invoice.objects.get(pk=int(e.source_id))
                    for line in inv.lines.all():
                        rate = float(getattr(line, 'vat_rate', 25) or 25)
                        line_pdv = float(line.total or 0) - float(line.total or 0) / (1 + rate/100)
                        if rate >= 24:
                            pdv25 += line_pdv
                        elif rate >= 12:
                            pdv13 += line_pdv
                        else:
                            pdv5 += line_pdv
                    base = total - pdv25 - pdv13 - pdv5
                except ObjectDoesNotExist:
                    # Fallback: 25% standard
                    pdv25 = total - total / 1.25
                    base = total - pdv25
                w.writerow([i, e.doc_date, e.doc_number, e.partner_name,
                            f'{base:.2f}', f'{pdv25:.2f}', f'{pdv13:.2f}', f'{pdv5:.2f}', f'{total:.2f}'])
            zf.writestr('KNJIGA_URA.csv', ura_csv.getvalue())

        # 3. IRA (izlazni racuni)
        ira = entries.filter(source_type__in=['invoice_out'])
        if ira.exists():
            ira_csv = io.StringIO()
            w = csv.writer(ira_csv, delimiter=';')
            w.writerow(['R.br.', 'Datum', 'Broj racuna', 'Kupac', 'Osnovica', 'PDV 25%', 'PDV 13%', 'PDV 5%', 'Ukupno'])
            for i, e in enumerate(ira, 1):
                total = float(e.amount or 0)
                pdv25 = pdv13 = pdv5 = 0.0
                base = total
                try:
                    inv = Invoice.objects.get(pk=int(e.source_id))
                    for line in inv.lines.all():
                        rate = float(getattr(line, 'vat_rate', 25) or 25)
                        line_pdv = float(line.total or 0) - float(line.total or 0) / (1 + rate/100)
                        if rate >= 24:
                            pdv25 += line_pdv
                        elif rate >= 12:
                            pdv13 += line_pdv
                        else:
                            pdv5 += line_pdv
                    base = total - pdv25 - pdv13 - pdv5
                except ObjectDoesNotExist:
                    pdv25 = total - total / 1.25
                    base = total - pdv25
                w.writerow([i, e.doc_date, e.doc_number, e.partner_name,
                            f'{base:.2f}', f'{pdv25:.2f}', f'{pdv13:.2f}', f'{pdv5:.2f}', f'{total:.2f}'])
            zf.writestr('KNJIGA_IRA.csv', ira_csv.getvalue())

        # 4. PDV summary
        total_in = ura.aggregate(t=Sum('amount'))['t'] or 0
        total_out = ira.aggregate(t=Sum('amount'))['t'] or 0
        pdv_in = float(total_in) - float(total_in) / 1.25
        pdv_out = float(total_out) - float(total_out) / 1.25
        pdv_diff = pdv_out - pdv_in

        pdv_txt = f"""PDV PREGLED
Tvrtka: {company.name}
OIB: {company.oib}
Period: {date_from} — {date_to}

IZLAZNI RACUNI (IRA):
  Ukupno: {float(total_out):,.2f} EUR
  PDV (approx): {pdv_out:,.2f} EUR
  Broj racuna: {ira.count()}

ULAZNI RACUNI (URA):
  Ukupno: {float(total_in):,.2f} EUR
  PDV (approx): {pdv_in:,.2f} EUR
  Broj racuna: {ura.count()}

RAZLIKA PDV:
  Za uplatu: {pdv_diff:,.2f} EUR
  (Pozitivno = za uplatu, Negativno = pretplata)

Generirano: {datetime.now().strftime('%d.%m.%Y %H:%M')}
LIMIT Connect ERP
"""
        zf.writestr('PDV_PREGLED.txt', pdv_txt)

        # 5. PDF fakture
        pdf_count = 0
        for e in entries.filter(has_pdf=True, file_path__isnull=False).exclude(file_path=''):
            full_path = os.path.join(settings.MEDIA_ROOT, e.file_path)
            if os.path.isfile(full_path):
                arcname = f'PDF/{e.source_type}/{e.archive_number}.pdf'
                zf.write(full_path, arcname)
                pdf_count += 1

        # 6. Summary
        summary = f"""REVIZORSKI PAKET — {company.name}
Period: {date_from} do {date_to}
Generirano: {datetime.now().strftime('%d.%m.%Y %H:%M')}

Sadrzaj:
- INDEX.csv — {entries.count()} dokumenata
- KNJIGA_URA.csv — {ura.count()} ulaznih racuna
- KNJIGA_IRA.csv — {ira.count()} izlaznih racuna
- PDV_PREGLED.txt — PDV summary
- PDF/ — {pdf_count} PDF faktura

LIMIT Connect ERP — limit-connect.com
"""
        zf.writestr('README.txt', summary)

    buf.seek(0)
    filename = f'revizija_{company.oib or company.pk}_{date_from}_{date_to}.zip'

    zip_bytes = buf.read()

    # Email opcija
    send_email = request.POST.get('send_email', '')
    if send_email:
        try:
            from django.core.mail import EmailMessage as _EM
            email_to = request.POST.get('email_to', '').strip()
            if not email_to:
                email_to = getattr(company, 'email', '') or ''
            if email_to and '@' in email_to:
                em = _EM(
                    subject=f'Revizorski paket — {company.name} ({date_from} do {date_to})',
                    body=f'U prilogu je revizorski paket za {company.name}.\nPeriod: {date_from} — {date_to}\n\nLIMIT Connect ERP',
                    to=[email_to],
                )
                em.attach(filename, zip_bytes, 'application/zip')
                em.send()
                messages.success(request, f'ZIP poslan na {email_to}')
        except ImportError as mail_err:
            logger.warning('Revizija email: %s', mail_err)
            messages.warning(request, f'ZIP generiran, ali email slanje nije uspjelo: {mail_err}')

    response = HttpResponse(zip_bytes, content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ════════════════════════════════════════════════════════════
# GUIDE / DOCUMENTATION VIEWS
# ════════════════════════════════════════════════════════════

def arhiva_upute(request):
    """Public guide page for archive module — no login required."""
    return render(request, "documents/arhiva_upute.html")


def arhiva_guide_pdf(request):
    """Printable A4 guide for archive module."""
    return render(request, "documents/arhiva_guide_pdf.html")


@login_required
def verfahrensdokumentation(request):
    """Verfahrensdokumentation page — online signature, download, call buttons."""
    company = get_user_company(request)
    return render(request, 'documents/verfahrensdokumentation.html', {
        'company': company,
    })


@login_required
@require_POST
def verfahren_sign(request):
    """Accept digital signature for Verfahrensdokumentation."""
    import base64
    import hashlib
    import json as json_lib

    company = get_user_company(request)
    data = json_lib.loads(request.body)

    signature_b64 = data.get('signature', '')
    signer_name = data.get('signer_name', '')

    if not signature_b64 or not signer_name:
        return JsonResponse({'error': 'Potpis i ime su obavezni'}, status=400)

    # Audit trail — pravno neoboriv potpis
    # SHA-256 hash verzije dokumenta u trenutku potpisa
    doc_path = '/var/www/fina-connect/docs/Verfahrensdokumentation_LIMIT_Connect.md'
    try:
        with open(doc_path, 'rb') as df:
            doc_hash = hashlib.sha256(df.read()).hexdigest()
    except (FileNotFoundError, PermissionError, IOError):
        doc_hash = 'FILE_NOT_FOUND'

    client_ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() or request.META.get('REMOTE_ADDR', '')
    user_agent = request.META.get('HTTP_USER_AGENT', '')[:300]

    # Duplicate check
    existing = ArhivaEntry.objects.filter(
        company=company, source_type='verfahren_sign',
    ).first()
    if existing:
        return JsonResponse({
            'ok': True,
            'message': 'Dokument je vec potpisan (%s).' % existing.doc_date,
            'already_signed': True,
        })

    entry = ArhivaEntry(
        company=company,
        source_type='verfahren_sign',
        source_id='verfahren_%s_%s' % (request.user.pk, doc_hash[:8]),
        doc_number='VD-%s' % timezone.now().strftime('%Y%m%d'),
        partner_name=signer_name,
        amount=0,
        currency='EUR',
        doc_date=timezone.now().date(),
    )
    entry.save()

    # Store audit trail metadata
    try:
        from superadmin_ai.models import PendingAIAction
        PendingAIAction.objects.create(
            company=company,
            module='verfahren_sign',
            action_type='audit_signature',
            description='Verfahrensdokumentation potpisan: %s (%s)' % (signer_name, company.name),
            payload={
                'signer_name': signer_name,
                'client_ip': client_ip,
                'user_agent': user_agent,
                'document_hash': doc_hash,
                'timestamp': str(timezone.now()),
                'entry_id': entry.pk,
            },
            status='completed',
        )
    except (IntegrityError, DatabaseError):
        pass

    # Save signature image
    sig_dir = os.path.join('/var/www/fina-connect/media/signatures')
    os.makedirs(sig_dir, exist_ok=True)
    sig_path = os.path.join(sig_dir, 'verfahren_%s_%s.png' % (company.oib, timezone.now().strftime('%Y%m%d_%H%M%S')))
    with open(sig_path, 'wb') as f:
        f.write(base64.b64decode(signature_b64.split(',')[1] if ',' in signature_b64 else signature_b64))

    # Save immutable PDF snapshot of document version
    try:
        import markdown as md_lib
        from weasyprint import HTML as WeasyprintHTML
        doc_md = '/var/www/fina-connect/docs/Verfahrensdokumentation_LIMIT_Connect.md'
        pdf_path = sig_path.replace('.png', '_document.pdf')
        html_content = '<html><body style="font-family:Arial;max-width:800px;margin:auto;padding:20px">'
        with open(doc_md) as md_f:
            html_content += md_lib.markdown(md_f.read(), extensions=['tables'])
        html_content += '<hr><p>Unterzeichnet von: %s<br>Datum: %s<br>IP: %s<br>Dokument-Hash: %s</p>' % (
            signer_name, str(timezone.now()), client_ip, doc_hash)
        html_content += '</body></html>'
        WeasyprintHTML(string=html_content).write_pdf(pdf_path)
    except (FileNotFoundError, PermissionError, IOError) as e:
        logger.warning('Immutable PDF failed: %s', e)

    return JsonResponse({
        'ok': True,
        'message': 'Verfahrensdokumentation erfolgreich unterzeichnet.',
        'entry_id': entry.pk,
    })
