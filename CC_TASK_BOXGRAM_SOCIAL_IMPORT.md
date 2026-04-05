# CC_TASK_BOXGRAM_SOCIAL_IMPORT.md
# Boxgram — FB / Instagram / TikTok import objava
# Agent: CC Code | Prioritet: VISOK | Datum: 05.04.2026.

## SVRHA
Korisnik lijepi URL objave s Facebooka, Instagrama ili TikToka.
Boxgram automatski povuče thumbnail, opis i datum — korisnik potvrdi
i objava postaje LifeEvent na profilu ljubimca. Zauvijek arhivirano.

## PRINCIP
- Faza 1 (odmah): oEmbed — radi bez API ključa, bez App Review
- Faza 2 (poslije): FB/IG Graph API OAuth — za automatski pull bez URL-a
- Nikad: screen scraping (ToS kršenje)

## ZAKONSKA OSNOVA
- Korisnik uvozi SVOJE objave → GDPR legalno
- oEmbed javnih objava → FB/IG/TikTok ToS dopušta
- Meta App Review potreban samo za Graph API (Faza 2)

---

## S1 — Import service (boxgram/services/social_import.py)

Novi fajl: `/var/www/fina-connect/boxgram/services/social_import.py`

```python
"""
Boxgram Social Import Service
Podržani: Facebook, Instagram, TikTok, YouTube
Metoda: oEmbed (bez API ključa, bez App Review)
"""
import logging
import requests
from urllib.parse import urlparse
from dataclasses import dataclass, field
from typing import Optional
from datetime import date

logger = logging.getLogger(__name__)

# Timeout za sve HTTP pozive
REQUEST_TIMEOUT = 10

# oEmbed endpointi po domeni
OEMBED_PROVIDERS = {
    'facebook.com':   'https://www.facebook.com/plugins/post/oembed.json',
    'www.facebook.com': 'https://www.facebook.com/plugins/post/oembed.json',
    'instagram.com':  'https://graph.facebook.com/v18.0/instagram_oembed',
    'www.instagram.com': 'https://graph.facebook.com/v18.0/instagram_oembed',
    'tiktok.com':     'https://www.tiktok.com/oembed',
    'www.tiktok.com': 'https://www.tiktok.com/oembed',
    'vm.tiktok.com':  'https://www.tiktok.com/oembed',
    'youtube.com':    'https://www.youtube.com/oembed',
    'www.youtube.com':'https://www.youtube.com/oembed',
    'youtu.be':       'https://www.youtube.com/oembed',
}

# Mapiranje domene na platform choice
PLATFORM_MAP = {
    'facebook.com': 'facebook',
    'www.facebook.com': 'facebook',
    'instagram.com': 'instagram',
    'www.instagram.com': 'instagram',
    'tiktok.com': 'tiktok',
    'www.tiktok.com': 'tiktok',
    'vm.tiktok.com': 'tiktok',
    'youtube.com': 'youtube',
    'www.youtube.com': 'youtube',
    'youtu.be': 'youtube',
}


@dataclass
class ImportPreview:
    """Rezultat oEmbed fetch-a — preview za korisnika."""
    success: bool
    platform: str = ''
    source_url: str = ''
    thumbnail_url: str = ''
    caption: str = ''
    author_name: str = ''
    embed_html: str = ''
    error: str = ''
    raw_data: dict = field(default_factory=dict)


def detect_platform(url: str) -> Optional[str]:
    """Vrati platform naziv iz URL-a."""
    try:
        domain = urlparse(url).netloc.lower()
        return PLATFORM_MAP.get(domain)
    except Exception:
        return None


def fetch_oembed(url: str) -> ImportPreview:
    """
    Glavni entry point. Povuci oEmbed metadata za dani URL.
    Vraca ImportPreview s podacima ili error porukom.
    """
    try:
        domain = urlparse(url).netloc.lower()
        platform = PLATFORM_MAP.get(domain)
        endpoint = OEMBED_PROVIDERS.get(domain)

        if not endpoint:
            return ImportPreview(
                success=False,
                error=f'Platforma nije podržana. Podržano: Facebook, Instagram, TikTok, YouTube.'
            )

        params = {'url': url, 'format': 'json'}

        # Instagram oEmbed zahtijeva access token (FB App)
        # Za MVP — preskačemo IG ako nema token, korisnik unosi ručno
        if platform == 'instagram':
            from django.conf import settings
            token = getattr(settings, 'INSTAGRAM_OEMBED_TOKEN', '')
            if not token:
                return ImportPreview(
                    success=False,
                    platform='instagram',
                    source_url=url,
                    error='Instagram import privremeno nedostupan. Unesi podatke ručno.',
                )
            params['access_token'] = token

        resp = requests.get(endpoint, params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        # Normaliziraj thumbnail — TikTok/YT koriste 'thumbnail_url', FB koristi drugačije
        thumbnail = (
            data.get('thumbnail_url') or
            data.get('thumbnail') or
            ''
        )

        # Caption — title ili author_name kao fallback
        caption = (
            data.get('title') or
            data.get('author_name') or
            ''
        )

        return ImportPreview(
            success=True,
            platform=platform or '',
            source_url=url,
            thumbnail_url=thumbnail,
            caption=caption[:500],  # max 500 znakova
            author_name=data.get('author_name', ''),
            embed_html=data.get('html', ''),
            raw_data=data,
        )

    except requests.exceptions.Timeout:
        return ImportPreview(success=False, error='Platforma ne odgovara. Pokušaj ponovo.')
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            return ImportPreview(success=False, error='Objava nije pronađena ili je privatna.')
        return ImportPreview(success=False, error=f'Greška platforme: {e.response.status_code}')
    except Exception as e:
        logger.warning(f'oEmbed fetch error za {url}: {e}')
        return ImportPreview(success=False, error='Neočekivana greška. Pokušaj ručni unos.')


def create_social_import(pet, url: str, requested_by=None):
    """
    Kreira SocialImport zapis i pokreće fetch u pozadini.
    Vraca (SocialImport, ImportPreview).
    """
    from boxgram.models import SocialImport
    from boxgram.tasks import fetch_social_import

    platform = detect_platform(url) or 'manual'

    # Provjeri duplikat
    existing = SocialImport.objects.filter(pet=pet, source_url=url).first()
    if existing:
        return existing, ImportPreview(
            success=False,
            error='Ova objava je već uvezena.'
        )

    preview = fetch_oembed(url)

    imp = SocialImport.objects.create(
        pet=pet,
        platform=platform,
        source_url=url,
        thumbnail_url=preview.thumbnail_url,
        caption=preview.caption,
        raw_data=preview.raw_data,
        status='pending',
    )

    # Async refresh u pozadini (ako sync nije uspio potpuno)
    if not preview.success:
        fetch_social_import.apply_async(args=[str(imp.id)], countdown=5)

    return imp, preview
```

