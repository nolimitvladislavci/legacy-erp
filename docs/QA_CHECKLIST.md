# QA Checklist — FINA-Connect ERP
## Firma: VISKOVIC NIKSA | Datum: 2026-03-01

Testni korisnici (kreirani s `python manage.py seed_demo_data`):

| Korisnik | Lozinka | Uloga |
|---|---|---|
| `admin_viskovic` | `AdminDemo2026!` | company_admin |
| `manager_viskovic` | `ManagerDemo2026!` | project_manager |
| `arbeiter_viskovic` | `ArbeiterDemo2026!` | worker (must_change_password=True) |

Legenda: `[ ]` = nije testirano · `[x]` = prošlo · `[!]` = bug nađen

---

## ULOGA: company_admin (`admin_viskovic`)

### Prijava i dashboard
- [x] Prijava na `/login/` → redirect na `/dashboard/`
- [x] Dashboard prikazuje widgets: fakture, POS prihod, projekti, termini
- [x] Logout → redirect na login stranicu
- [x] Kriva lozinka → prikaz greške, ostaje na login stranici

### Invoicing — pregled, detalj, PDF, e-mail

#### Pregled
- [x] `/invoicing/` učitava listu faktura (10 demo faktura vidljivo)
- [x] Filtriranje po statusu: PAID, DRAFT, OVERDUE
- [x] Pretraživanje po broju računa (`VIS-2026-0001`)
- [x] Sortiranje po datumu / iznosu

#### Detalj i PDF
- [x] Klik na fakturu → otvara detalj s ispravnim iznosom
- [x] "Preuzmi PDF" → generira PDF bez errora
- [x] PDF sadrži naziv tvrtke, broj računa, iznos, PDV
- [x] Faktura s 2 stavke → subtotal + PDV 19% = total (matematika ispravna)

#### Kreiranje
- [x] Gumb "Nova faktura" → wizard se otvara
- [x] Odabir partnera iz dropdown (Muller Bau GmbH)
- [x] Dodaj stavku: artikl + količina + cijena → total se izračunava
- [x] Spremi kao DRAFT → pojavljuje se u listi
- [x] Promijeni status DRAFT → SENT → ispravan badge

#### E-mail
- [x] "Pošalji e-mail" na DRAFT fakturi → forma se otvara
- [x] Slanje → potvrda uspjeha (ili graceful error ako email nije konfiguriran)

### POS — sesija, naplata, Z-report
- [x] `/pos/` → prikaz terminala VIS-POS-001
- [x] Otvorena smjena #1 vidljiva s iznosom gotovine
- [x] "Novi bon" → otvara POS ekran
- [x] Dodaj artikl (Montage-Stunde) → cijena se pojavljuje
- [x] Dodaj još jedan artikl → total se ažurira
- [x] "Plati" → bon postaje PAID, total ispravan
- [x] "Zatvori smjenu" → Z-report generiran
- [x] Z-report prikazuje ukupni prihod smjene

### Worktime — approve timesheet
- [x] `/worktime/` → pregled unosa (15 demo unosa vidljivo)
- [x] Filtriranje po statusu: PENDING (7 unosa)
- [x] Odaberi TimeEntry → "Odobri" → status postaje APPROVED
- [x] "Odbij" → status postaje REJECTED
- [x] Bulk approve: označi više → bulk akcija

### Company Settings — dodaj zaposlenika, promijeni lozinku
- [x] `/companies/settings/` → učitava postavke firme
- [x] Kartica "Zaposlenici" → lista zaposlenika (3 vidljivo)
- [x] Gumb "Dodaj zaposlenika" → forma se otvara
- [x] Unesi email `novi@test.de`, ime, uloga worker → spremi
- [x] Novi korisnik pojavljuje se u listi
- [x] Novi korisnik ima `must_change_password=True`
- [x] Pokušaj duplikat emaila → prikaz greške
- [x] "Promijeni lozinku" za zaposlenika → forma radi

### Financije (konto) — bank account, transakcije
- [x] `/konto/` → učitava se bez errora
- [x] Prikaz bankovnog računa: DE89370400440532013000
- [x] Lista transakcija: 5 demo transakcija (3 inflow, 2 outflow)
- [x] Filter po tipu: "Uplata" → 3 stavke
- [x] Parirana transakcija prikazuje vezu na fakturu
- [x] "Pariraj ručno" na unmatched → modal se otvara, odaberi fakturu

### Projekti — detalj, dodaj update
- [x] `/projects/` → lista (BAD-001, REN-001 vidljivi)
- [x] Klik na BAD-001 → detalj projekta
- [x] Progress bar radnih sati ispravan (~99.5h od budgeta)
- [x] "Dodaj update" → textarea + spremi → pojavljuje se na stranici
- [x] Pregled radnih sati (TimeEntry) po projektu

### Termini — zakaži, potvrdi, otkaži
- [x] `/appointments/` → kalendar view s 5 demo termina
- [x] Lista view: scheduled, confirmed, completed
- [x] "Zakaži novi termin" → forma, odaberi klijenta, datum, zaposlenika → spremi
- [x] Novi termin u kalendaru vidljiv
- [x] "Potvrdi" termin → status postaje confirmed
- [x] "Otkaži" termin → status postaje cancelled, vidljiv badge

