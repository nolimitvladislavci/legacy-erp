"""
Fenix QR Code endpoint — server-side generacija, bez vanjskih servisa.

GET /qr/?data=URL&size=200&color=000000&bg=ffffff
  data  — URL ili tekst (obavezno)
  size  — px dimenzija (default 200, max 1000)
  color — fill hex bez # (default 000000)
  bg    — background hex bez # (default ffffff)

Cachira 24h po kombinaciji parametara.
"""

import base64
import hashlib
import io
import re

from django.core.cache import cache
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_GET

MAX_SIZE = 1000
DEFAULT_SIZE = 200


def _hex_to_rgb(hex_str: str, default: tuple) -> tuple:
    h = re.sub(r"[^0-9a-fA-F]", "", str(hex_str))[:6]
    if len(h) != 6:
        return default
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _generate_png(data: str, size: int, fill: tuple, back: tuple) -> bytes:
    import qrcode

    box_size = max(1, size // 25)
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)
    # PIL factory — jedina pouzdana bez PyPNG
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
        return HttpResponseBadRequest("Missing 'data' parameter")

    try:
        size = min(int(request.GET.get("size", DEFAULT_SIZE)), MAX_SIZE)
    except (ValueError, TypeError):
        size = DEFAULT_SIZE

    color_hex = request.GET.get("color", "000000")
    bg_hex = request.GET.get("bg", "ffffff")
    fill = _hex_to_rgb(color_hex, (0, 0, 0))
    back = _hex_to_rgb(bg_hex, (255, 255, 255))

    cache_key = "qr_" + hashlib.md5(f"{data}|{size}|{color_hex}|{bg_hex}".encode()).hexdigest()

    png_bytes = cache.get(cache_key)
    if png_bytes is None:
        png_bytes = _generate_png(data, size, fill, back)
        cache.set(cache_key, png_bytes, 60 * 60 * 24)

    return HttpResponse(png_bytes, content_type="image/png")


def qr_base64(data: str, size: int = 200, color: str = "000000", bg: str = "ffffff") -> str:
    """Base64 data URI — za PDF (WeasyPrint) i email inline."""
    fill = _hex_to_rgb(color, (0, 0, 0))
    back = _hex_to_rgb(bg, (255, 255, 255))
    png_bytes = _generate_png(data, size, fill, back)
    return "data:image/png;base64," + base64.b64encode(png_bytes).decode()
