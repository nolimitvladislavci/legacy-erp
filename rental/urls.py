from django.urls import path
from . import views

app_name = 'rental'

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),

    # Properties CRUD
    path('properties/', views.property_list, name='property_list'),
    path('properties/new/', views.property_form, name='property_create'),
    path('properties/<int:pk>/edit/', views.property_form, name='property_edit'),

    # Bookings CRUD
    path('bookings/', views.booking_list, name='booking_list'),
    path('bookings/new/', views.booking_form, name='booking_create'),
    path('bookings/<int:pk>/edit/', views.booking_form, name='booking_edit'),

    # Check-in/out (admin)
    path('bookings/<int:pk>/check-in/', views.check_in, name='check_in'),
    path('bookings/<int:pk>/check-out/', views.check_out, name='check_out'),

    # Guest self-service (no login!)
    path('guest/<str:access_qr>/checkin/', views.guest_self_checkin, name='guest_checkin'),
    path('guest/<str:access_qr>/access/', views.guest_access, name='guest_access'),
    path('guest/<str:access_qr>/pay/', views.guest_pay, name='guest_pay'),

    # Housekeeping
    path('housekeeping/', views.housekeeping, name='housekeeping'),

    # Calendar
    path('calendar/', views.calendar_view, name='calendar'),

    # ── F3: Check-in + OCR + eVisitor + Accountant ──
    path('booking/<int:pk>/checkin/', views.checkin_flow, name='checkin_flow'),
    path('booking/<int:pk>/ocr/', views.guest_ocr_upload, name='guest_ocr'),
    path('booking/<int:pk>/evisitor.xml', views.evisitor_xml_download, name='evisitor_xml'),
    path('booking/<int:pk>/invoice.pdf', views.rental_invoice_pdf, name='rental_invoice_pdf'),
    path('accountant/', views.rental_accountant_dashboard, name='accountant_dashboard'),

    # ── TZ-2 Obrazac ──
    path('tz2/', views.tz2_preview, name='tz2_preview'),
    path('tz2/<int:year>/', views.tz2_preview, name='tz2_preview_year'),
    path('tz2/<int:year>/pdf/', views.tz2_download, name='tz2_download'),
    path('accountant/<str:company_id>/tz2/<int:year>.pdf', views.tz2_accountant_download, name='tz2_accountant_download'),

    path('tz2/<int:year>/xml/', views.tz2_xml_download, name='tz2_xml'),

    # ── PO-SD Obrazac ──
    path('posd/', views.posd_preview, name='posd_preview'),
    path('posd/<int:year>/', views.posd_preview, name='posd_preview_year'),
    path('posd/<int:year>/pdf/', views.posd_pdf, name='posd_pdf'),
    path('posd/<int:year>/xml/', views.posd_xml, name='posd_xml'),
]
