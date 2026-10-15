"""Spremnik slika dijelova u POSLOVNU ARHIVU flote (ARHIVA 2030) preko njezina web-API-ja.

Ugovor je pročitan iz koda (api/arhiva_core.py, services/arhiva_core/ulaz.py na EU), ne pogođen:
  POST {osnova}/api/v1/arhiva-core/upload-datoteka   multipart: datoteka (bajtovi), app_id;  Authorization: Bearer <sesija>
       202 JSON {weise3_id, ...}; weise3_id = hash sadržaja + kreatora (isti sadržaj = isti id, idempotentno);
       creator i tenant dolaze ISKLJUČIVO iz sesije (nikad iz zahtjeva)
  GET  {osnova}/api/v1/arhiva-core/{weise3_id}/original   sirovi bajtovi (traži sesiju istog tenanta)

OPREZ, trošak: svaki upload na SADAŠNJEM poslužitelju automatski pokreće obradu u pozadini (OCR, odvajanje podloge i DVA AI poziva).
Za fotografije dijelova to košta novac bez koristi. Zato se adapter uključuje TEK uz ARHIVA_BEZ_AI_POTVRDENO=1, a to smije
postaviti samo netko tko je potvrdio da je poslužitelj zakrpan da za app_id "kelava-dijelovi" preskače obradu
(vidi ../arhiva_spoj/PRIJEDLOG_upload_bez_ai.diff). Bez potvrde se odbija pokrenuti, ne šuti.
"""
from __future__ import annotations

import hashlib
import json
import re
import urllib.error
import urllib.request
import uuid

APP_ID = "kelava-dijelovi"
REF = re.compile(r"arhiva:([0-9a-f]{64})")
EKSTENZIJA = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


class SpremnikGreska(Exception):
    """Poruka je za radnicu (hrvatski); podaci NISU spremljeni."""


def _tip(b: bytes) -> str:
    if b[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        return "image/webp"
    return "application/octet-stream"


def _multipart(polja: dict, datoteka: tuple[str, str, bytes]) -> tuple[bytes, str]:
    granica = "----otpad" + uuid.uuid4().hex
    dijelovi = []
    for k, v in polja.items():
        dijelovi.append(f'--{granica}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    ime, tip, sadrzaj = datoteka
    dijelovi.append(f'--{granica}\r\nContent-Disposition: form-data; name="datoteka"; filename="{ime}"\r\n'
                    f'Content-Type: {tip}\r\n\r\n'.encode() + sadrzaj + b"\r\n")
    dijelovi.append(f"--{granica}--\r\n".encode())
    return b"".join(dijelovi), f"multipart/form-data; boundary={granica}"


class ArhivaSpremnik:
    PREFIKS = "arhiva:"

    def __init__(self, osnova: str, token: str, *, bez_ai_potvrdeno: bool, app_id: str = APP_ID, rok: int = 40):
        if not osnova or not token:
            raise ValueError("ARHIVA_URL i ARHIVA_TOKEN su obavezni")
        if not bez_ai_potvrdeno:
            raise ValueError("Arhiva se ne uključuje bez ARHIVA_BEZ_AI_POTVRDENO=1: svaki upload bi pokrenuo plaćenu AI obradu "
                             "(poslužitelj mora preskakati obradu za app_id " + app_id + ")")
        self.osnova, self.token, self.app_id, self.rok = osnova.rstrip("/"), token, app_id, rok

    def _zahtjev(self, metoda: str, put: str, tijelo: bytes | None = None, tip: str | None = None) -> tuple[int, bytes]:
        z = {"Authorization": "Bearer " + self.token, "User-Agent": "otpad-ekran/1"}
        if tip:
            z["Content-Type"] = tip
        r = urllib.request.Request(self.osnova + put, data=tijelo, method=metoda, headers=z)
        try:
            with urllib.request.urlopen(r, timeout=self.rok) as o:
                return o.status, o.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise SpremnikGreska("Arhiva trenutno nije dostupna. Slika nije spremljena, pokušaj ponovo za minutu.") from e

    @staticmethod
    def _poruka(kod: int, tijelo: bytes) -> str:
        if kod == 401:
            return "Prijava u arhivu je istekla ili nije valjana. Javi Ivanu; slika nije spremljena."
        if kod == 404:
            return "Arhiva ne nalazi dokument (ili ovaj korisnik nema pristup tom tenantu). Slika nije spremljena."
        if kod == 413:
            return "Slika je prevelika za arhivu."
        try:
            razlog = json.loads(tijelo).get("detail", "")
        except Exception:                                                        # noqa: BLE001
            razlog = ""
        return f"Arhiva je odbila sliku (šifra {kod}{': ' + str(razlog)[:80] if razlog else ''}). Slika nije spremljena."

    def spremi(self, sadrzaj: bytes) -> tuple[str, str]:
        sha = hashlib.sha256(sadrzaj).hexdigest()
        tip = _tip(sadrzaj)
        ime = f"dio-{sha[:12]}.{EKSTENZIJA.get(tip, 'bin')}"
        tijelo, ctype = _multipart({"app_id": self.app_id}, (ime, tip, sadrzaj))
        kod, odg = self._zahtjev("POST", "/api/v1/arhiva-core/upload-datoteka", tijelo, ctype)
        if kod not in (200, 201, 202):
            raise SpremnikGreska(self._poruka(kod, odg))
        try:
            w3 = json.loads(odg)["weise3_id"]
        except Exception as e:                                                   # noqa: BLE001
            raise SpremnikGreska("Arhiva je vratila neočekivan odgovor. Slika nije spremljena.") from e
        if not re.fullmatch(r"[0-9a-f]{64}", str(w3)):
            raise SpremnikGreska("Arhiva je vratila neispravan identifikator. Slika nije spremljena.")
        natrag = self.dohvati(f"arhiva:{w3}")                    # readback: bajt po bajt prije nego se redak stvori (Z48)
        if natrag != sadrzaj:
            raise SpremnikGreska("Provjera nakon spremanja u arhivu nije prošla (sadržaj se ne poklapa). Slika nije spremljena.")
        return sha, f"arhiva:{w3}"

    def dohvati(self, ref: str) -> bytes | None:
        m = REF.fullmatch(ref or "")
        if not m:
            return None
        kod, odg = self._zahtjev("GET", f"/api/v1/arhiva-core/{m[1]}/original")
        if kod == 404:
            return None
        if kod != 200:
            raise SpremnikGreska(self._poruka(kod, odg))
        return odg
