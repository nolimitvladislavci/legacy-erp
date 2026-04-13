"""Public library portal URLs — outside i18n, public-facing."""
from django.urls import path

from .public_views import (
    public_book,
    public_home,
    public_member_portal,
    public_reserve,
    public_search,
)

# These are mounted at /lib/<slug>/ in core/urls.py
urlpatterns = [
    path("", public_home, name="library_public_home"),
    path("pretraga/", public_search, name="library_public_search"),
    path("knjiga/<int:pk>/", public_book, name="library_public_book"),
    path("knjiga/<int:pk>/rezerviraj/", public_reserve, name="library_public_reserve"),
    path("portal/", public_member_portal, name="library_public_portal"),
]
