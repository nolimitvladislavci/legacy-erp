# LIMIT Connect — Marija Dry-Run Brief
# Datum: 08.04.2026. | Pripremio: Ivan Brtan

---

## ŠTO JE CILJ OVOG DANA

Marija Konjik kao ovlaštena knjigovođa i revizor verificira da je LIMIT Connect
spreman stati iza računovodstvenih procesa za 80+ klijentskih tvrtki.

Ovo nije demonstracija — ovo je profesionalna verifikacija.

---

## ŠTO JE GOTOVO (Sonnet + CC potvrđuju)

✅ Synesis import: 86 tvrtki, 33.270 partnera, ~110.000 knjižnih stavki
✅ Balans razlika: 0,01 EUR na godišnjoj razini (potvrđeno)
✅ NKD kodovi: 331 kod, 100% pokrivenost
✅ OIB validacija: aktivna na svim unosima
✅ Fiskalizacija: certifikati OK, fiskalizacija GO
✅ PDV obračun: automatizirani
✅ JOPPD: honorari modul s HR poreznim obračunom
✅ eRačun: posrednik "uz put" (post-launch)
✅ Konto knjiženje: camt.053 + CSV + MT940 parser
✅ Backup: pg_dump, 23s RTO, Backblaze B2, 543 tablice

---

## ŠTO MARIJA TREBA VERIFICIRATI

### 1. Knjiženje — točnost kontnog plana
- Otvoriti random 10 tvrtki iz importa
- Provjeriti da su konta ispravna (razred 1-8)
- Potražiti: porez na potrošnju, PDV poseban postupak, specifičnosti za sektor

### 2. Bilanca + RDG
- Jesu li početna stanja ispravna?
- Slaže li se bilanca?
- RDG logičan?

### 3. PDV obrazac
- Generirati PDV-S za test tvrtku
- Usporediti s Synesis izvodom za isti period

### 4. Fiskalizacija workflow
- Test narudžba → fiskalizirani račun
- OIB kupca → validacija
- Storno → ispravak

### 5. Provjera koja je PRONAŠLA RUPU ZADNJI PUT
→ Porez na potrošnju (asimiliran 100%)
→ Što još Marija vidi kao rizik?

---

## MARIJA, TVOJ INPUT JE POTREBAN ZA

1. **Scenarij A (639€/mj Konjik)** — decision needed
2. **Pricing za računovođe** — odvojen plan ili Professional?
3. **Go-live zeleno** — tvoj potpis je naš zeleni

---

## KORACI ZA DRY-RUN

1. Prijava: https://limit-connect.com/hr/login/
   Korisnik: [Ivan priprema testni login za Mariju]

2. Otvori test tvrtku: [Ivan definira koja]

3. Prođi redom kroz: Konto → Fakture → PDV → Fiskalizacija

4. Zabilježi sve što ne sjedi (bez filtriranja — sve, pa makar sitno)

5. Feedback do 09.04. → Ivan agregira → CC fix → 12.04. load test → 15.04. GO

---

## KONTAKT
Ivan Brtan | WhatsApp +385...
