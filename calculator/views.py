import io
import logging

from django.contrib import messages
from django.utils.translation import gettext as _
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import get_template

from .models import Calculation, CalculationItem, Normative

logger = logging.getLogger(__name__)


def public_calculator(request):
    """Public-facing tab calculator – no login required."""
    return render(request, 'calculator/public_calculator.html', {})


@login_required
def calculator_list(request):
    calculations = Calculation.objects.select_related('project').all().order_by('-created_at')
    return render(request, 'calculator/list.html', {'calculations': calculations})


@login_required
def add_item(request, calc_id):
    calculation = get_object_or_404(Calculation, id=calc_id)
    normatives = Normative.objects.all()
    if request.method == "POST":
        normative_id = request.POST.get('normative')
        quantity = float(request.POST.get('quantity', 1))
        normative = get_object_or_404(Normative, id=normative_id)
        CalculationItem.objects.create(
            calculation=calculation, normative=normative, description=normative.name,
            quantity=quantity, unit_price_material=normative.base_material_cost,
            labor_hours_per_unit=normative.estimated_hours_per_unit, labor_rate_applied=50.00
        )
        messages.success(request, f"Dodano: {normative.name}")
        return redirect('calculator:estimate_list')
    return render(request, 'calculator/add_item.html', {'calculation': calculation, 'normatives': normatives})


