from django.urls import path
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
from . import views

app_name = 'zeleni_otok'

urlpatterns = [
    # Public pages
    path('', views.landing_page, name='landing'),
    path('pricing/', views.pricing_page, name='pricing'),
    path('compare/', views.compare_page, name='compare'),
    path('compare/<slug:competitor_slug>/', views.compare_page, name='compare_competitor'),

    # Migration
    path('migration/', views.migration_page, name='migration'),
    path('migration/submit/', views.migration_submit, name='migration_submit'),
    path('migration/<uuid:pk>/status/', views.migration_status, name='migration_status'),

    # Free tools
    path('tools/pdv/', views.pdv_calculator, name='pdv_calculator'),
    path('tools/pdv/calculate/', views.pdv_calculate, name='pdv_calculate'),
    path('tools/oib/', views.oib_lookup, name='oib_lookup'),
    path('tools/oib/validate/', views.oib_validate, name='oib_validate'),
    path('tools/r1/', views.r1_validator, name='r1_validator'),
    path('tools/r1/validate/', views.r1_validate, name='r1_validate'),
    path('tools/roi/', views.roi_calculator, name='roi_calculator'),
    path('tools/roi/calculate/', views.roi_calculate, name='roi_calculate'),
    path('tools/tax-calendar/', views.tax_calendar, name='tax_calendar'),

    # Referral
    path('ref/<str:code>/', views.referral_landing, name='referral_landing'),
]
