"""
FernetEncryptedCharField — transparentna AES enkripcija za Django modele.

Graceful Degradation:
  - Čitanje: pokušava dekriptirati; ako ne uspije (plaintext), vraća kao-is.
  - Pisanje: ako je plaintext, kriptira; ako je već ciphertext, ostavlja.
  - Data migration: .save() na postojećem redu automatski kriptira plaintext.
"""
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models


class FernetEncryptedCharField(models.CharField):

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('max_length', 255)
        super().__init__(*args, **kwargs)

    @property
    def fernet(self):
        return Fernet(settings.FERNET_KEY.encode())

    def from_db_value(self, value, expression, connection):
        if not value:
            return value
        try:
            return self.fernet.decrypt(value.encode()).decode()
        except (InvalidToken, Exception):
            return value  # plaintext legacy

    def to_python(self, value):
        if not value:
            return value
        try:
            return self.fernet.decrypt(value.encode()).decode()
        except (InvalidToken, Exception):
            return value

    def get_prep_value(self, value):
        if not value:
            return value
        # Provjeri je li već kriptirano
        try:
            self.fernet.decrypt(value.encode())
            return value  # već ciphertext
        except (InvalidToken, Exception):
            return self.fernet.encrypt(value.encode()).decode()

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        if kwargs.get('max_length') == 255:
            del kwargs['max_length']
        return name, path, args, kwargs