@login_required
def export_calculation_pdf(request, pk):
    calculation = get_object_or_404(Calculation, pk=pk)
    totals = calculation.calculate_totals()
    items = calculation.items.all()
    context = {
        'calculation': calculation,
        'items': items,
        'totals': totals,
        'company_name': 'Viskovic Group',
    }
    try:
        from xhtml2pdf import pisa
        template = get_template('calculator/calculation_pdf.html')
        html = template.render(context)
        result = io.BytesIO()
        pdf = pisa.pisaDocument(io.BytesIO(html.encode("UTF-8")), result)
        if not pdf.err:
            response = HttpResponse(result.getvalue(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="Ponuda_{pk}.pdf"'
            return response
    except Exception:
        logger.exception('PDF generation failed')
    return HttpResponse("Greska prilikom generiranja PDF-a", status=400)


def salary_calculator(request):
    """Salary calculator (Gehaltsrechner) DE + HR, no login required."""
    return render(request, 'calculator/salary_calculator.html', {})


def bathroom_public(request):
    """Public bathroom renovation calculator, no login required."""
    return render(request, 'calculator/bathroom_public.html', {})

def bathroom_anfrage(request):
    """
    POST endpoint from public bathroom calculator.
    Creates ProjectLead + saves PDF to Document archive.
    Returns hvala page with lead reference number.
    """
    if request.method != 'POST':
        from django.shortcuts import redirect
        return redirect('calculator:bathroom_public')

    import io, uuid
    from django.utils import timezone
    from companies.models import Company
    from burza.models import ProjectLead
    from documents.models import Document

    # ── Contact data from form ─────────────────────────────────────────────
    name    = request.POST.get('contact_name', '').strip()
    phone   = request.POST.get('contact_phone', '').strip()
    email   = request.POST.get('contact_email', '').strip()
    loc     = request.POST.get('location', '').strip()
    budget_from = request.POST.get('budget_from', '').strip()
    budget_to   = request.POST.get('budget_to', '').strip()
    services    = request.POST.get('services', '').strip()
    quality     = request.POST.get('quality', 'premium').strip()
    sqm         = request.POST.get('sqm', '').strip()

    # ── Build description ──────────────────────────────────────────────────
    desc_lines = []
    if budget_from and budget_to:
        desc_lines.append(f"Geschätzte Kosten: {budget_from} – {budget_to} EUR")
    desc_lines.append(f"Qualität: {quality}")
    if sqm:
        desc_lines.append(f"Fläche: {sqm} m²")
    if loc:
        desc_lines.append(f"Adresse: {loc}")
    if services:
        desc_lines.append("\nLeistungen:")
        for s in services.split('|'):
            s = s.strip()
            if s:
                desc_lines.append(f"- {s}")
    description = "\n".join(desc_lines)

    # ── Viskovic Bau company ───────────────────────────────────────────────
    try:
        company = Company.objects.get(name__icontains='Viskovic bau')
    except Exception:
        company = None

    # ── Reference number ───────────────────────────────────────────────────
    ref = "BAD-" + timezone.now().strftime("%Y%m%d") + "-" + uuid.uuid4().hex[:4].upper()

    # ── Create Lead ────────────────────────────────────────────────────────
    lead = ProjectLead(
        title       = f"Badsanierung {sqm}m² ({quality}) – {name or 'Anfrage'}",
        description = description,
        category    = 'kupaonica',
        location    = loc,
        contact_name  = name,
        contact_phone = phone,
        contact_email = email,
        status      = 'NOVI_UPIT',
        is_public   = False,
        company     = company,
        internal_notes = f"Ref: {ref} | Via: Badsanierung-Kalkulator",
    )
    if budget_from:
        try: lead.budget_from = float(budget_from.replace('.','').replace(',','.'))
        except Exception: pass
    if budget_to:
        try: lead.budget_to = float(budget_to.replace('.','').replace(',','.'))
        except Exception: pass
    lead.save()

    # ── Generate PDF and save to Document archive ──────────────────────────
    pdf_saved = False
    try:
        from xhtml2pdf import pisa
        from django.template.loader import render_to_string
        from django.core.files.base import ContentFile

        pdf_context = {
            'lead': lead,
            'ref': ref,
            'name': name,
            'phone': phone,
            'email': email,
            'location': loc,
            'budget_from': budget_from,
            'budget_to': budget_to,
            'quality': quality,
            'sqm': sqm,
            'services_list': [s.strip() for s in services.split('|') if s.strip()],
            'date': timezone.now(),
        }
        html_str = render_to_string('calculator/bathroom_anfrage_pdf.html', pdf_context)
        buf = io.BytesIO()
        pisa.pisaDocument(io.BytesIO(html_str.encode('UTF-8')), buf)
        pdf_bytes = buf.getvalue()

        if pdf_bytes and len(pdf_bytes) > 100:
            doc = Document(
                company    = company,
                doc_type   = 'offer',
                doc_number = ref,
                date_issued = timezone.now().date(),
                total_amount = float(budget_to.replace('.','').replace(',','.')) if budget_to else 0,
            )
            doc.file.save(f"Angebot_{ref}.pdf", ContentFile(pdf_bytes), save=True)
            pdf_saved = True
            lead.internal_notes += f" | PDF: {doc.file.name}"
            lead.save()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"PDF archive failed: {e}")

    return render(request, 'calculator/bathroom_hvala.html', {
        'ref': ref,
        'name': name,
        'lead_pk': lead.pk,
        'pdf_saved': pdf_saved,
        'budget_from': budget_from,
        'budget_to': budget_to,
    })



@login_required
def bathroom_internal(request):
    """Internal bathroom renovation calculator, login required."""
    return redirect("/calculator/?preset=bad")


# ─── BOM / Sastavnice ─────────────────────────────────────────────────────────

@login_required
def bom_list(request):
    from core.tenant import get_current_company

    from .models import BOM
    company = get_current_company()
    if not company:
        try:
            company = request.user.profile.company
        except Exception:
            pass

    qs = BOM.objects.filter(company=company).select_related('article') if company else BOM.objects.none()
    q = request.GET.get('q', '').strip()
    if q:
        from django.db.models import Q
        qs = qs.filter(Q(name__icontains=q) | Q(article__name__icontains=q))
    return render(request, 'calculator/bom_list.html', {'boms': qs, 'q': q})


@login_required
def bom_create(request):
    from core.tenant import get_current_company

    from .models import BOM
    company = get_current_company()
    if not company:
        try:
            company = request.user.profile.company
        except Exception:
            pass

    if request.method == 'POST':
        from django.db import transaction
        with transaction.atomic():
            bom = BOM(company=company)
            article_id = request.POST.get('article')
            if article_id:
                bom.article_id = int(article_id)
            bom.name = request.POST.get('name', '')
            try:
                bom.yield_quantity = float(request.POST.get('yield_quantity', '1'))
            except (ValueError, TypeError):
                bom.yield_quantity = 1
            bom.is_active = 'is_active' in request.POST
            bom.notes = request.POST.get('notes', '')
            bom.save()

            # Items
            _save_bom_items(bom, request.POST)

        messages.success(request, f'BOM "{bom}" kreiran.')
        return redirect('calculator:bom_detail', pk=bom.pk)

    from inventory.models import InventoryItem
    articles = InventoryItem.objects.filter(company=company, is_active=True).order_by('name') if company else []
    return render(request, 'calculator/bom_form.html', {
        'bom': None, 'articles': articles, 'materials': articles,
    })


@login_required
def bom_detail(request, pk):
    from core.tenant import get_current_company

    from .models import BOM
    company = get_current_company()
    if not company:
        try:
            company = request.user.profile.company
        except Exception:
            pass
    bom = get_object_or_404(BOM, pk=pk, company=company)
    return render(request, 'calculator/bom_detail.html', {
        'bom': bom,
        'items': bom.items.select_related('material').all(),
        'total_cost': bom.total_material_cost(),
    })


@login_required
def bom_edit(request, pk):
    from core.tenant import get_current_company

    from .models import BOM
    company = get_current_company()
    if not company:
        try:
            company = request.user.profile.company
        except Exception:
            pass
    bom = get_object_or_404(BOM, pk=pk, company=company)

    if request.method == 'POST':
        from django.db import transaction
        with transaction.atomic():
            article_id = request.POST.get('article')
            if article_id:
                bom.article_id = int(article_id)
            bom.name = request.POST.get('name', '')
            try:
                bom.yield_quantity = float(request.POST.get('yield_quantity', '1'))
            except (ValueError, TypeError):
                bom.yield_quantity = 1
            bom.is_active = 'is_active' in request.POST
            bom.notes = request.POST.get('notes', '')
            bom.save()

            bom.items.all().delete()
            _save_bom_items(bom, request.POST)

        messages.success(request, f'BOM "{bom}" ažuriran.')
        return redirect('calculator:bom_detail', pk=pk)

    from inventory.models import InventoryItem
    articles = InventoryItem.objects.filter(company=company, is_active=True).order_by('name') if company else []
    return render(request, 'calculator/bom_form.html', {
        'bom': bom,
        'articles': articles,
        'materials': articles,
        'items': bom.items.select_related('material').all(),
    })


def _save_bom_items(bom, post):
    from .models import BOMItem
    mat_ids   = post.getlist('mat_id[]')
    quantities = post.getlist('mat_qty[]')
    units      = post.getlist('mat_unit[]')
    wastes     = post.getlist('mat_waste[]')
    for i, mid in enumerate(mat_ids):
        if not mid:
            continue
        try:
            qty   = float(quantities[i]) if i < len(quantities) else 1
            unit  = units[i]             if i < len(units)      else 'kom'
            waste = float(wastes[i])     if i < len(wastes)     else 0
        except (ValueError, TypeError):
            continue
        BOMItem.objects.create(
            bom=bom,
            material_id=int(mid),
            quantity=qty,
            unit=unit,
            waste_percent=waste,
        )


# ─── Synesis Export ────────────────────────────────────────────────────────────

@login_required
def export_to_synesis(request, pk):
    """
    POST /calculator/<pk>/synesis-export/
    Kreira SynesisExportQueue zapis s kalkulacijom.
    Windows sync skripta pokupi i upiše u Synesis ITEMS tablicu.
    """
    from django.http import JsonResponse
    from core.company_utils import get_user_company
    from synesis.models import SynesisExportQueue, SynesisConfig

    if request.method != 'POST':
        from django.http import HttpResponseNotAllowed
        return HttpResponseNotAllowed(['POST'])

    company = get_user_company(request)
    if not company:
        messages.error(request, _('Niste povezani s tvrtkom. Odaberite tvrtku iz izbornika.'))
        return redirect('calculator:estimate_list')

    calculation = get_object_or_404(Calculation, pk=pk)
    totals = calculation.calculate_totals()

    # Provjeri postoji li Synesis konfiguracija za ovu tvrtku
    has_synesis = SynesisConfig.objects.filter(company=company, is_active=True).exists()
    if not has_synesis:
        messages.error(request, "Synesis nije konfiguriran za ovu tvrtku. Idite na Integracije → Synesis.")
        return redirect('calculator:estimate_list')

    # Građi payload koji mapira na Synesis ITEMS tablicu
    project = calculation.project
    items_payload = []
    for item in calculation.items.select_related('normative').all():
        mat = float(item.unit_price_material) * item.quantity
        lab = item.labor_hours_per_unit * float(item.labor_rate_applied) * item.quantity
        items_payload.append({
            'description': item.description,
            'quantity': item.quantity,
            'unit_price_material': float(item.unit_price_material),
            'labor_hours': item.labor_hours_per_unit,
            'labor_rate': float(item.labor_rate_applied),
            'line_total': round(mat + lab, 2),
        })

    payload = {
        # ERP podaci — koriste se za Synesis OFFERS INSERT
        'calculation_id': calculation.pk,
        'project_name': project.name,
        'client_name': str(project.client) if project.client else '',
        'margin_percent': calculation.margin_percentage,
        'vat_percent': calculation.vat_percentage,
        'net_cost': float(totals['net_cost']),
        'offer_total_net': float(totals['offer_total_net']),
        'offer_total_vat': float(totals['offer_total_vat']),
        'items': items_payload,
    }

    # Pronađi synesis_id ako artikl već postoji u queuu (update) ili insert
    existing = SynesisExportQueue.objects.filter(
        company=company,
        export_type='calculation',
        erp_object_id=str(calculation.pk),
        is_confirmed=False,
    ).first()

    if existing:
        existing.payload = payload
        existing.is_exported = False
        existing.exported_at = None
        existing.description = f"Kalkulacija #{calculation.pk}: {project.name} — {totals['offer_total_vat']} EUR"
        existing.save()
        queue_entry = existing
        action_msg = "ažurirana"
    else:
        queue_entry = SynesisExportQueue.objects.create(
            company=company,
            export_type='calculation',
            action='insert',
            erp_object_id=str(calculation.pk),
            payload=payload,
            description=f"Kalkulacija #{calculation.pk}: {project.name} — {totals['offer_total_vat']} EUR",
            created_by=request.user,
        )
        action_msg = "dodana u red"

    messages.success(
        request,
        f"✅ Kalkulacija #{calculation.pk} ({totals['offer_total_vat']} EUR s PDV-om) {action_msg} za Synesis export. "
        f"Sljedeći put kada se sync skripta pokrene, bit će upisana u Synesis."
    )

    # AJAX poziv → JSON; browser redirect → back
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'ok': True,
            'queue_id': queue_entry.pk,
            'action': action_msg,
            'offer_total_vat': float(totals['offer_total_vat']),
        })

    return redirect('calculator:estimate_list')


