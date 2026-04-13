"""
core/image_compression.py — Auto Image Kompresija + Kvota pohrane

Dva sustava:
1. CompressedImageField — custom Django ImageField koji automatski komprimira
   slike pri uploadu (WebP, max 1920px, max 500KB, EXIF strip)
2. ImageQuotaMiddleware — provjerava kvote pohrane slika po firmi

LIMIT Connect ERP — 2026-03-25
"""
import io
import os
import logging
from decimal import Decimal

from django.db import models
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin

from PIL import Image, ExifTags

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
#  CompressedImageField — WebP auto-kompresija pri uploadu
# ═══════════════════════════════════════════════════════════════

MAX_WIDTH = 1920
MAX_FILE_SIZE = 500 * 1024  # 500 KB
INITIAL_QUALITY = 80
MIN_QUALITY = 40


def compress_image(image_file, max_width=MAX_WIDTH, max_size=MAX_FILE_SIZE,
                   initial_quality=INITIAL_QUALITY, min_quality=MIN_QUALITY):
    """
    Komprimira sliku u WebP format.
    
    - Resize na max_width (aspect ratio sačuvan)
    - Strip EXIF (privacy — ukloni GPS lokaciju)
    - Compress quality 80%, smanjuj dok < max_size (min 40%)
    - Vraća (filename, InMemoryUploadedFile)
    """
    try:
        img = Image.open(image_file)
    except Exception as e:
        logger.warning('compress_image: ne mogu otvoriti sliku: %s', e)
        return None

    # Strip EXIF podataka (privacy — ukloni GPS, kameru, itd.)
    # Sačuvaj orijentaciju prije stripa
    try:
        exif = img._getexif()
        if exif:
            for tag_id, value in exif.items():
                tag = ExifTags.Tags.get(tag_id, tag_id)
                if tag == 'Orientation':
                    if value == 3:
                        img = img.rotate(180, expand=True)
                    elif value == 6:
                        img = img.rotate(270, expand=True)
                    elif value == 8:
                        img = img.rotate(90, expand=True)
    except (AttributeError, Exception):
        pass

    # Konvertuj u RGB ako je RGBA/P/LA (WebP podržava RGBA ali za kompresiju bolje RGB)
    if img.mode in ('RGBA', 'LA', 'P'):
        # Za RGBA: sačuvaj transparentnost
        if img.mode == 'RGBA':
            pass  # WebP podržava RGBA
        else:
            img = img.convert('RGBA')
    elif img.mode != 'RGB':
        img = img.convert('RGB')

    # Resize na max_width (aspect ratio sačuvan)
    if img.width > max_width:
        ratio = max_width / img.width
        new_height = int(img.height * ratio)
        img = img.resize((max_width, new_height), Image.LANCZOS)

    # Komprimuj u WebP, smanjuj quality dok ne bude < max_size
    quality = initial_quality
    while quality >= min_quality:
        buffer = io.BytesIO()
        img.save(buffer, format='WEBP', quality=quality, optimize=True)
        size = buffer.tell()
        if size <= max_size:
            break
        quality -= 5
        logger.debug('compress_image: quality=%d, size=%d', quality, size)

    buffer.seek(0)

    # Generiraj novo ime fajla
    original_name = getattr(image_file, 'name', 'image.jpg')
    base_name = os.path.splitext(os.path.basename(original_name))[0]
    new_name = f'{base_name}.webp'

    compressed = InMemoryUploadedFile(
        file=buffer,
        field_name=None,
        name=new_name,
        content_type='image/webp',
        size=buffer.getbuffer().nbytes,
        charset=None,
    )

    logger.info(
        'compress_image: %s -> %s (quality=%d, size=%d KB)',
        original_name, new_name, quality,
        buffer.getbuffer().nbytes // 1024,
    )

    return compressed


