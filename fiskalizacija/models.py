"""FiscalConfig – per-company FINA certificate configuration."""
import base64
import hashlib
import os

from cryptography.fernet import Fernet
from django.conf import settings
from django.db import models


def _fernet():
    """Derive a Fernet key from Django SECRET_KEY."""
    key = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


class FiscalConfig(models.Model):
    """
    FINA digitalni certifikat i konfiguracija fiskalizacije po tvrtki.
    Certifikat (.p12) se sprema u /var/www/fina-connect/certs/
    Lozinka je Fernet-enkriptirana (ključ = SHA256(SECRET_KEY)).
    """
    company = models.OneToOneField(
        'companies.Company', on_delete=models.CASCADE,
        related_name='fiscal_config', verbose_name='Tvrtka',
    )
    cert_filename    = models.CharField(max_length=255, blank=True,
                                        verbose_name='Naziv .p12 datoteke')
    _cert_password   = models.BinaryField(null=True, blank=True,
                                           db_column='cert_password',
                                           verbose_name='Lozinka (enkriptirana)')
    ozn_pos_pr       = models.CharField(max_length=20, default='1',
                                         verbose_name='Oznaka poslovnog prostora')
    ozn_nap_ur       = models.CharField(max_length=20, default='1',
                                         verbose_name='Oznaka naplatnog uređaja')
    is_demo          = models.BooleanField(default=True,
                                            verbose_name='Demo način (CIS test)')
    is_active        = models.BooleanField(default=False,
                                            verbose_name='Fiskalizacija aktivna')
    cert_expires_at  = models.DateTimeField(null=True, blank=True,
                                             verbose_name='Certifikat istječe',
                                             help_text='Automatski iz P12 pri uploadu')
    cert_subject     = models.CharField(max_length=200, blank=True, default='',
                                         verbose_name='Certifikat Subject')
    last_test_at     = models.DateTimeField(null=True, blank=True,
                                             verbose_name='Zadnji test')
    last_test_ok     = models.BooleanField(null=True, blank=True,
                                            verbose_name='Zadnji test OK')
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    def extract_cert_metadata(self):
        """Izvuci expiry date i subject iz P12 — pozovi jednom pri uploadu."""
        import os
        cert_path = self.cert_path if hasattr(self, 'cert_path') else ''
        if not cert_path or not os.path.exists(cert_path):
            return
        try:
            from cryptography.hazmat.primitives.serialization.pkcs12 import load_key_and_certificates
            password = self.get_password()
            if isinstance(password, str):
                password = password.encode()
            with open(cert_path, 'rb') as f:
                p12_data = f.read()
            key, cert, chain = load_key_and_certificates(p12_data, password)
            self.cert_expires_at = cert.not_valid_after_utc
            self.cert_subject = cert.subject.rfc4514_string()[:200]
            self.save(update_fields=['cert_expires_at', 'cert_subject'])
        except (FileNotFoundError, PermissionError, IOError):
            pass

    class Meta:
        verbose_name        = 'Konfiguracija fiskalizacije'
        verbose_name_plural = 'Konfiguracije fiskalizacije'

    def __str__(self):
        status = 'AKTIVAN' if self.is_active else 'neaktivan'
        mode   = 'DEMO' if self.is_demo else 'PRODUKCIJA'
        return f'{self.company.name} – {status} ({mode})'

    def set_password(self, raw: str):
        if raw:
            self._cert_password = _fernet().encrypt(raw.encode())
        else:
            self._cert_password = None

    def get_password(self) -> str:
        if self._cert_password:
            return _fernet().decrypt(bytes(self._cert_password)).decode()
        return ''

    @property
    def cert_path(self) -> str | None:
        if not self.cert_filename:
            return None
        import os
        return os.path.join(settings.BASE_DIR, 'certs', self.cert_filename)

    @property
    def cert_exists(self) -> bool:
        p = self.cert_path
        return bool(p and os.path.isfile(p))