---

## S2 — API Views (boxgram/views_social.py)

Novi fajl: `/var/www/fina-connect/boxgram/views_social.py`

```python
"""
Boxgram Social Import API Views
"""
import json
import logging
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404

from boxgram.models import PetProfile, SocialImport, LifeEvent
from boxgram.services.social_import import fetch_oembed, create_social_import

logger = logging.getLogger(__name__)


@login_required
@require_POST
def import_url_preview(request):
    """
    POST /api/boxgram/import/preview/
    Body: {"url": "https://www.tiktok.com/...", "pet_slug": "rudi-pas"}

    Vraca preview bez kreiranja zapisa — za prikaz korisniku prije potvrde.
    """
    try:
        data = json.loads(request.body)
        url = data.get('url', '').strip()
        pet_slug = data.get('pet_slug', '').strip()

        if not url:
            return JsonResponse({'success': False, 'error': 'URL je obavezan.'}, status=400)

        # Provjeri da korisnik posjeduje ovog ljubimca
        if pet_slug:
            pet = get_object_or_404(PetProfile, slug=pet_slug, owner=request.user)
        else:
            pet = None

        preview = fetch_oembed(url)

        return JsonResponse({
            'success': preview.success,
            'platform': preview.platform,
            'thumbnail_url': preview.thumbnail_url,
            'caption': preview.caption,
            'author_name': preview.author_name,
            'embed_html': preview.embed_html,
            'error': preview.error,
        })

    except Exception as e:
        logger.error(f'import_url_preview error: {e}')
        return JsonResponse({'success': False, 'error': 'Greška servera.'}, status=500)


@login_required
@require_POST
def import_url_confirm(request):
    """
    POST /api/boxgram/import/confirm/
    Body: {
        "url": "...",
        "pet_slug": "rudi-pas",
        "event_type": "milestone",
        "title": "Rudi na plaži",     # opcionalno, fallback na caption
        "date": "2026-03-15"          # opcionalno, fallback na danas
    }

    Kreira SocialImport + odmah odobrava (vlasnik potvrđuje = auto-approve).
    """
    try:
        data = json.loads(request.body)
        url = data.get('url', '').strip()
        pet_slug = data.get('pet_slug', '').strip()
        event_type = data.get('event_type', 'milestone')
        custom_title = data.get('title', '').strip()
        custom_date = data.get('date', '')

        if not url or not pet_slug:
            return JsonResponse({'success': False, 'error': 'url i pet_slug su obavezni.'}, status=400)

        pet = get_object_or_404(PetProfile, slug=pet_slug, owner=request.user)

        imp, preview = create_social_import(pet=pet, url=url, requested_by=request.user)

        if not preview.success and not imp:
            return JsonResponse({'success': False, 'error': preview.error}, status=400)

        # Auto-odobri jer vlasnik sam uvozi
        from django.utils import timezone
        import datetime

        event_date = datetime.date.today()
        if custom_date:
            try:
                event_date = datetime.date.fromisoformat(custom_date)
            except ValueError:
                pass

        title = custom_title or imp.caption or f'Objava s {imp.get_platform_display()}'

        life_event = LifeEvent.objects.create(
            pet=pet,
            event_type=event_type,
            title=title[:200],
            description=imp.caption,
            date=event_date,
            source=imp.platform,
            source_url=url,
            source_id=str(imp.pk),
            is_public=True,
        )

        imp.status = 'approved'
        imp.mapped_to = life_event
        imp.save(update_fields=['status', 'mapped_to'])

        return JsonResponse({
            'success': True,
            'event_id': str(life_event.id),
            'pet_slug': pet.slug,
            'redirect': f'/boxgram/ljubimac/{pet.slug}/',
        })

    except Exception as e:
        logger.error(f'import_url_confirm error: {e}')
        return JsonResponse({'success': False, 'error': 'Greška servera.'}, status=500)


@login_required
@require_GET
def import_inbox(request):
    """
    GET /api/boxgram/import/inbox/
    Lista pending SocialImport zapisa za korisnikove ljubimce.
    """
    pets = PetProfile.objects.filter(owner=request.user)
    pending = SocialImport.objects.filter(
        pet__in=pets,
        status='pending'
    ).select_related('pet').order_by('-created_at')[:20]

    return JsonResponse({
        'count': pending.count(),
        'items': [
            {
                'id': str(i.id),
                'pet_name': i.pet.name,
                'pet_slug': i.pet.slug,
                'platform': i.platform,
                'thumbnail_url': i.thumbnail_url,
                'caption': i.caption[:150],
                'source_url': i.source_url,
                'created_at': i.created_at.isoformat(),
            }
            for i in pending
        ]
    })


@login_required
@require_POST
def import_reject(request, import_id):
    """POST /api/boxgram/import/{id}/reject/"""
    pet_ids = PetProfile.objects.filter(owner=request.user).values_list('id', flat=True)
    imp = get_object_or_404(SocialImport, id=import_id, pet_id__in=pet_ids)
    imp.status = 'rejected'
    imp.save(update_fields=['status'])
    return JsonResponse({'success': True})
```

