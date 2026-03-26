# Haiku Invoice Compliance — 2026-03-27

# LIMIT Connect Invoice Compliance Analiza

## 1. TOP 3 COMPLIANCE RIZIKA

| Prioritet | Rizik | Opis | Preporuka |
|-----------|-------|------|-----------|
| **KRITIČAN** | Dokumentni nebalans | 15.325 dokumenata, ali samo 4 INVOICE + 2 PO (0,04% standardnih) | Audit workflow - gdje se R/URA/IRA fakturiraju? Mogući bypass sustava |
| **VISOK** | Otvoreni periodi bez otpremnica | 6× ožujak 2026 "open" sa 0 otpremnica | Duplikati ili zaglavljeni periodi - očisti DB, aktiviraj samo aktuelne |
| **SREDNJI** | Nema PDV segmentacije | items_25pct=0, items_5pct=0 | Nisu kategorizirani stavovi po PDV stopi - rizik za fiskalnu kontrolu |

## 2. BILLINGPERIOD → OTPREMNICA → ZBIRNA FAKTURA TIJEK

**STATUS: BLOKIRAN** ⛔

- Sve otpremnice = 0 (šest perioda)
- Bez otpremnica → nema zakonske osnove za zbrojnu fakturu
- Čini se da se koristi R/URA/IRA dokumenti kao zamjena za standardni proces

## 3. HITNE AKCIJE ZA ADMINA

1. **TODAY** - Očisti `billing_periods`: ukloni duplikate (6× ožujak 2026), zadrži samo trenutne periode
2. **TODAY** - Audit R/URA/IRA mapiranja: gdje se 7.395 R-ova računa kao fakture?
3. **48h** - Aktiviraj otpremnice ili formalno dokumentira zašto se koristi alternativni tijek
4. **48h** - Konfiguriraj PDV stavove (5%, 25%) za compliance izvještaje

**Zaključak:** Sustav radi, ali sa **nestandarnim dokumentnim tokom** koji zaobilazi otpremnice.
---

## ⚠️ KOREKCIJA — DODANO 2026-03-27

**Prethodna analiza je bila netočna** jer je uključila historijske Synesis uvezene podatke (15.325 dokumenata, 2011-2025) u compliance provjeru.

### Ispravno stanje baze

| | Broj | Napomena |
|---|---|---|
| Produkcijski Invoice (2026) | **236** | Pravi klijenti, pravi propisi 2026 |
| POS računi (2026) | **251** | Pravi klijenti |
| Synesis uvoz (2011-2025) | **15.325** | Historija, **ISKLJUČI iz provjera** |
| Otpremnice | **0** | Tijek nije još aktiviran (Sprint 1) |

### Ispravni zaključak
- "Dokumentni nebalans" koji je Haiku prijavio = **lažni alarm** — to su historijski Synesis podaci
- "Nema PDV segmentacije" = **djelomično točno** za produkciju ali nije hitno (236 dok.)
- BillingPeriod s 0 otpremnica = **točno**, ali to je planirano (Sprint 1 to rješava)

### Compliance provjere koje stvarno treba raditi (2026+)
1. Je li 236 prod. Invoice-a pravilno fiskalizirano?
2. Imaju li DE klijenti e-Rechnung od 2025?
3. PDV stope na artiklima klijenata koji su u prehrambenoj djelatnosti?
