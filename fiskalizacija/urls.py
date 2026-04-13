from django.urls import path
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

from . import views

app_name = 'fiskalizacija'
urlpatterns = [
    path('', views.config_view, name='config'),
]
