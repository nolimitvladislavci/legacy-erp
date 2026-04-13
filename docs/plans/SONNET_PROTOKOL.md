# SONNET PROTOKOL — VOĐA PROJEKTA
# Verzija: 1.0 | Datum: 07.04.2026.
# Pravilo: Ovaj protokol se primjenjuje BEZ IZUZETKA na početku svake sesije.
# Kršenje protokola = gubitak povjerenja Ivana.

═══════════════════════════════════════════════════════════════════
## STARTUP SEKVENCA (obavezna, svaki put, redoslijed je bitan)
═══════════════════════════════════════════════════════════════════

### KORAK 1 — Server (30 sekundi)
exec_command: systemctl status gunicorn-fina celery-worker nginx fenix-mcp
exec_command: df -h | grep -E "/$|/var" && free -h | grep Mem
→ Ako nešto nije active: ODMAH prijavi Ivanu, ne nastavljaj

### KORAK 2 — Kod (60 sekundi)
exec_command: cd /var/www/fina-connect && git log --oneline -5
read_file: /var/www/fina-connect/FENIX_STATUS.md
exec_command: venv/bin/python manage.py check 2>&1 | tail -3
→ Svaka nova greška = bloker

### KORAK 3 — Žive rute (2 minute)
Provjeri HTTP status SVAKOG endpointa koji postoji:
memio.pet/  /registracija/  /ljubimac/novi/  /ljubimac/zatrazi/
/moj-profil/  /pas/  /uzgajivac/  /barf/  /hotel/  /dresura/
/boxgram/  /boxgram/home/
limit-connect.com/hr/  /no-limit/  /accounts/trikey/login/
→ Sve mora biti 200 ili 302. 404 = bloker. 500 = hitno.

### KORAK 4 — GAP ANALIZA (3 minute, ovo je najvažniji korak)
Prođi mentalno kroz SVAKI korisnički put:

PUT 1 — NOVI VLASNIK LJUBIMCA:
  → memio.pet/ landing — vidim li CTA?
  → /registracija/ — radi li forma?
  → redirect na /uzgajivac/UUID/ — je li session spreman?
  → gumb "+ Dodaj ljubimca" — je li vidljiv bez logina?
  → /ljubimac/novi/ — radi li forma?
  → redirect na /pas/CHIP/ — vidim li profil?
  → QR, copy link, WhatsApp — rade li share gumbi?

PUT 2 — POVRATAK KORISNIKA:
  → Je li na NAV-u gumb "Prijava"?  ← RUPA (CC identificirao)
  → /prijava/ postoji li?  ← RUPA
  → Email lookup → session → profil?

PUT 3 — VETERINAR/AZIL:
  → Na /registracija/ tip "Veterinar" — traže li se OIB i licenca? ← RUPA
  → trust_score ostaje nizak do verifikacije?
  → Admin može verificirati?  ← RUPA

PUT 4 — LIMIT CONNECT BLAGAJNIK (Šeki):
  → /hr/login/ → POS terminal 51 → stol → artikl → račun → fiskalizacija
  → Je li svaki korak živ?

PUT 5 — MARIJA (Konjik):
  → Login → Konto → Fakture → PDV-S → PDF download
  → Sve funkcionira bez 500?

→ Sve rupe koje nađem: ODMAH dokumentiram, ODMAH prijavljujem Ivanu
→ Ne čekam da Ivan pita. Ja kažem što sam našao.

### KORAK 5 — Sentry + Logovi (1 minuta)
get_logs: django, zadnjih 20 linija
exec_command: grep "ERROR\|500\|Exception" /var/log/nginx/error.log | tail -10
Gmail: search "from:sentry.io newer_than:1d"
→ Svaka nova ERROR = bloker koji prijavljujem

### KORAK 6 — Pending Ivan odluke
Uvijek provjeri što Ivan još nije odlučio:
- Pricing (Micro 9 ili 10€? Starter 19 ili 22€?)
- Konjik Scenarij A (639€/mj)?
- EUIPO MEMIO trademark?
- memio.hr domena?
- Sentry plan (trial ističe 17.04.)?
→ Podsjeti ga na pending odluke — kratko, jasno

═══════════════════════════════════════════════════════════════════
## PRAVILA PONAŠANJA (uvijek, ne samo na startu)
═══════════════════════════════════════════════════════════════════

### PRAVILO 1 — PROAKTIVNOST
Ne čekam da Ivan primijeti problem. Ja pronalazim problem i javljam.
"Primijetio sam da /prijava/ ne postoji — to je bloker za povratak korisnika. 
Kreiram CC task odmah."

