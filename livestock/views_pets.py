"""
livestock/views_pets.py — Uzgajalište ljubimaca (Ljubeta pilot)

Rute: /pets/
"""

import json
import logging
import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db import DatabaseError, IntegrityError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from core.company_utils import get_user_company

from .models import HealthRecord, Livestock

logger = logging.getLogger(__name__)

PET_VRSTE = getattr(Livestock, "PET_VRSTE", ("pas", "macka", "konj", "zec", "ostalo_ljubimac"))


@login_required
def pet_list(request):
    company = get_user_company(request)
    pets = Livestock.objects.filter(company=company, vrsta__in=PET_VRSTE).order_by("name", "ear_tag")

    vrsta = request.GET.get("vrsta", "")
    if vrsta and vrsta in PET_VRSTE:
        pets = pets.filter(vrsta=vrsta)

    stats = {
        "ukupno": pets.count(),
        "psi": Livestock.objects.filter(company=company, vrsta="pas").count(),
        "macke": Livestock.objects.filter(company=company, vrsta="macka").count(),
        "konji": Livestock.objects.filter(company=company, vrsta="konj").count(),
    }
    return render(
        request,
        "livestock/pets_list.html",
        {
            "pets": pets,
            "stats": stats,
            "vrsta_filter": vrsta,
            "pet_vrste": [v for v in Livestock.VRSTA_CHOICES if v[0] in PET_VRSTE],
        },
    )


@login_required
def pet_detail(request, pk):
    company = get_user_company(request)
    pet = get_object_or_404(Livestock, pk=pk, company=company, vrsta__in=PET_VRSTE)
    records = pet.health_records.all()

    if request.method == "POST" and request.POST.get("action") == "delete":
        pet.delete()
        messages.success(request, _("Ljubimac obrisan."))
        return redirect("livestock:pet_list")

    if request.method == "POST" and request.POST.get("action") == "add_health":
        try:
            HealthRecord.objects.create(
                animal=pet,
                datum=request.POST.get("datum") or timezone.now().date(),
                tip=request.POST.get("tip", "pregled"),
                opis=request.POST.get("opis", "").strip(),
                veterinar=request.POST.get("veterinar", "").strip(),
                lijek=request.POST.get("lijek", "").strip(),
                trosak_eur=request.POST.get("trosak_eur") or None,
                created_by=request.user,
            )
            messages.success(request, _("Zapis dodan."))
        except (IntegrityError, DatabaseError):
            messages.error(request, _("Nešto je pošlo krivo. Pokušajte ponovo ili kontaktirajte podršku."))
        return redirect("livestock:pet_detail", pk=pk)

    return render(
        request,
        "livestock/pets_detail.html",
        {
            "pet": pet,
            "records": records,
            "tip_choices": HealthRecord.TIP_CHOICES,
        },
    )


@login_required
def pet_create(request):
    company = get_user_company(request)

    if request.method == "POST":
        try:
            vrsta = request.POST.get("vrsta", "pas")
            name = request.POST.get("name", "").strip()
            # ear_tag: za pse koristimo chip ili UUID-bazirani auto-ID
            chip = request.POST.get("chip_number", "").strip()
            ear_tag = chip or f"PET-{company.pk}-{uuid.uuid4().hex[:8].upper()}"

            pet = Livestock(
                company=company,
                vrsta=vrsta,
                name=name,
                ear_tag=ear_tag,
                breed=request.POST.get("breed", "").strip(),
                spol=request.POST.get("spol", "N"),
                color_description=request.POST.get("color_description", "").strip(),
                chip_number=chip,
                pedigree_number=request.POST.get("pedigree_number", "").strip(),
                father_name=request.POST.get("father_name", "").strip(),
                mother_name=request.POST.get("mother_name", "").strip(),
                notes=request.POST.get("notes", "").strip(),
                status="aktivno",
            )
            dob = request.POST.get("date_of_birth")
            if dob:
                pet.date_of_birth = dob
            weight = request.POST.get("weight_kg")
            if weight:
                try:
                    pet.weight_kg = float(weight)
                except (ValueError, TypeError):
                    pass
            if "photo" in request.FILES:
                pet.photo = request.FILES["photo"]
            pet.save()
            messages.success(request, f"{pet.get_vrsta_display()} {name} uspješno dodan/a.")
            return redirect("livestock:pet_detail", pk=pet.pk)
        except (ValueError, TypeError):
            messages.error(request, _("Nešto je pošlo krivo. Pokušajte ponovo ili kontaktirajte podršku."))

    return render(
        request,
        "livestock/pets_create.html",
        {
            "pet_vrste": [v for v in Livestock.VRSTA_CHOICES if v[0] in PET_VRSTE],
            "spol_choices": [("M", "Mužjak"), ("F", "Ženka"), ("N", "Nepoznato")],
        },
    )


