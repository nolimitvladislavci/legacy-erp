"""
eracun/views_posrednik.py
Posrednik setup wizard + "Veliko Dugme" za slanje e-racuna.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _

from core.company_utils import get_user_company


@login_required
def posrednik_setup(request):
    """Posrednik setup wizard — rucni unos ILI AI paste."""
    company = get_user_company(request)
    if not company:
        messages.error(request, _("Niste povezani s tvrtkom. Odaberite tvrtku iz izbornika."))
        return redirect("dashboard")

    from .models import ERacunConfig

    config, _ = ERacunConfig.objects.get_or_create(company=company)

    if request.method == "POST":
        action = request.POST.get("action", "save")

        if action == "ai_parse":
            # AI parse from pasted text (email, document)
            raw_text = request.POST.get("raw_text", "")
            if raw_text.strip():
                from .services.ai_config_parser import parse_posrednik_config_ai

                parsed = parse_posrednik_config_ai(raw_text)
                config.posrednik_raw_config = parsed
                config.save(update_fields=["posrednik_raw_config"])
                return render(
                    request,
                    "eracun/posrednik_setup.html",
                    {
                        "config": config,
                        "parsed": parsed,
                        "parsed_confidence": round(parsed.get("_confidence", 0) * 100),
                        "raw_text": raw_text,
                        "step": "confirm",
                    },
                )
            else:
                messages.warning(request, _("Zalijepite tekst iz emaila ili dokumenta posrednika."))
                return redirect("eracun:posrednik_setup")

        elif action == "save":
            # Manual save
            config.posrednik_type = request.POST.get("posrednik_type", "")
            config.posrednik_api_url = request.POST.get("posrednik_api_url", "")
            config.posrednik_api_key = request.POST.get("posrednik_api_key", "")
            config.posrednik_api_secret = request.POST.get("posrednik_api_secret", "")
            config.posrednik_username = request.POST.get("posrednik_username", "")
            config.posrednik_password = request.POST.get("posrednik_password", "")
            config.posrednik_company_id = request.POST.get("posrednik_company_id", "")
            config.posrednik_test_mode = request.POST.get("posrednik_test_mode") == "on"
            config.posrednik_status = "testing"
            config.is_active = True
            config.save()
            messages.success(request, _("Posrednik konfiguriran! Testirajte vezu."))
            return redirect("eracun:posrednik_setup")

        elif action == "test":
            # Test connection to posrednik
            result = _test_posrednik(config)
            if result["success"]:
                config.posrednik_status = "active"
                config.posrednik_connected_at = timezone.now()
                config.save(update_fields=["posrednik_status", "posrednik_connected_at"])
                messages.success(request, f"Veza uspjesna! {result['message']}")
            else:
                config.posrednik_status = "error"
                config.save(update_fields=["posrednik_status"])
                messages.error(request, _("Radnja nije uspjela. Pokušajte ponovo."))
            return redirect("eracun:posrednik_setup")

    return render(
        request,
        "eracun/posrednik_setup.html",
        {
            "config": config,
            "step": "setup",
        },
    )


@login_required
def send_eracun_button(request, invoice_pk):
    """
    VELIKO DUGME — posalji e-racun s 3 razine potvrde.
    Step 1: Pregled (GET) — prikazi sto ce se poslati
    Step 2: Potvrda (POST confirm=1) — "Jeste li sigurni?"
    Step 3: Slanje (POST confirm=2) — "ZADNJA SANSA — posalji?"
    """
    from invoicing.models import Invoice

    from .models import ERacunConfig

    company = get_user_company(request)
    invoice = get_object_or_404(Invoice, pk=invoice_pk, company=company)

    config = ERacunConfig.objects.filter(company=company, is_active=True).first()
    if not config:
        messages.error(request, _("e-Racun nije konfiguriran. Idite na Postavke posrednika."))
        return redirect("eracun:posrednik_setup")

    if request.method == "GET":
        # Step 1: Preview
        return render(
            request,
            "eracun/send_button.html",
            {
                "invoice": invoice,
                "config": config,
                "step": 1,
            },
        )

    confirm_level = int(request.POST.get("confirm", 0))

    if confirm_level == 1:
        # Step 2: "Jeste li sigurni?"
        return render(
            request,
            "eracun/send_button.html",
            {
                "invoice": invoice,
                "config": config,
                "step": 2,
            },
        )

    if confirm_level == 2:
        # Step 3: FINAL — actually send
        from invoicing.services.entry_point import FiscalHandlerRegistry

        handler = FiscalHandlerRegistry.get(company, invoice)
        result = handler.process(invoice)

        if result.success:
            invoice.status = "FISCALIZED"
            invoice.save(update_fields=["status"])
            messages.success(request, f"e-Racun poslan! {result.message}")
        else:
            messages.error(request, _("Radnja nije uspjela. Pokušajte ponovo."))

        return redirect("eracun:dashboard")

    return redirect("eracun:dashboard")


def _test_posrednik(config):
    """Test connection to posrednik API."""
    if not config.posrednik_api_url:
        return {"success": False, "message": "API URL nije postavljen"}
    if not config.posrednik_api_key and not config.posrednik_username:
        return {"success": False, "message": "Nema kredencijala (API key ili username)"}

    try:
        import requests

        headers = {}
        if config.posrednik_api_key:
            headers["Authorization"] = f"Bearer {config.posrednik_api_key}"

        # Try a simple health/status endpoint
        url = config.posrednik_api_url.rstrip("/")
        for endpoint in ["/status", "/health", "/api/status", ""]:
            try:
                r = requests.get(url + endpoint, headers=headers, timeout=10)
                if r.status_code < 500:
                    return {
                        "success": r.status_code < 400,
                        "message": f"HTTP {r.status_code} od {url}{endpoint}",
                        "response": r.text[:200],
                    }
            except requests.RequestException:
                continue

        return {"success": False, "message": f"Ne mogu se spojiti na {url}"}

    except ImportError:
        return {"success": False, "message": "requests modul nije instaliran"}
    except requests.RequestException as e:
        return {"success": False, "message": str(e)}
