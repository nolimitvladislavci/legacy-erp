"""
sales/urls.py — URL patterns za prodajni modul.
"""

from django.urls import path
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
from . import views

app_name = 'sales'

urlpatterns = [
    # ══════════════════════════════════════════════════════════
    #  CJENICI
    # ══════════════════════════════════════════════════════════
    path('cjenici/', views.price_list_dashboard, name='price_list_dashboard'),
    path('cjenici/novi/', views.price_list_create, name='price_list_create'),
    path('cjenici/<uuid:pk>/', views.price_list_detail, name='price_list_detail'),
    path('cjenici/<uuid:pk>/uredi/', views.price_list_create, name='price_list_edit'),
    path('cjenici/<uuid:pk>/obrisi/', views.price_list_delete, name='price_list_delete'),
    path('api/ai-cijena/', views.ai_price_suggest, name='ai_price_suggest'),
    path('api/resolve-cijena/', views.resolve_price_api, name='resolve_price_api'),

    # ══════════════════════════════════════════════════════════
    #  NARUDŽBE
    # ══════════════════════════════════════════════════════════
    path('narudzbe/', views.order_dashboard, name='order_dashboard'),
    path('narudzbe/lista/', views.order_list, name='order_list'),
    path('narudzbe/nova/', views.order_create, name='order_create'),
    path('narudzbe/<uuid:pk>/', views.order_detail, name='order_detail'),
    path('narudzbe/<uuid:pk>/potvrdi/', views.order_confirm, name='order_confirm'),
    path('narudzbe/<uuid:pk>/isporuci/', views.order_ship, name='order_ship'),
    path('narudzbe/<uuid:pk>/fakturiraj/', views.order_invoice, name='order_invoice'),
    path('narudzbe/<uuid:pk>/otkazi/', views.order_cancel, name='order_cancel'),
    path('narudzbe/<uuid:pk>/pdf/', views.order_pdf, name='order_pdf'),
    path('api/ai-artikli/', views.ai_suggest_items, name='ai_suggest_items'),

    # ══════════════════════════════════════════════════════════
    #  SALDAKONTI
    # ══════════════════════════════════════════════════════════
    path('saldakonti/', views.saldakonti_dashboard, name='saldakonti_dashboard'),
    path('saldakonti/partner/<uuid:partner_id>/', views.partner_open_items, name='partner_open_items'),
    path('saldakonti/ios/generiraj/<uuid:partner_id>/', views.ios_generate, name='ios_generate'),
    path('saldakonti/ios/<uuid:pk>/pdf/', views.ios_pdf, name='ios_pdf'),
    path('saldakonti/ios/<uuid:pk>/email/', views.ios_send_email, name='ios_send_email'),
    path('saldakonti/uplata/<uuid:pk>/', views.payment_register, name='payment_register'),
    path('saldakonti/sync/', views.open_items_sync, name='open_items_sync'),
    path('api/ai-rizik/', views.ai_payment_risk, name='ai_payment_risk'),
]
