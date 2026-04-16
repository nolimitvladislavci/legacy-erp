from django.urls import path
from . import views

app_name = "identity"

urlpatterns = [
    path("", views.pristup_router, name="pristup"),
    path("pozivnica/<str:token>/", views.use_invite, name="use_invite"),
    path("zahtjev/", views.request_join, name="request_join"),
    path("admin/zahtjevi/", views.admin_pending_requests, name="admin_requests"),
    path("admin/zahtjevi/<uuid:request_id>/", views.resolve_request, name="resolve_request"),
]
