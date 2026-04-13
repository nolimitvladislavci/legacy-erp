from django.urls import path

from . import views

app_name = 'fiskalizacija'
urlpatterns = [
    path('', views.config_view, name='config'),
]