@login_required
def export_pkv_to_synesis(request, pk):
    """
    POST /calculator/<pk>/pkv-export/
    Kreira SynesisExportQueue zapis tipa 'pkv'.
    Windows sync skripta upisuje u Synesis RETAIL tablicu kao PKV primku.

    PKV primka = kalkulacija marže:
      - ITEM_TOTALPURCHASEVALUE = net_cost (cijena koštanja: materijal + rad)
      - RATIO                  = koeficijent (offer_total_net / net_cost)
      - RET_TOTALOUTPUT        = offer_total_net (prodajna cijena bez PDV-a)
      - VAT_INVOICEAMMOUNT     = offer_total_vat (s PDV-om)
      - DESCRIPTION            = naziv projekta
    """
    from django.http import JsonResponse
    from core.company_utils import get_user_company
    from synesis.models import SynesisExportQueue, SynesisConfig

    if request.method != 'POST':
        from django.http import HttpResponseNotAllowed
        return HttpResponseNotAllowed(['POST'])

    company = get_user_company(request)
    if not company:
        messages.error(request, _('Niste povezani s tvrtkom. Odaberite tvrtku iz izbornika.'))
        return redirect('calculator:estimate_list')

    calculation = get_object_or_404(Calculation, pk=pk)
    totals = calculation.calculate_totals()

    has_synesis = SynesisConfig.objects.filter(company=company, is_active=True).exists()
    if not has_synesis:
        messages.error(request, "Synesis nije konfiguriran. Idite na Integracije → Synesis.")
        return redirect('calculator:estimate_list')

    project = calculation.project
    net_cost        = float(totals['net_cost'])           # cijena koštanja (nabavna)
    offer_net       = float(totals['offer_total_net'])    # prodajna bez PDV-a
    offer_vat       = float(totals['offer_total_vat'])    # prodajna s PDV-om
    vat_amount      = round(offer_vat - offer_net, 2)
    vat_pct         = int(calculation.vat_percentage)
    margin_pct      = float(calculation.margin_percentage)
    ratio           = round(offer_net / net_cost, 6) if net_cost > 0 else 1.0
    client_name     = (str(project.client) if project.client else '')[:50]
    description     = f"ERP: {project.name}"[:30]
    remark          = f"Kalk #{calculation.pk} | m={margin_pct}%"[:50]

    vat_base25 = offer_net if vat_pct == 25 else 0.0
    vat_25     = vat_amount if vat_pct == 25 else 0.0
    vat_base10 = offer_net if vat_pct == 10 else 0.0
    vat_10     = vat_amount if vat_pct == 10 else 0.0
    vat_base5  = offer_net if vat_pct == 5  else 0.0
    vat_5      = vat_amount if vat_pct == 5  else 0.0

    # MPC = maloprodajna cijena = offer_vat (s PDV-om = prodajna s PDV-om)
    # Synesis PKV: ITEM_TOTALPURCHASEVALUE=nabavna, RET_TOTALINPUT=MPC vrijednost
    # TRANID='PKVINPUT' je fiksna Synesis oznaka tipa dokumenta
    # TRANCODE se generira sekvencijalno (MAX+1) - ne upisujemo fiksni broj
    mpc_total = offer_vat  # maloprodajna vrijednost s PDV-om

    payload = {
        # --- Identifikacija ---
        'calculation_id':   calculation.pk,
        'project_name':     project.name,
        'client_name':      client_name,

        # --- RETAIL zaglavlje (točno prema PKVINPUT zapisu iz baze) ---
        'PRIORITY':         2,
        'RETAIL_ID':        1,           # jedino maloprodajno mjesto
        'FOND':             1,
        'TRANDATE':         None,        # sync skripta upisuje datetime.now()
        'DESCRIPTION':      description,
        'VENDOR_NAME':      client_name,
        'DOCUMENT_NUMBER':  f"ERP-{calculation.pk}",
        'DOCUMENT_DATE':    None,        # sync skripta upisuje datetime.now()
        'REMARK':           remark,
        'CONID':            '1',
        'SE_CONTROLLER':    '1',

        # --- Financijski podaci (točno kao PKVINPUT) ---
        'ITEM_TOTALPURCHASEVALUE': net_cost,   # nabavna vrijednost (cijena koštanja)
        'RET_TOTALINPUT':          mpc_total,  # MPC vrijednost (prodajna s PDV-om)

        # --- SE_ postavke (prema PKVINPUT uzorku) ---
        'SE_PKVPRINTTYPE':        1,
        'SE_RETPRINTDISCOUNT':    1,
        'SE_RETPRINTPROFITRATE':  1,
        'SE_RETPRINTPROFIT':      1,
        'SE_JUMPMARGIN':          1,
        'SE_RETAILPRICE':         1,

        # --- Kontni plan (standardni Synesis kontovi iz uzorka) ---
        'SE_RETAILACCOUNT':       '66001',
        'SE_RETAILVATACCOUNT':    '664',
        'SE_RETAILVAT10ACCOUNT':  '664',
        'SE_RETAILVAT5ACCOUNT':   '664',
        'SE_RETAILPROFITACCOUNT': '668',
        'SE_RETNONINVOICED':      '6500',
        'SE_PACKRETACCOUNT':      '6500',

        # --- Duplikat zaštita (ERP interni ID, različit od Synesis TRANID) ---
        'erp_tranid': f"ERPPKV-{calculation.pk}",
    }

    # Update-or-create logika
    existing = SynesisExportQueue.objects.filter(
        company=company,
        export_type='pkv',
        erp_object_id=str(calculation.pk),
        is_confirmed=False,
    ).first()

    if existing:
        existing.payload      = payload
        existing.is_exported  = False
        existing.exported_at  = None
        existing.description  = f"PKV #{calculation.pk}: {project.name} — nab={net_cost:.2f} / prod={offer_net:.2f} EUR"
        existing.save()
        queue_entry = existing
        action_msg  = "ažurirana"
    else:
        queue_entry = SynesisExportQueue.objects.create(
            company=company,
            export_type='pkv',
            action='insert',
            erp_object_id=str(calculation.pk),
            payload=payload,
            description=f"PKV #{calculation.pk}: {project.name} — nab={net_cost:.2f} / prod={offer_net:.2f} EUR",
            created_by=request.user,
        )
        action_msg = "dodana u red"

    messages.success(
        request,
        f"📦 PKV primka za kalkulaciju #{calculation.pk} ({net_cost:.2f} → {offer_net:.2f} EUR, "
        f"marža {margin_pct}%) {action_msg} za Synesis export."
    )

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'ok': True,
            'queue_id': queue_entry.pk,
            'action': action_msg,
            'net_cost': net_cost,
            'offer_net': offer_net,
            'ratio': ratio,
        })

    return redirect('calculator:estimate_list')


