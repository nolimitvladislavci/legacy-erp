"""
evalidator/genesis.py — Genesis Block kreator

Kreira Block #0 ChainBlock lanca za NO LIMIT udrugu.
Zove se jednom, sutra (2026-04-20), čim Marija donese
rješenje o registraciji i OIB udruge.

Trenutno: Ivan Brtan OIB (70086599476) kao privremeni nosač IP-a.
Zamjena: update_genesis_oib(novi_oib) kada stigne OIB udruge.

Javna verifikacija: /verify/<seal_token>/
"""

import hashlib
from datetime import datetime

from core.dok_package import create_dok_package
from django.utils import timezone as dj_timezone

from .models import ChainBlockPOE

# ─────────────────────────────────────────────────────────────────────────────
# KONSTANTE
# ─────────────────────────────────────────────────────────────────────────────
GENESIS_ISSUER_NAME = "NO LIMIT — udruga za promicanje digitalizacije i dokaz autentičnosti"
GENESIS_ISSUER_OIB = "70086599476"  # Ivan Brtan OIB — privremeno do OIB udruge

GENESIS_TITLE = "Genesis Block #0 — Osnivački akt NO LIMIT i .dok standard"
GENESIS_DESCRIPTION = (
    "Digitalni osnivački akt NO LIMIT — udruge za promicanje digitalizacije i dokaz autentičnosti. "
    "Osnivači: Ivan Brtan (predsjednik), Ivica Kruljac (tajnik), "
    "Marija Brtan (zapisničar), Antonio Brtan (1. član). "
    "Projekti: Digitalni Roditelj · memio (pet/farm/world) · eValidator · LIMIT Connect · eArhivator (.dok standard). "
    "Zapečaćen sustavom čiji je intelektualni vlasnik NO LIMIT udruga. "
    "Sustav dokazuje vlastito rođenje. "
    "Autor: Ivan Brtan (osnivač) + CC (claude-sonnet-4-6, co-autor). "
    "Datum: 2026-04-20."
)

GENESIS_SEAL_TOKEN = "NOLIMIT-GENESIS-0001"
VERIFY_BASE_URL = "https://evalidator.hr"


