"""
Template tag za document integrity badge.

Usage u PDF templateima:
    {% load doc_integrity %}

    <!-- Na dnu dokumenta: -->
    {% doc_integrity_badge %}

    <!-- Ili s parametrima: -->
    {% doc_integrity_badge lang="de" %}
"""
from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.inclusion_tag('core/integrity_badge.html', takes_context=True)
def doc_integrity_badge(context, lang='hr'):
    """Renderira integrity badge s hashom, timestampom i pravnim tekstom."""
    return {
        'hash': context.get('integrity_hash', ''),
        'hash_full': context.get('integrity_hash_full', ''),
        'timestamp': context.get('integrity_timestamp', ''),
        'generated_by': context.get('integrity_generated_by', ''),
        'doc_id': context.get('integrity_doc_id', ''),
        'system': context.get('integrity_system', 'LIMIT Connect ERP'),
        'lang': lang,
        'verified_text': context.get('integrity_verified_text_de' if lang == 'de' else 'integrity_verified_text_hr', ''),
    }
