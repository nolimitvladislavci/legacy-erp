from django.urls import include, path
from rest_framework.routers import DefaultRouter
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

from . import views

router = DefaultRouter()
router.register(r"api/members", views.MemberViewSet)
router.register(r"api/checkins", views.MemberCheckInViewSet)

app_name = "fitness"
urlpatterns = [
    path("", views.member_list, name="member_list"),
    path("", views.member_list, name="list"),
    path("new/", views.member_create, name="create"),
    path("<int:pk>/", views.member_detail, name="member_detail"),
    path("<int:pk>/edit/", views.member_edit, name="edit"),
    path("<int:pk>/checkin/", views.member_checkin, name="checkin"),
    path("dashboard/", views.checkin_dashboard, name="checkin_dashboard"),
    path("dashboard/", views.checkin_dashboard, name="dashboard"),
    path("", include(router.urls)),
]
