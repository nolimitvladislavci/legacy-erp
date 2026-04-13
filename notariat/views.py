from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.db import DatabaseError
from django.shortcuts import render

from .models import DimnjacarskaInspekcija, PravniPredmet


@login_required
def pravnik_dashboard(request):
    company = request.user.userprofile.company
    predmeti = PravniPredmet.objects.filter(company=company, status="aktivan")
    pred_s_rokom = predmeti.filter(rok__gte=date.today(), rok__lte=date.today() + timedelta(days=7))
    return render(
        request,
        "notariat/pravnik_dashboard.html",
        {
            "predmeti": predmeti,
            "pred_s_rokom": pred_s_rokom,
            "page_title": "Odvjetnički dashboard",
        },
    )


@login_required
def dimnjacari_dashboard(request):
    company = request.user.userprofile.company
    inspekcije = DimnjacarskaInspekcija.objects.filter(company=company)
    sljedeci = inspekcije.filter(
        sljedeci_pregled__gte=date.today(), sljedeci_pregled__lte=date.today() + timedelta(days=30)
    ).order_by("sljedeci_pregled")
    return render(
        request,
        "notariat/dimnjacari_dashboard.html",
        {
            "inspekcije": inspekcije,
            "sljedeci": sljedeci,
            "page_title": "Dimnjačarski pregledi",
        },
    )


# ════════════════════════════════════════════════════════════
# PDF Generation (WeasyPrint) + Tarifa API
# ════════════════════════════════════════════════════════════

import hashlib

from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string


def _generate_notariat_pdf(request, template_name, context, filename):
    """Shared WeasyPrint PDF generator for all notariat documents."""
    import weasyprint
    from django.conf import settings

    context["MEDIA_URL"] = settings.MEDIA_URL
    context["STATIC_URL"] = settings.STATIC_URL
    html = render_to_string(template_name, context, request=request)
    base_url = f"https://{request.get_host()}/"
    pdf_bytes = weasyprint.HTML(string=html, base_url=base_url).write_pdf()

    # SHA-256 integrity
    sha = hashlib.sha256(pdf_bytes).hexdigest()
    context["_sha256"] = sha

    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["X-Document-Hash"] = sha
    return response, pdf_bytes, sha


@login_required
def potvrda_dimnjaka_pdf(request, pk):
    """Generira PDF: Potvrda o ispravnosti dimnjaka (NN 103/15)."""
    from django.shortcuts import get_object_or_404

    from .models import DimnjacarskaInspekcija

    insp = get_object_or_404(DimnjacarskaInspekcija, pk=pk, company=request.user.userprofile.company)

    ctx = {"insp": insp, "company": insp.company}
    response, pdf_bytes, sha = _generate_notariat_pdf(
        request,
        "notariat/pdf/potvrda_dimnjaka.html",
        ctx,
        f"potvrda_dimnjak_{insp.broj_dimnjaka}_{insp.datum_pregleda}.pdf",
    )

    # Save hash
    insp.pdf_sha256 = sha
    insp.save(update_fields=["pdf_sha256"])

    # Archive
    try:
        from documents.models import ArhivaEntry

        ArhivaEntry.objects.get_or_create(
            source_type="document",
            source_id=f"dimnjak-{insp.pk}",
            defaults={
                "company": insp.company,
                "doc_number": f"DIM-{insp.pk}",
                "partner_name": (insp.klijent.name if insp.klijent else insp.adresa)[:200],
                "amount": 0,
                "currency": "EUR",
                "doc_date": insp.datum_pregleda,
                "ai_summary": f"Dimnjak {insp.broj_dimnjaka}: {insp.get_status_dimnjaka_display()}",
            },
        )
    except DatabaseError:
        pass

    return response


@login_required
def punomoc_pdf(request):
    """Generira PDF: Opunomoćenje (punomoć)."""
    company = request.user.userprofile.company
    ctx = {
        "company": company,
        "opunomocitelj": request.GET.get("opunomocitelj", ""),
        "opunomocitelj_oib": request.GET.get("oib", ""),
        "opunomocenik": request.GET.get("opunomocenik", ""),
        "svrha": request.GET.get("svrha", ""),
        "datum": request.GET.get("datum", ""),
    }
    response, _, _ = _generate_notariat_pdf(request, "notariat/pdf/punomoc.html", ctx, "punomoc.pdf")
    return response


@login_required
def osnivanje_jdoo_pdf(request):
    """Generira PDF: Osnivački akt j.d.o.o."""
    company = request.user.userprofile.company
    ctx = {
        "company": company,
        "naziv_tvrtke": request.GET.get("naziv", ""),
        "osnivac": request.GET.get("osnivac", ""),
        "osnivac_oib": request.GET.get("oib", ""),
        "temeljni_kapital": request.GET.get("kapital", "10.00"),
        "sjediste": request.GET.get("sjediste", ""),
        "djelatnost": request.GET.get("djelatnost", ""),
        "nkd_kod": request.GET.get("nkd", ""),
    }
    response, _, _ = _generate_notariat_pdf(request, "notariat/pdf/osnivanje_jdoo.html", ctx, "osnivacki_akt_jdoo.pdf")
    return response


@login_required
def kupoprodaja_pdf(request):
    """Generira PDF: Ugovor o kupoprodaji nekretnine."""
    company = request.user.userprofile.company
    ctx = {
        "company": company,
        "prodavatelj": request.GET.get("prodavatelj", ""),
        "kupac": request.GET.get("kupac", ""),
        "nekretnina": request.GET.get("nekretnina", ""),
        "kat_cestica": request.GET.get("cestica", ""),
        "cijena": request.GET.get("cijena", ""),
        "datum": request.GET.get("datum", ""),
    }
    response, _, _ = _generate_notariat_pdf(request, "notariat/pdf/kupoprodaja.html", ctx, "ugovor_kupoprodaja.pdf")
    return response


@login_required
def zaduznica_pdf(request):
    """Generira PDF: Zadužnica (solemnizirana)."""
    company = request.user.userprofile.company
    ctx = {
        "company": company,
        "duznik": request.GET.get("duznik", ""),
        "duznik_oib": request.GET.get("oib", ""),
        "vjerovnik": request.GET.get("vjerovnik", ""),
        "iznos": request.GET.get("iznos", ""),
        "iban": request.GET.get("iban", ""),
        "datum": request.GET.get("datum", ""),
    }
    response, _, _ = _generate_notariat_pdf(request, "notariat/pdf/zaduznica.html", ctx, "zaduznica.pdf")
    return response


def api_tarifa(request):
    """API: Izračun bilježničke tarife."""
    from .tarifa import izracunaj_tarifu

    vrsta = request.GET.get("vrsta", "")
    vrijednost = request.GET.get("vrijednost", "0")
    try:
        vrijednost = float(vrijednost)
    except ValueError:
        vrijednost = 0
    result = izracunaj_tarifu(vrsta, vrijednost)
    # Serialize Decimals
    return JsonResponse({k: float(v) if hasattr(v, "quantize") else v for k, v in result.items()})