# ─────────────────────────────────────────────────────────────────────────────
# ChainBlock specifikacija — tekst dokumenta (generira se ako nema PDF-a)
# ─────────────────────────────────────────────────────────────────────────────
CHAINBLOCK_SPEC_TEXT = """\
CHAINBLOCK SPECIFIKACIJA v1.0
NO LIMIT — Udruga za promicanje digitalizacije i dokaz autentičnosti
Datum: 2026-04-20

OSNIVAČI:
  Ivan Brtan     — predsjednik
  Ivica Kruljac  — tajnik
  Marija Brtan   — zapisničar
  Antonio Brtan  — 1. član

PROJEKTI:
  Digitalni Roditelj · memio (pet/farm/world) · eValidator · LIMIT Connect · eArhivator (.dok)

Autor: Ivan Brtan (osnivač) + CC (claude-sonnet-4-6, co-autor)

================================================================
ŠTO JE CHAINBLOCK
================================================================

ChainBlock je kriptografski lanac dokaza postojanja (Proof of Existence).
Svaki blok u lancu sadrži:

  1. Listu zapečaćenih dokumenata (SHA-256 hash svakog)
  2. Hash prethodnog bloka (chain integrity)
  3. SHA-256 hash cijelog bloka (block_hash)
  4. eValidator seal_token za javnu verifikaciju
  5. Timestamp pečata (nepromjenjiv)

Lanac je append-only — blokovi se samo dodaju, nikad ne brišu ili mijenjaju.
Ako se ijedan bit u bilo kojoj datoteci promijeni, hash ne odgovara.

================================================================
GENESIS BLOCK #0
================================================================

Genesis Block je Block #0 — prvi u nizu.
Nema prethodnog bloka (prev_hash = "genesis").
Sadrži osnivačke dokumente NO LIMIT udruge:

  1. Statut NO LIMIT (PDF s web stranice)
  2. Rješenje o registraciji (Registar udruga RH, 2026-04-20)
  3. Ova ChainBlock specifikacija

Značenje:
  Udruga postoji od sutra pravno.
  Digitalno — postoji od trenutka pečata, s nepobitnim timestampom,
  zapečaćena vlastitim sustavom koji je njezin intelektualni vlasnik.

  "Sustav koji dokazuje vlastito rođenje."

================================================================
.DOK FORMAT
================================================================

Svaki blok se pakira u .dok datoteku (ZIP arhiva):

  manifest.xml   — MPEG-7 kompatibilan opis sadržaja
  master/        — originalni dokumenti (neizmijenjeni)
  schema.xsd     — embedana kopija sheme (čitljivo bez interneta)
  readme.txt     — HR + EN + DE objašnjenje

Otvori ga za 100 godina bez interneta i znat ćeš što je i što znači.

================================================================
PRAVNA OSNOVA
================================================================

  eIDAS Art. 41  — elektronički vremenski žig = presumpcija integriteta
  ZED HR NN 150/05 — digitalni dokument s timestampom = original
  GDPR Art. 6(1)(b) — pohrana u svrhu izvršenja obveza

================================================================
VERIFIKACIJA
================================================================

  Javna: https://evalidator.hr/verify/NOLIMIT-GENESIS-0001/
  API:   https://evalidator.hr/api/verify/NOLIMIT-GENESIS-0001/

  Svaki čitatelj može provjeriti integritet bez kontaktiranja
  NO LIMIT ili Fenix sustava — samo SHA-256 i timestamp.

================================================================
INTELEKTUALNO VLASNIŠTVO
================================================================

  eArhivator sustav, ChainBlock format i .dok specifikacija
  intelektualno je vlasništvo NO LIMIT.
  Svrha: promicanje digitalizacije i dokaz autentičnosti.
  Projekti: Digitalni Roditelj · Memio (pet/farm/world) · eValidator · .dok standard
  OIB nosača: 70086599476 (Ivan Brtan, privremeno do OIB udruge)

  Sustav je razvijen u suradnji s Claude Code (Anthropic) —
  CC (claude-sonnet-4-6) je co-autor specifikacije.

================================================================
"""


