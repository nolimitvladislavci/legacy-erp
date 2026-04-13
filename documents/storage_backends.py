"""
Document Storage Backends — 3 opcije za spremanje datoteka.
1. LOCAL  — /media/arhiva/ na serveru
2. CLOUD  — Backblaze B2 / AWS S3
3. DATABASE — PostgreSQL BinaryField

Svaka firma moze imati svoju konfiguraciju.
Auto-kompresija slika prije spremanja.
"""

import hashlib
import io
import logging
import os
import uuid
from datetime import datetime

from django.conf import settings
from django.db import DatabaseError, IntegrityError

logger = logging.getLogger(__name__)

# Register HEIC/HEIF opener for iPhone photos
try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:
    pass

DB_MAX_SIZE = 500 * 1024
IMAGE_TARGET_SIZE = 200 * 1024


def compress_image(file_bytes, filename, max_bytes=IMAGE_TARGET_SIZE):
    """Kompresira sliku na target velicinu. Vraca (bytes, content_type)."""
    try:
        from PIL import Image

        img = Image.open(io.BytesIO(file_bytes))

        try:
            from PIL import ExifTags

            for orientation in ExifTags.TAGS:
                if ExifTags.TAGS[orientation] == "Orientation":
                    break
            exif = img._getexif()
            if exif and orientation in exif:
                if exif[orientation] == 3:
                    img = img.rotate(180, expand=True)
                elif exif[orientation] == 6:
                    img = img.rotate(270, expand=True)
                elif exif[orientation] == 8:
                    img = img.rotate(90, expand=True)
        except ImportError:
            pass

        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        max_dim = 1920
        if max(img.size) > max_dim:
            img.thumbnail((max_dim, max_dim), Image.LANCZOS)

        quality_lo, quality_hi = 20, 85
        best_buf = None
        for _ in range(6):
            quality = (quality_lo + quality_hi) // 2
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=quality, optimize=True)
            size = buf.tell()
            if size <= max_bytes:
                best_buf = buf
                quality_lo = quality + 1
            else:
                quality_hi = quality - 1

        if best_buf is None:
            best_buf = io.BytesIO()
            img.save(best_buf, format="JPEG", quality=20, optimize=True)

        best_buf.seek(0)
        return best_buf.read(), "image/jpeg"

    except ImportError:
        logger.warning("Pillow not installed, skipping image compression")
        return file_bytes, "application/octet-stream"
    except (FileNotFoundError, PermissionError, IOError) as e:
        logger.warning("Image compression failed: %s", e)
        return file_bytes, "application/octet-stream"


def generate_storage_path(company_id, source_type, filename):
    now = datetime.now()
    ext = os.path.splitext(filename)[1].lower() if filename else ".bin"
    unique = uuid.uuid4().hex[:12]
    return f"arhiva/{company_id}/{now.year}/{now.month:02d}/{unique}{ext}"


def get_file_hash(file_bytes):
    return hashlib.sha256(file_bytes).hexdigest()


class LocalStorageBackend:
    """Sprema u MEDIA_ROOT/arhiva/..."""

    def save(self, file_bytes, filename, company_id, source_type, **kwargs):
        rel_path = generate_storage_path(company_id, source_type, filename)
        full_path = os.path.join(settings.MEDIA_ROOT, rel_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "wb") as f:
            f.write(file_bytes)
        logger.info("LOCAL saved: %s (%d bytes)", rel_path, len(file_bytes))
        return {
            "backend": "local",
            "path": rel_path,
            "url": f"{settings.MEDIA_URL}{rel_path}",
            "size": len(file_bytes),
            "hash": get_file_hash(file_bytes),
        }

    def retrieve(self, path):
        full_path = os.path.join(settings.MEDIA_ROOT, path)
        if not os.path.exists(full_path):
            return None
        with open(full_path, "rb") as f:
            return f.read()

    def delete(self, path):
        full_path = os.path.join(settings.MEDIA_ROOT, path)
        if os.path.exists(full_path):
            os.remove(full_path)
            return True
        return False

    def exists(self, path):
        return os.path.exists(os.path.join(settings.MEDIA_ROOT, path))


