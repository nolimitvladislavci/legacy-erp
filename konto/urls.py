from django.urls import path

from . import views, views_ai_review, views_bank

app_name = 'konto'

urlpatterns = [
    path('datev-export/', views.datev_export, name='datev_export'),
    path('skr03-seed/', views.skr03_seed, name='skr03_seed'),
    # Dashboard
    path('', views.dashboard, name='dashboard'),

    # Kontni plan
    path('accounts/', views.chart_of_accounts, name='chart_of_accounts'),
    path('accounts/<int:pk>/', views.account_detail, name='account_detail'),
    path('accounts/save/', views.account_save, name='account_save'),

    # Žiro računi
    path('bank/', views.bank_accounts, name='bank_accounts'),
    path('bank/save/', views.bank_account_save, name='bank_account_save'),

    # Transakcije
    path('transactions/', views.transactions, name='transactions'),

    # Temeljnice
    path('journal/', views.journal_entries, name='journal_entries'),
    path('journal/<int:pk>/', views.journal_entry_detail, name='journal_entry_detail'),
    path('journal/create/', views.journal_entry_create, name='journal_entry_create'),

    # Izvještaji
    path('reports/pnl/', views.report_profit_loss, name='report_pnl'),
    path('reports/balance-sheet/', views.report_balance_sheet, name='report_balance_sheet'),
    path('reports/receivables/', views.report_receivables, name='report_receivables'),

    # Porezni izvještaji (HR + DE)
    path('reports/tax-dashboard/', views.tax_dashboard, name='tax_dashboard'),
    path('reports/vat/', views.report_vat, name='report_vat'),
    path('reports/annual-tax/', views.report_annual_tax, name='report_annual_tax'),
    path('reports/euer/', views.report_euer, name='report_euer'),
    path('reports/corporate-tax/', views.report_corporate_tax, name='report_corporate_tax'),
    path('reports/po-sd/', views.report_po_sd, name='report_po_sd'),
    path('reports/vat/<int:pk>/filed/', views.report_vat_mark_filed, name='report_vat_mark_filed'),

    # Deutsche Steuerberichte
    path('reports/ustva/', views.report_ustva, name='report_ustva'),
    path('reports/ustva/<int:year>/<int:month>/xml/', views.ustva_xml_export, name='ustva_xml_export'),
    path('reports/koerperschaftsteuer/', views.report_koerperschaftsteuer, name='report_kst'),

    # ── Bank Import (camt.053) ──
    path('bank/dashboard/', views_bank.bank_dashboard, name='bank_dashboard'),
    path('bank/create/', views_bank.bank_account_create, name='bank_account_create'),
    path('bank/upload/', views_bank.bank_upload, name='bank_upload'),
    path('bank/reconcile/<int:pk>/', views_bank.bank_reconcile, name='bank_reconcile'),
    path('bank/auto-reconcile/', views_bank.bank_auto_reconcile, name='bank_auto_reconcile'),
    # Profitni centri
    path('cost-centers/', views.cost_centers, name='cost_centers'),
    path('cost-centers/<int:pk>/', views.cost_center_detail, name='cost_center_detail'),
    path('cost-centers/save/', views.cost_center_save, name='cost_center_save'),

    # API
    path('api/auto-match/', views.api_auto_match, name='api_auto_match'),
    path('api/match/<int:pk>/', views.api_match_transaction, name='api_match_transaction'),
    path('api/book-invoice/<int:pk>/', views.api_book_invoice, name='api_book_invoice'),
    path('api/book-transactions/', views.api_book_transactions, name='api_book_transactions'),
    path('api/ignore/<int:pk>/', views.api_ignore_transaction, name='api_ignore_transaction'),
    path('api/transaction/create/', views.api_transaction_create, name='api_transaction_create'),
    path('api/chart/', views.api_chart_data, name='api_chart_data'),
# Audit hash chain    path('audit/verify/', views.audit_verify, name='audit_verify'),    path('audit/certificate.pdf', views.audit_certificate_pdf, name='audit_certificate_pdf'),
    path('api/unmatched-invoices/', views.api_unmatched_invoices, name='api_unmatched_invoices'),

    # Bankovna rekoncilijacija
    path('reconciliation/', views.reconciliation_dashboard, name='reconciliation'),
    path('api/reconcile-batch/', views.api_reconcile_batch, name='api_reconcile_batch'),

    # Period management
    path('periods/', views.period_management, name='period_management'),

    # OPZ-STAT-1
    path('reports/opz-stat/', views.report_opz_stat, name='report_opz_stat'),

    # GFI-POD export
    path('reports/gfi-pod/', views.gfi_pod_export, name='gfi_pod_export'),

    # AI Review Queue
    path('ai-review/', views_ai_review.ai_review_queue, name='ai_review_queue'),
    path('ai-review/<int:pk>/confirm/', views_ai_review.ai_confirm_booking, name='ai_confirm_booking'),

    # SAF-T HR Export
    path('saft/export/', views.saft_export_view, name='saft_export'),
]
