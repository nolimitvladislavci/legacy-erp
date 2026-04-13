from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

from .models import FiscalConfiguration, FiscalLog, FiscalProvider
from .providers.de_tse import DETseProvider
from .providers.hr_fina import HRFinaProvider


@login_required
def test_connection(request):
    config_id = request.GET.get("config_id")
    if not config_id:
        return JsonResponse({"ok": False, "error": "config_id required"})
    try:
        config = FiscalConfiguration.objects.get(pk=config_id)
    except FiscalConfiguration.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Config not found"})
    providers = {FiscalProvider.HR_FINA: HRFinaProvider, FiscalProvider.DE_TSE: DETseProvider}
    provider_class = providers.get(config.provider)
    if not provider_class:
        return JsonResponse({"ok": False, "error": "Unknown provider"})
    ok = provider_class(config).test_connection()
    return JsonResponse({"ok": ok, "provider": config.get_provider_display()})


@login_required
def fiscal_status(request):
    configs = FiscalConfiguration.objects.filter(is_active=True).select_related("company", "branch")
    recent_logs = FiscalLog.objects.select_related("config")[:20]
    return JsonResponse(
        {
            "configs": [
                {
                    "id": c.id,
                    "company": str(c.company),
                    "branch": str(c.branch) if c.branch else None,
                    "provider": c.get_provider_display(),
                    "test_mode": c.is_test_mode,
                }
                for c in configs
            ],
            "recent_logs": [
                {
                    "id": l.id,
                    "receipt_type": l.receipt_type,
                    "receipt_id": l.receipt_id,
                    "status": l.status,
                    "created_at": l.created_at.isoformat(),
                }
                for l in recent_logs
            ],
        }
    )
