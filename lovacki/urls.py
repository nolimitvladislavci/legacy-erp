from django.urls import path
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
from . import views

app_name = 'lovacki'

urlpatterns = [
    path('', views.hunting_dashboard, name='dashboard'),
    path('novi/', views.hunt_record_create, name='record_create'),
]
