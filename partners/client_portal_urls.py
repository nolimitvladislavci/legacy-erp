from django.urls import path
from . import client_portal_views as views

app_name = 'client_portal'

urlpatterns = [
    path('', views.client_dashboard, name='dashboard'),
    path('deliveries/', views.client_deliveries, name='deliveries'),
    path('deliveries/<int:delivery_id>/track/', views.client_delivery_track, name='track'),
    path('invoices/', views.client_invoices, name='invoices'),
    path('support/new/', views.client_new_ticket, name='new_ticket'),
    path('support/<int:ticket_id>/', views.client_ticket_detail, name='ticket_detail'),
]
