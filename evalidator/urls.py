from django.urls import path
from evalidator import views
app_name = 'evalidator'
urlpatterns = [
    path('', views.landing, name='home'),
    path('validate/oib/', views.validate_oib, name='validate_oib'),
    path('validate/iban/', views.validate_iban_view, name='validate_iban'),
    path('validate/vat/', views.validate_vat_view, name='validate_vat'),
    path('api/v1/oib/', views.api_oib, name='api_oib'),
    path('api/status/', views.api_status, name='api_status'),
    path('api/v1/batch/', views.api_batch, name='api_batch'),
    path('docs/', views.api_docs, name='api_docs'),
    path('pricing/', views.pricing, name='pricing'),
]
