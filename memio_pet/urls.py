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
    # UKLONJENO 08.04.2026 — sigurnosna rupa, zamijenjeno token authom
    # path("ljubimac/novi/", views.add_animal, name="add_animal"),
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
    # Legal + SEO
    path("privatnost/", views.privatnost, name="privatnost"),
    path("uvjeti/", views.uvjeti, name="uvjeti"),
    path("sitemap.xml", views.sitemap_xml, name="sitemap"),
    path("uvezi/", views.social_import_wizard, name="social_import"),
    path(
        "feed/", lambda r: __import__("django.shortcuts", fromlist=["redirect"]).redirect("/boxgram/feed/"), name="feed"
    ),
    path("api/hit/", views.analytics_hit, name="analytics_hit"),
    # Digitalno Nasljeđe
    path("pas/<str:chip_or_tag>/naslijede/", views.pet_heritage, name="pet_heritage"),
    path("pas/<str:chip_or_tag>/naslijede/qr/", views.heritage_qr_code, name="heritage_qr"),
    path("naslijede/", views.heritage_showcase, name="heritage_showcase"),
    path("api/heritage/<str:chip_or_tag>/", views.heritage_api, name="heritage_api"),

    # PLAN-002: gram + pretraga + prodaja + farma
    path("gram/", lambda r: __import__("django.shortcuts", fromlist=["redirect"]).redirect("/boxgram/feed/"), name="gram"),
    path("pretraga/", views.pretraga, name="pretraga"),
    path("prodaja/", views.prodaja, name="prodaja"),
    path("farma/", views.farma_landing, name="farma_landing"),

    # PLAN-008: .dok Putovnica
    path("pas/<str:chip_or_tag>/putovnica/", views.pet_passport_dok, name="pet_passport"),

    # PLAN-011: Brzi PIN login
    path("pin/<uuid:breeder_pk>/", views.pin_login, name="pin_login"),
    path("pin/postavi/", views.pin_setup, name="pin_setup"),

    # PLAN-010: Odjava
    path("odjava/", views.odjava, name="odjava"),
]
