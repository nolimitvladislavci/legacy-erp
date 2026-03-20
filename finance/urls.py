from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"api", views.TransactionViewSet)

app_name = "finance"
urlpatterns = [
    path("", views.transaction_list, name="list"),
    path("new/", views.transaction_create, name="create"),
    path("<int:pk>/delete/", views.transaction_delete, name="delete"),
    path("bank-import/", views.bank_import_csv, name="bank_import"),
    path("bank-import-xml/", views.bank_import_xml, name="bank_import_xml"),
    path("pain001/suppliers/", views.bank_pain001_suppliers, name="pain001_suppliers"),
    path("pain001/salaries/", views.bank_pain001_salaries, name="pain001_salaries"),
    path("discrepancies/", views.bank_discrepancies, name="bank_discrepancies"),
    path("discrepancies/legacy/", views.bank_discrepancies_legacy, name="bank_discrepancies_legacy"),
    path("cashflow-api/", views.cashflow_api, name="cashflow_api"),
    path("reports/pnl/pdf/", views.report_pnl_pdf, name="report_pnl_pdf"),
    path("reports/vat/<int:pk>/pdf/", views.report_vat_pdf, name="report_vat_pdf"),
    path("", include(router.urls)),
]