@login_required
def aufnahme_view(request):
    """Terenska forma — obdukcijski nalaz za majstora."""
    return render(request, 'calculator/aufnahme.html', {})


@login_required
def aufnahme_save(request):
    """Sprema obdukcijski nalaz kao ProjectLead + PDF u arhivu."""
    if request.method != 'POST':
        from django.http import JsonResponse
        return JsonResponse({'ok': False, 'error': 'POST only'})

    import io, uuid
    from django.utils import timezone
    from django.http import JsonResponse
    from companies.models import Company
    from burza.models import ProjectLead
    from documents.models import Document
    from django.core.files.base import ContentFile

    ref  = 'AUF-' + timezone.now().strftime('%Y%m%d') + '-' + uuid.uuid4().hex[:4].upper()
    name = request.POST.get('contact_name', '').strip()
    phone = request.POST.get('contact_phone', '').strip()
    loc  = request.POST.get('location', '').strip()
    cat  = request.POST.get('category', 'sonstiges')
    datum = request.POST.get('datum', '')
    notes = request.POST.get('notes', '').strip()
    next_step = request.POST.get('next_step', '').strip()
    leistungen = request.POST.get('leistungen', '')

    # Build rooms summary
    rooms_txt = []
    i = 1
    while request.POST.get(f'room_name_{i}'):
        rn = request.POST.get(f'room_name_{i}', '')
        rl = request.POST.get(f'room_l_{i}', '')
        rb = request.POST.get(f'room_b_{i}', '')
        rh = request.POST.get(f'room_h_{i}', '')
        parts = [p for p in [rl, rb, rh] if p]
        if rn or parts:
            rooms_txt.append(f"{rn}: L={rl}m × B={rb}m × H={rh}m")
        i += 1

    desc = f"Aufnahme: {datum}\nAdresse: {loc}\n"
    if rooms_txt:
        desc += "\nMaße:\n" + "\n".join(f"  {r}" for r in rooms_txt)
    if leistungen:
        desc += "\n\nVereinbarte Leistungen:\n" + "\n".join(f"  - {l}" for l in leistungen.split('|') if l.strip())
    if notes:
        desc += f"\n\nNotizen:\n{notes}"
    if next_step:
        desc += f"\n\nNächster Schritt: {next_step}"

    try:
        company = Company.objects.filter(name__icontains='Viskovic bau').first()
    except Exception:
        company = None

    CAT_MAP = {'bad':'kupaonica','wohnung':'renovacija','kueche':'ostalo',
               'buero':'ostalo','neubau':'gradnja','sonstiges':'ostalo'}

    lead = ProjectLead(
        title=f"Aufnahme: {name or loc or ref}",
        description=desc,
        category=CAT_MAP.get(cat, 'ostalo'),
        location=loc,
        contact_name=name,
        contact_phone=phone,
        status='INTERNA_PROCJENA',
        is_public=False,
        company=company,
        internal_notes=f"Ref: {ref} | Via: Terenska forma",
    )
    lead.save()

    # Save photos
    photo_count = int(request.POST.get('photo_count', 0))
    photo_urls = []
    for pi in range(min(photo_count, 10)):
        b64data = request.POST.get(f'photo_{pi}', '')
        if b64data and ',' in b64data:
            try:
                import base64 as b64mod
                _, data = b64data.split(',', 1)
                img_bytes = b64mod.b64decode(data)
                from django.core.files.base import ContentFile
                from burza.models import ProjectPhoto
                photo = ProjectPhoto(project_lead=lead, user=request.user)
                photo.photo.save(f"{ref}_photo_{pi}.jpg", ContentFile(img_bytes), save=True)
                photo_urls.append(photo.photo.url)
            except Exception:
                pass

    # Generate PDF
    pdf_url = None
    try:
        from xhtml2pdf import pisa
        from django.template.loader import render_to_string
        ctx = {
            'ref': ref, 'name': name, 'phone': phone, 'location': loc,
            'datum': datum, 'notes': notes, 'next_step': next_step,
            'leistungen_list': [l.strip() for l in leistungen.split('|') if l.strip()],
            'rooms': rooms_txt,
            'category': cat,
        }
        html_str = render_to_string('calculator/aufnahme_pdf.html', ctx)
        buf = io.BytesIO()
        pisa.pisaDocument(io.BytesIO(html_str.encode('UTF-8')), buf)
        pdf_bytes = buf.getvalue()
        if pdf_bytes and len(pdf_bytes) > 200:
            doc = Document(
                company=company, doc_type='OTHER', doc_number=ref,
                date_issued=timezone.now().date(), total_amount=0,
            )
            doc.file.save(f"Aufnahme_{ref}.pdf", ContentFile(pdf_bytes), save=True)
            pdf_url = doc.file.url
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Aufnahme PDF failed: {e}")

    return JsonResponse({
        'ok': True, 'ref': ref,
        'name': name or 'Aufnahme',
        'date': datum,
        'pdf_url': pdf_url or '',
        'lead_pk': lead.pk,
    })
