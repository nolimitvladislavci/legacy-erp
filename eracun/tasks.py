

from celery import shared_task
import logging
from django.db import IntegrityError, DatabaseError

logger = logging.getLogger('eracun.tasks')


@shared_task(bind=True, soft_time_limit=120)
def fetch_posrednik_inbox(self):
    """
    Two-Step Fetch: dohvati listu -> za svaki dohvati XML -> receive_eracun().
    Step 1: GET /incoming-invoices -> JSON lista s ID-jevima
    Step 2: GET /incoming-invoices/{id}/xml -> puni UBL 2.1 XML
    receive_eracun() kreira ERacun + Items + TaxSummary + okida FENIX Interceptor.
    """
    from companies.models import Company
    from eracun.services.posrednik_service import PosrednikService
    from eracun.services.inbox import receive_eracun
    from eracun.models import ERacun
    from django.utils import timezone
    from datetime import timedelta

    fetched = 0
    skipped = 0
    errors = 0
    since = timezone.now() - timedelta(days=7)

    for company in Company.objects.all():
        if not PosrednikService.is_configured(company):
            continue

        try:
            result = PosrednikService.fetch_inbox(company, since=since)
            if not result.get('ok') or not result.get('invoices'):
                continue

            for inv_data in result['invoices']:
                inv_id = inv_data.get('id', inv_data.get('invoiceId', ''))
                inv_number = inv_data.get('invoiceNumber', inv_data.get('invoice_number', str(inv_id)))
                issuer_oib = inv_data.get('senderOib', inv_data.get('issuer_oib', ''))

                # Duplikat check PRIJE API poziva (stedi bandwidth)
                if ERacun.objects.filter(
                    company=company,
                    invoice_number=inv_number,
                    issuer_oib=issuer_oib,
                    direction='incoming',
                ).exists() or ERacun.objects.filter(fina_uuid=inv_id).exists():
                    skipped += 1
                    continue

                # Two-Step: dohvati puni XML
                xml_string = PosrednikService.get_incoming_xml(company, str(inv_id))

                if xml_string and xml_string.strip().startswith('<?xml') or (xml_string and '<Invoice' in xml_string):
                    # Puni UBL XML — delegiraj na receive_eracun (koji okida FENIX)
                    try:
                        inbox_result = receive_eracun(company, xml_string, received_via='posrednik')
                        if inbox_result.get('success'):
                            # Spremi posrednik ID za tracking
                            eracun = inbox_result.get('eracun')
                            if eracun and inv_id:
                                eracun.fina_uuid = str(inv_id)
                                eracun.save(update_fields=['fina_uuid'])
                            fetched += 1
                            logger.info('Two-Step fetch OK: %s od %s', inv_number, issuer_oib)
                            # BORG Audit Entry — e-Racun primljen
                            try:
                                from borg_ops.audit_helpers import log_borg_audit
                                log_borg_audit(
                                    company=company,
                                    entry_type='ERACUN',
                                    summary=f'e-Racun primljen: {inv_number} od {issuer_oib}',
                                    document=eracun,
                                    verification_type='FINA',
                                    verification_result={'fina_uuid': str(inv_id), 'issuer_oib': issuer_oib},
                                )
                            except ImportError:
                                pass
                        else:
                            # Duplikat ili parse error — logiramo ali ne pada
                            skipped += 1
                            logger.debug('receive_eracun skip: %s', inbox_result.get('error', ''))
                    except ImportError as e:
                        errors += 1
                        logger.warning('receive_eracun error za %s: %s', inv_number, e)
                elif xml_string is None:
                    # XML endpoint nije dostupan — fallback na header-only (stari nacin)
                    ERacun.objects.create(
                        company=company,
                        direction='incoming',
                        doc_type='380',
                        invoice_number=inv_number,
                        issuer_name=inv_data.get('senderName', ''),
                        issuer_oib=issuer_oib,
                        recipient_name=company.name,
                        recipient_oib=company.oib or '',
                        total=inv_data.get('totalAmount', 0),
                        issue_date=timezone.now().date(),
                        status='accepted',
                        fina_uuid=str(inv_id),
                        note='Primljeno od posrednika (samo zaglavlje — XML nedostupan)',
                    )
                    fetched += 1
                    logger.info('Header-only fetch: %s (XML endpoint nedostupan)', inv_number)
                else:
                    errors += 1
                    logger.warning('Nevaljan XML za %s: %s...', inv_number, (xml_string or '')[:50])

        except (IntegrityError, DatabaseError) as e:
            errors += 1
            logger.warning('Inbox fetch error za %s: %s', company.name, e)

    logger.info('fetch_posrednik_inbox: fetched=%d, errors=%d', fetched, errors)
    return {'fetched': fetched, 'errors': errors}


