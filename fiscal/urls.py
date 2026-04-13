from django.urls import path
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
from . import views

app_name = 'fiscal'

urlpatterns = [
    path('test/', views.test_connection, name='test_connection'),
    path('status/', views.fiscal_status, name='status'),
]
