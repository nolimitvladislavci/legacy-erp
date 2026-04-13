from django.urls import path

from . import views

app_name = 'gastro_menu'

urlpatterns = [
    # Public (no login)
    path('menu/<slug:slug>/', views.public_menu, name='public_menu'),
    path('menu/<slug:slug>/order/', views.public_order, name='public_order'),
    path('menu/<slug:slug>/upute/', views.upute, name='upute'),

    # Kitchen (login required)
    path('kitchen/', views.kitchen_display, name='kitchen'),
    path('kitchen/orders/', views.kitchen_orders_fragment, name='kitchen_orders'),
    path('kitchen/status/', views.kitchen_update_status, name='kitchen_status'),

    # Admin (login required)
    path('admin/', views.admin_dashboard, name='admin_dashboard'),
    path('admin/toggle-availability/', views.toggle_availability, name='toggle_availability'),
    path('admin/update-price/', views.update_price, name='update_price'),
]
