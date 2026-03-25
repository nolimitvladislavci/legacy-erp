from django.urls import path

from . import views
from . import deactivation
from . import data_export

app_name = 'accounts'
urlpatterns = [
    path('switch-company/', views.switch_company, name='switch_company'),
    path('password/', views.change_password, name='change_password'),
    path('', views.UserListView.as_view(), name='user_list'),
    path('<int:pk>/edit/', views.user_edit, name='user_edit'),
    path('<int:pk>/reset-password/', views.reset_password_request, name='reset_password'),
    path('<int:pk>/toggle/', views.toggle_user_status, name='toggle_status'),
    path('quick-register/', views.quick_register, name='quick_register'),
    path('translations/<str:lang_code>/', views.translation_manager, name='translation_manager'),
    # Deactivation flow
    path('deactivate/', deactivation.request_deactivation, name='request_deactivation'),
    path('deactivate/status/', deactivation.deactivation_status, name='deactivation_status'),
    path('deactivate/cancel/', deactivation.cancel_deactivation, name='cancel_deactivation'),
    # GDPR data export
    path('export/', data_export.export_company_data, name='export_company_data'),
]
