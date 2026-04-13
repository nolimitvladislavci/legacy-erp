"""
Grossmarkt shared validators - OIB, phone, price, quantity.
"""
import re

from django.core.exceptions import ValidationError


def validate_oib(value):
    """Validate Croatian OIB (11-digit tax ID)."""
    if not value:
        return
    value = str(value).strip()
    if not re.match(r'^\d{11}$', value):
        raise ValidationError('OIB mora imati točno 11 znamenki.')
    # ISO 7064 MOD 11,10 check
    remainder = 10
    for digit in value[:10]:
        remainder = (remainder + int(digit)) % 10
        if remainder == 0:
            remainder = 10
        remainder = (remainder * 2) % 11
    check = 11 - remainder
    if check == 10:
        check = 0
    if check != int(value[10]):
        raise ValidationError('OIB nije valjan (kontrolna znamenka).')


def validate_phone_hr(value):
    """Validate Croatian/international phone number."""
    if not value:
        return
    cleaned = re.sub(r'[\s\-\(\)]', '', value)
    if not re.match(r'^(\+?\d{8,15})$', cleaned):
        raise ValidationError('Neispravan format telefonskog broja.')


def validate_positive_price(value):
    """Ensure price is positive."""
    if value is not None and value < 0:
        raise ValidationError('Cijena ne može biti negativna.')


def validate_positive_quantity(value):
    """Ensure quantity is positive."""
    if value is not None and value <= 0:
        raise ValidationError('Količina mora biti veća od 0.')


def validate_document_number(value):
    """Validate document number format: PREFIX-YYYY-NNNN."""
    if not value:
        return
    if not re.match(r'^[A-Z]{2,4}-\d{4}-\d{4}$', value):
        raise ValidationError('Broj dokumenta mora biti u formatu: PREFIX-YYYY-NNNN (npr. OTP-2026-0001)')


def sanitize_text(value):
    """Remove potentially dangerous characters from text input."""
    if not value:
        return value
    # Remove script tags and event handlers
    value = re.sub(r'<script[^>]*>.*?</script>', '', value, flags=re.IGNORECASE | re.DOTALL)
    value = re.sub(r'on\w+\s*=', '', value, flags=re.IGNORECASE)
    return value.strip()


class StrongPasswordValidator:
    """Zahtijeva: veliko slovo, broj, specijalni znak."""

    def validate(self, password, user=None):
        errors = []
        if not re.search(r'[A-Z]', password):
            errors.append('Lozinka mora sadrzavati barem jedno veliko slovo.')
        if not re.search(r'\d', password):
            errors.append('Lozinka mora sadrzavati barem jedan broj.')
        if not re.search(r'[!@#$%^&*(),.?\":{}|<>_\-+=/\\]', password):
            errors.append('Lozinka mora sadrzavati barem jedan poseban znak (!@#$%...).')
        if errors:
            from django.core.exceptions import ValidationError
            raise ValidationError(errors)

    def get_help_text(self):
        return 'Lozinka mora imati barem 10 znakova, jedno veliko slovo, jedan broj i jedan poseban znak.'


# ═══════════════════════════════════════════════════════════════════════════
# EU-wide form validators — use as field validators=[...]
# Single source: delegates to core.oib_validator
# ═══════════════════════════════════════════════════════════════════════════

def validate_iban(value):
    """ISO 13616 IBAN validator for Django forms."""
    if not value:
        return
    from core.oib_validator import validate_iban as _check
    value = str(value).strip().replace(' ', '').upper()
    if not _check(value):
        raise ValidationError(
            'IBAN nije valjan (MOD97 provjera neuspješna).',
            code='invalid_iban',
        )


def validate_tax_id(value, country='HR'):
    """Multi-country tax ID validator for Django forms."""
    if not value:
        return
    from core.oib_validator import validate_vat_id
    value = str(value).strip()
    if not validate_vat_id(value, country):
        raise ValidationError(
            f'Porezni ID nije valjan za državu {country}.',
            code='invalid_tax_id',
        )


def validate_mbs(value):
    """MBS (matični broj subjekta) validator — 8 digits."""
    if not value:
        return
    value = str(value).strip()
    if not (len(value) == 8 and value.isdigit()):
        raise ValidationError(
            'MBS mora imati točno 8 znamenki.',
            code='invalid_mbs',
        )
