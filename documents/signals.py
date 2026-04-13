"""
documents/signals.py
Auto-kreiranje ArhivaEntry kad se Invoice, ERacun ili POSReceipt spremi.
Koristi get+save umjesto update_or_create da prolazi kroz ArhivaEntry.save()
(integritet hash, barcode, archive_number, deletion protection).
"""
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import IntegrityError, DatabaseError

logger = logging.getLogger('documents.signals')

# Cache invalidation
from documents.cache import invalidate_arhiva_cache


def _trigger_ai_proposal(entry):
    '''Async AI proposal for new ArhivaEntry.'''
    try:
        if entry and (entry.has_pdf or entry.has_image) and not entry.ai_proposal:
            from documents.tasks import generate_ai_proposal
            generate_ai_proposal.apply_async(args=[entry.pk], countdown=5)
    except Exception as e:
        logger.warning('_trigger_ai_proposal failed: %s', e)


@receiver(post_save, sender='invoicing.Invoice')
def archive_invoice(sender, instance, created, **kwargs):
    from django.db import transaction as _tx
    _tx.on_commit(lambda: _archive_invoice_inner(instance))

def _archive_invoice_inner(instance):
    from documents.models import ArhivaEntry
    source_type = 'invoice_out'
    source_id = str(instance.pk)
    doc_date = (instance.date_issued.date() if hasattr(instance.date_issued, 'date') else instance.date_issued) if instance.date_issued else None
    if not doc_date:
        return
    vals = {
        'company': instance.company,
        'doc_number': instance.number or '',
        'partner_name': instance.client_name or '',
        'amount': instance.total or 0,
        'currency': getattr(instance, 'currency', 'EUR') or 'EUR',
        'doc_date': doc_date,
        'zki': getattr(instance, 'zki', '') or '',
        'jir': getattr(instance, 'jir', '') or '',
    }
    try:
        entry = ArhivaEntry.objects.unscoped().filter(source_type=source_type, source_id=source_id).first()
        if entry:
            for k, v in vals.items():
                setattr(entry, k, v)
            entry.integrity_hash = entry.compute_integrity_hash()
            entry.save(update_fields=list(vals.keys()) + ['integrity_hash'])
        else:
            entry = ArhivaEntry(source_type=source_type, source_id=source_id, **vals)
            entry.save()
            logger.debug('ArhivaEntry created for Invoice %s', instance.number)

        # PDF arhivacija
        try:
            from invoicing.services.pdf_service import generate_invoice_pdf
            pdf_result = generate_invoice_pdf(instance)
            pdf_bytes = pdf_result[0] if isinstance(pdf_result, tuple) else pdf_result
            if pdf_bytes:
                import os
                from django.conf import settings as _s
                rel_path = f'arhiva/{entry.company_id}/{entry.archive_number}.pdf'
                full_path = os.path.join(_s.MEDIA_ROOT, rel_path)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, 'wb') as _f:
                    _f.write(pdf_bytes)
                entry.file_path = rel_path
                entry.has_pdf = True
                entry.save(update_fields=['file_path', 'has_pdf'])
                logger.debug('PDF archived for Invoice %s -> %s', instance.number, rel_path)
        except (FileNotFoundError, PermissionError, IOError) as pdf_err:
            logger.warning('PDF arhiva greska za Invoice %s: %s', instance.pk, pdf_err)


        # ── Fenix Inbox infusion (Sprint Fenix) ──
        try:
            from smart_import.models import FenixInboxItem
            _tip_dok = 'ura' if getattr(instance, 'doctype', '') == 'URA' else 'ira'
            FenixInboxItem.objects.create(
                company=instance.company,
                izvor='invoice', tip=_tip_dok, status='arhivirano',
                invoice_id=instance.pk,
                arhiva_entry_id=entry.pk if entry and entry.pk else None,
                doc_broj=instance.number or '',
                partner_naziv=(getattr(instance, 'client_name', '') or '')[:200],
                iznos=instance.total,
                valuta=getattr(instance, 'currency', 'EUR') or 'EUR',
                ai_tip_confidence=1.0,
                ai_summary=f'Auto: {instance.number}',
            )
        except (IntegrityError, DatabaseError) as _fie:
            logger.warning('FenixInbox invoice signal: %s', _fie)

        _trigger_ai_proposal(entry)
        invalidate_arhiva_cache(instance.company_id)

    except (FileNotFoundError, PermissionError, IOError) as e:
        logger.error('ArhivaEntry signal failed for Invoice %s: %s', instance.pk, e)


@receiver(post_save, sender='eracun.ERacun')
def archive_eracun(sender, instance, created, **kwargs):
    from django.db import transaction as _tx
    _tx.on_commit(lambda: _archive_eracun_inner(instance))

