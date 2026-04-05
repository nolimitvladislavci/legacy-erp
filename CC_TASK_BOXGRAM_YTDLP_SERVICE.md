# CC_TASK_BOXGRAM_YTDLP_SERVICE.md
# Boxgram — yt-dlp video download service
# Agent: CC Code | Prioritet: VISOK | Datum: 05.04.2026.

## STATUS PLATFORMI
- YouTube:   ✅ Radi bez cookies (server OK)
- Facebook:  ⚠️  Treba cookies (datacenter IP blokiran)
- Instagram: ⚠️  Treba cookies (datacenter IP blokiran)
- TikTok:    ❌  Blokira datacenter IP agresivno → client-side upload fallback

## ARHITEKTURA
1. Korisnik lijepi URL
2. Backend pokušava yt-dlp s cookies
3. Ako cookies ne postoje ili fail → fallback: korisnik sam uploaduje video
4. Video se sprema u /media/boxgram/imports/ i mapira na LifeEvent

---

## V1 — Download service (boxgram/services/video_downloader.py)

```python
"""
Boxgram Video Downloader Service
Koristi yt-dlp za preuzimanje videa s društvenih mreža.

Platforme:
- YouTube: radi bez cookies
- Facebook/Instagram: treba cookies iz browsera
- TikTok: blokira datacenter IP → korisnik uploaduje ručno

Cookies format: Netscape cookies.txt
Kako exportati cookies:
  Firefox: addon "Export Cookies" → cookies.txt
  Chrome:  addon "Get cookies.txt LOCALLY" → cookies.txt
  Putanja na serveru: /var/www/fina-connect/media/boxgram/cookies/{platform}.txt
"""
import os
import uuid
import logging
import tempfile
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

MEDIA_ROOT = Path('/var/www/fina-connect/media/boxgram/imports')
COOKIES_ROOT = Path('/var/www/fina-connect/media/boxgram/cookies')
MAX_FILE_SIZE_MB = 200
MAX_DURATION_SEC = 600  # 10 minuta max

PLATFORM_COOKIES = {
    'instagram': COOKIES_ROOT / 'instagram.txt',
    'facebook':  COOKIES_ROOT / 'facebook.txt',
    'tiktok':    COOKIES_ROOT / 'tiktok.txt',
}


@dataclass
class DownloadResult:
    success: bool
    file_path: str = ''
    thumbnail_url: str = ''
    title: str = ''
    duration: int = 0
    platform: str = ''
    error: str = ''
    needs_manual_upload: bool = False


def get_video_info(url: str) -> dict:
    """Dohvati metadata bez downloada."""
    import yt_dlp

    platform = _detect_platform(url)
    ydl_opts = _build_opts(platform, download=False)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                'title': info.get('title', ''),
                'thumbnail': info.get('thumbnail', ''),
                'duration': info.get('duration', 0),
                'uploader': info.get('uploader', ''),
                'platform': platform,
                'success': True,
            }
    except Exception as e:
        return {'success': False, 'error': str(e), 'platform': platform}


def download_video(url: str, pet_slug: str) -> DownloadResult:
    """
    Preuzmi video s URL-a i spremi lokalno.
    Vraca DownloadResult s putanjom fajla.
    """
    import yt_dlp

    platform = _detect_platform(url)

    # TikTok → odmah fallback na manual upload
    if platform == 'tiktok':
        return DownloadResult(
            success=False,
            platform='tiktok',
            needs_manual_upload=True,
            error='TikTok videi se ne mogu preuzeti automatski. Uploaduj video ručno.',
        )

    # Provjeri cookies
    cookies_file = PLATFORM_COOKIES.get(platform)
    if cookies_file and not cookies_file.exists():
        logger.warning(f'Cookies za {platform} nisu konfigurirani: {cookies_file}')

    # Output putanja
    output_dir = MEDIA_ROOT / pet_slug
    output_dir.mkdir(parents=True, exist_ok=True)
    file_id = str(uuid.uuid4())[:8]
    output_template = str(output_dir / f'{file_id}_%(id)s.%(ext)s')

    ydl_opts = _build_opts(
        platform=platform,
        download=True,
        output_template=output_template,
        cookies_file=str(cookies_file) if cookies_file and cookies_file.exists() else None,
    )

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

            # Nađi downloadani fajl
            filename = ydl.prepare_filename(info)
            # yt-dlp može promijeniti ekstenziju
            actual_file = _find_downloaded_file(output_dir, file_id)

            if not actual_file:
                return DownloadResult(
                    success=False,
                    platform=platform,
                    error='Video preuzet ali fajl nije pronađen.',
                )

            # Provjeri veličinu
            size_mb = actual_file.stat().st_size / 1024 / 1024
            if size_mb > MAX_FILE_SIZE_MB:
                actual_file.unlink()
                return DownloadResult(
                    success=False,
                    platform=platform,
                    error=f'Video je prevelik ({size_mb:.0f} MB). Max: {MAX_FILE_SIZE_MB} MB.',
                )

            return DownloadResult(
                success=True,
                file_path=str(actual_file.relative_to('/var/www/fina-connect/media')),
                thumbnail_url=info.get('thumbnail', ''),
                title=info.get('title', ''),
                duration=info.get('duration', 0),
                platform=platform,
            )

    except yt_dlp.utils.DownloadError as e:
        err = str(e)
        needs_manual = 'login' in err.lower() or 'cookie' in err.lower() or 'private' in err.lower()
        return DownloadResult(
            success=False,
            platform=platform,
            error='Video nije dostupan. Možda je privatan ili treba login.',
            needs_manual_upload=needs_manual,
        )
    except Exception as e:
        logger.error(f'yt-dlp download error za {url}: {e}')
        return DownloadResult(
            success=False,
            platform=platform,
            error='Greška pri preuzimanju. Pokušaj ručni upload.',
            needs_manual_upload=True,
        )


def _detect_platform(url: str) -> str:
    from urllib.parse import urlparse
    domain = urlparse(url).netloc.lower().replace('www.', '')
    MAP = {
        'tiktok.com': 'tiktok',
        'vm.tiktok.com': 'tiktok',
        'instagram.com': 'instagram',
        'facebook.com': 'facebook',
        'fb.watch': 'facebook',
        'youtube.com': 'youtube',
        'youtu.be': 'youtube',
    }
    for key, val in MAP.items():
        if key in domain:
            return val
    return 'other'


def _build_opts(platform: str, download: bool = False,
                output_template: str = '', cookies_file: str = None) -> dict:
    opts = {
        'quiet': True,
        'no_warnings': False,
        'extract_flat': not download,
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'merge_output_format': 'mp4',
        'max_filesize': MAX_FILE_SIZE_MB * 1024 * 1024,
    }

    if download and output_template:
        opts['outtmpl'] = output_template

    if cookies_file:
        opts['cookiefile'] = cookies_file

    # Platform-specific
    if platform == 'instagram':
        opts['http_headers'] = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15',
        }

    return opts


def _find_downloaded_file(directory: Path, file_id: str) -> Optional[Path]:
    """Nađi fajl koji počinje s file_id u direktoriju."""
    for f in directory.iterdir():
        if f.name.startswith(file_id) and f.suffix in ['.mp4', '.webm', '.mkv', '.mov']:
            return f
    return None
```

