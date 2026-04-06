"""
memio_pet/urls.py -- URL routing za memio.pet public views
"""
from django.urls import path
from memio_pet import views

app_name = "memio_pet"

urlpatterns = [
    path("", views.landing_page, name="landing"),
    path("pas/<str:chip_or_tag>/", views.pet_profile_page, name="pet_profile"),
    path("pas/<str:chip_or_tag>/qr/", views.pet_qr_code, name="pet_qr"),
    path("uzgajivac/<uuid:breeder_id>/", views.breeder_profile_page, name="breeder_profile"),

    # BARF + Badge (Sprint BARF)
    path("badge/<uuid:breeder_id>/", views.njuskalo_badge, name="njuskalo_badge"),
    path("barf/", views.barf_listings, name="barf_listings"),
    path("barf/nova/", views.barf_create, name="barf_create"),
    path("hotel/", views.pet_hotel_booking, name="pet_hotel_booking"),
    path("registracija/", views.registracija, name="registracija"),
    path("dresura/", views.training_list, name="training_list"),

    # Dashboard (login required)
    path("moj-profil/", views.breeder_dashboard, name="breeder_dashboard"),

    # Add animal — journey flow
    path("ljubimac/novi/", views.add_animal, name="add_animal"),
    path("ljubimac/zatrazi/", views.add_animal_auth, name="add_animal_zatrazi"),
]
