# BOXGRAM — Pilot Checklist

**Piloti:** Ljubeta (Novaki) & Pero Lapis  
**Datum:** 05.04.2026.  
**Goal:** Validacija feature-a prije General Availability

---

## PILOT 1: LJUBETA NOVAKI — Kennel profil

### Kontekst
Ljubeta je profesionalni uzgajivač pasa (kennel) iz Novaka sa više od 20 godina iskustva.
Ima ~15 reproduktivnih pasa + 40-50 štena godišnje za prodaju.

**URL:** https://memio.pet/kennel/ljubeta-novaki/

---

### P1.1 Kennel profil (Tvrtka, ne ljubimac)

**Setup zadaci:**
```
[ ] 1. Kreiraj User račun: ljubeta@memio.pet / lozinka_test_123
[ ] 2. U Boxgram settings: "Tip profila" = "Kennel" (nova opcija u PetProfile ili odvojena tablica)
[ ] 3. Upload Logo: kennel_logo.png (500x500px)
[ ] 4. Bio/Opis: "Kennel LJUBETA — 20 godina uzgoja s ljubavlju"
[ ] 5. Website: https://kennel-ljubeta.hr
[ ] 6. Lokacija: Novaki, HR
[ ] 7. Potvrdi email
```

**Test slučajevi:**
```
[ ] Prikaži kennel kao "Tvrtka" profil, ne kao obični ljubimac
[ ] Mogućnost masovnog dodavanja pasa (import iz CSV ili forme)
[ ] URL je /memio.pet/kennel/ljubeta-novaki/ (slug based)
[ ] Kennel se NE pojavljuje u regular "Životinje" feed-u (samo u Kennel directory)
[ ] Mogućnost dodavanja tekstualne biografije + fotografija kennelov (galerija)
```

---

### P1.2 Psi kao PetProfile

**Dodaj pse:**
```
Svaki pas je odvojena PetProfile stavka sa:
[ ] Ime: Rex, Luna, Šišo, ...
[ ] Vrsta: pas
[ ] Rasa: Njemački ovčar (FCI standard)
[ ] Datum rođenja: DD.MM.YYYY.
[ ] Avatar: [Foto psa]
[ ] Bio: "Kamp šampion 2024, otac 4 legla"

Ponavljaj za sve pse Ljubete.
```

**Test:**
```
[ ] Svaki pas ima vlastiti /memio.pet/ljubimac/{slug}/ URL
[ ] QR kod genira se u Celery task-u nakon kreiranja
[ ] QR kod je dostupan za download na profilu psa
[ ] Mogućnost "Promijeni vlasnika" na admin panelu
    → Promjena vlasnika trebala bi dodati novi PetProfileOwnershipHistory entry
    → Old owner može još editirati ako je memorial
```

---

### P1.3 Rodovnica (Pedigree)

**Setup:**
```
Za pse sa poznatim roditeljima:
[ ] Dodaj "Otac" i "Majka" polja u PetProfile
[ ] Oba bi trebala biti opciona (nullable)
[ ] Za Rexove štene: Otac=Rex, Majka=Luna

Očekivani rezultat:
┌─────────────────────┐
│ Štene (Pas)         │
│                     │
│ Otac: Rex           │
│ Majka: Luna         │
│ Rodjeno: 15.03.2025│
│                     │
│ [Otvori roditeljski│
│  profil]            │
└─────────────────────┘
```

**Test:**
```
[ ] Klikni na roditelja → Otvori parent PetProfile
[ ] Mogućnost reverse linkov (Rex vidi sve svoje štene)
[ ] Rodovnica se sprema u father_name, mother_name (tekstualna polja)
[ ] Mogućnost attacha "Pedigree dokumenta" kao EventMedia
```

---

### P1.4 Verificirani uzgajivač badge

**Setup:**
```
[ ] Kreiraj BreederProfile (iz memio_pet) za Ljubetu
    - account_type = 'breeder'
    - OIB: [enkriptovano]
    - is_cro_validated = True (ručno validacija)
    - validated_at = [datum]
[ ] Link PetProfile.owner sa User koji je Breeder
[ ] PetProfile.is_verified_breeder = True
```

**Test:**
```
[ ] Prikaži ✓ badge na Ljubetinom kennel profilu
    "Verificirani uzgajivač ✓ (Hrvatski registar)"
[ ] Na svakom Rexovom profilu vidljivo:
    "Uzgajivač: Ljubeta Novaki ✓"
[ ] Badge link → Love Ljubetinog kennel profila
[ ] Mogućnost filtriranja po "Samo verificirani uzgajivači" u search-u
```

---

### P1.5 Timeline za Ljubetu (kennel life events)

