"""smart_import/tasks.py -- Celery task for async invoice processing.
   v2 - 2026-03-17: Race condition fix, status tracking, retry fallback, regex fix.
"""
import logging
import re

from celery import shared_task

logger = logging.getLogger(__name__)

LOCK_PREFIX = "smart_import_lock_"
LOCK_TTL = 300


def _acquire_lock(batch_id):
    """Acquire Redis lock to prevent duplicate processing."""
    try:
        from django.core.cache import cache
        lock_key = f"{LOCK_PREFIX}{batch_id}"
        return cache.add(lock_key, "1", LOCK_TTL)
    except Exception:
        return True


def _release_lock(batch_id):
    """Release Redis lock."""
    try:
        from django.core.cache import cache
        lock_key = f"{LOCK_PREFIX}{batch_id}"
        cache.delete(lock_key)
    except Exception:
        pass


@shared_task(bind=True, max_retries=2, soft_time_limit=120, time_limit=180)
def process_import_batch(self, batch_id):
    """Parse uploaded file and create ImportBatchItems with fuzzy-matched inventory items."""
    from django.utils import timezone
    from smart_import.models import ImportBatch, ImportBatchItem
    from smart_import.services import parse_xml, parse_pdf, parse_image, match_items

    try:
        batch = ImportBatch.objects.get(pk=batch_id)
    except ImportBatch.DoesNotExist:
        logger.error("ImportBatch %s not found", batch_id)
        return

    if not _acquire_lock(batch_id):
        logger.warning("Batch %s already being processed (lock held), skipping", batch_id)
        return

    try:
        batch.status = "processing"
        batch.status_message = "AI cita racun..."
        batch.processing_started_at = timezone.now()
        batch.retry_count = (batch.retry_count or 0) + 1
        batch.save(update_fields=["status", "status_message", "processing_started_at", "retry_count"])

        ft = batch.file_type.lower()
        fp = batch.file.path

        if not batch.original_filename and batch.file:
            import os
            batch.original_filename = os.path.basename(batch.file.name)
            batch.save(update_fields=["original_filename"])

        batch.status_message = "Ekstrakcija podataka..."
        batch.save(update_fields=["status_message"])

        if ft == "xml":
            rows = parse_xml(fp)
        elif ft == "pdf":
            rows = parse_pdf(fp)
        elif ft in ("image", "img"):
            rows = parse_image(fp)
        elif ft == "multipage":
            rows = _process_multipage(batch)
        else:
            rows = []

        if not rows and ft in ("image", "img"):
            batch.status_message = "Ponovni pokusaj s poboljsanom slikom..."
            batch.save(update_fields=["status_message"])
            from smart_import.services import parse_image_enhanced
            rows = parse_image_enhanced(fp)

        if not rows:
            batch.status = "error"
            batch.error_msg = "Nema stavki - datoteka je prazna ili format nije prepoznat."
            batch.status_message = "Neuspjelo - nema prepoznatih stavki"
            batch.save(update_fields=["status", "error_msg", "status_message"])
            _release_lock(batch_id)
            return

        batch.status_message = "Spremanje stavki..."
        batch.save(update_fields=["status_message"])

        if ft != "multipage":
            batch.raw_json = rows
        batch.items.all().delete()
        for i, row in enumerate(rows):
            ImportBatchItem.objects.create(
                batch=batch,
                row_index=i,
                vendor_name=row.get("vendor_name", ""),
                quantity=row.get("quantity", "1"),
                purchase_price=row.get("purchase_price", "0"),
            )

        batch.status_message = "Spajanje s artiklima..."
        batch.save(update_fields=["status_message"])

        match_items(batch)

        batch.status = "ready"
        batch.status_message = "Gotovo! {} stavki prepoznato.".format(batch.items.count())
        batch.save(update_fields=["status", "raw_json", "status_message"])
        logger.info("Batch #%d processed successfully: %d items", batch_id, batch.items.count())

    except Exception as exc:
        logger.exception("process_import_batch failed for batch %s", batch_id)
        retry_count = getattr(batch, "retry_count", 0) or 0

        if retry_count < 2:
            batch.status = "pending"
            batch.status_message = "Ponovni pokusaj ({}/3)...".format(retry_count + 1)
            batch.save(update_fields=["status", "status_message"])
            _release_lock(batch_id)
            raise self.retry(exc=exc, countdown=10)
        else:
            batch.status = "error"
            batch.error_msg = "Obrada nije uspjela nakon {} pokusaja: {}".format(retry_count, str(exc)[:200])
            batch.status_message = "Greska - prijavite problem ili pokusajte ponovo"
            batch.save(update_fields=["status", "error_msg", "status_message"])
    finally:
        _release_lock(batch_id)


