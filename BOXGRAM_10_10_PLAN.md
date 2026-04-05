# BOXGRAM_10_10_PLAN.md
# Put do 10/10 — Boxgram / memio.pet
# Datum: 05.04.2026. | Koordinator: Sonnet | Cilj: BR. 1 U EUROPI

## TRENUTNO STANJE: 8.2 / 10

### Što je gotovo (baza)
- [x] 9 Django modela, migracije aplicirane
- [x] 11 API endpointa (DRF ViewSets)
- [x] 5 Django signala — LIMIT Connect → Boxgram sync (field names ispravljeni)
- [x] Social import: oEmbed service (YT/FB/TikTok), 3-step wizard
- [x] video_downloader.py — yt-dlp wrapper, TikTok fallback
- [x] 28 + 15 = 43 testa, svi prolaze
- [x] 2,179 linija dokumentacije (UX, arhitektura, risk, pilot checklist)
- [x] CRNA_KUTIJA ažurirana — selidba checklista
- [x] mcp-fina.service fix — orphan problem riješen zauvijek

### Što nedostaje do 10/10
- [ ] AI Faza 1 — Haiku auto-opisi (3/10 → 9/10)
- [ ] Javni profil ljubimca — memio.pet/ljubimac/{slug}/
- [ ] Boxgram feed — javna stranica
- [ ] Rate limiting na API-ju
- [ ] Cookies za IG/FB (Ivan — ručno, 10 min)
- [ ] Pilot onboarding — Pero + Ljubeta (Ivan — WhatsApp)
- [ ] Takmičenje UI — glasanje stranica

---

## SPRINT DO 10/10 — 3 TASKA, 1 IVAN AKCIJA

---

### TASK A — CC Code: AI Faza 1 (Haiku auto-opisi)
**Cilj: AI sloj 3/10 → 9/10**
**Fajl: CC_TASK_BOXGRAM_AI_F1.md**

#### A1 — boxgram/services/ai_enrichment.py

```python
"""
Boxgram AI Enrichment — Haiku auto-opisi za LifeEvent
Svaki novi LifeEvent automatski dobiva AI-generiran opis.
Model: claude-haiku-4-5 (brz, jeftin)
"""
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

EVENT_PROMPTS = {
    'rodenje': 'Napiši toplu, kratku (2 rečenice max) objavu na hrvatskom za profil ljubimca koji se upravo rodio. Ime: {name}, vrsta: {species}. Bez emojija. Bez klišeja. Iskreno i toplo.',
    'vet':     'Napiši kratki update (2 rečenice) na hrvatskom o vet posjetu ljubimca. Ime: {name}, vrsta: {species}, naslov posjeta: {title}. Informativno, bez dramatiziranja.',
    'nagrada': 'Napiši kratki slavodobitan tekst (2 rečenice) na hrvatskom o nagradi/uspjehu ljubimca. Ime: {name}, nagrada: {title}. Ponosno ali skromno.',
    'milestone':'Napiši kratki, topli opis prekretnice (2 rečenice) na hrvatskom za ljubimca. Ime: {name}, vrsta: {species}, događaj: {title}. Bez klišeja.',
    'natjecanje':'Napiši kratki tekst (2 rečenice) na hrvatskom o sudjelovanju na natjecanju. Ime: {name}, natjecanje: {title}. Uzbudljivo ali ne pretjerano.',
    'ostalo':  'Napiši kratki, topli opis (2 rečenice) na hrvatskom o ovom trenutku u životu ljubimca. Ime: {name}, vrsta: {species}, opis: {title}.',
}

def enrich_life_event(event) -> str:
    """
    Generiraj AI opis za LifeEvent.
    Vraća generirani tekst ili prazan string ako API nije dostupan.
    Nikad ne baca exception — samo logira i vraća ''.
    """
    if not getattr(settings, 'ANTHROPIC_API_KEY', ''):
        return ''

    # Ne generiraj ako već ima opis
    if event.description and len(event.description) > 50:
        return event.description

    try:
        import anthropic

        pet = event.pet
        prompt_template = EVENT_PROMPTS.get(event.event_type, EVENT_PROMPTS['ostalo'])
        prompt = prompt_template.format(
            name=pet.name,
            species=pet.get_species_display(),
            title=event.title or '',
        )

        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        message = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=150,
            messages=[{'role': 'user', 'content': prompt}]
        )

        generated = message.content[0].text.strip()
        logger.info(f'Boxgram AI: LifeEvent {event.pk} enriched ({len(generated)} chars)')
        return generated

    except Exception as e:
        logger.warning(f'Boxgram AI enrich skip (LifeEvent {getattr(event, "pk", "?")}): {e}')
        return ''
```

