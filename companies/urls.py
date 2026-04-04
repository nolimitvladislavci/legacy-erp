from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views
from . import views_modules

router = DefaultRouter()
router.register(r"api", views.CompanyViewSet)

app_name = "companies"

urlpatterns = [
    path("", views.company_list, name="list"),
    path("new/", views.company_create, name="create"),
    path("<str:pk>/edit/", views.company_edit, name="edit"),
    # Company Settings
    # Setup Wizard (DRON2)
    path("setup/", views.setup_wizard, name="setup_wizard"),
    path("setup/company/", views.setup_wizard_company, name="setup_wizard_company"),
    path("setup/contact/", views.setup_wizard_contact, name="setup_wizard_contact"),
    path("setup/fiscal/", views.setup_wizard_fiscal, name="setup_wizard_fiscal"),
    path("settings/", views.company_settings, name="settings"),
    path("settings/employee/create/", views.employee_create, name="employee_create"),
    path("settings/employee/<int:pk>/edit/", views.employee_edit, name="employee_edit"),
    path("settings/employee/<int:pk>/password/", views.employee_change_password, name="employee_change_password"),
    path("settings/employee/<int:pk>/toggle/", views.employee_toggle_redirect, name="employee_toggle_active"),
    path("settings/branch/save/", views.branch_save_redirect, name="branch_create"),
    path("settings/branch/<int:pk>/save/", views.branch_save_redirect, name="branch_edit"),
    path("settings/branch/<int:pk>/toggle/", views.branch_toggle_redirect, name="branch_toggle_active"),
    path("onboarding/dismiss/", views.onboarding_dismiss, name="onboarding_dismiss"),
    path("tax-rates/", views.tax_rate_list, name="tax_rates"),
    path("api/nkd-search/", views.nkd_search, name="nkd_search"),
    path("", include(router.urls)),

    # Module Picker (general ERP modules)
    path('modules/', views_modules.module_picker, name='module_picker'),
    path('modules/api/toggle/', views_modules.module_toggle_api, name='module_toggle'),

    # Specialized Module Config (udruge, DVD, KUD, etc.)
    path('modules/config/', views_modules.company_modules, name='company_modules'),
    path('modules/config/api/toggle/', views_modules.spec_module_toggle_api, name='spec_module_toggle'),
]

# KS LIMIT Komitent Manager
from companies import views_komitent
urlpatterns += [
    path('komitenti/', views_komitent.komitent_dashboard, name='komitent_dashboard'),
    path('komitenti/novi/', views_komitent.komitent_create, name='komitent_create'),
    path('komitenti/<int:pk>/', views_komitent.komitent_detail, name='komitent_detail'),
    path('komitenti/<int:pk>/status/', views_komitent.komitent_quick_status, name='komitent_status'),

    # Pretplata
    path('subscription/', views.subscription_view, name='subscription'),
    path('subscription/cancel/', views.subscription_cancel, name='subscription_cancel'),

    # T&C Consent
    path('tc-consent/', views.tc_consent_view, name='tc_consent'),
]
