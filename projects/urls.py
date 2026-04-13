from django.urls import include, path
from rest_framework.routers import DefaultRouter
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

from . import views

router = DefaultRouter()
router.register(r"api/projects", views.ProjectViewSet)
router.register(r"api/photos", views.ProjectPhotoViewSet, basename="projectphoto")

urlpatterns = [
    path("", views.index, name="projects_index"),
    path("new/", views.project_create, name="project_create"),
    path("<int:pk>/", views.project_detail, name="project_detail"),
    path("<int:pk>/edit/", views.project_edit, name="project_edit"),
    path("<int:pk>/update/", views.project_update_add, name="project_update_add"),
    path("upload-photo/", views.upload_photo, name="upload_photo"),
    path("", include(router.urls)),
    path("<int:pk>/team/add/", views.project_team_add, name="project_team_add"),
    path("<int:pk>/team/remove/", views.project_team_remove, name="project_team_remove"),
]
