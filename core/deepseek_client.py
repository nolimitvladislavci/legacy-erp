"""
DeepSeek via AWS Bedrock — GDPR compliant (eu-central-1).
Koristi se umjesto direktnog DeepSeek API-ja.

Konfiguracija u .env:
  AWS_ACCESS_KEY_ID=AKIA...
  AWS_SECRET_ACCESS_KEY=...
  AWS_BEDROCK_REGION=eu-central-1
  DEEPSEEK_MODEL_ID=deepseek-v3-2  (provjeriti točan ID u Bedrocku)
"""

import logging

from django.conf import settings

logger = logging.getLogger(__name__)

# Model ID-ovi (verificirati u AWS Bedrock katalog)
DEEPSEEK_V3_MODEL = getattr(settings, "DEEPSEEK_MODEL_ID", "deepseek-v3-2")
DEEPSEEK_SPECIALE_MODEL = getattr(settings, "DEEPSEEK_SPECIALE_MODEL_ID", "deepseek-v3-2-speciale")


def _get_bedrock_client():
    """Vrati boto3 Bedrock Runtime klijent za eu-central-1."""
    try:
        import boto3

        return boto3.client(
            service_name="bedrock-runtime",
            region_name=getattr(settings, "AWS_BEDROCK_REGION", "eu-central-1"),
            aws_access_key_id=getattr(settings, "AWS_ACCESS_KEY_ID", ""),
            aws_secret_access_key=getattr(settings, "AWS_SECRET_ACCESS_KEY", ""),
        )
    except ImportError:
        raise RuntimeError("boto3 nije instaliran: pip install boto3")


def deepseek_chat(
    prompt: str,
    model: str = DEEPSEEK_V3_MODEL,
    max_tokens: int = 1000,
    system: str = "",
    temperature: float = 0.3,
) -> str:
    """
    Pozovi DeepSeek model via AWS Bedrock.
    Podaci ostaju u eu-central-1 — GDPR compliant.

    Args:
        prompt: Korisnički upit
        model: Model ID (v3.2 ili speciale)
        max_tokens: Max tokena u odgovoru
        system: System prompt
        temperature: 0.0 = deterministično, 1.0 = kreativno

    Returns:
        Tekstualni odgovor modela

    Raises:
        RuntimeError: Ako Bedrock nije konfiguriran ili model nedostupan
    """

    client = _get_bedrock_client()

    # Bedrock Converse API — standardni format za sve modele
    messages = [{"role": "user", "content": [{"text": prompt}]}]

    kwargs = {
        "modelId": model,
        "messages": messages,
        "inferenceConfig": {
            "maxTokens": max_tokens,
            "temperature": temperature,
        },
    }
    if system:
        kwargs["system"] = [{"text": system}]

    try:
        response = client.converse(**kwargs)
        return response["output"]["message"]["content"][0]["text"]
    except Exception as e:
        logger.error("DeepSeek Bedrock error: %s", e)
        # Fallback na Haiku ako Bedrock ne radi
        return _fallback_to_haiku(prompt, system, max_tokens)


def deepseek_reasoning(prompt: str, max_tokens: int = 2000, system: str = "") -> str:
    """
    DeepSeek-V3.2-Speciale — za kompleksne zadatke (PDV audit, GoBD, kod).
    Sporiji, skuplji, ali reasoning-first.
    Koristiti samo za 20% najtežih zadataka.
    """
    return deepseek_chat(
        prompt=prompt,
        model=DEEPSEEK_SPECIALE_MODEL,
        max_tokens=max_tokens,
        system=system,
        temperature=0.1,  # nizak — determinističan za logiku
    )


def _fallback_to_haiku(prompt: str, system: str, max_tokens: int) -> str:
    """Fallback na Claude Haiku ako Bedrock nedostupan."""
    import anthropic

    logger.warning("DeepSeek Bedrock nedostupan — fallback na Haiku")
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model=settings.HAIKU_MODEL,
        max_tokens=max_tokens,
        system=system or "Ti si koristan asistent.",
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


def deepseek_available() -> bool:
    """Provjeri je li Bedrock konfiguriran i dostupan."""
    if not getattr(settings, "AWS_ACCESS_KEY_ID", ""):
        return False
    try:
        import boto3  # noqa: F401

        return bool(getattr(settings, "AWS_BEDROCK_REGION", ""))
    except ImportError:
        return False


# ── Pixtral — Vision model za skeniranje faktura ──────────────────────────────


def pixtral_read_invoice(image_base64: str, media_type: str = "image/jpeg") -> dict:
    """
    Pixtral Large via AWS Bedrock — čita skenirane fakture iz slike.
    Vraća strukturirane podatke: iznos, datum, partner, OIB, IBAN.

    Args:
        image_base64: Base64 enkodirana slika fakture
        media_type: "image/jpeg" ili "image/png"

    Returns:
        dict s poljima: iznos, datum, partner, oib, iban, broj_fakture, valuta
    """
    import json

    import boto3
    from django.conf import settings

    client = boto3.client(
        "bedrock-runtime",
        region_name=getattr(settings, "AWS_BEDROCK_REGION", "eu-central-1"),
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )

    prompt = """Analiziraj ovu fakturu i izvuci podatke. Odgovori SAMO JSON:
{
  "broj_fakture": "...",
  "datum": "DD.MM.YYYY",
  "datum_dospijeća": "DD.MM.YYYY ili null",
  "partner_naziv": "...",
  "partner_oib": "11 znamenki ili null",
  "partner_iban": "HR... ili DE... ili null",
  "iznos_bez_pdv": "decimalni broj",
  "iznos_pdv": "decimalni broj",
  "iznos_ukupno": "decimalni broj",
  "valuta": "EUR ili HRK ili ...",
  "napomena": "kratka napomena ako je relevantna"
}
Ako neko polje ne možeš pročitati, stavi null."""

    try:
        response = client.converse(
            modelId=getattr(settings, "PIXTRAL_MODEL_ID", "eu.mistral.pixtral-large-2502-v1:0"),
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "image": {
                                "format": media_type.split("/")[1],
                                "source": {"bytes": __import__("base64").b64decode(image_base64)},
                            }
                        },
                        {"text": prompt},
                    ],
                }
            ],
            inferenceConfig={"maxTokens": 500, "temperature": 0.1},
        )
        text = response["output"]["message"]["content"][0]["text"]
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0:
            return json.loads(text[start:end])
        return {"error": "Nije mogao parsirati JSON", "raw": text[:200]}
    except Exception as e:
        logger.error("Pixtral invoice read error: %s", e)
        return {"error": str(e)[:200]}


def devstral_code_review(code: str, context: str = "") -> str:
    """
    Devstral 123B — code review i prijedlozi za Django kod.
    Koristi se u Trojstvu kao 3. glasač za tehničke probleme.
    """
    system = (
        "Ti si senior Django/Python inženjer specijaliziran za ERP sustave. "
        "Analiziraš kod i daješ konkretne, kratke prijedloge poboljšanja."
    )
    prompt = f"{context}\n\n```python\n{code[:2000]}\n```" if context else f"```python\n{code[:2000]}\n```"
    return deepseek_chat(
        prompt=prompt,
        model=getattr(
            __import__("django.conf", fromlist=["settings"]).settings, "DEEPSEEK_MODEL_ID", "mistral.devstral-2-123b"
        ),
        system=system,
        max_tokens=800,
        temperature=0.2,
    )
