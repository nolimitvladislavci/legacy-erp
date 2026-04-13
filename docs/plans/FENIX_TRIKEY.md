# FENIX — TriKey Authentication System

## Princip: 3 ključa za 1 bravu

LIMIT Connect koristi trostruku autentifikaciju — svaki korisnik ima 3 ključa,
a za pristup sustavu treba kombinaciju 2 od 3. Za osjetljive operacije trebaju sva 3.

## 3 Ključa

### 🔑 Ključ 1: PIN (6 znakova)
- Brz kao mBanking — 6 znamenki, poznato svima
- Hash: Django Argon2/PBKDF2 (ne plain text!)
- Rate limit: 5 pokušaja → 15min lockout
- Trivijalni PIN-ovi odbijeni (123456, 111111, etc.)
- Setup pri registraciji ili kroz /accounts/trikey/pin/setup/

### 🔑 Ključ 2: Passkey (WebAuthn/FIDO2)
- Biometrija: Face ID, Touch ID, Windows Hello
- Phishing-resistant — credential vezan za domenu
- 3× brži login od lozinke
- Anti-replay: sign_count tracking
- Setup: /accounts/trikey/passkey/options/ → /passkey/complete/

### 🔑 Ključ 3: Business Key (FINA + ePosrednik)
- FINA .p12 certifikat → SHA-256 fingerprint (ne pohranjujemo cert!)
- ePosrednik API ključ → HMAC-SHA256 hash
- Firma već ima oboje — nula dodatan trošak
- Najjači ključ — dokazuje poslovni identitet
- Setup: /accounts/trikey/business-key/

## Pravila pristupa

| Operacija | Potrebno | Primjer |
|---|---|---|
| Obični login | 2 od 3 ključa | PIN + Passkey |
| Pregled podataka | 1 ključ (nakon logina) | Već logiran |
| Fiskalizacija | 3 od 3 | PIN + Passkey + Business Key |
| Plaće / JOPPD | 3 od 3 | PIN + Passkey + Business Key |
| GDPR export | 3 od 3 | PIN + Passkey + Business Key |
| Promjena PIN-a | 2 od 3 | Passkey + Business Key |
| Brisanje firme | 3 od 3 + admin | Sva 3 + superadmin potvrda |

## Povrat pristupa

| Scenarij | Rješenje |
|---|---|
| Zaboravljen PIN | Business Key + email → novi PIN na email |
| Izgubljen uređaj (Passkey) | PIN + Business Key → registracija novog Passkey-a |
| Istekao FINA cert | PIN + Passkey → registracija novog certa |
| Sve izgubljeno | Kontakt support + OIB verifikacija + Marija odobri |

## OIB Auto-Fill

Pri registraciji:
1. Korisnik unese OIB
2. Sustav šalje na Sudski registar API (sudreg-data.gov.hr)
3. Automatski popunjava: naziv firme, adresa, grad, MBS, djelatnosti
4. Fallback: provjera u bazi partnera (33K+)
5. Cache: 24h (smanjuje API pozive)
6. Validacija: ISO 7064 MOD 11,10 checksum

## Lokacije u kodu

| Fajl | Što sadrži |
|---|---|
| accounts/trikey.py | TriKeyProfile model, OIB lookup, PIN generator |
| accounts/trikey_views.py | 8 views (login, PIN setup, Passkey, Business Key, status, recovery) |
| accounts/urls.py | 8 URL patterns pod /accounts/trikey/ |
| accounts/migrations/0015_trikeyprofile.py | Model migracija |

## Sigurnosne mjere

1. PIN: Argon2 hash, nikad plain text
2. FINA cert: samo fingerprint (SHA-256), cert se NE pohranjuje
3. ePosrednik key: HMAC-SHA256, originalni key se NE pohranjuje
4. Passkey: private key ostaje na uređaju, mi imamo samo public key
5. Rate limiting: PIN 5/15min, Business Key 3/1h
6. Replay protection: WebAuthn sign_count
7. Timing-safe comparison: hmac.compare_digest()

## Cjenik (ažuriran)

| Plan | Cijena | Ključna promjena |
|---|---|---|
| POS Besplatno | 0€ | — |
| Paušalac | 0€ | — |
| Micro | 9€ (bilo 10€) | Ispod psihološke granice 10€ |
| Starter | 19€ (bilo 22€) | Ispod 20€ |
| Računovođa | 39€ (NOVO) | Za knjigovodstvene servise, do 20 firmi |
| Professional | 49€ (bilo 69€) | Ispod 50€, konkurentnije od Minimax |
| Enterprise | 149€ (bilo 189€) | Ispod 150€ |
| Distributor | 359€ | — |
| Komunalno Osnovno | 990€ jednokratno (NOVO) | Ispod praga javne nabave |
| Komunalno Napredno | 1.990€ jednokratno (NOVO) | Ispod praga javne nabave |
