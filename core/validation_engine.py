"""
core/validation_engine.py — Global Validation Engine

ARHITEKTURA:
Jedan pre_save signal koji pokriva SVE modele u sustavu.
Inspektira field names (oib, iban, tax_id, mbs) i automatski validira
koristeći centralne validatore iz core/oib_validator.py.

ZAŠTO OVAJ PRISTUP:
- Pokriva 15+ appova bez ijedne migracije
- Nije moguće zaobići (signal na post_init/pre_save razini)
- Country-aware: detektira državu iz company FK-a
- Graceful: logira warning umjesto da blokira save za postojeće loše podatke
- Strict mode: za nove zapise blokira unos nevalidnih podataka

KORIŠTENJE:
Automatski se aktivira pri startu Django-a (core/apps.py ready()).
Ne treba ništa mijenjati u postojećim modelima.

Za forme i API: koristi Django validatore iz core/validators.py koji
pozivaju iste funkcije.
"""

import logging
import re

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import pre_save

logger = logging.getLogger(__name__)

logger = logging.getLogger("validation_engine")

# Field name patterns that trigger validation
OIB_FIELD_PATTERNS = re.compile(
    r"^(oib|tax_id|buyer_oib|client_oib|seller_oib|partner_oib)$",
    re.IGNORECASE,
)
IBAN_FIELD_PATTERNS = re.compile(
    r"^(iban|bank_account|employee_iban|seller_iban|buyer_iban|partner_iban)$",
    re.IGNORECASE,
)
MBS_FIELD_PATTERNS = re.compile(
    r"^(mbs|registration_number)$",
    re.IGNORECASE,
)

# Only validate these concrete field types (never FK, M2M, etc.)
VALIDATABLE_FIELD_TYPES = (models.CharField, models.TextField)

# Apps to skip (framework internals)
SKIP_APPS = frozenset(
    {
        "django",
        "admin",
        "auth",
        "contenttypes",
        "sessions",
        "allauth",
        "socialaccount",
        "sites",
        "django_celery_beat",
        "django_celery_results",
    }
)

# Models to skip (audit trails — may contain historical data we must not block)
SKIP_MODELS = frozenset(
    {
        "SystemAuditLog",
        "BookingSignature",
        "FiscalLog",
        "ImpersonationLog",
        "SynesisImportLog",
        "MigrationRecord",
        "MemioPetWaitlist",
    }
)

_engine_active = False


def activate():
    """Connect the global validation signal. Called from core/apps.py."""
    global _engine_active
    if _engine_active:
        return
    pre_save.connect(_global_validation_guard)
    _engine_active = True
    logger.info("Validation Engine activated — all models monitored")


def _get_country_safe(instance):
    """
    Detect country from instance's company relationship.
    All attribute access is wrapped in try/except to avoid DB lookups
    on unsaved FK references.
    """
    try:
        company = getattr(instance, "company", None)
        if company and hasattr(company, "country"):
            return getattr(company, "country", None) or "HR"
    except (AttributeError, TypeError):
        logger.exception("Company operation failed")

    try:
        session = getattr(instance, "session", None)
        if session:
            terminal = getattr(session, "terminal", None)
            if terminal:
                company = getattr(terminal, "company", None)
                if company:
                    return getattr(company, "country", None) or "HR"
    except (AttributeError, TypeError):
        logger.exception("Unexpected error in: session = getattr(instance, 'session', None)")

    return "HR"


def _global_validation_guard(sender, instance, **kwargs):
    """
    Universal pre_save guard.

    Inspects every model save for OIB/IBAN/MBS CharField fields and validates.
    - New records (no pk): STRICT — raises ValidationError
    - Existing records: WARNING — logs but allows save (backward compat)
    """
    app_label = sender._meta.app_label
    model_name = sender.__name__

    if app_label in SKIP_APPS or model_name in SKIP_MODELS:
        return

    from core.oib_validator import (
        validate_iban,
        validate_mbs,
        validate_oib_hr,
        validate_vat_id,
    )

    is_new = instance.pk is None
    country = None  # Lazy-loaded
    errors = []

    for field in sender._meta.get_fields():
        # Only validate concrete CharField/TextField — never FK, M2M, reverse
        if not isinstance(field, VALIDATABLE_FIELD_TYPES):
            continue

        field_name = field.name

        # Read raw value from instance __dict__ to avoid FK descriptor traps
        value = instance.__dict__.get(field_name)

        if not value or not isinstance(value, str):
            continue

        value = value.strip()
        if not value or value.startswith("DRAFT"):
            continue

        # ── OIB / tax_id ──────────────────────────────────────────────
        if OIB_FIELD_PATTERNS.match(field_name):
            if country is None:
                country = _get_country_safe(instance)

            valid = validate_oib_hr(value) if country == "HR" else validate_vat_id(value, country)
            if not valid:
                label = "OIB" if country == "HR" else f"VAT ID ({country})"
                msg = f"{model_name}.{field_name}: {label} '{value}' ne prolazi provjeru"
                if is_new:
                    errors.append(msg)
                else:
                    logger.warning("EXISTING DATA: %s", msg)

        # ── IBAN ──────────────────────────────────────────────────────
        elif IBAN_FIELD_PATTERNS.match(field_name):
            if not validate_iban(value):
                msg = f"{model_name}.{field_name}: IBAN '{value[:8]}...' ne prolazi MOD97 provjeru"
                if is_new:
                    errors.append(msg)
                else:
                    logger.warning("EXISTING DATA: %s", msg)

        # ── MBS ───────────────────────────────────────────────────────
        elif MBS_FIELD_PATTERNS.match(field_name):
            if not validate_mbs(value):
                msg = f"{model_name}.{field_name}: MBS '{value}' nije 8 znamenki"
                if is_new:
                    errors.append(msg)
                else:
                    logger.warning("EXISTING DATA: %s", msg)

    if errors:
        raise ValidationError(errors)
