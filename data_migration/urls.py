from django.urls import path

from . import views

app_name = "data_migration"

urlpatterns = [
    # Dashboard
    path("", views.dashboard, name="dashboard"),

    # Upload (step 1)
    path("upload/", views.upload_view, name="upload"),

    # Mapping (step 2)
    path("<int:pk>/mapping/", views.mapping_view, name="mapping"),
    path("<int:pk>/mapping/save/", views.mapping_save_api, name="mapping_save"),

    # Preview (step 3)
    path("<int:pk>/preview/", views.preview_view, name="preview"),

    # Execute (step 4)
    path("<int:pk>/execute/", views.execute_api, name="execute"),
    path("<int:pk>/status/", views.status_api, name="status"),

    # Result (step 5)
    path("<int:pk>/result/", views.result_view, name="result"),

    # Delete
    path("<int:pk>/delete/", views.delete_project, name="delete"),
]
