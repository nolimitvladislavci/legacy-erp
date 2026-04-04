# NO LIMIT INKLUZIJA — Inkubator Plan
**Datum:** 2026-04-04 | **Status:** KONCEPT → čeka Marijin blagoslov
**Jedna rečenica:** NO LIMIT udruga postaje most između osoba s invaliditetom i digitalnog rada — kroz LIMIT Connect kao alat i pet hotel kao fizičko mjesto.

---

## TRI PROGRAMA

### PROGRAM 1 — "POSTANI AMBASADOR"
**Za:** osobe s invaliditetom koje mogu raditi od doma

| Stavka | Detalj |
|--------|--------|
| Tko | Osoba s invaliditetom (tjelesna, intelektualna, sluh, vid) |
| Što | Prodaje LIMIT Connect pretplate u svom gradu/mreži |
| Kako | WhiteLabel link, QR kod, jednostavan onboarding |
| Zarada | 15% komisija od svake aktivne pretplate — trajno |
| Podrška | Marija mentor (email/WhatsApp), Fenix AI asistent 24/7 |

**Što NO LIMIT udruga dobiva:**
- EU ESF+ sredstva za "digitalno zapošljavanje marginaliziranih"
- HZZ poticaj za zapošljavanje invalida (do 50% plaće)
- Medijsku priču koja otvara vrata

**U LIMIT Connect:** `BreederProfile` / `SalesLead` model → dodati `is_disability_ambassador = BooleanField`. Agent dashboard već postoji. Nema novog koda — samo flag i onboarding mail.

---

### PROGRAM 2 — "POSTANI KNJIGOVOĐA"
**Za:** osobe s invaliditetom, SSS ili više

| Stavka | Detalj |
|--------|--------|
| Što | Uči koristiti LIMIT Connect kao "Mini-Marija" |
| Zadaci | Proknjižava ulazne račune (Arhiva AI + human review), šalje podsjetnike, priprema PDV uz AI |
| Gdje | 100% online, od doma, bez fizičkih prepreka |
| Mentor | Marija Brtan, 2h/tjedan |
| Poslodavac | Konjik d.o.o. (formalni) ili ugovor o djelu |

**Zakonski okvir:**
- Zakon o profesionalnoj rehabilitaciji (NN 157/2013)
- HZZ: sufinanciranje plaće invalida do 70%
- EU ESF+ Fond: digitalna inkluzija
- Kvotni sustav: tvrtke s 20+ zaposlenih MORAJU imati 3% invalida

**Poslovni model koji se sam financira:**
1. Firma X mora imati invalida (zakonska kvota)
2. Ne može naći → plaća penale (alternativna kvota)
3. NO LIMIT nudi: "Mi rješavamo vašu kvotu. Plaćate 800 EUR/mj."
4. Od toga: 500 EUR → Ambasadoru, 300 EUR → NO LIMIT udruzi
5. HZZ refundira 350 EUR → **svi profitiraju**

**Ciljne tvrtke:** svaka firma s 20+ zaposlenih u Osječko-baranjskoj županiji (~400 tvrtki)

---

### PROGRAM 3 — "PET HOTEL POD NO LIMIT OKRILJEM"
**Socijalno poduzetništvo — fizičko mjesto**

| Stavka | Detalj |
|--------|--------|
| Entitet | NO LIMIT osniva socijalnu zadružu ili j.d.o.o. |
| Zaposleni | Osobe s invaliditetom (fizički rad) + osobe s lakim intelektualnim teškoćama (briga o životinjama) |
| Lokacija | Čepin/Osijek ili Gornji Mosti (Višnja Pevec — farma s ovcama, jelenima) |

**Tri revenue streama:**
1. **Smještaj kućnih ljubimaca** — 60 EUR/noć × 5 pasa = 300 EUR/dan
2. **Terapija** — pas + dijete s teškoćama = 150 EUR/h (EU fondovi)
3. **BARF dostava** — hotel naručuje janjetinu od OPG-a Kruljac → marketplace

**Zašto radi:**
- Terapeutski rad sa životinjama dokazan u rehabilitaciji
- EU LEADER fond + ESF+ za ruralni razvoj = do 85% sufinanciranja
- Čepin/Osijek — nema konkurencije u segmentu
- `memio.pet` evidencija = digitalni dnevnik svakog gosta
- LIMIT Connect POS + fiskalizacija = sve pod jednim krovom

**Potencijalni "Treći":** Višnja Pevec — već ima životinje i lokaciju

---

## LOVCI — EVIDENCIJA DIVLJAČI (zasebni CC task za tjedan dana)
- HR: ~75.000 lovaca, 1.200+ lovačkih udruga
- Zakon o lovstvu: svaki odstrjel se mora evidentirati
- CITES: međunarodni certifikat za određene vrste
- Lovačka udruga = umbrella (model već postoji)
- Evidencija odstrjela: vrsta, datum, lokacija, težina
- Godišnji plan vs realizacija (kvote)
- BARF veza: srna, vepar, zec, divlja patka → marketplace
- Cijena: Starter 9 EUR/mj → 10.800 EUR/mj ako 10% udruga

