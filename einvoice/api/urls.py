from django.urls import path, include
from rest_framework.routers import DefaultRouter
from einvoice.api.views import AS4MessageViewSet, SmartMailboxViewSet, verify_archive

router = DefaultRouter()
router.register("messages", AS4MessageViewSet, basename="as4-message")
router.register("inbox", SmartMailboxViewSet, basename="smart-mailbox")

urlpatterns = [
    path("", include(router.urls)),
    path("archive/verify/<str:sha256_hash>/", verify_archive, name="archive-verify"),
]
