from django.urls import path
from einvoice import views

app_name = "einvoice"

urlpatterns = [
    # Smart Mailbox (inbound)
    path("inbox/", views.smart_mailbox, name="smart_mailbox"),
    path("inbox/<uuid:pk>/", views.mailbox_detail, name="mailbox_detail"),
    path("inbox/<uuid:pk>/approve/", views.mailbox_approve, name="mailbox_approve"),
    path("inbox/<uuid:pk>/reject/", views.mailbox_reject, name="mailbox_reject"),
    # Outbound messages
    path("outbound/", views.outbound_messages, name="outbound_messages"),
    path("message/<uuid:pk>/", views.message_detail, name="message_detail"),
]
