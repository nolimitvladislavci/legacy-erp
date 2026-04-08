import logging
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.template.loader import render_to_string
from django.views.decorators.http import require_GET
from django.views.decorators.cache import cache_page

logger = logging.getLogger(__name__)


@require_GET
def preuzmi_vodic(request):
    """Generira i vraca PDF vodic za memio.pet."""
    import weasyprint

    context = {"MEDIA_URL": settings.MEDIA_URL}
    html_string = render_to_string("no_limit/pdf/memio_vodic.html", context, request=request)

    base_url = f"https://{request.get_host()}/"
    pdf_file = weasyprint.HTML(
        string=html_string,
        base_url=base_url,
    ).write_pdf()

    response = HttpResponse(pdf_file, content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="memio-pet-digitalna-zastita-zivotinja-2026.pdf"'
    return response


@require_GET
def vodic_online(request):
    """HTML verzija vodica za citanje online."""
    context = {"MEDIA_URL": settings.MEDIA_URL}
    return render(request, "no_limit/vodic_online.html", context)


def prijava_azila(request):
    """Forma za prijavu azila."""
    from no_limit.models import AzilPrijava

    if request.method == "POST":
        naziv = request.POST.get("naziv", "").strip()
        email = request.POST.get("email", "").strip()
        grad = request.POST.get("grad", "").strip()
        poruka = request.POST.get("poruka", "").strip()
        if naziv and email and grad:
            AzilPrijava.objects.create(naziv=naziv, email=email, grad=grad, poruka=poruka)
            try:
                from core.whatsapp import send_whatsapp
                wa_number = getattr(settings, "IVAN_WHATSAPP_NUMBER", "")
                if wa_number:
                    send_whatsapp(wa_number, f"Nov azil: {naziv}, {grad} ({email})")
            except Exception:
                pass
            return redirect("/no-limit/?prijava=ok")
    return redirect("/no-limit/")


@cache_page(300)
def azil_landing(request):
    """Landing page za azil program — /no-limit/."""
    return render(request, "no_limit/azil_landing.html")
