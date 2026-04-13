"""
Global Photo Registry — archive_photo()

Central service for registering photos from ANY app into ArhivaEntry.
Handles: EXIF GPS extraction, thumbnail generation, integrity hash, audit log.

Usage from any app:
    from documents.photo_registry import archive_photo
    archive_photo(
        company=company,
        file_field=instance.photo_before,      # Django FieldFile
        source_type='site_photo',
        source_app='stolarija',
        source_model='Measurement',
        source_object_id=instance.pk,
        captured_by=user,
        tags=['teren', 'mjerenje'],
        latitude=45.123,                       # optional, auto-extracted from EXIF
        longitude=15.456,
    )
"""

import hashlib
import logging
import os
from datetime import datetime

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger("documents")

# Thumbnail settings
THUMB_MAX_SIZE = 200
THUMB_QUALITY = 75
THUMB_DIR = "arhiva/thumbs"


def archive_photo(
    company,
    file_field=None,
    file_path=None,
    source_type="site_photo",
    source_app="",
    source_model="",
    source_object_id=None,
    captured_by=None,
    tags=None,
    latitude=None,
    longitude=None,
    address="",
    content_category="photo",
    doc_number="",
    doc_date=None,
    partner_name="",
):
    """
    Register a photo/file in the global ArhivaEntry archive.

    Args:
        company: Company instance (required)
        file_field: Django FieldFile (e.g., instance.photo_before) — preferred
        file_path: str path relative to MEDIA_ROOT — fallback if no file_field
        source_type: ArhivaEntry SOURCE_TYPE value
        source_app: app label (e.g., 'stolarija')
        source_model: model name (e.g., 'Measurement')
        source_object_id: PK of source object
        captured_by: User instance
        tags: list of strings
        latitude/longitude: GPS coords (auto-extracted from EXIF if None)
        address: text address
        content_category: 'photo'|'document'|'scan'|'signature'|'certificate'|'receipt'
        doc_number: optional document number for archive
        doc_date: optional date

    Returns:
        ArhivaEntry instance or None if duplicate/error
    """
    from documents.models import ArhivaEntry

    if tags is None:
        tags = []

    # Resolve file path
    resolved_path = ""
    if file_field and hasattr(file_field, "name") and file_field.name:
        resolved_path = file_field.name
    elif file_path:
        resolved_path = file_path

    if not resolved_path:
        return None

    # Check for duplicate (same company + source + file)
    existing = ArhivaEntry.objects.filter(
        company=company,
        source_app=source_app,
        source_model=source_model,
        source_object_id=source_object_id,
        file_path=resolved_path,
    ).first()
    if existing:
        return existing

    abs_path = os.path.join(settings.MEDIA_ROOT, resolved_path) if not os.path.isabs(resolved_path) else resolved_path
    if os.path.exists(abs_path):
        _compute_file_hash(abs_path)  # verify file readable + populate cache

        # Try EXIF GPS extraction if coords not provided
        if latitude is None or longitude is None:
            exif_data = _extract_exif(abs_path)
            if exif_data.get("lat") and exif_data.get("lng"):
                latitude = exif_data["lat"]
                longitude = exif_data["lng"]

        # Generate thumbnail
        thumbnail_path = _generate_thumbnail(abs_path, resolved_path)
    else:
        thumbnail_path = ""

    # Determine has_image/has_pdf
    ext = os.path.splitext(resolved_path)[1].lower()
    has_image = ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff")
    has_pdf = ext == ".pdf"

    # Create archive entry
    now = timezone.now()
    entry = ArhivaEntry(
        company=company,
        source_type=source_type,
        source_id=f"{source_app}.{source_model}:{source_object_id}" if source_object_id else "",
        doc_number=doc_number or f"{source_app.upper()}-{source_model}-{source_object_id or ''}",
        doc_date=doc_date or now.date(),
        partner_name=partner_name,
        file_path=resolved_path,
        has_image=has_image,
        has_pdf=has_pdf,
        # Photo registry fields
        latitude=latitude,
        longitude=longitude,
        address=address,
        source_app=source_app,
        source_model=source_model,
        source_object_id=source_object_id,
        tags=tags,
        thumbnail_path=thumbnail_path,
        captured_at=now,
        captured_by=captured_by,
        content_category=content_category,
        # Audit
        archived_by=captured_by,
    )

    # Auto-match partner by address
    if address and company:
        try:
            from partners.models import Partner

            partner = Partner.objects.filter(
                company=company,
                address__icontains=address[:30],
            ).first()
            if partner:
                entry.partner = partner
                entry.partner_name = str(partner)[:200]
        except Exception:
            pass

    try:
        entry.save()
        logger.info(
            "archive_photo: %s.%s:%s → %s",
            source_app,
            source_model,
            source_object_id,
            entry.archive_number,
        )
        return entry
    except Exception:
        logger.exception("archive_photo failed for %s", resolved_path)
        return None


