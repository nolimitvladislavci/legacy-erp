from django.urls import path

from . import propter_views, views

app_name = "registration"

urlpatterns = [
    path("", views.register_step1, name="register_step1"),
    path("company/", views.register_quick, name="register_step2"),
    path("trikey/", views.register_trikey, name="register_trikey"),
    path("company-full/", views.register_step2_combined, name="register_step2_full"),
    path("company-legacy/", views.register_step2, name="register_step2_legacy"),
    path("account/", views.register_step3_confirm, name="register_step3"),
    path("account-legacy/", views.register_step3, name="register_step3_legacy"),
    path("confirm/", views.register_step4, name="register_step4"),
    path("success/", views.register_success, name="register_success"),
    path("upgrade/", views.upgrade_required, name="upgrade_required"),
    path("superadmin/registrations/", views.admin_registration_list, name="admin_list"),
    path("superadmin/registrations/<uuid:pk>/", views.admin_registration_detail, name="admin_detail"),
    path("superadmin/registrations/<uuid:pk>/approve/", views.admin_approve_registration, name="admin_approve"),
    path("superadmin/registrations/<uuid:pk>/reject/", views.admin_reject_registration, name="admin_reject"),
    path("api/check-promo/", views.api_check_promo, name="api_check_promo"),
    path("api/oib-lookup/", views.api_oib_lookup, name="api_oib_lookup"),
    path("api/plan-suggest/", views.api_plan_suggest, name="api_plan_suggest"),
    path("umbrella/invites/", views.umbrella_invite_manage, name="umbrella_invites"),
    # Propter SaaS
    path("propter/", propter_views.propter_dashboard, name="propter_dashboard"),
    path("propter/new/", propter_views.propter_create_tenant, name="propter_create_tenant"),
    path("propter/<int:pk>/", propter_views.propter_tenant_detail, name="propter_tenant_detail"),
    path("propter/<int:pk>/regenerate-key/", propter_views.propter_regenerate_api_key, name="propter_regenerate_key"),
    path("propter/<int:pk>/toggle-api/", propter_views.propter_toggle_api, name="propter_toggle_api"),
    path("propter/api/stats/", propter_views.propter_api_stats, name="propter_api_stats"),
    # Sales Wizard
    path("sales-wizard/", views.sales_wizard, name="sales_wizard"),
    path("sales-wizard/submit/", views.sales_wizard_submit, name="sales_wizard_submit"),
    # Agent Dashboard
    path("agent/", views.agent_dashboard, name="agent_dashboard"),
    path("api/name-search/", views.api_name_search, name="api_name_search"),
]
