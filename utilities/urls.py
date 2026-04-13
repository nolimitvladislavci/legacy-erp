from django.urls import path

from . import views

app_name = "utilities"

urlpatterns = [
    path("", views.utilities_dashboard, name="dashboard"),
    path("bill/<uuid:bill_id>/book/", views.bill_book, name="bill_book"),
]
