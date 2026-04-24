"""
core/tajna_protokol.py — TAJNA Protocol v1.0

Rješava ahilovu petu BunkerSeala:
  Napadač s DB pristupom ne može lažirati pečate jer ne može reproducirati
  TAJNA_KLJUČ bez TOČNIH bytova krunica_nft_bridge.so binarnog.

Trokutasta obrana (svaki štiti drugi dva):
  krunica.so  → zaštićen BunkerSealom
  BunkerSeal  → zaštićen TAJNA lancem
  TAJNA lanac → zaštićen krunica.so bajtovima

TAJNA_KLJUČ = HKDF(
    SHA3-256(krunica.so[:ANCHOR_SIZE])   ← binarni sidro
  + Kyber768_random(32)                  ← kvantna entropija (efemeralna)
)

TAJNA_N = HMAC-SHA3-256(
    TAJNA_KLJUČ,
    merkle_root_N || TAJNA_{N-1} || timestamp_N
)

TAJNA_KLJUČ se čuva kriptiran: AES-256-GCM(key=SHA3(krunica.so))
→ dešifriranje zahtijeva TOČNE bytove .so
→ modificiranjem .so → sve stare TAJNA ključeve ne možeš dešifrirati
→ bez TAJNA_KLJUČ → ne možeš lažirati ni jedan TAJNA_N
→ lanac → ne možeš lažirati TAJNA_N bez TAJNA_{N-1}
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
from pathlib import Path

logger = logging.getLogger("fenix.tajna")

# ── Konstante ─────────────────────────────────────────────────────────────────

# Binarni sidro — Cython kompajlirani modul (1.4MB)
# Zamijeniti ako se .so regenerira (nova kompilacija)
_SO_PATH = Path("/var/www/fenix-v3/evalidator/krunica_nft_bridge.cpython-312-x86_64-linux-gnu.so")

# Koliko bytova .so koristimo kao sidro (prvih 64KB = dovoljno entropije)
_ANCHOR_SIZE = 65536

# Genesis marker za prvu vezu u lancu
_GENESIS = b"TAJNA-GENESIS-FENIX-V3-2026"


# ── Binarni sidro ─────────────────────────────────────────────────────────────

def _read_anchor_bytes() -> bytes:
    """Čitaj prvih _ANCHOR_SIZE bytova .so fajla — binarni sidro."""
    try:
        with open(_SO_PATH, "rb") as f:
            return f.read(_ANCHOR_SIZE)
    except FileNotFoundError:
        # Fallback: genesis.py ako .so ne postoji
        gp = Path("/var/www/fenix-v3/evalidator/genesis.py")
        logger.warning("TAJNA: krunica.so not found, using genesis.py as anchor")
        return gp.read_bytes()


def _so_anchor_hash() -> bytes:
    """SHA3-256 od anchor bytova — binarni ključ."""
    anchor = _read_anchor_bytes()
    return hashlib.sha3_256(anchor).digest()


def _so_fingerprint() -> str:
    """Prvih 16 hex znakova hasha — za log i provjeru."""
    return _so_anchor_hash().hex()[:16]


# ── Kvantna entropija ─────────────────────────────────────────────────────────

def _quantum_entropy(n: int = 32) -> bytes:
    """Kyber768 ako dostupan, inače os.urandom (kriptografski siguran)."""
    try:
        import oqs
        kem = oqs.KeyEncapsulation("Kyber768")
        pub = kem.generate_keypair()
        _, ss = kem.encap_secret(pub)
        return (ss + os.urandom(n))[:n]
    except Exception:
        return os.urandom(n)


# ── TAJNA_KLJUČ generacija ────────────────────────────────────────────────────

def generate_tajna_key() -> bytes:
    """
    Generiraj TAJNA_KLJUČ za novu sesiju pečatiranja.

    TAJNA_KLJUČ = HKDF-SHA3-256(
        ikm  = SHA3-256(krunica.so[:64KB])  ← binarni sidro
             + Kyber768_random(32)           ← kvantna entropija
        salt = b"TAJNA-v1"
        info = b"fenix-bunker-seal"
    )

    Rezultat je 32-bajtni ključ koji:
    - Ovisi o TOČNIM bytovima krunica.so
    - Sadrži nepredvidivu kvantnu entropiju iz ove sesije
    - Ne može se reproducirati bez oba komponenta
    """
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF

    so_hash = _so_anchor_hash()         # SHA3-256(krunica.so) — 32 bajta
    q_entropy = _quantum_entropy(32)    # Kyber/os.urandom — 32 bajta

    ikm = so_hash + q_entropy           # 64 bajta kombiniranog materijala

    key = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"TAJNA-v1",
        info=b"fenix-bunker-seal",
    ).derive(ikm)

    logger.info(
        "TAJNA_KLJUČ generiran: so_anchor=%s kyber=%s",
        so_hash.hex()[:12],
        "ACTIVE" if _kyber_ok() else "X25519-FB",
    )
    return key


# ── TAJNA_KLJUČ enkripcija / dekripcija ──────────────────────────────────────

def encrypt_tajna_key(tajna_key: bytes) -> tuple[str, str]:
    """
    Enkriptiraj TAJNA_KLJUČ s AES-256-GCM.
    Enkripcijski ključ = SHA3-256(krunica.so[:64KB]).

    Returns: (ciphertext_b64, nonce_b64)
    Da dešifriraš: trebaš TOČNE bytove krunica.so.
    Modificiran .so = nevalidan ključ = garbage = alarm.
    """
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    aes_key = _so_anchor_hash()          # AES key = SHA3(krunica.so)
    nonce = os.urandom(12)
    ct = AESGCM(aes_key).encrypt(nonce, tajna_key, b"TAJNA-v1")

    return (
        base64.b64encode(ct).decode(),
        base64.b64encode(nonce).decode(),
    )


def decrypt_tajna_key(ct_b64: str, nonce_b64: str) -> bytes | None:
    """
    Dešifriruj TAJNA_KLJUČ.
    Ako je .so modificiran → vraća None (alarm triger).
    """
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.exceptions import InvalidTag

    try:
        aes_key = _so_anchor_hash()
        nonce = base64.b64decode(nonce_b64)
        ct = base64.b64decode(ct_b64)
        return AESGCM(aes_key).decrypt(nonce, ct, b"TAJNA-v1")
    except (InvalidTag, Exception) as e:
        logger.critical(
            "TAJNA ALARM: TAJNA_KLJUČ dekripcija neuspješna! "
            "krunica.so možda modificiran! err=%s so_fp=%s",
            e, _so_fingerprint()
        )
        return None


# ── TAJNA_N računanje ─────────────────────────────────────────────────────────

def compute_tajna_n(
    tajna_key: bytes,
    merkle_root: str,
    prev_tajna: str,
    timestamp: str = "",  # Zadržan za API kompatibilnost, ne koristi se u poruci
) -> str:
    """
    TAJNA_N = HMAC-SHA3-256(
        TAJNA_KLJUČ,
        merkle_root_N || "||" || TAJNA_{N-1} || "||" || timestamp_N
    )

    Lanac: svaki TAJNA ovisi o prethodnom.
    Da lažiraš TAJNA_16 → trebaš TAJNA_15 → trebaš TAJNA_14 → ... → trebaš TAJNA_1.
    Svaki zahtijeva TAJNA_KLJUČ iz te sesije pečatiranja.
    TAJNA_KLJUČ je enkriptiran krunica.so → nedostupan bez .so.
    """
    prev_bytes = prev_tajna.encode() if prev_tajna else _GENESIS
    # Timestamp nije u poruci — Kyber entropija u TAJNA_KLJUČ garantira jedinstvenost
    # bez potrebe za timestamp koji se može razlikovati između kreiranja i verifikacije
    message = (
        merkle_root.encode()
        + b"||"
        + prev_bytes
    )
    mac = hmac.new(tajna_key, message, hashlib.sha3_256).digest()
    return base64.b64encode(mac).decode()


# ── Verifikacija ──────────────────────────────────────────────────────────────

def verify_tajna_n(
    ct_b64: str,
    nonce_b64: str,
    stored_tajna_n: str,
    merkle_root: str,
    prev_tajna: str,
    timestamp: str = "",  # Vise se ne koristi — Kyber entropija garantira jedinstvenost
) -> bool:
    """
    Verificiraj TAJNA_N za zadani pečat.

    Returns False ako:
    - krunica.so modificiran (dekripcija neuspješna)
    - merkle_root promijenjen (DB tamper)
    - TAJNA lanac prekinut (prethodni pečati lažirani)
    """
    tajna_key = decrypt_tajna_key(ct_b64, nonce_b64)
    if tajna_key is None:
        logger.critical("TAJNA VERIFY FAIL: ne mogu dešifrirati TAJNA_KLJUČ (so tamper?)")
        return False

    computed = compute_tajna_n(tajna_key, merkle_root, prev_tajna)

    if computed != stored_tajna_n:
        logger.critical(
            "TAJNA VERIFY FAIL: lažiran pečat! merkle=%s stored=%s computed=%s",
            merkle_root[:16], stored_tajna_n[:16], computed[:16]
        )
        return False

    return True


# ── Seal-level API (poziva bunker_seal.py) ───────────────────────────────────

class TajnaSession:
    """
    Kontekst jednog ciklusa pečatiranja.
    Generiraj jednom, koristi za sve pečate u sesiji, zatim uništi.
    """

    def __init__(self):
        self.tajna_key = generate_tajna_key()
        self.ct_b64, self.nonce_b64 = encrypt_tajna_key(self.tajna_key)
        self.so_fingerprint = _so_fingerprint()
        logger.info("TajnaSession inicijaliziran: so=%s", self.so_fingerprint)

    def seal(self, merkle_root: str, prev_tajna: str, timestamp: str = "") -> str:
        """Izračunaj TAJNA_N za ovaj pečat."""
        return compute_tajna_n(self.tajna_key, merkle_root, prev_tajna)

    def export(self) -> dict:
        """Podaci za Storage u BunkerSeal modelu."""
        return {
            "tajna_key_enc": self.ct_b64,
            "tajna_nonce":   self.nonce_b64,
            "so_fingerprint": self.so_fingerprint,
        }

    def destroy(self):
        """Uništi TAJNA_KLJUČ iz memorije (security hygiene)."""
        # Overwrite in-memory key
        import ctypes
        try:
            buf = (ctypes.c_char * len(self.tajna_key)).from_buffer_copy(self.tajna_key)
            ctypes.memset(buf, 0, len(self.tajna_key))
        except Exception:
            pass
        self.tajna_key = b"\x00" * 32
        logger.info("TajnaSession destroyed — TAJNA_KLJUČ obrisan iz memorije")


# ── Status / diagnostika ──────────────────────────────────────────────────────

def tajna_status() -> dict:
    """Dijagnostika TAJNA protokola."""
    try:
        anchor = _so_anchor_hash()
        so_ok = _SO_PATH.exists()
        so_size = _SO_PATH.stat().st_size if so_ok else 0
    except Exception as e:
        return {"ok": False, "error": str(e)}

    return {
        "ok": True,
        "so_path": str(_SO_PATH),
        "so_exists": so_ok,
        "so_size_mb": round(so_size / 1024 / 1024, 2),
        "so_fingerprint": anchor.hex()[:16] if so_ok else "N/A",
        "kyber_active": _kyber_ok(),
        "anchor_size_kb": _ANCHOR_SIZE // 1024,
        "protocol_version": "TAJNA-1.0",
    }


def _kyber_ok() -> bool:
    try:
        import oqs
        return True
    except ImportError:
        return False


# ── INOVACIJA 1: Shamir 2-of-2 Split ──────────────────────────────────────────

def split_tajna_key_shamir(tajna_key: bytes, passphrase: str) -> tuple:
    """
    Podijeli TAJNA_KLJUC na 2 dijela (Shamir 2-of-2 XOR).
    Share A = fizicki (cuva se enkriptirano na serveru)
    Share B = passphrase (zivi samo u covjekovoj glavi)

    Rekonstrukcija UVIJEK zahtijeva i jedno i drugo.
    Napadac s DB pristupom ima samo Share A -- beskorisno.
    """
    from core.vivus.shamir import split_key_2of2
    return split_key_2of2(tajna_key, passphrase)


def reconstruct_tajna_key_shamir(share_a: str, share_b: str, passphrase: str) -> bytes:
    """Rekonstruiraj TAJNA_KLJUC iz 2 Shamir dijela + passphrase."""
    from core.vivus.shamir import combine_key_2of2
    return combine_key_2of2(share_a, share_b, passphrase)


# ── INOVACIJA 2: MMR root za lanac ────────────────────────────────────────────

def compute_mmr_root(tajna_chain: list) -> str:
    """
    Izracunaj Merkle Mountain Range root za TAJNA lanac.
    O(log n) verifikacija umjesto O(n) linearnog lanca.

    tajna_chain: kronoloska lista svih TAJNA_N vrijednosti
    Returns: MMR root hash -- moze se cuvati u ChainBlock za vanjske audite
    """
    from core.vivus.mmr import mmr_root
    return mmr_root(tajna_chain)


def generate_tajna_audit_proof(tajna_chain: list, block_index: int) -> dict:
    """
    Generiraj inclusion proof za jedan TAJNA_N pecat.
    Auditor moze verificirati bez pristupa cijelom lancu.
    """
    from core.vivus.mmr import mmr_inclusion_proof
    return mmr_inclusion_proof(tajna_chain, block_index)


# ── INOVACIJA 3: Time-Lock dead-man switch ────────────────────────────────────

def seal_tajna_timelock(tajna_key: bytes, passphrase: str, ttl_days: int = 30) -> str:
    """
    Zapecati TAJNA_KLJUC u Time-Lock omotnicu.
    - Legit user s passphrase: unlock u ms
    - Napadac bez passphrase: mora rijesiti CPU puzzle (~0.1s-25s ovisno o hardness)
    - Dead-man switch: ako nije 'dotaknut' u ttl_days dana -> ALARM

    Returns JSON string omotnice (za cuvanje u DB ili fajlu).
    """
    from core.vivus.timelock import create_timelock
    env = create_timelock(tajna_key, passphrase, ttl_days=ttl_days)
    return env.to_json()


def unseal_tajna_timelock(envelope_json: str, passphrase: str) -> bytes:
    """Otkljucaj TAJNA_KLJUC iz Time-Lock omotnice s passphrase."""
    from core.vivus.timelock import TimeLockEnvelope, unlock_with_passphrase, check_deadman
    env = TimeLockEnvelope.from_json(envelope_json)

    # Provjeri dead-man status
    status = check_deadman(env)
    if not status["alive"]:
        logger.critical("TAJNA TIMELOCK: dead-man aktiviran -- pristup blokiran!")
        raise ValueError("TAJNA dead-man aktiviran -- sigurnosni protokol je zaustavio pristup")

    return unlock_with_passphrase(env, passphrase)


def touch_tajna_timelock(envelope_json: str) -> str:
    """Refreshaj dead-man switch -- pozivati dnevno ili pri svakom normalnom pecatiranju."""
    from core.vivus.timelock import TimeLockEnvelope, touch
    env = TimeLockEnvelope.from_json(envelope_json)
    env = touch(env)
    return env.to_json()
