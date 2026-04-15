# PLAY.EU — Sprint 1 Plan
## Vanjski deadline: Creative Europe 2026-05-07
## Status: AKTIVAN — Faza A DONE

---

## CILJ
Demo-ready MVP za Creative Europe prijavu:
- 3 Django modela u memio_world bazi
- Europeana API integracija (IIIF + Search)
- Višejezične paralelne priče (min 5 jezika)
- Heritage kartice (digitalne rekonstrukcije)
- Kviz engine s ocjenjivanjem

---

## FAZA A: Modeli + Migracije ✅ DONE

### Model 1: EuropeanaItem
- Cache/proxy za Europeana API (55M+ objekata, 20M CC0)
- 32 polja, tablica `play_europeana_item`
- Rights tracking (CC0, CC-BY, is_commercially_usable)
- Kategorije: alphabet, counting, story, song, game, illustration, map, manuscript, bestiary

### Model 2: ParallelStory
- Ista priča na 7 jezika (HR, DE, EN, FR, IT, ES, TR)
- 37 polja, tablica `play_parallel_story`
- Izvori: Grimm, Andersen, Perrault, StoryWeaver, Gutenberg, Europeana, folk
- Audio naracija (HR, DE, EN)
- FK na EuropeanaItem za ilustracije

### Model 3: HeritageCard
- Digitalne rekonstrukcije starih igara/slovarica
- 24 polja, tablica `play_heritage_card`
- Card setovi: grimm_bestiary, hr_alphabet, le_quadrille...
- Game mehanike: memory, quiz, sequence, matching, collection

Migracija: `0007_play_eu_sprint1_europeana_story_heritage` — primijenjena.
Admin: registrirano za sva 3 modela.

---

## FAZA B: Europeana API Integracija ✅ DONE

### B.1: API Client
- `memio_world/europeana_client.py`
- Search API wrapper s rate limiting
- IIIF Manifest parser za slike
- Filter: `reusability=open` → samo CC0/CC-BY
- Cache rezultata u Redis (TTL 24h)

### B.2: Sync Command
- `manage.py europeana_sync --category alphabet --limit 100`
- Povlači items iz Europeana, kreira EuropeanaItem zapise
- Dedup po europeana_id
- Auto-detect commercially_usable iz rights polja

### B.3: Celery Beat
- `europeana_weekly_sync` — tjedni sync
- Sync novih items po svim kategorijama
- Max 500 items/tjedan (API fair use)

---

## FAZA C: Sadržaj ✅ DONE

### C.1: Grimm Priče (5 jezika)
- Scrape GrimmStories.com (13 jezika dostupno, public domain)
- Import u ParallelStory: HR, DE, EN, FR, IT
- Min 20 bajki za demo

### C.2: Bestiarij Kartice
- Aberdeen Bestiary items via Europeana
- HeritageCard set: "aberdeen_bestiary"
- 30 kartica (životinje s ilustracijama)
- Memory game mehanika

### C.3: HR Slovarica
- HeritageCard set: "hr_alphabet"
- 30 kartica (A-Ž + Č, Ć, Đ, Š, Ž)
- Ilustracije iz Europeana + Gallica abécédaires
- Quiz mehanika

---

## FAZA D: Kviz Engine ✅ DONE

### D.1: Quiz Model
- `memio_world/quiz_models.py`
- Quiz, QuizQuestion, QuizAnswer, QuizAttempt, QuizResult
- Podržava: multiple choice, matching, sequence, true/false
- Auto-grading
- Difficulty progression (adaptivna težina)

### D.2: Teacher Dashboard
- Kreiranje kvizova iz HeritageCard setova
- Dodijeljivanje kao domaća zadaća
- Rezultati po učeniku / razredu
- CSV export ocjena

### D.3: Parent Dashboard
- Pregled djetetovog napretka
- Područja za poboljšanje
- Preporučeni sadržaj

---

## FAZA E: Demo UI

### E.1: PWA Shell
- Responsive, mobile-first
- Offline capable (Service Worker)
- Parchment/medieval vizualni stil

### E.2: 3 Demo Scenarija
1. Dijete bira bajku → čita na HR → prebacuje na DE → sluša audio
2. Učitelj kreira kviz iz bestiarij kartica → učenici igraju memory
3. Roditelj pregledava napredak → vidi koje jezike dijete uči

---

## METRIKE ZA CREATIVE EUROPE PRIJAVU
- 20+ višejezičnih priča
- 60+ heritage kartica (bestiarij + slovarica)
- 3 igre mehanike (memory, kviz, slagalica)
- 5+ EU jezika
- GDPR-compliant (parent consent flow)
- Europeana API integracija s 100+ cultural items
- Offline PWA

---

## ROUTING NA HEAVY QUEUE
- Svi AI/Europeana taskovi idu na `heavy` queue
- Ne smiju blokirati POS fiskalizaciju ili WhatsApp

## DISK PROCJENA
- 3 modela, max 10K redova u prvoj fazi
- Slike: thumbnailovi, ne full-res (Europeana hostira originale)
- Audio: max 20 priča × 3 jezika × ~2MB = ~120MB
- Ukupno: <200MB od 85GB slobodnih

## TROŠKOVI
- Europeana API: besplatan
- DeepSeek za prijevode: ~$0.05/dan
- Ukupno Sprint 1: <$5
