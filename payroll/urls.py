from django.urls import path

from . import views

app_name = 'payroll'

urlpatterns = [
    path('', views.payroll_list, name='list'),
    path('new/', views.payroll_new, name='new'),
    path('<int:pk>/', views.payroll_detail, name='detail'),
    path('<int:pk>/run/', views.payroll_run_action, name='run'),
    path('<int:pk>/book/', views.payroll_book_action, name='book'),
    path('<int:pk>/pain001/', views.payroll_pain001, name='pain001'),
    path('<int:pk>/datev/', views.payroll_datev_export, name='datev'),
    path('<int:pk>/pdf/<int:user_id>/', views.payslip_pdf, name='payslip_pdf'),
    # HR-specific exports
    path('<int:pk>/joppd/', views.payroll_joppd_export, name='joppd'),
    path('<int:pk>/sepa-hr/', views.payroll_sepa_hr, name='sepa_hr'),
]
