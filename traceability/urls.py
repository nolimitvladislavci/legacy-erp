from django.urls import path

from . import views

app_name = "traceability"

urlpatterns = [
    path("", views.index, name="index"),
]