class CloudStorageBackend:
    """S3-kompatibilan storage (Backblaze B2 ili AWS S3)."""

    def __init__(self):
        self.bucket_name = os.environ.get("STORAGE_BUCKET", "")
        self.key_id = os.environ.get("STORAGE_KEY_ID", "")
        self.app_key = os.environ.get("STORAGE_APP_KEY", "")
        self.endpoint = os.environ.get("STORAGE_ENDPOINT", "")
        self.region = os.environ.get("STORAGE_REGION", "us-west-004")
        self._client = None

    @property
    def client(self):
        if self._client is None:
            import boto3

            kwargs = {
                "service_name": "s3",
                "aws_access_key_id": self.key_id,
                "aws_secret_access_key": self.app_key,
                "region_name": self.region,
            }
            if self.endpoint:
                kwargs["endpoint_url"] = self.endpoint
            self._client = boto3.client(**kwargs)
        return self._client

    @property
    def is_configured(self):
        return bool(self.bucket_name and self.key_id and self.app_key)

    def save(self, file_bytes, filename, company_id, source_type, content_type="application/octet-stream", **kwargs):
        if not self.is_configured:
            raise RuntimeError(
                "Cloud storage not configured. Set STORAGE_BUCKET, STORAGE_KEY_ID, STORAGE_APP_KEY in .env"
            )

        rel_path = generate_storage_path(company_id, source_type, filename)
        self.client.put_object(
            Bucket=self.bucket_name,
            Key=rel_path,
            Body=file_bytes,
            ContentType=content_type,
        )
        if self.endpoint:
            url = f"{self.endpoint}/{self.bucket_name}/{rel_path}"
        else:
            url = f"https://{self.bucket_name}.s3.amazonaws.com/{rel_path}"

        logger.info("CLOUD saved: %s (%d bytes)", rel_path, len(file_bytes))
        return {
            "backend": "cloud",
            "path": rel_path,
            "url": url,
            "size": len(file_bytes),
            "hash": get_file_hash(file_bytes),
        }

    def retrieve(self, path):
        if not self.is_configured:
            return None
        try:
            resp = self.client.get_object(Bucket=self.bucket_name, Key=path)
            return resp["Body"].read()
        except IOError as e:
            logger.error("Cloud retrieve error: %s", e)
            return None

    def delete(self, path):
        if not self.is_configured:
            return False
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=path)
            return True
        except Exception:
            return False

    def exists(self, path):
        if not self.is_configured:
            return False
        try:
            self.client.head_object(Bucket=self.bucket_name, Key=path)
            return True
        except Exception:
            return False


