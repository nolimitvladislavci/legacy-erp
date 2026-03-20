"""
Permission decorators for views
"""
from functools import wraps

from django.contrib import messages
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect

from .manager import PermissionManager


def require_permission(permission_codename, company_param='company_id'):
    """
    Decorator to require specific permission

    Usage:
        @require_permission('invoices.create')
        def create_invoice(request):
            ...

        @require_permission('companies.edit', company_param='pk')
        def edit_company(request, pk):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')

            # Get company from request
            company = None
            if company_param:
                company_id = kwargs.get(company_param) or request.GET.get(company_param)
                if company_id:
                    from companies.models import Company
                    try:
                        company = Company.objects.get(pk=company_id)
                    except Company.DoesNotExist:
                        pass

            # Check permission
            has_perm = PermissionManager.has_permission(
                request.user,
                permission_codename,
                company
            )

            if not has_perm:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'error': 'Permission denied',
                        'required_permission': permission_codename
                    }, status=403)

                messages.error(request, f'Nemate dozvolu: {permission_codename}')
                return HttpResponseForbidden('Permission denied')

            return view_func(request, *args, **kwargs)

        return wrapper
    return decorator
def require_any_permission(*permission_codenames, company_param='company_id'):
    """Require ANY of the listed permissions"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')

            company = None
            if company_param:
                company_id = kwargs.get(company_param) or request.GET.get(company_param)
                if company_id:
                    from companies.models import Company
                    try:
                        company = Company.objects.get(pk=company_id)
                    except Company.DoesNotExist:
                        pass

            has_perm = PermissionManager.has_any_permission(
                request.user,
                permission_codenames,
                company
            )

            if not has_perm:
                messages.error(request, 'Nemate potrebne dozvole')
                return HttpResponseForbidden('Permission denied')

            return view_func(request, *args, **kwargs)

        return wrapper
    return decorator
def require_role(*role_types):
    """
    Require specific role(s)

    Usage:
        @require_role('superadmin', 'company_admin')
        def admin_view(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')

            # Superusers bypass role checks
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            # Tenant admins can access superadmin views (with filtered data)
            if 'superadmin' in role_types:
                try:
                    if request.user.profile.role == 'tenant_admin':
                        return view_func(request, *args, **kwargs)
                except Exception:
                    pass

            user_role = PermissionManager.get_user_role(request.user)

            if not user_role or user_role.role_type not in role_types:
                messages.error(request, 'Nemate odgovarajucu ulogu')
                return HttpResponseForbidden('Insufficient role')

            return view_func(request, *args, **kwargs)

        return wrapper
    return decorator
