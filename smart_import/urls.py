from django.urls import path
from . import views

app_name = "smart_import"

urlpatterns = [
    path("",                         views.upload_view,         name="upload"),
    path("<int:pk>/",                views.stage_view,          name="stage"),
    path("<int:pk>/status/",         views.batch_status_api,    name="status"),
    path("<int:pk>/retry/",          views.retry_batch_api,     name="retry"),
    path("<int:pk>/report-problem/", views.report_problem_api,  name="report_problem"),
    path("<int:pk>/save-mapping/",   views.save_mapping_api,    name="save_mapping"),
    path("<int:pk>/update-item/",    views.update_item_api,     name="update_item"),
    path("<int:pk>/delete-item/",    views.delete_item_api,     name="delete_item"),
    path("<int:pk>/add-item/",       views.add_item_api,        name="add_item"),
    path("<int:pk>/update-supplier/",views.update_supplier_api, name="update_supplier"),
    path("<int:pk>/confirm/",        views.confirm_view,        name="confirm"),
    path("<int:pk>/manual-entry/",   views.manual_entry_view,   name="manual_entry"),
    path("api/inbound-webhook/<str:secret>/", views.inbound_email_webhook, name="inbound_webhook"),
]
