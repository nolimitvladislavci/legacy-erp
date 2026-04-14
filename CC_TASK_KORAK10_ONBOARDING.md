# CC TASK — KORAK 10: Onboarding Provjera
**Executor: CC Code | Koordinator: Opus**

---

## CILJ
Nova firma → aktivni korisnik za < 30 minuta bez tehničke pomoći.
Svaki korak registracije i postavljanja mora raditi BEZ GREŠKE.

## PRAVILA
- Čitaj CLAUDE.md i FENIX_STATUS.md prije rada
- Commitaj svaki logički blok zasebno
- manage.py check mora proći na kraju
- NE diraj gunicorn (nemoj systemctl)
- TESTIRAJ svaki flow programski (Django test client ili management command)

---

## ZADACI

### 10.1 — Registration Flow Audit
- Pronađi registration view (accounts app ili gdje je)
- Prođi CIJELI flow programski:
  1. GET /register/ (ili /accounts/register/) — mora vratiti 200
  2. POST s validnim podacima (email, password, ime) — mora kreirati usera
  3. Email verifikacija (ako postoji) — provjeri flow
  4. Login nakon registracije — mora raditi
- Svaki bug = fix odmah + test

### 10.2 — Company Setup Flow
- Nakon registracije, korisnik mora moći:
  1. Kreirati novu firmu (OIB, naziv, adresa)
  2. Uploadati logo
  3. Postaviti IBAN
  4. Aktivirati fiskalizaciju (ako je HR)
- Provjeri da OIB validacija radi (ISO 7064)
- Provjeri da duplikat OIB baca grešku
- Svaki bug = fix odmah

### 10.3 — Prva Faktura Flow
- Korisnik u novoj firmi:
  1. Kreira partnera (kupca)
  2. Kreira fakturu
  3. Dodaje stavke
  4. Generira PDF
  5. Šalje na email (ili client portal link)
- Provjeri da PDF izgleda ispravno (nema praznih polja, ima logo)
- Provjeri client portal: kupac može prihvatiti/odbiti

### 10.4 — POS Flow (ako postoji)
- Kreiraj POS lokaciju
- Kreiraj bon
- Provjeri fiskalizaciju mock
- Provjeri PDF bon

### 10.5 — Dokument Upload → Arhiva
- Upload dokumenta (slika ili PDF)
- Provjeri da se pojavi u arhivi
- Provjeri metadata (timestamp, user, firma)
- Provjeri da SHA-256 hash postoji

### 10.6 — Error Handling Audit
- Što se dogodi kad:
  1. Korisnik unese krivi OIB? → mora biti jasna poruka
  2. Korisnik unese dupli email pri registraciji? → jasna poruka
  3. Korisnik pokuša kreirati fakturu bez partnera? → jasna poruka
  4. Session istekne usred rada? → redirect na login, ne 500
  5. Korisnik bez firme pokuša pristupiti /invoicing/? → jasna poruka
- Svaki slučaj koji vraća 500 = bug = fix odmah

### 10.7 — Smoke Test Suite
- Kreiraj/proširi automatski smoke test:
  ```python
  # core/tests/test_onboarding_smoke.py
  # Cijeli flow: register → login → company → partner → invoice → PDF → arhiva
  ```
- Test mora prolaziti sa `pytest core/tests/test_onboarding_smoke.py -v`

### 10.8 — Commit i izvještaj
- Commitaj sve promjene
- Na kraju ispiši tablicu:
  | Flow | Status | Bugovi nađeni | Bugovi popravljeni |
  |------|--------|---------------|-------------------|
  | Registration | ✅/❌ | N | N |
  | Company setup | ✅/❌ | N | N |
  | Prva faktura | ✅/❌ | N | N |
  | POS | ✅/❌ | N | N |
  | Arhiva | ✅/❌ | N | N |
  | Error handling | ✅/❌ | N | N |
  | Smoke test | ✅/❌ | N | N |

---

## ZAVRŠETAK
Kad sve bude ✅, ispiši: **KORAK 10 — ONBOARDING PROVJERA ✅ GOTOV**
