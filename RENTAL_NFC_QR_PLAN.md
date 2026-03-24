# RENTAL IDENTIFIKACIJA + NFC + QR — Master Plan
## "Selfie, čip, QR — trostruka zakonska osnova"

**Datum:** 2026-03-24  
**Istraživanje:** NFC tehničke mogućnosti, HR eOI zakon, selfie GDPR okvir

---

## BRUTALNA ISTINA O NFC

### Što je moguće BEZ posebnog čitača

| Metoda | Uređaj | Radi u web? | Zahtjevi |
|--------|--------|-------------|----------|
| OCR/MRZ skeniranje | Android + iOS | DA ✅ | Kamera + Haiku (već imamo) |
| Web NFC (NDEF) | Android Chrome 89+ | DA, ali ograničeno | NDEF tagovi — NE za dokumente |
| NFC ePassport čitanje | Android app | NE u browseru | Native app + ICAO library |
| NFC ePassport čitanje | iOS app | NE u browseru | CoreNFC Swift/RN |
| HR eOI certifikat | Svi | Djelomično | Certilia app + PIN |

**Ključna mina:** Web NFC API ne može čitati čip putovnice/osobne.
Čip koristi ISO 7816 APDU protokol. Web NFC radi samo s NDEF tagovima.
Za čitanje dokumentnog čipa OBAVEZNO treba native Android/iOS app.

**Ključna zaštita privatnosti:** Čip se ne može pročitati bez MRZ ključa.
Netko ne može "tiho" pročitati putovnicu u džepu. Mora biti otvorena pred čitačem.

---

## NAŠA STRATEGIJA: 3 SLOJA IDENTIFIKACIJE

### Sloj 1: MRZ OCR (odmah, web, 95%+ točnost)
- Haiku Vision čita MRZ s fotografije dokumenta
- Radi na svim uređajima, u browseru
- Dovoljan za eVisitor prijavu (trenutni standard u HR)
- Konkurenti (mVisitor, inCheckin) imaju samo ovo

### Sloj 2: Selfie kao consent dokaz (odmah, web, GDPR OK)
- Gost fotografira sebe s dokumentom u ruci
- Nije biometrija ako NE radimo face matching
- Jest biometrija ako DA radimo face matching → posebna kategorija GDPR
- Za rental v1: selfie = consent foto, ne biometrija
- Čuvamo 30 dana, automatski brišemo (GDPR)
- Pravna vrijednost: dokaz da je gost fizički prisutan i suglasan

### Sloj 3: QR na svakom koraku (odmah, web, besplatno)
- Svaki booking ima QR koji vodi na gost self-check-in stranicu
- QR u apartmanu → WiFi kod + pristupni kod brave
- QR na check-in papiru → potvrda rezervacije
- QR na računu → provjera autentičnosti
- QR na TZ-2 obrascu → Marija skenira i vidi klijentov status

---

## SELFIE — ZAKONSKI OKVIR HR

### Što zakon kaže za iznajmljivače

HR Zakon o ugostiteljskoj djelatnosti + Pravilnik o načinu vođenja popisa turista:
- Obveza: popis svih gostiju s podacima iz dokumenta
- Metoda: nije propisana — može biti ručno, OCR, foto
- GDPR: podaci se mogu prikupljati za zakonsku obvezu (čl. 6 st. 1 toč. c)
- Rok čuvanja: minimalno 2 godine

### Selfie consent protokol (bez biometrije)

```
Korak 1: Gost otvori QR link na mobitelu
Korak 2: Prikaže se GDPR consent forma (HR/EN/DE/IT)
          → "Vaši podaci prikupljaju se isključivo za zakonsku prijavu gostiju
             sukladno Zakonu o ugostiteljskoj djelatnosti"
          → Checkbox: Slažem se
Korak 3: Selfie s dokumentom (nije obavezno, ali preporučeno)
          → "Selfie je opcionalan i služi kao dokaz prisutnosti"
          → Bez face matching-a → nije biometrija
Korak 4: OCR dokumenta (Haiku MRZ scan)
Korak 5: Potvrda i eVisitor prijava
```

### Ako HOĆEMO biometriju (v3, strateški)

