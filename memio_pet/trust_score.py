"""
memio_pet/trust_score.py -- Trust Score kalkulacija (0-100)

Formula je TRANSPARENTNA -- svaki bod ima objasnjenje.
Breeder vidi breakdown: sto mu fali i kako popraviti score.

Kategorije:
  OIB verifikacija:     +20  (CroValidator potvrda)
  Veterinar potpis:     +25  (verificirani vet na health recordima)
  Zdravstveni kartoni:  +15  (cijepljenja, pregledi)
  Lanac vlasnistva:     +15  (ownership chain, ugovori)
  Foto dokumentacija:   +10  (slike zivotinja)
  Recenzije/aktivnost:  +15  (redovitost, azuriranost)
  UKUPNO:              =100
"""
import logging
from datetime import timedelta
from django.utils import timezone

logger = logging.getLogger("memio_pet")


def calculate_trust_score(breeder):
    """
    Racuna Trust Score za BreederProfile.
    Vraca (score, breakdown_dict).
    """
    db = "memio_pets"
    breakdown = {}

    # ── 1. OIB VERIFIKACIJA (max 20) ────────────────────────────
    oib_score = 0
    oib_notes = []
    if breeder.oib:
        oib_score += 5
        oib_notes.append("OIB unesen (+5)")
    else:
        oib_notes.append("OIB nije unesen (0/5)")
    if breeder.is_cro_validated:
        oib_score += 15
        oib_notes.append("CroValidator potvrda (+15)")
    else:
        oib_notes.append("CroValidator nije potvrdjen (0/15)")
    breakdown["oib"] = {"score": oib_score, "max": 20, "notes": oib_notes}

    # ── 2. VETERINAR POTPIS (max 25) ────────────────────────────
    vet_score = 0
    vet_notes = []
    animals = breeder.animals.using(db).all()
    total_animals = animals.count()

    if total_animals > 0:
        from memio_pet.models import PetHealthRecord
        animals_with_vet = 0
        for animal in animals:
            has_verified_vet = PetHealthRecord.objects.using(db).filter(
                animal=animal,
                vet_profile__isnull=False,
                vet_profile__is_verified=True
            ).exists()
            if has_verified_vet:
                animals_with_vet += 1

        ratio = animals_with_vet / total_animals
        vet_score = int(ratio * 25)
        vet_notes.append(f"{animals_with_vet}/{total_animals} zivotinja s verificiranim vetom (+{vet_score})")
        if ratio < 1.0:
            vet_notes.append(f"Dodajte verificiranog veterinara za preostalih {total_animals - animals_with_vet}")
    else:
        vet_notes.append("Nema unesenih zivotinja (0/25)")
    breakdown["veterinar"] = {"score": vet_score, "max": 25, "notes": vet_notes}

    # ── 3. ZDRAVSTVENI KARTONI (max 15) ─────────────────────────
    health_score = 0
    health_notes = []
    if total_animals > 0:
        from memio_pet.models import PetHealthRecord
        total_records = PetHealthRecord.objects.using(db).filter(
            animal__breeder=breeder
        ).count()

        avg_records = total_records / total_animals
        if avg_records >= 3:
            health_score = 15
        elif avg_records >= 2:
            health_score = 10
        elif avg_records >= 1:
            health_score = 5
        health_notes.append(f"{total_records} zapisa, prosjek {avg_records:.1f}/zivotinji (+{health_score})")
        if health_score < 15:
            health_notes.append("Cilj: min 3 zapisa po zivotinji za puni score")
    else:
        health_notes.append("Nema zivotinja (0/15)")
    breakdown["zdravlje"] = {"score": health_score, "max": 15, "notes": health_notes}

    # ── 4. LANAC VLASNISTVA (max 15) ───────────────────────────
    own_score = 0
    own_notes = []
    if total_animals > 0:
        from memio_pet.models import PetOwnership
        animals_with_ownership = 0
        for animal in animals:
            if PetOwnership.objects.using(db).filter(animal=animal).exists():
                animals_with_ownership += 1

        ratio = animals_with_ownership / total_animals
        own_score = int(ratio * 15)
        own_notes.append(f"{animals_with_ownership}/{total_animals} s evidencijom vlasnistva (+{own_score})")
        if ratio < 1.0:
            own_notes.append("Unesite vlasnistvo za sve zivotinje")
    else:
        own_notes.append("Nema zivotinja (0/15)")
    breakdown["vlasnistvo"] = {"score": own_score, "max": 15, "notes": own_notes}

    # ── 5. FOTO DOKUMENTACIJA (max 10) ─────────────────────────
    photo_score = 0
    photo_notes = []
    if total_animals > 0:
        with_photo = animals.exclude(photo="").exclude(photo__isnull=True).count()
        ratio = with_photo / total_animals
        photo_score = int(ratio * 10)
        photo_notes.append(f"{with_photo}/{total_animals} sa fotografijom (+{photo_score})")
        if ratio < 1.0:
            photo_notes.append("Dodajte fotografije — kupci zele vidjeti ljubimca")
    else:
        photo_notes.append("Nema zivotinja (0/10)")
    breakdown["foto"] = {"score": photo_score, "max": 10, "notes": photo_notes}

    # ── 6. AKTIVNOST / AZURIRANOST (max 15) ────────────────────
    act_score = 0
    act_notes = []
    now = timezone.now()

    if total_animals > 0:
        recently_updated = animals.filter(
            updated_at__gte=now - timedelta(days=90)
        ).count()
        ratio = recently_updated / total_animals
        pts = int(ratio * 8)
        act_score += pts
        act_notes.append(f"{recently_updated}/{total_animals} azurirano u zadnjih 90 dana (+{pts})")

    # Bonus za profile starije od 30 dana (nije fly-by-night)
    if breeder.created_at and (now - breeder.created_at).days >= 30:
        act_score += 4
        act_notes.append("Profil aktivan 30+ dana (+4)")
    else:
        act_notes.append("Profil mladi od 30 dana (0/4)")

    # Bonus za kontakt info
    if breeder.phone or breeder.website:
        act_score += 3
        act_notes.append("Kontakt info dostupan (+3)")
    else:
        act_notes.append("Dodajte telefon ili web stranicu (+3)")

    act_score = min(act_score, 15)
    breakdown["aktivnost"] = {"score": act_score, "max": 15, "notes": act_notes}

    # ── TOTAL ───────────────────────────────────────────────────
    total = sum(cat["score"] for cat in breakdown.values())
    total = min(total, 100)

    return total, breakdown


def update_trust_score(breeder):
    """Racuna i sprema Trust Score na BreederProfile."""
    score, breakdown = calculate_trust_score(breeder)
    breeder.trust_score = score
    breeder.trust_breakdown = breakdown
    breeder.trust_updated = timezone.now()
    breeder.save(using="memio_pets", update_fields=["trust_score", "trust_breakdown", "trust_updated"])
    logger.info("Trust Score updated: %s = %d/100", breeder.name, score)
    return score, breakdown


def bulk_update_trust_scores():
    """Azurira Trust Score za sve breedere. Celery task ili manual."""
    from memio_pet.models import BreederProfile
    breeders = BreederProfile.objects.using("memio_pets").all()
    results = []
    for b in breeders:
        score, _ = update_trust_score(b)
        results.append((b.name, score))
    return results
