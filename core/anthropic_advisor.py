"""
Anthropic — LIMIT Connect AI pozivi
=====================================
COST CONTROL: 2026-04-17
Opus advisor pattern UGAŠEN — trošio $80+/dan.
Sve ide kroz Haiku. Sonnet samo kad je eksplicitno zatražen.
Opus = ZABRANJEN u produkciji.

Cijene (za referencu):
  Haiku 4.5:  $0.80/$4.00 per MTok (in/out)
  Sonnet 4.6: $3.00/$15.00 per MTok
  Opus 4.6:   $15.00/$75.00 per MTok  ← 20x skuplje od Haiku
"""

import logging
from typing import Optional

logger = logging.getLogger("anthropic_advisor")

HAIKU_MODEL  = "claude-3-5-haiku-20241022"
SONNET_MODEL = "claude-3-5-haiku-20241022"  # COST CONTROL 2026-04-17: downgrade dok API billing nije pod kontrolom
# OPUS_MODEL je namjerno uklonjen — ne koristiti u produkciji


def haiku_with_advisor(
    messages: list,
    max_tokens: int = 1500,
    max_uses: int = 1,   # parametar zadržan radi kompatibilnosti, ignorira se
    system: Optional[str] = None,
) -> str:
    """
    Zamjena za stari Haiku+Opus advisor pattern.
    Sada koristi samo Haiku — identično sučelje, 20x jeftiniji.
    """
    import anthropic
    from django.conf import settings

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    kwargs = dict(
        model=HAIKU_MODEL,
        max_tokens=max_tokens,
        messages=messages,
    )
    if system:
        kwargs["system"] = system

    try:
        resp = client.messages.create(**kwargs)
        text_parts = [b.text for b in resp.content if hasattr(b, "text") and b.text]
        result = "\n".join(text_parts).strip()
        logger.debug("Haiku poziv | in=%s out=%s", resp.usage.input_tokens, resp.usage.output_tokens)
        return result
    except Exception as e:
        logger.error("haiku_with_advisor greška: %s", e)
        raise


def call_sonnet(
    messages: list,
    max_tokens: int = 2000,
    system: Optional[str] = None,
) -> str:
    """
    Sonnet — samo za eksplicitno kompleksne zadatke.
    Ne koristiti u Celery taskovima koji se ponavljaju.
    """
    import anthropic
    from django.conf import settings

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    kwargs = dict(model=SONNET_MODEL, max_tokens=max_tokens, messages=messages)
    if system:
        kwargs["system"] = system

    try:
        resp = client.messages.create(**kwargs)
        text_parts = [b.text for b in resp.content if hasattr(b, "text") and b.text]
        return "\n".join(text_parts).strip()
    except Exception as e:
        logger.error("call_sonnet greška: %s", e)
        raise