def _process_multipage(batch):
    """Process multi-page camera capture: parse each page image and merge results."""
    from smart_import.services import parse_image
    import os

    raw = batch.raw_json or {}
    page_paths = raw.get("page_paths", [])

    if not page_paths:
        page_paths = [batch.file.path]

    all_rows = []
    page_results = []

    for idx, path in enumerate(page_paths):
        if not os.path.exists(path):
            logger.warning("Page %d missing: %s", idx + 1, path)
            continue

        batch.status_message = "AI cita stranicu {}/{}...".format(idx + 1, len(page_paths))
        batch.save(update_fields=["status_message"])

        logger.info("Processing page %d/%d: %s", idx + 1, len(page_paths), path)
        rows = parse_image(path)
        page_results.append({"page": idx + 1, "items": len(rows)})
        all_rows.extend(rows)

    seen = {}
    deduped = []
    for row in all_rows:
        key = row["vendor_name"].strip().lower()
        if key in seen:
            existing = seen[key]
            if float(existing.get("purchase_price", 0)) == 0 and float(row.get("purchase_price", 0)) > 0:
                seen[key] = row
                deduped = [r for r in deduped if r["vendor_name"].strip().lower() != key]
                deduped.append(row)
        else:
            seen[key] = row
            deduped.append(row)

    batch.raw_json = {"page_results": page_results, "rows": deduped}
    batch.save(update_fields=["raw_json"])

    return deduped


