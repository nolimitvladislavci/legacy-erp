import os

def setup_pdf_engine():
    # 1. Nadogradnja Views-a za korištenje postojećih HR/DE predložaka
    views_path = 'calculator/views.py'
    views_code = """from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from django.template.loader import get_template
from django.contrib.auth.decorators import login_required
from .models import Calculation
from xhtml2pdf import pisa
import io

@login_required
def export_calculation_pdf(request, pk):
    calculation = get_object_or_404(Calculation, pk=pk)
    totals = calculation.calculate_totals()
    
    # Odabir jezika (default HR, može se proširiti)
    lang = request.GET.get('lang', 'hr')
    template_path = f'invoicing/invoice_{lang}.html'
    
    # Mapiranje podataka kalkulatora u format koji predložak računa očekuje
    context = {
        'invoice': {
            'number': f"PON-{calculation.project.code}",
            'date': calculation.created_at,
            'client': calculation.project.client,
            'company': calculation.project.company,
            'items': [
                {
                    'description': item.description,
                    'quantity': item.quantity,
                    'unit': item.normative.unit if item.normative else 'kom',
                    'price': float(item.unit_price_material) + (item.labor_hours_per_unit * float(item.labor_rate_applied)),
                    'total': item.total_price
                } for item in calculation.items.all()
            ],
            'total_net': totals['offer_total_net'],
            'total_vat': totals['offer_total_vat'] - totals['offer_total_net'],
            'total_gross': totals['offer_total_vat'],
            'is_offer': True  # Marker da predložak ispiše "PONUDA" umjesto "RAČUN"
        }
    }

    template = get_template(template_path)
    html = template.render(context)
    result = io.BytesIO()
    pdf = pisa.pisaDocument(io.BytesIO(html.encode("UTF-8")), result)

    if not pdf.err:
        response = HttpResponse(result.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="Ponuda_{calculation.project.code}.pdf"'
        return response
    return HttpResponse("Greška pri generiranju PDF-a", status=400)
"""
    with open(views_path, 'a') as f:
        f.write(views_code)

    # 2. Registracija URL putanje za PDF
    urls_path = 'calculator/urls.py'
    urls_code = """
    path('<int:pk>/pdf/', views.export_calculation_pdf, name='calculation_pdf'),
"""
    # Čistimo i ponovno pišemo URL-ove da izbjegnemo duplanje
    with open(urls_path, 'w') as f:
        f.write("from django.urls import path\\nfrom . import views\\n\\nurlpatterns = [\\n")
        f.write("    path('create/<int:project_id>/', views.create_from_project, name='create_calculation'),\\n")
        f.write("    path('<int:pk>/', views.calculation_detail, name='calculation_detail'),\\n")
        f.write("    path('<int:pk>/pdf/', views.export_calculation_pdf, name='calculation_pdf'),\\n")
        f.write("]\\n")

    print("PDF Engine integriran s postojećim HR/DE predlošcima.")

if __name__ == "__main__":
    setup_pdf_engine()
