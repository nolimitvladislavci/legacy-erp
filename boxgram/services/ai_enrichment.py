from django.db import IntegrityError
"""
Boxgram AI Enrichment — Haiku auto-opisi za LifeEvent
Model: claude-haiku-4-5-20251001
"""

import logging

from django.conf import settings

logger = logging.getLogger(__name__)

EVENT_PROMPTS = {
    "rodenje": "Napiši toplu, kratku (2 rečenice max) objavu na hrvatskom za profil ljubimca koji se upravo rodio. Ime: {name}, vrsta: {species}. Bez emojija. Bez klišeja. Iskreno i toplo.",
    "vet": "Napiši kratki update (2 rečenice) na hrvatskom o vet posjetu ljubimca. Ime: {name}, vrsta: {species}, naslov posjeta: {title}. Informativno, bez dramatiziranja.",
    "nagrada": "Napiši kratki slavodobitan tekst (2 rečenice) na hrvatskom o nagradi/uspjehu ljubimca. Ime: {name}, nagrada: {title}. Ponosno ali skromno.",
    "milestone": "Napiši kratki, topli opis prekretnice (2 rečenice) na hrvatskom za ljubimca. Ime: {name}, vrsta: {species}, događaj: {title}. Bez klišeja.",
    "natjecanje": "Napiši kratki tekst (2 rečenice) na hrvatskom o sudjelovanju na natjecanju. Ime: {name}, natjecanje: {title}. Uzbudljivo ali ne pretjerano.",
    "cijepljenje": "Napiši kratki update (2 rečenice) na hrvatskom o cijepljenju ljubimca. Ime: {name}, vrsta: {species}, cijepljenje: {title}. Informativno.",
    "leglo": "Napiši topli tekst (2 rečenice) na hrvatskom o novom leglu/rojenju. Ime: {name}, vrsta: {species}, detalji: {title}. Radosno.",
    "smrt": "Napiši kratki, dostojanstven tekst (2 rečenice) na hrvatskom u sjećanje na ljubimca koji je preminuo. Ime: {name}, vrsta: {species}. S poštovanjem, bez klišeja.",
    "memorijal": "Napiši kratki memorijalni tekst (2 rečenice) na hrvatskom za profil ljubimca. Ime: {name}, vrsta: {species}, povod: {title}. Toplo i dostojanstveno.",
    "ostalo": "Napiši kratki, topli opis (2 rečenice) na hrvatskom o ovom trenutku u životu ljubimca. Ime: {name}, vrsta: {species}, opis: {title}.",
}


def enrich_life_event(event) -> str:
    """
    Generiraj AI opis za LifeEvent.
    Nikad ne baca exception — samo logira i vraća ''.
    """
    api_key = getattr(settings, "ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.warning("Boxgram AI: ANTHROPIC_API_KEY nije postavljen")
        return ""

    if event.description and len(event.description) > 50:
        return event.description

    try:
        import anthropic

        pet = event.pet
        prompt_template = EVENT_PROMPTS.get(event.event_type, EVENT_PROMPTS["ostalo"])
        prompt = prompt_template.format(
            name=pet.name,
            species=pet.get_species_display(),
            title=event.title or "",
        )

        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001", max_tokens=150, messages=[{"role": "user", "content": prompt}]
        )

        generated = message.content[0].text.strip()
        logger.info(f"Boxgram AI: LifeEvent {event.pk} enriched ({len(generated)} chars)")
        return generated

    except (IntegrityError, DatabaseError) as e:
        logger.warning(f"Boxgram AI enrich skip: {e}")
        return ""


def moderate_social_import(import_obj) -> dict:
    """
    Provjeri je li uvezeni sadržaj prikladan za platformu.
    Vraća: {approved: bool, reason: str}
    """
    api_key = getattr(settings, "ANTHROPIC_API_KEY", "")
    if not api_key:
        return {"approved": True, "reason": "AI moderacija nije konfigurirana"}

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)

        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=100,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Je li ovaj sadržaj prikladan za platformu za ljubimce? "
                        f"Odgovori samo: PRIKLADNO ili NEPRIKLADNO i kratko zašto (1 rečenica).\n\n"
                        f"Naslov: {import_obj.caption[:200]}"
                    ),
                }
            ],
        )

        result = message.content[0].text.strip()
        approved = result.upper().startswith("PRIKLADNO")
        return {"approved": approved, "reason": result}

    except (IntegrityError, DatabaseError) as e:
        logger.warning(f"AI moderacija error: {e}")
        return {"approved": True, "reason": f"AI error: {e}"}