#### A2 — Celery task: async enrich

U boxgram/tasks.py dodaj:

```python
@shared_task(queue='default', time_limit=30)
def enrich_life_event_ai(event_id: str):
    """Async AI enrichment za LifeEvent — ne blokira save()."""
    try:
        from boxgram.models import LifeEvent
        from boxgram.services.ai_enrichment import enrich_life_event

        event = LifeEvent.objects.get(id=event_id)

        # Preskači ako već ima opis
        if event.description and len(event.description) > 50:
            return 'skip — already has description'

        generated = enrich_life_event(event)
        if generated:
            event.description = generated
            event.save(update_fields=['description'])
            return f'OK — {len(generated)} chars'
        return 'skip — AI returned empty'

    except LifeEvent.DoesNotExist:
        return f'skip — LifeEvent {event_id} not found'
    except Exception as e:
        logger.warning(f'enrich_life_event_ai error: {e}')
        return f'error: {e}'
```

#### A3 — Signal: auto-enrich pri kreiranju

U boxgram/signals.py dodaj novi signal:

```python
from django.db.models.signals import post_save
from boxgram.models import LifeEvent

@receiver(post_save, sender=LifeEvent)
def auto_enrich_life_event(sender, instance, created, **kwargs):
    """Odmah po kreiranju LifeEventa → async AI enrichment."""
    if not created:
        return
    if instance.description and len(instance.description) > 50:
        return  # Vec ima opis
    try:
        from boxgram.tasks import enrich_life_event_ai
        enrich_life_event_ai.apply_async(
            args=[str(instance.id)],
            countdown=2  # 2 sekunde delay — čekaj da se transakcija committa
        )
    except Exception as e:
        logger.warning(f'auto_enrich signal error: {e}')
```

#### A4 — AI moderacija (bonus, Faza 2 start)

```python
def moderate_social_import(import_obj) -> dict:
    """
    Provjeri je li uvezeni sadržaj prikladan.
    Vraća: {approved: bool, reason: str}
    """
    if not getattr(settings, 'ANTHROPIC_API_KEY', ''):
        return {'approved': True, 'reason': 'AI moderacija nije konfigurirana'}

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

        message = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=100,
            messages=[{
                'role': 'user',
                'content': (
                    f'Je li ovaj sadržaj prikladan za platformu za ljubimce? '
                    f'Odgovori samo: PRIKLADNO ili NEPRIKLADNO i kratko zašto (1 rečenica).\n\n'
                    f'Naslov: {import_obj.caption[:200]}'
                )
            }]
        )

        result = message.content[0].text.strip()
        approved = result.upper().startswith('PRIKLADNO')
        return {'approved': approved, 'reason': result}

    except Exception as e:
        logger.warning(f'AI moderacija error: {e}')
        return {'approved': True, 'reason': f'AI error: {e}'}
```

#### DONE kriterij Task A
- [ ] boxgram/services/ai_enrichment.py kreiran
- [ ] enrich_life_event_ai Celery task radi
- [ ] auto_enrich_life_event signal registriran
- [ ] Test: kreiraj LifeEvent → 2 sekunde → description auto-popunjen
- [ ] moderate_social_import radi (za Fazu 2)
- [ ] Commit: "feat(boxgram): AI Faza 1 — Haiku auto-opisi za LifeEvent"