class DatabaseStorageBackend:
    """Sprema u DocumentBlob model (PostgreSQL bytea)."""

    def save(self, file_bytes, filename, company_id, source_type, content_type="application/octet-stream", **kwargs):
        from .models import DocumentBlob

        if len(file_bytes) > DB_MAX_SIZE:
            raise ValueError(
                "Datoteka prevelika za DB storage (%dKB > %dKB). "
                "Koristite Local ili Cloud backend." % (len(file_bytes) // 1024, DB_MAX_SIZE // 1024)
            )

        file_hash = get_file_hash(file_bytes)

        existing = DocumentBlob.objects.filter(file_hash=file_hash, company_id=company_id).first()
        if existing:
            logger.info("DB dedup hit: %s", file_hash[:16])
            return {
                "backend": "database",
                "path": "db://%s" % existing.id,
                "url": "/documents/blob/%s/" % existing.id,
                "size": existing.file_size,
                "hash": file_hash,
                "blob_id": str(existing.id),
            }

        blob = DocumentBlob.objects.create(
            company_id=company_id,
            filename=filename or "unknown",
            content_type=content_type,
            file_data=file_bytes,
            file_size=len(file_bytes),
            file_hash=file_hash,
            source_type=source_type,
        )
        logger.info("DB saved: %s (%d bytes)", blob.id, len(file_bytes))
        return {
            "backend": "database",
            "path": "db://%s" % blob.id,
            "url": "/documents/blob/%s/" % blob.id,
            "size": len(file_bytes),
            "hash": file_hash,
            "blob_id": str(blob.id),
        }

    def retrieve(self, path):
        from .models import DocumentBlob

        blob_id = path.replace("db://", "")
        try:
            blob = DocumentBlob.objects.get(id=blob_id)
            return bytes(blob.file_data)
        except DocumentBlob.DoesNotExist:
            return None

    def delete(self, path):
        from .models import DocumentBlob

        blob_id = path.replace("db://", "")
        try:
            DocumentBlob.objects.filter(id=blob_id).delete()
            return True
        except (IntegrityError, DatabaseError):
            return False

    def exists(self, path):
        from .models import DocumentBlob

        blob_id = path.replace("db://", "")
        return DocumentBlob.objects.filter(id=blob_id).exists()


BACKENDS = {
    "local": LocalStorageBackend,
    "cloud": CloudStorageBackend,
    "database": DatabaseStorageBackend,
}


def get_backend(backend_name=None):
    if backend_name is None:
        backend_name = os.environ.get("STORAGE_BACKEND", "local")
    cls = BACKENDS.get(backend_name)
    if cls is None:
        raise ValueError("Unknown storage backend: %s" % backend_name)
    return cls()


def store_document(
    file_bytes, filename, company_id, source_type, backend_name=None, auto_compress=True, content_type=None
):
    """
    Glavni entry point za spremanje dokumenata.

    from documents.storage_backends import store_document
    result = store_document(
        file_bytes=uploaded_file.read(),
        filename='racun-001.jpg',
        company_id=company.id,
        source_type='invoice_in',
        backend_name='cloud',  # ili 'local', 'database'
    )
    """
    if not content_type:
        ext = os.path.splitext(filename)[1].lower() if filename else ""
        content_type = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".pdf": "application/pdf",
            ".heic": "image/heic",
            ".heif": "image/heif",
            ".xml": "application/xml",
            ".json": "application/json",
        }.get(ext, "application/octet-stream")

    is_image = content_type.startswith("image/")
    if auto_compress and is_image and len(file_bytes) > IMAGE_TARGET_SIZE:
        original_size = len(file_bytes)
        file_bytes, content_type = compress_image(file_bytes, filename)
        logger.info("Compressed %s: %dKB -> %dKB", filename, original_size // 1024, len(file_bytes) // 1024)

    backend = get_backend(backend_name)
    result = backend.save(
        file_bytes=file_bytes,
        filename=filename,
        company_id=company_id,
        source_type=source_type,
        content_type=content_type,
    )
    result["content_type"] = content_type
    result["original_filename"] = filename

    # ── DUAL-WRITE: uvijek spremi i lokalno kao backup ──
    actual_backend = backend_name or os.environ.get("STORAGE_BACKEND", "local")
    if actual_backend != "local":
        try:
            local = LocalStorageBackend()
            local_result = local.save(
                file_bytes=file_bytes,
                filename=filename,
                company_id=company_id,
                source_type=source_type,
            )
            result["local_backup_path"] = local_result["path"]
            logger.info("Dual-write: local backup at %s", local_result["path"])
        except Exception as e:
            logger.warning("Dual-write local backup failed: %s", e)

    return result


def retrieve_document(path, backend_name=None):
    """Dohvaca fajl — pokusava primarni backend, fallback na local."""
    if path.startswith("db://"):
        backend_name = "database"
    backend = get_backend(backend_name)
    data = backend.retrieve(path)

    # Fallback: ako cloud ne uspije, pokusaj lokalno
    if data is None and backend_name not in (None, "local"):
        local = LocalStorageBackend()
        data = local.retrieve(path)
        if data:
            logger.info("Cloud retrieve failed, served from local backup: %s", path)

    return data


def migrate_existing_files():
    """
    Skenira postojece media/ fajlove i kreira ArhivaEntry zapise.
    Pokreni jednom: python manage.py shell -c "from documents.storage_backends import migrate_existing_files; migrate_existing_files()"
    """
    import os
    from datetime import datetime

    from companies.models import Company

    # Lazy imports to avoid circular
    from documents.models import ArhivaEntry

    media_root = settings.MEDIA_ROOT
    migrated = 0
    skipped = 0

    # Mapiranje media direktorija na source_type
    DIR_MAP = {
        "documents": "document",
        "smart_import": "invoice_in",
        "fiscal": "fiscal_cert",
        "leads": "document",
        "dossier": "document",
        "inventory": "document",
    }

    # Skip ove direktorije (nisu dokumenti)
    SKIP_DIRS = {"company_logos", "website", "site_photos", "arhiva", "certs"}

    companies = {str(c.id): c for c in Company.objects.all()}
    default_company = Company.objects.first()

    for root, dirs, files in os.walk(media_root):
        rel_root = os.path.relpath(root, media_root)
        top_dir = rel_root.split(os.sep)[0] if rel_root != "." else ""

        if top_dir in SKIP_DIRS:
            continue

        source_type = DIR_MAP.get(top_dir, "document")

        for fname in files:
            full_path = os.path.join(root, fname)
            rel_path = os.path.relpath(full_path, media_root)

            # Skip ako vec postoji
            if ArhivaEntry.objects.filter(file_path=rel_path).exists():
                skipped += 1
                continue

            # Pokusaj naci company iz path-a
            company = default_company
            for cid, co in companies.items():
                if cid in rel_path:
                    company = co
                    break

            ext = os.path.splitext(fname)[1].lower()
            stat = os.stat(full_path)
            file_date = datetime.fromtimestamp(stat.st_mtime).date()

            ArhivaEntry.objects.create(
                company=company,
                source_type=source_type,
                source_id="migrated:%s" % rel_path,
                doc_number=fname,
                partner_name="",
                amount=0,
                currency="EUR",
                doc_date=file_date,
                file_path=rel_path,
                has_pdf=(ext == ".pdf"),
                has_xml=(ext == ".xml"),
                has_image=(ext in (".jpg", ".jpeg", ".png", ".gif", ".webp")),
                session_key="",
            )
            migrated += 1

    print("Migracija zavrsena: %d novih zapisa, %d preskocenih (vec postoje)" % (migrated, skipped))
    return migrated
