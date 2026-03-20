from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    path('', views.payment_dashboard, name='dashboard'),
    path('settings/', views.payment_settings, name='settings'),
    path('list/', views.payment_list, name='list'),

    # API endpoints (called by other modules)
    path('api/create/', views.create_payment_api, name='api_create'),
    path('api/status/<uuid:payment_id>/', views.payment_status_api, name='api_status'),

    # Gateway webhooks
    path('webhook/stripe/', views.stripe_webhook, name='stripe_webhook'),
    path('webhook/btcpay/', views.btcpay_webhook, name='btcpay_webhook'),

    # Redirect pages
    path('success/', views.payment_success, name='success'),
    path('paypal/return/', views.paypal_return, name='paypal_return'),
    path('cancel/', views.payment_cancel, name='cancel'),
]
