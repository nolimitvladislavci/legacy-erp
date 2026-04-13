import json
import logging

from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from .models import Competition, CompetitionEntry, CompetitionVote, EventMedia, LifeEvent, PetProfile, SocialImport
from .serializers import CompetitionSerializer, LifeEventSerializer, PetProfileSerializer, SocialImportSerializer
from .tasks import fetch_social_import, generate_pet_qr
from .throttles import ImportRateThrottle, VoteRateThrottle

logger = logging.getLogger(__name__)


class FeedPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


@extend_schema_view(list=extend_schema(tags=["Boxgram"]))
class PetProfileViewSet(viewsets.ModelViewSet):
    queryset = PetProfile.objects.all().select_related("tenant", "owner", "company")
    serializer_class = PetProfileSerializer
    lookup_field = "slug"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "breed", "bio", "location_city"]
    ordering_fields = ["created_at", "hearts_count", "followers_count"]
    ordering = ["-created_at"]

    def get_queryset(self):
        qs = PetProfile.objects.all().select_related("tenant", "owner", "company")

        if self.action == "feed":
            qs = qs.filter(is_public=True)
        elif self.request.user.is_authenticated:
            qs = qs.filter(owner=self.request.user)
        else:
            qs = qs.filter(is_public=True)

        # Filter po species i city
        species = self.request.query_params.get("species")
        city = self.request.query_params.get("city")
        if species:
            qs = qs.filter(species=species)
        if city:
            qs = qs.filter(location_city__icontains=city)

        return qs

    @action(detail=False, methods=["get"], permission_classes=[permissions.AllowAny])
    def feed(self, request):
        qs = self.filter_queryset(self.get_queryset())
        paginator = FeedPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = PetProfileSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @action(detail=True, methods=["get"], permission_classes=[permissions.AllowAny])
    def timeline(self, request, slug=None):
        pet = self.get_object()
        events = pet.life_events.filter(is_public=True).order_by("-date")
        paginator = FeedPagination()
        page = paginator.paginate_queryset(events, request)
        serializer = LifeEventSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @action(detail=True, methods=["post"])
    def add_event(self, request, slug=None):
        pet = self.get_object()
        if pet.owner != request.user:
            return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

        serializer = LifeEventSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(pet=pet)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["get"], permission_classes=[permissions.AllowAny])
    def qr(self, request, slug=None):
        pet = self.get_object()
        if not pet.qr_code:
            generate_pet_qr.delay(str(pet.id))
        return Response({"qr_url": pet.qr_code.url if pet.qr_code else None, "generating": not pet.qr_code})


@extend_schema_view(list=extend_schema(tags=["Boxgram"]))
class LifeEventViewSet(viewsets.ModelViewSet):
    queryset = LifeEvent.objects.all().select_related("pet")
    serializer_class = LifeEventSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["title", "description", "location"]
    ordering = ["-date"]


@extend_schema_view(list=extend_schema(tags=["Boxgram"]))
class CompetitionViewSet(viewsets.ModelViewSet):
    queryset = Competition.objects.all().select_related("tenant", "winner")
    serializer_class = CompetitionSerializer
    filter_backends = [filters.OrderingFilter]
    ordering = ["-start_date"]

    @action(
        detail=True, methods=["post"], throttle_classes=[VoteRateThrottle], permission_classes=[permissions.AllowAny]
    )
    def vote(self, request, pk=None):
        competition = self.get_object()
        entry_id = request.data.get("entry_id")

        try:
            entry = CompetitionEntry.objects.get(id=entry_id, competition=competition)
        except CompetitionEntry.DoesNotExist:
            return Response({"error": "Entry not found"}, status=status.HTTP_404_NOT_FOUND)

        voter_ip = self.get_client_ip(request)

        vote, created = CompetitionVote.objects.get_or_create(
            entry=entry,
            voter_ip=voter_ip,
            defaults={"voter_user": request.user if request.user.is_authenticated else None},
        )

        if created:
            entry.votes += 1
            entry.save(update_fields=["votes"])
            logger.info(f"Vote recorded for entry {entry_id} from IP {voter_ip}")

        return Response({"status": "success", "votes": entry.votes})

    @staticmethod
    def get_client_ip(request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0]
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip


@extend_schema_view(list=extend_schema(tags=["Boxgram"]))
class SocialImportViewSet(viewsets.ModelViewSet):
    queryset = SocialImport.objects.all().select_related("pet", "mapped_to")
    serializer_class = SocialImportSerializer
    throttle_classes = [ImportRateThrottle]

    @action(detail=False, methods=["post"])
    def import_url(self, request):
        url = request.data.get("url")
        if not url:
            return Response({"error": "URL required"}, status=status.HTTP_400_BAD_REQUEST)

        serializer = SocialImportSerializer(data=request.data)
        if serializer.is_valid():
            social_import = serializer.save()
            fetch_social_import.delay(str(social_import.id))
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        social_import = self.get_object()
        social_import.status = "approved"
        social_import.save()
        return Response({"status": "approved"})

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        social_import = self.get_object()
        social_import.status = "rejected"
        social_import.save()
        return Response({"status": "rejected"})


