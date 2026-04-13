from django.urls import path
from . import views

app_name = 'superadmin_ai'

urlpatterns = [
    path(''    , views.dashboard, name='dashboard'),
    path('api/update-permission/', views.update_permission, name='update_permission'),
    path('api/bulk-permission/', views.bulk_permission, name='bulk_permission'),
    path('api/bulk-all/', views.bulk_all, name='bulk_all'),
    path('api/resolve-action/', views.resolve_action, name='resolve_action'),
    path('api/submit-request/', views.submit_request, name='submit_request'),
    path('api/tim-chat-send/', views.tim_chat_send, name='tim_chat_send'),
    path('logs/', views.action_logs, name='logs'),
    path('subscriptions/', views.subscription_cockpit, name='subscription_cockpit'),
    path('api/live-metrics/', views.live_metrics, name='live_metrics'),
]
