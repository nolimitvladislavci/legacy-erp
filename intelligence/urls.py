from django.urls import path
from . import views

app_name = 'intelligence'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('results/', views.results_list, name='results_list'),
    path('funds/', views.funds_list, name='funds_list'),
    path('fund/<int:pk>/', views.fund_detail, name='fund_detail'),
]
