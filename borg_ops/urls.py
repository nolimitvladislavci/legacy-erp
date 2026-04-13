from django.urls import path

from . import views

app_name = "borg_ops"

urlpatterns = [
    path("api/card/move/", views.card_move, name="card_move"),
    path("api/card/version/", views.board_version, name="board_version"),
    path("api/card/activity/", views.activity_fragment, name="activity_fragment"),
    path("api/dispatch/suggest/<int:pk>/", views.dispatch_suggest, name="dispatch_suggest"),
    path("dashboard/operations/", views.operations_dashboard, name="operations_dashboard"),
    path("api/worker/gps/", views.update_worker_gps, name="update_worker_gps"),
    path("trace/<str:qr_token>/", views.public_trace_api, name="public_trace"),
    path("hub/", views.borg_hub, name="borg_hub"),
]
