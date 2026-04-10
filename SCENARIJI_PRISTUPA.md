# SCENARIJI PRISTUPA — Analiza i rješenja
# Kreirao: Sonnet — 2026-04-10

## STANJE U BAZI
- 350 korisnika ukupno
- 292 NEAKTIVNIH (od toga 300 syn_ Synesis importa)
- 288 bez email adrese
- 58 aktivnih

---

## SCENARIJ 1: Korisnik importan iz Synesis (syn_xxxxx)
### Što se dogodilo s Ivanom:
- Kreiran kao zaposlenik u Viskovic Bau putem Synesis importa
- is_active=False (namjerno — nije pravi korisnik sustava)
- Nema lozinku
- Email je bio tu, ali račun zaključan

### Problem:
Korisnik pokušava login → "Vaš račun je deaktiviran" — bez objašnjenja zašto

### Rješenje (kod):
Login poruka mora biti specifičnija:
```python
if not user.is_active:
    # Provjeri je li syn_ korisnik
    if user.username.startswith('syn_'):
        errors.append('Vaš korisnički račun još nije aktiviran. '
                      'Kontaktirajte administratora ili kliknite "Postavi lozinku".')
    else:
        errors.append('Vaš račun je deaktiviran. Kontaktirajte administratora.')
```

Link "Postavi lozinku" → šalje reset email → korisnik sam aktivira račun.

---

## SCENARIJ 2: Novi radnik kojeg je računovođa/admin dodala
### Flow koji mora raditi:
1. Admin dodaje email radnika u sustav
2. Sustav šalje **invite email**: "Vaš račun je kreiran. Kliknite za postavljanje lozinke."
3. Radnik klikne link, postavi lozinku → is_active=True automatski
4. Login radi

### Trenutno stanje: DJELOMIČNO RADI
- Email verifikacija postoji (accounts/email_verification.py)
- Ali syn_ korisnici nikad ne dobiju invite email

### Fix: Nakon Synesis importa, pošalji invite svim syn_ korisnicima s emailom:
```python
if email and not user_already_existed:
    send_invite_email(user)  # → "Postavi lozinku i aktiviraj račun"
```

---

## SCENARIJ 3: Firma otkaže pretplatu — korisnik želi arhivu
### Zakonska obaveza: 11 godina pristup računovodstvenim dokumentima (ZOR)

### Flow koji mora raditi:
- valid_until prođe → plan se downgradeava na 'archive_readonly'
- Korisnik se MOŽE logirati
- Vidi samo: Arhiva, Konto pregled, Fakture pregled (read-only)
- Ne može: kreirati nove dokumente, POS, PDV podnošenje

### Status: CC_TASK_ARCHIVE_READONLY.md napisan, čeka implementaciju

---

## SCENARIJ 4: Novi korisnik koji se sam registrira
### Trenutni flow (RADI):
1. /accounts/quick-register/ → unese podatke
2. Kreira se korisnik s is_active=True
3. Kreira se prazna firma (DRAFT OIB) — 14 dana trial
4. Login odmah radi
5. Email verifikacija ide u pozadini (ne blokira)

### Problem: DRAFT firma s OIB=DRAFTxxxxxxxx
Marija ne može u DRON2 onboarding čarobnjak koji traži pravi OIB.
Fix: nakon registracije → obavezni onboarding (tvrtka, OIB, adresa).

---

## SCENARIJ 5: Korisnik zaboravio lozinku
### Trenutni flow: RADI (password_reset postoji)
- /password-reset/ → email s linkom
- Problem: syn_ korisnici bez emaila ne mogu reset

---

## SCENARIJ 6: Računovođa koja ima 80 firmi
### Marija-model — trenutno:
- 1 login → vidi workspace → bira klijenta → radi
- Radi ali nema batch operacije

### Dolazi: CC_TASK_ACCOUNTANT_COCKPIT.md (post-launch)

---

## ŠTO TREBA POPRAVITI ODMAH (prije launcha)

### KRITIČNO #1: Login poruka za neaktivne syn_ korisnike
Jedna linija u core/views.py — 5 minuta posla.

### KRITIČNO #2: Invite email za syn_ korisnike s emailom
Kad Synesis import kreira korisnika s emailom → pošalji invite.
BEZ OVOGA: 288 zaposlenika ne zna da ima račun.

### POST-LAUNCH #1: Archive readonly plan
CC_TASK_ARCHIVE_READONLY.md — zakonska obaveza.

### POST-LAUNCH #2: Onboarding nakon registracije
DRAFT firma mora postati prava firma u 24h ili se obriše.