class CompressedImageField(models.ImageField):
    """
    ImageField koji automatski komprimira sliku pri uploadu.
    Max 500KB, WebP format, max 1920px širina.
    EXIF strip (privacy — ukloni GPS lokaciju iz metadataka).
    
    Korištenje:
        class MyModel(models.Model):
            photo = CompressedImageField(upload_to='photos/%Y/')
    """

    def __init__(self, *args, max_width=MAX_WIDTH, max_file_size=MAX_FILE_SIZE,
                 compress_quality=INITIAL_QUALITY, min_quality=MIN_QUALITY, **kwargs):
        self.max_width = max_width
        self.max_file_size = max_file_size
        self.compress_quality = compress_quality
        self.min_quality = min_quality
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        if self.max_width != MAX_WIDTH:
            kwargs['max_width'] = self.max_width
        if self.max_file_size != MAX_FILE_SIZE:
            kwargs['max_file_size'] = self.max_file_size
        if self.compress_quality != INITIAL_QUALITY:
            kwargs['compress_quality'] = self.compress_quality
        if self.min_quality != MIN_QUALITY:
            kwargs['min_quality'] = self.min_quality
        return name, path, args, kwargs

    def pre_save(self, model_instance, add):
        file = getattr(model_instance, self.attname)
        if file and hasattr(file, 'file') and hasattr(file, 'name'):
            # Samo komprimiraj ako je nova datoteka (ne postoji u storage-u)
            if not file._committed:
                compressed = compress_image(
                    file,
                    max_width=self.max_width,
                    max_size=self.max_file_size,
                    initial_quality=self.compress_quality,
                    min_quality=self.min_quality,
                )
                if compressed:
                    setattr(model_instance, self.attname, compressed)

        return super().pre_save(model_instance, add)


# ═══════════════════════════════════════════════════════════════
#  Kvote pohrane po planu pretplate
# ═══════════════════════════════════════════════════════════════

# Plan -> max storage u bajtovima
STORAGE_QUOTAS = {
    'starter':      1 * 1024 * 1024 * 1024,      # 1 GB
    'micro':        1 * 1024 * 1024 * 1024,       # 1 GB
    'professional': 10 * 1024 * 1024 * 1024,      # 10 GB
    'business':     10 * 1024 * 1024 * 1024,      # 10 GB (legacy)
    'enterprise':   50 * 1024 * 1024 * 1024,      # 50 GB
    'distributor':  50 * 1024 * 1024 * 1024,      # 50 GB
}
DEFAULT_QUOTA = 1 * 1024 * 1024 * 1024  # 1 GB default


def get_company_plan(company):
    """Dohvati aktivni plan pretplate za firmu."""
    try:
        from registration.models import CompanySubscription
        sub = CompanySubscription.objects.filter(
            company=company, is_active=True
        ).order_by('-valid_from').first()
        if sub:
            return sub.plan
    except Exception:
        pass
    return 'starter'


def get_company_storage_quota(company):
    """Vraća dozvoljenu kvotu pohrane u bajtovima za firmu."""
    # Platform owner = unlimited
    if getattr(company, 'is_platform_owner', False):
        return float('inf')
    plan = get_company_plan(company)
    return STORAGE_QUOTAS.get(plan, DEFAULT_QUOTA)


def get_company_storage_usage(company):
    """
    Izračunaj ukupnu pohranu firme pregledavajući sve relevantne modele
    koji imaju ImageField ili FileField.
    
    Vraća ukupnu veličinu u bajtovima.
    """
    from django.apps import apps
    from django.db.models import FileField as DjangoFileField

    total_bytes = 0
    company_id = company.pk

    for model in apps.get_models():
        # Pronađi sve FileField / ImageField na modelu
        file_fields = [
            f.name for f in model._meta.get_fields()
            if isinstance(f, DjangoFileField)
        ]
        if not file_fields:
            continue

        # Provjeri ima li model FK na company
        company_fk = None
        for field in model._meta.get_fields():
            if hasattr(field, 'related_model') and field.related_model:
                related = field.related_model.__name__
                if related == 'Company' and hasattr(field, 'column'):
                    company_fk = field.name
                    break

        if not company_fk:
            continue

        try:
            qs = model.objects.filter(**{company_fk: company_id})
            for obj in qs.only(*file_fields).iterator(chunk_size=500):
                for fname in file_fields:
                    field_file = getattr(obj, fname, None)
                    if field_file and field_file.name:
                        try:
                            total_bytes += field_file.size
                        except (FileNotFoundError, OSError):
                            # Fajl ne postoji na disku — preskoči
                            pass
                        except Exception:
                            pass
        except Exception as e:
            logger.debug('get_company_storage_usage: skip %s.%s: %s',
                         model._meta.app_label, model.__name__, e)
            continue

    return total_bytes


