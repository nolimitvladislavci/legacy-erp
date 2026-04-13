from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CompetitionViewSet,
    LifeEventViewSet,
    PetProfileViewSet,
    SocialImportViewSet,
    add_event_web,
    boxgram_landing,
    competition_detail,
    competition_vote_web,
    public_feed,
    public_profile,
)
from .views_social import import_inbox, import_reject, import_url_confirm, import_url_preview

app_name = "boxgram"

router = DefaultRouter()
router.register(r"pets", PetProfileViewSet, basename="pet")
router.register(r"events", LifeEventViewSet, basename="event")
router.register(r"competitions", CompetitionViewSet, basename="competition")
router.register(r"import", SocialImportViewSet, basename="socialimport")

urlpatterns = [
    path("", include(router.urls)),
    # Web routes
    path("ljubimac/<slug:slug>/", public_profile, name="public_profile"),
    path("ljubimac/<slug:slug>/dodaj/", add_event_web, name="add_event_web"),
    path("home/", boxgram_landing, name="landing"),
    path("feed/", public_feed, name="public_feed"),
    path("takmicenje/<uuid:competition_id>/", competition_detail, name="competition_detail"),
    path("takmicenje/<uuid:competition_id>/vote/", competition_vote_web, name="competition_vote_web"),
    # Social Import endpoints
    path("api/boxgram/import/preview/", import_url_preview, name="import_preview"),
    path("api/boxgram/import/confirm/", import_url_confirm, name="import_confirm"),
    path("api/boxgram/import/inbox/", import_inbox, name="import_inbox"),
    path("api/boxgram/import/<uuid:import_id>/reject/", import_reject, name="import_reject"),
]
