"""
core/templatetags/fenix_ai.py — AI vidljivost za korisnike

Korištenje:
    {% load fenix_ai %}
    {% ai_badge "Proknjiženo" confidence=98 %}
    {% ai_badge "Klasificirano" model="Haiku" review_url="/ai/actions/42/" %}
    {% ai_status_pill "done" %}
    {% ai_summary_widget company=company limit=5 %}
"""
from django import template
from django.utils.html import format_html, mark_safe
from django.utils.timesince import timesince

register = template.Library()


@register.simple_tag
def ai_badge(action, confidence=None, model=None, review_url=None):
    """
    Inline badge: 🤖 Proknjiženo od BORG AI (98%) [Revidiraj]
    """
    conf_html = ""
    if confidence is not None:
        conf_html = format_html(
            ' <span style="font-weight:700;opacity:.85;">({}%)</span>', confidence
        )

    review_html = ""
    if review_url:
        review_html = format_html(
            ' <a href="{}" style="color:inherit;opacity:.7;text-decoration:underline;'
            'font-size:.65rem;margin-left:.3rem;">Revidiraj</a>',
            review_url,
        )

    model_name = model or "BORG AI"

    return format_html(
        '<span class="fenix-ai-action" title="Automatska AI akcija">'
        '<span style="font-size:.8rem;">&#x1F916;</span>'
        '&nbsp;{} &middot; <em style="font-style:normal;opacity:.75;">{}</em>'
        "{}{}"
        "</span>",
        action,
        model_name,
        conf_html,
        review_html,
    )


@register.simple_tag
def ai_status_pill(status):
    """
    Status pill: pending | processing | done | failed
    """
    cfg = {
        "pending":    ("&#x23F3;", "rgba(245,158,11,.12)", "#d97706"),
        "processing": ("&#x2699;",  "rgba(59,130,246,.12)", "#2563eb"),
        "done":       ("&#x2713;",  "rgba(34,197,94,.12)",  "#16a34a"),
        "failed":     ("&#x2717;",  "rgba(239,68,68,.12)",  "#dc2626"),
    }
    icon, bg, color = cfg.get(status, cfg["pending"])
    return format_html(
        '<span style="background:{};color:{};padding:.15rem .55rem;'
        "border-radius:12px;font-size:.7rem;font-weight:600;"
        'display:inline-flex;align-items:center;gap:.25rem;">'
        "{} {}</span>",
        bg, color, mark_safe(icon), status,
    )


@register.inclusion_tag("ai_assistant/partials/ai_activity_widget.html", takes_context=True)
def ai_summary_widget(context, company=None, limit=5, source_object=None):
    """
    Prikazuje zadnjih N AI akcija za kompaniju.

    {% ai_summary_widget company=company limit=5 %}
    {% ai_summary_widget company=company source_object="Invoice #123" limit=3 %}
    """
    from limit_connect_ai.models_ai_action import AIAction

    comp = company or context.get("company")
    if not comp:
        return {"actions": [], "unreviewed": 0}

    qs = AIAction.objects.filter(company=comp).order_by("-created_at")
    if source_object:
        qs = qs.filter(source_object__icontains=source_object)

    actions = list(qs[:limit])
    unreviewed = AIAction.objects.filter(company=comp, is_reviewed=False).count()

    return {
        "actions": actions,
        "unreviewed": unreviewed,
        "request": context.get("request"),
    }


@register.filter
def ai_confidence_color(confidence):
    """{{ action.confidence|ai_confidence_color }}"""
    if confidence is None:
        return "#6b7280"
    if confidence >= 95:
        return "#16a34a"
    if confidence >= 80:
        return "#d97706"
    return "#dc2626"


@register.simple_tag
def ai_inline_note(text, icon="🤖"):
    """
    Mala napomena ispod polja: "🤖 Auto-detektirano"
    {% ai_inline_note "Auto-detektirano iz OIB-a" %}
    """
    return format_html(
        '<small style="color:#7c3aed;font-size:.72rem;display:block;margin-top:.2rem;">'
        "{} {}</small>",
        icon, text,
    )
