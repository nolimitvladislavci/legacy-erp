from django.urls import path
from . import views

app_name = 'pdv_s'

urlpatterns = [
    path('', views.pdv_s_report, name='report'),
    path('<int:year>/<int:month>/xml/', views.pdv_s_xml_export, name='xml_export'),
]