---

## V2 — Celery task za async download

U `boxgram/tasks.py` dodaj:

```python
@shared_task(queue='default', time_limit=300, soft_time_limit=270)
def download_social_video(social_import_id: str):
    """
    Async download videa za SocialImport zapis.
    Pokreće se nakon što korisnik potvrdi import.
    """
    from boxgram.models import SocialImport, EventMedia
    from boxgram.services.video_downloader import download_video

    try:
        imp = SocialImport.objects.get(id=social_import_id)
        result = download_video(url=imp.source_url, pet_slug=imp.pet.slug)

        if result.success:
            # Kreiraj EventMedia ako postoji mapped LifeEvent
            if imp.mapped_to:
                EventMedia.objects.get_or_create(
                    event=imp.mapped_to,
                    source_url=imp.source_url,
                    defaults={
                        'file': result.file_path,
                        'file_type': 'video',
                        'thumbnail_url': result.thumbnail_url,
                    }
                )
            imp.raw_data['download_path'] = result.file_path
            imp.raw_data['download_ok'] = True
            imp.save(update_fields=['raw_data'])
            logger.info(f'Video download OK: {imp.source_url} → {result.file_path}')
        else:
            imp.raw_data['download_error'] = result.error
            imp.raw_data['needs_manual_upload'] = result.needs_manual_upload
            imp.save(update_fields=['raw_data'])
            logger.warning(f'Video download FAIL: {imp.source_url} — {result.error}')

        return result.success

    except SocialImport.DoesNotExist:
        logger.error(f'SocialImport {social_import_id} ne postoji')
        return False
```

---

## V3 — API endpoint za manual video upload (fallback)

U `boxgram/views_social.py` dodaj:

