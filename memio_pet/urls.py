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

    # BARF + Badge
    path("badge/<uuid:breeder_id>/", views.njuskalo_badge, name="njuskalo_badge"),
    path("barf/", views.barf_listings, name="barf_listings"),
    path("barf/nova/", views.barf_create, name="barf_create"),
    path("hotel/", views.pet_hotel_booking, name="pet_hotel_booking"),
    path("registracija/", views.registracija, name="registracija"),
    path("pristanak/<str:token>/", views.parental_consent, name="parental_consent"),
    path("pristanak-ponovo/", views.resend_consent, name="resend_consent"),
    path("prijava/", views.prijava, name="prijava"),
    path("dresura/", views.training_list, name="training_list"),

    # Dashboard
    path("moj-profil/", views.breeder_dashboard, name="breeder_dashboard"),

    # Add animal — journey flow
    path("ljubimac/novi/", views.add_animal, name="add_animal"),
    path("ljubimac/zatrazi/", views.add_animal_request, name="add_animal_zatrazi"),
    path("ljubimac/token/<str:token>/", views.add_animal_with_token, name="add_animal_token"),
    path("ljubimac/milestone/novi/", views.add_milestone, name="add_milestone"),

    # Udomljavanje
    path("udomljavanje/", views.udomljavanje_lista, name="udomljavanje"),

    # Dugini Most — memorial
    path("pas/<str:chip_or_tag>/dugini-most/", views.dugini_most, name="dugini_most"),
    path("api/memorial/<str:chip_or_tag>/candle/", views.memorial_candle_api, name="memorial_candle"),
    path("memorijal/<str:chip_or_tag>/uredi/", views.memorial_edit, name="memorial_edit"),

    # Knjiga sjecanja PDF
    path("pas/<str:chip_or_tag>/knjiga/", views.knjiga_sjecanja_pdf, name="knjiga_sjecanja"),

    # Direktoriji
    path("krematoriji/", views.krematoriji_lista, name="krematoriji_lista"),
    path("hoteli/", views.hoteli_lista, name="hoteli_lista"),
]
