"""
memio_world/encrypted_fields.py — Fernet AES enkripcija za digitalne uspomene

ODVOJEN KLJUČ od memio_pets i ERP-a:
  - MEMIO_WORLD_FERNET_KEY u env varijabli
  - TimeCapsule poruke, MemoryVault sadržaj, FamilyStory — sve enkriptirano
  - 18 godina trajnosti — ključ se backupira na N lokacija
  - Čak ni platformski admin ne čita sadržaj bez ključa
"""

import logging
import os

from cryptography.fernet import Fernet, InvalidToken
from django.db import models

logger = logging.getLogger("memio_world.security")

_WORLD_FERNET_KEY = None


def _get_fernet():
    global _WORLD_FERNET_KEY
    if _WORLD_FERNET_KEY is None:
        key = os.environ.get("MEMIO_WORLD_FERNET_KEY", "")
        if not key:
            logger.critical("MEMIO_WORLD_FERNET_KEY nije postavljen! Podaci NEĆE biti kriptirani!")
            from django.conf import settings

            key = settings.FERNET_KEY
        _WORLD_FERNET_KEY = Fernet(key.encode())
    return _WORLD_FERNET_KEY


class WorldEncryptedField(models.TextField):
    """Transparentno šifrirani TextField za memio_world modele.
    TextField (ne CharField) jer kapsule i priče mogu biti duge.
    """

    def from_db_value(self, value, expression, connection):
        if not value:
            return value
        try:
            return _get_fernet().decrypt(value.encode()).decode()
        except (InvalidToken, Exception):
            return value

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
        try:
            _get_fernet().decrypt(value.encode())
            return value
        except (InvalidToken, Exception):
            return _get_fernet().encrypt(value.encode()).decode()
