"""
FENIX ACCESS LAYER — RouteRegistry
Faza 1: Centralni registar pristupnih razina za sve URL rute.

KLJUČNA IDEJA: koristiti resolver_match.view_name umjesto request.path
View name je language-agnostic — /hr/2fa/setup/ i /en/2fa/setup/
obje resolveaju u view_name='setup_2fa'. Jedan entry umjesto N.
"""

import logging
from enum import Enum, auto

logger = logging.getLogger("fal.route_registry")


class AccessLevel(Enum):
    PUBLIC = auto()  # Bez logina, bez company
    AUTHENTICATED = auto()  # Treba login, ne treba company
    COMPANY = auto()  # Treba login + aktivan company membership
    ADMIN = auto()  # company_admin ili superadmin
    SUPERADMIN = auto()  # Samo superuser


# ─────────────────────────────────────────────────────────────
# REGISTAR RUTA
# Format: 'view_name': AccessLevel  (bez i18n prefiksa)
# Default za neregistrirane rute: COMPANY (konzervativni default)
# ─────────────────────────────────────────────────────────────
ROUTE_REGISTRY: dict = {
    # ── POTPUNO JAVNE ─────────────────────────────────────────
    "home": AccessLevel.PUBLIC,
    "home_root": AccessLevel.PUBLIC,
    "login": AccessLevel.PUBLIC,
    "login_root": AccessLevel.PUBLIC,
    "login_fallback": AccessLevel.PUBLIC,
    "logout": AccessLevel.PUBLIC,
    "health_check": AccessLevel.PUBLIC,
    "api_validate": AccessLevel.PUBLIC,
    "brochure_croxmlverify": AccessLevel.PUBLIC,
    "no_limit_web": AccessLevel.PUBLIC,
    "brosura_posrednik": AccessLevel.PUBLIC,
    "panic_button": AccessLevel.AUTHENTICATED,
    "panic_revoke": AccessLevel.AUTHENTICATED,
    "inspector_dashboard": AccessLevel.PUBLIC,
    "brochure_golubar": AccessLevel.PUBLIC,
    "brochure_golubar_i18n": AccessLevel.PUBLIC,
    "pricing": AccessLevel.PUBLIC,
    "about": AccessLevel.PUBLIC,
    "impressum": AccessLevel.PUBLIC,
    "datenschutz": AccessLevel.PUBLIC,
    "privatnost": AccessLevel.PUBLIC,
    "tippgeber_vertrag": AccessLevel.PUBLIC,
    "tippgeber_ausweis": AccessLevel.PUBLIC,
    "posrednicki_ugovor": AccessLevel.PUBLIC,
    "opci_uvjeti": AccessLevel.PUBLIC,
    "dpa": AccessLevel.PUBLIC,
    "digitalni_posrednik": AccessLevel.PUBLIC,
    "partner_signup": AccessLevel.PUBLIC,
    "partner_signup_api": AccessLevel.PUBLIC,
    "memio_waitlist": AccessLevel.PUBLIC,
    "memio_pet_profile": AccessLevel.PUBLIC,
    # Memio.pet HTML views (namespaced — app_name='memio_pet')
    "memio_pet:pet_profile": AccessLevel.PUBLIC,
    "memio_pet:pet_qr": AccessLevel.PUBLIC,
    "memio_pet:breeder_profile": AccessLevel.PUBLIC,
    "memio_pet:njuskalo_badge": AccessLevel.PUBLIC,
    "memio_pet:barf_listings": AccessLevel.PUBLIC,
    "memio_pet:barf_create": AccessLevel.AUTHENTICATED,
    "memio_pet:pet_hotel_booking": AccessLevel.PUBLIC,
    "memio_pet:training_list": AccessLevel.PUBLIC,
    "memio_stats": AccessLevel.PUBLIC,
    "robot_pekara": AccessLevel.PUBLIC,
    "de_landing": AccessLevel.PUBLIC,
    "de_pakete": AccessLevel.PUBLIC,
    "de_anleitung": AccessLevel.PUBLIC,
    "de_ohne_papier": AccessLevel.PUBLIC,
    "newsletter": AccessLevel.PUBLIC,
    "newsletter_de": AccessLevel.PUBLIC,
    "promo_hr": AccessLevel.PUBLIC,
    "promo_de": AccessLevel.PUBLIC,
    "promo_opg": AccessLevel.PUBLIC,
    "sw_js": AccessLevel.PUBLIC,
    "manifest_json": AccessLevel.PUBLIC,
    "offline_html": AccessLevel.PUBLIC,
    "receipt_public_short": AccessLevel.PUBLIC,
    "receipt_public_noslash": AccessLevel.PUBLIC,
    "public_sos": AccessLevel.PUBLIC,
    "intervention_tracking": AccessLevel.PUBLIC,
    "library_public_home": AccessLevel.PUBLIC,
    "library_public_search": AccessLevel.PUBLIC,
    "library_public_book": AccessLevel.PUBLIC,
    "library_public_reserve": AccessLevel.PUBLIC,
    "library_public_portal": AccessLevel.PUBLIC,
    "validator": AccessLevel.PUBLIC,
    "whatsapp_webhook": AccessLevel.PUBLIC,
    "inbound_webhook_direct": AccessLevel.PUBLIC,
    "fenix_scan": AccessLevel.PUBLIC,
    "device_token_auto_login": AccessLevel.PUBLIC,
    "device_token_login_api": AccessLevel.PUBLIC,
    "tc_consent": AccessLevel.PUBLIC,
    "tc_accept_view": AccessLevel.PUBLIC,
    "tc_accept": AccessLevel.PUBLIC,
    "password_reset": AccessLevel.PUBLIC,
    "password_reset_done": AccessLevel.PUBLIC,
    "password_reset_confirm": AccessLevel.PUBLIC,
    "password_reset_complete": AccessLevel.PUBLIC,
    "verify_email": AccessLevel.PUBLIC,
    "resend_verification": AccessLevel.PUBLIC,
    "public_booking_by_slug": AccessLevel.PUBLIC,
    "scan_mobile": AccessLevel.PUBLIC,
    "scan_upload": AccessLevel.PUBLIC,
    "ai_agent_gateway": AccessLevel.PUBLIC,
    "whatsapp_health": AccessLevel.PUBLIC,
    "synesis_script_public": AccessLevel.PUBLIC,
    "synesis_export_api": AccessLevel.PUBLIC,
    "synesis_export_confirm": AccessLevel.PUBLIC,
    "grosmarkt_anfrage_direct": AccessLevel.PUBLIC,
    "grosmarkt_partners": AccessLevel.PUBLIC,
    "mcp_sse": AccessLevel.PUBLIC,
    "bau_page_root": AccessLevel.PUBLIC,
    # Brochure / landing stranice
    "frisko": AccessLevel.PUBLIC,
    "rizo_paket": AccessLevel.PUBLIC,
    "seki_paket": AccessLevel.PUBLIC,
    "optika_konjik": AccessLevel.PUBLIC,
    "korpas": AccessLevel.PUBLIC,
    "financijski_plan": AccessLevel.PUBLIC,
    "trzisna_analiza": AccessLevel.PUBLIC,
    # ── TREBA LOGIN (ne nužno company) ────────────────────────
    "setup_2fa": AccessLevel.AUTHENTICATED,
    "verify_2fa": AccessLevel.AUTHENTICATED,
    "gdpr_export": AccessLevel.AUTHENTICATED,
    "gdpr_delete": AccessLevel.AUTHENTICATED,
    "gdpr_dashboard": AccessLevel.AUTHENTICATED,
    "api_gdpr_export": AccessLevel.AUTHENTICATED,
    "api_gdpr_erase": AccessLevel.AUTHENTICATED,
    "device_token_manage": AccessLevel.AUTHENTICATED,
    "device_token_detail": AccessLevel.AUTHENTICATED,
    "device_token_qr_image": AccessLevel.AUTHENTICATED,
    "onboarding_wizard": AccessLevel.AUTHENTICATED,
    "onboarding_update_profile": AccessLevel.AUTHENTICATED,
    "onboarding_add_partner": AccessLevel.AUTHENTICATED,
    "onboarding_add_item": AccessLevel.AUTHENTICATED,
    "onboarding_activate_pos": AccessLevel.AUTHENTICATED,
    "onboarding_skip_step": AccessLevel.AUTHENTICATED,
    "onboarding_complete": AccessLevel.AUTHENTICATED,
    # ── SUPERADMIN ONLY ────────────────────────────────────────
    "superadmin_dashboard": AccessLevel.SUPERADMIN,
    "control_tower": AccessLevel.SUPERADMIN,
    "control_tower_api": AccessLevel.SUPERADMIN,
    "cross_company_dashboard": AccessLevel.SUPERADMIN,
    "ivan_cockpit": AccessLevel.SUPERADMIN,
    "superadmin_companies": AccessLevel.SUPERADMIN,
    "superadmin_users": AccessLevel.SUPERADMIN,
    "superadmin_edit_user": AccessLevel.SUPERADMIN,
    "start_impersonation": AccessLevel.SUPERADMIN,
    "stop_impersonation": AccessLevel.SUPERADMIN,
    "superadmin_create_promo": AccessLevel.SUPERADMIN,
    "update_company_modules": AccessLevel.SUPERADMIN,
    "umbrella_dashboard": AccessLevel.SUPERADMIN,
    "tc_consent_status": AccessLevel.SUPERADMIN,
    "tc_consent_remind": AccessLevel.SUPERADMIN,
    "borg_error_queue": AccessLevel.SUPERADMIN,
    # Claim Your Business
    "claim_company": AccessLevel.PUBLIC,
    "submit_claim": AccessLevel.PUBLIC,
    "activate_invite": AccessLevel.PUBLIC,
    "approve_claim": AccessLevel.AUTHENTICATED,
    "pending_claims": AccessLevel.AUTHENTICATED,
    "send_company_invite": AccessLevel.AUTHENTICATED,
    # Mandate (eracun)
    "eracun:mandate_list": AccessLevel.AUTHENTICATED,
    "eracun:mandate_create": AccessLevel.AUTHENTICATED,
    "eracun:mandate_activate": AccessLevel.AUTHENTICATED,
    "eracun:mandate_revoke": AccessLevel.AUTHENTICATED,
    "eracun:mandate_bulk_umbrella": AccessLevel.AUTHENTICATED,
    # Public website & booking
    "company_site": AccessLevel.PUBLIC,
    "company_site_contact": AccessLevel.PUBLIC,
    "company_site_public": AccessLevel.PUBLIC,
    "company_site_contact_public": AccessLevel.PUBLIC,
    # ── Proizvodnja (MRP) ──────────────────────────────────────
    "production:dashboard": 1,
    "production:bom_list": 1,
    "production:bom_detail": 1,
    "production:bom_create": 2,
    "production:order_list": 1,
    "production:order_detail": 1,
    "production:order_create": 2,
    "production:order_start": 3,
    "production:order_produce": 2,
    "production:order_complete": 3,
    "production:order_cancel": 3,
    "production:step_update": 2,
    "production:qc_create": 2,
    "production:workstation_list": 1,
    "production:workstation_create": 2,
    "production:order_pdf": 1,
    "production:api_availability": 1,
}