**Dodaj event-e:**
```
[ ] Rodjenje štena (15.03.2025):
    - Title: "Prvo leglo Rexove štene!"
    - Type: rodenje
    - Photos: 5 fotki novorodjene štene
    - Description: "4 štena, 3 mužjaka + 1 ženka"

[ ] Vet pregled (20.03.2025):
    - Type: vet
    - Notes: "Sve štene zdrava i aktivna"
    - Veterinar: Dr. Marko Horvat

[ ] Prodaja štena (15.04.2025):
    - Type: promjena_vlasnika
    - Description: "Prva tri štena pronašla novi dom"

[ ] Natjecanje (10.05.2025):
    - Type: natjecanje
    - Photos: Rex na выставици
```

**Test:**
```
[ ] Timeline prikazuje sve event-e cronološki (reverse)
[ ] Filteri rade: [Svi] [Rodjenja] [Vet] [Natjecanja]
[ ] Event detalji se otvaraju u modal-u
[ ] Hearts rate event-a (♥ broji srca)
[ ] Mogućnost editiranja vlastitih event-a
[ ] Mogućnost brisanja event-a (soft delete → is_public=False)
```

---

### P1.6 Import sa društvenih mreža

**Test scenario:**
```
Ljubeta ima Instagram profil @kennel_ljubeta sa 1.2k followers.
Sada želi importati svoje objave u Boxgram timeline.

[ ] Kreiraj test Instagram postove sa Boxgram URL-ovima
[ ] Paste URL u "Uvezi objavu" form
[ ] Backend pokušava oEmbed (ili scrape fallback)
[ ] Preview prikaži thumbnail + caption
[ ] Korisnik odabere event tip ("Ostalo") i potvrdi
[ ] Status: 'pending' (na čekanju) — samo vlasnik vidi
[ ] Vlasnik klikne "Objavi"
[ ] Event se pojavljuje na timeline-u
```

**Test checklist:**
```
[ ] oEmbed fetch uspješan (Instagram endpoint)
[ ] Thumbnail + caption preuzeti ispravno
[ ] SocialImport status='pending' dok nije odobreno
[ ] Promjena statusa na 'approved' → event je public
[ ] Mogućnost rejection → SocialImport.status='rejected'
```

---

### P1.7 Takmičenja sa psima

**Setup:**
```
Admin kreira takmičenja:
[ ] "Najmirnije ponašanje" (psima samo)
[ ] "Najljepši German Shepherd u gradu"
[ ] "Najbolji kennel godinu"

Ljubeta dodaje svoje pse u takmičenja:
[ ] Za svaku stavku: Rex, Luna, Šišo (kompetencija izbira)
[ ] Dodaj "Najbolja fotka" kao EventMedia
```

**Test slučajevi:**
```
[ ] Prikaži pse u leaderboard-u
[ ] Mogućnost glasanja (1-click IP limit)
[ ] Live vote count se ažurira
[ ] Ako je prijavljena: user-based vote, ako anoniman: IP-based
[ ] Rate limiting: 3 glasa/IP/sat, 5 glasova/device/dan
[ ] Turnstile CAPTCHA prikazan prije glasanja
```

---

### P1.8 QR markice

**Test:**
```
[ ] Klikni na Rex's profil → Skrolaj do "Identifikacija"
[ ] Prikaži QR kod (PNG 200x200px)
[ ] URL u QR: https://memio.pet/ljubimac/rex-pas-a1b2c3d4/
[ ] SHA-256 pečat vidljiv ispod QR-a
[ ] Mogućnost preuzimanja QR-a (PNG + SVG)
[ ] Mogućnost narudžbe fizičke markice (5 EUR)
```

**Test fizičke markice:**
```
[ ] Klikni [Naruči markicu]
[ ] Otvori modal sa opcijama
[ ] Odaberi: Plastična, Kvadrat 50x50mm
[ ] Dodaj tekst: "Rex — 0951234567"
[ ] Potvrdi narudžbu
[ ] Payment form (Stripe / PayPal)
[ ] Email sa tracking linkom
```

---

### P1.9 Mogućnost "Pronađi mog psa" na javnosti

**Scenario:**
```
Rex je pobjegao 5. travnja iz Ljubetinog vrta.
Ljubeta:
[ ] Kreiraj novi event: "IZGUBLJEN PSI"
    - Type: ostalo
    - Title: "IZGUBLJEN: Rex, njemački ovčar, Novaki"
    - Photo: Rex sa karakteristikalnim znakovima
    - Lokacija: Novaki, Hrvatska
    - Kontakt: 0991234567
[ ] Označi kao "URGENT" (crtvena boja?)
[ ] Mogućnost Share-a na FB, viber, SMS
```

