from django.urls import path
from website import views
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

urlpatterns = [
    path('<slug:slug>/', views.company_site, name='company_site'),
    path('<slug:slug>/contact/', views.company_site_contact, name='company_site_contact'),
]
