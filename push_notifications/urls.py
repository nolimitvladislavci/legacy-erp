from django.urls import path
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

from . import views

app_name = 'push'
urlpatterns = [
    path('vapid-public-key/', views.vapid_public_key, name='vapid_key'),
    path('subscribe/',        views.subscribe,        name='subscribe'),
    path('unsubscribe/',      views.unsubscribe,      name='unsubscribe'),
]