---

## S3 — URL rute (dodaj u boxgram/urls.py)

```python
from django.urls import path
from boxgram import views_social

urlpatterns += [
    # Social import
    path('api/boxgram/import/preview/',      views_social.import_url_preview,  name='boxgram_import_preview'),
    path('api/boxgram/import/confirm/',      views_social.import_url_confirm,  name='boxgram_import_confirm'),
    path('api/boxgram/import/inbox/',        views_social.import_inbox,        name='boxgram_import_inbox'),
    path('api/boxgram/import/<uuid:import_id>/reject/', views_social.import_reject, name='boxgram_import_reject'),
]
```

---

## S4 — Frontend: Import Wizard HTML template

Fajl: `boxgram/templates/boxgram/import_wizard.html`

```html
{% extends 'base.html' %}
{% block title %}Uvezi objavu — Boxgram{% endblock %}
{% block content %}

<div class="row justify-content-center">
<div class="col-12 col-md-7 col-lg-5">

<div class="stat-card">
  <h5 class="mb-1">📥 Uvezi objavu s društvenih mreža</h5>
  <p class="text-muted small mb-4">
    Zalijepi link objave s Facebooka, TikToka ili YouTubea.
    Objava se arhivira na profilu tvog ljubimca — zauvijek.
  </p>

  <!-- Korak 1: URL -->
  <div id="step1">
    <label class="form-label fw-bold">Link objave</label>
    <div class="input-group mb-2">
      <input type="url" id="importUrl" class="form-control"
             placeholder="https://www.tiktok.com/...">
      <button class="btn btn-warning" onclick="previewUrl()">Provjeri →</button>
    </div>
    <div class="d-flex gap-2 mb-3">
      <span class="badge bg-secondary">Facebook</span>
      <span class="badge bg-secondary">TikTok</span>
      <span class="badge bg-secondary">YouTube</span>
      <span class="badge bg-secondary opacity-50">Instagram (uskoro)</span>
    </div>
    <div id="previewError" class="alert alert-danger d-none small"></div>
  </div>

  <!-- Korak 2: Preview + potvrda -->
  <div id="step2" class="d-none">
    <div class="d-flex gap-3 align-items-start mb-3 p-3 border rounded-3">
      <img id="previewThumb" src="" alt="" style="width:80px;height:80px;object-fit:cover;border-radius:8px;">
      <div>
        <div id="previewPlatform" class="badge bg-warning text-dark mb-1"></div>
        <div id="previewCaption" class="small text-muted" style="max-height:60px;overflow:hidden;"></div>
      </div>
    </div>

    <!-- Za kojeg ljubimca -->
    <label class="form-label fw-bold">Za kojeg ljubimca?</label>
    <select id="petSelect" class="form-select mb-3">
      {% for pet in user_pets %}
      <option value="{{ pet.slug }}">{{ pet.name }} ({{ pet.get_species_display }})</option>
      {% endfor %}
    </select>

    <!-- Tip događaja -->
    <label class="form-label fw-bold">Tip događaja</label>
    <select id="eventType" class="form-select mb-3">
      <option value="milestone">Prekretnica / Poseban trenutak</option>
      <option value="natjecanje">Natjecanje</option>
      <option value="nagrada">Nagrada</option>
      <option value="vet">Vet posjet</option>
      <option value="ostalo">Ostalo</option>
    </select>

    <!-- Naslov (opcionalno) -->
    <label class="form-label fw-bold">Naslov <span class="text-muted fw-normal">(opcionalno)</span></label>
    <input type="text" id="eventTitle" class="form-control mb-3"
           placeholder="Ostavite prazno za automatski naslov">

    <!-- Datum -->
    <label class="form-label fw-bold">Datum objave</label>
    <input type="date" id="eventDate" class="form-control mb-4"
           value="{{ today }}">

    <div class="d-flex gap-2">
      <button class="btn btn-outline-secondary" onclick="resetWizard()">← Natrag</button>
      <button class="btn btn-warning flex-grow-1" onclick="confirmImport()">
        📌 Arhiviraj na profilu ljubimca
      </button>
    </div>
  </div>

  <!-- Korak 3: Uspjeh -->
  <div id="step3" class="d-none text-center py-4">
    <div style="font-size:3rem" class="mb-2">🐾</div>
    <h5 class="mb-1">Arhivirano!</h5>
    <p class="text-muted small mb-3">Objava je sačuvana na profilu ljubimca zauvijek.</p>
    <a id="profileLink" href="#" class="btn btn-warning">Pogledaj profil →</a>
  </div>

</div>
</div>
</div>

<script>
let currentUrl = '';

async function previewUrl() {
  const url = document.getElementById('importUrl').value.trim();
  if (!url) return;
  currentUrl = url;

  const btn = document.querySelector('#step1 button');
  btn.disabled = true;
  btn.textContent = 'Učitavam...';

  try {
    const r = await fetch('/api/boxgram/import/preview/', {
      method: 'POST',
      headers: {'Content-Type':'application/json','X-CSRFToken': getCsrf()},
      body: JSON.stringify({url})
    });
    const data = await r.json();

    if (data.success) {
      document.getElementById('previewThumb').src = data.thumbnail_url || '/static/boxgram/img/no-thumb.svg';
      document.getElementById('previewPlatform').textContent = data.platform.toUpperCase();
      document.getElementById('previewCaption').textContent = data.caption || 'Nema opisa';
      document.getElementById('step1').classList.add('d-none');
      document.getElementById('step2').classList.remove('d-none');
    } else {
      document.getElementById('previewError').textContent = data.error;
      document.getElementById('previewError').classList.remove('d-none');
    }
  } catch(e) {
    document.getElementById('previewError').textContent = 'Greška veze. Pokušaj ponovo.';
    document.getElementById('previewError').classList.remove('d-none');
  }

  btn.disabled = false;
  btn.textContent = 'Provjeri →';
}

async function confirmImport() {
  const btn = document.querySelector('#step2 .btn-warning');
  btn.disabled = true;
  btn.textContent = 'Arhiviram...';

  const r = await fetch('/api/boxgram/import/confirm/', {
    method: 'POST',
    headers: {'Content-Type':'application/json','X-CSRFToken': getCsrf()},
    body: JSON.stringify({
      url: currentUrl,
      pet_slug: document.getElementById('petSelect').value,
      event_type: document.getElementById('eventType').value,
      title: document.getElementById('eventTitle').value,
      date: document.getElementById('eventDate').value,
    })
  });
  const data = await r.json();

  if (data.success) {
    document.getElementById('profileLink').href = data.redirect;
    document.getElementById('step2').classList.add('d-none');
    document.getElementById('step3').classList.remove('d-none');
  } else {
    alert(data.error);
    btn.disabled = false;
    btn.textContent = '📌 Arhiviraj na profilu ljubimca';
  }
}

function resetWizard() {
  document.getElementById('step1').classList.remove('d-none');
  document.getElementById('step2').classList.add('d-none');
  document.getElementById('previewError').classList.add('d-none');
  document.getElementById('importUrl').value = '';
  currentUrl = '';
}

function getCsrf() {
  return document.cookie.split(';').find(c=>c.trim().startsWith('csrftoken='))?.split('=')[1] || '';
}
</script>
{% endblock %}
```

