"""Lažna poslovna arhiva za TEST: oponaša ugovor pročitan iz api/arhiva_core.py (upload-datoteka, original), nije stvarna arhiva.

Što oponaša: Bearer sesija; creator iz sesije (weise3_id = sha256(sadržaj + '::' + token)), pa je upload idempotentan;
`ai_pokrenuto` broji upload-e za koje bi SADAŠNJI poslužitelj pokrenuo plaćenu AI obradu (app_id koji nije u bez_ai_app_ids).
Kvarovi za test: kvar = 'krivi_original' (readback ne štima), '500', '401'.
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
from email.parser import BytesParser
from email import policy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class LaznaArhiva:
    def __init__(self, token: str = "TESTSESIJA", bez_ai_app_ids=("kelava-dijelovi",), kvar: str | None = None):
        self.token, self.bez_ai, self.kvar = token, set(bez_ai_app_ids), kvar
        self.dokumenti: dict[str, tuple[bytes, str]] = {}
        self.ai_pokrenuto = 0
        self.zahtjevi: list[dict] = []
        arh = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _odgovor(self, kod, tijelo: bytes, tip="application/json"):
                self.send_response(kod); self.send_header("Content-Type", tip)
                self.send_header("Content-Length", str(len(tijelo))); self.end_headers(); self.wfile.write(tijelo)

            def _autoriziran(self):
                if arh.kvar == "401" or self.headers.get("Authorization") != "Bearer " + arh.token:
                    self._odgovor(401, json.dumps({"detail": "Prijava je istekla"}).encode()); return False
                if arh.kvar == "500":
                    self._odgovor(500, b'{"detail":"interna greska"}'); return False
                return True

            def do_POST(self):
                if self.path != "/api/v1/arhiva-core/upload-datoteka":
                    return self._odgovor(404, b"{}")
                if not self._autoriziran():
                    return
                n = int(self.headers.get("Content-Length") or 0)
                tijelo = self.rfile.read(n)
                poruka = BytesParser(policy=policy.default).parsebytes(
                    b"Content-Type: " + self.headers["Content-Type"].encode() + b"\r\n\r\n" + tijelo)
                polja, datoteka, ime = {}, None, ""
                for dio in poruka.iter_parts():
                    naziv = dio.get_param("name", header="content-disposition")
                    if naziv == "datoteka":
                        datoteka, ime = dio.get_payload(decode=True), dio.get_filename() or ""
                    else:
                        polja[naziv] = dio.get_content().strip() if dio.get_content_type() == "text/plain" else ""
                if not datoteka:
                    return self._odgovor(422, json.dumps({"detail": "Prazna datoteka"}).encode())
                w3 = hashlib.sha256(datoteka + b"::" + arh.token.encode()).hexdigest()
                arh.dokumenti[w3] = (datoteka, ime.rsplit(".", 1)[-1] if "." in ime else "")
                arh.zahtjevi.append({"app_id": polja.get("app_id"), "ime": ime, "velicina": len(datoteka)})
                if polja.get("app_id") not in arh.bez_ai:
                    arh.ai_pokrenuto += 1
                self._odgovor(202, json.dumps({"weise3_id": w3, "app_id": polja.get("app_id"), "ai_status": "pending"}).encode())

            def do_GET(self):
                m = re.fullmatch(r"/api/v1/arhiva-core/([0-9a-f]{64})/original", self.path)
                if not m:
                    return self._odgovor(404, b"{}")
                if not self._autoriziran():
                    return
                dok = arh.dokumenti.get(m[1])
                if dok is None:
                    return self._odgovor(404, json.dumps({"detail": "Dokument nije pronađen"}).encode())
                b = dok[0] + (b"x" if arh.kvar == "krivi_original" else b"")
                self._odgovor(200, b, {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(dok[1], "application/octet-stream"))

        self._srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self._srv.server_address[1]}"
        self._t = threading.Thread(target=self._srv.serve_forever, daemon=True)

    def start(self):
        self._t.start(); return self

    def stop(self):
        self._srv.shutdown(); self._srv.server_close()