```python
@login_required
@require_POST
def upload_video_manual(request, import_id):
    """
    POST /api/boxgram/import/{id}/upload-video/
    Multipart form: video file

    Fallback kad yt-dlp ne može preuzeti (TikTok, privatni profili).
    Korisnik sam downloaduje video na mobitelu i uploaduje ovdje.
    """
    from boxgram.models import SocialImport, EventMedia

    pet_ids = PetProfile.objects.filter(owner=request.user).values_list('id', flat=True)
    imp = get_object_or_404(SocialImport, id=import_id, pet_id__in=pet_ids)

    video_file = request.FILES.get('video')
    if not video_file:
        return JsonResponse({'success': False, 'error': 'Video fajl je obavezan.'}, status=400)

    # Provjeri tip i veličinu
    allowed_types = ['video/mp4', 'video/quicktime', 'video/webm', 'video/x-msvideo']
    if video_file.content_type not in allowed_types:
        return JsonResponse({'success': False, 'error': 'Dozvoljeni formati: MP4, MOV, WebM.'}, status=400)

    max_size = 200 * 1024 * 1024  # 200 MB
    if video_file.size > max_size:
        return JsonResponse({'success': False, 'error': 'Video je prevelik. Max 200 MB.'}, status=400)

    # Spremi video
    from django.core.files.storage import default_storage
    import os
    ext = os.path.splitext(video_file.name)[1] or '.mp4'
    save_path = f'boxgram/imports/{imp.pet.slug}/{uuid.uuid4()}{ext}'
    saved_path = default_storage.save(save_path, video_file)

    # Kreiraj EventMedia
    if imp.mapped_to:
        EventMedia.objects.create(
            event=imp.mapped_to,
            file=saved_path,
            file_type='video',
            source_url=imp.source_url,
        )

    imp.raw_data['manual_upload_path'] = saved_path
    imp.raw_data['download_ok'] = True
    imp.save(update_fields=['raw_data'])

    return JsonResponse({
        'success': True,
        'message': 'Video uspješno uploadovan na profil ljubimca.',
    })
```

---

## V4 — Cookies setup (jednokratno)

### Kako postaviti cookies za Instagram/Facebook:

```bash
# Na serveru kreiraj direktorij
mkdir -p /var/www/fina-connect/media/boxgram/cookies
chmod 700 /var/www/fina-connect/media/boxgram/cookies

# Na svom browseru (Firefox/Chrome):
# Instaliraj addon: "Get cookies.txt LOCALLY" (Chrome) ili "Export Cookies" (Firefox)
# Logiraj se na Instagram/Facebook
# Exportaj cookies kao cookies.txt
# Uploadaj na server:

# scp cookies.txt root@37.27.248.86:/var/www/fina-connect/media/boxgram/cookies/instagram.txt
# scp cookies.txt root@37.27.248.86:/var/www/fina-connect/media/boxgram/cookies/facebook.txt

# Postavi restriktivne dozvole (cookies su osjetljivi!)
chmod 600 /var/www/fina-connect/media/boxgram/cookies/*.txt
```

### Test nakon cookies upload:
```bash
yt-dlp --cookies /var/www/fina-connect/media/boxgram/cookies/instagram.txt \
       --no-download --print "%(title)s" \
       "https://www.instagram.com/p/SOME_POST/"
```

---

## V5 — URL rute (dodaj u boxgram/urls.py)

```python
path('api/boxgram/import/<uuid:import_id>/upload-video/',
     views_social.upload_video_manual, name='boxgram_upload_video'),
```

---

## DONE kriterij

- [ ] `boxgram/services/video_downloader.py` kreiran
- [ ] `download_social_video` Celery task u tasks.py
- [ ] `upload_video_manual` view i URL ruta
- [ ] YouTube download test prolazi:
  ```bash
  cd /var/www/fina-connect
  venv/bin/python -c "
  from boxgram.services.video_downloader import get_video_info
  r = get_video_info('https://www.youtube.com/watch?v=dQw4w9WgXcQ')
  print(r)
  "
  ```
- [ ] TikTok → odmah vraća needs_manual_upload=True (bez grešaka)
- [ ] Manual upload endpoint prima MP4 do 200MB
- [ ] `/var/www/fina-connect/media/boxgram/cookies/` direktorij postoji, chmod 700
- [ ] Commit: "feat(boxgram): yt-dlp video downloader + manual upload fallback"

## NAPOMENA ZA IVANA
Cookies za Instagram/Facebook — eksportiraj iz svog browsera:
1. Chrome: instaliraj "Get cookies.txt LOCALLY" addon
2. Logiraj se na instagram.com
3. Klikni addon → "Export cookies for this domain"
4. Spremi kao instagram.txt
5. Uploadaj na server putem SSH ili SFTP

TikTok cookies možda pomognu ali server IP je često na blacklisti.
Najsigurniji fallback za TikTok: korisnik downloaduje video s mobitela i uploaduje direktno.
