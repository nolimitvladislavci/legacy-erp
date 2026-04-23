"""
DocumentProcessor — Enterprise service layer za scan batch pipeline.

State Machine: collecting -> processing -> grouping -> ready -> archiving -> done
Principi: nema sleep, atomic transactions, graceful degradation
"""

import base64
import io
import json
import logging
import os
import re
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation

from django.db import transaction

logger = logging.getLogger(__name__)


class BatchState:
    COLLECTING = "collecting"
    PROCESSING = "processing"
    GROUPING = "grouping"
    READY = "ready"
    ARCHIVING = "archiving"
    DONE = "done"
    ERROR = "error"

    TRANSITIONS = {
        "collecting": {"processing"},
        "processing": {"grouping", "error", "processing"},
        "grouping": {"ready", "error"},
        "ready": {"archiving", "collecting"},
        "archiving": {"done", "error"},
        "error": {"collecting", "processing"},
    }

    @classmethod
    def can_transition(cls, frm, to):
        return to in cls.TRANSITIONS.get(frm, set())


class DocumentProcessor:
    GEMINI_MODEL = "gemini-2.5-flash"
    BATCH_SIZE = 10
    RATE_LIMIT_SECONDS = 62

    EXTRACTION_PROMPT = (
        "Analiziraj ovu sliku racuna. Vrati SAMO JSON:\n"
        '{"invoice_number":"","issue_date":"DD.MM.YYYY",'
        '"seller":{"name":"","oib":"","address":""},'
        '"items":[{"description":"","quantity":1,'
        '"unit_price":0.00,"vat_rate":25,"line_total":0.00}],'
        '"subtotal":0.00,"vat_amount":0.00,"total":0.00,'
        '"currency":"EUR","payment_method":"",'
        '"zki":"","jir":"",'
        '"is_fuel":false,"is_cash_receipt":false,'
        '"doc_type":"invoice_in"}\n'
        'Gotovinski bon -> is_cash_receipt:true, doc_type:"pos_receipt".\n'
        "Gorivo -> is_fuel:true. Decimale. NIKAD ne izmisljaj."
    )

    @staticmethod
    def get_gemini_client():
        key = os.environ.get("GEMINI_API_KEY", "")
        if not key:
            return None
        try:
            from google import genai

            return genai.Client(api_key=key)
        except ImportError:
            return None

    @staticmethod
    def get_claude_client():
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not key:
            return None
        try:
            import anthropic

            return anthropic.Anthropic(api_key=key)
        except ImportError:
            return None

    @staticmethod
    def prepare_image(image_path):
        try:
            from PIL import ExifTags, Image, ImageEnhance

            img = Image.open(image_path)
            try:
                for k in ExifTags.TAGS:
                    if ExifTags.TAGS[k] == "Orientation":
                        break
                exif = img._getexif()
                if exif and k in exif:
                    r = {3: 180, 6: 270, 8: 90}.get(exif[k])
                    if r:
                        img = img.rotate(r, expand=True)
            except KeyError:
                pass
            if max(img.size) > 2048:
                img.thumbnail((2048, 2048), Image.LANCZOS)
            img = ImageEnhance.Contrast(img).enhance(1.3)
            img = ImageEnhance.Sharpness(img).enhance(1.5)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=90)
            buf.seek(0)
            return base64.b64encode(buf.read()).decode()
        except ImportError:
            with open(image_path, "rb") as f:
                return base64.b64encode(f.read()).decode()

    @classmethod
    def extract_with_gemini(cls, client, b64):
        try:
            resp = client.models.generate_content(
                model=cls.GEMINI_MODEL,
                contents=[
                    {
                        "role": "user",
                        "parts": [
                            {"text": cls.EXTRACTION_PROMPT},
                            {"inline_data": {"mime_type": "image/jpeg", "data": b64}},
                        ],
                    }
                ],
            )
            text = resp.text.strip()
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            return json.loads(text)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("Gemini failed: %s", e)
            return None

    @classmethod
    def extract_with_claude(cls, client, b64):
        try:
            resp = client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=600,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
                            {"type": "text", "text": cls.EXTRACTION_PROMPT},
                        ],
                    }
                ],
            )
            text = resp.content[0].text.strip()
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            return json.loads(text)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("Claude failed: %s", e)
            return None

    @classmethod
    def process_chunk(cls, batch_id, offset=0):
        """Obradi BATCH_SIZE slika. Nema sleep. Vraca (ok, err, more)."""
        from documents.models import ScanBatch

        try:
            batch = ScanBatch.objects.get(pk=batch_id)
        except ScanBatch.DoesNotExist:
            return 0, 0, False

        imgs = list(batch.images.order_by("order")[offset : offset + cls.BATCH_SIZE])
        if not imgs:
            return 0, 0, False

        total = batch.images.count()
        chunk = (offset // cls.BATCH_SIZE) + 1
        chunks = (total + cls.BATCH_SIZE - 1) // cls.BATCH_SIZE

        cls._set_status(batch, BatchState.PROCESSING, "Grupa %d/%d — %d slika..." % (chunk, chunks, len(imgs)))

        gemini = cls.get_gemini_client()
        claude = cls.get_claude_client() if not gemini else None

        if not gemini and not claude:
            cls._set_status(batch, BatchState.ERROR, "Nema AI kljuca (GEMINI ni ANTHROPIC)")
            return 0, 0, False

        ok = err = 0
        for img in imgs:
            try:
                path = img.image.path
                if not os.path.isfile(path):
                    cls._fail_image(img, "Datoteka ne postoji")
                    err += 1
                    continue
                b64 = cls.prepare_image(path)
                data = None
                if gemini:
                    data = cls.extract_with_gemini(gemini, b64)
                if data is None:
                    c = claude or cls.get_claude_client()
                    if c:
                        data = cls.extract_with_claude(c, b64)
                if data:
                    img.extracted_data = data
                    img.extracted_text = json.dumps(data, ensure_ascii=False)[:500]
                    img.ai_confidence = 0.9 if gemini else 0.85
                else:
                    img.extracted_data = {}
                    img.ai_confidence = 0.0
                    err += 1
                img.save(update_fields=["extracted_data", "extracted_text", "ai_confidence"])
                ok += 1
            except (TypeError, ValueError) as e:
                logger.error("Img %s: %s", img.pk, e)
                cls._fail_image(img, str(e)[:200])
                err += 1

        has_more = (offset + cls.BATCH_SIZE) < total
        done = offset + ok + err
        engine = "gemini" if gemini else "claude"
        cls._set_status(batch, BatchState.PROCESSING, "Obradeno %d/%d (%s, %d gr.)" % (done, total, engine, err))
        return ok, err, has_more

    @classmethod
    def group_documents(cls, batch_id):
        from documents.models import ScanBatch, ScanBatchImage

        batch = ScanBatch.objects.get(pk=batch_id)
        cls._set_status(batch, BatchState.GROUPING, "Grupiram...")

        imgs = list(batch.images.order_by("order"))
        groups, cur, cur_key = [], [], None

        for img in imgs:
            d = img.extracted_data or {}
            seller = (d.get("seller", {}).get("name", "") or "").strip().lower()[:20]
            dt = d.get("issue_date", "")
            key = (seller, dt) if seller else None

            if d and key and cur_key and key == cur_key:
                cur.append(img)
                continue
            if cur:
                groups.append(cur)
            cur = [img]
            cur_key = key if d else None
        if cur:
            groups.append(cur)

        with transaction.atomic():
            for gi, grp in enumerate(groups, 1):
                for pi, img in enumerate(grp, 1):
                    ScanBatchImage.objects.filter(pk=img.pk).update(document_group=gi, page_in_group=pi)
            batch.status = BatchState.READY
            batch.total_documents = len(groups)
            batch.error_message = "%d dok. iz %d slika" % (len(groups), len(imgs))
            batch.save(update_fields=["status", "total_documents", "error_message"])

        return len(groups)

    @classmethod
    def archive_batch(cls, batch_id, user_id=None):
        """Atomic. Sve ili nista."""
        from documents.models import ArhivaEntry, ScanBatch
        from documents.tasks import generate_ai_proposal

        batch = ScanBatch.objects.get(pk=batch_id)
        if batch.status != BatchState.READY:
            raise ValueError("Not READY")

        company = batch.company
        user = None
        if user_id:
            from django.contrib.auth import get_user_model

            user = get_user_model().objects.filter(pk=user_id).first()

        grps = defaultdict(list)
        for img in batch.images.filter(document_group__isnull=False).order_by("document_group", "page_in_group"):
            grps[img.document_group].append(img)

        entries = []
        with transaction.atomic():
            cls._set_status(batch, BatchState.ARCHIVING, "Arhiviram %d dok..." % len(grps))
            for gn, gimgs in sorted(grps.items()):
                first = gimgs[0]
                d = first.extracted_data or {}
                e = ArhivaEntry(
                    company=company,
                    source_type=cls._src_type(d),
                    source_id="scan:%d:g:%d" % (batch.pk, gn),
                    doc_number=d.get("invoice_number", "SCAN-%d-%d" % (batch.pk, gn)),
                    partner_name=d.get("seller", {}).get("name", ""),
                    partner=cls._resolve_partner(d.get("seller", {}).get("name", ""), company),
                    amount=cls._dec(d.get("total", 0)),
                    currency=d.get("currency", "EUR"),
                    doc_date=cls._dt(d.get("issue_date", "")),
                    file_path=first.image.name if first.image else "",
                    has_image=True,
                    zki=(d.get("zki", "") or "")[:64],
                    jir=(d.get("jir", "") or "")[:64],
                    archived_by=user or batch.created_by,
                    session_key="scan_%d" % batch.pk,
                )
                e.save()
                if e.pk:
                    entries.append(e)
            batch.status = BatchState.DONE
            batch.total_documents = len(entries)
            batch.error_message = "%d arhivirano" % len(entries)
            batch.save(update_fields=["status", "total_documents", "error_message"])

        ai = 0
        for e in entries:
            try:
                generate_ai_proposal.apply_async(args=[e.pk], countdown=5)
                ai += 1
            except Exception:
                pass

        cls._notify(batch, len(entries), ai)
        return len(entries), ai

    @classmethod
    def recover_failed(cls, batch_id):
        from documents.models import ScanBatch, ScanBatchImage

        batch = ScanBatch.objects.get(pk=batch_id)
        if batch.status not in (BatchState.ERROR, BatchState.PROCESSING):
            return False
        with transaction.atomic():
            ScanBatchImage.objects.filter(batch=batch, ai_confidence__isnull=True).update(
                extracted_data=None, extracted_text="", document_group=None, page_in_group=None
            )
            batch.status = BatchState.COLLECTING
            batch.error_message = "Resetiran"
            batch.save(update_fields=["status", "error_message"])
        return True

    @classmethod
    def get_summary(cls, batch_id):
        from documents.models import ScanBatch

        batch = ScanBatch.objects.get(pk=batch_id)
        imgs = batch.images.order_by("order")
        r = {
            "status": batch.status,
            "total_images": batch.total_images,
            "total_documents": batch.total_documents,
            "error_message": batch.error_message,
            "processed": imgs.exclude(ai_confidence__isnull=True).count(),
            "failed": imgs.filter(ai_confidence=0.0).count(),
            "images": [
                {
                    "id": i.pk,
                    "order": i.order,
                    "group": i.document_group,
                    "page": i.page_in_group,
                    "confidence": i.ai_confidence,
                    "has_data": bool(i.extracted_data),
                }
                for i in imgs
            ],
        }
        if batch.status == BatchState.READY:
            gs = {}
            for i in imgs:
                g = i.document_group
                if g and g not in gs:
                    ed = i.extracted_data or {}
                    gs[g] = {
                        "group": g,
                        "seller": ed.get("seller", {}).get("name", "?"),
                        "total": ed.get("total", 0),
                        "currency": ed.get("currency", "EUR"),
                        "date": ed.get("issue_date", ""),
                        "invoice_number": ed.get("invoice_number", ""),
                        "is_fuel": ed.get("is_fuel", False),
                        "is_cash": ed.get("is_cash_receipt", False),
                        "pages": 0,
                    }
                if g and g in gs:
                    gs[g]["pages"] += 1
            r["document_groups"] = list(gs.values())
        return r

    # ── private ──

    @staticmethod
    def _set_status(batch, st, msg=""):
        batch.status = st
        if msg:
            batch.error_message = msg
        batch.save(update_fields=["status", "error_message"])

    @staticmethod
    def _fail_image(img, reason):
        img.extracted_data = {"_error": reason}
        img.ai_confidence = 0.0
        img.extracted_text = "[FAIL] %s" % reason[:200]
        img.save(update_fields=["extracted_data", "ai_confidence", "extracted_text"])

    @staticmethod
    def _src_type(d):
        if d.get("is_cash_receipt"):
            return "pos_receipt"
        if d.get("doc_type") == "invoice_in":
            return "invoice_in"
        return "document"

    @staticmethod
    def _resolve_partner(name, company):
        if not name or not name.strip():
            return None
        from partners.models import Partner

        n = name.strip()
        p = Partner.objects.filter(company=company, is_active=True, name__iexact=n).first()
        if p:
            return p
        p = Partner.objects.filter(company=company, is_active=True, name__istartswith=n[:10]).first()
        if p:
            return p
        words = [w for w in n.split() if len(w) > 3]
        if words:
            longest = max(words, key=len)
            p = Partner.objects.filter(company=company, is_active=True, name__icontains=longest).first()
            if p:
                return p
        tokens = set(n.lower().split())
        if tokens:
            best, bs = None, 0
            for c in Partner.objects.filter(company=company, is_active=True)[:500]:
                ct = set(c.name.lower().split())
                if ct:
                    ov = len(tokens & ct) / max(len(tokens), len(ct))
                    if ov > bs:
                        bs = ov
                        best = c
            if best and bs >= 0.5:
                return best
        return None

    @staticmethod
    def _dec(v):
        try:
            if isinstance(v, str):
                v = v.replace(",", ".")
            return Decimal(str(v or 0))
        except (InvalidOperation, ValueError):
            return Decimal("0")

    @staticmethod
    def _dt(raw):
        if not raw:
            return date.today()
        try:
            parts = raw.replace("/", ".").replace("-", ".").split(".")
            if len(parts) == 3:
                if len(parts[0]) == 4:
                    return date(int(parts[0]), int(parts[1]), int(parts[2]))
                return date(int(parts[2]), int(parts[1]), int(parts[0]))
        except (ValueError, IndexError):
            pass
        return date.today()

    @staticmethod
    def _notify(batch, created, ai_queued):
        try:
            from notifications.services import notify

            notify(
                recipient=batch.created_by,
                notification_type="success",
                title="Batch arhiviran",
                message="%d dok. spremljeno, %d AI prijedloga." % (created, ai_queued),
                url="/hr/documents/arhiva/",
                company=batch.company,
            )
        except ImportError as e:
            logger.warning("Notify failed: %s", e)
