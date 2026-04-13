from django.urls import include, path
from rest_framework.routers import DefaultRouter
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

from . import views

router = DefaultRouter()
router.register(r"api", views.InsurancePolicyViewSet)

app_name = "insurance"
urlpatterns = [
    path("", views.policy_list, name="list"),
    path("new/", views.policy_create, name="create"),
    path("<int:pk>/edit/", views.policy_edit, name="edit"),
    path("<int:pk>/delete/", views.policy_delete, name="delete"),
    path("", include(router.urls)),
]
