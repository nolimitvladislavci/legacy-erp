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

    path('api/institutional/<str:scope>/', views.institutional_api, name='institutional_api'),
    path('tokens/', views.token_management, name='token_management'),

    # Inspektorski mod
    path('inspect/<str:scope>/<str:token>/', views.inspector_live_view, name='inspector_live_view'),
    path('inspekcija/', views.inspector_panic_button, name='panic_button'),
    path('inspekcija/pdf/', views.generate_inspection_pdf, name='inspection_pdf'),
]