@shared_task(bind=True, soft_time_limit=60)
def retry_unsent_eracuni(self):
    """Retry slanja e-racuna koji su ostali u statusu error/draft."""
    from eracun.models import ERacun
    from eracun.services.posrednik_service import PosrednikService
    from django.utils import timezone
    from datetime import timedelta

    cutoff = timezone.now() - timedelta(hours=48)
    unsent = ERacun.objects.filter(
        status__in=['error', 'draft'],
        source_receipt__isnull=False,
        created_at__gte=cutoff,
    ).select_related('company')

    sent = 0
    for eracun in unsent[:20]:
        if PosrednikService.is_configured(eracun.company):
            result = PosrednikService.send(eracun)
            if result.get('ok'):
                sent += 1

    return {'retried': unsent.count(), 'sent': sent}


# ── Cert Expiry Monitor — dnevna provjera ──────────────────────────────────

from celery import shared_task

@shared_task(name='eracun.check_cert_expiry')
def check_cert_expiry():
    """Dnevna provjera certifikata. Celery beat: svaki dan 08:00."""
    from eracun.services.cert_monitor import run_daily_check
    results = run_daily_check()
    expiring = [r for r in results if r.get('status') not in ('ok', 'ERROR')]
    return f'{len(results)} certs checked, {len(expiring)} expiring'


# ══════════════════════════════════════════════════════════════════════════════
# BORG FENIX: Async e-Racun slanje s XSD-First + Exponential Backoff
# ══════════════════════════════════════════════════════════════════════════════

