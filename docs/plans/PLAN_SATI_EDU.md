# PLAN: Sati.ink → Edukativna platforma za djecu
**Datum ideje:** 02.04.2026. | **Status:** ZAMRZNUT do post-launch 15.04.
**Vođa:** Ivan Brtan

---

## Vizija

Online platforma za djecu (0-10 god) s:
- Slikovnice, priče, brojalice, slovarice — na svim jezicima (HR, DE, SI, EN, HU...)
- Čitaonica online (integracija s knjižnica modulom LIMIT Connect)
- "Spajanje umova" — društvene igre za djecu
- AI ocjenjivanje napretka (Gemini evaluator)
- Testovi i interaktivni sadržaj
- Praćenje talenata od vrtića

## Poslovni model
- Roditelji "potpisuju suradnju" — pristanak za praćenje razvoja djeteta
- Besplatni tier (osnovna slikovnica i priče)
- Premium (AI praćenje napretka, izvještaji za roditelje)
- Partnerstvo s vrtićima i školama (institucijski pristup)

## Tehnička osnova (već postoji)
- Domena: sati.ink
- Server: 37.27.248.86 (isti Hetzner)
- Codebase: /var/www/sati/razbibriga (Node.js + AI evaluator)
- Knjižnica modul: LIMIT Connect knjiznica/ app
- WeasyPrint: PDF slikovnice/sadržaj
- Gemini: AI ocjenjivanje

## Ime
"Razbibriga" → zadržati ili preimenovati (odluka Ivana)
Prijedlog: "Pametnica" / "Znalica" / ostaje Razbibriga

---

## ⚠️ PRAVNI PREDUVJETI (OBAVEZNO PRIJE LANSIRANJA)

### GDPR čl. 8 — Podaci djece su posebna kategorija
1. Pristanak mora dati roditelj/skrbnik (ne dijete)
2. Pristanak: specifičan, informiran, opoziv — ne klik na "Prihvati"
3. AI profil maloljetnika → posebno pravno mišljenje odvjetnika
4. Svaka EU zemlja ima lokalne dopune — HR + DE + SI posebno
5. Podaci djece: zabrana komercijalnog profiliranja

### Što treba napraviti PRIJE registracije prvog djeteta:
- [ ] Odvjetnik specijaliziran za EU digital law potpiše Privacy Policy
- [ ] AZOP notifikacija (HR) za obradu podataka djece
- [ ] Roditeljski ugovor o suradnji — pravno valjan, ne click-wrap
- [ ] Data Retention Policy za dječje profile
- [ ] Mehanizam za brisanje profila (GDPR čl. 17 — pravo na zaborav)

---

## Faze razvoja (post-launch)

**Faza 1 (Svibanj 2026):** MVP
- Landing page sati.ink s formom za "Zainteresirani roditelji"
- 10 slikovnica u PDF (WeasyPrint)
- Čitaonica: 3 jezik (HR, DE, EN)
- Roditeljski račun + pristanak

**Faza 2 (Lipanj 2026):** AI evaluacija
- Gemini ocjenjivanje čitanja/prepoznavanja
- Izvještaj za roditelje
- Igre: "Spajanje umova" (jednostavne)

**Faza 3 (Rujan 2026):** Institucionalni
- Partneri: vrtići, škole
- Praćenje grupe djece (educator panel)
- Višejezični sadržaj (HR, DE, SI, HU, CZ)

---

## Integracija s LIMIT Connect
- Knjižnica modul → čitaonica online (shared reader)
- Azil/Udruge → donacijska veza (udruge podupiru edukaciju)
- POS → roditeljske pretplate

---
*Zamrznut do 15.04.2026. — ne dirati do GO-LIVE LIMIT Connect*
