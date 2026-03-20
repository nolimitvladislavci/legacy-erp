"""
Document Integrity Service — SHA-256 hash za sve dokumente.

Usage:
    from core.doc_integrity import compute_doc_hash, get_integrity_badge_context

    # U view-u koji generira PDF:
    ctx = get_integrity_badge_context(request, document_id='INV-2026-001', content=html_string)
    # ctx sadrzi: doc_hash, timestamp, generated_by, verified_text
"""
import hashlib
from datetime import datetime
from django.utils import timezone


def compute_doc_hash(content):
    """SHA-256 hash bilo kojeg sadrzaja (string ili bytes)."""
    if isinstance(content, str):
        content = content.encode('utf-8')
    return hashlib.sha256(content).hexdigest()


def get_integrity_badge_context(request=None, document_id='', content='', company=None):
    """
    Vraca context dict za integrity badge u PDF templateima.
    Dodaje se u template context pri renderiranju PDF-a.
    """
    doc_hash = compute_doc_hash(content) if content else ''
    ts = timezone.now()

    generated_by = ''
    if request and hasattr(request, 'user') and request.user.is_authenticated:
        generated_by = request.user.get_full_name() or request.user.username

    client_ip = ''
    if request:
        client_ip = (
            request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
            or request.META.get('REMOTE_ADDR', '')
        )

    company_name = ''
    company_oib = ''
    if company:
        company_name = company.name
        company_oib = company.oib

    return {
        'integrity_hash': doc_hash[:16] + '...' + doc_hash[-8:] if doc_hash else '',
        'integrity_hash_full': doc_hash,
        'integrity_timestamp': ts.strftime('%d.%m.%Y %H:%M:%S'),
        'integrity_generated_by': generated_by,
        'integrity_client_ip': client_ip,
        'integrity_doc_id': document_id,
        'integrity_company': company_name,
        'integrity_oib': company_oib,
        'integrity_verified_text_hr': 'Elektronicki dokument — vjerodostojan bez pecata i potpisa (cl. 9. st. 2. ZOR-a)',
        'integrity_verified_text_de': 'Elektronisches Dokument — gueltig ohne Stempel und Unterschrift (§14 UStG)',
        'integrity_system': 'LIMIT Connect ERP v2026.03',
    }
