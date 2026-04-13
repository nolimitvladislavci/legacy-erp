from django.urls import path
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
from . import views

app_name = 'utilities'

urlpatterns = [
    path('', views.utilities_dashboard, name='dashboard'),
    path('bill/<uuid:bill_id>/book/', views.bill_book, name='bill_book'),
]
