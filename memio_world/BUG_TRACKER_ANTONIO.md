# MEMIO.WORLD — BUG TRACKER
> Tester: Antonio Brtan | Datum: 2026-04-18 | Zapisao: Sonnet
> Sve greške pronađene u realnom testiranju

---

## STATUS PREGLED

| Igrica/Feature | Status | Prioritet | Bilješka |
|----------------|--------|-----------|---------|
| Čovječe ne ljuti se — kocka | ✅ radi | — | |
| Čovječe ne ljuti se — figure | ❌ NE RADI | 🔴 HITNO | Figure se ne pomiču |
| Memorija | ❌ NE RADI na iPhone | 🔴 HITNO | Antonio testirao |
| Vješalica | ✅ radi | — | |
| Kviz — rezultati | ❌ NE RADI | 🔴 HITNO | Sve točno = 0 bodova |
| Mudrosti — životinje | ❌ POGREŠNI ODGOVORI | 🔴 HITNO | A=avion, B=balon (nije životinja) |
| Slovarica — font | ❌ Pedagoški propust | 🟡 | Uncial Antiqua ≠ štampano slovo |
| Slovarica — canvas feedback | ❌ Nema ohrabrenja | 🟡 | Zapisano CC_TASK |

---

## BUG 1 — ČOVJEČE: FIGURE NE FUNKCIONIRAJU
**Simptom:** Kocka baca broj, figure se ne pomiču.
**Vjerojatni uzrok:** JS event listener ne hvata klik na figuru, ili moveToken() funkcija ima grešku u logici pomicanja.
**Gdje gledati:** templates/memio_world/ludo_game.html → moveToken() i figuriClick()

## BUG 2 — MEMORIJA NE RADI NA iPhone
**Simptom:** Antonio testirao na iPhoneu — igrica ne funkcionira.
**Vjerojatni uzrok:** 
  - CSS grid/flexbox kompatibilnost na Safari/WebKit
  - Touch eventi vs Mouse eventi (iOS tretira drugačije)
  - `pointer-events` ili `cursor:pointer` ne reagiraju na iOS Safari
**Gdje gledati:** templates/memio_world/memory_game.html → touch eventovi

## BUG 3 — KVIZ: REZULTAT 0 KAD JE SVE TOČNO
**Simptom:** Sve točno odgovoreno → rezultat = 0.
**Vjerojatni uzrok:** 
  - Usporedba stringa vs integera (answer === vs answer ==)
  - Case sensitivity ('A' vs 'a')
  - Score se ne inkremntira (možda reset na kraju?)
**Gdje gledati:** templates/memio_world/ kviz template → scoreCheck()

## BUG 4 — MUDROSTI: POGREŠNE KATEGORIJE
**Simptom:** Pod "Životinje" — odgovor A=avion, B=balon (nisu životinje).
**Uzrok:** Seed podaci su krivi — pitanja/odgovori nisu sortirani po kategoriji.
**Gdje gledati:** management/commands/seed_* ili quiz_models.py → QuizQuestion

---

## REDESIGN — ČOVJEČE NE LJUTI SE
> Ivan Brtan — nova vizija igrice

