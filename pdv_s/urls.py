from django.urls import path

from . import views

app_name = 'pdv_s'

urlpatterns = [
    path('', views.pdv_s_report, name='report'),
    path('<int:year>/<int:month>/xml/', views.pdv_s_xml_export, name='xml_export'),
    path('batch-generate/', views.pdv_s_batch_generate, name='batch_generate'),
    path('batch-xml/<int:year>/<int:month>/', views.pdv_s_batch_xml_zip, name='batch_xml_zip'),
]