@login_required
def pet_edit(request, pk):
    company = get_user_company(request)
    pet = get_object_or_404(Livestock, pk=pk, company=company, vrsta__in=PET_VRSTE)

    if request.method == "POST":
        try:
            pet.name = request.POST.get("name", pet.name).strip()
            pet.breed = request.POST.get("breed", pet.breed or "").strip()
            pet.spol = request.POST.get("spol", pet.spol)
            pet.color_description = request.POST.get("color_description", "").strip()
            pet.chip_number = request.POST.get("chip_number", "").strip()
            pet.pedigree_number = request.POST.get("pedigree_number", "").strip()
            pet.father_name = request.POST.get("father_name", "").strip()
            pet.mother_name = request.POST.get("mother_name", "").strip()
            pet.notes = request.POST.get("notes", "").strip()
            pet.status = request.POST.get("status", pet.status)
            dob = request.POST.get("date_of_birth")
            if dob:
                pet.date_of_birth = dob
            weight = request.POST.get("weight_kg")
            if weight:
                try:
                    pet.weight_kg = float(weight)
                except (ValueError, TypeError):
                    pass
            if request.POST.get("photo_clear"):
                if pet.photo:
                    pet.photo.delete(save=False)
                    pet.photo = None
            if "photo" in request.FILES:
                pet.photo = request.FILES["photo"]
            pet.save()
            messages.success(request, _("Podaci ažurirani."))
            return redirect("livestock:pet_detail", pk=pk)
        except (ValueError, TypeError):
            messages.error(request, _("Nešto je pošlo krivo. Pokušajte ponovo ili kontaktirajte podršku."))

    return render(
        request,
        "livestock/pets_edit.html",
        {
            "pet": pet,
            "pet_vrste": [v for v in Livestock.VRSTA_CHOICES if v[0] in PET_VRSTE],
            "spol_choices": [("M", "Mužjak"), ("F", "Ženka"), ("N", "Nepoznato")],
            "status_choices": Livestock.STATUS_CHOICES,
        },
    )


@login_required
def pet_pedigree_pdf(request, pk):
    """Generira rodovnicu u PDF-u."""
    import os
    import subprocess
    import tempfile

    from django.template.loader import render_to_string

    company = get_user_company(request)
    pet = get_object_or_404(Livestock, pk=pk, company=company, vrsta__in=PET_VRSTE)
    records = pet.health_records.filter(tip="cijepljenje").order_by("datum")

    base_url = f"{request.scheme}://{request.get_host()}"
    html = render_to_string(
        "livestock/pedigree_pdf.html",
        {
            "pet": pet,
            "company": company,
            "records": records,
            "today": timezone.now().date(),
            "base_url": base_url,
        },
        request=request,
    )

    try:
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8") as tmp:
            tmp.write(html)
            tmp_path = tmp.name
        pdf_path = tmp_path.replace(".html", ".pdf")
        subprocess.run(
            ["weasyprint", "--base-url", base_url, tmp_path, pdf_path], check=True, capture_output=True, timeout=30
        )
        with open(pdf_path, "rb") as f:
            pdf_data = f.read()
        os.unlink(tmp_path)
        os.unlink(pdf_path)
        filename = f"rodovnica_{pet.name or pet.ear_tag}.pdf".replace(" ", "_")
        resp = HttpResponse(pdf_data, content_type="application/pdf")
        resp["Content-Disposition"] = f'inline; filename="{filename}"'
        return resp
    except (FileNotFoundError, PermissionError, IOError) as e:
        logger.error("pedigree PDF error: %s", e)
        # Fallback — HTML
        return HttpResponse(html, content_type="text/html")


