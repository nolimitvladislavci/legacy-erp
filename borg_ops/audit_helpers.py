"""
BORG Audit Helpers — centralna funkcija za kreiranje BorgAuditEntry.

Koristi se iz bilo kojeg modula:
    from borg_ops.audit_helpers import log_borg_audit
    log_borg_audit(company, 'FISCAL', 'Fiskalizacija uspjesna', document=receipt)
"""
import logging

from django.contrib.contenttypes.models import ContentType
from django.db import DatabaseError, IntegrityError

logger = logging.getLogger('borg.audit')


def log_borg_audit(company, entry_type, summary, severity='INFO',
                   document=None, regulatory_update=None,
                   legal_reference='', verification_type='',
                   verification_result=None, user=None, metadata=None):
    """
    Kreiraj immutable BorgAuditEntry.

    Args:
        company: Company instance (required)
        entry_type: str — REGULATORY, FISCAL, INVOICE, ERACUN, VIES_CHECK,
                    OIB_CHECK, AML_ALERT, GDPR_ACTION, TRUST_CHECKPOINT,
                    EXPORT, BRIEFING
        summary: str — Human-readable opis
        severity: str — INFO, WARNING, ACTION_REQUIRED, CRITICAL
        document: Model instance za generic FK (invoice, receipt, eracun...)
        regulatory_update: RegulatoryUpdate instance
        legal_reference: str — "NN 35/2026, cl.15"
        verification_type: str — VIES, OIB, CIS, FINA
        verification_result: dict — rezultat verifikacije
        user: User instance
        metadata: dict — slobodni podaci

    Returns:
        BorgAuditEntry instance or None on error
    """
    from borg_ops.models import BorgAuditEntry

    ct = None
    obj_id = None
    if document is not None:
        ct = ContentType.objects.get_for_model(document)
        obj_id = document.pk

    try:
        entry = BorgAuditEntry(
            company=company,
            entry_type=entry_type,
            severity=severity,
            content_type=ct,
            object_id=obj_id,
            regulatory_update=regulatory_update,
            legal_reference=legal_reference,
            verification_type=verification_type,
            verification_result=verification_result or {},
            summary=summary,
            metadata=metadata or {},
            created_by=user,
        )
        entry.save()
        logger.debug('BorgAuditEntry created: [%s] %s', entry_type, summary[:80])
        return entry
    except (IntegrityError, DatabaseError) as e:
        logger.error('BorgAuditEntry creation failed: %s', e)
        return None
