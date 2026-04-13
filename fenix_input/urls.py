from django.urls import path

from fenix_input import views

app_name = "fenix_input"

urlpatterns = [
    path("voice/", views.voice_input, name="voice_input"),
    path("sms/", views.sms_webhook, name="sms_webhook"),
    path("confirm/<int:message_id>/", views.confirm_message, name="confirm_message"),
    path("history/", views.message_history, name="message_history"),
    path("bluetooth/config/", views.bluetooth_config, name="bluetooth_config"),
]