def format_storage_size(bytes_val):
    """Formatiraj veličinu u čitljiv format (KB, MB, GB)."""
    if bytes_val < 1024:
        return f'{bytes_val} B'
    elif bytes_val < 1024 * 1024:
        return f'{bytes_val / 1024:.1f} KB'
    elif bytes_val < 1024 * 1024 * 1024:
        return f'{bytes_val / (1024 * 1024):.1f} MB'
    else:
        return f'{bytes_val / (1024 * 1024 * 1024):.2f} GB'


# ═══════════════════════════════════════════════════════════════
#  ImageQuotaMiddleware — provjerava kvote po firmi
# ═══════════════════════════════════════════════════════════════

class ImageQuotaMiddleware:
    """
    Provjerava kvote pohrane slika po firmi.
    
    Planovi:
        Starter/Micro:      1 GB
        Professional:      10 GB
        Enterprise:        50 GB
    
    Provjera se vrši samo za POST/PUT/PATCH requeste koji sadrže datoteke.
    Ako firma prelazi kvotu, vraća 413 (Payload Too Large) s porukom na HR.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Samo provjeri za upload requeste s datotekama
        if request.method in ('POST', 'PUT', 'PATCH') and request.FILES:
            company = getattr(request, 'company', None)
            if not company:
                try:
                    company = request.user.userprofile.company
                except Exception:
                    company = None

            if company:
                # Izračunaj veličinu uploadanih datoteka
                upload_size = sum(f.size for f in request.FILES.values())

                # Dohvati kvotu i trenutnu potrošnju
                quota = get_company_storage_quota(company)
                if quota != float('inf'):
                    usage = get_company_storage_usage(company)

                    if usage + upload_size > quota:
                        plan = get_company_plan(company)
                        quota_str = format_storage_size(quota)
                        usage_str = format_storage_size(usage)
                        upload_str = format_storage_size(upload_size)

                        logger.warning(
                            'ImageQuota BLOCKED: company=%s plan=%s usage=%s quota=%s upload=%s',
                            company.name, plan, usage_str, quota_str, upload_str,
                        )

                        # Provjeri je li API ili browser request
                        if request.path.startswith('/api/') or \
                           'application/json' in request.headers.get('Accept', ''):
                            return JsonResponse({
                                'error': 'Prekoračena kvota pohrane',
                                'detail': (
                                    f'Vaš plan ({plan}) dozvoljava {quota_str} pohrane. '
                                    f'Trenutno koristite {usage_str}. '
                                    f'Upload od {upload_str} premašuje limit. '
                                    f'Nadogradite plan za više prostora.'
                                ),
                                'usage_bytes': usage,
                                'quota_bytes': quota if quota != float('inf') else -1,
                                'upload_bytes': upload_size,
                            }, status=413)
                        else:
                            from django.contrib import messages
                            from django.shortcuts import redirect
                            messages.error(
                                request,
                                f'Prekoračena kvota pohrane! '
                                f'Vaš plan ({plan}) dozvoljava {quota_str}. '
                                f'Trenutno koristite {usage_str}. '
                                f'Nadogradite plan za više prostora.'
                            )
                            referrer = request.META.get('HTTP_REFERER', '/')
                            return redirect(referrer)

        return self.get_response(request)