@login_required
@require_POST
def pet_scan_photo(request):
    """Snimi/učitaj foto psa → FenixScan AI → vrati prijedlog polja.
    Rate limit: 20 zahtjeva / sat po korisniku.
    """
    # Rate limiting: 20 req/h per user
    cache_key = f"pet_scan:{request.user.pk}"
    count = cache.get(cache_key, 0)
    if count >= 20:
        return JsonResponse({"error": "Previše zahtjeva. Pokušajte za sat vremena."}, status=429)
    cache.set(cache_key, count + 1, timeout=3600)

    try:
        data = json.loads(request.body)
        b64_image = data.get("image", "")
        if not b64_image:
            return JsonResponse({"error": "Nema slike."}, status=400)

        from core.views_scan import _build_content, _call_anthropic, _parse_json, _validate_images

        images, warn = _validate_images([b64_image])
        if not images:
            return JsonResponse({"error": "Slika prevelika ili neispravna."}, status=400)

        content = _build_content(images, "pas")
        raw = _call_anthropic(content, max_tokens=250)
        fields = _parse_json(raw)

        return JsonResponse(
            {
                "ok": True,
                "fields": fields,
                "confidence": float(fields.get("confidence", 0.5)),
                "warning": warn,
            }
        )
    except (json.JSONDecodeError, ValueError) as e:
        logger.error("pet_scan_photo: %s", e)
        return JsonResponse({"error": str(e)[:150]}, status=500)


