"""
memio.world — Heritage Bridge | Digitalno Nasljeđe (2026-04-21)

Spaja tri platforme kroz zajednički Heritage Oracle:
  memio.pet  → pet_fragments  (ljubimci, Dugini Most)
  memio.farm → farm_fragments (farme, stoka, zemlja)
  memio.world → world_fragments (sjećanja, TimeCapsule)

Logika:
  Kad ljubimac prođe na Dugini Most (status=uginulo) →
    → svako dijete u "zajedničkim sjećanjima" dobije pet_fragment
    → fragment se enkriptira u Oracle do dobi unlock_age (default 18)
    → na 18. rođendan: "Mapa Porijekla" uključuje priču o prvom ljubimcu

Patent MPH-001 — Konjik d.o.o. / NO LIMIT udruga
"""

import logging
from datetime import date
from django.db import transaction

logger = logging.getLogger("memio_world.heritage_bridge")

MEMIO_PET_DB  = "memio_pets"
MEMIO_WORLD_DB = "memio_world"


def add_pet_fragment_to_oracle(child, chip_or_tag: str, animal_name: str,
                                animal_species: str, is_memorial: bool = False,
                                date_of_death=None, epitaph: str = "") -> bool:
    """
    Dodaj fragment o ljubimcu u HeritageOracle djeteta.

    Poziva se:
      - Kad dijete "označi" ljubimca kao svog (link profil↔dijete)
      - Automatski kad ljubimac prijeđe na Dugini Most
      - Manualno iz breedera / vlasnika

    Fragment format:
    {
        "type": "first_pet" | "beloved_pet" | "memorial",
        "chip": "12345",
        "name": "Rex",
        "species": "pas",
        "memorial": true/false,
        "date_of_death": "2026-04-21",
        "epitaph": "Uvijek ćeš biti u našim srcima",
        "memio_pet_url": "https://memio.pet/pas/12345/naslijede/",
        "added_at": "2026-04-21"
    }
    """
    try:
        from memio_world.models import HeritageOracle, ChildProfile

        oracle = HeritageOracle.objects.using(MEMIO_WORLD_DB).filter(child=child).first()
        if not oracle:
            # Kreiraj Oracle ako ne postoji
            oracle = HeritageOracle.objects.using(MEMIO_WORLD_DB).create(
                child=child,
                status="collecting",
                unlock_age=18,
            )

        # Provjeri postoji li već fragment za ovaj chip
        existing = oracle.pet_fragments or []
        for frag in existing:
            if frag.get("chip") == chip_or_tag:
                # Ažuriraj ako je promijenio status na memorial
                if is_memorial and not frag.get("memorial"):
                    frag["memorial"] = True
                    frag["date_of_death"] = str(date_of_death) if date_of_death else None
                    frag["epitaph"] = epitaph
                    oracle.pet_fragments = existing
                    oracle.save(using=MEMIO_WORLD_DB, update_fields=["pet_fragments"])
                    logger.info("Heritage Bridge: ažuriran memorial fragment %s za dijete %s", chip_or_tag, child.name)
                return True  # Već postoji

        # Dodaj novi fragment
        fragment_type = "memorial" if is_memorial else "beloved_pet"
        new_fragment = {
            "type": fragment_type,
            "chip": chip_or_tag,
            "name": animal_name,
            "species": animal_species,
            "memorial": is_memorial,
            "date_of_death": str(date_of_death) if date_of_death else None,
            "epitaph": epitaph,
            "memio_pet_url": f"https://memio.pet/pas/{chip_or_tag}/naslijede/",
            "added_at": str(date.today()),
        }
        existing.append(new_fragment)
        oracle.pet_fragments = existing

        # Ažuriraj status Oraclea ako je značajan fragment
        if is_memorial and oracle.status == "collecting":
            oracle.status = "growing"

        oracle.save(using=MEMIO_WORLD_DB, update_fields=["pet_fragments", "status"])
        logger.info(
            "Heritage Bridge: dodan %s fragment '%s' (chip:%s) za dijete %s",
            fragment_type, animal_name, chip_or_tag, child.name
        )
        return True

    except Exception as exc:
        logger.error("Heritage Bridge: greška pri dodavanju pet fragmenta: %s", exc, exc_info=True)
        return False


def sync_dugini_most_to_oracles(animal) -> int:
    """
    Kada ljubimac prijeđe na Dugini Most (status=uginulo):
      → Traži sve ChildProfile u memio.world koji su vezani uz ovog vlasnika
      → Svako dijete dobije memorial fragment u Oracle
      → Vraća broj ažuriranih Oracle-a

    Poziva se iz: memio_pet/signals.py (post_save na AnimalProfile)
    """
    try:
        from memio_world.models import ChildProfile

        chip = getattr(animal, "chip_number", "") or ""
        name = animal.name or animal.ear_tag
        species = getattr(animal, "vrsta", "pas")

        # Dohvati memorial info
        date_of_death = None
        epitaph = ""
        try:
            memorial = animal.memorial
            date_of_death = getattr(memorial, "date_of_death", None)
            epitaph = getattr(memorial, "epitaph", "")
        except Exception:
            pass

        # Breeder OIB ili limit_company_id za mapiranje na obitelji
        breeder = getattr(animal, "breeder", None)
        limit_id = breeder.limit_company_id if breeder else ""

        # Pronađi djecu vezanu uz ovu obitelj/korisnika
        # Heuristika: ChildProfile.parent (User) → breeder.user
        children_qs = ChildProfile.objects.using(MEMIO_WORLD_DB).none()
        if breeder and breeder.user_id:
            children_qs = ChildProfile.objects.using(MEMIO_WORLD_DB).filter(
                created_by_id=breeder.user_id
            )

        count = 0
        for child in children_qs:
            success = add_pet_fragment_to_oracle(
                child=child,
                chip_or_tag=chip or animal.ear_tag,
                animal_name=name,
                animal_species=species,
                is_memorial=True,
                date_of_death=date_of_death,
                epitaph=epitaph,
            )
            if success:
                count += 1

        if count:
            logger.info("Heritage Bridge: Dugini Most — %d Oracle(a) ažurirano za '%s'", count, name)
        return count

    except Exception as exc:
        logger.error("Heritage Bridge: sync_dugini_most greška: %s", exc, exc_info=True)
        return 0


def get_pet_heritage_for_child(child) -> list:
    """
    Dohvati sve pet fragmente za dijete — za prikaz na memio.world profilima.
    Vraća listu fragmenata sortirano: memorials prvo, onda beloved.
    """
    try:
        from memio_world.models import HeritageOracle
        oracle = HeritageOracle.objects.using(MEMIO_WORLD_DB).filter(child=child).first()
        if not oracle:
            return []
        frags = oracle.pet_fragments or []
        # Sortiranje: memorial → beloved_pet → first_pet
        order = {"memorial": 0, "beloved_pet": 1, "first_pet": 2}
        return sorted(frags, key=lambda f: order.get(f.get("type", "beloved_pet"), 3))
    except Exception:
        return []
