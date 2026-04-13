from django.urls import include, path
from rest_framework.routers import DefaultRouter
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

from . import views, wizard_views, portal_views

router = DefaultRouter()
router.register(r"api", views.PartnerViewSet, basename="partner")

app_name = "partners"
urlpatterns = [
    path("", views.partner_list, name="partner_list"),
    path("", views.partner_list, name="list"),
    path("new/", views.partner_create, name="create"),
    path("verify-buyer-type/", views.buyer_type_verify, name="buyer_type_verify"),
    path("<int:pk>/", views.partner_detail, name="detail"),
    path("<int:pk>/edit/", views.partner_edit, name="edit"),
    path("<int:pk>/delete/", views.partner_delete, name="delete"),
    path("api/quick-create/", views.partner_quick_create, name="quick_create"),
    path("api/oib-lookup/", views.partner_oib_lookup, name="oib_lookup"),
    path("", include(router.urls)),
    path("<int:partner_id>/send-portal-link/", portal_views.send_portal_link, name="send_portal_link"),
    path("<int:partner_id>/send-portal-whatsapp/", portal_views.send_portal_whatsapp, name="send_portal_whatsapp"),
    # Ured u džepu — onboarding wizard
    path("wizard/", wizard_views.wizard_view, name="wizard"),
    path("wizard/save-step/", wizard_views.wizard_save_step, name="wizard_save_step"),
    path("wizard/step-preview/", wizard_views.wizard_step_preview, name="wizard_step_preview"),
    path("wizard/reset/", wizard_views.wizard_reset, name="wizard_reset"),
    path("wizard/suglasnost-pdf/", wizard_views.wizard_suglasnost_pdf, name="wizard_suglasnost_pdf"),
    path("wizard/nkd-semantic/", wizard_views.wizard_nkd_semantic, name="wizard_nkd_semantic"),
]
