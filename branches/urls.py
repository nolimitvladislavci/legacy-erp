from django.urls import path
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

from . import views

app_name = 'branches'

urlpatterns = [
    path('optika/',     views.optika_dashboard,     name='optika'),
    path('fitness/',    views.fitness_dashboard,    name='fitness'),
    path('retail/',     views.retail_dashboard,     name='retail'),
    path('accounting/', views.accounting_dashboard, name='accounting'),
    path('restaurant/', views.restaurant_dashboard, name='restaurant'),
    path('salon/',      views.salon_dashboard,      name='salon'),
    path('other/',      views.other_dashboard,      name='other'),
]
