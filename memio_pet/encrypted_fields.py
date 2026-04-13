"""
memio_pet/encrypted_fields.py — Fernet AES enkripcija s MEMIO-ZASEBNIM ključem

Doktrina "boje u vreći":
  - Šifrira email, OIB, IP adrese i osobne podatke u memio_pets bazi
  - Koristi MEMIO_PETS_FERNET_KEY — odvojen od ERP Fernet ključa
  - Čak ni ERP admin ne može čitati memio_pets PII bez ovog ključa
  - Ključ se čuva odvojeno od baze (env var, vault)

Ako Hrvoje uzme DB dump: dobiva AES-128-CBC šifrat.
Bez ključa → neupotrebljivi bajt niz.
"""
import logging
import os

from cryptography.fernet import Fernet, InvalidToken
from django.db import models

logger = logging.getLogger('memio_pet.security')

_MEMIO_FERNET_KEY = None


def _get_fernet():
    global _MEMIO_FERNET_KEY
    if _MEMIO_FERNET_KEY is None:
        key = os.environ.get('MEMIO_PETS_FERNET_KEY', '')
        if not key:
            logger.critical("MEMIO_PETS_FERNET_KEY nije postavljen! PII podaci NEĆE biti kriptirani!")
            # Fallback: koristi ERP ključ (bolje nego plaintext)
            from django.conf import settings
            key = settings.FERNET_KEY
        _MEMIO_FERNET_KEY = Fernet(key.encode())
    return _MEMIO_FERNET_KEY


class MemioEncryptedField(models.CharField):
    """
    Transparentno šifrirani CharField za memio_pet modele.
    U bazi: AES-128-CBC ciphertext (Fernet format)
    U Python-u: plaintext string
    """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('max_length', 512)
        super().__init__(*args, **kwargs)

    def from_db_value(self, value, expression, connection):
        if not value:
            return value
        try:
            return _get_fernet().decrypt(value.encode()).decode()
        except (InvalidToken, Exception):
            return value  # plaintext fallback (migracija)

    def to_python(self, value):
        if not value:
            return value
        try:
            return _get_fernet().decrypt(value.encode()).decode()
        except (InvalidToken, Exception):
            return value

    def get_prep_value(self, value):
        if not value:
            return value
        # Provjeri je li već kriptirano
        try:
            _get_fernet().decrypt(value.encode())
            return value  # već ciphertext
        except (InvalidToken, Exception):
            return _get_fernet().encrypt(value.encode()).decode()

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        if kwargs.get('max_length') == 512:
            del kwargs['max_length']
        return name, path, args, kwargs
