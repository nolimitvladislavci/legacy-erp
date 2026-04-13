"""
Country Registry — Strategy Pattern za multi-country ERP.

Centralno mjesto za registriranje poreznih, fiskalnih i reporting providera po drzavi.
Trenutno: HR + DE. Spreman za: AT, SI, RS, BA, IT, PL...

Usage:
    from core.country_registry import get_fiscal_provider, get_invoice_format, SUPPORTED_COUNTRIES

    provider = get_fiscal_provider('HR')  # -> 'fina_cis'
    format = get_invoice_format('DE')     # -> 'xrechnung'
"""

# ══════════════════════════════════════════════════════════════
# COUNTRY CONFIGURATIONS
# ══════════════════════════════════════════════════════════════

COUNTRY_CONFIG = {
    "HR": {
        "name": "Hrvatska",
        "fiscal_provider": "fina_cis",  # fiskalizacija/fisk.py
        "fiscal_module": "fiskalizacija.fisk",
        "invoice_format": "ubl",  # eracun/services/ubl_generator.py
        "invoice_standard": "PEPPOL BIS 3.0",
        "ngo_report": "pr_ras_npf",  # udruge/fina_reports.py
        "ngo_chart": "nonprofit_hr",  # konto/nonprofit_setup.py
        "tax_rates": [25, 13, 5, 0],
        "currency": "EUR",
        "tip_annual_limit": 3360,  # EUR
        "b2b_invoice_required": True,  # od 2026
        "kleinbetragsrechnung_limit": None,  # nema limita u HR
        "legal_text": "Elektronicki dokument — cl. 9. st. 2. ZOR-a",
        "status": "PRODUCTION",
    },
    "DE": {
        "name": "Deutschland",
        "fiscal_provider": "fiskaly_tse",  # pos/tse_adapter.py
        "fiscal_module": "pos.tse_adapter",
        "invoice_format": "xrechnung",  # eracun/services/xrechnung.py
        "invoice_standard": "XRechnung 3.0 (CII)",
        "zugferd": True,  # eracun/services/zugferd.py
        "ngo_report": None,  # TODO: DATEV SKR42
        "ngo_chart": None,  # TODO
        "tax_rates": [19, 7, 0],
        "currency": "EUR",
        "tip_annual_limit": None,  # nema limita u DE za Arbeitnehmer
        "b2b_invoice_required": True,  # od 2025 (primanje), 2027 (slanje)
        "kleinbetragsrechnung_limit": 250,  # EUR
        "dsfinvk": True,
        "legal_text": "Elektronisches Dokument — gueltig gem. Paragraph 147 AO, GoBD-konform",
        "status": "PRODUCTION",
    },
    "AT": {
        "name": "Oesterreich",
        "fiscal_provider": "rksv",  # TODO: RKSV (Registrierkassensicherheitsverordnung)
        "invoice_format": "ubl",  # ebInterface ili PEPPOL
        "tax_rates": [20, 13, 10, 0],
        "currency": "EUR",
        "kleinbetragsrechnung_limit": 400,  # EUR
        "legal_text": "Elektronischer Beleg — RKSV-konform",
        "status": "PLANNED",
    },
    "SI": {
        "name": "Slovenija",
        "fiscal_provider": "furs",  # TODO: FURS API (slicno FINA)
        "invoice_format": "ubl",
        "tax_rates": [22, 9.5, 5, 0],
        "currency": "EUR",
        "status": "PLANNED",
    },
    "RS": {
        "name": "Srbija",
        "fiscal_provider": "sef",  # TODO: SEF (UBL 2.1)
        "invoice_format": "ubl",
        "tax_rates": [20, 10, 0],
        "currency": "RSD",
        "status": "PLANNED",
    },
    "BA": {
        "name": "Bosna i Hercegovina",
        "fiscal_provider": None,  # Fragmentirano (FBiH vs RS)
        "invoice_format": None,
        "tax_rates": [17, 0],
        "currency": "BAM",
        "status": "RESEARCH",
    },
    "IT": {
        "name": "Italia",
        "fiscal_provider": "rt",  # Registratore Telematico (hardware)
        "invoice_format": "fatturapa",  # FatturaPA XML
        "tax_rates": [22, 10, 5, 4, 0],
        "currency": "EUR",
        "status": "RESEARCH",
    },
}

SUPPORTED_COUNTRIES = [k for k, v in COUNTRY_CONFIG.items() if v.get("status") == "PRODUCTION"]
PLANNED_COUNTRIES = [k for k, v in COUNTRY_CONFIG.items() if v.get("status") == "PLANNED"]


def get_config(country_code):
    """Get full config for a country."""
    return COUNTRY_CONFIG.get(country_code, COUNTRY_CONFIG.get("HR"))


def get_fiscal_provider(country_code):
    """Get fiscal provider name for a country."""
    cfg = get_config(country_code)
    return cfg.get("fiscal_provider")


def get_invoice_format(country_code):
    """Get e-invoice format for a country."""
    cfg = get_config(country_code)
    return cfg.get("invoice_format")


def get_tax_rates(country_code):
    """Get available tax rates for a country."""
    cfg = get_config(country_code)
    return cfg.get("tax_rates", [25, 0])


def get_legal_text(country_code):
    """Get legal validity text for documents."""
    cfg = get_config(country_code)
    return cfg.get("legal_text", "")


def is_b2b_invoice_required(country_code):
    """Check if B2B e-invoice is mandatory."""
    cfg = get_config(country_code)
    return cfg.get("b2b_invoice_required", False)


def get_kleinbetragsrechnung_limit(country_code):
    """Get small invoice limit (buyer data not required below this)."""
    cfg = get_config(country_code)
    return cfg.get("kleinbetragsrechnung_limit")
