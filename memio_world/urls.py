from django.urls import path
from memio_world import views
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

app_name = 'memio_world'

urlpatterns = [
    path('waitlist/', views.waitlist_signup, name='waitlist_signup'),
    path('waitlist/count/', views.waitlist_count, name='waitlist_count'),
    path('registracija/', views.registracija_page, name='registracija'),
    path('o-projektu/', views.o_projektu_page, name='o_projektu'),
]
