import logging
from datetime import datetime

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from boxgram.models import EventMedia, LifeEvent, PetProfile, SocialImport
from boxgram.serializers import LifeEventSerializer
from boxgram.services.social_import import create_social_import, fetch_oembed

logger = logging.getLogger(__name__)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def import_url_preview(request):
    """
    Preview socijalne objave bez kreiranja zapisa.

    POST /api/boxgram/import/preview/
    Body: {
        "url": "https://www.youtube.com/watch?v=...",
        "pet_slug": "fluffy" (optional)
    }
    """
    url = request.data.get("url", "").strip()

    if not url:
        return Response({"error": "URL je obavezan"}, status=status.HTTP_400_BAD_REQUEST)

    # Provjerava da URL počinje sa http/https
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    preview = fetch_oembed(url)

    return Response(
        {
            "success": preview.success,
            "platform": preview.platform,
            "source_url": preview.source_url,
            "thumbnail_url": preview.thumbnail_url,
            "caption": preview.caption,
            "author_name": preview.author_name,
            "error": preview.error,
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def import_url_confirm(request):
    """
    Potvrdi import i kreiraj LifeEvent.

    POST /api/boxgram/import/confirm/
    Body: {
        "url": "https://www.youtube.com/watch?v=...",
        "pet_slug": "fluffy",
        "event_type": "social_import",
        "title": "Moj ljubimac na YouTubeu (optional)",
        "date": "2026-04-05" (optional, default today)
    }
    """
    url = request.data.get("url", "").strip()
    pet_slug = request.data.get("pet_slug", "").strip()
    event_type = request.data.get("event_type", "social_import")
    title = request.data.get("title", "").strip()
    date_str = request.data.get("date")

    # Validacija
    if not url or not pet_slug:
        return Response({"error": "URL i pet_slug su obavezni"}, status=status.HTTP_400_BAD_REQUEST)

    # Dohvati pet
    pet = get_object_or_404(PetProfile, slug=pet_slug, owner=request.user)

    # Provjeri da je event_type valjan
    valid_event_types = [choice[0] for choice in LifeEvent._meta.get_field("event_type").choices]
    if event_type not in valid_event_types:
        event_type = "social_import"

    # Pripremi URL
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    # Kreiraj SocialImport i povuči preview
    social_import, preview = create_social_import(pet, url, request.user)

    if not preview.success:
        return Response(
            {"error": preview.error, "import_id": str(social_import.id)}, status=status.HTTP_400_BAD_REQUEST
        )

    # Pripremi datum
    if date_str:
        try:
            date = datetime.fromisoformat(date_str).date()
        except (ValueError, AttributeError):
            date = timezone.now().date()
    else:
        date = timezone.now().date()

    # Pripremi naslov
    if not title:
        title = preview.caption[:100] or f"Import sa {preview.platform.upper()}"

    # Kreiraj LifeEvent
    life_event = LifeEvent.objects.create(
        pet=pet,
        event_type=event_type,
        title=title,
        description=preview.caption or "",
        date=date,
        source="facebook" if preview.platform == "facebook" else preview.platform,
        source_url=url,
        is_public=True,
    )

    # Kreiraj EventMedia sa thumbnail-om
    if preview.thumbnail_url:
        EventMedia.objects.create(
            event=life_event, file_type="image", source_url=url, thumbnail_url=preview.thumbnail_url
        )

    # Mappiraj SocialImport na LifeEvent
    social_import.status = "approved"
    social_import.mapped_to = life_event
    social_import.save()

    logger.info(f"Social import approved: {social_import.id} -> Event: {life_event.id}")

    return Response(
        {
            "success": True,
            "import_id": str(social_import.id),
            "event_id": str(life_event.id),
            "event": LifeEventSerializer(life_event).data,
            "message": f"Objava je dodana na vremensku liniju za {pet.name}",
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def import_inbox(request):
    """
    Dohvati sve pending importa za korisnikove ljubimce.

    GET /api/boxgram/import/inbox/
    """
    # Dohvati sve pending importa za korisnikove love
    user_pets = PetProfile.objects.filter(owner=request.user)
    pending_imports = SocialImport.objects.filter(pet__in=user_pets, status="pending").order_by("-created_at")

    return Response(
        {
            "count": pending_imports.count(),
            "imports": [
                {
                    "id": str(imp.id),
                    "pet_slug": imp.pet.slug,
                    "pet_name": imp.pet.name,
                    "platform": imp.platform,
                    "source_url": imp.source_url,
                    "thumbnail": imp.raw_data.get("thumbnail_url"),
                    "caption": imp.raw_data.get("title", "")[:100],
                    "created_at": imp.created_at.isoformat(),
                }
                for imp in pending_imports
            ],
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def import_reject(request, import_id):
    """
    Odbij pending import.

    POST /api/boxgram/import/{import_id}/reject/
    """
    social_import = get_object_or_404(SocialImport, id=import_id)

    # Provjeri da je korisnik vlasnik ljubimca
    if social_import.pet.owner != request.user:
        return Response({"error": "Nemate dozvolu za ovu akciju"}, status=status.HTTP_403_FORBIDDEN)

    if social_import.status != "pending":
        return Response(
            {"error": f"Import je već u statusu {social_import.status}"}, status=status.HTTP_400_BAD_REQUEST
        )

    social_import.status = "rejected"
    social_import.save()

    logger.info(f"Social import rejected: {import_id}")

    return Response({"success": True, "message": "Import je odbijen"})
