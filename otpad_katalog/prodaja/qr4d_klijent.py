"""Klijent za postojeći servis flote `qr4d` (EU :8120, javno na genesis.limit-connect.com).

Ne crta ništa sam (Ustav §8: nema dupliciranja u floti). Šalje JSON na POST /api/v1/qr4d/uplatnica i
vraća PNG koji servis izradi (HUB3 PDF417 za hrvatske račune, EPC/GiroCode za ostale IBAN-e).
Servis sam čita sliku natrag i javlja X-Provjera = DRZI | PAD | NEPOZNATO; mi to samo prenosimo.
Non-custodial: kod nosi IBAN primatelja, novac ne prolazi kroz nas. Servis ništa ne sprema.
"""
from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.request

OSNOVA = os.environ.get("QR4D_URL", "https://genesis.limit-connect.com").rstrip("/")


class Qr4dNedostupan(Exception):
    """Servis nije odgovorio ili je javio grešku: stanje je NEPOZNATO, nikad 'uspjelo'."""


def uplatnica(primatelj: str, iban: str, iznos_centi: int, opis: str, *, oblik: str = "hub3",
              model: str = "HR99", poziv: str = "", adresa: str = "", mjesto: str = "",
              osnova: str | None = None, rok: int = 30) -> dict:
    """-> {"png": bytes, "provjera": "DRZI|PAD|NEPOZNATO", "oblik": str, "sha256": str}.
    Iznos ide kao niz "12,50" jer ga servis tako čita (zarez = decimalni)."""
    if iznos_centi <= 0:
        raise ValueError("iznos mora biti veći od 0")
    tijelo = {
        "oblik": oblik, "primatelj": primatelj, "iban": iban,
        "iznos": f"{iznos_centi // 100},{iznos_centi % 100:02d}",
        "opis": opis, "model": model, "poziv": poziv, "adresa": adresa, "mjesto": mjesto,
    }
    req = urllib.request.Request((osnova or OSNOVA) + "/api/v1/qr4d/uplatnica",
                                 data=json.dumps(tijelo).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=rok) as o:
            png = o.read()
            provjera = o.headers.get("X-Provjera", "NEPOZNATO")
            stvarni_oblik = o.headers.get("X-Oblik", oblik)
    except urllib.error.HTTPError as e:
        try:
            razlog = json.loads(e.read()).get("detail", "")
        except Exception:                                    # noqa: BLE001
            razlog = ""
        raise Qr4dNedostupan(f"qr4d HTTP {e.code}: {razlog}") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise Qr4dNedostupan(f"qr4d nedostupan: {e}") from e
    if not png.startswith(b"\x89PNG"):
        raise Qr4dNedostupan("qr4d nije vratio PNG")
    return {"png": png, "provjera": provjera, "oblik": stvarni_oblik, "sha256": hashlib.sha256(png).hexdigest()}
