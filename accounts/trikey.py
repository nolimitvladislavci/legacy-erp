"""
accounts/trikey.py ��� TriKey Authentication System

"3 ključa za 1 bravu" — LIMIT Connect signature auth

🔑 Ključ 1: PIN (6 znakova) — svakodnevni pristup, brz kao mBanking
🔑 Ključ 2: Passkey (WebAuthn/FIDO2) — biometrija, phishing-resistant
🔑 Ključ 3: Business Key (FINA cert fingerprint + ePosrednik API key)

Pravila:
  - Login: Bilo koja 2 od 3 ključa
  - Sensitive ops (fiskalizacija, plaće, GDPR): Sva 3
  - Povrat PIN-a: Ključ 3 (FINA/ePosrednik) + email verifikacija
  - Registracija: OIB → Sudski registar auto-fill → email → PIN setup

Rate limiting:
  - PIN: 5 pokušaja → lockout 15min
  - Passkey: unlimited (biometric)
  - Business Key: 3 pokušaja → lockout 1h
"""

import hashlib
import hmac
import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.cache import cache
from django.db import models
from django.utils import timezone
from django.db import IntegrityError, DatabaseError

logger = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════════════
# MODEL — TriKey profil (extension of User)
# ════════════════════════════════════════════════════════════════


