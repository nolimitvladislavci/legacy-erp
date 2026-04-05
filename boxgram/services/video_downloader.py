"""
Boxgram Video Downloader Service
yt-dlp wrapper za preuzimanje videa s društvenih mreža.

Platforme:
  YouTube   → radi odmah, bez cookies
  Facebook  → treba cookies iz browsera
  Instagram → treba cookies iz browsera
  TikTok    → datacenter IP blokiran → manual upload fallback

Cookies format: Netscape cookies.txt
Putanja: /var/www/fina-connect/media/boxgram/cookies/{platform}.txt
Kako eksportirati: Chrome addon "Get cookies.txt LOCALLY"
"""
import os
import uuid
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

MEDIA_ROOT = Path('/var/www/fina-connect/media/boxgram/imports')
COOKIES_ROOT = Path('/var/www/fina-connect/media/boxgram/cookies')
MAX_FILE_SIZE_MB = 200
MAX_DURATION_SEC = 600

PLATFORM_COOKIES = {
    'instagram': COOKIES_ROOT / 'instagram.txt',
    'facebook':  COOKIES_ROOT / 'facebook.txt',
    'tiktok':    COOKIES_ROOT / 'tiktok.txt',
}

PLATFORM_MAP = {
    'tiktok.com': 'tiktok', 'vm.tiktok.com': 'tiktok',
    'instagram.com': 'instagram', 'www.instagram.com': 'instagram',
    'facebook.com': 'facebook', 'www.facebook.com': 'facebook', 'fb.watch': 'facebook',
    'youtube.com': 'youtube', 'www.youtube.com': 'youtube', 'youtu.be': 'youtube',
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


def detect_platform(url: str) -> str:
    from urllib.parse import urlparse
    domain = urlparse(url).netloc.lower().replace('www.', '')
    for key, val in PLATFORM_MAP.items():
        if key.replace('www.', '') in domain:
            return val
    return 'other'


def get_video_info(url: str) -> dict:
    """Dohvati metadata bez downloada — za preview."""
    try:
        import yt_dlp
        platform = detect_platform(url)
        cookies_file = _get_cookies(platform)

        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
        }
        if cookies_file:
            ydl_opts['cookiefile'] = cookies_file

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                'success': True,
                'title': info.get('title', ''),
                'thumbnail': info.get('thumbnail', ''),
                'duration': info.get('duration', 0),
                'uploader': info.get('uploader', ''),
                'platform': platform,
            }
    except Exception as e:
        return {'success': False, 'error': str(e), 'platform': detect_platform(url)}


def download_video(url: str, pet_slug: str) -> DownloadResult:
    """
    Preuzmi video i spremi lokalno.
    Vraca DownloadResult s putanjom fajla ili error.
    """
    try:
        import yt_dlp
    except ImportError:
        return DownloadResult(
            success=False,
            error='yt-dlp nije instaliran. Pokreni: pip install yt-dlp',
            needs_manual_upload=True,
        )

    platform = detect_platform(url)

    # TikTok → odmah manual upload
    if platform == 'tiktok':
        return DownloadResult(
            success=False,
            platform='tiktok',
            needs_manual_upload=True,
            error='TikTok videi se ne mogu preuzeti automatski s ovog servera. Uploaduj video ručno.',
        )

    cookies_file = _get_cookies(platform)
    if platform in ('instagram', 'facebook') and not cookies_file:
        return DownloadResult(
            success=False,
            platform=platform,
            needs_manual_upload=True,
            error=f'{platform.title()} zahtijeva cookies. Uploaduj video ručno ili postavi cookies na server.',
        )

    # Output direktorij
    output_dir = MEDIA_ROOT / pet_slug
    output_dir.mkdir(parents=True, exist_ok=True)
    file_id = str(uuid.uuid4())[:8]
    output_template = str(output_dir / f'{file_id}_%(id)s.%(ext)s')

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'outtmpl': output_template,
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best[filesize<?{}M]'.format(MAX_FILE_SIZE_MB),
        'merge_output_format': 'mp4',
        'max_filesize': MAX_FILE_SIZE_MB * 1024 * 1024,
        'match_filter': yt_dlp.utils.match_filter_func(f'duration < {MAX_DURATION_SEC}'),
    }

    if cookies_file:
        ydl_opts['cookiefile'] = cookies_file

    if platform == 'instagram':
        ydl_opts['http_headers'] = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15',
        }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

            actual_file = _find_downloaded_file(output_dir, file_id)
            if not actual_file:
                return DownloadResult(
                    success=False,
                    platform=platform,
                    error='Video preuzet ali fajl nije pronađen.',
                    needs_manual_upload=True,
                )

            size_mb = actual_file.stat().st_size / 1024 / 1024
            if size_mb > MAX_FILE_SIZE_MB:
                actual_file.unlink(missing_ok=True)
                return DownloadResult(
                    success=False,
                    platform=platform,
                    error=f'Video je prevelik ({size_mb:.0f} MB). Max: {MAX_FILE_SIZE_MB} MB.',
                )

            # Relativna putanja od MEDIA_ROOT projekta
            rel_path = str(actual_file.relative_to('/var/www/fina-connect/media'))

            return DownloadResult(
                success=True,
                file_path=rel_path,
                thumbnail_url=info.get('thumbnail', ''),
                title=info.get('title', ''),
                duration=info.get('duration', 0),
                platform=platform,
            )

    except yt_dlp.utils.DownloadError as e:
        err_str = str(e).lower()
        needs_manual = any(x in err_str for x in ['login', 'cookie', 'private', 'blocked', 'unavailable'])
        return DownloadResult(
            success=False,
            platform=platform,
            error='Video nije dostupan ili je privatan. Pokušaj ručni upload.',
            needs_manual_upload=needs_manual,
        )
    except Exception as e:
        logger.error(f'video_downloader: neočekivana greška za {url}: {e}')
        return DownloadResult(
            success=False,
            platform=platform,
            error='Greška pri preuzimanju. Pokušaj ručni upload.',
            needs_manual_upload=True,
        )


def _get_cookies(platform: str) -> Optional[str]:
    """Vrati putanju cookies fajla ako postoji i nije prazan."""
    cookies_path = PLATFORM_COOKIES.get(platform)
    if cookies_path and cookies_path.exists() and cookies_path.stat().st_size > 100:
        return str(cookies_path)
    return None


def _find_downloaded_file(directory: Path, file_id: str) -> Optional[Path]:
    """Nađi downloadani fajl po prefiksu."""
    VIDEO_EXTS = {'.mp4', '.webm', '.mkv', '.mov', '.m4v'}
    for f in directory.iterdir():
        if f.name.startswith(file_id) and f.suffix.lower() in VIDEO_EXTS:
            return f
    return None
