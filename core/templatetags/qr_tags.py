"""
Fenix QR template tagovi.

Upotreba:
  {% load qr_tags %}

  <!-- URL za <img src> -->
  <img src="{% qr_url data %}" width="200" height="200" alt="QR">
  <img src="{% qr_url data size=300 color="c9a84c" bg="0a0a0a" %}" alt="QR">

  <!-- Direktno <img> element -->
  {% qr_img data size=200 alt="QR kod" class="my-class" %}

  <!-- Base64 za PDF/email (WeasyPrint) -->
  <img src="{% qr_b64 data size=150 %}">
"""

from django import template
from django.utils.html import format_html

register = template.Library()


@register.simple_tag
def qr_url(data: str, size: int = 200, color: str = "000000", bg: str = "ffffff") -> str:
    """Vrati URL do QR endpoint-a."""
    from urllib.parse import urlencode

    params = urlencode({"data": data, "size": size, "color": color, "bg": bg})
    return f"/qr/?{params}"


@register.simple_tag
def qr_img(
    data: str, size: int = 200, color: str = "000000", bg: str = "ffffff", alt: str = "QR", css_class: str = ""
) -> str:
    """Vrati kompletan <img> tag za QR kod."""
    from urllib.parse import urlencode

    params = urlencode({"data": data, "size": size, "color": color, "bg": bg})
    url = f"/qr/?{params}"
    return format_html(
        '<img src="{}" width="{}" height="{}" alt="{}" class="{}" loading="lazy">',
        url,
        size,
        size,
        alt,
        css_class,
    )


@register.simple_tag
def qr_b64(data: str, size: int = 200, color: str = "000000", bg: str = "ffffff") -> str:
    """Vrati base64 data URI za PDF/email gdje relativan URL ne radi."""
    from core.qr_views import qr_base64

    return qr_base64(data, size=size, color=color, bg=bg)