def _compute_file_hash(abs_path):
    """SHA-256 of file contents."""
    h = hashlib.sha256()
    with open(abs_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _extract_exif(abs_path):
    """Extract GPS coordinates and datetime from EXIF data."""
    result = {"lat": None, "lng": None, "datetime": None}
    try:
        from PIL import Image
        from PIL.ExifTags import GPSTAGS, TAGS

        img = Image.open(abs_path)
        exif_data = img._getexif()
        if not exif_data:
            return result

        # DateTime
        for tag_id, value in exif_data.items():
            tag = TAGS.get(tag_id, tag_id)
            if tag == "DateTimeOriginal":
                try:
                    result["datetime"] = datetime.strptime(value, "%Y:%m:%d %H:%M:%S")
                except (ValueError, TypeError):
                    pass

        # GPS
        gps_info = {}
        for tag_id, value in exif_data.items():
            tag = TAGS.get(tag_id, tag_id)
            if tag == "GPSInfo":
                for gps_tag_id, gps_value in value.items():
                    gps_tag = GPSTAGS.get(gps_tag_id, gps_tag_id)
                    gps_info[gps_tag] = gps_value

        if "GPSLatitude" in gps_info and "GPSLongitude" in gps_info:
            lat = _gps_to_decimal(gps_info["GPSLatitude"], gps_info.get("GPSLatitudeRef", "N"))
            lng = _gps_to_decimal(gps_info["GPSLongitude"], gps_info.get("GPSLongitudeRef", "E"))
            if lat and lng:
                result["lat"] = lat
                result["lng"] = lng

    except Exception:
        pass
    return result


def _gps_to_decimal(gps_coords, ref):
    """Convert GPS EXIF coords to decimal degrees."""
    try:
        d = float(gps_coords[0])
        m = float(gps_coords[1])
        s = float(gps_coords[2])
        decimal = d + m / 60 + s / 3600
        if ref in ("S", "W"):
            decimal = -decimal
        return round(decimal, 7)
    except (TypeError, IndexError, ValueError, ZeroDivisionError):
        return None


def _generate_thumbnail(abs_path, relative_path):
    """Generate thumbnail for image files. Returns relative path or empty string."""
    try:
        from PIL import Image

        img = Image.open(abs_path)
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")

        img.thumbnail((THUMB_MAX_SIZE, THUMB_MAX_SIZE))

        # Build thumbnail path
        thumb_rel = os.path.join(THUMB_DIR, os.path.basename(relative_path))
        thumb_ext = os.path.splitext(thumb_rel)[0] + ".jpg"
        thumb_abs = os.path.join(settings.MEDIA_ROOT, thumb_ext)

        os.makedirs(os.path.dirname(thumb_abs), exist_ok=True)
        img.save(thumb_abs, "JPEG", quality=THUMB_QUALITY)

        return thumb_ext
    except Exception:
        return ""


def retroactive_archive(
    app_label,
    model_name,
    image_field_name,
    source_type="site_photo",
    content_category="photo",
    tags=None,
    batch_size=100,
):
    """
    Management command helper: archive existing photos from an app's model.

    Usage:
        from documents.photo_registry import retroactive_archive
        retroactive_archive('stolarija', 'Measurement', 'photo_before',
                          source_type='before_photo', tags=['teren'])
    """
    from django.apps import apps

    Model = apps.get_model(app_label, model_name)
    qs = Model.objects.exclude(**{f"{image_field_name}": ""}).exclude(**{f"{image_field_name}__isnull": True})

    archived = 0
    for obj in qs.iterator(chunk_size=batch_size):
        file_field = getattr(obj, image_field_name, None)
        if not file_field or not file_field.name:
            continue

        company = _resolve_company(obj)
        if not company:
            continue

        user = _resolve_user(obj)

        result = archive_photo(
            company=company,
            file_field=file_field,
            source_type=source_type,
            source_app=app_label,
            source_model=model_name,
            source_object_id=obj.pk,
            captured_by=user,
            tags=tags or [],
            content_category=content_category,
        )
        if result:
            archived += 1

    logger.info("retroactive_archive: %s.%s.%s → %d entries", app_label, model_name, image_field_name, archived)
    return archived


def _resolve_company(obj):
    """Try to find company FK on any model."""
    if hasattr(obj, "company"):
        return obj.company
    if hasattr(obj, "session") and hasattr(obj.session, "company"):
        return obj.session.company
    if hasattr(obj, "installation") and hasattr(obj.installation, "company"):
        return obj.installation.company
    if hasattr(obj, "warranty") and hasattr(obj.warranty, "session"):
        return obj.warranty.session.company
    return None


def _resolve_user(obj):
    """Try to find user FK on any model."""
    for attr in ("captured_by", "created_by", "team_lead", "technician", "user", "archived_by"):
        user = getattr(obj, attr, None)
        if user:
            return user
    return None
