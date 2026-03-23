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

    # Module Picker
    path('modules/', views_modules.module_picker, name='module_picker'),
    path('modules/api/toggle/', views_modules.module_toggle_api, name='module_toggle'),
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
]