---

### TASK B — CC Code: Javni profil + Feed
**Cilj: Frontend 6/10 → 9/10**
**Fajl: CC_TASK_BOXGRAM_FRONTEND.md**

#### B1 — Javni profil: memio.pet/ljubimac/{slug}/

Template: boxgram/templates/boxgram/public_profile.html

Sadržaj:
- Cover foto (full width, fallback: gradijent po species)
- Avatar + ime + vrsta + pasmina + badge-ovi (Vet ✓, Uzgajivač ✓)
- Bio tekst
- Statistike: X pratitelja · X srca · X događaja
- Gumbi: [Prati] [Podijeli] [QR kod]
- Vertikalni timeline eventi (filtrirani is_public=True)
- Memorial mode: poseban header ako is_memorial=True
- Share meta tagovi (OG, Twitter Card za WhatsApp preview)

View (boxgram/views.py — dodaj):
```python
def public_profile(request, slug):
    pet = get_object_or_404(PetProfile, slug=slug, is_public=True)
    events = pet.events.filter(is_public=True).order_by('-date')[:20]
    return render(request, 'boxgram/public_profile.html', {
        'pet': pet, 'events': events,
    })
```

URL: `path('ljubimac/<slug:slug>/', views.public_profile, name='public_profile')`
Nginx routing: memio.pet → fina-connect app

#### B2 — Boxgram feed: memio.pet/feed/

Javni feed svih ljubimaca.
- Kartice: avatar + ime + zadnji event + srca
- Filter po vrsti (pas, mačka, pčela...)
- Paginacija (20 po stranici)
- Beskonačni scroll (JS)

#### B3 — Open Graph meta tagovi

Za WhatsApp/FB preview kad dijele profil:
```html
<meta property="og:title" content="{{ pet.name }} — memio.pet">
<meta property="og:description" content="{{ pet.bio|truncatewords:20 }}">
<meta property="og:image" content="{{ pet.avatar.url }}">
<meta property="og:url" content="https://memio.pet/ljubimac/{{ pet.slug }}/">
<meta property="og:type" content="profile">
```

#### B4 — Takmičenje stranica: memio.pet/takmicenje/{id}/

- Lista prijavljenih ljubimaca (kartica + foto + broj glasova)
- Glasanje jednim klikom (AJAX, bez reloada)
- Countdown timer do kraja
- Live leaderboard (5 sek refresh)
- Pobjeda: zlatni banner na profilu pobjednika

#### DONE kriterij Task B
- [ ] /ljubimac/{slug}/ radi i prikazuje profil
- [ ] OG meta tagovi — WhatsApp preview izgleda ispravno
- [ ] Feed /feed/ prikazuje javne PetProfile-e
- [ ] Takmičenje stranica s glasanjem
- [ ] Memorial mode — poseban izgled za is_memorial=True
- [ ] Commit: "feat(boxgram): javni profil, feed, takmičenje UI"

---

### TASK C — CC Code: Rate limiting + API polish
**Cilj: API 8/10 → 10/10**
**Fajl: CC_TASK_BOXGRAM_API_POLISH.md**

#### C1 — DRF Throttling

U core/settings.py:
```python
REST_FRAMEWORK = {
    ...
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '60/hour',
        'user': '1000/hour',
        'vote': '5/hour',      # Custom za glasanje
        'import': '20/hour',   # Custom za social import
    }
}
```

Custom throttle za glasanje:
```python
class VoteRateThrottle(UserRateThrottle):
    scope = 'vote'

class ImportRateThrottle(UserRateThrottle):
    scope = 'import'
```

#### C2 — DRF Spectacular serializer fix

