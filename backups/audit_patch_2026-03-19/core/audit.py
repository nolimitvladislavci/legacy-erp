"""
Audit trail via Django signals.
Covers all critical financial models with post_save and post_delete.
Uses threading.local() to get current user from middleware.
"""
import threading
from django.db.models.signals import post_save, post_delete, pre_save

_thread_locals = threading.local()


def get_current_user():
    return getattr(_thread_locals, 'user', None)


def get_current_ip():
    return getattr(_thread_locals, 'ip', None)


class AuditMiddleware:
    """Stores current user and IP in thread-local for signal access."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _thread_locals.user = getattr(request, 'user', None)
        _thread_locals.ip = (
            request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
            or request.META.get('REMOTE_ADDR')
        )
        response = self.get_response(request)
        return response


# Models to audit - add model paths here
AUDITED_MODELS = [
    'konto.JournalEntry',
    'konto.LedgerLine',
    'konto.AccountingPeriod',
    'konto.BankTransaction',
    'invoicing.Invoice',
    'invoicing.InvoiceItem',
    'partners.Partner',
    'inventory.InventoryItem',
    'payments.Payment',
    'payroll.PayrollRun',
    'worktime.TravelOrder',
]


def _safe_value(val):
    """Convert value to JSON-safe type."""
    if val is None:
        return None
    if isinstance(val, (str, int, float, bool)):
        return val
    return str(val)


def _get_changes(instance, created):
    """Extract changes dict for audit log."""
    if created:
        data = {}
        for f in instance._meta.concrete_fields:
            val = getattr(instance, f.attname, None)
            if val is not None:
                data[f.name] = _safe_value(val)
        return data

    if hasattr(instance, '_audit_old_values'):
        changes = {}
        for field_name, old_val in instance._audit_old_values.items():
            new_val = getattr(instance, field_name, None)
            if str(old_val) != str(new_val):
                changes[field_name] = {
                    'old': str(old_val) if old_val is not None else None,
                    'new': str(new_val) if new_val is not None else None,
                }
        return changes
    return {}


def _should_audit(instance):
    """Check if this model instance should be audited."""
    model_path = f"{instance._meta.app_label}.{instance.__class__.__name__}"
    return model_path in AUDITED_MODELS


def _log_action(instance, action, created=False):
    """Create an audit log entry."""
    if not _should_audit(instance):
        return

    from core.models import SystemAuditLog

    company = None
    if hasattr(instance, 'company_id'):
        company_id = instance.company_id
        if company_id:
            from companies.models import Company
            try:
                company = Company.objects.get(pk=company_id)
            except Company.DoesNotExist:
                pass

    user = get_current_user()
    if user and not user.is_authenticated:
        user = None

    try:
        SystemAuditLog.objects.create(
            user=user,
            company=company,
            action=action,
            model_name=f"{instance._meta.app_label}.{instance.__class__.__name__}",
            object_id=str(instance.pk),
            object_repr=str(instance)[:300],
            changes=_get_changes(instance, created) if action != 'delete' else {'deleted': str(instance)[:200]},
            ip_address=get_current_ip(),
        )
    except Exception:
        pass  # Never let audit logging break the main operation


def audit_post_save(sender, instance, created, **kwargs):
    action = 'create' if created else 'update'
    _log_action(instance, action, created)


def audit_post_delete(sender, instance, **kwargs):
    _log_action(instance, 'delete')


def audit_pre_save(sender, instance, **kwargs):
    """Store old values before save for change tracking."""
    if instance.pk:
        try:
            old = sender.objects.get(pk=instance.pk)
            instance._audit_old_values = {
                f.name: getattr(old, f.name) for f in old._meta.concrete_fields
            }
        except sender.DoesNotExist:
            pass


def connect_audit_signals():
    """Connect signals to all audited models. Call from AppConfig.ready()."""
    from django.apps import apps

    for model_path in AUDITED_MODELS:
        try:
            app_label, model_name = model_path.split('.')
            model = apps.get_model(app_label, model_name)
            pre_save.connect(audit_pre_save, sender=model, dispatch_uid=f'audit_pre_{model_path}')
            post_save.connect(audit_post_save, sender=model, dispatch_uid=f'audit_post_{model_path}')
            post_delete.connect(audit_post_delete, sender=model, dispatch_uid=f'audit_del_{model_path}')
        except Exception:
            pass
