"""
memio_pet/urls.py -- URL routing za memio.pet public views
"""
from django.urls import path
from memio_pet import views

app_name = "memio_pet"

urlpatterns = [
    path("pas/<str:chip_or_tag>/", views.pet_profile_page, name="pet_profile"),
    path("pas/<str:chip_or_tag>/qr/", views.pet_qr_code, name="pet_qr"),
    path("uzgajivac/<uuid:breeder_id>/", views.breeder_profile_page, name="breeder_profile"),
]
