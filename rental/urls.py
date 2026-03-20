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
]