# ══════════════════════════════════════════════════════
# WEB VIEWS (Not REST API)
# ══════════════════════════════════════════════════════


def public_profile(request, slug):
    """Public pet profile page with timeline."""
    pet = get_object_or_404(PetProfile, slug=slug, is_public=True)
    events = pet.life_events.filter(is_public=True).order_by("-date")[:50]

    is_owner = request.user.is_authenticated and pet.owner == request.user
    context = {
        "pet": pet,
        "events": events,
        "is_owner": is_owner,
        "og_title": f"{pet.name} — memio.pet",
        "og_description": pet.bio[:160] if pet.bio else f"Pet profile: {pet.name}",
        "og_image": pet.avatar.url if pet.avatar else "",
    }
    return render(request, "boxgram/public_profile.html", context)


def public_feed(request):
    """Public feed with all pets, filterable by species."""
    species = request.GET.get("species", "")
    qs = PetProfile.objects.filter(is_public=True).select_related("tenant", "owner", "company").order_by("-updated_at")

    if species:
        qs = qs.filter(species=species)

    paginator = Paginator(qs, 20)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    from boxgram.models import SPECIES_CHOICES

    species_choices = SPECIES_CHOICES

    context = {
        "page_obj": page_obj,
        "species": species,
        "species_choices": species_choices,
    }
    # Standalone template za memio.pet, LIMIT Connect base za ostalo
    host = request.get_host()
    if "memio.pet" in host:
        template = "boxgram/feed_standalone.html"
    else:
        template = "boxgram/feed.html"
    return render(request, template, context)


def competition_detail(request, competition_id):
    """Competition detail page with live leaderboard."""
    comp = get_object_or_404(Competition, id=competition_id)
    entries = comp.entries.select_related("pet").order_by("-votes")

    context = {
        "competition": comp,
        "entries": entries,
    }
    return render(request, "boxgram/competition_detail.html", context)


@require_POST
def competition_vote_web(request, competition_id):
    """AJAX endpoint for competition voting with IP limit."""
    comp = get_object_or_404(Competition, id=competition_id, status="active")

    try:
        data = json.loads(request.body)
        entry_id = data.get("entry_id")
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON"}, status=400)

    entry = get_object_or_404(CompetitionEntry, id=entry_id, competition=comp)

    ip = request.META.get("HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR", ""))
    if "," in ip:
        ip = ip.split(",")[0].strip()

    if CompetitionVote.objects.filter(entry=entry, voter_ip=ip).select_related("entry", "voter_user").exists():
        return JsonResponse({"success": False, "error": "Već ste glasali."})

    CompetitionVote.objects.create(
        entry=entry, voter_ip=ip, voter_user=request.user if request.user.is_authenticated else None
    )
    entry.votes += 1
    entry.save(update_fields=["votes"])

    return JsonResponse({"success": True, "votes": entry.votes})


@require_POST
def add_event_web(request, slug):
    """Web endpoint za dodavanje LifeEventa s media uploadom (FenixCamera)."""
    import datetime

    if not request.user.is_authenticated:
        return JsonResponse({"success": False, "error": "Prijavi se."}, status=401)

    pet = get_object_or_404(PetProfile, slug=slug, owner=request.user)

    title = request.POST.get("title", "").strip()
    event_type = request.POST.get("event_type", "ostalo")
    date_str = request.POST.get("date", "")
    description = request.POST.get("description", "").strip()

    if not title:
        return JsonResponse({"success": False, "error": "Naslov je obavezan."}, status=400)

    try:
        event_date = datetime.date.fromisoformat(date_str) if date_str else datetime.date.today()
    except ValueError:
        event_date = datetime.date.today()

    event = LifeEvent.objects.create(
        pet=pet,
        event_type=event_type,
        title=title,
        description=description,
        date=event_date,
        source="manual",
        is_public=True,
    )

    # Media upload — FenixCamera šalje kao file
    for f in request.FILES.getlist("media"):
        file_type = "photo"
        if f.content_type and "video" in f.content_type:
            file_type = "video"
        EventMedia.objects.create(
            event=event,
            file=f,
            file_type=file_type,
        )

    return JsonResponse(
        {
            "success": True,
            "event_id": str(event.id),
            "redirect": f"/boxgram/ljubimac/{pet.slug}/",
        }
    )


def boxgram_landing(request):
    """Boxgram landing page — digitalni život tvog ljubimca."""
    recent_pets = (
        PetProfile.objects.filter(is_public=True)
        .select_related("tenant", "owner", "company")
        .order_by("-updated_at")[:6]
    )
    total_pets = PetProfile.objects.filter(is_public=True).select_related("tenant", "owner", "company").count()
    context = {
        "recent_pets": recent_pets,
        "total_pets": total_pets,
    }
    return render(request, "boxgram/landing.html", context)