---

## S5 — Settings (core/settings.py)

Dodaj:
```python
# Boxgram Social Import
INSTAGRAM_OEMBED_TOKEN = env('INSTAGRAM_OEMBED_TOKEN', default='')
# Postavi u .env kada dobiješ Meta App token
# Bez tokena: Instagram import nedostupan, ostale platforme rade
```

U .env:
```
INSTAGRAM_OEMBED_TOKEN=
```

---

## S6 — Faza 2 placeholder (Meta App Review)

Fajl: `docs/BOXGRAM_META_APP_REVIEW.md`

```markdown
# Meta App Review — plan za Fazu 2

## Što treba
- Facebook Developer App (business.facebook.com)
- Permissions: pages_read_engagement, user_posts, instagram_basic
- App Review: ~2-4 tjedna nakon submita

## Kad pokrenuti review
- Nakon što Boxgram ima 10+ aktivnih korisnika
- Nakon što landing page memio.pet pokazuje jasnu svrhu

## Zaobilaznica (MVP)
- oEmbed radi bez review za javne objave
- Instagram: korisnik lijepi URL ručno, system ne fetch-a (IG blokira bez tokena)
- Facebook/TikTok/YouTube: odmah rade

## Kontakt
- Meta for Developers: developers.facebook.com
- App ID: (kreirati)
- Redirect URI: https://memio.pet/boxgram/oauth/facebook/callback/
```

