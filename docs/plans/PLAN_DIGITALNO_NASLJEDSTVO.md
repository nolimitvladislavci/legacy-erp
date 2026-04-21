# PLAN: Digitalno Nasljeđe — memio.pet
**Datum:** 2026-04-21 | **Autor:** CC + Ivan Brtan | **Status:** IN PROGRESS

## Srž ideje
Svaki ljubimac ima naslijeđene osobine, titule i povjerenje prethodnih generacija.
Svaki vlasnik ostavlja digitalnu oporuku. Svaki uzgajivač gradi dinastiju.
→ "Nama se vjeruje" nije slučajno — grade se generacijama.

## Novi modeli (migration 0013)
1. `HeritageTrait` — genetska obilježja, zdravstvene potvrde, titule (nasljedivo)
2. `LegacyBequest` — digitalna oporuka: tko nasljeđuje profil i pod kojim uvjetima
3. `DigitalHeritage` — agregatni zapis naslijeđa (OneToOne → AnimalProfile)

## AnimalProfile proširenje
- `father_chip` CharField — chip otca (soft ref, ne FK)
- `mother_chip` CharField — chip majke (soft ref, ne FK)
- `generation_number` IntegerField — koja generacija u uzgoju

## Trust Score — nova dimenzija Heritage (+15)
- Genealogija dokumentirana ≥ 1 generacija: +5
- Genetski testovi / health clearance: +5
- Prvak u rodovnici (HeritageTrait.type=champion): +3
- Legacy Bequest kreiran: +2

## URL-ovi
- `/pas/<chip>/naslijede/` — stranica digitalnog nasljeđa
- `/naslijede/` — showcase svih heritage profila
- `/api/heritage/<chip>/` — JSON za genealoško stablo

## Template izmjene
- Novi: `heritage.html` — genealoško stablo + traits + bequest
- Extend: `profile.html` — sekcija Nasljeđe (badge + link)
- Extend: `breeder.html` — Heritage Dynasty section

## Patent
- `/var/www/fina-connect/docs/patents/PATENT-MPH-001.md`
- 4 patentna zahtjeva (method, system, process, data structure)
- Prijaviti: Konjik d.o.o. → EUIPO / DPZA

## Commit plan
1. `feat(memio-pet): digitalno nasljeđe — modeli + migracija`
2. `feat(memio-pet): heritage trust score + views + urls`
3. `feat(memio-pet): heritage templates — stablo + profil + breeder`
4. `docs(patent): PATENT-MPH-001 digitalno nasljeđe živih bića`
