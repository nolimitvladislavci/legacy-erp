# PLAN: Bilježnički modul — Digitalizacija ureda javnog bilježnika
**Datum:** 02.04.2026. | **Pilot:** Šimašek, Osijek
**Status:** ZAMRZNUT do post-launch | **Prioritet:** Visok (toplim kontakt)

---

## Što HJK ima (ne diramo)
- **eNotar** — centralni HJK sustav (zatvoren, ne za komercijalne platforme)
- **NotarOnline** — remote ovjera (HJK platforma)
- **Registri** — oporuke, zadužnice, punomoći (HJK)
- **e-Ovrhe** — digitalizirani ovršni postupak (HJK/sud)

## Što HJK NEMA — naš prostor
```
CRM / upravljanje klijentima         ← mi
Template generator (pred-ovjera)     ← mi  
Online zakazivanje termina           ← mi
Automatski izračun tarife            ← mi
Fakturiranje + eRačun                ← mi
Klijentski portal                    ← mi
Arhiva skeniranih dokumenata         ← mi
Billing tracker po predmetu          ← mi
```

---

## 10 Najčešćih bilježničkih predložaka (Phase 1)

### 1. Ugovor o kupoprodaji nekretnine
Polja: prodavatelj (OIB, adresa), kupac (OIB, adresa), nekretnina
(katastarska čestica, ZK uložak, površina), cijena, rok isplate, datum

### 2. Ugovor o darovanju
Polja: darovatelj, obdarenik, predmet darovanja, eventualni uvjeti

### 3. Opunomoćenje (punomoć)
Polja: vlastodavac, opunomoćenik, opseg ovlasti, trajanje, predmet

### 4. Osnivački akt d.o.o. (nacrt)
Polja: osnivači (OIB), tvrtka, temeljni kapital, poslovodstvo, 
sjedište, djelatnosti (NKD) — LIMIT Connect ima 331 NKD kod ✅

### 5. Izjava o prihvatu/odricanju nasljedstva
Polja: nasljednik, ostavitelj, datum smrti, imovina

### 6. Zadužnica
Polja: dužnik (OIB), vjerovnik, iznos, rok, kamate, ovlast za ovrhu

### 7. Bjanko zadužnica
Polja: dužnik (OIB), maksimalni iznos, trajanje ovlaštenja

### 8. Suglasnost za putovanje maloljetnika
Polja: dijete (OIB, datum rođenja), roditelji, destinacija, 
pratnja, trajanje — GDPR: posebna kategorija ✅

### 9. Ugovor o doživotnom uzdržavanju
Polja: davatelj, primatelj, imovina, obveze, raskidni uvjeti

### 10. Izjava o priznavanju očinstva
Polja: otac (OIB), dijete, majka, datum, matičar (obavijest)

---

## Automatski izračun tarife

Zakon o javnobilježničkim pristojbama (NN 115/12, 139/12):
Tarifa ovisi o: vrsti radnje + vrijednosti predmeta

```python
# Primjer implementacije (Phase 2)
class BiljeznickaTarifa:
    OSNOVICE = {
        'kupoprodaja_nekretnine':  {'do_10k': 16.84, 'do_100k': 33.63},
        'opunomocenje':            {'osnovna': 10.00},
        'zaduznica':               {'postotak': 0.001, 'min': 10.00},
        'osnivanje_doo':           {'osnovna': 50.00},
        # + PDV 25% + javnobilježnička pristojba
    }
```

---

## Klijentski workflow

```
1. Klijent online odabere vrstu isprave
2. Ispuni predložak (podaci se validiraju — OIB modulo 11 ✅)
3. Uplati akontaciju (Stripe)
4. Odabere termin (online kalendar)
5. Dobiva PDF nacrta dokumenta
6. Dolazi kod Šimašeka s nacrtom
7. Šimašek ovjerava / solemnizira (eNotar — HJK sustav, ne naš)
8. Klijent dobiva skenirani akt u portal
9. eRačun ide automatski
```

---

## Šta Šimašek dobiva

- Klijent dolazi SPREMAN — nema pola sata prikupljanja podataka
- Nema tonera — sve digitalno
- Automatski izračun naknade i faktura
- eRačun za d.o.o. klijente
- Arhiva predmeta pretraživa
- Zakazivanje online — nema telefoniranja

**Procjena uštede:** 20-40 min po predmetu × ~10 predmeta/dan = 3-7 sati/dan

---

## Tehnička osnova (što već postoji)

```
WeasyPrint PDF generiranje      ✅
OIB modulo 11 validator         ✅ (upravo aktiviran)
NKD 331 kod (za d.o.o.)         ✅
eRačun modul                    ✅
Stripe naplate                  ✅
FenixScan OCR (skeniranje)      ✅
Arhiva / documents modul        ✅
```

Nedostaje:
- Appointment booking modul (kalendar)
- Tarifa kalkulator (ZJBPristojbe parser)
- Template forme (10 predložaka)

---

## Poslovni model za Šimašeka

- **Osnovni pristup:** 49 EUR/mj (sve funkcije, 1 korisnik)
- **Ili:** Referral model — Šimašek ovjerava Tier 4 dokumente iz Pravnog Validatora
  → dobiva % od svake ovjere koja dođe kroz LIMIT Connect

---
*Kontakt: Šimašek, Osijek — bivši klijent (potrošni materijal)*
*Poziv: nakon 15.04.2026.*
