"""Spremnik slika dijelova: PRIJELAZNI lokalni direktorij izvan repoa, za test dok se ne spoji prava poslovna arhiva.

Slike dijelova pripadaju u poslovnu arhivu (ARHIVA 2030), iz nje se gradi webshop. U Krunicu (lanac) ne ide sadržaj slike,
nego samo atom s Merkle korijenom. Spajanje: `arhiva_core/ulaz.py: primi_dokument(db, sadrzaj, ime_datoteke, kreator,
tenant_id, app_id)` (asinkrono, traži kreatora i tenanta, ključ = weise3 od sadržaja i kreatora, readback prije retka).
Prije spajanja treba izmjeriti dvije stvari: što `resolver.put` radi dalje s dokumentom (replikacija) i kako se u arhivi
razlikuju privatne slike (tamni dio) od javnih (oglas). Sučelje ostaje isto: spremi(bajtovi) -> (sha256, ref), dohvati(ref).
Bez OTPAD_SLIKE spremnik ne postoji i učitavanje slika vraća 503 (nema slučajnog spremanja).
"""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

REF = re.compile(r"lokalno:([0-9a-f]{64})")


class LokalniSpremnik:
    def __init__(self, korijen: str):
        self.korijen = Path(korijen)
        self.korijen.mkdir(mode=0o700, parents=True, exist_ok=True)

    def _put(self, sha: str) -> Path:
        return self.korijen / sha[:2] / sha

    def spremi(self, sadrzaj: bytes) -> tuple[str, str]:
        sha = hashlib.sha256(sadrzaj).hexdigest()
        put = self._put(sha)
        if not put.exists():
            put.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            tmp = put.with_suffix(".tmp")
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(sadrzaj)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, put)
        if hashlib.sha256(put.read_bytes()).hexdigest() != sha:       # readback prije nego se redak stvori (Z48)
            raise RuntimeError("readback slike nije prošao")
        return sha, f"lokalno:{sha}"

    def dohvati(self, ref: str) -> bytes | None:
        m = REF.fullmatch(ref or "")
        if not m:
            return None
        put = self._put(m[1])
        return put.read_bytes() if put.exists() else None


def iz_okoline() -> LokalniSpremnik | None:
    k = os.environ.get("OTPAD_SLIKE", "").strip()
    return LokalniSpremnik(k) if k else None
