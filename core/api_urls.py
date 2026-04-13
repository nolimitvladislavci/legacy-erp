"""
API documentation URLs — include in core/urls.py:

    from core.api_urls import api_doc_patterns
    urlpatterns += api_doc_patterns
"""

from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

api_doc_patterns = [
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]
