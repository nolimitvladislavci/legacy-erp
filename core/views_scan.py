"""
core/views_scan.py — FenixScan: Univerzalni AI Document Scanner

Jedan endpoint za sve module:
  - ring      : prsten goluba (N slika → cross-reference)
  - golub     : foto goluba → ime + boja
  - id_card   : osobna iskaznica / putovnica (MRZ + vizualni podaci)
  - invoice   : račun (broj, datum, iznos, dobavljač)
  - complaint : knjiga prigovora / utisaka
  - general   : opće prepoznavanje

POST /api/fenix/scan/
Body: {
    "doc_type": "ring|golub|id_card|invoice|complaint|general",
    "images":   ["<b64_jpeg>", ...],   # 1-5 slika
    "context":  {}                      # opcijalni kontekst
}
Response: {
    "fields":     { ... },   # ekstrakcija ovisna o doc_type
    "confidence": 0.0-1.0,
    "doc_type":   "ring",
    "images_used": 2,
    "warning":    null | "..."
}
"""

import json
import logging
import os
import re

from django.http import JsonResponse
from django.views.decorators.http import require_POST

logger = logging.getLogger("borg.scan")

# ─── Anthropic size limit: 5MB decoded → ~3.7MB b64 ──────────────────────────
MAX_B64_BYTES = 3_700_000
MAX_IMAGES = 5

# ─── Prompts po tipu dokumenta ────────────────────────────────────────────────
PROMPTS = {
    "ring": """\
Prikazano je {n} fotografij{suffix} prstena goluba trkača.
Pogledi SVE slike i pokuši pročitati broj prstena.
Tipični formati: HR-YYYY-NNNNN | CRO YYYY NNNNN | HOG YYYY NNNNN | LOK oznaka.
Ako su slike različitih kutova istog prstena — koristi sve za veću točnost.
Odgovori ISKLJUČIVO JSON, nula komentara:
{{"prsten_broj":"HR-2026-12345","godina":"2026","confidence":0.92}}
Ako nisi siguran, smanji confidence. Ispod 0.35 = prsten_broj vrati prazan string.""",
    "golub": """\
Prikazano je {n} fotografij{suffix} goluba trkača (racing pigeon).
Predloži ime i opiši boju.
Ime: snažno, hrvatsko (Vihor, Munja, Oluja, Srebrni, Planinar, Stijela, Zorko, Grom, Sjever, Zora, Ponoć, Talac).
boja_kod MORA biti jedan od: siv | bijel | crn | smed | plav | crven | zut | sareno | ostalo
Odgovori ISKLJUČIVO JSON:
{{"ime":"Vihor","opis_boje":"siv s bijelim krilnim perima","boja_kod":"siv","confidence":0.88}}""",
    "id_card": """\
Prikazano je {n} fotografij{suffix} dokumenta (osobna iskaznica, putovnica, vozačka dozvola).
Ako imaš prednju I stražnju stranu — koristi obje.
Pročitaj MRZ (Machine Readable Zone) I vidljive podatke.
Odgovori ISKLJUČIVO JSON:
{{
  "doc_type": "id_card|passport|driving_license",
  "ime": "IVAN",
  "prezime": "HORVAT",
  "datum_rodjenja": "1990-05-15",
  "spol": "M|F",
  "broj_dokumenta": "012345678",
  "nacionalnost": "HRV",
  "vrijedi_do": "2030-05-15",
  "issuing_country": "HRV",
  "confidence": 0.95
}}
Polja koja ne možeš pročitati postavi na null.""",
    "invoice": """\
Prikazano je {n} fotografij{suffix} računa / dokumenta.
Ako je više strana istog računa — objedini podatke.
Odgovori ISKLJUČIVO JSON:
{{
  "broj_racuna": "IR-2026-001",
  "datum": "2026-01-15",
  "dobavljac": "Naziv tvrtke d.o.o.",
  "oib_dobavljac": "12345678901",
  "iznos_bez_pdv": 100.00,
  "pdv_iznos": 25.00,
  "iznos_ukupno": 125.00,
  "valuta": "EUR",
  "opis": "kratki opis usluge/robe",
  "iban": "HR...",
  "confidence": 0.90
}}
Brojeve uvijek kao decimale. Polja koja ne vidiš: null.""",
    "complaint": """\
Prikazano je {n} fotografij{suffix} stranice iz knjige prigovora ili knjige utisaka.
Pročitaj tekst rukopisa ili tiskanog teksta.
Odgovori ISKLJUČIVO JSON:
{{
  "vrsta": "prigovor|utisak|pohvala|prijedlog",
  "tekst": "puni tekst koji si pročitao",
  "datum": "YYYY-MM-DD ili null",
  "ime_posjetitelja": "ili null",
  "kategorija": "hrana|usluga|čistoća|cijena|osoblje|ostalo",
  "sentiment": "pozitivan|neutralan|negativan",
  "confidence": 0.85
}}""",
    "azil_zivotinja": """Prikazano je {n} fotografij{suffix} napustene zivotinje pronasene u terenu ili dovedene u skloniste.
Procijeni sto vidis i popuni polja. Budi konkretan ali oprezan - reci PROCJENA ako nisi siguran.
Chip broj CITAJ ISKLJUCIVO s naljepnice/dokumenta (ne skeniras implantirani chip).
Odgovori ISKLJUCIVO JSON:
{{
  "vrsta": "pas|macka|kunic|ptica|ostalo",
  "naziv_pasmina": "procjena pasmine ili null",
  "spol": "M|Z|N",
  "dob_procjena": "npr. 2-3 godine (procjena)",
  "boja_opis": "detaljan opis boje i sare dlake",
  "mikrocip": "15-znamenkasti broj s dokumenta ili null",
  "vidljive_ozljede": "opis vidljivih ozljeda ili null",
  "napomena_ulaz": "kratki opis situacije pronalaska",
  "confidence": 0.80
}}
Polja koja ne mozes procijeniti postavi na null.""",
    "pas": """\
Prikazano je {n} fotografij{suffix} psa.
Procijeni pasminu, boju, spol i dob. Budi konkretan.
spol: "M" za muzjaka, "F" za zenku, "N" ako nije vidljivo.
boja_kod: jedan od: crn|bijel|siv|smed|zlatni|sareno|crvenkast|krem|ostalo
Odgovori ISKLJUCIVO JSON:
{"pasmina":"Njemacki ovcar","boja_opis":"crno-smedi sa standardnim sarama","boja_kod":"sareno","spol":"M","dob_procjena":"2-3 godine","ime_prijedlog":"Rex","confidence":0.88}
Polja koja ne mozes procijeniti postavi na null.""",
    "general": """\
Prikazano je {n} fotografij{suffix} dokumenta ili predmeta.
Izvuci sve relevantne tekstualne i vizualne informacije.
Odgovori ISKLJUČIVO JSON s poljem "podaci" (objekt s ekstrahiranim ključ-vrijednost parovima) i "opis" (1-2 rečenice):
{{"podaci":{{}},"opis":"...","confidence":0.8}}""",
}


