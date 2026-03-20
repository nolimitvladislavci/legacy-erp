"""PDV-S views."""
from django.db import models
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.utils import timezone

from core.company_utils import get_user_company


@login_required
def pdv_s_report(request):
    """PDV-S obrazac — generiranje."""
    company = get_user_company(request)

    if request.method == 'POST':
        year = int(request.POST.get('year', timezone.now().year))
        month = int(request.POST.get('month', timezone.now().month))

        from invoicing.models import Invoice
        from pdv_s.service import generate_pdv_s, format_pdv_s_text

        # Ulazni racuni (purchases) za period
        # Ulazni: URA doctype + eRacun incoming
        invoices_in = Invoice.objects.filter(
            company=company,
            date_issued__year=year,
            date_issued__month=month,
        ).filter(
            models.Q(doctype='URA') | models.Q(source='eracun')
        ).exclude(status__in=['DRAFT', 'CANCELLED', 'STORNO'])

        # Izlazni racuni (sales) za period
        # Izlazni: R, PO, P, A, FA doctype (ne URA, ne S)
        invoices_out = Invoice.objects.filter(
            company=company,
            date_issued__year=year,
            date_issued__month=month,
            doctype__in=['R', 'PO', 'P', 'A', 'FA', 'RN'],
        ).exclude(status__in=['DRAFT', 'CANCELLED', 'STORNO'])

        pdv_data = generate_pdv_s(company, year, month, invoices_in, invoices_out)
        text_summary = format_pdv_s_text(pdv_data)

        # Save to model
        from pdv_s.models import PDVSReport
        report, created = PDVSReport.objects.update_or_create(
            company=company, year=year, month=month,
            defaults={
                'i1_base': pdv_data['i1_base'], 'i1_tax': pdv_data['i1_tax'],
                'i2_base': pdv_data['i2_base'], 'i2_tax': pdv_data['i2_tax'],
                'i3_base': pdv_data['i3_base'], 'i3_tax': pdv_data['i3_tax'],
                'ii1_base': pdv_data['ii1_base'], 'ii1_tax': pdv_data['ii1_tax'],
                'ii2_base': pdv_data['ii2_base'], 'ii2_tax': pdv_data['ii2_tax'],
                'ii3_base': pdv_data['ii3_base'], 'ii3_tax': pdv_data['ii3_tax'],
                'ii4_base': pdv_data['ii4_base'],
                'ii5_base': pdv_data['ii5_base'],
                'ii6_base': pdv_data['ii6_base'],
                'iii_total_pretporez': pdv_data['iii_total_pretporez'],
                'iii_ispravak': pdv_data['iii_ispravak'],
                'iv_pdv_isporuke': pdv_data['iv_pdv_isporuke'],
                'iv_pretporez': pdv_data['iv_pretporez'],
                'iv_razlika': pdv_data['iv_razlika'],
                'generated_by': request.user,
            }
        )

        return render(request, 'pdv_s/report.html', {
            'company': company,
            'report': report,
            'pdv_data': pdv_data,
            'text_summary': text_summary,
            'year': year,
            'month': month,
            'invoices_in_count': invoices_in.count(),
            'invoices_out_count': invoices_out.count(),
        })

    # GET — show form
    now = timezone.now()
    from pdv_s.models import PDVSReport
    history = PDVSReport.objects.filter(company=company).order_by('-year', '-month')[:12]

    return render(request, 'pdv_s/form.html', {
        'company': company,
        'current_year': now.year,
        'current_month': now.month,
        'years': range(now.year, now.year - 3, -1),
        'months': range(1, 13),
        'history': history,
    })


@login_required
def pdv_s_xml_export(request, year, month):
    """Download PDV-S XML."""
    company = get_user_company(request)

    from pdv_s.models import PDVSReport
    report = get_object_or_404(PDVSReport, company=company, year=year, month=month)

    from pdv_s.service import generate_pdv_s_xml
    # Rebuild pdv_data from report model
    pdv_data = {field.name: getattr(report, field.name)
                for field in report._meta.fields
                if field.name.startswith(('i1', 'i2', 'i3', 'ii', 'iii', 'iv'))}

    xml_str = generate_pdv_s_xml(company, year, month, pdv_data)

    filename = f"PDV-S_{company.oib}_{month:02d}{year}.xml"
    resp = HttpResponse(xml_str, content_type='application/xml')
    resp['Content-Disposition'] = f'attachment; filename="{filename}"'
    return resp
