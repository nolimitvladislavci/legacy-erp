from django.urls import path
from . import views

app_name = "synesis"

urlpatterns = [
    path("", views.synesis_settings, name="settings"),
    path("regenerate-token/", views.regenerate_token, name="regenerate_token"),
    path("download-script/", views.download_script, name="download_script"),
    path("download-setup/", views.download_setup_bat, name="download_setup"),
    path("download-schema-probe/", views.download_schema_probe, name="download_schema_probe"),
    path("download-pkv-probe/", views.download_pkv_probe, name="download_pkv_probe"),

    # MDB Online Import
    path('mdb/upload/', views.mdb_upload, name='mdb_upload'),
    path('mdb/preview/', views.mdb_preview, name='mdb_preview'),
    path('mdb/import/', views.mdb_import_execute, name='mdb_import'),
]
