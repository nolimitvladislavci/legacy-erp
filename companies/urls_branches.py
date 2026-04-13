"""
companies/urls_branches.py
Shim: re-exports URL patterns from the 'branches' app so that
core/urls.py can include('companies.urls_branches', namespace='branches').
"""
from branches.urls import app_name, urlpatterns  # noqa: F401