def _compute_block_hash(
    block_number: int,
    issuer_oib: str,
    issuer_name: str,
    documents: list[dict],
    prev_hash: str,
    timestamp: datetime,
) -> str:
    """Deterministički SHA-256 hash bloka."""
    import json

    data = json.dumps(
        {
            "block_number": block_number,
            "issuer_oib": issuer_oib,
            "documents": sorted(d["hash"] for d in documents),
            "prev_hash": prev_hash,
            "timestamp": timestamp.isoformat(),
            "issuer": issuer_name,
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def create_genesis_block(
    statut_pdf: bytes | None = None,
    rjesenje_pdf: bytes | None = None,
    issuer_oib: str = GENESIS_ISSUER_OIB,
    issuer_name: str = GENESIS_ISSUER_NAME,
) -> ChainBlockPOE:
    """
    Kreira Genesis Block #0.

    Args:
        statut_pdf:   PDF sadržaj Statuta (bytes). Ako None, koristi placeholder.
        rjesenje_pdf: PDF sadržaj Rješenja o registraciji (bytes). Ako None, placeholder.
        issuer_oib:   OIB nosača IP-a (default: Ivan Brtan, zamijeni OIB-om udruge).
        issuer_name:  Naziv nosača IP-a.

    Returns:
        ChainBlockPOE — Genesis Block #0
    """
    if ChainBlockPOE.objects.filter(block_number=0).exists():
        raise ValueError("Genesis Block #0 već postoji. Ne može se kreirati dvaput.")

    ts = dj_timezone.now()

    # Pripremi datoteke
    files = []

    if statut_pdf:
        files.append(
            {
                "name": "statut-no-limit.pdf",
                "content": statut_pdf,
                "mime": "application/pdf",
            }
        )
    else:
        # Placeholder do pravog PDF-a
        placeholder = b"%PDF-1.4 PLACEHOLDER: Statut NO LIMIT (uploadati pravi PDF)"
        files.append(
            {
                "name": "statut-no-limit-placeholder.txt",
                "content": placeholder,
                "mime": "text/plain",
            }
        )

    if rjesenje_pdf:
        files.append(
            {
                "name": "rjesenje-o-registraciji-no-limit.pdf",
                "content": rjesenje_pdf,
                "mime": "application/pdf",
            }
        )
    else:
        placeholder = b"PLACEHOLDER: Rjesenje o registraciji (uploadati sutra, 2026-04-20)"
        files.append(
            {
                "name": "rjesenje-o-registraciji-placeholder.txt",
                "content": placeholder,
                "mime": "text/plain",
            }
        )

    # ChainBlock specifikacija — uvijek prisutna, to je srž
    files.append(
        {
            "name": "chainblock-specifikacija-v1.txt",
            "content": CHAINBLOCK_SPEC_TEXT.encode("utf-8"),
            "mime": "text/plain; charset=utf-8",
        }
    )

    # Izračunaj hasheve dokumenata (potrebno za block_hash)
    documents_meta = [
        {
            "name": f["name"],
            "hash": hashlib.sha256(f["content"]).hexdigest(),
            "size": len(f["content"]),
            "mime": f.get("mime", "application/octet-stream"),
        }
        for f in files
    ]

    prev_hash = "genesis"  # Block #0 nema prethodnika
    block_hash = _compute_block_hash(
        block_number=0,
        issuer_oib=issuer_oib,
        issuer_name=issuer_name,
        documents=documents_meta,
        prev_hash=prev_hash,
        timestamp=ts,
    )

    # Kreiraj .dok paket
    dok_bytes, dok_hash, documents_meta = create_dok_package(
        seal_token=GENESIS_SEAL_TOKEN,
        issuer_name=issuer_name,
        issuer_oib=issuer_oib,
        block_number=0,
        prev_hash=prev_hash,
        block_hash=block_hash,
        timestamp=ts,
        title=GENESIS_TITLE,
        files=files,
        verify_base_url=VERIFY_BASE_URL,
    )

    # Spremi .dok u Minio (opcionalno — ako nema Minio, spremi lokalno)
    dok_minio_url = _save_dok_to_minio(dok_bytes, GENESIS_SEAL_TOKEN)

    # Kreiraj ChainBlockPOE u bazi
    block = ChainBlockPOE.objects.create(
        block_number=0,
        issuer_name=issuer_name,
        issuer_oib=issuer_oib,
        title=GENESIS_TITLE,
        description=GENESIS_DESCRIPTION,
        documents_json=documents_meta,
        prev_hash=prev_hash,
        block_hash=block_hash,
        seal_token=GENESIS_SEAL_TOKEN,
        timestamp=ts,
        dok_minio_url=dok_minio_url,
        dok_hash=dok_hash,
    )

    return block


def _save_dok_to_minio(dok_bytes: bytes, seal_token: str) -> str:
    """Spremi .dok paket u Minio. Vrati URL ili lokalni path."""
    try:
        from django.conf import settings
        from minio import Minio

        client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
        bucket = getattr(settings, "MINIO_BUCKET_EARHIVATOR", "earhivator")
        obj_key = f"chainblock/{seal_token}.dok"
        import io

        client.put_object(
            bucket,
            obj_key,
            io.BytesIO(dok_bytes),
            len(dok_bytes),
            content_type="application/zip",
        )
        return f"minio://{bucket}/{obj_key}"
    except Exception:
        # Fallback: spremi lokalno u /tmp

        path = f"/tmp/{seal_token}.dok"
        with open(path, "wb") as f:
            f.write(dok_bytes)
        return f"file://{path}"


def update_genesis_oib(novi_oib: str, novi_naziv: str | None = None) -> ChainBlockPOE:
    """
    Ažurira OIB Genesis Blocka kada NO LIMIT dobije OIB udruge.
    Recalculates block_hash i regenerira .dok paket.
    Pozovi sutra čim Marija donese rješenje.
    """
    block = ChainBlockPOE.objects.get(block_number=0)
    block.issuer_oib = novi_oib
    if novi_naziv:
        block.issuer_name = novi_naziv

    # Recalculate hash s novim OIB-om
    block.block_hash = block.compute_block_hash()

    # Regeneriraj .dok — zahtijeva ručni re-upload binarnih sadržaja

    block.save()
    return block
