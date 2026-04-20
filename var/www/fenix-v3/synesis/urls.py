from django.urls import path
from . import views

app_name = "synesis"

urlpatterns = [
    path("", views.SynesisSettingsView.as_view(), name="settings"),
    path("regenerate-token/", views.RegenerateTokenView.as_view(), name="regenerate_token"),
    path("download-script/", views.DownloadScriptView.as_view(), name="download_script"),
    path("download-setup/", views.DownloadSetupView.as_view(), name="download_setup"),
    path("mdb/upload/", views.MdbUploadView.as_view(), name="mdb_upload"),
    path("mdb/preview/", views.MdbPreviewView.as_view(), name="mdb_preview"),
    path("mdb/import/", views.MdbImportExecuteView.as_view(), name="mdb_import"),
    # Public token-based script download (no login, used in setup.bat)
    path("script/<str:token>/", views.download_script_public, name="download_script_public"),
]