**Test:**
```
[ ] Event se pojavljuje na javnom feed-u
[ ] Mogućnost filtriranja po "Izgubljeni" event-ima
[ ] Drugi korisnici mogu comentirati sa inforamcijama
[ ] Email notifikacija onih koji prate Rexov profil
```

---

## PILOT 2: PERO LAPIS — Pčelinjak

### Kontekst
Pero je poljoprivrednik sa OPG-om koji se bavi uzgojem pčela.
Ima ~30 košnica, članica je HAPIH-a i prodaje med na lokalnom tržištu.

**URL:** https://memio.pet/pcela/pcelinjak-pero-lapis/

---

### P2.1 Species='pcela' test

**Setup:**
```
[ ] Kreiraj User: pero@memio.pet
[ ] Nova PetProfile stavka:
    - Name: "Pčelinjak Pero Lapis"
    - Species: 'pcela' ✓ (treba biti dostupan)
    - Description: "30 košnica, ekološki uzgoj"
    - Avatar: Foto košnice
```

**Test:**
```
[ ] Species 'pcela' se sprema u bazu bez greške
[ ] Prikaži kao "Pčelinja zajednica" na UI-u
[ ] Avatar + Bio + Link na OPG website
[ ] Mogućnost dodavanja više košnica kao "children" entiteta
```

---

### P2.2 Košnice kao child entities

**Setup:**
```
Umjesto BeeHive modela (ako nije spreman), koristi PetProfile sa relationships:

Pero dodaje 5 košnica:
[ ] Košnica #1 (HR-PERO-001)
    - Owner: Pero
    - Parent: "Pčelinjak Pero Lapis"
    - Location: 45.2341, 16.5678
[ ] Košnica #2 (HR-PERO-002)
[ ] ... i tako dalje

Mogućnost organizacije u "grupe" ili "sektore".
```

**Test:**
```
[ ] Svaka košnica ima vlastiti slug
[ ] Timeline za svaku košnicu (event-i specifični za pčele)
[ ] Mogućnost "Prikazi sve košnice" → lista sa lokacijama na karti
[ ] Reverse link: Košnica → Pčelinjak (parent)
```

---

### P2.3 Event tipovi za pčele

**Novi event tipovi trebali bi:**
```
U EVENT_TYPE_CHOICES dodaj:
[ ] 'rojenje' — 'Rojenje / Skupljanje roja'
[ ] 'med_berba' — 'Berba meda'
[ ] 'zimovanje' — 'Zimovanje'
[ ] 'zagrada' — 'Zagrada (biljka)'
[ ] 'bolest' — 'Bolest / Tretman'
[ ] 'matrice' — 'Zamjena matice'
```

**Test:**
```
Pero dodaje event-e:
[ ] 15.04.2025 — Rojenje (Košnica #2)
[ ] 01.06.2025 — Zagrada na divljanom kestenu
[ ] 15.08.2025 — Berba meda (80kg sa 5 košnica)
[ ] 01.10.2025 — Priprema za zimovanje

[ ] Event timeline prikaže samo event-e sa 'pcela' species filter-om
[ ] Mogućnost dodavanja foto-a sa berbe meda
```

---

### P2.4 HAPIH registracija

**Setup:**
```
Pero unosi HAPIH podatke:
[ ] HAPIH reg. broj: HR-123456-PERO
[ ] Datum registracije: 10.01.2020.
[ ] Broj košnica: 30

Admin mogućnosti:
[ ] Import HAPIH XML (u budućnosti — integracija sa HAPIH bazom)
[ ] Manual unos u PetProfile.custom_fields ili BeeHive model
```

**Test:**
```
[ ] Prikaži HAPIH status na profilu
[ ] Badge: "Registriran kod HAPIH ✓"
[ ] Mogućnost export-a za HAPIH:
    [Izvezi za HAPIH] gumb → CSV download
    CSV sadrži: Hive #, Address, HAPIH #, Expires
```

---

### P2.5 Veterinarska certifikacija

**Test:**
```
[ ] Veterinar (Dr. Marko) unese certifikaciju za košnice:
    - Broj certifikata: HV-123456
    - Datum: 15.04.2025
    - Status: Sve je zdravo
    
[ ] Prikaži na Perovom profilu:
    "Posljednja veterinarska provjera: 15.04.2025 ✓"
[ ] Mogućnost dodavanja Health Record-a za bolesti/tretmane
```

---

### P2.6 "Izvezi za HAPIH" akcija

**Test scenario:**
```
Admin panel → BeeHive (ili PetProfile filtriran po pcela) → 
Actions: "Izvezi za HAPIH"

[ ] Generiraj CSV sa svim registriranim košnicama
[ ] Sadrži: Hive #, Address, HAPIH Reg #, Expiry date
[ ] Download kao hapih_export_2026_04_05.csv
[ ] Pero može submitati HAPIH-u za godišnju registraciju
```

