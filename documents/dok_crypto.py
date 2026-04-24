"""
core/vivus/dok_crypto.py
VIVUS .dok kriptografski sloj — AES-256-GCM + PBKDF2-HMAC-SHA256.

Format bloba: VIVUS_DOK_V1:<salt_b64>:<nonce_b64>:<ciphertext_b64>
  salt    = 16 random bajta (za PBKDF2)
  nonce   = 12 random bajta (za AES-GCM)
  ciphertext = enkriptirani payload + 16-bajt GCM tag na kraju

Kljuc se izvodi: PBKDF2(passphrase, salt, iterations=600000, hash=SHA256) -> 32 bajta

OpenSSL kompatibilna alternativa (za "bez softvera"):
  openssl enc -aes-256-gcm -d -pbkdf2 -iter 600000 -k "fraza" -in dok.bin
"""
import base64
import os
import hashlib
import hmac as _hmac
from dataclasses import dataclass
from typing import Union


VERSION = "VIVUS_DOK_V1"
PBKDF2_ITERATIONS = 600_000
SALT_SIZE = 16
NONCE_SIZE = 12


@dataclass
class DokBlob:
    version: str
    salt: bytes
    nonce: bytes
    ciphertext: bytes  # includes GCM tag (last 16 bytes)

    def to_string(self) -> str:
        """Serializiraj u prijenosni string."""
        return ":".join([
            self.version,
            base64.urlsafe_b64encode(self.salt).decode(),
            base64.urlsafe_b64encode(self.nonce).decode(),
            base64.urlsafe_b64encode(self.ciphertext).decode(),
        ])

    @classmethod
    def from_string(cls, s: str) -> "DokBlob":
        parts = s.strip().split(":")
        if len(parts) != 4 or parts[0] != VERSION:
            raise ValueError(f"Nevazeci DokBlob format: ocekivano {VERSION}")
        return cls(
            version=parts[0],
            salt=base64.urlsafe_b64decode(parts[1]),
            nonce=base64.urlsafe_b64decode(parts[2]),
            ciphertext=base64.urlsafe_b64decode(parts[3]),
        )


def _derive_key(passphrase: Union[str, bytes], salt: bytes) -> bytes:
    """PBKDF2-HMAC-SHA256, 600k iteracija -> 32 bajta."""
    if isinstance(passphrase, str):
        passphrase = passphrase.encode("utf-8")
    return hashlib.pbkdf2_hmac("sha256", passphrase, salt, PBKDF2_ITERATIONS, dklen=32)


def encrypt(data: Union[str, bytes], passphrase: Union[str, bytes]) -> str:
    """
    Enkriptiraj data s passphrase.
    Vraca prijenosni VIVUS_DOK_V1:... string.
    """
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    if isinstance(data, str):
        data = data.encode("utf-8")

    salt = os.urandom(SALT_SIZE)
    nonce = os.urandom(NONCE_SIZE)
    key = _derive_key(passphrase, salt)

    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, data, None)  # ciphertext + 16-byte tag

    blob = DokBlob(version=VERSION, salt=salt, nonce=nonce, ciphertext=ciphertext)
    return blob.to_string()


def decrypt(blob_string: str, passphrase: Union[str, bytes]) -> bytes:
    """
    Dekriptiraj VIVUS_DOK_V1:... string s passphrase.
    Vraca originalne bajte.
    Baca ValueError ako je lozinka pogresna ili je blob ostecen.
    """
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.exceptions import InvalidTag

    blob = DokBlob.from_string(blob_string)
    key = _derive_key(passphrase, blob.salt)

    aesgcm = AESGCM(key)
    try:
        return aesgcm.decrypt(blob.nonce, blob.ciphertext, None)
    except InvalidTag:
        raise ValueError("Pogresna lozinka ili osteceni dokument")


def encrypt_to_file(data: Union[str, bytes], passphrase: Union[str, bytes], path: str) -> None:
    """Enkriptiraj i spremi u .dok fajl."""
    blob_string = encrypt(data, passphrase)
    with open(path, "w", encoding="utf-8") as f:
        f.write(blob_string)


def decrypt_from_file(path: str, passphrase: Union[str, bytes]) -> bytes:
    """Ucitaj .dok fajl i dekriptiraj."""
    with open(path, encoding="utf-8") as f:
        blob_string = f.read().strip()
    return decrypt(blob_string, passphrase)


def fingerprint(blob_string: str) -> str:
    """SHA3-256 hash bloba — za ChainBlock/VIVUS L1."""
    return hashlib.sha3_256(blob_string.encode()).hexdigest()