def _archive_eracun_inner(instance):
    from documents.models import ArhivaEntry
    source_type = 'eracun'
    source_id = str(instance.pk)
    doc_date = getattr(instance, 'issue_date', None) or getattr(instance, 'created_at', None)
    if hasattr(doc_date, 'date'):
        doc_date = doc_date.date()
    if not doc_date:
        return
    vals = {
        'company': instance.company,
        'doc_number': getattr(instance, 'invoice_number', '') or str(instance.pk)[:8],
        'partner_name': getattr(instance, 'recipient_name', '') or '',
        'amount': getattr(instance, 'total', 0) or 0,
        'currency': 'EUR',
        'doc_date': doc_date,
        'has_xml': True,
    }
    try:
        entry = ArhivaEntry.objects.unscoped().filter(source_type=source_type, source_id=source_id).first()
        if entry:
            for k, v in vals.items():
                setattr(entry, k, v)
            entry.integrity_hash = entry.compute_integrity_hash()
            entry.save(update_fields=list(vals.keys()) + ['integrity_hash'])
        else:
            entry = ArhivaEntry(source_type=source_type, source_id=source_id, **vals)
            entry.save()
        _trigger_ai_proposal(entry)
        invalidate_arhiva_cache(instance.company_id)
    except (IntegrityError, DatabaseError) as e:
        logger.error('ArhivaEntry signal failed for ERacun %s: %s', instance.pk, e)


@receiver(post_save, sender='pos.POSReceipt')
def archive_pos_receipt(sender, instance, created, **kwargs):
    if instance.status != 'paid':
        return
    # Ne arhiviraj bonove s 0 iznosom (prazni/cancelled/test)
    if not instance.total or instance.total <= 0:
        return
    # Defer to on_commit — avoid breaking outer transaction.atomic() in process_payment
    from django.db import transaction as _tx
    _tx.on_commit(lambda: _archive_pos_receipt_inner(instance))

def _archive_pos_receipt_inner(instance):
    from documents.models import ArhivaEntry
    source_type = 'pos_receipt'
    source_id = str(instance.pk)
    try:
        company = instance.session.terminal.company
    except Exception:
        logger.error('archive_pos_receipt: ne mogu dohvatiti company za bon %s', instance.pk)
        return
    doc_date = instance.created_at
    if hasattr(doc_date, 'date'):
        doc_date = doc_date.date()
    if not doc_date:
        return
    vals = {
        'company': company,
        'doc_number': str(instance.receipt_number),
        'partner_name': getattr(instance, 'customer_name', '') or 'Gotovinska prodaja',
        'amount': instance.total or 0,
        'currency': 'EUR',
        'doc_date': doc_date,
        'zki': getattr(instance, 'zki', '') or '',
        'jir': getattr(instance, 'jir', '') or '',
    }
    try:
        entry = ArhivaEntry.objects.unscoped().filter(source_type=source_type, source_id=source_id).first()
        if entry:
            for k, v in vals.items():
                setattr(entry, k, v)
            entry.integrity_hash = entry.compute_integrity_hash()
            entry.save(update_fields=list(vals.keys()) + ['integrity_hash'])
        else:
            entry = ArhivaEntry(source_type=source_type, source_id=source_id, **vals)
            entry.save()

        # ── Fenix Inbox POS infusion ──
        try:
            from smart_import.models import FenixInboxItem
            _pos_co = instance.session.terminal.company if hasattr(instance, 'session') else None
            if _pos_co:
                FenixInboxItem.objects.create(
                    company=_pos_co,
                    izvor='pos', tip='ira', status='arhivirano',
                    pos_receipt_id=instance.pk,
                    arhiva_entry_id=entry.pk if entry and entry.pk else None,
                    doc_broj=f'BON-{instance.receipt_number}',
                    partner_naziv=(getattr(instance, 'buyer_name', '') or 'Gotovinski kupac')[:200],
                    iznos=instance.total, valuta='EUR',
                    ai_tip_confidence=1.0,
                    ai_summary=f'POS bon #{instance.receipt_number}',
                )
        except (IntegrityError, DatabaseError) as _fpe:
            logger.warning('FenixInbox pos signal: %s', _fpe)

    except (IntegrityError, DatabaseError) as e:
        logger.error('ArhivaEntry signal failed for POSReceipt %s: %s', instance.pk, e)


# ── Activity Tracking for Archive entries ──────────────────────────────
@receiver(post_save, sender='documents.ArhivaEntry')
def track_archive_activity(sender, instance, created, **kwargs):
    """Track new archive entries as activity events."""
    if not created:
        return
    user = getattr(instance, 'archived_by', None)
    if not user:
        return
    try:
        from worktime.tracker import track
        track(user, 'DOC', 'ARCHIVE_UPLOAD', ref=instance.archive_number,
              detail='%s: %s (%s EUR)' % (
                  instance.get_source_type_display(),
                  instance.doc_number,
                  instance.amount),
              company=instance.company)
    except Exception:
        pass
