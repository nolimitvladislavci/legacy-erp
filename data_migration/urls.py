from django.urls import path
from . import views

app_name = 'data_migration'

urlpatterns = [
    path('', views.project_list, name='project_list'),
    path('upload/', views.upload_migration_file, name='upload'),
    path('<uuid:project_id>/mapping/', views.mapping_view, name='mapping'),
    path('<uuid:project_id>/preview/', views.preview_view, name='preview'),
    path('<uuid:project_id>/execute/', views.execute_import, name='execute'),
    path('<uuid:project_id>/status/', views.import_status, name='status'),
]
