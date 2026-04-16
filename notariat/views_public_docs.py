"""
notariat/views_public_docs.py
Javni dokumenti s evalidator digitalnim pečatom.
L1, G1, T1 — generiranje PDF-a i HTML pregled.
"""

import hashlib

from django.http import HttpResponse
from django.shortcuts import render
from django.template.loader import render_to_string

# ═══════════════════════════════════════════════════════════════
#  Dokument registry — svi javni dokumenti na jednom mjestu
# ═══════════════════════════════════════════════════════════════

PUBLIC_DOCS = {
    "L1": {
        "template": "notariat/pdf/L1_licencni_ugovor.html",
        "title": "Licencni ugovor — Konjik d.o.o. ↔ No-limit udruga",
        "version": "1.0.0",
        "date": "16.04.2026.",
        "issuer": "No-limit udruga / Konjik d.o.o.",
        "filename": "L1_licencni_ugovor_v{version}.pdf",
    },
    "G1": {
        "template": "notariat/pdf/G1_gdpr_kids.html",
        "title": "GDPR-Kids — Politika zaštite djece",
        "version": "1.0.0",
        "date": "16.04.2026.",
        "issuer": "No-limit udruga / Konjik d.o.o.",
        "filename": "G1_gdpr_kids_v{version}.pdf",
    },
    "T1": {
        "template": "notariat/pdf/T1_tos_evalidator.html",
        "title": "Uvjeti korištenja — evalidator.eu",
        "version": "1.0.0",
        "date": "16.04.2026.",
        "issuer": "No-limit udruga / Konjik d.o.o.",
        "filename": "T1_tos_evalidator_v{version}.pdf",
    },
}


def _build_doc_context(doc_id):
    """Kreiraj kontekst za dokument s hashom i metapodacima."""
    doc = PUBLIC_DOCS[doc_id]
    ctx = {
        "doc_id": doc_id,
        "doc_version": doc["version"],
        "doc_date": doc["date"],
        "doc_issuer": doc["issuer"],
        "doc_url": f"https://evalidator.eu/verify/{doc_id}/",
        "doc_hash": "",  # placeholder — popuni se nakon renderiranja
        "doc_hash_short": "",
    }
    return ctx


def _generate_public_pdf(doc_id):
    """Generiraj PDF za javni dokument s SHA-256 pečatom."""
    import weasyprint

    doc = PUBLIC_DOCS[doc_id]
    ctx = _build_doc_context(doc_id)

    # Prvi pass — generiraj HTML bez hasha
    html_content = render_to_string(doc["template"], ctx)

    # Izračunaj hash HTML sadržaja (bez samog hasha — hash sadržaja dokumenta)
    content_hash = hashlib.sha256(html_content.encode("utf-8")).hexdigest()
    ctx["doc_hash"] = content_hash
    ctx["doc_hash_short"] = content_hash[:16]

    # Drugi pass — generiraj HTML s hashom
    html_final = render_to_string(doc["template"], ctx)

    # Generiraj PDF
    pdf_bytes = weasyprint.HTML(string=html_final).write_pdf()

    # Hash PDF-a (za verifikaciju integriteta datoteke)
    pdf_hash = hashlib.sha256(pdf_bytes).hexdigest()

    filename = doc["filename"].format(version=doc["version"])
    return pdf_bytes, pdf_hash, filename, ctx


# ═══════════════════════════════════════════════════════════════
#  Views — PDF download
# ═══════════════════════════════════════════════════════════════


def public_doc_pdf(request, doc_id):
    """Generiraj i download PDF za javni dokument."""
    doc_id = doc_id.upper()
    if doc_id not in PUBLIC_DOCS:
        return HttpResponse(f"Dokument {doc_id} ne postoji.", status=404)

    pdf_bytes, pdf_hash, filename, ctx = _generate_public_pdf(doc_id)

    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["X-Document-Hash"] = pdf_hash
    response["X-Document-ID"] = doc_id
    response["X-Document-Version"] = ctx["doc_version"]
    return response


def public_doc_view(request, doc_id):
    """Prikaži dokument kao HTML stranicu (za online čitanje)."""
    doc_id = doc_id.upper()
    if doc_id not in PUBLIC_DOCS:
        return HttpResponse(f"Dokument {doc_id} ne postoji.", status=404)

    doc = PUBLIC_DOCS[doc_id]
    ctx = _build_doc_context(doc_id)

    # Generiraj hash za prikaz
    html_content = render_to_string(doc["template"], ctx)
    content_hash = hashlib.sha256(html_content.encode("utf-8")).hexdigest()
    ctx["doc_hash"] = content_hash
    ctx["doc_hash_short"] = content_hash[:16]

    return render(request, doc["template"], ctx)


def public_doc_verify(request, doc_id):
    """API: Verificiraj integritet dokumenta — vraća hash i metapodatke."""
    from django.http import JsonResponse

    doc_id = doc_id.upper()
    if doc_id not in PUBLIC_DOCS:
        return JsonResponse({"error": f"Dokument {doc_id} ne postoji."}, status=404)

    doc = PUBLIC_DOCS[doc_id]
    ctx = _build_doc_context(doc_id)
    html_content = render_to_string(doc["template"], ctx)
    content_hash = hashlib.sha256(html_content.encode("utf-8")).hexdigest()

    return JsonResponse(
        {
            "document_id": doc_id,
            "title": doc["title"],
            "version": doc["version"],
            "date": doc["date"],
            "issuer": doc["issuer"],
            "content_hash_sha256": content_hash,
            "signature_type": "AES (Advanced Electronic Signature)",
            "eidas_reference": "EU Regulation 910/2014",
            "verification_url": f"https://evalidator.eu/verify/{doc_id}/",
            "pdf_download_url": f"https://evalidator.eu/docs/{doc_id}/pdf/",
            "note": "Za QES (Qualified Electronic Signature) potrebna je ovjera kod javnog bilježnika.",
        }
    )


def public_docs_index(request):
    """Pregled svih javnih dokumenata."""
    docs = []
    for doc_id, doc in PUBLIC_DOCS.items():
        ctx = _build_doc_context(doc_id)
        html_content = render_to_string(doc["template"], ctx)
        content_hash = hashlib.sha256(html_content.encode("utf-8")).hexdigest()
        docs.append(
            {
                "id": doc_id,
                "title": doc["title"],
                "version": doc["version"],
                "date": doc["date"],
                "hash_short": content_hash[:16],
                "hash_full": content_hash,
            }
        )
    return render(request, "notariat/public_docs_index.html", {"docs": docs})