---

## EU FONDOVI — PRIMJENJIVI PROGRAMI

| Fond | Za što | Iznos |
|------|--------|-------|
| ESF+ 2021-2027 | Digitalna inkluzija, zapošljavanje invalida | do 100% za udruge |
| LEADER (EAFRD) | Ruralni razvoj, socijalno poduzetništvo, pet hotel | do 85% |
| HZZ poticaji | Sufinanciranje plaće invalida | do 70% plaće |
| Erasmus+ | Edukacija mentora, digitalna pismenost | do 100% |
| IPA fondovi | Prekogranična suradnja HR-SRB-HU | do 85% |

---

## FRONTEND VIZIJA — 10/10

### Ambasador Portal (nova sekcija u dashboardu)
- **Moj QR kod** — personaliziran, ispis na A4 ili share via WhatsApp
- **Moje zarade** — real-time komisija tracker (graf + brojka)
- **Moji klijenti** — ko se registrirao preko mog linka, status pretplate
- **Accessibility 10/10** — WCAG 2.1 AA, kontrast, screen reader, tab navigation, font scaling

### Inkluzija Dashboard (za NO LIMIT udrugu)
- **Ukupno Ambasadora** — mapa po gradovima
- **Ukupna zarada mreže** — mjesečni graf
- **Kvotni kalkulator** — firma unese broj zaposlenih → izračun koliko invalida treba + ponuda
- **EU fond tracker** — koji fond je otvoren, status prijave

### Pet Hotel Booking (javna stranica)
- **Kalendar slobodnih mjesta** — zeleno/crveno, mobile-first
- **Booking u 3 klika** — vrsta, datum, plati
- **Live cam** — vlasnik vidi ljubimca (opcionalno, Phase 2)
- **BARF meni** — dnevni jelovnik za goste (psi), naručuje se iz inventorija

### Accessibility kao brand
- **"Prvu stvar" testira osoba s invaliditetom** — QA tim = naši ambasadori
- **Dark mode + High contrast mode** — toggle u headeru
- **Voice navigation** — Fenix AI razumije govorne komande (Phase 2)
- **Svaka stranica ima aria-labels** — od danas

---

## TIMELINE

| Kada | Što | Tko |
|------|-----|-----|
| **Danas 04.04.** | NO_LIMIT_INKUBATOR_PLAN.md kreiran | CC Code |
| **Sutra 05.04.** | Marijin blagoslov za mentor rolu | Ivan → Marija |
| **07.04.** | HZZ Osijek kontakt — kvotni sistem upit | Ivan |
| **07-11.04.** | `is_disability_ambassador` flag + Ambasador onboarding mail | CC Code |
| **14.04.** | CC_TASK_LOVACKI_MODUL.md | CC Code |
| **15.04.** | NO LIMIT portal — inkluzija sekcija | CC Code |
| **Do 30.04.** | ESF+ prijava draft | Ivan + konzultant |
| **Q2 2026** | Pet hotel feasibility + lokacija | NO LIMIT + Višnja |

---

## KLJUČNI ZAKONSKI PROPISI

1. **Zakon o profesionalnoj rehabilitaciji i zapošljavanju osoba s invaliditetom** (NN 157/2013, 152/2014, 39/2018)
   - Čl. 8: Kvota 3% za poslodavce s 20+ zaposlenih
   - Čl. 10: Zamjenska kvota — penali ili alternativno ispunjenje
   - Čl. 15: Poticaji za zapošljavanje — HZZ refundacija

2. **Zakon o ustanovama** (NN 76/1993) — za socijalnu zadružu

3. **Zakon o socijalnom poduzetništvu** (NN 18/2018)
   - Čl. 5: Socijalni poduzetnik zapošljava min. 30% marginaliziranih

4. **Zakon o lovstvu** (NN 99/2018, 32/2019)
   - Čl. 62: Evidencija odstrjela obvezna
   - Čl. 65: Godišnji plan gospodarenja lovištem

---

## FENIX ASIMILACIJA

Ovo nije charity — ovo je **poslovni model koji rješava zakonsku obvezu tvrtki**.
NO LIMIT ne moli za donacije — nudi uslugu: "Mi vam ispunjavamo kvotu."
LIMIT Connect nije ERP za invalide — ali jest platforma na kojoj invalid može zarađivati.
Pet hotel nije samo smještaj — to je terapijski centar s digitalnim dnevnikom.
Lovci nisu niche — to je 75.000 korisnika s obvezom evidencije.

**Sve se vrti oko jedne platforme. Sve se plaća samo.**
