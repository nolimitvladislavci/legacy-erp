"""
core/audit_access.py — Sensitive data access audit decorator.

GDPR Article 5(1)(f) — integrity and confidentiality.
Logs 'read' actions to SystemAuditLog when users access sensitive data.

Usage:
    from core.audit_access import audit_sensitive_access

    @audit_sensitive_access('payroll.Payslip', description='Pregled platnog listića')
    @login_required
    def payslip_detail(request, pk):
        ...
"""
import functools
import logging

from django.db import DatabaseError, IntegrityError
from django.utils import timezone

logger = logging.getLogger(__name__)


def audit_sensitive_access(model_name, description='', get_object_id=None):
    """
    Decorator that logs a 'read' entry in SystemAuditLog when a view is accessed.

    Args:
        model_name: Dotted model path (e.g. 'payroll.Payslip')
        description: Human-readable description for the log
        get_object_id: Optional callable(request, *args, **kwargs) → str object_id.
                       Default: extracts 'pk' from kwargs.
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Execute the view first
            response = view_func(request, *args, **kwargs)

            # Only log successful reads (2xx/3xx)
            status = getattr(response, 'status_code', 200)
            if status >= 400:
                return response

            # Extract object_id
            if get_object_id:
                obj_id = get_object_id(request, *args, **kwargs)
            else:
                obj_id = str(kwargs.get('pk', kwargs.get('id', '')))

            # Get company from thread-local
            try:
                from core.tenant import get_current_company
                company = get_current_company()
            except ImportError:
                company = None

            # Get IP
            ip = (
                request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
                or request.META.get('REMOTE_ADDR')
            )

            # Log the read
            try:
                from core.models import SystemAuditLog
                SystemAuditLog.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    company=company,
                    action='read',
                    model_name=model_name,
                    object_id=obj_id,
                    object_repr=description or f'Access to {model_name}',
                    changes={
                        'path': request.path,
                        'method': request.method,
                        'timestamp': timezone.now().isoformat(),
                    },
                    ip_address=ip,
                )
            except (IntegrityError, DatabaseError) as e:
                logger.debug('Audit access log failed: %s', e)

            return response
        return wrapper
    return decorator


def audit_bulk_access(model_name, description=''):
    """
    Decorator for list views that access multiple records.
    Logs a single 'read' entry with count of records accessed.
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            response = view_func(request, *args, **kwargs)

            status = getattr(response, 'status_code', 200)
            if status >= 400:
                return response

            try:
                from core.models import SystemAuditLog
                from core.tenant import get_current_company
                company = get_current_company()
                ip = (
                    request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
                    or request.META.get('REMOTE_ADDR')
                )
                SystemAuditLog.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    company=company,
                    action='read',
                    model_name=model_name,
                    object_id='list',
                    object_repr=description or f'List access to {model_name}',
                    changes={
                        'path': request.path,
                        'query': request.GET.dict(),
                        'timestamp': timezone.now().isoformat(),
                    },
                    ip_address=ip,
                )
            except (IntegrityError, DatabaseError) as e:
                logger.debug('Audit bulk access log failed: %s', e)

            return response
        return wrapper
    return decorator
