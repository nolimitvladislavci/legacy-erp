from django.urls import path
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
from . import views

app_name = "limit_connect_ai"

urlpatterns = [
    path("cockpit/", views.ai_cockpit, name="ai_cockpit"),
    path("missions/", views.ai_missions, name="ai_missions"),
    path("reports/", views.ai_reports, name="ai_reports"),
    path("funds/", views.ai_funds, name="ai_funds"),
    # BORG Signal
    path("api/signal/", __import__("limit_connect_ai.views_signal", fromlist=["submit_signal"]).submit_signal, name="borg_signal"),
]


# AI Actions review
from . import views_ai_actions  # noqa: E402
urlpatterns += [
    path("actions/<int:action_id>/review/", views_ai_actions.review_action, name="review_ai_action"),
    path("actions/", views_ai_actions.ai_actions_list, name="ai_actions_list"),
]

# Claude Doktor
from . import views_doktor  # noqa: E402
urlpatterns += [
    path("doktor/", views_doktor.doktor_dashboard, name="doktor_dashboard"),
    path("doktor/<int:company_id>/", views_doktor.doktor_dashboard, name="doktor_dashboard_company"),
    path("superadmin/doktor/", views_doktor.doktor_superadmin, name="doktor_superadmin"),
    path("doktor/<int:company_id>/trigger/", views_doktor.doktor_trigger, name="doktor_trigger"),
]
