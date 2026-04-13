from django.urls import path
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
from . import views

app_name = "eldercare"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("korisnici/", views.resident_list, name="resident_list"),
    path("korisnici/novi/", views.resident_create, name="resident_create"),
    path("korisnici/<int:pk>/", views.resident_detail, name="resident_detail"),
    path("sobe/", views.room_list, name="room_list"),
    path("smjene/", views.shift_schedule, name="shift_schedule"),
    path("aktivnosti/", views.activity_list, name="activity_list"),
    path("naplata/", views.billing_list, name="billing_list"),
    path("naplata/generiraj/", views.billing_generate, name="billing_generate"),
]
