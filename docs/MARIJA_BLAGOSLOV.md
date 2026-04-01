# MARIJA_BLAGOSLOV — Potvrda usklađenja kontnog plana

**Datum:** 02.04.2026.
**Zadatak:** CC_TASK_USKLADENJE_A — Ispravka account_type mappinga iz Synesis importa

---

## Što je napravljeno

Automatskim importom iz Synesis MDB-a, **2.514 konto računa** (od ukupno 5.170) imalo je pogrešno klasificirani tip računa. Ovo je utjecalo na prikaz u izvještajima (RDG, bilanca po tipovima), ali **nije utjecalo na iznose — sve bilance su bile i ostale D=P balansirane**.

### Ključne ispravke:
1. **Klasa 7 (Prihodi):** Promijenjeno iz `income` u `revenue` — ispravno za RDG
2. **Klasa 8 (Rezultat):** Dobit/Gubitak (800-804) promijenjeno u `equity`, Porez (803) ostaje `expense`
3. **Klasa 9 (Kapital):** Dugoročne obveze (94x-96x) promijenjeno u `liability`
4. **DE firme:** Viskovic Bau, Dado Haustechnik — primijenjeno SKR03 mapping

### Zahvaćene firme:
- **90 HR firmi** — 2.420 konto računa ispravljeno
- **3 DE firme** — 94 konto računa ispravljeno

---

## Verifikacija

- [x] Bilanca D=P za svaku firmu — **SVE BALANSIRANO**
- [x] Nema negativnih iznosa u knjiženjima
- [x] Nema dupliciranih temeljnica
- [x] 17 automatskih testova — **SVI PROLAZE**
- [x] Idempotentnost — ponovljeno pokretanje ne mijenja ništa
- [x] Synesis import skripta ažurirana za buduće importe

---

## Potpis

Potvrđujem da sam pregledala gorenavedene promjene i da su u skladu s
HR RRF kontnim planom i DE SKR03 standardom.

**Marija Brtan**
Ovlaštena računovotkinja
Konjik d.o.o.

Potpis: ____________________________

Datum: ____________________________

---

*Dokument generiran automatski. Za pitanja kontaktirati tehničku podršku.*
