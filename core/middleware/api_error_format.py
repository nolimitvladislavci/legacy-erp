"""
core/middleware/api_error_format.py
Standardizes all JSON error responses from /api/ endpoints to:
  {"status": "error", "code": <http_code>, "message": "..."}
"""
import json
import logging
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

logger = logging.getLogger(__name__)


class ApiErrorFormatMiddleware:
    """
    Intercepts JSON responses from API endpoints with status >= 400
    and normalizes them to a consistent format.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Only process API endpoints returning JSON errors
        if not self._is_api_request(request):
            return response

        if response.status_code < 400:
            return response

        content_type = response.get('Content-Type', '')
        if 'application/json' not in content_type:
            return response

        try:
            data = json.loads(response.content)
        except (ValueError, json.JSONDecodeError):
            return response

        # Already in standard format
        if 'status' in data and 'code' in data and 'message' in data:
            return response

        # Normalize
        normalized = {
            'status': 'error',
            'code': response.status_code,
            'message': data.get('error') or data.get('detail') or data.get('message') or str(data),
        }

        # Preserve extra fields (like 'difference_pct', 'code' from CartError, etc.)
        for key in data:
            if key not in ('error', 'detail', 'status'):
                normalized[key] = data[key]

        response.content = json.dumps(normalized, ensure_ascii=False).encode('utf-8')
        return response

    @staticmethod
    def _is_api_request(request):
        return '/api/' in request.path
