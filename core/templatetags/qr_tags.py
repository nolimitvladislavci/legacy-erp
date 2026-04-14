"""
Fenix QR template tagovi — sve URL-ove potpisuje automatski.

{% load qr_tags %}
<img src="{% qr_url data %}" width="200">
<img src="{% qr_url data size=300 color="c9a84c" bg="0a0a0a" %}">
{% qr_img data size=200 alt="QR" %}
<img src="{% qr_b64 data %}">  {# PDF/email #}
"""

from django import template
from django.utils.html import format_html

register = template.Library()


@register.simple_tag
def qr_url(data: str, size: int = 200, color: str = "000000", bg: str = "ffffff") -> str:
    from core.qr_views import signed_qr_url

    return signed_qr_url(str(data), size=size, color=color, bg=bg)


@register.simple_tag
def qr_img(
    data: str, size: int = 200, color: str = "000000", bg: str = "ffffff", alt: str = "QR", css_class: str = ""
) -> str:
    from core.qr_views import signed_qr_url

    url = signed_qr_url(str(data), size=size, color=color, bg=bg)
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
    from core.qr_views import qr_base64

    return qr_base64(str(data), size=size, color=color, bg=bg)
