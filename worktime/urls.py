from django.urls import path

from . import timesheet_views, views, travel_views
from .views import api_clock_in, api_clock_out, api_auditor_flags

app_name = 'worktime'
urlpatterns = [
    path('api/quick-create-project/', views.api_quick_create_project, name='api_quick_create_project'),
    path('', timesheet_views.worker_dashboard, name='ts_worker'),
    path('manager/', timesheet_views.manager_timesheet, name='ts_manager'),
    path('analytics/', timesheet_views.timesheet_analytics, name='ts_analytics'),
    path('weekly/', timesheet_views.weekly_entry, name='ts_weekly'),
    path('profile/', timesheet_views.worker_profile, name='ts_profile'),
    path('timer/start/', timesheet_views.timer_start, name='timer_start'),
    path('timer/pause/', timesheet_views.timer_pause, name='timer_pause'),
    path('timer/resume/', timesheet_views.timer_resume, name='timer_resume'),
    path('timer/stop/', timesheet_views.timer_stop, name='timer_stop'),
    path('timer/discard/', timesheet_views.timer_discard, name='timer_discard'),
    path('timer/status/', timesheet_views.timer_status, name='timer_status'),
    path('add/', timesheet_views.time_entry_add, name='ts_add'),
    path('edit/<int:pk>/', timesheet_views.time_entry_edit, name='ts_edit'),
    path('delete/<int:pk>/', timesheet_views.time_entry_delete, name='ts_delete'),
    path('duplicate/<int:pk>/', timesheet_views.time_entry_duplicate, name='ts_duplicate'),
    path('copy-prev/', timesheet_views.copy_previous_day, name='ts_copy_prev'),
    path('copy-day/', timesheet_views.copy_day, name='ts_copy_day'),
    path('copy-week/', timesheet_views.copy_week, name='ts_copy_week'),
    path('copy-month/', timesheet_views.copy_month, name='ts_copy_month'),
    path('note/save/', timesheet_views.daily_note_save, name='ts_note_save'),
    path('template/use/<int:pk>/', timesheet_views.template_use, name='ts_template_use'),
    path('approve/', timesheet_views.approve_entries, name='ts_approve'),
    path('bill/', timesheet_views.bill_entries, name='ts_bill'),
    path('pdf/', timesheet_views.timesheet_pdf, name='ts_pdf'),
    path('billable/', timesheet_views.billable_hours, name='billable'),
    path('export/excel/', timesheet_views.export_timesheet_excel, name='ts_export_excel'),
    path('inspector/', timesheet_views.inspector_print, name='ts_inspector_print'),
    path('payroll/', timesheet_views.payroll_summary, name='ts_payroll'),


    # Travel Orders
    path('travel-orders/', travel_views.travel_order_list, name='travel_order_list'),
    path('travel-orders/create/', travel_views.travel_order_create, name='travel_order_create'),
    path('travel-orders/<int:pk>/', travel_views.travel_order_detail, name='travel_order_detail'),
    path('travel-orders/<int:pk>/approve/', travel_views.travel_order_approve, name='travel_order_approve'),
    path('travel-orders/<int:pk>/expense/', travel_views.travel_expense_add, name='travel_expense_add'),
    path('travel-orders/<int:pk>/pdf/', travel_views.travel_order_pdf, name='travel_order_pdf'),

    # Hybrid Time Tracking API
    path('api/clock-in/', api_clock_in, name='api_clock_in'),
    path('api/clock-out/', api_clock_out, name='api_clock_out'),
    path('api/auditor/flags/', api_auditor_flags, name='api_auditor_flags'),

    path('api/offline-sync/', views.offline_sync, name='offline_sync'),
]
