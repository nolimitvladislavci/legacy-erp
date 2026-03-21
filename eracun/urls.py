from django.urls import path
from . import views
from . import views_inbox
from . import views_posrednik

app_name = 'eracun'

urlpatterns = [
    # Dashboard & settings
    path('', views.dashboard, name='dashboard'),
    path('settings/', views.settings_view, name='settings'),

    # Detail & actions
    path('<uuid:pk>/', views.detail, name='detail'),
    path('<uuid:pk>/send/', views.send_eracun, name='send'),
    path('<uuid:pk>/xml/', views.download_xml, name='download_xml'),
    path('<uuid:pk>/fina-xml/', views.download_fina_xml, name='download_fina_xml'),

    # Create from existing invoice
    path('from-invoice/<uuid:invoice_pk>/', views.create_from_invoice, name='from_invoice'),

    # External API (API key auth)
    path('api/create/', views.api_create, name='api_create'),
    path('api/status/<uuid:pk>/', views.api_status, name='api_status'),
    path('api/list/', views.api_list, name='api_list'),

    # ── INBOX (primanje e-racuna) ──
    path('inbox/', views_inbox.inbox_dashboard, name='inbox'),
    path('inbox/upload/', views_inbox.inbox_upload, name='inbox_upload'),
    path('inbox/<uuid:pk>/', views_inbox.inbox_detail, name='inbox_detail'),
    path('inbox/<uuid:pk>/book/', views_inbox.inbox_book, name='inbox_book'),


    # ── POSREDNIK (setup + veliko dugme) ──
    path('posrednik/', views_posrednik.posrednik_setup, name='posrednik_setup'),
    path('send/<int:invoice_pk>/', views_posrednik.send_eracun_button, name='send_button'),
    # API: primanje e-racuna od vanjskih sustava
    path('api/receive/', views_inbox.api_receive, name='api_receive'),
    path('p/<uuid:uuid>/', views.public_invoice_download, name='public_invoice'),

    # DE: ZUGFeRD + XRechnung download
    path('<uuid:pk>/zugferd/', views.download_zugferd, name='download_zugferd'),
    path('<uuid:pk>/xrechnung/', views.download_xrechnung, name='download_xrechnung'),
]
