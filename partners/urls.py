from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views, portal_views

router = DefaultRouter()
router.register(r"api", views.PartnerViewSet, basename="partner")

app_name = "partners"
urlpatterns = [
    path("", views.partner_list, name="list"),
    path("new/", views.partner_create, name="create"),
    path("<int:pk>/", views.partner_detail, name="detail"),
    path("<int:pk>/edit/", views.partner_edit, name="edit"),
    path("<int:pk>/delete/", views.partner_delete, name="delete"),
    path("api/quick-create/", views.partner_quick_create, name="quick_create"),
    path("api/oib-lookup/", views.partner_oib_lookup, name="oib_lookup"),
    path("", include(router.urls)),
    path("<int:partner_id>/send-portal-link/", portal_views.send_portal_link, name="send_portal_link"),
    path("<int:partner_id>/send-portal-whatsapp/", portal_views.send_portal_whatsapp, name="send_portal_whatsapp"),
]

