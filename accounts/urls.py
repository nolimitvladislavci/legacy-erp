from django.urls import path

from . import views

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
]