class RouteRegistry:
    """
    Single source of truth za pristupne razine ruta.
    Koristi view_name umjesto path string matchinga.
    """

    DEFAULT_LEVEL = AccessLevel.COMPANY  # konzervativni default

    # Ovi path prefiksi uvijek prolaze bez provjere (static files, admin)
    BYPASS_PREFIXES = (
        "/static/",
        "/media/",
        "/admin/",
        "/__debug__/",
        "/favicon",
        "/robots.txt",
        "/api/whatsapp/",
        "/_dev/",
        "/waha/",
        "/mcp/",
        "/messages/",
    )

    @classmethod
    def get_access_level(cls, request) -> AccessLevel:
        """Odredi pristupnu razinu za trenutni request."""
        path = request.path

        # Bypass prefiksi — propusti bez ikakve provjere
        for prefix in cls.BYPASS_PREFIXES:
            if path.startswith(prefix):
                return AccessLevel.PUBLIC

        # resolver_match — može biti None kod 404
        resolver_match = getattr(request, "resolver_match", None)
        if resolver_match is None:
            return AccessLevel.PUBLIC  # Django će vratiti 404

        view_name = resolver_match.url_name or ""
        namespace = resolver_match.namespace or ""

        # Provjeri s namespace-om (npr. 'udruge:golubar_dashboard')
        full_name = f"{namespace}:{view_name}" if namespace else view_name

        level = ROUTE_REGISTRY.get(full_name) or ROUTE_REGISTRY.get(view_name)

        if level is None:
            logger.debug(f"RouteRegistry MISS: '{full_name}' → default {cls.DEFAULT_LEVEL.name}")
            return cls.DEFAULT_LEVEL

        return level

    @classmethod
    def is_public(cls, request) -> bool:
        return cls.get_access_level(request) == AccessLevel.PUBLIC

    @classmethod
    def requires_auth_only(cls, request) -> bool:
        return cls.get_access_level(request) == AccessLevel.AUTHENTICATED

    @classmethod
    def requires_company(cls, request) -> bool:
        level = cls.get_access_level(request)
        return level in (AccessLevel.COMPANY, AccessLevel.ADMIN, AccessLevel.SUPERADMIN)