Za face matching (selfie ↔ foto na dokumentu):
- Treba eksplicitna suglasnost (ne samo checkbox)
- Treba obrada posebnih kategorija GDPR čl. 9
- Treba DPO procjena rizika (DPIA)
- Treba ROI analiza — je li to dodana vrijednost za iznajmljivača?
- Odgovor za v1/v2: ne — troškovi > koristi

---

## NFC REACT NATIVE APP — v2 PLAN

### Zašto React Native (ne Flutter)

- Naš tim poznaje JavaScript/React (LIMIT Connect koristi Django + vanilla JS)
- React Native dijeli dio JS logike s web frontom
- react-native-nfc-manager je najzreliji NFC library (MIT licenca)
- Jedna codebase → iOS + Android

### Arhitektura

```
[React Native App]
    ↓ NFC read (react-native-nfc-manager)
    ↓ ICAO BAC/PACE (mrtdreader library)
    ↓ Parsed DG1 (ime, br.dok., datum) + DG2 (foto)
    ↓ POST https://limit-connect.com/api/rental/nfc-checkin/
    ↓ Django backend: Guest.objects.create(...)
    ↓ QR generiran → JSON response
    ↓ App prikaže: "Check-in gotov ✓"
```

### Ključne biblioteke

```
react-native-nfc-manager     — NFC hardware pristup
@siteartwork/react-native-nfc-mrtd — ICAO 9303 parser
react-native-camera          — za MRZ OCR (fallback)
react-native-qrcode-svg      — QR generacija
```

### Vremenski plan

- Tjedan 1-2: React Native setup + NFC reader (proof of concept)
- Tjedan 3-4: Backend API endpoint (/rental/nfc-checkin/)
- Tjedan 5-6: iOS build + TestFlight beta
- Tjedan 7-8: Android beta
- Tjedan 9-10: Produkcija + App Store submit

**Napomena:** App Store zahtijeva posebno objašnjenje za NFC korištenje.
Key phrase: "For hospitality guest registration per Croatian Tourism Law"

---

## HR eOI CERTIFIKAT — v3 STRATEŠKA OPCIJA

### Što je to

HR eOI 2. generacije (od 2021) sadrži identifikacijski certifikat.
Uz Certilia app i PIN, gost se može identificirati kriptografski.
Pravna snaga: eIDAS Visoka razina (LoA High).

### Scenarij za rental

```
Iznajmljivač šalje link gostu (HR klijent s eOI)
Gost otvori link
Klikne "Identificiraj se s eOI"
→ Otvori Certilia app
→ Unese PIN1
→ Certilia vrati potpisani JWT s imenPrezime + OIB
→ LIMIT Connect provjeri potpis s HR NIAS certifikatom
→ Automatski popuni sva polja (bez tipkanja!)
→ eVisitor prijava jednim klikom
```

### Limitacije

- Radi samo za HR državljane s aktiviranom eOI
- Strani gosti (koji su većina turista u sezoni) ne mogu
- Certilia integracija zahtijeva MUP/AKD suglasnost i partnerstvo
- Vremenski okvir: 6-12 mjeseci za integraciju

**Zaključak:** Sjajan dugoročni cilj, ali nije blocker za v1.

---

## QR MASTER PLAN — odmah, bez kapitalnih ulaganja

### Gdje i zašto QR na svakom koraku

```
QR 1 — Na booking potvrdi (email)
        → Gost skenira i dobiva: detalji, check-in forma, WiFi, kontakt
        → Iznajmljivač vidi: tko je skenirao, kada

QR 2 — Na ulaznom QR posteru u apartmanu
        → Gost skenira i dobiva: WiFi, pristupni kod brave, kućni red
        → Samo za aktivne bookinge (provjera datum)

QR 3 — Na fizičnom računu (print)
        → Provjera autentičnosti računa
        → Link na PDF original

QR 4 — Na TZ-2 obrascu (Marija)
        → Marija skenira i vidi klijentov godišnji status
        → Prihodi YTD, broj kreveta, sljedeći rok plaćanja

QR 5 — Na eVisitor XML exportu
        → Link na Marija dashboard za ovaj gost
        → Brza provjera je li prijava ispravna
```

### Implementacija (CC Code, tjedan 1)

