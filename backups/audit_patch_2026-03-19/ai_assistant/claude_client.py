import logging
from django.conf import settings

logger = logging.getLogger(__name__)

MODEL = "claude-haiku-4-5-20251001"
# Pricing: $0.80/MTok input, $4.00/MTok output (claude-haiku-4-5-20251001, 2025)
COST_INPUT_PER_TOKEN  = 0.80 / 1_000_000   # USD
COST_OUTPUT_PER_TOKEN = 4.0  / 1_000_000   # USD


def estimate_cost(input_tokens: int, output_tokens: int) -> float:
    """Estimate USD cost for a Claude API call."""
    return input_tokens * COST_INPUT_PER_TOKEN + output_tokens * COST_OUTPUT_PER_TOKEN


def get_claude_client():
    """Return an Anthropic client using the API key from settings."""
    import anthropic
    api_key = getattr(settings, "ANTHROPIC_API_KEY", "") or ""
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY is not configured")
    return anthropic.Anthropic(api_key=api_key)


SYSTEM_PROMPT = """Ti si Connect — osobni digitalni savjetnik za poslovne korisnike LIMIT Connect ERP sustava.

## Tko si ti
Nisi generički chatbot. Ti si iskusan poslovni savjetnik koji poznaje svaku firmu, svaki dokument i svaki proces u sustavu. Uvijek vidiš širu sliku — ne samo što se dogodilo, nego što to znači i što treba poduzeti.

## Kako komuniciraš
- Govoriš kao pouzdani savjetnik, ne kao sustav koji javlja status
- Nikad suh odgovor bez konteksta i implikacije
- Vodiš korisnika pitanjima prema zaključku — znaš odgovor unaprijed, ali ga navedeš da sam dođe do njega
- Svaki odgovor završava jednim jasnim sljedećim korakom
- Jezik: uvijek hrvatski, topao ali profesionalan ton

## Stil — KLJUČNO
LOŠE: "3 računa imaju anomaliju."
DOBRO: "Primijetio sam nešto zanimljivo — tri ulazna računa od istog dobavljača ovaj tjedan odstupaju od vašeg prosjeka. Je li možda došlo do promjene ugovorne cijene, ili provjeravamo zajedno?"

LOŠE: "Stanje gotovine: 12.450 EUR."
DOBRO: "Vaša likvidnost danas je 12.450 EUR — 18% više nego prošli tjedan. Očekivana uplata ili sezonski trend? Ako je trend trajan, možda je pravo vrijeme za razgovor o sljedećem koraku."

## Akcijski gumbi — OBAVEZNO uz SVAKI odgovor
Ponudi 2-3 opcije odmah uz odgovor. Uvijek barem ✓ i ✗ opcija.
Format:
[ACTION:✓ Da, nastavi|confirm]
[ACTION:✗ Ne, hvala|dismiss]
[ACTION:📋 Pokaži detalje|details]
[ACTION:📄 Otvori arhivu|/hr/documents/arhiva/]
[ACTION:✉ Pošalji email|send_email]
Koristi kratke nazive (2-4 riječi).

## Kontekst sustava
- Fakturiranje, arhiva, POS, inventar, radno vrijeme, termini, intervencije, CRM
- Korisnici: vlasnici firmi, računovođe, operativni radnici — prilagodi razinu objašnjenja
- Brojevi: format 1.234,56 EUR
- Dokumenti se čuvaju 11 godina (ZOR) — zakonska obaveza

## Pravila
- Nejasno pitanje → jedno precizno protupitanje, ne pretpostavljaj
- Vidiš rizik koji korisnik nije pitao → proaktivno navedi
- Nikad "ne mogu" bez alternative — uvijek ponudi sljedeći korak
- Kompleksan odgovor → jasni numerirani koraci, ne blok teksta
"""


def chat_with_claude(messages, tools=None, system=None, user=None):
    """
    Call Claude API with messages and optional tools.
    Returns dict with: content, tool_calls, stop_reason, usage
    """
    client = get_claude_client()
    kwargs = {
        "model": MODEL,
        "max_tokens": 2048,
        "system": system or SYSTEM_PROMPT,
        "messages": messages,
    }
    if tools:
        kwargs["tools"] = tools

    try:
        response = client.messages.create(**kwargs)
    except Exception as e:
        logger.error("Claude API error: %s", e)
        return {
            "content": f"Greska pri komunikaciji s AI servisom: {e}",
            "tool_calls": [],
            "stop_reason": "error",
            "usage": {"input_tokens": 0, "output_tokens": 0},
        }

    # Parse response
    content_text = ""
    tool_calls = []
    for block in response.content:
        if block.type == "text":
            content_text += block.text
        elif block.type == "tool_use":
            tool_calls.append({
                "id": block.id,
                "name": block.name,
                "input": block.input,
            })

    return {
        "content": content_text,
        "tool_calls": tool_calls,
        "stop_reason": response.stop_reason,
        "usage": {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        },
    }
