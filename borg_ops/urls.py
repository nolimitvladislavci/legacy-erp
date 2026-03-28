from django.urls import path
from . import views

app_name = 'borg_ops'

urlpatterns = [
    path('api/card/move/', views.card_move, name='card_move'),
    path('api/card/version/', views.board_version, name='board_version'),
    path('dashboard/operations/', views.operations_dashboard, name='operations_dashboard'),
]