```python
# rental/qr_service.py

import qrcode
from io import BytesIO
import base64

def generate_booking_qr(booking) -> str:
    """QR za booking potvrdu — vode na gost check-in stranicu."""
    url = f"https://limit-connect.com/hr/rental/guest/{booking.access_qr}/"
    qr = qrcode.QRCode(version=1, box_size=10, border=2,
                       error_correction=qrcode.constants.ERROR_CORRECT_H)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1e3a5f", back_color="white")
    buf = BytesIO()
    img.save(buf, format='PNG')
    return base64.b64encode(buf.getvalue()).decode()

def generate_apartment_qr(rental_property) -> str:
    """QR poster za apartman — WiFi + info."""
    url = f"https://limit-connect.com/hr/rental/property/{rental_property.qr_code}/"
    # ... isti pattern

def generate_invoice_qr(rental_invoice) -> str:
    """QR za provjeru autentičnosti računa."""
    url = f"https://limit-connect.com/hr/rental/invoice/{rental_invoice.pk}/verify/"
    # ...
```

```python
# rental/views.py — novi view

def property_qr_landing(request, qr_code):
    """
    Gost skenira QR u apartmanu.
    Prikazuje: WiFi, pristupni kod, kućni red, info.
    Bez logina — public page.
    """
    prop = get_object_or_404(Property, qr_code=qr_code, is_active=True)
    
    # Provjeri je li gost u aktivnom bookingu
    from django.utils import timezone
    today = timezone.now().date()
    active_booking = Booking.objects.filter(
        rental_property=prop,
        check_in__lte=today,
        check_out__gte=today,
        status='checked_in',
    ).first()
    
    return render(request, 'rental/property_qr_landing.html', {
        'property': prop,
        'booking': active_booking,
        'show_wifi': active_booking is not None,
        'show_access_code': active_booking is not None,
    })
```

### QR plakat za printer (A5 format)

CC Code generira PDF plakat za svaki apartman:
- LIMIT Connect logo + naziv apartmana
- QR kod (velik, skenirljiv s 1m)
- "Skenirajte za informacije o boravku"
- HR / EN / DE tekst

```
┌─────────────────────────────┐
│  LIMIT Connect              │
│  Apartman Sunset            │
│                             │
│       ███████████           │
│       ██  █  ███            │  ← QR kod
│       ██████████            │
│       ███  ██ ██            │
│       ███████████           │
│                             │
│  Skenirajte za:             │
│  ✓ WiFi lozinku             │
│  ✓ Pristupni kod brave      │
│  ✓ Kućni red                │
│  ✓ Kontakt iznajmljivača    │
└─────────────────────────────┘
```

---

## KAMPANJA ZA RENTAL MODUL

### Poruka iznajmljivaču

> "Zaboravi papire. Gost skenira QR kod u hodniku,
> upiše podatke s mobitela — u manje od 3 minute
> automatski je prijavljen u eVisitor i račun mu ide na mail.
> Ti ne radiš ništa. Zakon je ispoštovan. Gost je zadovoljan."

### Ciljna publika 

1. **Marija's klijenti** (odmah) — 5-10 beta testiranja
2. **TZ newsletter** (travanj) — turistička zajednica Osijek?
3. **Iznajmljivač.hr, Cimerfraj.hr** (travanj) — edukativni članak
4. **Booking.com Host Community Croatia** (Facebook) — 12.000 članova
5. **HOK newsletter** (svibanj) — zajedno s Tax Wizard kampanjom

### Poruka za Booking.com hostsove

> "Koristite Booking.com? Mi smo JEDINI sustav koji:
> (1) Automatski puni eVisitor iz slike putovnice
> (2) Generira fiskalni račun odmah
> (3) Prati prihode prema 40.000€ paušalnom pragu
> 9,99€ / mjes — manje od jedne pive po gostu"

---

## PRIORITETI ZA IMPLEMENTACIJU

```
ODMAH (ovaj tjedan):
├── QR generacija (qr_service.py)
├── QR poster PDF generator
├── Property QR landing page (WiFi + info)
├── Booking QR potvrda (email)
└── GDPR consent forma na gost check-in

KRATKOROČNO (idući tjedan):
├── Selfie consent upload (bez face matching)
├── GDPR auto-delete (30 dana)
└── QR invoice verify page

SREDNOROČNO (6-8 tjedana):
├── React Native app proof of concept
├── NFC Android read (ICAO BAC)
└── Backend NFC endpoint

DUGOROČNO (12+ mjeseci):
├── HR eOI Certilia integracija
├── iOS NFC
└── Face matching (DPIA obvezna)
```
