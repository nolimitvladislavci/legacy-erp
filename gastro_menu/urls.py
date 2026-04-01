from django.urls import path
from . import views

app_name = 'gastro_menu'

urlpatterns = [
    # Public menu (QR scan)
    path('menu/<slug:slug>/', views.public_menu, name='public_menu'),

    # Admin panel
    path('admin/', views.admin_dashboard, name='admin_dashboard'),
    path('admin/toggle-availability/', views.toggle_availability, name='toggle_availability'),
    path('admin/update-price/', views.update_price, name='update_price'),
]
