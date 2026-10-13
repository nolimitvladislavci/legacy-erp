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
    PREFIKS = "lokalno:"

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


class Spremnici:
    """Primarni spremnik za NOVE slike; dohvat ide po prefiksu refa, pa stare lokalne slike ostaju čitljive."""

    def __init__(self, primarni, svi):
        self.primarni, self.svi = primarni, [x for x in svi if x is not None]

    def spremi(self, sadrzaj: bytes) -> tuple[str, str]:
        return self.primarni.spremi(sadrzaj)

    def dohvati(self, ref: str) -> bytes | None:
        for x in self.svi:
            if (ref or "").startswith(x.PREFIKS):
                return x.dohvati(ref)
        return None

    def opis(self) -> str:
        return type(self.primarni).__name__


def iz_okoline() -> Spremnici | None:
    """OTPAD_SLIKE (lokalno, prijelazno) i/ili ARHIVA_URL + ARHIVA_TOKEN + ARHIVA_BEZ_AI_POTVRDENO=1 (poslovna arhiva).
    Ako su oba, nove slike idu u arhivu, a stare lokalne ostaju čitljive. Pogrešna postavka arhive baca ValueError (server ne starta)."""
    k = os.environ.get("OTPAD_SLIKE", "").strip()
    lokalni = LokalniSpremnik(k) if k else None
    arhiva = None
    if os.environ.get("ARHIVA_URL") or os.environ.get("ARHIVA_TOKEN"):
        from arhiva_spremnik import ArhivaSpremnik
        arhiva = ArhivaSpremnik(os.environ.get("ARHIVA_URL", ""), os.environ.get("ARHIVA_TOKEN", ""),
                                bez_ai_potvrdeno=os.environ.get("ARHIVA_BEZ_AI_POTVRDENO") == "1")
    primarni = arhiva or lokalni
    return Spremnici(primarni, [arhiva, lokalni]) if primarni else None
