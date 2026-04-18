"""Fenix v3 — Arhiva URLs | PLAN_025-032"""
from django.urls import path
from . import views

app_name = "arhiva"

urlpatterns = [
    # Authenticated — knjigov.
    path("", views.ArhivaListView.as_view(), name="list"),
    path("upload/", views.ArhivaUploadView.as_view(), name="upload"),
    path("<uuid:pk>/", views.ArhivaDetailView.as_view(), name="detail"),
    path("<uuid:pk>/status/", views.ArhivaScanStatusView.as_view(), name="scan_status"),
    path("scan-tokeni/", views.ArhivaScanTokenListView.as_view(), name="scan_tokens"),
]

# Public routes (bez login-a) — registrirane u core/urls_pub.py
public_urlpatterns = [
    path("scan/<str:token>/", views.ArhivaMobileScanView.as_view(), name="mobile_scan"),
    path("portal/<str:token>/", views.ArhivaPortalView.as_view(), name="portal"),
    # PLAN_032 — WAHA webhook (bez logina, HMAC opcionalan)
    path("wh/waha/", views.ArhivaWAHAWebhookView.as_view(), name="waha_webhook"),
]
