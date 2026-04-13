from django.urls import path
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

from . import views

app_name = "traceability"

urlpatterns = [
    path("", views.index, name="index"),
]
