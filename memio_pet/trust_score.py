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
            has_verified_vet = (
                PetHealthRecord.objects.using(db)
                .filter(animal=animal, vet_profile__isnull=False, vet_profile__is_verified=True)
                .exists()
            )
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

        total_records = PetHealthRecord.objects.using(db).filter(animal__breeder=breeder).count()

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
        recently_updated = animals.filter(updated_at__gte=now - timedelta(days=90)).count()
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

    # ── 7. RECENZIJE KUPACA (max 15 iz aktivnost) ──────────────
    # Preraspodjela: aktivnost 10 + review 5 (kad bude vise reviewsa, povecaj)
    rev_score = 0
    rev_notes = []
    from memio_pet.models import BreederReview

    reviews = BreederReview.objects.using(db).filter(breeder=breeder, is_published=True)
    rev_count = reviews.count()
    if rev_count > 0:
        from django.db.models import Avg

        avg_rating = reviews.aggregate(avg=Avg("rating"))["avg"] or 0
        verified_count = reviews.filter(is_verified_purchase=True).count()
        # Score: do 5 za kolicinu, do 5 za kvalitetu, do 5 za verificirane
        qty_pts = min(rev_count, 5)  # 1 bod po reviewu, max 5
        qual_pts = int(avg_rating)  # 1-5 bodova za prosjecnu ocjenu
        ver_pts = min(verified_count * 2, 5)  # 2 boda po verificiranom, max 5
        rev_score = min(qty_pts + qual_pts + ver_pts, 15)
        rev_notes.append(f"{rev_count} recenzija, prosjek {avg_rating:.1f}/5 (+{rev_score})")
        if verified_count:
            rev_notes.append(f"{verified_count} verificiranih kupnji")
    else:
        rev_notes.append("Nema recenzija (0/15) — potaknite kupce da ostave ocjenu")
    breakdown["recenzije"] = {"score": rev_score, "max": 15, "notes": rev_notes}

    # Smanjujemo aktivnost na max 10 (ukupno ostaje 100)
    if "aktivnost" in breakdown:
        act = breakdown["aktivnost"]
        act["max"] = 10
        act["score"] = min(act["score"], 10)

    # ── 8. DIGITALNO NASLJEĐE (animal level, avg po životinji) ────────────
    heritage_score_sum = 0
    heritage_notes = []
    if total_animals > 0:
        from memio_pet.models import DigitalHeritage as DH
        heritage_scores = []
        for anim in animals:
            try:
                dh = DH.objects.using(db).get(animal=anim)
                heritage_scores.append(dh.heritage_score)
            except DH.DoesNotExist:
                heritage_scores.append(0)
        if heritage_scores:
            avg_h = sum(heritage_scores) / len(heritage_scores)
            heritage_score_sum = min(15, int(avg_h))
            heritage_notes.append(f"Prosjek Heritage Score: {avg_h:.1f}/15 (+{heritage_score_sum})")
        if heritage_score_sum < 15:
            heritage_notes.append("Dodajte genealogiju i certifikate za veći score")
    else:
        heritage_notes.append("Nema životinja s Heritage profilom (0/15)")
    breakdown["digitalno_nasljedstvo"] = {"score": heritage_score_sum, "max": 15, "notes": heritage_notes}

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


