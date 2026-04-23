"""
core/local_fallback.py — Lokalni fallback kad AI API nije dostupan

Pokriva:
  - OCR (Tesseract) za slike i PDF
  - Regex ekstrakcija za racune (iznos, datum, OIB, IBAN)
  - Rule-based NKD klasifikacija
  - Bookkeeping heuristike (konto, PDV)
  - Media processing (Pillow + FFmpeg)

Nula vanjskih API poziva. Radi offline.
"""
from __future__ import annotations
import re
import os
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("fenix.fallback")


@dataclass
class FallbackResult:
    success: bool
    method: str          # 'tesseract' | 'regex' | 'heuristic' | 'empty'
    text: str = ""
    data: dict = field(default_factory=dict)
    error: str = ""


# OCR -------------------------------------------------------------------------

def ocr_image(image_bytes: bytes, lang: str = "hrv+deu+eng") -> FallbackResult:
    """Tesseract OCR na slici. Vraca raw tekst."""
    try:
        import pytesseract
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(image_bytes))
        img = img.convert("L")  # grayscale za bolji OCR
        text = pytesseract.image_to_string(img, lang=lang, config="--psm 6")
        logger.info("Tesseract OCR: %d znakova", len(text))
        return FallbackResult(success=True, method="tesseract", text=text.strip())
    except Exception as e:
        logger.warning("Tesseract greska: %s", e)
        return FallbackResult(success=False, method="tesseract", error=str(e))


def ocr_pdf(pdf_bytes: bytes) -> FallbackResult:
    """pdfplumber za PDF tekst ekstrakciju. Fallback na pdf2image+tesseract."""
    try:
        import pdfplumber
        import io
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            pages = [p.extract_text() or "" for p in pdf.pages]
        text = "\n".join(pages).strip()
        if len(text) > 50:
            logger.info("pdfplumber: %d znakova iz %d stranica", len(text), len(pages))
            return FallbackResult(success=True, method="pdfplumber", text=text)
    except Exception as e:
        logger.warning("pdfplumber greska: %s", e)

    # Fallback: pdf2image + tesseract
    try:
        from pdf2image import convert_from_bytes
        import pytesseract
        images = convert_from_bytes(pdf_bytes, dpi=200, first_page=1, last_page=3)
        texts = [pytesseract.image_to_string(img, lang="hrv+deu+eng") for img in images]
        text = "\n".join(texts).strip()
        logger.info("pdf2image+tesseract: %d znakova", len(text))
        return FallbackResult(success=True, method="pdf2image_tesseract", text=text)
    except Exception as e:
        logger.error("PDF OCR fallback greska: %s", e)
        return FallbackResult(success=False, method="empty", error=str(e))


# REGEX EKSTRAKCIJA RACUNA ----------------------------------------------------

_AMOUNT_RE = re.compile(
    r"(?:EUR|HRK|USD|[€]|kn)?\s*"
    r"(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2}))"
    r"\s*(?:EUR|HRK|USD|[€]|kn)?",
    re.IGNORECASE,
)
_DATE_RE = re.compile(
    r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{4})\b"
    r"|\b(\d{4})[./-](\d{1,2})[./-](\d{1,2})\b"
)
_OIB_RE = re.compile(r"\b(?:OIB[:.\s]*)(\d{11})\b", re.IGNORECASE)
_IBAN_RE = re.compile(r"\b([A-Z]{2}\d{2}[A-Z0-9]{4,30})\b")
_INVOICE_NUM_RE = re.compile(
    r"\b(?:racun|invoice|rechnungs?(?:nr|nummer)?|r-|inv[-.]?)"
    r"[\s.:-]*([A-Z0-9/\-]{3,20})\b",
    re.IGNORECASE,
)


def _extract_vendor(text: str) -> str:
    lines = [l.strip() for l in text.split("\n") if l.strip() and len(l.strip()) > 3]
    for line in lines[:5]:
        if not re.match(r"^[\d./-]+$", line) and len(line) > 4:
            return line
    return ""


