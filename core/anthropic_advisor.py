"""
Anthropic Advisor Strategy — LIMIT Connect integracija
======================================================
Haiku (executor) + Opus (advisor) pattern.

Objavljeno: 2026-04-09
Beta header: advisor-tool-2026-03-01

Dokumentacija:
  https://www.buildfastwithai.com/blogs/anthropic-advisor-strategy-claude-api

Opis:
  Haiku radi sve standardne zadatke.
  Kada naiđe na arhitekturalno kompleksan problem,
  može pozvati Opus (advisor) — max max_uses puta po requestu.
  Advisor tokeni → Opus cijena.
  Executor tokeni → Haiku cijena.

Primjena u LIMIT Connect:
  - Trojstvo: _haiku_analiza() — max_uses=2
  - Claude Doktor: _call_haiku() — max_uses=1
  - batch skripte: BEZ advisora (predrago, overkill)
"""
import logging
from typing import Optional

logger = logging.getLogger('anthropic_advisor')

HAIKU_MODEL = 'claude-haiku-4-5-20251001'
OPUS_MODEL  = 'claude-opus-4-6'
ADVISOR_BETA = 'advisor-tool-2026-03-01'


def haiku_with_advisor(
    messages: list,
    max_tokens: int = 1500,
    max_uses: int = 1,
    system: Optional[str] = None,
) -> str:
    """
    Pokreni Haiku s Opus advisorom.

    Args:
        messages:   Standardni Anthropic messages format
        max_tokens: Maksimalni output tokeni (default 1500)
        max_uses:   Koliko puta Haiku smije konzultirati Opus (default 1)
        system:     Opcionalni system prompt

    Returns:
        Tekst odgovora (str)

    Raises:
        Exception ako API poziv ne uspije
    """
    import anthropic
    from django.conf import settings

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    kwargs = dict(
        model=HAIKU_MODEL,
        max_tokens=max_tokens,
        betas=[ADVISOR_BETA],
        tools=[{
            'type': 'advisor_20260301',
            'name': 'advisor',
            'model': OPUS_MODEL,
            'max_uses': max_uses,
        }],
        messages=messages,
    )
    if system:
        kwargs['system'] = system

    try:
        resp = client.beta.messages.create(**kwargs)

        # Prikupi sve text blokove
        text_parts = [
            block.text
            for block in resp.content
            if hasattr(block, 'text')
        ]
        result = '\n'.join(text_parts).strip()

        # Log advisor usage
        advisor_used = any(
            getattr(block, 'type', '') == 'tool_use' and
            getattr(block, 'name', '') == 'advisor'
            for block in resp.content
        )
        if advisor_used:
            logger.info(
                'Advisor Strategy: Haiku konzultirao Opus | '
                'input=%s output=%s',
                resp.usage.input_tokens,
                resp.usage.output_tokens,
            )

        return result

    except (IntegrityError, DatabaseError) as e:
        logger.error('haiku_with_advisor greška: %s', e)
        raise
