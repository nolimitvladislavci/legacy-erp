"""Propter URL routing."""

from django.urls import path

from . import views

app_name = "propter"

urlpatterns = [
    # Dashboard
    path("", views.dashboard, name="dashboard"),
    # BillingPeriod
    path("periods/", views.period_list, name="period_list"),
    path("periods/<int:pk>/", views.period_detail, name="period_detail"),
    path("periods/<int:pk>/close/", views.period_close, name="period_close"),
    path("periods/<int:pk>/aggregate/", views.period_aggregate, name="period_aggregate"),
    # Otpremnice
    path("otpremnice/", views.otpremnica_list, name="otpremnica_list"),
    path("otpremnice/create/", views.otpremnica_create, name="otpremnica_create"),
    path("otpremnice/<uuid:pk>/", views.otpremnica_detail, name="otpremnica_detail"),
    # EkoStats
    path("eko/", views.eko_dashboard, name="eko_dashboard"),
    path("eko/<int:year>/<int:month>/", views.eko_month, name="eko_month"),
    path("eko/pdf/", views.esg_pdf, name="esg_pdf_current"),
    path("eko/pdf/<int:year>/", views.esg_pdf, name="esg_pdf"),
    # Public eko page (no login)
    path("eko/public/<slug:slug>/", views.eko_public, name="eko_public"),
    # PropterTenant settings
    path("settings/", views.tenant_settings, name="tenant_settings"),
    # Propter Soba
    path("soba/", views.propter_soba, name="propter_soba"),
    # SaaS Landing (public)
    path("landing/", views.propter_landing, name="landing"),
    # API (za Synesis + vanjski pozivi)
    path("api/otpremnica/", views.api_create_otpremnica, name="api_create_otpremnica"),
    path("api/period/status/<int:pk>/", views.api_period_status, name="api_period_status"),
    # Fenix Inbox
    path("inbox/", views.fenix_inbox, name="fenix_inbox"),
    path("inbox/<int:item_id>/action/", views.fenix_inbox_action, name="fenix_inbox_action"),
]
