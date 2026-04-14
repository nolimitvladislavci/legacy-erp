"""
Fenix QR Code endpoint — server-side, potpisan, bez vanjskih servisa.

SIGURNOST:
  Svaki zahtjev mora imati HMAC potpis (sig parametar).
  Bez potpisa → 403. Onemogućuje open QR proxy zlouporabu.

  Interni URL: /qr/?data=URL&size=200&color=000000&bg=ffffff&sig=HMAC
  Generiranje URL-a: from core.qr_views import signed_qr_url
  Template tag: {% load qr_tags %} → {% qr_url data %}

GET /qr/?data=URL&size=200&color=000000&bg=ffffff&sig=HMAC
  data  — URL ili tekst (max 2048 znakova)
  size  — px dimenzija (default 200, max 1000)
  color — fill hex bez # (default 000000)
  bg    — background hex bez # (default ffffff)
  sig   — HMAC-SHA256 potpis (prvih 16 hex znakova)

Cachira 24h po kombinaciji parametara.
"""

import base64
import hashlib
import hmac
import io
import re

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_GET

MAX_SIZE = 1000
MAX_DATA = 2048
DEFAULT_SIZE = 200
# Rate limit: 120 QR generacija po IP-u na 60 sekundi
RATE_LIMIT = 120
RATE_WINDOW = 60


def _get_secret() -> bytes:
    secret = getattr(settings, "QR_HMAC_SECRET", "")
    if not secret:
        secret = settings.SECRET_KEY
    return secret.encode() if isinstance(secret, str) else secret


def _sign(data: str, size: int, color: str, bg: str) -> str:
    """Vrati prvih 16 hex znakova HMAC-SHA256 potpisa."""
    msg = f"{data}|{size}|{color}|{bg}".encode()
    return hmac.new(_get_secret(), msg, hashlib.sha256).hexdigest()[:16]


def signed_qr_url(data: str, size: int = 200, color: str = "000000", bg: str = "ffffff") -> str:
    """
    Vrati potpisan URL do QR endpointa.
    Jedina ispravna metoda za generiranje QR URL-a u platformi.

    Primjer:
        from core.qr_views import signed_qr_url
        url = signed_qr_url("https://limit-connect.com/hr/ponuda/UUID/", size=300)
    """
    from urllib.parse import urlencode

    sig = _sign(data, size, color, bg)
    return "/qr/?" + urlencode({"data": data, "size": size, "color": color, "bg": bg, "sig": sig})


def _hex_to_rgb(hex_str: str, default: tuple) -> tuple:
    h = re.sub(r"[^0-9a-fA-F]", "", str(hex_str))[:6]
    if len(h) != 6:
        return default
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _generate_png(data: str, size: int, fill: tuple, back: tuple, error_correction: str | None = None) -> bytes:
    import qrcode

    ec_map = {
        "H": qrcode.constants.ERROR_CORRECT_H,
        "Q": qrcode.constants.ERROR_CORRECT_Q,
        "M": qrcode.constants.ERROR_CORRECT_M,
        "L": qrcode.constants.ERROR_CORRECT_L,
    }
    ec = ec_map.get(error_correction, qrcode.constants.ERROR_CORRECT_M)
    box_size = max(1, size // 25)
    qr = qrcode.QRCode(
        version=None,
        error_correction=ec,
        box_size=box_size,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)
    fill_hex = "#{:02x}{:02x}{:02x}".format(*fill)
    back_hex = "#{:02x}{:02x}{:02x}".format(*back)
    img = qr.make_image(fill_color=fill_hex, back_color=back_hex)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@require_GET
@cache_control(max_age=86400, public=True)
def qr_code_view(request):
    data = request.GET.get("data", "").strip()
    if not data:
        return HttpResponseBadRequest("Missing 'data'")
    if len(data) > MAX_DATA:
        return HttpResponseBadRequest(f"'data' exceeds {MAX_DATA} chars")

    try:
        size = min(int(request.GET.get("size", DEFAULT_SIZE)), MAX_SIZE)
    except (ValueError, TypeError):
        size = DEFAULT_SIZE

    color_hex = re.sub(r"[^0-9a-fA-F]", "", request.GET.get("color", "000000"))[:6] or "000000"
    bg_hex = re.sub(r"[^0-9a-fA-F]", "", request.GET.get("bg", "ffffff"))[:6] or "ffffff"

    # Provjeri HMAC potpis
    sig_provided = request.GET.get("sig", "")
    sig_expected = _sign(data, size, color_hex, bg_hex)
    if not hmac.compare_digest(sig_provided, sig_expected):
        return HttpResponseForbidden("Invalid signature")

    # Rate limiting po IP-u
    ip = request.META.get("HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR", ""))[:45]
    rl_key = f"qr_rl_{ip}"
    count = cache.get(rl_key, 0)
    if count >= RATE_LIMIT:
        from django.http import HttpResponse as HR

        return HR("Rate limit exceeded", status=429)
    cache.set(rl_key, count + 1, RATE_WINDOW)

    # Cache po parametrima
    cache_key = "qr_" + hashlib.md5(f"{data}|{size}|{color_hex}|{bg_hex}".encode()).hexdigest()

    png_bytes = cache.get(cache_key)
    if png_bytes is None:
        fill = _hex_to_rgb(color_hex, (0, 0, 0))
        back = _hex_to_rgb(bg_hex, (255, 255, 255))
        png_bytes = _generate_png(data, size, fill, back)
        cache.set(cache_key, png_bytes, 60 * 60 * 24)

    return HttpResponse(png_bytes, content_type="image/png")


def qr_base64(
    data: str, size: int = 200, color: str = "000000", bg: str = "ffffff", error_correction: str | None = None
) -> str:
    """Base64 data URI — za PDF (WeasyPrint) i email inline.

    error_correction: None/"M" (default), "H" (FINA fiskalizacija), "Q", "L"
    """
    fill = _hex_to_rgb(color, (0, 0, 0))
    back = _hex_to_rgb(bg, (255, 255, 255))
    png_bytes = _generate_png(data, size, fill, back, error_correction=error_correction)
    return "data:image/png;base64," + base64.b64encode(png_bytes).decode()


def qr_png_bytes(
    data: str, size: int = 200, color: str = "000000", bg: str = "ffffff", error_correction: str | None = None
) -> bytes:
    """Raw PNG bytes — za HttpResponse views i file saves (npr. ImageField).

    error_correction: None/"M" (default), "H" (FINA), "Q", "L"
    """
    fill = _hex_to_rgb(color, (0, 0, 0))
    back = _hex_to_rgb(bg, (255, 255, 255))
    return _generate_png(data, size, fill, back, error_correction=error_correction)


def qr_svg_bytes(data: str, size: int = 200) -> bytes:
    """SVG bytes — za HttpResponse s content_type='image/svg+xml'."""
    import qrcode
    from qrcode.image.svg import SvgPathImage

    box_size = max(1, size // 25)
    qr = qrcode.QRCode(version=None, box_size=box_size, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(image_factory=SvgPathImage)
    buf = io.BytesIO()
    img.save(buf)
    return buf.getvalue()
