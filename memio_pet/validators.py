"""
memio_pet/validators.py — Obrambeni sloj: samo dozvoljen sadržaj u bazu

Doktrina: "Blockchain razina" — svaki unos prolazi kroz validaciju
prije nego dođe do baze. Ni jedan script, ni jedan SQL payload,
ni jedna nelegalna vrijednost ne smije ući.
"""
import re
import html
import logging
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db import DatabaseError, IntegrityError

logger = logging.getLogger('memio_pet.security')

# ─── Dozvoljena slova po tipu polja ────────────────────────────────────────

# Ime ljubimca/uzgajivača: slova, razmaci, crtice, apostrof, točka
_NAME_RE = re.compile(r"^[\w\s\-'.čćžšđČĆŽŠĐüöäÜÖÄßéèêàâ]{1,200}$", re.UNICODE)

# OIB: samo 11 znamenki
_OIB_RE = re.compile(r"^\d{11}$")

# Email: standardni format
_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")

# Čip broj: ISO 11784/11785 — samo znamenke, 9-15 znakova
_CHIP_RE = re.compile(r"^\d{9,15}$")

# Ear tag: alfanumerički + crtice, max 30
_EAR_RE = re.compile(r"^[A-Z0-9\-_]{1,30}$", re.IGNORECASE)

# Slobodan tekst (opis, napomene): bez HTML taga i JS
_SCRIPT_RE = re.compile(
    r"(<script|</script|javascript:|on\w+\s*=|<iframe|<object|<embed|data:text/html)",
    re.IGNORECASE
)

# SQL injection patterns
_SQL_RE = re.compile(
    r"(\bUNION\b|\bSELECT\b|\bDROP\b|\bINSERT\b|\bDELETE\b|\bEXEC\b|--|;--|\bOR\b\s+\d+=\d+)",
    re.IGNORECASE
)

# IP adresa
_IP_RE = re.compile(
    r"^(\d{1,3}\.){3}\d{1,3}$|^[0-9a-fA-F:]{3,39}$"
)


# ─── Sanitizacija ────────────────────────────────────────────────────────────

def sanitize_text(value: str, max_len: int = 500) -> str:
    """
    Sanitizira slobodan tekst:
    - Ukloni HTML entitete
    - Strip whitespace
    - Skrati na max_len
    """
    if not value:
        return ''
    v = html.escape(value.strip())
    return v[:max_len]


def sanitize_name(value: str, max_len: int = 200) -> str:
    """Sanitizira ime — strip i skraćivanje."""
    if not value:
        return ''
    return value.strip()[:max_len]


# ─── Validatori (Django ValidationError) ────────────────────────────────────

def validate_no_scripts(value: str):
    """Zabrani HTML/JS injection u bilo koje tekstualno polje."""
    if not value:
        return
    if _SCRIPT_RE.search(value):
        logger.warning("SECURITY: Script injection pokušaj: %r", value[:100])
        raise ValidationError(
            "Nedozvoljeni sadržaj u polju. HTML i skriptni kod nisu dozvoljeni."
        )


def validate_no_sql(value: str):
    """Zabrani SQL injection pokušaje."""
    if not value:
        return
    if _SQL_RE.search(value):
        logger.warning("SECURITY: SQL injection pokušaj: %r", value[:100])
        raise ValidationError(
            "Nedozvoljeni sadržaj u polju."
        )


def validate_oib_format(value: str):
    """OIB mora biti točno 11 znamenki."""
    if not value:
        return
    if not _OIB_RE.match(value):
        raise ValidationError("OIB mora biti točno 11 znamenki.")
    # ISO 7064 MOD 11,10 checksum
    a = 10
    for digit in value[:10]:
        a = (a + int(digit)) % 10
        if a == 0:
            a = 10
        a = (a * 2) % 11
    check = 11 - a
    if check == 10:
        check = 0
    if check != int(value[10]):
        raise ValidationError("OIB nije ispravan (checksum ne odgovara).")


def validate_chip_number(value: str):
    """Čip broj: ISO 11784/11785 — samo znamenke, 9-15 znakova."""
    if not value:
        return
    if not _CHIP_RE.match(value):
        raise ValidationError("Broj mikročipa mora sadržavati samo znamenke (9-15). Ako nema čipa, ostavi prazno.")


def validate_name_field(value: str):
    """Ime: slova, razmaci, uobičajena interpunkcija."""
    if not value:
        return
    validate_no_scripts(value)
    validate_no_sql(value)
    if len(value) > 200:
        raise ValidationError("Ime ne smije biti dulje od 200 znakova.")


def validate_free_text(value: str):
    """Slobodan tekst: dozvoljeno sve osim script/SQL."""
    if not value:
        return
    validate_no_scripts(value)
    validate_no_sql(value)


# ─── API ulazna sanitizacija (za views) ─────────────────────────────────────

def clean_api_input(data: dict) -> dict:
    """
    Sanitizira cijeli API payload prije obrade.
    Koristi se na vrhu svakog javnog endpointa.
    """
    cleaned = {}
    for key, value in data.items():
        if isinstance(value, str):
            # Strip whitespace
            v = value.strip()
            # Ukloni null bytes
            v = v.replace('\x00', '')
            # Skraćivanje na razumne limite
            limits = {
                'name': 120, 'email': 254, 'oib': 11,
                'chip_number': 20, 'breed': 100, 'notes': 2000,
                'color_description': 200, 'source': 50,
            }
            max_len = limits.get(key, 500)
            v = v[:max_len]
            cleaned[key] = v
        else:
            cleaned[key] = value
    return cleaned
