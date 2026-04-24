"""
/var/www/fina-connect/memio_pet/ai_views.py
PLAN-013: AI media za memio.pet
- POST /memio/ai/breed/ — foto → JSON analiza (rasa, vrsta, zdravlje)
- POST /memio/ai/transcribe/ — audio → tekst transkript
- GET  /memio/ai/status/ — koji AI provideri su dostupni

Globalno dostupno, poziva se po potrebi.
Fallback lanac: Sonnet Vision → Gemini → offline poruka.
"""
import json
import logging
import base64

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

logger = logging.getLogger(__name__)

# ── AI helpers (direktno Anthropic + Gemini, fina-connect nema ai_gateway) ─────

def _call_vision(image_bytes: bytes, prompt: str, mime_type: str = "image/jpeg") -> dict:
    """Sonnet vision → Gemini vision → offline."""
    from django.conf import settings

    # 1. Sonnet vision
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        b64 = base64.standard_b64encode(image_bytes).decode()
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": mime_type, "data": b64}},
                {"type": "text", "text": prompt},
            ]}],
        )
        return {"ok": True, "content": msg.content[0].text, "provider": "sonnet"}
    except Exception as e:
        logger.warning("AI media Sonnet greska: %s", e)

    # 2. Gemini vision fallback
    try:
        import httpx
        api_key = settings.GEMINI_API_KEY
        b64 = base64.standard_b64encode(image_bytes).decode()
        resp = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}",
            json={"contents": [{"parts": [
                {"inlineData": {"mimeType": mime_type, "data": b64}},
                {"text": prompt},
            ]}]},
            timeout=60,
        )
        resp.raise_for_status()
        parts = resp.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
        content = parts[0].get("text", "") if parts else ""
        return {"ok": True, "content": content, "provider": "gemini"}
    except Exception as e:
        logger.warning("AI media Gemini vision greska: %s", e)

    return {"ok": False, "content": "", "provider": "offline",
            "error": "Svi vision provideri nedostupni — pokusaj ponovo"}


def _call_transcribe(audio_bytes: bytes, mime_type: str = "audio/mpeg", language: str = "hr") -> dict:
    """Gemini audio → tekst."""
    from django.conf import settings
    import httpx
    try:
        api_key = settings.GEMINI_API_KEY
        b64 = base64.standard_b64encode(audio_bytes).decode()
        resp = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}",
            json={"contents": [{"parts": [
                {"inlineData": {"mimeType": mime_type, "data": b64}},
                {"text": f"Transkribiraj audio na jeziku: {language}. Samo tekst, bez komentara."},
            ]}]},
            timeout=120,
        )
        resp.raise_for_status()
        parts = resp.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
        content = parts[0].get("text", "") if parts else ""
        if not content:
            raise ValueError("Prazan transkript")
        return {"ok": True, "content": content, "provider": "gemini"}
    except Exception as e:
        logger.warning("AI media transcribe greska: %s", e)
        return {"ok": False, "content": "", "provider": "offline",
                "error": f"Transkripcija neuspjesna: {e}"}


# ── Views ───────────────────────────────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["POST"])
def breed_detect(request):
    """
    POST /memio/ai/breed/
    Body: multipart s poljem 'photo' (slika zivotinje)
    Vraca JSON: vrsta, rasa, spol, procjena_dobi, zdravlje, povjerenje
    """
    photo = request.FILES.get("photo")
    if not photo:
        return JsonResponse({"error": "Nedostaje polje 'photo'"}, status=400)

    max_size = 10 * 1024 * 1024  # 10MB
    if photo.size > max_size:
        return JsonResponse({"error": "Slika prevelika (max 10MB)"}, status=400)

    image_bytes = photo.read()
    mime_type = photo.content_type or "image/jpeg"

    prompt = (
        "Analiziraj fotografiju zivotinje. Vrati SAMO validan JSON bez markdowna:\n"
        '{"vrsta":"pas/macka/konj/govedo/ostalo","rasa":"naziv rase ili Unknown",'
        '"spol":"muzjak/zenska/nepoznato","procjena_dobi":"npr. 2-3 godine",'
        '"zdravlje":"zdravo/moguce_ozljede/potreban_pregled",'
        '"povjerenje":0.85,"napomena":"kratka napomena"}'
    )

    result = _call_vision(image_bytes, prompt, mime_type)

    if not result["ok"]:
        return JsonResponse({
            "ok": False,
            "provider": result["provider"],
            "error": result.get("error", "Greska"),
        }, status=503)

    # Pokusaj parsirati JSON iz AI odgovora
    content = result["content"]
    animal_data = {}
    try:
        # Izdvoji JSON iz odgovora (AI ponekad dodaje tekst oko JSON-a)
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            animal_data = json.loads(content[start:end])
    except json.JSONDecodeError:
        animal_data = {"napomena": content}

    # Ako je zadana zivotinja u URL parametru, azuriraj breed polje
    ear_tag = request.POST.get("ear_tag") or request.GET.get("ear_tag")
    if ear_tag and animal_data.get("rasa"):
        try:
            from memio_pet.models import AnimalProfile
            animal = AnimalProfile.objects.using("memio_pets").filter(ear_tag=ear_tag).first()
            if animal and not animal.breed:
                animal.breed = animal_data["rasa"]
                animal.save(using="memio_pets")
                animal_data["breed_updated"] = True
        except Exception as e:
            logger.warning("AI breed update greska: %s", e)

    return JsonResponse({
        "ok": True,
        "provider": result["provider"],
        **animal_data,
    })


@csrf_exempt
@require_http_methods(["POST"])
def transcribe_audio(request):
    """
    POST /memio/ai/transcribe/
    Body: multipart s poljem 'audio'
    Vraca JSON: transcript (tekst)
    """
    audio = request.FILES.get("audio")
    if not audio:
        return JsonResponse({"error": "Nedostaje polje 'audio'"}, status=400)

    max_size = 20 * 1024 * 1024  # 20MB
    if audio.size > max_size:
        return JsonResponse({"error": "Audio prevelik (max 20MB)"}, status=400)

    audio_bytes = audio.read()
    mime_type = audio.content_type or "audio/mpeg"
    language = request.POST.get("language", "hr")

    result = _call_transcribe(audio_bytes, mime_type, language)

    if not result["ok"]:
        return JsonResponse({
            "ok": False,
            "provider": result["provider"],
            "error": result.get("error", "Greska"),
        }, status=503)

    return JsonResponse({
        "ok": True,
        "provider": result["provider"],
        "transcript": result["content"],
    })


@require_http_methods(["GET"])
def ai_status(request):
    """
    GET /memio/ai/status/
    Vraca koji AI provideri su dostupni (bez testnog poziva — samo cache stanje).
    """
    from django.conf import settings
    import datetime

    haiku_blocked = datetime.date.today() < datetime.date(2026, 5, 1)

    return JsonResponse({
        "providers": {
            "sonnet_vision": bool(getattr(settings, "ANTHROPIC_API_KEY", "")),
            "gemini": bool(getattr(settings, "GEMINI_API_KEY", "")),
            "haiku": not haiku_blocked,
        },
        "haiku_blocked_until": "2026-05-01" if haiku_blocked else None,
        "features": {
            "breed_detect": "POST /ai/breed/",
            "transcribe": "POST /ai/transcribe/",
        },
    })
