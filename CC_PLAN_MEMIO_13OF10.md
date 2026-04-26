# MEMIO GRUPA — 13/10 PLAN
# Kreirano: 2026-04-27 | Sudačka odluka Claude
# Memio se NE prodaje — vlasništvo Udruge, EU fondovi, sigurnost podataka

## TRENUTNI REZULTATI
| App | Trenutno | Cilj |
|-----|---------|------|
| memio.pet | 6.5/10 | 13/10 |
| memio.world | 6.0/10 | 13/10 |
| memio.farm | 3.0/10 | 13/10 |
| no_limit | 8.0/10 | 13/10 |

## ⚠️ HITNO — Creative Europe rok: 2026-05-07 (PLAY.EU Sprint 2)

---

## PLAN-M1 — memio.pet → 13/10

### Sprint 1 (HITNO, ovaj tjedan)
- [ ] M1-01: pretraga.html view + template (PLAN-005) — AnimalProfile.objects.filter(is_public=True)
- [ ] M1-02: SaleAd model + /prodaja/ view (PLAN-006) — oglas za prodaju ljubimca

### Sprint 2 (sljedeći tjedan)
- [ ] M1-03: AI Breed Detection (PLAN-013) — Claude Haiku API, slika → pasmina + opis
- [ ] M1-04: Vet Bridge webhook (PLAN-014) — primanje vet zapisa od vanjskih sustava
- [ ] M1-05: PWA manifest + service worker — offline public profil

### Sprint 3 (do kraja svibnja)
- [ ] M1-06: VIVUS .dok upgrade — svaki ljubimac dobiva .dok putovnicu
- [ ] M1-07: Trust Score badge + ChainBlock POE na public profilu
- [ ] M1-08: BPZ-9 honeypot za lažne profile
- [ ] M1-09: TLS 1.3 only + GDPR font fix (Google Fonts → self-hosted)
- [ ] M1-10: Folija Live Badge na uzgajivačkim profilima

---

## PLAN-M2 — memio.world → 13/10

### Sprint 1 (⚠️ HITNO — EU rok 2026-05-07)
- [ ] M2-01: PLAY.EU Sprint 2 — 7 game/story templates:
       story_reader.html, game_play.html, heritage_card.html,
       parallel_story.html, voice_legacy_record.html,
       time_capsule_create.html, memory_vault.html
- [ ] M2-02: Pokrenuti GEMINI_TASK_EU_FONDOVI_MEMIO_WORLD.md

### Sprint 2
- [ ] M2-03: VoiceLegacy UI — WebAudio API + S3 upload
- [ ] M2-04: TimeCapsule UI — kreiranje, zaključavanje, scheduled-open
- [ ] M2-05: Parent dashboard — ChildProfile + Milestone + LearningModule

### Sprint 3
- [ ] M2-06: VIVUS L5 klaster — FamilyStory = Merkle klaster
- [ ] M2-07: ChainBlock POE za TimeCapsule
- [ ] M2-08: GDPR fonts + TLS 1.3
- [ ] M2-09: 8-jezik SEO (HR/DE/EN/FR/IT/SK/SL/HU)

---

## PLAN-M3 — memio.farm → 13/10

### Sprint 1 (idući tjedan — temelji)
- [ ] M3-01: 7 modela: HealthRecord, EarTag, FeedLog, ProductionRecord, HACCPDocument, SlaughterRecord, AgronetSync
- [ ] M3-02: Migracije + manage.py check
- [ ] M3-03: CRUD views za FarmAnimal + HealthRecord

### Sprint 2
- [ ] M3-04: AGRONET bridge — XML sync → FarmAnimal
- [ ] M3-05: HACCP dokument generator (PDF via ReportLab)
- [ ] M3-06: Seed — 50 životinja, 3 farme, 10 HealthRecord unosa

### Sprint 3
- [ ] M3-07: EU grant field — eu_eligible_hours na farmskim aktivnostima
- [ ] M3-08: memio_farm domena live + landing page
- [ ] M3-09: .dok putovnica za farmske životinje (VIVUS L1)
- [ ] M3-10: Beehive digitalna košnica — med prinos tracking

---

## PLAN-M4 — no_limit → 13/10

### Sprint 1
- [ ] M4-01: Email potvrda za AmbassadorApplication (faza 2)
- [ ] M4-02: Leaflet.js karta Europe — 14 zemalja, ambasadori pinovi
- [ ] M4-03: Stripe donacije — /doniraj/ endpoint

### Sprint 2
- [ ] M4-04: Django i18n SEO URLs — /hr/, /de/, /en/, /it/ prefiksi
- [ ] M4-05: Živih životinja listing — memio.pet AnimalProfile (shelter=True)
- [ ] M4-06: No Limit OIB udruge — BLOCKER čeka Marija

---

## REDOSLIJED AKTIVACIJE
```
ODMAH:            M2-01 + M2-02 (EU rok 2026-05-07!)
OVAJ TJEDAN:      M1-01 + M1-02 (memio.pet pretraga+prodaja)
SLJEDEĆI TJEDAN:  M3-01 do M3-03 (memio.farm temelji)
                  M4-01 do M4-03 (no_limit faza 2)
```
