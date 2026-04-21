"""
Fenix v3 — URL Configuration
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect
from django.http import JsonResponse


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", lambda r: redirect("accounts:dashboard"), name="root"),
    path("", include("accounts.urls")),
    path("kompanije/", include("companies.urls")),
    path("racuni/", include("invoicing.urls")),
    path("arhiva/", include("arhiva.urls")),
    path("stolarija/", include("stolarija.urls")),
    path("pos/", include("pos.urls")),
    path("health/", lambda r: JsonResponse({"status": "ok", "version": "3.0"})),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