def calculate_heritage_score(animal) -> tuple[int, dict]:
    """
    Izračunava Heritage Score za AnimalProfile (0-100).
    Nadopunjuje globalni Trust Score kao 8. dimenzija Breedera.

    Bodovi:
      Genealogija dokumentirana:   +5  (barem jedan roditelj poznat)
      Duboka rodovnica (≥2 gen.):  +5
      Genetski testovi (pass):     +5  (health clearances)
      Prvak u rodovnici:           +5  (championship trait)
      Naslijeđeni Trust Score:     +10 (avg roditeljskog trust / 10)
      Legacy Bequest kreiran:      +5
      Sve komponente zajedno:      +5  (bonus za kompletnost)
      ─────────────────────────────────
      MAX:                        = 40 (normalizira se na 15 za Trust Score)
    """
    db = "memio_pets"
    breakdown = {}
    score_raw = 0

    from memio_pet.models import HeritageTrait, LegacyBequest

    # ── 1. GENEALOGIJA ──────────────────────────────────────────────────────
    gen_score = 0
    gen_notes = []
    has_father = bool(animal.father_chip)
    has_mother = bool(animal.mother_chip)

    if has_father or has_mother:
        gen_score += 5
        gen_notes.append(f"Barem jedan roditelj poznat (+5)")

    # Dohvati generacijski dubinu
    generation = animal.generation_number or 1
    if generation >= 2:
        gen_score += 5
        gen_notes.append(f"Generacija {generation} — duboka rodovnica (+5)")
    elif has_father and has_mother:
        gen_notes.append("Oba roditelja dokumentirana — dodaj generacijski broj")

    breakdown["genealogija"] = {"score": gen_score, "max": 10, "notes": gen_notes}
    score_raw += gen_score

    # ── 2. GENETSKI TESTOVI I HEALTH CLEARANCES ────────────────────────────
    health_score = 0
    health_notes = []
    clearances = HeritageTrait.objects.using(db).filter(
        animal=animal, trait_type="health_clearance", result__in=["pass", "grade_a", "grade_b"]
    )
    n_clearances = clearances.count()
    if n_clearances >= 3:
        health_score = 5
    elif n_clearances >= 1:
        health_score = 3
    if n_clearances:
        health_notes.append(f"{n_clearances} health clearance(s) potvrđenih (+{health_score})")
    else:
        health_notes.append("Dodajte genetske testove (OFA, PennHip, ...)")
    breakdown["health_clearances"] = {"score": health_score, "max": 5, "notes": health_notes}
    score_raw += health_score

    # ── 3. PRVACI U RODOVNICI ───────────────────────────────────────────────
    champ_score = 0
    champ_notes = []
    championships = HeritageTrait.objects.using(db).filter(animal=animal, trait_type="championship")
    n_champs = championships.count()
    if n_champs >= 2:
        champ_score = 5
    elif n_champs == 1:
        champ_score = 3
    if n_champs:
        champ_notes.append(f"{n_champs} titule u rodovnici (+{champ_score})")
        for c in championships[:3]:
            champ_notes.append(f"  🏆 {c.name}")
    else:
        champ_notes.append("Nema evidentiranih titula")
    breakdown["prvaci"] = {"score": champ_score, "max": 5, "notes": champ_notes}
    score_raw += champ_score

    # ── 4. NASLIJEĐENI TRUST SCORE OD RODITELJA ────────────────────────────
    inherited_score = 0
    inherited_notes = []
    parent_trusts = []

    if animal.father_chip:
        from memio_pet.models import AnimalProfile
        father = AnimalProfile.objects.using(db).filter(chip_number=animal.father_chip).first()
        if father and father.breeder:
            parent_trusts.append(father.breeder.trust_score)
            inherited_notes.append(f"Otac: {father.name} (Trust {father.breeder.trust_score}/100)")

    if animal.mother_chip:
        from memio_pet.models import AnimalProfile
        mother = AnimalProfile.objects.using(db).filter(chip_number=animal.mother_chip).first()
        if mother and mother.breeder:
            parent_trusts.append(mother.breeder.trust_score)
            inherited_notes.append(f"Majka: {mother.name} (Trust {mother.breeder.trust_score}/100)")

    if parent_trusts:
        avg_trust = sum(parent_trusts) / len(parent_trusts)
        inherited_score = min(10, int(avg_trust / 10))  # max 10 bodova
        inherited_notes.append(f"Naslijeđeni score: {avg_trust:.0f}/100 → +{inherited_score} bodova")
    else:
        inherited_notes.append("Nema dokumentiranih roditelja u sustavu")

    breakdown["naslijedeni_trust"] = {"score": inherited_score, "max": 10, "notes": inherited_notes}
    score_raw += inherited_score

    # ── 5. LEGACY BEQUEST ───────────────────────────────────────────────────
    bequest_score = 0
    bequest_notes = []
    has_bequest = LegacyBequest.objects.using(db).filter(
        animal=animal, status__in=["active", "triggered", "completed"]
    ).exists()
    if has_bequest:
        bequest_score = 5
        bequest_notes.append("Digitalna oporuka kreirana (+5)")
    else:
        bequest_notes.append("Kreirajte digitalnu oporuku → nasljedni bonus")
    breakdown["digitalna_oporuka"] = {"score": bequest_score, "max": 5, "notes": bequest_notes}
    score_raw += bequest_score

    # ── 6. KOMPLETNOST BONUS ────────────────────────────────────────────────
    completeness = 0
    if gen_score >= 5 and health_score >= 3 and n_champs > 0 and has_bequest:
        completeness = 5
        breakdown["kompletnost"] = {"score": 5, "max": 5, "notes": ["Sve Heritage komponente popunjene (+5)"]}
    else:
        missing = []
        if gen_score < 5:   missing.append("genealogija")
        if health_score < 3: missing.append("genetski testovi")
        if n_champs == 0:   missing.append("titule")
        if not has_bequest: missing.append("oporuka")
        breakdown["kompletnost"] = {"score": 0, "max": 5, "notes": [f"Nedostaje: {', '.join(missing)}"]}
    score_raw += completeness

    # ── NORMALIZACIJA na 15 ─────────────────────────────────────────────────
    max_raw = 40
    normalized = int((score_raw / max_raw) * 15)
    normalized = min(normalized, 15)

    return normalized, score_raw, breakdown


def update_digital_heritage(animal) -> "DigitalHeritage":
    """
    Izračunava i sprema DigitalHeritage zapis za životinju.
    Poziva se: post_save signal, Celery beat (noćno), manualno.
    """
    from memio_pet.models import DigitalHeritage, HeritageTrait

    db = "memio_pets"
    normalized, raw, breakdown = calculate_heritage_score(animal)

    # Known champions i health clearances za agregatne fielde
    n_champs = HeritageTrait.objects.using(db).filter(
        animal=animal, trait_type="championship"
    ).count()
    n_clearances = HeritageTrait.objects.using(db).filter(
        animal=animal, trait_type="health_clearance", result__in=["pass", "grade_a", "grade_b"]
    ).count()

    heritage, _ = DigitalHeritage.objects.using(db).update_or_create(
        animal=animal,
        defaults={
            "generation_depth": animal.generation_number or 1,
            "known_champions": n_champs,
            "health_clearances": n_clearances,
            "heritage_score": normalized,
            "heritage_breakdown": breakdown,
        }
    )
    logger.info("DigitalHeritage updated: %s = %d/15", animal.name, normalized)
    return heritage