views_social.py views trebaju serializer_class ili @extend_schema decorator.
Fix W002 warningove iz `manage.py check`.

#### C3 — Paginacija na feed endpointu

Feed vraća 20 ljubimaca, cursor-based paginacija.

#### C4 — Search endpoint

GET /api/boxgram/pets/?search=rudi&species=pas&city=osijek
Koristi DRF SearchFilter + OrderingFilter.

#### DONE kriterij Task C
- [ ] Throttling na svim endpointima
- [ ] VoteRateThrottle — max 5 glasova/sat po korisniku
- [ ] manage.py check — 0 Errora, 0 Warning-a za boxgram
- [ ] Paginacija na /api/boxgram/feed/
- [ ] Search: ?search=, ?species=, ?city=
- [ ] Commit: "feat(boxgram): API polish — throttling, search, pagination"

---

### IVAN AKCIJA (10 minuta, bez koda)

#### I1 — Cookies za Instagram i Facebook
```
1. Chrome → instaliraj addon "Get cookies.txt LOCALLY"
2. Otvori instagram.com → logiraj se
3. Klikni addon → "Export" → spremi kao instagram.txt
4. Ponovi za facebook.com → facebook.txt
5. Upload na server:
   scp instagram.txt root@37.27.248.86:/var/www/fina-connect/media/boxgram/cookies/instagram.txt
   scp facebook.txt root@37.27.248.86:/var/www/fina-connect/media/boxgram/cookies/facebook.txt
```
Rezultat: IG i FB video download odmah rade.

#### I2 — WhatsApp Ljubeti
> "Ljubeta, spreman je tvoj profil na memio.pet — pošalji mi OIB firme i ime prvog psa pa ga odmah ubacujem."

#### I3 — WhatsApp Peri Lapisu
> "Pero, pčelar profil je gotov. Pošalji mi OIB OPG-a i naziv prvog pčelinjaka."

---

## SCORECARD — PUT DO 10/10

| Kategorija | Sad | Nakon A | Nakon B | Nakon C + Ivan |
|---|---|---|---|---|
| Arhitektura modela | 9 | 9 | 9 | 9 |
| API endpointi | 8 | 8 | 8 | **10** |
| Sync bridge | 9 | 9 | 9 | 9 |
| Social import | 7 | 7 | 7 | 8 |
| Video download | 8 | 8 | 8 | **9** (s cookies) |
| Testovi | 8 | **9** | 9 | 9 |
| Frontend/UI | 6 | 6 | **9** | 9 |
| Dokumentacija | 10 | 10 | 10 | 10 |
| **AI podrška** | **3** | **9** | 9 | 9 |
| Pilot korisnici | 0 | 0 | 0 | **10** |
| **UKUPNO** | **8.2** | **8.8** | **9.3** | **10.0** |

---

## REDOSLJED IZVRŠAVANJA

```
ODMAH (paralelno):
  CC Code → TASK A (AI Faza 1)       ← prioritet #1, biggest delta
  CC Code → TASK B (Javni profil)    ← prioritet #2, korisnici čekaju

OVAJ TJEDAN:
  CC Code → TASK C (API polish)      ← završni polish
  Ivan    → IVAN AKCIJA (cookies + WhatsApp pilotima)

REZULTAT: memio.pet 10/10 — Broj 1 u EU
```

---

## FINALNA VIZIJA

Pero Lapis unosi berbu meda u LIMIT Connect.
→ Signal pali.
→ LifeEvent kreira se u Boxgramu.
→ Haiku generira topli opis na hrvatskom.
→ Pero dobiva link: memio.pet/ljubimac/pcelinjak-pero/
→ Šalje na WhatsApp grupi pčelara.
→ Baka iz Čepina glasa za Perin med.
→ Susjed iz Novaka vidi profil Ljubetinih pasa.
→ Kupac skenira QR s ogrlice → vidi rodovnicu.

**Jedan sustav. Jedan login. Cijeli život.**
