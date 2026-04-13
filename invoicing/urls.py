from django.urls import path
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

from . import views

app_name = 'invoicing'

urlpatterns = [
    path('', views.index, name='invoice_list'),
    path('', views.index, name='index'),
    path('new/', views.invoice_create, name='invoice_create'),
    path('wizard/', views.invoice_wizard, name='invoice_wizard'),
    path('save/', views.invoice_save, name='invoice_save'),
    path('<int:pk>/', views.invoice_edit, name='invoice_detail'),
    path('<int:pk>/edit/', views.invoice_edit, name='invoice_edit'),
    path('<int:pk>/pdf/', views.generate_pdf, name='generate_pdf'),
    path('<int:pk>/download/', views.download_pdf, name='download_pdf'),
    path('<int:pk>/email/', views.send_email, name='send_email'),
    path('<int:pk>/fiscalize/', views.fiscalize, name='fiscalize'),
    path('<int:pk>/storno/', views.storno, name='storno'),
    path('<int:pk>/eracun/', views.generate_eracun, name='generate_eracun'),

    # Workflow
    path('<int:pk>/whatsapp/',       views.send_invoice_whatsapp, name='send_whatsapp'),
    path('<int:pk>/to-predracun/', views.convert_to_predracun, name='to_predracun'),
    path('<int:pk>/to-invoice/',   views.convert_to_invoice,   name='to_invoice'),
    path('<int:pk>/mark-sent/',    views.mark_sent,            name='mark_sent'),
    path('<int:pk>/mark-accepted/', views.mark_accepted,       name='mark_accepted'),
    path('<int:pk>/mark-rejected/', views.mark_rejected,       name='mark_rejected'),

    # Javni PDF za klijentski portal (bez login_required)
    path('public/<uuid:token>/pdf/', views.public_pdf, name='public_pdf'),

    # API rute
    path('api/profiles/', views.api_invoice_profiles, name='api_profiles'),
    path('api/oib-lookup/', views.api_oib_lookup, name='api_oib_lookup'),
    path('api/partner-hint/', views.api_partner_hint, name='api_partner_hint'),
    path('track/<str:token>/', views.email_tracking_pixel, name='email_tracking_pixel'),
    path('api/nkd-search/', views.api_nkd_search, name='api_nkd_search'),
    path('api/partners/', views.api_partners, name='api_partners'),
    path('api/articles/', views.api_articles, name='api_articles'),
    path('api/tax-rates/', views.api_tax_rates, name='api_tax_rates'),
    path('api/import/<str:module>/', views.api_import, name='api_import'),
    path('office/', views.invoice_office_wizard, name='invoice_office_wizard'),
    path('field/', views.invoice_field_wizard, name='invoice_field_wizard'),
    path('api/field-create/', views.api_field_create, name='api_field_create'),
    path('api/item/<int:pk>/update/', views.api_update_item, name='api_update_item'),
    path('api/item/<int:pk>/delete/', views.api_delete_item, name='api_delete_item'),
    path('api/invoice/<int:pk>/update/', views.api_update_invoice, name='api_update_invoice'),
    path('api/invoice/<int:pk>/status/', views.api_update_status, name='api_update_status'),
    path('api/invoice/<int:pk>/add-item/', views.api_add_item, name='api_add_item'),
    path("api/worktime-entries/", views.api_worktime_entries, name="api_worktime_entries"),
    path('<int:pk>/add-hours/', views.invoice_add_hours, name='add_hours'),
    path('<int:pk>/xml/', views.generate_eracun, name='invoice_xml'),
    path('<int:pk>/clone/',      views.invoice_clone,    name='invoice_clone'),
    path('client/<uuid:token>/', views.client_portal,   name='client_portal'),
    path('fiscal/certificates/', views.fiscal_certificates, name='fiscal_certificates'),
    path('fiscal/certificates/upload/', views.fiscal_certificate_upload, name='fiscal_certificate_upload'),
    path('fiscal/certificates/<int:pk>/test/', views.fiscal_certificate_test, name='fiscal_certificate_test'),
    path('fiscal/certificates/<int:pk>/delete/', views.fiscal_certificate_delete, name='fiscal_certificate_delete'),
    path('fiscal/batch/', views.fiscal_batch_view, name='fiscal_batch'),
    path('fiscal/batch/', views.fiscal_batch_list, name='fiscal_batch_list'),
    path('fiscal/batch/create/', views.fiscal_batch_create, name='fiscal_batch_create'),
    path('api/tax-calculate/', views.api_tax_calculate, name='api_tax_calculate'),
    path('form/', views.invoice_form_view, name='invoice_form'),
    path('form-standalone/', views.standalone_invoice_form, name='invoice_form_standalone'),
    path('profiles/', views.invoice_profiles_list, name='profiles_list'),
    path('profiles/save/', views.invoice_profile_save, name='profile_save'),
    path('profiles/<int:pk>/delete/', views.invoice_profile_delete, name='profile_delete'),
    path('canvas/', views.transaction_canvas, name='transaction_canvas'),
    path('api/recent-for-copy/', views.api_recent_for_copy, name='api_recent_for_copy'),
    path('api/invoice/<int:pk>/items/', views.api_invoice_items, name='api_invoice_items'),
    path('api/smart-lookup/', views.api_smart_lookup, name='api_smart_lookup'),
    path('dunning/', views.dunning_dashboard, name='dunning_dashboard'),
    path('api/invoice/<int:pk>/timeline/', views.api_invoice_timeline, name='api_invoice_timeline'),
    path('api/invoice/<int:pk>/morph/', views.api_invoice_morph, name='api_invoice_morph'),
    path('ira-ura/', views.ira_ura_dashboard, name='ira_ura_dashboard'),
]