def parse_invoice_text(text: str) -> dict:
    """Parsira tekst racuna regex-om. Vraca iznos, datum, oib, iban, broj_racuna, dobavljac."""
    result = {}
    amounts = []
    for m in _AMOUNT_RE.finditer(text):
        raw = m.group(1).replace(".", "").replace(",", ".")
        try:
            amounts.append(float(raw))
        except ValueError:
            pass
    if amounts:
        result["iznos"] = max(amounts)
        result["iznos_str"] = f"{max(amounts):.2f}"

    date_match = _DATE_RE.search(text)
    if date_match:
        g = date_match.groups()
        if g[3]:
            result["datum"] = f"{g[3]}-{int(g[4]):02d}-{int(g[5]):02d}"
        else:
            result["datum"] = f"{g[2]}-{int(g[1]):02d}-{int(g[0]):02d}"

    oib_match = _OIB_RE.search(text)
    if oib_match:
        result["oib"] = oib_match.group(1)

    iban_match = _IBAN_RE.search(text)
    if iban_match:
        result["iban"] = iban_match.group(1)

    inv_match = _INVOICE_NUM_RE.search(text)
    if inv_match:
        result["broj_racuna"] = inv_match.group(1).strip()

    vendor = _extract_vendor(text)
    if vendor:
        result["dobavljac"] = vendor

    return result


# NKD KLASIFIKACIJA (rule-based) ----------------------------------------------

_NKD_KEYWORDS = {
    "47.11": ["supermarket", "konzum", "spar", "lidl", "kaufland", "prehrambeni", "namirnice"],
    "47.91": ["webshop", "online shop", "e-commerce", "amazon", "ebay"],
    "56.10": ["restoran", "kafic", "pizza", "burger", "catering", "ugostiteljstvo"],
    "49.39": ["prijevoz", "taxi", "uber", "bolt", "prijevoznik"],
    "62.01": ["softver", "razvoj", "programiranje", "IT", "web", "aplikacija"],
    "62.02": ["konzultant", "savjetovanje", "consulting", "IT usluge"],
    "69.20": ["racunovodstvo", "porezna", "revizija", "knjigovodstvo", "racunovoda"],
    "41.20": ["gradnja", "izgradnja", "adaptacija", "rekonstrukcija", "zidarski"],
    "45.20": ["auto servis", "auto radionica", "vulkanizer"],
    "86.21": ["lijecnik", "ordinacija", "klinika", "bolnica", "medicinska"],
    "68.20": ["najam", "zakup", "iznajmljivanje", "nekretnine", "stan"],
    "85.59": ["edukacija", "tecaj", "obuka", "trening", "kurs", "obrazovanje"],
}


def classify_nkd(text: str) -> dict:
    """Rule-based NKD klasifikacija."""
    text_lower = text.lower()
    scores: dict[str, int] = {}
    for nkd_code, keywords in _NKD_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw.lower() in text_lower)
        if score > 0:
            scores[nkd_code] = score
    if not scores:
        return {"nkd": "47.99", "naziv": "Ostala trgovina na malo", "confidence": "low", "method": "default"}
    best = max(scores, key=lambda k: scores[k])
    return {"nkd": best, "confidence": "high" if scores[best] >= 2 else "medium",
            "method": "keyword_match", "score": scores[best]}


# BOOKKEEPING HEURISTIKE ------------------------------------------------------

_KONTO_MAP = [
    (r"uredska oprema|namjestaj|racunalo|laptop|monitor", "0220", "Uredska oprema"),
    (r"gorivo|benzin|dizel|nafta|INA|PETROL", "3222", "Gorivo"),
    (r"telefon|mobitel|internet|telekom|A1|HT|Tele2", "3232", "Telekomunikacije"),
    (r"najam|zakup|renta|stanarina", "3211", "Najam"),
    (r"struja|elektricna|HEP|plin|komunaln", "3231", "Energija"),
    (r"osiguranje|polica", "3240", "Osiguranje"),
    (r"placa|neto placa|bruto|isplata place", "4000", "Place"),
    (r"PDV|porez na dodanu vrijednost", "1410", "PDV pretporez"),
    (r"reprezentaci|restoran|catering|ugostit", "3292", "Reprezentacija"),
    (r"prijevoz|taxi|bus|vlak|putni|dnevnica", "3252", "Putni troskovi"),
    (r"reklam|marketing|oglas", "3271", "Reklama i propaganda"),
    (r"uredski materijal|papir|toner|pisac", "3221", "Uredski materijal"),
    (r"savjetovanje|konzultant|uslug[ae]", "3299", "Ostale usluge"),
    (r"roba|materijal|inventar|zalihe", "3100", "Zalihe robe"),
]


