# GEMINI_TASK_BOXGRAM_REVIEW.md
# Boxgram — Arhitektura + UX + Adversarial Review
# Prioritet: VISOK | Ekipa: Gemini
# Datum: 05.04.2026.

## KONTEKST
Boxgram je nova Django app unutar memio.pet / fina-connect projekta.
Filozofija: "Preslika vanjskog života u digitalni portal — od rođenja do zauvijek."

CC Code gradi backend (CC_TASK_BOXGRAM_CORE.md).
Tvoj zadatak: arhitektura review + UX spec + adversarial analiza.

Piloti koji čekaju:
- Ljubeta (Novaki) — uzgajivač pasa, kennel
- Pero Lapis — pčelar (OPG), košnice i matice
- 3 korisnika s waitliste memio.pet

Rok za review: prije nego CC Code završi B5 (migracije).

---

## G1 — Arhitektura Review

Provjeri CC_TASK_BOXGRAM_CORE.md modele i odgovori:

1. **PetProfile.slug** — predloži strategiju generiranja (ime-vrsta-uuid4[:8]?)
2. **CompetitionVote unique_together** — bug je prisutan: `entry__competition` nije validno za unique_together. Predloži ispravak.
3. **EventHeart unique_together** — jedan glas po IP je dovoljan ili treba i per-event?
4. **SocialImport → LifeEvent mapiranje** — je li OneToOne ispravan ili može jedna objava mapirati na više evenata?
5. **Tenant izolacija** — PetProfile ima tenant FK. Je li feed /api/boxgram/feed/ cross-tenant ili per-tenant?
6. **Memorial mode** — što se desi s EventHeart i CompetitionEntry kad is_memorial=True?
7. **qrcode library** — je li instalirana na serveru? Provjeri requirements.txt

---

## G2 — UX Specifikacija (za CC frontend)

### G2.1 — Registracija ljubimca (3 koraka)
```
Korak 1: Osnovno
  - Ime ljubimca (required)
  - Vrsta (dropdown — HR nazivi)
  - Pasmina (text, optional)
  - Datum rođenja (date picker, optional)

Korak 2: Priča
  - Bio tekst (max 300 znakova)
  - Avatar foto upload
  - Naslovna fotka (optional)

Korak 3: Vidljivost
  - Javni profil? (toggle, default: DA)
  - Verificirani uzgajivač? (checkbox — šalje na review)
  → Kreiraj profil → redirect na /ljubimac/{slug}/
```

### G2.2 — Timeline stranica (javni profil)
```
Header:
  - Cover foto (full width)
  - Avatar (overlap, krug)
  - Ime + vrsta + pasmina
  - Badge: [Vet ✓] [Uzgajivač ✓] [Pčelar ✓]
  - Bio
  - Statistike: X pratitelja · X srca · X događaja
  - Gumbi: [Prati] [Podijeli] [QR kod]

Timeline (vertikalni):
  - Filter tabovi: Sve | Vet | Nagrade | Socijalno | Memorijal
  - Svaki event: ikona, datum, naslov, opis, media, srca
  - "Dodaj događaj" FAB (samo vlasniku vidljivo)

Memorial mode:
  - Tamna tema (ne crna — topla siva)
  - "Rudi živi u našim srcima · 2019 — 2026"
  - Timeline zaključan za nove evente (osim Memorijal tipa)
  - "Ostavi sjećanje" forma za posjetitelje
```

### G2.3 — Import wizard (uvoz s društvenih mreža)
```
Ulaz: vlasnik lijepi URL (FB/IG/TikTok/YouTube)
System:
  1. Fetch oEmbed metadata
  2. Prikaži preview (thumbnail, caption, datum)
  3. "Za kojeg ljubimca je ovo?" → picker
  4. "Koji tip događaja?" → dropdown
  5. "Datum objave" → auto-fill ili manual
  → Spremi → SocialImport(status=pending)
  → Vlasnik odobrava u dashboard inbox-u
```

