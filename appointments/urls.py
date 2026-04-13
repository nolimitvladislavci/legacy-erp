from django.urls import include, path
from rest_framework.routers import DefaultRouter
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

from . import views

router = DefaultRouter()
router.register(r'viewset', views.AppointmentViewSet, basename='appointment')

app_name = "appointments"
urlpatterns = [
    # Interni kalendar
    path("", views.calendar_view, name="calendar"),
    path("lista/", views.appointment_list, name="list"),
    path("new/", views.appointment_create, name="create"),
    path("<int:pk>/edit/", views.appointment_edit, name="edit"),
    path("<int:pk>/delete/", views.appointment_delete, name="delete"),
    path("<int:pk>/status/", views.appointment_status, name="status"),
    # Usluge (CRUD)
    path("usluge/", views.service_list, name="service_list"),
    path("usluge/new/", views.service_create, name="service_create"),
    path("usluge/<int:pk>/edit/", views.service_edit, name="service_edit"),
    # Kartoni klijenata
    path("kartoni/", views.dossier_list, name="dossier_list"),
    path("kartoni/<int:partner_id>/", views.dossier_detail, name="dossier_detail"),
    path("kartoni/<int:partner_id>/unos/", views.dossier_entry_create, name="dossier_entry_create"),
    path("kartoni/<int:partner_id>/unos/<int:entry_id>/edit/", views.dossier_entry_edit, name="dossier_entry_edit"),
    path("kartoni/<int:partner_id>/unos/<int:entry_id>/delete/", views.dossier_entry_delete, name="dossier_entry_delete"),
    # API
    path("api/events/", views.api_events, name="api_events"),
    path("api/appointments/", views.api_appointments, name="api_appointments_create"),
    path("api/appointments/<int:pk>/", views.api_appointments, name="api_appointments_detail"),
    path("api/slots/week/", views.api_slots_week, name="api_slots_week"),
    path("api/", include(router.urls)),
    # Javni portal
    path("booking/", views.public_booking_index, name="public_booking_index"),
    path("booking/<int:service_id>/", views.public_booking_calendar, name="public_booking_calendar"),
    path("booking/<int:service_id>/wizard/", views.public_booking_wizard, name="booking_wizard"),
    path("booking/ics/<int:appointment_id>/", views.download_ics, name="download_ics"),
    path("api/booking/slots/", views.api_available_slots, name="api_available_slots"),
    path("api/booking/slots/week/", views.api_slots_week, name="api_slots_week_public"),
    path("api/booking/submit/", views.api_submit_public_booking, name="api_submit_public_booking"),
    path("api/booking/auth-check/", views.api_booking_auth_check, name="api_booking_auth_check"),
    path("api/booking/register/", views.api_booking_register, name="api_booking_register"),

    # Company-scoped public booking
    path("booking/c/<slug:company_slug>/", views.public_booking_by_slug, name="booking_by_slug"),
    path("booking/track/<int:pk>/", views.booking_track, name="booking_track"),
    path("baking/", views.baking_board, name="baking_board"),
    path("baking/<int:pk>/intake/", views.baking_intake, name="baking_intake"),
    path("baking/<int:pk>/status/", views.baking_status_update, name="baking_status_update"),
    path('<int:pk>/send-reminder/', views.send_reminder, name='send_reminder'),
    path('send-reminders-now/', views.send_reminders_now, name='send_reminders_now'),

    # Polymorphic Scheduling — Double-Lock
    path('api/book/', views.api_book_double_lock, name='api_book_double_lock'),
    path('api/check-availability/', views.api_check_double_lock, name='api_check_double_lock'),
    path("api/dl-slots/", views.api_double_lock_slots, name="api_double_lock_slots"),
    path("booking-calendar/", views.booking_calendar_view, name="booking_calendar"),

    # ── Guest verification ────────────────────────────────────────────────────
    path("api/booking/guest-register/",  views.api_booking_guest_register,  name="booking_guest_register"),
    path("api/booking/verify-email/",    views.api_booking_verify_email,    name="booking_verify_email"),
    path("api/booking/verify-wa-pin/",   views.api_booking_verify_wa_pin,   name="booking_verify_wa_pin"),
    path("api/booking/qr-login/",        views.api_booking_qr_login,        name="booking_qr_login"),
    path("api/booking/generate-qr/",     views.api_booking_generate_qr,     name="booking_generate_qr"),

]