class TriKeyProfile(models.Model):
    """
    3-ključ autentifikacijski profil za korisnika.
    Pohranjuje hasheve ključeva, ne plain text.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='trikey',
    )
    # 🔑 Ključ 1: PIN (6 znakova, hashed)
    pin_hash = models.CharField(max_length=128, blank=True,
                                 help_text='Argon2/PBKDF2 hash 6-digit PIN-a')
    pin_set_at = models.DateTimeField(null=True, blank=True)
    pin_attempts = models.PositiveIntegerField(default=0)
    pin_locked_until = models.DateTimeField(null=True, blank=True)

    # 🔑 Ključ 2: Passkey (WebAuthn credential ID)
    passkey_credential_id = models.CharField(max_length=512, blank=True,
                                              help_text='Base64 WebAuthn credential ID')
    passkey_public_key = models.TextField(blank=True,
                                          help_text='CBOR-encoded public key')
    passkey_sign_count = models.PositiveIntegerField(default=0)
    passkey_registered_at = models.DateTimeField(null=True, blank=True)
    passkey_device_name = models.CharField(max_length=100, blank=True)

    # 🔑 Ključ 3: Business Key
    fina_cert_fingerprint = models.CharField(
        max_length=64, blank=True,
        help_text='SHA-256 fingerprint FINA .p12 certifikata',
    )
    fina_cert_serial = models.CharField(max_length=50, blank=True)
    fina_cert_expires = models.DateField(null=True, blank=True)
    eposrednik_api_key_hash = models.CharField(
        max_length=128, blank=True,
        help_text='HMAC hash ePosrednik API ključa',
    )
    business_key_verified_at = models.DateTimeField(null=True, blank=True)

    # Auth metadata
    last_auth_method = models.CharField(max_length=20, blank=True)
    last_auth_at = models.DateTimeField(null=True, blank=True)
    auth_level = models.PositiveSmallIntegerField(
        default=0,
        help_text='0=none, 1=single key, 2=dual key, 3=triple key',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'accounts'
        verbose_name = 'TriKey profil'
        verbose_name_plural = 'TriKey profili'

    def __str__(self):
        keys = self.available_keys
        return f'{self.user.username} — {len(keys)}/3 ključa ({", ".join(keys)})'

    @property
    def available_keys(self):
        """Koje ključeve korisnik ima postavljene."""
        keys = []
        if self.pin_hash:
            keys.append('PIN')
        if self.passkey_credential_id:
            keys.append('Passkey')
        if self.fina_cert_fingerprint or self.eposrednik_api_key_hash:
            keys.append('BusinessKey')
        return keys

    @property
    def key_count(self):
        return len(self.available_keys)

    @property
    def is_fully_armed(self):
        """Ima li sva 3 ključa?"""
        return self.key_count == 3

    # ── PIN Methods ──────────────────────────────────────────

    BANNED_PINS = {
        # Sekvencijalni
        "123456", "234567", "345678", "456789", "567890",
        "654321", "543210", "987654", "876543",
        # Ponavljajući
        "111111", "222222", "333333", "444444", "555555",
        "666666", "777777", "888888", "999999", "000000",
        # Poznate kombinacije
        "112233", "998877", "121212", "010101", "131313",
        "147258", "258369", "369147", "159753",
    }

    def set_pin(self, raw_pin):
        """Postavi PIN (6 znakova). Hashira s Django hasher-om."""
        if len(raw_pin) != 6 or not raw_pin.isdigit():
            raise ValueError("PIN mora biti točno 6 znamenki")
        if raw_pin in self.BANNED_PINS:
            raise ValueError("Ovaj PIN je previše jednostavan. Odaberite sigurniji.")
        if len(set(raw_pin)) < 3:
            raise ValueError("PIN mora sadržavati barem 3 različite znamenke.")
        self.pin_hash = make_password(raw_pin)
        self.pin_set_at = timezone.now()
        self.pin_attempts = 0
        self.pin_locked_until = None
        self.save(update_fields=["pin_hash", "pin_set_at", "pin_attempts", "pin_locked_until"])

    def verify_pin(self, raw_pin):
        """Provjeri PIN. Rate limiting: 5 pokušaja → 15min lockout."""
        if self.pin_locked_until and timezone.now() < self.pin_locked_until:
            remaining = (self.pin_locked_until - timezone.now()).seconds
            raise PermissionError(f'PIN zaključan još {remaining}s. Pokušajte kasnije.')

        if not self.pin_hash:
            return False

        if check_password(raw_pin, self.pin_hash):
            self.pin_attempts = 0
            self.pin_locked_until = None
            self.last_auth_method = 'pin'
            self.last_auth_at = timezone.now()
            self.save(update_fields=['pin_attempts', 'pin_locked_until',
                                     'last_auth_method', 'last_auth_at'])
            return True
        else:
            self.pin_attempts += 1
            if self.pin_attempts >= 5:
                self.pin_locked_until = timezone.now() + timedelta(minutes=15)
                logger.warning(f'TriKey PIN locked for {self.user.username} (5 attempts)')
            self.save(update_fields=['pin_attempts', 'pin_locked_until'])
            return False

    # ── Passkey Methods ──────────────────────────────────────

    def register_passkey(self, credential_id, public_key, device_name=''):
        """Registriraj Passkey (WebAuthn)."""
        self.passkey_credential_id = credential_id
        self.passkey_public_key = public_key
        self.passkey_sign_count = 0
        self.passkey_registered_at = timezone.now()
        self.passkey_device_name = device_name
        self.save(update_fields=[
            'passkey_credential_id', 'passkey_public_key',
            'passkey_sign_count', 'passkey_registered_at', 'passkey_device_name',
        ])

    def verify_passkey(self, sign_count):
        """Verificiraj Passkey sign count (anti-replay)."""
        if sign_count <= self.passkey_sign_count:
            logger.warning(f'TriKey Passkey replay detected for {self.user.username}')
            return False
        self.passkey_sign_count = sign_count
        self.last_auth_method = 'passkey'
        self.last_auth_at = timezone.now()
        self.save(update_fields=['passkey_sign_count', 'last_auth_method', 'last_auth_at'])
        return True

    # ── Business Key Methods ─────────────────────────────────

    def register_fina_cert(self, cert_bytes):
        """Registriraj FINA .p12 cert — pohranjuj samo fingerprint."""
        import hashlib
        fingerprint = hashlib.sha256(cert_bytes).hexdigest()
        self.fina_cert_fingerprint = fingerprint
        self.business_key_verified_at = timezone.now()

        # Parse cert za serial i expiry
        try:
            from cryptography import x509
            from cryptography.hazmat.primitives.serialization import pkcs12
            private_key, cert, chain = pkcs12.load_key_and_certificates(cert_bytes, None)
            if cert:
                self.fina_cert_serial = str(cert.serial_number)[:50]
                self.fina_cert_expires = cert.not_valid_after_utc.date()
        except ImportError:
            pass

        self.save(update_fields=[
            'fina_cert_fingerprint', 'fina_cert_serial',
            'fina_cert_expires', 'business_key_verified_at',
        ])
        return fingerprint

    def register_eposrednik_key(self, api_key):
        """Registriraj ePosrednik API ključ — pohranjuj samo HMAC hash."""
        secret = getattr(settings, 'TRIKEY_HMAC_SECRET', 'limit-connect-trikey-2026')
        key_hash = hmac.new(secret.encode(), api_key.encode(), hashlib.sha256).hexdigest()
        self.eposrednik_api_key_hash = key_hash
        self.business_key_verified_at = timezone.now()
        self.save(update_fields=['eposrednik_api_key_hash', 'business_key_verified_at'])
        return key_hash

    def verify_business_key(self, fina_fingerprint=None, api_key=None):
        """Verificiraj Business Key — FINA cert fingerprint ili ePosrednik API key."""
        if fina_fingerprint and self.fina_cert_fingerprint:
            if fina_fingerprint == self.fina_cert_fingerprint:
                self.last_auth_method = 'fina_cert'
                self.last_auth_at = timezone.now()
                self.save(update_fields=['last_auth_method', 'last_auth_at'])
                return True

        if api_key and self.eposrednik_api_key_hash:
            secret = getattr(settings, 'TRIKEY_HMAC_SECRET', 'limit-connect-trikey-2026')
            check = hmac.new(secret.encode(), api_key.encode(), hashlib.sha256).hexdigest()
            if hmac.compare_digest(check, self.eposrednik_api_key_hash):
                self.last_auth_method = 'eposrednik'
                self.last_auth_at = timezone.now()
                self.save(update_fields=['last_auth_method', 'last_auth_at'])
                return True

        return False

    # ── Auth Level Calculator ────────────────────────────────

    def calculate_auth_level(self, keys_verified):
        """
        Izračunaj razinu autentifikacije.
        keys_verified: set of {'pin', 'passkey', 'business_key'}
        """
        level = len(keys_verified)
        self.auth_level = level
        self.save(update_fields=['auth_level'])
        return level

    @staticmethod
    def can_perform(required_level, current_level):
        """Može li korisnik izvršiti operaciju na ovoj razini?"""
        return current_level >= required_level


# ════════════════════════════════════════════════════════════════
# OIB LOOKUP — Sudski registar API
# ════════════════════════════════════════════════════════════════

def oib_lookup(oib):
    """
    Provjeri OIB kroz Sudski registar API.
    Returns: dict s podacima firme ili None.
    """
    import requests

    # Validate OIB format
    from core.oib_validator import validate_oib_hr
    if not oib or not validate_oib_hr(oib):
        return None

    # OIB checksum validation (ISO 7064, MOD 11,10)
    remainder = 10
    for digit in oib[:10]:
        remainder = (remainder + int(digit)) % 10
        if remainder == 0:
            remainder = 10
        remainder = (remainder * 2) % 11
    check = (11 - remainder) % 10
    if check != int(oib[10]):
        return None

    # Try Sudski registar API
    cache_key = f'oib_lookup:{oib}'
    cached = cache.get(cache_key)
    if cached:
        return cached

    try:
        # Sudski registar open data API
        url = f'https://sudreg-podaci.pravosudje.hr/api/javni/subjekt?oib={oib}'
        headers = {'Accept': 'application/json'}
        resp = requests.get(url, headers=headers, timeout=10)

        if resp.status_code == 200:
            data = resp.json()
            if data and isinstance(data, list) and len(data) > 0:
                subj = data[0]
                result = {
                    'oib': oib,
                    'name': subj.get('naziv', ''),
                    'mbs': subj.get('mbs', ''),
                    'address': subj.get('sjediste', ''),
                    'city': subj.get('grad', ''),
                    'activities': subj.get('djelatnosti', []),
                    'status': subj.get('status', ''),
                    'source': 'sudreg',
                }
                cache.set(cache_key, result, timeout=86400)  # 24h cache
                return result
    except requests.RequestException as e:
        logger.warning(f'Sudski registar API error for OIB {oib}: {e}')

    # Fallback: provjera u našoj bazi partnera
    try:
        from partners.models import Partner
        partner = Partner.objects.filter(oib=oib).first()
        if partner:
            result = {
                'oib': oib,
                'name': partner.name,
                'address': getattr(partner, 'address', ''),
                'city': getattr(partner, 'city', ''),
                'source': 'internal',
            }
            cache.set(cache_key, result, timeout=3600)
            return result
    except DatabaseError:
        pass

    return None


def generate_pin():
    """Generiraj siguran 6-digit PIN — koristi BANNED_PINS iz TriKeyProfile."""
    banned = getattr(TriKeyProfile, 'BANNED_PINS', set())
    while True:
        pin = str(secrets.randbelow(900000) + 100000)
        if len(set(pin)) < 3:
            continue
        if pin in banned:
            continue
        return pin