@shared_task(bind=True, max_retries=5, soft_time_limit=120)
def send_eracun_to_fina_async(self, eracun_id):
    """
    Async slanje e-Racuna prema FINA CIS-u.

    Pravilo 1 (XSDFirst): XSD validacija PRIJE slanja. Ako padne -> XSD_ERROR, nema retryja.
    Pravilo 2 (Celery Always): Exponential backoff: 1min, 2min, 4min, 8min, 16min.
    Pravilo 3 (Redis Shield): Bonitet check koristi cache.

    Flow:
    1. Dohvati ERacun iz baze
    2. validate_xml_against_xsd() — ako padne, XSD_ERROR, STOP
    3. process_eracun() — sign + send to FINA
    4. Ako FINA timeout/error -> retry s exponential backoff
    5. Ako FINA reject (poslovni razlog) -> nema retryja, rejected
    """
    from eracun.models import ERacun, ERacunLog
    from eracun.services.engine import process_eracun, build_fina_xml, get_cert_pem
    from eracun.services.validator import validate_xml_against_xsd, XSDValidationError
    from lxml import etree
    import requests

    try:
        eracun = ERacun.objects.select_related('company').get(pk=eracun_id)
    except ERacun.DoesNotExist:
        logger.error('[FINA ASYNC] ERacun %s ne postoji', eracun_id)
        return {'error': 'ERacun not found'}

    # ── Pravilo 1: XSD-First validacija ──────────────────────────────
    if eracun.xml_request:
        try:
            validate_xml_against_xsd(eracun.xml_request.encode('utf-8'))
            logger.info('[FINA ASYNC] XSD validacija OK za %s', eracun.invoice_number)
        except XSDValidationError as xsd_err:
            # XSD greska = STOP, nema retryja
            eracun.status = 'invalid'
            eracun.error_message = f'XSD validacija: {xsd_err.errors[0]["message_hr"]}'
            eracun.error_code = 'XSD_ERROR'
            eracun.save(update_fields=['status', 'error_message', 'error_code'])
            ERacunLog.objects.create(
                eracun=eracun, action='xsd_validation', status='error',
                message=eracun.error_message,
                details={'errors': xsd_err.errors[:5]},
            )
            logger.warning('[FINA ASYNC] XSD FAIL za %s: %s', eracun.invoice_number, xsd_err)
            return {
                'status': 'XSD_ERROR',
                'errors': xsd_err.errors[:5],
                'retry': False,
            }

    # ── Slanje prema FINA ────────────────────────────────────────────
    try:
        success, message = process_eracun(eracun)

        if success:
            logger.info('[FINA ASYNC] Uspjesno: %s -> %s', eracun.invoice_number, message)
            # BORG Audit Entry — e-Racun poslan uspjesno
            try:
                from borg_ops.audit_helpers import log_borg_audit
                log_borg_audit(
                    company=eracun.company,
                    entry_type='ERACUN',
                    summary=f'e-Racun poslan FINA: {eracun.invoice_number}',
                    document=eracun,
                    verification_type='FINA',
                    verification_result={'status': 'accepted', 'message': message},
                )
            except ImportError:
                pass
            return {'status': 'accepted', 'message': message}

        # FINA rejected (poslovni razlog) -> nema retryja
        if eracun.status == 'rejected':
            logger.warning('[FINA ASYNC] FINA rejected %s: %s', eracun.invoice_number, message)
            return {'status': 'rejected', 'message': message, 'retry': False}

        # Ostale greske -> retry
        raise Exception(message)

    except requests.exceptions.RequestException as e:
        # ── Pravilo 2: Exponential backoff ───────────────────────────
        countdown = 2 ** self.request.retries * 60  # 60s, 120s, 240s, 480s, 960s
        logger.warning(
            '[FINA ASYNC] Network error za %s (pokusaj %d/%d, retry za %ds): %s',
            eracun.invoice_number, self.request.retries + 1, 5, countdown, e,
        )
        eracun.status = 'error'
        eracun.error_message = f'FINA nedostupna (pokusaj {self.request.retries + 1}/5): {str(e)[:100]}'
        eracun.save(update_fields=['status', 'error_message'])
        raise self.retry(countdown=countdown, exc=e)

    except Exception as e:
        if self.request.retries < self.max_retries:
            countdown = 2 ** self.request.retries * 60
            logger.warning(
                '[FINA ASYNC] Error za %s (pokusaj %d/%d, retry za %ds): %s',
                eracun.invoice_number, self.request.retries + 1, 5, countdown, e,
            )
            eracun.status = 'error'
            eracun.error_message = f'Greska (pokusaj {self.request.retries + 1}/5): {str(e)[:100]}'
            eracun.save(update_fields=['status', 'error_message'])
            raise self.retry(countdown=countdown, exc=e)
        else:
            # Max retries exhausted
            eracun.status = 'error'
            eracun.error_message = f'Svi pokusaji iscrpljeni (5/5): {str(e)[:100]}'
            eracun.save(update_fields=['status', 'error_message'])
            ERacunLog.objects.create(
                eracun=eracun, action='sent', status='error',
                message=eracun.error_message,
            )
            logger.error('[FINA ASYNC] Max retries za %s: %s', eracun.invoice_number, e)
            return {'status': 'max_retries_exhausted', 'error': str(e)[:200]}