---

### P2.7 Prodaja meda — Future integration

**Future scope (nije dio pilot-a, ali planiran):**
```
[ ] Timeline event: "Berba meda 2025 (80kg)"
[ ] Mogućnost dodavanja "Product listing":
    - Med bez dodataka
    - Količina: 500g, 1kg, 5kg
    - Cijena: EUR per kg
    - Dostava: Lokalno preuzimanje ili poštanska dostava
    
[ ] BARF Marketplace (RawFoodListing model) bi trebao biti prošireno
    na proizvode kao med, propolis, maточni mlijeko
```

---

### P2.8 Takmičenja sa pčelama (special)

**Setup:**
```
Admin kreiramo "Memorial" takmičenja za pčele:
[ ] "Najproduktivnija košnica godine"
[ ] "Najbolji med 2025"

Pero dodaje svoje košnice:
[ ] Košnica #1: "Med sa divljeg kestena — 45kg"
[ ] Košnica #3: "Med sa lipe — 38kg"
```

**Test:**
```
[ ] Mogućnost glasanja za košnice (ne samo ljubi mace)
[ ] Leaderboard prikazuje metriku: "Berba meda (kg)"
[ ] Filter takmičenja: [Svi] [Samo za pčele]
```

---

### P2.9 QR markica za košnicu

**Test:**
```
[ ] Svaka košnica ima QR kod
[ ] URL u QR: https://memio.pet/pcela/hr-pero-001/
[ ] Ako je košnica izgubljena / uhvaćena:
    - Neko skenira QR
    - Otvori Perov profil sa kontaktInfoManager-om
    - Može kontaktirati Pera: "Imam tvoju košnicu"
```

---

## General Test Coverage

### Backend validacija
```
[ ] Sve FK relationships radi (no 500 errors)
[ ] Cascade delete-i ispravljeni (test brisanja korisnika)
[ ] unique_together constraints radi (uključujući CompetitionVote fix)
[ ] Slug generiranje bez kolizija
[ ] QR code generiranje u Celery-u bez errors
[ ] oEmbed fallback radi (test sa real Instagram URL-om)
```

### Frontend responsiveness
```
[ ] Stranice dobre na mobile (375px width)
[ ] Timeline scrolling brz (lazy loading media)
[ ] Forms accessible (keyboard navigation)
[ ] Modali se zatvaraju (escape key, ✕ gumb)
```

### Performance
```
[ ] Timeline /memio.pet/ljubimac/{slug}/ učitava < 2s
[ ] Feed /api/boxgram/feed/ ne vraća više od 20 stavki po stranici
[ ] Database query-i optimizirani (select_related, prefetch_related)
```

### Security
```
[ ] CSRF tokeni na svim POST formama
[ ] XSS zaštita (escape HTML u bio/description)
[ ] GDPR compliance (mogućnost brisanja korisnika)
[ ] IP rate limiting na glasanju
[ ] Turnstile CAPTCHA radi
```

---

## Success Criteria

### Ljubeta (Kennel)
```
✅ Kennel profil sa >10 pasa
✅ QR kodovi za sve pse
✅ Verificirani uzgajivač badge
✅ Timeline sa 20+ event-a
✅ Učešće u 3+ takmičenja
✅ Izvezeni za HAPIH ready
```

### Pero (Pčelinjak)
```
✅ Species 'pcela' radi bez greške
✅ 5+ košnica registrirano
✅ HAPIH registracija vidljiva
✅ Veterinska certifikacija dokazana
✅ Timeline sa pčele-specifičnim event-ima
✅ Export za HAPIH radi
```

### Ukupno
```
✅ >500 radi bez greške
✅ <2s loading time na svim stranicama
✅ GDPR brisanje radi bez orphaned zapisa
✅ Turnstile CAPTCHA aktivna
✅ QR kod printanje i narudžba radi
✅ Dva pilot-a ne nađu greške koje mogu suspenzije korisnika
```

---

## Post-Pilot Actions

### Ako test uspješan
```
1. Deploy u produkciju
2. Javna objava: Boxgram je u beta, pridružite se!
3. Pozovi Ljubetu i Pera kao "founding members"
4. Feature zahtjevi za phase 2:
   - Komentari na event-e
   - Privatne poruke između korisnika
   - Marketplace za prodaju štena/meda
   - API za third-party aplikacije
```

### Ako se nađu greške
```
1. Bug triage i severity procjena
2. Priority fix ako je P0 (brisanje podataka, security)
3. Roadmap update za P1/P2 (UX, performance)
4. Razgovori sa Ljubetom/Perom za feedback
```

