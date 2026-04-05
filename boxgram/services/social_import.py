import requests
import json
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from urllib.parse import urlparse
from django.conf import settings
from boxgram.models import SocialImport, PetProfile

logger = logging.getLogger(__name__)

# oEmbed endpoints za razne platforme
OEMBED_PROVIDERS = {
    'facebook.com': 'https://www.facebook.com/plugins/post/oembed.json',
    'instagram.com': 'https://graph.instagram.com/instagram_oembed',
    'tiktok.com': 'https://www.tiktok.com/oembed',
    'youtube.com': 'https://www.youtube.com/oembed',
    'youtu.be': 'https://www.youtube.com/oembed',
    'vimeo.com': 'https://vimeo.com/api/oembed.json',
}

# Mapiranje domena na platforme
PLATFORM_MAP = {
    'facebook.com': 'facebook',
    'instagram.com': 'instagram',
    'tiktok.com': 'tiktok',
    'youtube.com': 'youtube',
    'youtu.be': 'youtube',
    'vimeo.com': 'youtube',  # Tretiraj kao video
}


@dataclass
class ImportPreview:
    """Rezultat preview-a社会 importa"""
    success: bool
    platform: Optional[str] = None
    source_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    caption: Optional[str] = None
    author_name: Optional[str] = None
    embed_html: Optional[str] = None
    error: Optional[str] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)


def detect_platform(url: str) -> Optional[str]:
    """
    Detektuj platformu na osnovu URL-a.
    
    Args:
        url: URL objekta sa društvene mreže
        
    Returns:
        String ('facebook', 'instagram', 'tiktok', 'youtube') ili None
    """
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.replace('www.', '')
        return PLATFORM_MAP.get(domain)
    except Exception as e:
        logger.error(f"Error detecting platform from {url}: {e}")
        return None


def fetch_oembed(url: str) -> ImportPreview:
    """
    Povuči oEmbed podatke sa društvene mreže.
    
    Args:
        url: URL objekta sa društvene mreže
        
    Returns:
        ImportPreview sa rezultatima
    """
    platform = detect_platform(url)
    
    if not platform:
        return ImportPreview(
            success=False,
            source_url=url,
            error='Nepodržana platforma. Podržane: Facebook, Instagram, TikTok, YouTube'
        )
    
    # Pronađi odgovarajući oEmbed endpoint
    oembed_url = None
    for domain, endpoint in OEMBED_PROVIDERS.items():
        if domain in url:
            oembed_url = endpoint
            break
    
    if not oembed_url:
        return ImportPreview(
            success=False,
            platform=platform,
            source_url=url,
            error=f'Nema oEmbed endpoint-a za {platform}'
        )
    
    try:
        # Pripremi parametre ovisno o platformi
        params = {'url': url}
        
        if platform == 'instagram':
            # Instagram zahtijeva poseban token
            instagram_token = getattr(settings, 'INSTAGRAM_OEMBED_TOKEN', '')
            if not instagram_token:
                return ImportPreview(
                    success=False,
                    platform=platform,
                    source_url=url,
                    error='Instagram token nije konfiguriran. Kontaktiraj administratora.'
                )
            params['access_token'] = instagram_token
        
        # Kreni HTTP zahtjev sa timeout-om
        response = requests.get(
            oembed_url,
            params=params,
            timeout=10,
            headers={'User-Agent': 'Boxgram/1.0'}
        )
        response.raise_for_status()
        
        data = response.json()
        
        # Normaliziraj podatke
        thumbnail_url = data.get('thumbnail_url') or data.get('thumbnail')
        
        # Za TikTok - cache thumbnail lokalno
        if platform == 'tiktok':
            thumbnail_url = data.get('thumbnail_url')
        
        # Za YouTube - koristi standard thumbnail URL
        if platform == 'youtube':
            # Ekstrakuj video ID
            video_id = _extract_youtube_id(url)
            if video_id:
                thumbnail_url = f'https://img.youtube.com/vi/{video_id}/maxresdefault.jpg'
        
        caption = data.get('title') or data.get('description', '')
        
        return ImportPreview(
            success=True,
            platform=platform,
            source_url=url,
            thumbnail_url=thumbnail_url,
            caption=caption[:300],  # Limitiraj na 300 znakova
            author_name=data.get('author_name'),
            embed_html=data.get('html'),
            raw_data=data
        )
        
    except requests.Timeout:
        return ImportPreview(
            success=False,
            platform=platform,
            source_url=url,
            error='Timeout pri dohvatanom sadržaja. Platforma ne odgovara.'
        )
    except requests.HTTPError as e:
        if response.status_code == 404:
            error_msg = 'Objava nije pronađena. Provjerite URL.'
        elif response.status_code == 403:
            error_msg = 'Objava nije dostupna ili je privatna.'
        else:
            error_msg = f'HTTP greška {response.status_code}'
        
        return ImportPreview(
            success=False,
            platform=platform,
            source_url=url,
            error=error_msg
        )
    except json.JSONDecodeError:
        return ImportPreview(
            success=False,
            platform=platform,
            source_url=url,
            error='Greška pri parsiranju odgovora platforme.'
        )
    except Exception as e:
        logger.error(f"Error fetching oEmbed for {url}: {e}")
        return ImportPreview(
            success=False,
            platform=platform,
            source_url=url,
            error=f'Greška: {str(e)[:100]}'
        )


def _extract_youtube_id(url: str) -> Optional[str]:
    """Ekstrakuj YouTube video ID iz URL-a"""
    try:
        if 'youtu.be' in url:
            return url.split('/')[-1].split('?')[0]
        elif 'youtube.com' in url:
            parsed = urlparse(url)
            return parsed.query.split('v=')[1].split('&')[0] if 'v=' in parsed.query else None
    except Exception:
        pass
    return None


def create_social_import(pet: PetProfile, url: str, requested_by) -> tuple[SocialImport, ImportPreview]:
    """
    Kreiraj SocialImport zapis i povuči oEmbed podatke.
    
    Args:
        pet: PetProfile instance
        url: URL objekta
        requested_by: User koji je zahtjevao import
        
    Returns:
        Tuple od (SocialImport instance, ImportPreview)
    """
    # Provjeri duplikat
    existing = SocialImport.objects.filter(
        pet=pet,
        source_url=url
    ).first()
    
    if existing:
        # Dohvati već stare podatke
        preview = ImportPreview(
            success=True,
            platform=existing.platform,
            source_url=url,
            raw_data=existing.raw_data,
            error='Ovaj URL je već importan.'
        )
        return existing, preview
    
    platform = detect_platform(url)
    if not platform:
        platform = 'manual'
    
    # Kreiraj SocialImport zapis
    social_import = SocialImport.objects.create(
        pet=pet,
        platform=platform,
        source_url=url,
        status='pending'
    )
    
    # Povuči preview
    preview = fetch_oembed(url)
    
    # Spremi raw_data ako je uspješno
    if preview.success:
        social_import.raw_data = preview.raw_data
        social_import.save()
    else:
        # Ako fetch nije uspio, pokreni async task za retry
        from boxgram.tasks import retry_fetch_social_import
        retry_fetch_social_import.apply_async(
            args=(str(social_import.id),),
            countdown=60  # Pokušaj za 1 minutu
        )
    
    return social_import, preview
