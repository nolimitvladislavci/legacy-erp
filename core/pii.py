"""
core/pii.py — PII Encryption/Decryption Service

Transparentni encrypt/decrypt za osobne podatke (GDPR čl.32).
Koristi Fernet (AES-128-CBC) koji je već u sustavu za payment keys.

Polja koja štitimo:
  - rental.Guest: document_number, first_name, last_name
  - partners.Partner: oib (za inozemne)

Hybrid pristup: plaintext za search, encrypted za backup/audit.
"""

import base64
import logging
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

logger = logging.getLogger("pii")


@lru_cache(maxsize=1)
def _get_fernet():
    key = getattr(settings, "FIELD_ENCRYPTION_KEY", None) or getattr(settings, "FERNET_KEY", None)
    if not key:
        logger.error("FIELD_ENCRYPTION_KEY nije postavljen! PII enkripcija onemogućena.")
        return None
    if isinstance(key, str):
        key = key.encode()
    try:
        return Fernet(key)
    except Exception as e:
        logger.error("Fernet key error: %s", e)
        return None


def encrypt_pii(plaintext: str) -> str:
    if not plaintext:
        return ""
    f = _get_fernet()
    if not f:
        return ""
    try:
        token = f.encrypt(plaintext.encode("utf-8"))
        return base64.urlsafe_b64encode(token).decode("ascii")
    except ValueError as e:
        logger.warning("PII encrypt failed: %s", e)
        return ""


def decrypt_pii(ciphertext: str) -> str:
    if not ciphertext:
        return ""
    f = _get_fernet()
    if not f:
        return "[ENCRYPTED]"
    try:
        token = base64.urlsafe_b64decode(ciphertext.encode("ascii"))
        return f.decrypt(token).decode("utf-8")
    except (InvalidToken, Exception) as e:
        logger.warning("PII decrypt failed: %s", e)
        return "[ENCRYPTED]"


def encrypt_guest_pii(guest):
    changed = False
    if guest.document_number and not guest.encrypted_document_number:
        guest.encrypted_document_number = encrypt_pii(guest.document_number)
        changed = True
    if guest.first_name and not guest.encrypted_first_name:
        guest.encrypted_first_name = encrypt_pii(guest.first_name)
        changed = True
    if guest.last_name and not guest.encrypted_last_name:
        guest.encrypted_last_name = encrypt_pii(guest.last_name)
        changed = True
    if changed:
        guest.pii_encrypted = True
    return changed


def gdpr_erase_guest(guest):
    guest.first_name = "[ERASED]"
    guest.last_name = "[ERASED]"
    guest.document_number = "[ERASED]"
    guest.document_country = ""
    guest.nationality = ""
    guest.date_of_birth = None
    guest.save(
        update_fields=[
            "first_name",
            "last_name",
            "document_number",
            "document_country",
            "nationality",
            "date_of_birth",
        ]
    )
    logger.info("GDPR erasure: Guest %s PII obrisano", guest.pk)


def batch_encrypt_guests(company=None, dry_run=False):
    from rental.models import Guest

    qs = Guest.objects.filter(pii_encrypted=False)
    if company:
        qs = qs.filter(booking__company=company)
    total = qs.count()
    encrypted = 0
    for guest in qs.iterator(chunk_size=100):
        if encrypt_guest_pii(guest):
            if not dry_run:
                guest.save(
                    update_fields=[
                        "encrypted_document_number",
                        "encrypted_first_name",
                        "encrypted_last_name",
                        "pii_encrypted",
                    ]
                )
            encrypted += 1
    logger.info("Batch PII: %d/%d %s", encrypted, total, "(DRY)" if dry_run else "encrypted")
    return {"total": total, "encrypted": encrypted}