@login_required
def pet_qr_code(request, pk):
    """
    GET /livestock/pets/<pk>/qr/
    Generira QR kod koji vodi na memio.pet javni profil ljubimca.
    Vraća PNG ili PDF ovisno o ?format=pdf parametru.
    """
    import io

    import qrcode

    company = get_user_company(request)
    pet = get_object_or_404(Livestock, pk=pk, company=company, vrsta__in=PET_VRSTE)

    identifier = pet.chip_number or pet.ear_tag
    qr_url = f"https://memio.pet/pas/{identifier}"

    fmt = request.GET.get("format", "png")

    qr = qrcode.QRCode(version=2, box_size=10, border=4, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(qr_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="#1a1a2e", back_color="white")
    buf = io.BytesIO()
    img.save(buf)
    buf.seek(0)

    if fmt == "pdf":
        # PDF ogrlica — A6 format, QR + ime + chip
        import os
        import subprocess
        import tempfile

        from django.template.loader import render_to_string

        html = render_to_string(
            "livestock/qr_collar.html",
            {
                "pet": pet,
                "qr_url": qr_url,
                "identifier": identifier,
                "qr_b64": __import__("base64").b64encode(buf.read()).decode(),
            },
            request=request,
        )

        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8") as tmp:
            tmp.write(html)
            tmp_path = tmp.name
        pdf_path = tmp_path.replace(".html", ".pdf")
        try:
            subprocess.run(["weasyprint", tmp_path, pdf_path], check=True, capture_output=True, timeout=20)
            with open(pdf_path, "rb") as f:
                pdf_data = f.read()
            os.unlink(tmp_path)
            os.unlink(pdf_path)
            resp = HttpResponse(pdf_data, content_type="application/pdf")
            resp["Content-Disposition"] = f'inline; filename="qr_{pet.name or identifier}.pdf"'
            return resp
        except (FileNotFoundError, PermissionError, IOError) as e:
            logger.error("QR PDF error: %s", e)
            # Fallback: PNG
            buf.seek(0)

    resp = HttpResponse(buf.read(), content_type="image/png")
    resp["Content-Disposition"] = f'inline; filename="qr_{pet.name or identifier}.png"'
    return resp


@login_required
@require_POST
def pet_adopt(request, pk):
    """
    POST /livestock/pets/<pk>/adopt/
    Mijenja status u 'udomljen', bilježi udomljavača, generira PDF ugovor.
    """
    company = get_user_company(request)
    pet = get_object_or_404(Livestock, pk=pk, company=company, vrsta__in=PET_VRSTE)

    adopter_name = request.POST.get("adopter_name", "").strip()
    adopter_address = request.POST.get("adopter_address", "").strip()
    adopter_oib = request.POST.get("adopter_oib", "").strip()
    adopter_email = request.POST.get("adopter_email", "").strip()

    if not adopter_name:
        messages.error(request, _("Ime udomljavača je obavezno."))
        return redirect("livestock:pet_detail", pk=pk)

    # Zapamti udomljavača u notes
    adoption_note = (
        f"\n--- UDOMLJAVANJE {timezone.now().date()} ---\n"
        f"Udomljavač: {adopter_name}\n"
        f"Adresa: {adopter_address}\n"
        f"OIB: {adopter_oib}\n"
        f"Email: {adopter_email}"
    )
    pet.notes = (pet.notes or "") + adoption_note
    pet.status = "udomljen"
    pet.save(update_fields=["status", "notes"])

    HealthRecord.objects.create(
        animal=pet,
        datum=timezone.now().date(),
        tip="pregled",
        opis=f"Udomljen. Udomljavač: {adopter_name}, {adopter_address}",
        created_by=request.user,
    )

    messages.success(request, f"{pet.name or pet.ear_tag} uspješno udomljen/a. Generiranje ugovora...")

    # Redirect na PDF ugovor
    from urllib.parse import urlencode

    from django.urls import reverse

    params = urlencode(
        {
            "name": adopter_name,
            "address": adopter_address,
            "oib": adopter_oib,
            "email": adopter_email,
        }
    )
    return redirect(f"{reverse('livestock:pet_adoption_contract', kwargs={'pk': pk})}?{params}")


@login_required
def pet_adoption_contract(request, pk):
    """
    GET /livestock/pets/<pk>/contract/
    PDF Ugovor o udomljavanju.
    """
    import os
    import subprocess
    import tempfile

    from django.template.loader import render_to_string

    company = get_user_company(request)
    pet = get_object_or_404(Livestock, pk=pk, company=company, vrsta__in=PET_VRSTE)

    context = {
        "pet": pet,
        "company": company,
        "today": timezone.now().date(),
        "adopter_name": request.GET.get("name", ""),
        "adopter_address": request.GET.get("address", ""),
        "adopter_oib": request.GET.get("oib", ""),
        "adopter_email": request.GET.get("email", ""),
        "base_url": f"{request.scheme}://{request.get_host()}",
    }

    html = render_to_string("livestock/adoption_contract.html", context, request=request)

    try:
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8") as tmp:
            tmp.write(html)
            tmp_path = tmp.name
        pdf_path = tmp_path.replace(".html", ".pdf")
        subprocess.run(
            ["weasyprint", "--base-url", context["base_url"], tmp_path, pdf_path],
            check=True,
            capture_output=True,
            timeout=30,
        )
        with open(pdf_path, "rb") as f:
            pdf_data = f.read()
        os.unlink(tmp_path)
        os.unlink(pdf_path)
        fname = f"ugovor_udomljavanje_{pet.name or pet.ear_tag}_{timezone.now().date()}.pdf".replace(" ", "_")
        resp = HttpResponse(pdf_data, content_type="application/pdf")
        resp["Content-Disposition"] = f'inline; filename="{fname}"'
        return resp
    except (FileNotFoundError, PermissionError, IOError) as e:
        logger.error("adoption contract PDF: %s", e)
        return HttpResponse(html, content_type="text/html")