### G2.4 — Takmičenje
```
Lista takmičenja:
  - Karta: naslov, rok, broj prijavljenih, status
  - Filter: aktivna / završena / moja vrsta ljubimca

Glasanje:
  - Kartica ljubimca: foto + ime + broj srca
  - Jedan klik → glas (bez registracije, IP limit)
  - Animacija srca pri glasanju
  - Live leaderboard (5 sekundi refresh)
  - Odbrojavanje do kraja

Pobjeda:
  - Automatski trofej na profilu
  - "🏆 Pobjednik: Najslađe štene travanj 2026."
  - Share gumb → WhatsApp/FB
```

### G2.5 — QR markica
```
Stranica: /ljubimac/{slug}/qr/
  - Prikaz QR koda (512x512)
  - Uputa: "Isprintaj i stavi na ogrlicu"
  - Download PNG gumb
  - Opcija narudžbe fizičke markice (5 EUR)
    → forma → email potvrda → ručna obrada za MVP
```

---

## G3 — Pilot profili — što treba biti gotovo za Ljubetu i Peru

### Ljubeta (uzgajivač pasa):
```
Tip: Uzgajivač / Kennel
Treba:
  - Kreirati kennel profil (firma, ne ljubimac)
  - Dodati pse (svaki pas = PetProfile)
  - Rodovnica po psu (LifeEvent tip: rodenje + parents)
  - Verificirani uzgajivač badge
  - Javni URL: memio.pet/kennel/ljubeta-novaki
```

### Pero Lapis (pčelar):
```
Tip: OPG pčelar
Treba:
  - species='pcela' (Pčelinja zajednica) mora raditi
  - Košnica = PetProfile (ime: "Košnica 1", "Matica Ana")
  - LifeEvent tipovi relevantni za pčele:
    leglo → Rojenje
    vet → Pregled košnice / liječenje varoze
    nagrada → Medalja na sajmu meda
  - Javni URL: memio.pet/pcela/pcelinjak-pero-lapis
```

---

## G4 — Adversarial Review

Pronađi i dokumentiraj sljedeće rizike:

### 4.1 Fake glasovi na takmičenjima
- IP spoofing? VPN abuseovi?
- Predloži: rate limit + honeypot + Cloudflare Turnstile
- Koliko glasova po IP po danu je razumno?

### 4.2 GDPR — brisanje vlasnika
- Vlasnik traži brisanje računa (GDPR čl. 17)
- Što se desi s PetProfile-om? S LifeEvent-ima?
- Prijedlog: anonymize owner FK, profil ostaje ako je_public=True
- Memorial profili: posebna kategorija (baština, ne osobni podaci)

### 4.3 Privatnost mrtvih ljubimaca
- Tko može editirati memorial profil?
- Može li novi vlasnik preuzeti profil?
- Što ako vlasnik i ljubimac umru istovremeno (stariji vlasnici)?

### 4.4 FB/IG API nestabilnost
- Meta mijenja API bez najave
- Fallback plan: manual URL import uvijek dostupan
- oEmbed je stabilniji od Graph API — prioritiziraj

### 4.5 Sadržaj koji ne smije proći
- Okrutnost prema životinjama
- Ilegalni uzgoj (bez dozvole za određene vrste)
- Zaštićene vrste (npr. egzotične ptice)
- Prijedlog: report dugme + moderator queue

### 4.6 Pčele — regulativa
- HAPIH (HR) zahtijeva registraciju košnica
- Je li Boxgram u sukobu ili komplementaran?
- Prijedlog: "Izvezi za HAPIH" gumb (CSV format koji prihvaćaju)

---

## G5 — Internacionalizacija (priprema)

Pripremi listu svega što treba prevesti za fazu EU:
- Species choices (HR → EN, DE, SLO, IT)
- Event type choices
- UI stringovi (sve label-e u templateima)
- URL slug strategija (hr/pas/rudi vs en/dog/rudi)

Preporuka za implementaciju: django-modeltranslation ili gettext?

---

## G6 — Finalni output Geminija

Dostavi:
1. **BOXGRAM_ARCHITECTURE_REVIEW.md** — odgovori na G1 pitanja
2. **BOXGRAM_UX_SPEC.md** — finalizirana UX spec (G2)
3. **BOXGRAM_RISK_REPORT.md** — adversarial nalazi (G4)
4. **BOXGRAM_PILOT_CHECKLIST.md** — što mora raditi za Ljubetu i Peru

Format: Markdown, bez suvišnih uvoda. Direktno na point.
