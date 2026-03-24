"""tax_wizard/urls.py — Porezni Savjetnik URL routing."""
from django.urls import path

from tax_wizard import views

app_name = 'tax_wizard'

urlpatterns = [
    # Dashboard — kalendar + pregled svih obrazaca
    path('', views.dashboard, name='dashboard'),

    # Wizard
    path('start/<str:form_type>/', views.wizard_start, name='wizard_start'),
    path('session/<uuid:session_id>/', views.wizard_view, name='wizard_view'),
    path('session/<uuid:session_id>/save/', views.wizard_save_step, name='wizard_save_step'),
    path('session/<uuid:session_id>/preview/', views.wizard_preview, name='wizard_preview'),
    path('session/<uuid:session_id>/finalize/', views.wizard_finalize, name='wizard_finalize'),
    path('session/<uuid:session_id>/xml/', views.export_xml, name='export_xml'),
    path('session/<uuid:session_id>/pdf/', views.export_pdf, name='export_pdf'),

    # Simulacije
    path('simulate/salary-dividend/', views.simulate_salary_dividend, name='sim_salary_div'),
    path('simulate/deductions/', views.simulate_deductions, name='sim_deductions'),
    path('simulate/pausal-tier/', views.simulate_pausal_tier, name='sim_pausal_tier'),

    # Računovođa dashboard (B2B2C — referred sesije)
    path('accountant/', views.accountant_dashboard, name='accountant_dashboard'),
    path('session/<uuid:session_id>/review/', views.accountant_review, name='accountant_review'),

    # API — kalendar, notifikacije
    path('api/deadlines/', views.api_deadlines, name='api_deadlines'),
    path('api/calendar/<int:year>/', views.api_calendar, name='api_calendar'),

    # PO-SD Auto-Fill (Zero-Click)
    path('api/auto-fill/', views.posd_auto_fill, name='posd_auto_fill'),
    path('session/<uuid:session_id>/auto-fill/', views.posd_auto_fill_session, name='posd_auto_fill_session'),
]