def _suffix(n):
    if n == 1:
        return "a"
    if n in (2, 3, 4):
        return "e"
    return "a"


def _validate_images(raw_list):
    """Validira i filtrira slike. Vraća (valid_list, warning|None)."""
    valid = []
    skipped = 0
    for raw in raw_list[:MAX_IMAGES]:
        b64 = raw.strip() if raw else ""
        if not b64:
            continue
        size = len(b64) * 3 // 4
        if size > MAX_B64_BYTES:
            skipped += 1
            logger.warning("scan: slika %dKB prevelika, preskačem", size // 1024)
            continue
        valid.append(b64)
    warning = None
    if skipped:
        warning = f"{skipped} slika preskočeno (prevelike). Koristi resize na frontendu."
    return valid, warning


def _build_content(images, doc_type):
    """Gradi Anthropic content array: slike + prompt."""
    content = []
    for b64 in images:
        content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": b64,
                },
            }
        )
    n = len(images)
    prompt_tpl = PROMPTS.get(doc_type, PROMPTS["general"])
    prompt = prompt_tpl.format(n=n, suffix=_suffix(n))
    content.append({"type": "text", "text": prompt})
    return content


def _call_anthropic(content, max_tokens=300):
    import anthropic as ant

    client = ant.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    response = client.messages.create(
        model=os.environ.get("HAIKU_MODEL", "claude-3-5-haiku-20241022"),
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": content}],
    )
    return response.content[0].text.strip()


def _parse_json(raw):
    m = re.search(r"\{[\s\S]*\}", raw)
    if m:
        return json.loads(m.group(0))
    raise ValueError(f"Nema JSON u odgovoru: {raw[:100]}")


def _post_process(fields, doc_type):
    """Normalizacije per doc_type."""
    if doc_type == "ring":
        conf = float(fields.get("confidence", 0))
        if conf < 0.35:
            fields["prsten_broj"] = ""
    if doc_type == "id_card":
        nat = fields.get("nacionalnost", "")
        if nat == "HRC":
            fields["nacionalnost"] = "HRV"
    if doc_type == "azil_zivotinja":
        # Normaliziraj chip — samo brojevi, 15 znakova
        chip = str(fields.get("mikrocip") or "").strip().replace(" ", "")
        fields["mikrocip"] = chip if len(chip) == 15 and chip.isdigit() else ""
        # Spol: osiguraj M/Z/N
        spol = str(fields.get("spol") or "N").upper()[:1]
        fields["spol"] = spol if spol in ("M", "Z") else "N"
    return fields


@require_POST
def fenix_scan(request):
    """
    POST /api/fenix/scan/
    Universalni AI Document Scanner.
    """
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Prijava potrebna"}, status=401)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Neispravan JSON"}, status=400)

    doc_type = data.get("doc_type", "general").strip()
    if doc_type not in PROMPTS:
        doc_type = "general"

    raw_images = data.get("images", [])
    if not isinstance(raw_images, list):
        raw_images = [raw_images]

    images, warning = _validate_images(raw_images)

    if not images:
        return JsonResponse(
            {
                "error": "Nema valjanih slika. Slike su ili prevelike ili nisu proslijeđene.",
                "hint": "Koristi FenixScan.resize() — max 1200px, JPEG 0.82",
            },
            status=400,
        )

    try:
        # Broj tokena ovisno o tipu
        max_tok = 400 if doc_type in ("invoice", "id_card", "complaint") else 250
        content = _build_content(images, doc_type)
        raw = _call_anthropic(content, max_tokens=max_tok)
        fields = _parse_json(raw)
        fields = _post_process(fields, doc_type)

        confidence = float(fields.get("confidence", 0.5))

        logger.info("fenix_scan [%s] %d slika → conf=%.2f user=%s", doc_type, len(images), confidence, request.user)

        return JsonResponse(
            {
                "ok": True,
                "doc_type": doc_type,
                "fields": fields,
                "confidence": confidence,
                "images_used": len(images),
                "warning": warning,
            }
        )

    except json.JSONDecodeError as e:
        logger.error("scan JSON parse error: %s", e)
        return JsonResponse({"error": "AI nije vratio valjan JSON. Pokušaj ponovo."}, status=502)
    except (ValueError, TypeError) as e:
        logger.error("fenix_scan error [%s]: %s", doc_type, e, exc_info=True)
        return JsonResponse({"error": str(e)[:200]}, status=500)
