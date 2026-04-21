import hashlib
import logging

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  LANDING
# ═══════════════════════════════════════════════════════════════


def landing(request):
    """Landing page — no-limit.world."""
    from no_limit.models import AmbassadorApplication

    prijava_ok = request.GET.get("prijava") == "ok"
    ambasadori = AmbassadorApplication.objects.filter(status__in=["approved", "active"])
    return render(
        request,
        "no_limit/landing.html",
        {
            "prijava_ok": prijava_ok,
            "ambasadori": ambasadori,
            "ambasador_count": ambasadori.count(),
        },
    )


# ═══════════════════════════════════════════════════════════════
#  STATUT
# ═══════════════════════════════════════════════════════════════


def statut(request):
    """Online čitanje statuta."""
    return render(request, "no_limit/statut.html")


def statut_pdf(request):
    """PDF download statuta s evalidator pečatom."""
    import weasyprint

    ctx = {
        "doc_id": "STATUT-NL",
        "doc_version": "1.0.0",
        "doc_date": "16.04.2026.",
        "doc_issuer": "No-limit udruga",
        "doc_url": "https://no-limit.world/statut/",
        "doc_hash": "",
        "doc_hash_short": "",
    }
    html = render_to_string("no_limit/pdf/statut_no_limit.html", ctx)
    content_hash = hashlib.sha256(html.encode()).hexdigest()
    ctx["doc_hash"] = content_hash
    ctx["doc_hash_short"] = content_hash[:16]
    html_final = render_to_string("no_limit/pdf/statut_no_limit.html", ctx)

    pdf_bytes = weasyprint.HTML(string=html_final).write_pdf()
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="statut_no_limit_v1.0.0.pdf"'
    response["X-Document-Hash"] = hashlib.sha256(pdf_bytes).hexdigest()
    return response


# ═══════════════════════════════════════════════════════════════
#  AMBASADORI
# ═══════════════════════════════════════════════════════════════


def ambasadori(request):
    """Pregled ambasadorske mreže."""
    from no_limit.models import AmbassadorApplication

    active = AmbassadorApplication.objects.filter(status__in=["approved", "active"])
    return render(request, "no_limit/ambasadori.html", {"ambasadori": active})


def _make_qr_b64(data: str) -> str:
    """Generira base64 PNG QR kod (gold on dark)."""
    try:
        import base64, io
        import qrcode

        qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=2)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#c9a84c", back_color="#0a0a0a")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return ""


def ambasador_prijava(request):
    """Forma za prijavu ambasadora + WA notifikacija."""
    from no_limit.models import AmbassadorApplication

    if request.method == "POST":
        full_name = request.POST.get("full_name", "").strip()
        email = request.POST.get("email", "").strip()
        country = request.POST.get("country", "").strip()
        city = request.POST.get("city", "").strip()
        organization = request.POST.get("organization", "").strip()
        organization_type = request.POST.get("organization_type", "").strip()
        desired_role = request.POST.get("desired_role", "national_coordinator").strip()
        motivation = request.POST.get("motivation", "").strip()
        experience = request.POST.get("experience", "").strip()
        languages = request.POST.get("languages", "").strip()
        phone = request.POST.get("phone", "").strip()
        device_tz = request.POST.get("device_tz", "").strip()[:60]
        device_platform = request.POST.get("device_platform", "").strip()[:30]
        # Pohrani device podatke u experience polje (metadata)
        if device_tz or device_platform:
            if not experience:
                experience = f"[Device: {device_platform}, TZ: {device_tz}]"
            else:
                experience = f"{experience} [Device: {device_platform}, TZ: {device_tz}]"

        if full_name and email and country and motivation:
            AmbassadorApplication.objects.create(
                full_name=full_name,
                email=email,
                country=country,
                city=city,
                organization=organization,
                organization_type=organization_type,
                desired_role=desired_role,
                motivation=motivation,
                experience=experience,
                languages=languages,
                phone=phone,
            )
            # WA notifikacija Ivanu
            try:
                from core.whatsapp import send_text as send_whatsapp

                wa_number = getattr(settings, "IVAN_WHATSAPP_NUMBER", "")
                if wa_number:
                    country_display = dict(AmbassadorApplication.COUNTRY_CHOICES).get(country, country)
                    role_display = dict(AmbassadorApplication.ROLE_CHOICES).get(desired_role, desired_role)
                    send_whatsapp(
                        wa_number,
                        f"Nova ambasadorska prijava!\n{full_name} iz {country_display}\nUloga: {role_display}\nOrg: {organization or 'N/A'}\nEmail: {email}",
                    )
            except Exception:
                logger.exception("WA notification failed for ambassador application")
            return redirect("/ambasadori/hvala/")

    # QR kod koji otvara ovu stranicu s ?qr=1 (za mobilni scan)
    qr_url = request.build_absolute_uri("/no-limit/ambasadori/prijava/?qr=1")
    qr_b64 = _make_qr_b64(qr_url)
    return render(request, "no_limit/ambasador_prijava.html", {"qr_b64": qr_b64, "qr_url": qr_url})


def ambasador_hvala(request):
    """Thank you stranica nakon prijave."""
    return render(request, "no_limit/ambasador_hvala.html")


def ambasador_ugovor_pdf(request):
    """PDF: Ambasadorski ugovor (A1) s evalidator pečatom."""
    import weasyprint

    ctx = {
        "doc_id": "A1",
        "doc_version": "1.0.0",
        "doc_date": "16.04.2026.",
        "doc_issuer": "No-limit udruga",
        "doc_url": "https://no-limit.world/dokumenti/",
        "doc_hash": "",
        "doc_hash_short": "",
        "amb_name": request.GET.get("name", "[Ime i prezime ambasadora]"),
        "amb_country": request.GET.get("country", "[država]"),
        "amb_email": request.GET.get("email", "[email]"),
        "amb_role": request.GET.get("role", "nacionalni koordinator"),
    }
    html = render_to_string("no_limit/pdf/ambasadorski_ugovor.html", ctx)
    content_hash = hashlib.sha256(html.encode()).hexdigest()
    ctx["doc_hash"] = content_hash
    ctx["doc_hash_short"] = content_hash[:16]
    html_final = render_to_string("no_limit/pdf/ambasadorski_ugovor.html", ctx)

    pdf_bytes = weasyprint.HTML(string=html_final).write_pdf()
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="ambasadorski_ugovor_A1.pdf"'
    response["X-Document-Hash"] = hashlib.sha256(pdf_bytes).hexdigest()
    return response


# ═══════════════════════════════════════════════════════════════
#  OSTALE STRANICE
# ═══════════════════════════════════════════════════════════════


def o_nama(request):
    return render(request, "no_limit/o_nama.html")


def partneri(request):
    return render(request, "no_limit/partneri.html")


def kontakt(request):
    return render(request, "no_limit/kontakt.html")


def projekti(request):
    return render(request, "no_limit/projekti.html")


# ═══════════════════════════════════════════════════════════════
#  STARE VIEWS (backward compat)
# ═══════════════════════════════════════════════════════════════


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
            except ImportError:
                pass
            return redirect("/?prijava=ok")
    return redirect("/")
