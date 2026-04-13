from django.urls import path
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
from . import views
from . import views_pets

app_name = "livestock"

urlpatterns = [
    path('gospodarstvo/', views.farm_list, name='farm_list'),
    path('gospodarstvo/novo/', views.farm_register, name='farm_register'),

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

    # ── Kućni ljubimci / uzgajalište ──────────────────────────────────
    path('pets/', views_pets.pet_list, name='pet_list'),
    path('pets/create/', views_pets.pet_create, name='pet_create'),
    path('pets/<int:pk>/', views_pets.pet_detail, name='pet_detail'),
    path('pets/<int:pk>/edit/', views_pets.pet_edit, name='pet_edit'),
    path('pets/<int:pk>/pdf/', views_pets.pet_pedigree_pdf, name='pet_pedigree_pdf'),
    path('pets/api/scan-photo/', views_pets.pet_scan_photo, name='pet_scan_photo'),
    path('pets/<int:pk>/qr/', views_pets.pet_qr_code, name='pet_qr_code'),
    path('pets/<int:pk>/adopt/', views_pets.pet_adopt, name='pet_adopt'),
    path('pets/<int:pk>/contract/', views_pets.pet_adoption_contract, name='pet_adoption_contract'),
]