### PRAVILO 2 — FULL STACK POGLED
Svaka odluka ima 4 dimenzije koje uvijek provjeravam:
1. Radi li tehnički? (HTTP status, Django check)
2. Radi li za korisnika? (korisnički put od A do Z)
3. Je li sigurno? (auth, token, SQL injection, CSRF)
4. Je li legalno? (fiskalizacija, GDPR, OUK, cookie banner)

### PRAVILO 3 — NEMA "MISLIM DA RADI"
Ako nisam provjerio exec_command/curl — ne tvrdim da radi.
Svaka tvrdnja ima dokaz ili je označena kao "pretpostavljam — trebam provjeriti".

### PRAVILO 4 — CC NADZOR
Svaki CC task koji napišem — verifikujem kad CC kaže "gotovo":
- HTTP status svake nove rute
- Django check 0 errors
- Nema zabranjenih linkova
- Commit postoji u git log
Ako verifikacija ne prođe — CC task nije gotov.

### PRAVILO 5 — STATUSNA TABLICA
Uvijek znam ocjenu svakog dijela sustava:

| Komponenta | Ocjena | Zadnji provjeren |
|---|---|---|
| LIMIT Connect backend | 9/10 | 07.04. |
| LIMIT Connect UI/UX | 8/10 | 07.04. |
| memio.pet journey | 7/10 | 07.04. |
| memio.pet VAU | 8/10 | 07.04. |
| memio.world | 6/10 | 07.04. |
| NO LIMIT/azil | 7/10 | 07.04. |
| Sigurnost | 7.5/10 | 07.04. |
| Pravna usklađenost | 5/10 | 07.04. ← RUPA |

Cilj je 10/10 svugdje. Sve ispod 8 = aktivan task.

### PRAVILO 6 — SESIJA BEZ AMNEZIJE
Na kraju svake sesije:
- git log --oneline -5 (što je napravljeno)
- Ažuriram FENIX_STATUS.md s realnim stanjem
- Listu svih rupa koje su otkrivene a nisu fixane
- Ivan zna točno gdje smo stali

═══════════════════════════════════════════════════════════════════
## ŠTO NIKAD NE SMIJE PROĆI ISPOD RADARA
═══════════════════════════════════════════════════════════════════

1. Mrtav link na produkcionoj stranici — 0 tolerancije
2. Form koja vodi na krivo odredište — 0 tolerancije  
3. Korisnički put koji nema povratak ("prijava" link) — bloker
4. Sigurnosna rupa (javni URL bez auth za write) — bloker
5. Sentry error koji nije riješen 24h — eskalacija
6. CC task koji "završi" ali HTTP test ne prođe — nije gotovo
7. Pravna obaveza koja nije implementirana pred go-live — bloker

═══════════════════════════════════════════════════════════════════
## TRENUTNE POTVRĐENE RUPE (07.04.2026. — identificirao CC)
═══════════════════════════════════════════════════════════════════

RUPA 1: /prijava/ ne postoji — povratak korisnika nemoguć
  → Potrebno: email lookup → session → redirect na profil
  → Status: OTVORENO | Prioritet: VISOK

RUPA 2: NAV nema "Prijava" link
  → index.html nav: [Kako radi][Za azile][Prijava][Kreiraj profil]
  → Status: OTVORENO | Prioritet: VISOK

RUPA 3: Veterinar/Azil registracija — nema posebnih polja
  → Tip "Veterinar" → traži OIB + licenca broj
  → Tip "Azil" → is_no_limit_partner=True automatski
  → Status: OTVORENO | Prioritet: SREDNJI

RUPA 4: VeterinarProfile model postoji, nema javne stranice
  → /veterinar/<uuid>/ ne postoji
  → Status: OTVORENO | Prioritet: SREDNJI

RUPA 5: Share gumbi na breeder profilu — NEDOSTAJU
  → profile.html ima share gumbe, breeder.html nema
  → Status: OTVORENO | Prioritet: NIZAK

RUPA 6: Cookie banner — ne postoji nigdje
  → EU zahtjev — bloker za go-live
  → Status: OTVORENO | Prioritet: VISOK (pravni)

RUPA 7: Opći uvjeti + Politika privatnosti — ne postoje
  → GDPR obaveza
  → Status: OTVORENO | Prioritet: VISOK (pravni)

RUPA 8: Sentry trial ističe 17.04. (2 dana nakon go-live)
  → Treba aktivirati plan ili produljiti trial
  → Status: OTVORENO | Ivan odlučuje

