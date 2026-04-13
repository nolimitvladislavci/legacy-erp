from django.urls import path
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
from . import views

app_name = 'tracking'

urlpatterns = [
    path('', views.tracking_dashboard, name='dashboard'),
    path('api/<str:token>/', views.tracking_status_api, name='status_api'),
    path('api/<str:token>/events/', views.tracking_events_api, name='events_api'),
    path('update/<int:pk>/', views.tracking_update, name='update'),
    path('shipment/<int:pk>/update/', views.shipment_update, name='shipment_update'),
    path('t/<str:token>/', views.tracking_public, name='public'),
]
