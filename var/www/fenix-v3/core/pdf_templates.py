"""
Fenix V3 — Globalni PDF Template Resolver
Tri formata ispisa × dva jezika = 6 template-a

  viskovic  — gold/premium (HR: #0f172a, DE: #1e3a5f)
  modern    — plavo/bijeli dark-navy top bar
  datev     — crno-bijeli, DATEV/GoBD kompatibilan

Upotreba u generatoru:
    from core.pdf_templates import get_invoice_template
"""

PDF_TEMPLATE_CHOICES = [
    ("viskovic", "Visković (Gold / Premium)"),
    ("modern", "Modern (Plavo / Bijeli)"),
    ("datev", "DATEV (Minimalistički / Steuerberater)"),
]

_INVOICE_TEMPLATES = {
    ("hr", "viskovic"): "invoicing/pdf/invoice_hr_viskovic.html",
    ("hr", "modern"): "invoicing/pdf/invoice_hr_modern.html",
    ("hr", "datev"): "invoicing/pdf/invoice_hr_datev.html",
    ("de", "viskovic"): "invoicing/pdf/invoice_de_viskovic.html",
    ("de", "modern"): "invoicing/pdf/invoice_de_modern.html",
    ("de", "datev"): "invoicing/pdf/invoice_de_datev.html",
}


def _detect_lang(company=None) -> str:
    """Odredi jezik na osnovu države firme (HR → hr, ostalo → de)."""
    if company is None:
        return "hr"
    country = (getattr(company, "country", None) or "HR").upper()
    return "de" if country in ("DE", "AT", "CH") else "hr"


def get_invoice_template(company=None, lang: str = None) -> str:
    style = getattr(company, "pdf_template", "viskovic") or "viskovic"
    if lang is None:
        lang = _detect_lang(company)
    key = (lang, style)
    return _INVOICE_TEMPLATES.get(key, _INVOICE_TEMPLATES[("hr", "viskovic")])


def get_pdf_base(company=None) -> str:
    # Legacy — base templates nisu više potrebni (self-contained templates)
    return ""


def get_all_templates() -> list:
    return [
        {
            "id": "viskovic",
            "name": "Visković (Gold/Premium)",
            "preview": "Zlatno zaglavlje, tamni akcenti, premium osjećaj",
        },
        {
            "id": "modern",
            "name": "Modern (Plavo/Bijeli)",
            "preview": "Plavo gradijent zaglavlje, zaobljeni kutovi, svjež stil",
        },
        {
            "id": "datev",
            "name": "DATEV (Minimalistički)",
            "preview": "Crno-bijeli, tabularni format, § 147 AO / GoBD-konforman",
        },
    ]