---

## S7 — Tests

```python
# boxgram/tests/test_social_import.py
from django.test import TestCase, Client
from unittest.mock import patch, MagicMock
from boxgram.services.social_import import fetch_oembed, detect_platform, ImportPreview

class TestDetectPlatform(TestCase):
    def test_tiktok(self):
        self.assertEqual(detect_platform('https://www.tiktok.com/@user/video/123'), 'tiktok')

    def test_facebook(self):
        self.assertEqual(detect_platform('https://www.facebook.com/reel/123'), 'facebook')

    def test_youtube(self):
        self.assertEqual(detect_platform('https://youtu.be/abc123'), 'youtube')

    def test_unsupported(self):
        self.assertIsNone(detect_platform('https://twitter.com/user'))


class TestFetchOembed(TestCase):
    @patch('boxgram.services.social_import.requests.get')
    def test_tiktok_success(self, mock_get):
        mock_get.return_value = MagicMock(
            ok=True,
            json=lambda: {
                'title': 'Rudi na plaži',
                'thumbnail_url': 'https://cdn.tiktok.com/thumb.jpg',
                'author_name': '@rudipas',
                'html': '<iframe ...></iframe>'
            }
        )
        mock_get.return_value.raise_for_status = lambda: None

        result = fetch_oembed('https://www.tiktok.com/@rudipas/video/123')
        self.assertTrue(result.success)
        self.assertEqual(result.platform, 'tiktok')
        self.assertEqual(result.caption, 'Rudi na plaži')

    @patch('boxgram.services.social_import.requests.get')
    def test_timeout(self, mock_get):
        import requests
        mock_get.side_effect = requests.exceptions.Timeout()
        result = fetch_oembed('https://www.tiktok.com/@user/video/123')
        self.assertFalse(result.success)
        self.assertIn('ne odgovara', result.error)

    def test_unsupported_platform(self):
        result = fetch_oembed('https://twitter.com/user/status/123')
        self.assertFalse(result.success)
        self.assertIn('nije podržana', result.error)
```

---

## DONE kriterij

- [ ] `boxgram/services/` direktorij s `__init__.py` i `social_import.py`
- [ ] `fetch_oembed()` vraća ImportPreview za TikTok/FB/YouTube URLove
- [ ] `import_url_preview` endpoint vraća JSON preview
- [ ] `import_url_confirm` kreira LifeEvent i odobrava SocialImport
- [ ] `import_inbox` vraća listu pending importa
- [ ] Import Wizard template — 3 koraka, radi bez JS frameworka
- [ ] INSTAGRAM_OEMBED_TOKEN u settings + .env (prazno = Instagram disabled)
- [ ] Tests: min 5 test case-a, svi prolaze
- [ ] `docs/BOXGRAM_META_APP_REVIEW.md` kreiran
- [ ] Commit: "feat(boxgram): social import service — oEmbed FB/TikTok/YouTube"

## NAPOMENA
TikTok i YouTube rade odmah — testiraj s ovim URL-ovima:
- TikTok: https://www.tiktok.com/@khaby.lame/video/7009979597467136261
- YouTube: https://www.youtube.com/watch?v=dQw4w9WgXcQ
- Facebook: ovisi o privacy postavkama objave
Instagram: disabled dok nema Meta App tokena