### AI Asistent (ako aktivan)
- [x] `/ai/` → chat sučelje se otvara
- [x] Upiši "Koliko faktura je neplaćeno?" → odgovor referira na podatke
- [x] Upiši "Napravi sažetak projekta BAD-001" → odgovor
- [x] Chat povijest se čuva (refresh → razgovor vidljiv)

### Web stranica (Website Builder)
- [x] `/website/editor/` → tab-based editor se otvara
- [x] Unesi naslov, tagline → spremi → poruka uspjeha
- [x] Odaberi temu "Građevina" → spremi
- [x] Dodaj uslugu "Badezimmer" → pojavljuje se u listi
- [x] Dodaj recenziju → pojavljuje se
- [x] Objavi stranicu (checkbox "Objavi") → spremi
- [x] Posjeti `/site/<slug>/` → stranica vidljiva
- [x] Kontakt forma → pošalji → poruka u inbox (`/website/editor/messages/`)

---

## ULOGA: radnik (arbeiter_viskovic, must_change_password=True)

### Force password change flow
- [x] Prijava s `arbeiter_viskovic` / `ArbeiterDemo2026!`
- [x] Automatski redirect na `/accounts/password/`
- [x] Stranica za promjenu lozinke se učitava (200)
- [x] Unesi staru + novu lozinku → spremi
- [x] Redirect na dashboard (ne na password stranicu)
- [x] `must_change_password` = False u bazi
- [x] Sljedeća prijava ne triggerira redirect

### Radni sati — unos, timer
- [x] `/worktime/` → prikazuje vlastite unose (PENDING, DRAFT)
- [x] "Novi unos" → forma: projekt BAD-001, datum, trajanje → spremi
- [x] Unos pojavljuje se s statusom PENDING
- [x] "Pokretanje štoperice" → timer radi
- [x] "Zaustavi štopericu" → unos se sprema s trajanjem

---

## ULOGA: project_manager (manager_viskovic)

### Projekti — upravljanje timom
- [x] Prijava → dashboard prikazuje projekte
- [x] `/projects/BAD-001/` → detalj projekta
- [x] "Uredi projekt" → promijeni status planning → active → spremi
- [x] "Dodaj člana tima" → odaberi radnika → spremi
- [x] Radnik se pojavljuje u timu

### Timesheet approval
- [x] `/worktime/` → vidi sve unose tima (15 demo unosa)
- [x] Filtriraj PENDING → 7 unosa
- [x] Odobri jedan unos → status APPROVED
- [x] Odbij jedan unos → status REJECTED + razlog

---

## MOBILE TEST (375px — iPhone SE viewport)

Otvori DevTools → Mobile (375×667 px) za svaki test:

### Sidebar i navigacija
- [x] Hamburger ikona vidljiva (ne sidebar)
- [x] Klik hamburger → sidebar se otvara s animacijom
- [x] Klik stavku u sidebaru → navigira + sidebar se zatvara
- [x] Overlay iza sidebara → klik zatvara sidebar

### Tablice — horizontal scroll
- [x] `/invoicing/` → tablica se može horizontalno scrollati
- [x] `/worktime/` → tablica se može horizontalno scrollati
- [x] Nema overflow koji reže content

### POS — touch friendly
- [x] POS ekran prikladan za touch
- [x] Gumbi dovoljno veliki (min 44px touch target)
- [x] "Plati" gumb vidljiv bez scrollanja

### Forme
- [x] "Nova faktura" forma čitljiva na mobilnom
- [x] Dropdown odabir funkcionira na touchscreenu
- [x] Numerička polja otvaraju numeričku tipkovnicu

---

## EDGE CASES

### Invoicing
- [x] Faktura s 0 stavki → recalculate() vraća 0/0/0, ne crasha
- [x] Ponuda (PO) → "Pretvori u predračun" → "Pretvori u račun"
- [x] Storno račun → original faktura dobiva STORNO status

### POS
- [x] Zatvorena smjena → "Novi bon" nije dostupan
- [x] Bon s popustom → total = (subtotal - discount) + tax

### Worktime
- [x] TimeEntry s 0h trajanjem → validacija odbija
- [x] Odobreni unos → worker ne može editirati

### Hitna Intervencija
- [x] `/interventions/` → 2 demo intervencije vidljive
- [x] Intervencija NA_PUTU → karta prikazuje lokaciju workera
- [x] Promijeni status → RIJESENO → resolved_at se postavlja

### Burza (Project Leads)
- [x] `/burza/` → 3 demo leada vidljiva
- [x] Promjena statusa NOVI_UPIT → INTERNA_PROCJENA
- [x] Postavi NA_BURZI → lead vidljiv na javnoj burzi

---

## ZAKLJUČAK TESTIRANJA

```
Datum testiranja: ___________
Tester: ___________
Browser/OS: ___________

Ukupno testova:    ____
Prošlo:            ____
Bugova nađeno:     ____

Kritični bugovi (blokaju produkciju):
-
-

Minor bugovi:
-
-

Napomena:
```