@shared_task(bind=True, max_retries=2)
def fetch_invoices_from_email(self):
    """
    Skenira CompanyMailbox zapise (DB) + .env fallback.
    Podrzava Gmail + addressing za multi-company routing.
    """
    import os
    import imaplib
    import email as email_mod
    from email.header import decode_header
    from django.core.files.base import ContentFile
    from django.utils import timezone
    from companies.models import Company
    from smart_import.models import ImportBatch, CompanyMailbox, FailedImport

    ALLOWED_EXTS = {
        ".xml": "xml", ".pdf": "pdf",
        ".jpg": "image", ".jpeg": "image", ".png": "image",
        ".webp": "image", ".heic": "image", ".heif": "image",
    }

    MIN_FILE_SIZE = 10_000
    # FIX: escaped hyphen in character class to avoid regex error
    SKIP_FILENAME_RE = re.compile(
        r"^(icon|logo|badge|warning|banner|signature|footer|header|spacer|pixel|tracking)[_\-.]",
        re.IGNORECASE,
    )

    all_mailboxes = list(
        CompanyMailbox.objects.filter(is_active=True, protocol="imap")
        .select_related("company")
    )

    def base_email(addr):
        local, domain = addr.lower().split("@")
        if "+" in local:
            local = local.split("+")[0]
        return "{}@{}".format(local, domain)

    email_company_map = {}
    for mb in all_mailboxes:
        email_company_map[mb.email_address.lower()] = {
            "company": mb.company,
            "db_obj": mb,
        }

    imap_logins = {}
    for mb in all_mailboxes:
        if not mb.imap_server or not mb.imap_password:
            continue
        be = base_email(mb.email_address)
        if be not in imap_logins:
            imap_logins[be] = {
                "server": mb.imap_server,
                "user": be,
                "pass": mb.imap_password,
                "folder": mb.imap_folder or "INBOX",
                "ssl": mb.imap_use_ssl,
                "default_company": mb.company,
                "default_db_obj": mb,
            }

    db_bases = set(imap_logins.keys())
    box_count = int(os.getenv("IMAP_MAILBOX_COUNT", "0"))
    fallback_company = None
    for i in range(1, box_count + 1):
        prefix = "IMAP_BOX{}".format(i)
        server = os.getenv("{}_SERVER".format(prefix))
        user = os.getenv("{}_USER".format(prefix))
        pwd = os.getenv("{}_PASS".format(prefix))
        folder = os.getenv("{}_FOLDER".format(prefix), "INBOX")
        if server and user and pwd and user.lower() not in db_bases:
            if fallback_company is None:
                fallback_company = Company.objects.first()
            imap_logins[user.lower()] = {
                "server": server, "user": user, "pass": pwd,
                "folder": folder, "ssl": True,
                "default_company": fallback_company, "default_db_obj": None,
            }

    if not imap_logins:
        logger.warning("Email Rampa: nema konfiguriranih sanducica.")
        return "Nema konfiguriranih sanducica"

    total_count = 0
    results = []

    def resolve_company(msg):
        for header in ("Delivered-To", "To", "X-Original-To"):
            val = msg.get(header, "")
            if not val:
                continue
            for addr_part in val.split(","):
                addr_part = addr_part.strip().lower()
                if "<" in addr_part and ">" in addr_part:
                    addr_part = addr_part.split("<")[1].split(">")[0]
                if addr_part in email_company_map:
                    entry = email_company_map[addr_part]
                    return entry["company"], entry["db_obj"]
        return None, None

    for login_key, login in imap_logins.items():
        mb_user = login["user"]
        try:
            if login["ssl"]:
                mail_conn = imaplib.IMAP4_SSL(login["server"])
            else:
                mail_conn = imaplib.IMAP4(login["server"])
            mail_conn.login(mb_user, login["pass"])
            mail_conn.select(login["folder"])

            status, msg_ids = mail_conn.search(None, "UNSEEN")
            if status != "OK" or not msg_ids[0]:
                mail_conn.logout()
                results.append("{}: 0 novih".format(mb_user))
                if login["default_db_obj"]:
                    login["default_db_obj"].last_check = timezone.now()
                    login["default_db_obj"].last_error = ""
                    login["default_db_obj"].save(update_fields=["last_check", "last_error"])
                continue

            count = 0
            for num in msg_ids[0].split():
                res, msg_data = mail_conn.fetch(num, "(BODY.PEEK[])")
                for response_part in msg_data:
                    if not isinstance(response_part, tuple):
                        continue

                    msg = email_mod.message_from_bytes(response_part[1])
                    subject = str(msg.get("Subject", ""))
                    sender = str(msg.get("From", ""))

                    company, db_obj = resolve_company(msg)
                    if not company:
                        company = login["default_company"]
                        db_obj = login["default_db_obj"]

                    if not company:
                        logger.warning("Email Rampa [%s]: nema firme za: %s", mb_user, subject)
                        continue

                    logger.info("Email Rampa [%s -> %s]: od %s (%s)",
                                mb_user, company.name, sender, subject)

                    attachments_found = 0
                    for part in msg.walk():
                        if part.get_content_maintype() == "multipart":
                            continue
                        if part.get("Content-Disposition") is None:
                            continue

                        filename = part.get_filename()
                        if not filename:
                            continue

                        decoded_name, encoding = decode_header(filename)[0]
                        if isinstance(decoded_name, bytes):
                            filename = decoded_name.decode(encoding or "utf-8", errors="ignore")
                        else:
                            filename = str(decoded_name)

                        ext = os.path.splitext(filename)[1].lower()
                        if ext not in ALLOWED_EXTS:
                            continue

                        file_data = part.get_payload(decode=True)
                        if not file_data:
                            continue

                        content_id = part.get("Content-ID")
                        is_inline = "inline" in (part.get("Content-Disposition") or "").lower()
                        if (content_id or is_inline) and ext in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
                            logger.debug("Skipping inline image: %s", filename)
                            continue

                        if len(file_data) < MIN_FILE_SIZE and ext not in (".xml",):
                            logger.debug("Skipping tiny file (%d B): %s", len(file_data), filename)
                            continue

                        if SKIP_FILENAME_RE.match(filename):
                            logger.debug("Skipping signature image: %s", filename)
                            continue

                        try:
                            from django.db import transaction
                            with transaction.atomic():
                                batch = ImportBatch.objects.create(
                                    company=company,
                                    file_type=ALLOWED_EXTS[ext],
                                    status="pending",
                                    status_message="Primljeno putem emaila",
                                    original_filename=filename[:255],
                                )
                                safe_name = filename.replace(" ", "_")
                                batch.file.save(safe_name, ContentFile(file_data), save=True)
                            process_import_batch.delay(batch.pk)
                        except Exception as db_exc:
                            logger.error(
                                "Email Rampa [%s]: DB greska za privitak '%s': %s",
                                mb_user, filename, db_exc
                            )
                            try:
                                FailedImport.objects.create(
                                    company=company,
                                    email_subject=subject[:500],
                                    email_sender=sender[:255],
                                    filename=filename[:255],
                                    error_message=str(db_exc),
                                    mailbox_user=mb_user[:255],
                                )
                            except Exception:
                                pass
                            continue
                        attachments_found += 1
                        logger.info(
                            "Email Rampa [%s -> %s]: '%s' -> Batch #%d (%s)",
                            mb_user, company.name, filename, batch.pk, ALLOWED_EXTS[ext]
                        )

                    count += attachments_found
                    mail_conn.store(num, "+FLAGS", "\\Seen")
                    if db_obj and attachments_found:
                        db_obj.total_imported += attachments_found
                        db_obj.save(update_fields=["total_imported"])

            mail_conn.close()
            mail_conn.logout()
            total_count += count

            now = timezone.now()
            for mb_entry in email_company_map.values():
                obj = mb_entry["db_obj"]
                if obj and base_email(obj.email_address) == login_key:
                    obj.last_check = now
                    obj.last_error = ""
                    obj.save(update_fields=["last_check", "last_error"])

            results.append("{}: {} privitaka".format(mb_user, count))

        except imaplib.IMAP4.error as e:
            logger.error("IMAP greska za %s: %s", mb_user, e)
            results.append("{}: IMAP GRESKA - {}".format(mb_user, e))
            if login["default_db_obj"]:
                login["default_db_obj"].last_check = timezone.now()
                login["default_db_obj"].last_error = str(e)
                login["default_db_obj"].save(update_fields=["last_check", "last_error"])
        except Exception as e:
            logger.exception("Email Rampa kriticna greska za %s", mb_user)
            results.append("{}: GRESKA - {}".format(mb_user, e))
            if login["default_db_obj"]:
                login["default_db_obj"].last_check = timezone.now()
                login["default_db_obj"].last_error = str(e)
                login["default_db_obj"].save(update_fields=["last_check", "last_error"])

    summary = "Email Rampa: {} ukupno. ".format(total_count) + " | ".join(results)
    logger.info(summary)
    return summary


@shared_task
def detect_stale_batches():
    """Detect ImportBatch stuck in pending/processing > 5 min."""
    from django.utils import timezone
    from datetime import timedelta
    from smart_import.models import ImportBatch

    cutoff = timezone.now() - timedelta(minutes=5)
    stale = ImportBatch.objects.filter(
        status__in=["pending", "processing"],
        created_at__lt=cutoff,
    )
    count = stale.count()
    if count == 0:
        return "Nema zaostalih batcheva"

    for batch in stale:
        logger.warning(
            "Stale batch #%d (%s) kreiran %s, status=%s -> error",
            batch.pk, batch.file_type, batch.created_at, batch.status,
        )
        batch.status = "error"
        batch.error_msg = "Obrada je trajala predugo. Molimo pokusajte ponovo ili prijavite problem."
        batch.status_message = "Timeout - pokusajte ponovo"
        batch.save(update_fields=["status", "error_msg", "status_message"])
        _release_lock(batch.pk)

    return "{} zaostalih batcheva oznaceno kao error".format(count)
