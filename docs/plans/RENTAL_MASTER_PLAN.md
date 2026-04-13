# IZNAJMLJIVAČ BORG — Master Plan
## "Broj 1 u HR" — Kompletan sustav za iznajmljivače + Marija kao Axis

**Datum:** 2026-03-24  
**Cilj:** Dominacija HR tržišta iznajmljivanja soba/stanova/apartmana

---

## ANALIZA KONKURENCIJE

### Što postoji u HR

| Igrač | Što radi | Cijena | Rupa |
|-------|----------|--------|------|
| **mVisitor** | OCR dokumenta → eVisitor | Paketi po check-inima | Samo eVisitor prijava, nema ERP |
| **inCheckin** | OCR → eVisitor, multi-account | 10 besplatnih, paketi | Samo prijava, nema računa, nema bukiranja |
| **PrijaviTuriste** | OCR → eVisitor + račun PDF | Paketi | Nema calendar, nema Mariju, nema ERP |
| **MyRent** | Channel manager + eVisitor + financije | Pretplata ~50€/mjes | Kompleksan, skup, bez HR računovođe integracije |
| **Booking.com/Airbnb** | Bukiranje | 15-17% provizija | Krade podatke gostiju, nema kontrole |
| **eVisitor (državni)** | Prijava turista | Besplatno | Ručni unos, bez OCR, bez računa, bez integracije |

### Naš moat koji nitko nema

```
mVisitor + inCheckin = samo OCR → eVisitor (bez računa, bez ERP)
MyRent = channel manager (skupo, kompleksno, bez Marije)
Mi = OCR + eVisitor + račun + boravišna pristojba + ERP + Marija kao računovođa
     + AI asistencija + online bukiranje + gost samo-prijava QR
```

**Ključna razlika:** Marija's klijent iznajmljivač sve radi u jednom sustavu.
Marija pristupa istom sustavu i jednim klikom ispiše račun, pregleda knjige, 
spremi u arhivu. Nitko drugi ne nudi ovo.

---

## ŠTO POSTOJI (rental modul — skeleton)

```
✅ Property model (soba/apartman/kuća, cijene, WiFi, QR, smart lock)
✅ Booking model (rezervacija, check-in/out, access_qr, boravišna pristojba)
✅ SeasonalPrice model
✅ HousekeepingLog model
✅ guest_self_checkin view (QR pristup)
✅ guest_access view
✅ calendar_view
```

```
❌ OCR dokumenta (nije implementiran)
❌ eVisitor XML export / API integracija
❌ Gost sam-bukiranja (public booking page)
❌ Račun za gosta (automatski iz bookinga)
❌ Evidencija prometa (Obrazac EP)
❌ Boravišna pristojba obračun/uplatnice
❌ TZ-2 obrazac generacija
❌ Marija dashboard (računovođa pristup)
❌ AI asistencija
❌ UI templates
```

---

## ARHITEKTURA SUSTAVA

```
IZNAJMLJIVAČ (Marko, ima 3 apartmana)
         │
    [LIMIT Connect Rental]
    ┌────────────────────────────────────────────────────┐
    │                                                    │
    │  OBJEKTI      KALENDAR      BUKIRANJE              │
    │  3 apartmana  Slobodno/Zauzeto  Direktno/QR        │
    │                                                    │
    │  GOST DOLAZI:                                      │
    │  1. Skenira osobnu → sve popunjeno automatski      │
    │  2. eVisitor prijava → 1 klik                      │
    │  3. Račun generiran automatski                     │
    │  4. EP evidencija ažurirana                        │
    │                                                    │
    │  AI ASISTENCIJA:                                   │
    │  "Ovaj tjedan imaš 3 dolaska. Podsjeti me..."      │
    │  "Boravišna pristojba za ovaj kvartal: X€"        │
    │  "Prihodujete X€ - prekoračujete 40k limit?"      │
    └────────────────────────────────────────────────────┘
         │
    MARIJA (računovođa)
    ┌────────────────────────────────────────────────────┐
    │  Vidi sve klijente iznajmljivače                   │
    │  Pregleda EP evidenciju                            │
    │  [Ispiši TZ-2] [Ispiši EP] [Pošalji u arhivu]     │
    │  Automatski u knjigovodstvo                        │
    └────────────────────────────────────────────────────┘
```

---

## 4 MISIJE — PARALELNO

| Agent | Misija | Fajl |
|-------|--------|------|
| CC Code | Modeli (Guest, GuestDocument) + OCR pipeline + eVisitor XML | CC_TASK_RENTAL_F1.md |
| Gemini | AI asistencija + PDV analiza + automatski upozorenja | GEMINI_TASK_RENTAL_F2.md |
| Sonnet | UI (check-in flow, gost-bukiranje, Marija dashboard) | SONNET_TASK_RENTAL_F3.md |
| Ivan | Marija onboarding + beta iznajmljivači | IVAN_TASK_RENTAL_F4.md |

---

## POSLOVNI MODEL

| Paket | Tko | Cijena |
|-------|-----|--------|
| Iznajmljivač Starter | 1-3 objekt | **9,99€/mjes** |
| Iznajmljivač Pro | 4-10 objekata | **19,99€/mjes** |
| Iznajmljivač Business | 10+ objekata | **39,99€/mjes** |
| Računovođa (Marija) | Neograničeno klijenti | **49€/mjes** |

**Provizija:** Marija dobiva 20% od svakog klijenta kojeg dovede.

**Usporedba s konkurencijom:**
- inCheckin: paketi za check-ine (50 check-ina = ~10€) — nema ERP
- MyRent: ~50€/mjes za channel manager — nema Mariju
- **Mi: 9,99€ s računovođom, ERP, eVisitor, računima** = win

---

## MILESTONE TRACKER

```
[ ] F1: Guest model + GuestDocument model
[ ] F1: OCR MRZ pipeline (Haiku Vision)
[ ] F1: eVisitor XML export funkcija
[ ] F1: Račun za gosta (automatski iz bookinga)
[ ] F1: EP Evidencija o prometu
[ ] F2: AI upozorenja (40k limit, boravišna, TZ-2 rok)
[ ] F2: Automatski obračun boravišne pristojbe
[ ] F2: TZ-2 obrazac generator
[ ] F3: Check-in flow UI (OCR + forma + 1 klik eVisitor)
[ ] F3: Gost self-check-in stranica (QR → forma → potvrda)
[ ] F3: Public booking page (slobodna/zauzeta + rezerviraj)
[ ] F3: Marija dashboard (svi klijenti + gumbi)
[ ] F4: 3 beta iznajmljivača iz Marija mreže
```
