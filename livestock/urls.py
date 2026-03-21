from django.urls import path
from . import views

app_name = "livestock"

urlpatterns = [
    path("", views.livestock_list, name="list"),
    path("<int:pk>/", views.livestock_detail, name="detail"),
    path("create/", views.livestock_create, name="create"),
    path("fields/", views.field_list, name="field_list"),
    path("crops/", views.crop_list, name="crop_list"),

    # Public vet entry (no login)
    path("vet/<str:farm_token>/", views.vet_quick_entry, name="vet_quick_entry"),

    # Vet dashboard (login required)
    path("vet-dashboard/", views.vet_dashboard, name="vet_dashboard"),

    # Robot API (token auth)
    path("api/identify/", views.robot_identify, name="robot_identify"),
]
