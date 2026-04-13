from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
"""
PDF Template Resolver — dohvaća pravi base template ovisno o company.pdf_template.

Usage u viewu:
    from core.pdf_templates import get_pdf_base
    base = get_pdf_base(company)  # → 'pdf/base_viskovic.html'

Usage u templateu:
    {% extends pdf_base %}
    {% block doc_title %}RAČUN{% endblock %}
    {% block content %}...{% endblock %}
"""

TEMPLATES = {
    'viskovic': 'pdf/base_viskovic.html',
    'datev': 'pdf/base_datev.html',
    'modern': 'pdf/base_modern.html',
}


def get_pdf_base(company=None):
    """Vrati path do base PDF templatea za firmu."""
    if company:
        choice = getattr(company, 'pdf_template', 'viskovic')
        return TEMPLATES.get(choice, TEMPLATES['viskovic'])
    return TEMPLATES['viskovic']


def get_all_templates():
    """Lista svih dostupnih predložaka za settings UI."""
    return [
        {'id': 'viskovic', 'name': 'Visković (Gold/Premium)', 'preview': 'Zlatno zaglavlje, tamni akcenti, premium osjećaj'},
        {'id': 'datev', 'name': 'DATEV (Minimalistički)', 'preview': 'Crno-bijeli, strogi tabularni format, Steuerberater standard'},
        {'id': 'modern', 'name': 'Modern (Plavo/Bijeli)', 'preview': 'Plavo zaglavlje, zaobljeni kutovi, svjež i profesionalan'},
    ]
