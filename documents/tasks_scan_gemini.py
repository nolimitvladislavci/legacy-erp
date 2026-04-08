"""
Scan Batch Celery Tasks — Self-Rescheduling Pipeline.

Umjesto time.sleep(62) koji blokira workera:
  1. Task obradi 10 slika
  2. Ako ima jos, pozove SAMOG SEBE s countdown=62
  3. Worker slobodan za druge korisnike u tih 62s

10/10 inzenjerstvo. Nula blokiranja.
"""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, soft_time_limit=120, name='documents.process_scan_chunk')
def process_scan_chunk(self, batch_id, offset=0, cumulative_ok=0, cumulative_err=0):
    """
    Obradi jednu grupu od 10 slika, zatim se SAMO-RESCHEDULIRA.

    Flow:
      Poziv #1: offset=0  -> obradi slike 0-9   -> countdown=62 -> poziv #2
      Poziv #2: offset=10 -> obradi slike 10-19  -> countdown=62 -> poziv #3
      ...
      Poziv #N: offset=90 -> obradi slike 90-99  -> has_more=False -> group_documents

    Worker je SLOBODAN izmedju poziva. Moze obradjivati
    druge korisnike, druge batcheve, bilo sto.
    """
    from documents.services.document_processor import DocumentProcessor

    processed, errors, has_more = DocumentProcessor.process_chunk(batch_id, offset)

    total_ok = cumulative_ok + processed
    total_err = cumulative_err + errors

    if has_more:
        # Self-reschedule s countdown=62s (rate limit)
        # Worker je SLOBODAN u tih 62 sekundi
        next_offset = offset + DocumentProcessor.BATCH_SIZE
        process_scan_chunk.apply_async(
            args=[batch_id, next_offset, total_ok, total_err],
            countdown=DocumentProcessor.RATE_LIMIT_SECONDS,
        )
        logger.info(
            'Batch %d: chunk at offset %d done (%d ok, %d err). '
            'Next chunk in %ds.',
            batch_id, offset, processed, errors,
            DocumentProcessor.RATE_LIMIT_SECONDS
        )
    else:
        # Zadnja grupa — pokreni grouping
        logger.info(
            'Batch %d: all chunks done (total: %d ok, %d err). Grouping...',
            batch_id, total_ok, total_err
        )
        finalize_scan_batch.delay(batch_id, total_ok, total_err)

    return {
        'batch_id': batch_id,
        'offset': offset,
        'processed': processed,
        'errors': errors,
        'has_more': has_more,
    }


@shared_task(bind=True, soft_time_limit=60, name='documents.finalize_scan_batch')
def finalize_scan_batch(self, batch_id, total_ok=0, total_err=0):
    """
    Zavrsi batch: AI grupiranje visestranicnih dokumenata.
    Poziva se automatski kad zadnji chunk zavrsi.
    """
    from documents.services.document_processor import DocumentProcessor

    try:
        num_groups = DocumentProcessor.group_documents(batch_id)
        logger.info(
            'Batch %d finalized: %d groups, %d ok, %d err',
            batch_id, num_groups, total_ok, total_err
        )
        return {
            'batch_id': batch_id,
            'documents': num_groups,
            'total_ok': total_ok,
            'total_err': total_err,
        }
    except Exception as e:
        logger.error('Batch %d finalize failed: %s', batch_id, e)
        from documents.models import ScanBatch
        try:
            batch = ScanBatch.objects.get(pk=batch_id)
            batch.status = 'error'
            batch.error_message = 'Grupiranje neuspjelo: %s' % str(e)[:200]
            batch.save(update_fields=['status', 'error_message'])
        except Exception:
            pass
        return {'error': str(e)}


@shared_task(bind=True, soft_time_limit=300, name='documents.archive_scan_batch')
def archive_scan_batch(self, batch_id, user_id=None):
    """Atomic arhiviranje + AI proposal queue."""
    from documents.services.document_processor import DocumentProcessor

    try:
        created, ai_queued = DocumentProcessor.archive_batch(batch_id, user_id)
        logger.info(
            'Batch %d archived: %d entries, %d AI proposals',
            batch_id, created, ai_queued
        )
        return {'archived': created, 'ai_queued': ai_queued}
    except Exception as e:
        logger.error('Batch %d archive failed: %s', batch_id, e)
        from documents.models import ScanBatch
        try:
            batch = ScanBatch.objects.get(pk=batch_id)
            batch.status = 'error'
            batch.error_message = 'Arhiviranje neuspjelo: %s' % str(e)[:200]
            batch.save(update_fields=['status', 'error_message'])
        except Exception:
            pass
        return {'error': str(e)}