def suggest_konto(text: str) -> dict:
    """Predlazi konto za knjizenje na temelju teksta racuna."""
    text_lower = text.lower()
    for pattern, konto, opis in _KONTO_MAP:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return {"konto": konto, "opis": opis, "method": "rule_based", "confidence": "medium"}
    return {"konto": "3299", "opis": "Ostale usluge", "method": "default", "confidence": "low"}


# MEDIA PROCESSING (Pillow + FFmpeg) ------------------------------------------

def process_image(
    image_bytes: bytes,
    max_width: int = 1920,
    max_height: int = 1080,
    quality: int = 85,
    output_format: str = "WEBP",
) -> Optional[bytes]:
    """Resize + compress sliku via Pillow. Vraca optimizirani WebP."""
    try:
        from PIL import Image, ImageOps
        import io
        img = Image.open(io.BytesIO(image_bytes))
        try:
            img = ImageOps.exif_transpose(img)
        except Exception:
            pass
        img.thumbnail((max_width, max_height), Image.LANCZOS)
        out = io.BytesIO()
        img.save(out, format=output_format, quality=quality, method=6)
        result = out.getvalue()
        ratio = len(result) / max(len(image_bytes), 1) * 100
        logger.info("Image compress: %dB -> %dB (%.0f%%)", len(image_bytes), len(result), ratio)
        return result
    except Exception as e:
        logger.error("Image processing greska: %s", e)
        return None


def process_video_ffmpeg(
    input_path: str,
    output_path: str,
    codec: str = "libx265",
    crf: int = 28,
    audio_codec: str = "aac",
    audio_bitrate: str = "128k",
) -> dict:
    """Transkodira video via FFmpeg subprocess."""
    import subprocess
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-c:v", codec, "-crf", str(crf),
        "-c:a", audio_codec, "-b:a", audio_bitrate,
        "-movflags", "+faststart",
        output_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=3600)
        if result.returncode != 0:
            err = result.stderr.decode()[-300:]
            logger.error("FFmpeg greska: %s", err)
            return {"success": False, "error": err}
        orig = os.path.getsize(input_path)
        out = os.path.getsize(output_path)
        logger.info("FFmpeg: %dMB -> %dMB (%.0f%%)", orig // 1048576, out // 1048576, out / orig * 100)
        return {"success": True, "output_path": output_path, "original_size": orig, "output_size": out}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "FFmpeg timeout (>1h)"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def extract_video_thumbnail(input_path: str, output_path: str, time_offset: str = "00:00:02") -> bool:
    """Ekstrahira thumbnail iz videa."""
    import subprocess
    cmd = ["ffmpeg", "-y", "-i", input_path, "-ss", time_offset, "-vframes", "1", output_path]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        return result.returncode == 0
    except Exception:
        return False


def process_audio_ffmpeg(
    input_path: str,
    output_path: str,
    codec: str = "libopus",
    bitrate: str = "64k",
) -> dict:
    """Normalizira i konvertira audio via FFmpeg (EBU R128)."""
    import subprocess
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-c:a", codec, "-b:a", bitrate,
        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
        output_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=600)
        if result.returncode != 0:
            return {"success": False, "error": result.stderr.decode()[-200:]}
        return {"success": True, "output_path": output_path}
    except Exception as e:
        return {"success": False, "error": str(e)}


# GLAVNI FALLBACK WRAPPER -----------------------------------------------------

def ai_with_fallback(ai_fn, fallback_fn, *args, fallback_label: str = "local", **kwargs):
    """
    Pokusaj AI fn, na gresci koristi lokalni fallback.

    Primjer:
        result = ai_with_fallback(
            lambda: gateway.ocr(image_bytes),
            lambda: ocr_image(image_bytes),
            fallback_label="tesseract"
        )
    """
    try:
        return ai_fn(*args, **kwargs)
    except Exception as e:
        logger.warning("AI nedostupan (%s), koristim fallback '%s'", e, fallback_label)
        return fallback_fn(*args, **kwargs)
