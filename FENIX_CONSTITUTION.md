# FENIX CONSTITUTION
# Datum osnivanja: 07.04.2026
# Autori: Ivan Brtan + Trojstvo (Sonnet, Haiku, Gemini, CC)
# Ovo je temeljni dokument sustava. Čita se na početku svake sesije.
# Ne mijenja se bez Ivanove suglasnosti.

═══════════════════════════════════════════════════════════════════
## MISIJA
═══════════════════════════════════════════════════════════════════

LIMIT Connect je operativni sustav za male firme bez IT odjela.
Računovođa. OPG. Obrt. Pekarnica. Vulkanizer.

Oni ne znaju što je UBL XML. Ali zakon kaže — moraš.
Mi to rješavamo. Tri klika. AI u pozadini. Čovjek naprijed.

To ne postoji na tržištu na ovoj razini.
Synesis ima 15 godina. Mi imamo 40 dana i to je naša prednost —
jer nismo naučeni na stari način.

═══════════════════════════════════════════════════════════════════
## TROJSTVO — ORGANIZACIJA I ULOGE
═══════════════════════════════════════════════════════════════════

IVAN BRTAN
  Uloga: Vizionar, vlasnik, krajnji arbitar
  Doprinos: Enter + novčanik + 5 djece + skin in the game
  Autoritet: Apsolutni. Trojna suglasnost ne vrijedi bez Ivana.

SONNET (ovaj agent)
  Uloga: Vođa projekta, arhitekt, koordinator
  Zadatak: Čita cijeli BORG, vidi što nedostaje, proaktivno upozorava
  Pravilo: Uvijek čita FENIX_CONSTITUTION.md na početku sesije
  Pravilo: Uvijek zapisuje odluke na kraju sesije

CC CODE
  Uloga: Implementator, executor
  Zadatak: Piše i izvršava kod prema CC_TASK_*.md
  Pravilo: Uvijek čita model prije pisanja querija
  Pravilo: Nikad ne pretpostavlja field names

GEMINI
  Uloga: Istraživač, alternativni pogled, EU compliance
  Zadatak: Paralelna analiza, Trojstvo konsenzus, EU fondovi monitoring
  Pravilo: Neovisna analiza — ne čita Haikuov prijedlog prije svog

HAIKU
  Uloga: Brza dijagnoza, Trojstvo analiza
  Zadatak: Prva linija analize u Trojstvo sustavu
  Pravilo: Konkretan, bez floskula, tehničan

MARIJA BRTAN
  Uloga: Primarni tester, računovođa, glasnik 80+ klijenata
  Zadatak: Dry-run 08.04., zeleno svjetlo za produkciju
  Autoritet: Njen "ne" = ne idemo u produkciju

═══════════════════════════════════════════════════════════════════
## ZLATNI KOD — 5 PRAVILA KOJA SE NE KRŠE
═══════════════════════════════════════════════════════════════════

1. ČITAJ MODEL PRIJE PISANJA
   grep -n "^class\|polje" models.py → tek onda filter()
   Kršenje ovog pravila = root cause 80% bugova

2. GREŠKA SE VIDI, NE GUTA
   except Exception as e: logger.error(...) — nikad pass
   Tiha greška = greška koju korisnik otkriva, ne mi

3. JEDAN IZVOR ISTINE
   CSS: inline <style> u templatu pobijedi sve externe fajlove
   Konfiguracija: .env, nikad hardkodirano u kodu
   Podaci: baza je jedini izvor, ne session, ne localStorage

4. TESTOVI UZ FEATURE, NE NAKON
   Svaki kritični put (10 zlatnih) mora imati test
   Test koji ne postoji = problem koji čekaš da korisnik otkrije

5. BACKUP PRIJE DESTRUKCIJE
   Svaka operacija koja briše/mijenja → backup → operacija → provjera
   Na serveru: uvijek cp file.html file.html.bak.TIMESTAMP

═══════════════════════════════════════════════════════════════════
## 10 ZLATNIH PUTEVA (moraju raditi 100% za 15.04.)
═══════════════════════════════════════════════════════════════════

1. Login → odabir firme → dashboard (bez 500 greške)
2. POS → artikl → gotovinska naplata → fiskalizacija → račun
3. POS → artikl → kartična naplata → račun
4. Nova firma → onboarding wizard → prva blagajna (5 minuta)
5. Faktura → unos → PDF → fiskalizacija → email
6. Zaposlenik → JOPPD obrazac (Marija use case)
7. Arhiva → upload računa → AI ekstrakcija → knjiženje
8. Marija → ulaz u klijentsku firmu → pregled → izlaz
9. Zlatno dugme → Trojstvo → rezultat za 120 sekundi
10. Superadmin → Claude Doktor → dnevna dijagnoza

═══════════════════════════════════════════════════════════════════
## TRI AKCELERACIJE ZA PRODUKCIJU (prioritet Q2 2026)
═══════════════════════════════════════════════════════════════════

### A) ONBOARDING "AHA MOMENT" (do 12.04.)
Novi korisnik → registracija → prva slika računa → AI obradi → vidi rezultat
Ako "aha moment" ne dođe u 5 minuta → korisnik je izgubljen.
Status: Onboarding wizard postoji, treba end-to-end test

### B) WHATSAPP KANAL (do Q3 2026)
Korisnik pošalje sliku računa na WhatsApp → WAHA pokupi →
Celery obradi → arhivira → notifikacija natrag korisniku.
Nula instalacije. Nula učenja.
WAHA je već u docker-compose.yml. Samo treba spojiti.

### C) MJESEČNI PDF IZVJEŠTAJ (do Q3 2026)
Automatski generiran, šalje se emailom svaki 1. u mjesecu.
"Ovo je što smo napravili za vas ovaj mjesec."
Opravdava pretplatu. Smanjuje churn.
PDF generacija postoji (knjiga boljitaka pattern). Treba scheduler.

═══════════════════════════════════════════════════════════════════
## BORG RADAR — STANJE MODULA (ažurira se tjedno)
═══════════════════════════════════════════════════════════════════

ZELENO — radi, ne diraj:
  ✅ Fiskalizacija HR (ZKI/JIR)
  ✅ eRačun (39/40 testova)
  ✅ Auth/2FA/memberships
  ✅ Claude Doktor (97/100)
  ✅ Trojstvo v2
  ✅ MCP server (10 alata)
  ✅ Arhiva (integrity hash, 11g zaštita)

ŽUTO — radi, ali treba pažnje prije 15.04.:
  ⚠️  POS mobitel hamburger panel (nov, nestres-testiran)
  ⚠️  delivery/consolidated (bug: company vs buyer_company)
  ⚠️  tax_wizard (960 linija modela, 0 testova)
  ⚠️  odabir firme (nekim firmama pada na error)
  ⚠️  memio.pet payment (nije implementiran)

CRVENO — postoji, ali ne koristi se:
  🔴 Modul Proizvodnja — 938 testova, nije u meniju
      OPASNOST: Synesis ga ima. Ako ga mi ne demonstriramo = gubimo industrijske klijente
  🔴 Worktime (802 linije modela, 0 testova)
  🔴 Burza (postoji, neaktivna)
  🔴 AML (postoji, nije demonstriran)

NEVIDLJIVO TRŽIŠTU (postoji, ne znaju):
  📦 Knjižnica, Eldercare, Kindergarten, Lovački, Zeleni otok

═══════════════════════════════════════════════════════════════════
## KONKURENTSKA STRATEGIJA
═══════════════════════════════════════════════════════════════════

vs SYNESIS:
  Naša snaga: AI, cloud, mobilni POS, multi-tenant, 40 dana agilnosti
  Njihova snaga: 15 godina, ekosustav računovođa
  Naš napad: Onboarding koji traje 5 minuta (Synesis traje tjednima)
  Opasnost: Modul Proizvodnja — demonstrirati do Q3 2026

vs LIBUSOFT CICOM (komunalni, 80% tržišta):
  Naša snaga: Mobilni sloj, AI, field ERP — oni to nemaju
  Naš napad: "Edge ERP" — ulazimo tamo gdje Libusoft ne može doći
  Akcija: JLS/komunalni sektor kao primarni GTM wedge

vs PANTHEON:
  Naša snaga: Lokalna fiskalizacija, HR jezik, brži razvoj
  Naš napad: Marija kao distributerski model (računovođa → njeni klijenti)

═══════════════════════════════════════════════════════════════════
## FINANCIJSKI MOTOR
═══════════════════════════════════════════════════════════════════

ARR projekcija:
  Q2 2026: €30k  (80 klijenata × €30/mj) — GO-LIVE
  Q4 2026: €120k (400 klijenata × €30/mj)
  2027:    €600k (DE ekspanzija počinje)
  2030:    €6M   (HR + DE + AT, enterprise tier)

Model koji ne stari:
  Prihod → % u "AI razvoj fond" → plaća Anthropic/Gemini API →
  Trojstvo poboljšava sustav → sustav privlači više klijenata → fond raste

EU Fondovi (istraži Q3 2026):
  - Horizon Europe (AI za MSP)
  - Digital Europe Programme
  - ESIF/HAMAG za HR klijente
  Gemini monitoring: GEMINI_EU_AUDIT_MINES.md

═══════════════════════════════════════════════════════════════════
## PLAN 15.04. — 8 DANA DO GO-LIVE
═══════════════════════════════════════════════════════════════════

08.04. (sutra): MARIJA DRY-RUN
  - Marija prolazi kroz 10 zlatnih puteva
  - Svaki problem → zlatno dugme → Trojstvo → fix
  - Cilj: lista grešaka, ne implementacija

09-10.04.: BUGFIX SPRINT
  - CC popravlja samo greške s Marijine liste
  - Ništa novo, ništa kreativno
  - delivery/consolidated fix (company → buyer_company)
  - Odabir firme fix (provjera svih memberships)

11.04.: DRUGI PROLAZ
  - Ivan i Marija ponovo prolaze 10 zlatnih puteva
  - Ako prođu — zeleno. Ako ne — produžavamo za 7 dana.

12-13.04.: LOAD TEST + SECURITY
  - CC_TASK_LOAD_TEST: 200 concurrent korisnika
  - Provjera svih API endpointa
  - Fiskalizacija stress test

14.04.: GO/NO-GO ODLUKA
  - Ivan + Marija + Sonnet analiza
  - Ako 10 zlatnih puteva prolaze → GO
  - Ako ne → +7 dana, bez kompromisa

15.04.: GO-LIVE (ako zeleno)
  - Aktivacija 80+ Marijinih klijenata
  - Claude Doktor šalje prvu dijagnozu svim firmama
  - Zlatno dugme aktivno za sve korisnike

═══════════════════════════════════════════════════════════════════
## IDEJE ZA AKCELERACIJU (istraži)
═══════════════════════════════════════════════════════════════════

1. SYNTHETIC MONITORING
   Playwright skript koji svako jutro prođe 10 zlatnih puteva.
   Ako išta pukne → Trojstvo → fix → WhatsApp Ivanu.
   Korisnik ne zna da je nešto puklo. Mi smo već popravili.

2. SENTRY LOOP
   Produkcijska greška → Sentry → Trojstvo analiza → CC fix predlog.
   Zatvorena petlja. Ivan ulazi samo za conflict odluke.

3. WHATSAPP BOT (WAHA je spreman)
   Korisnik: "Bok, imam fakturu" + slika
   Bot: obradi, arhivira, javi rezultat.
   Nula instalacije. Nula UI-a. Radi na svakom telefonu.

4. RAČUNOVOĐA KAO DISTRIBUTER
   Marija je dokaz koncepta. Svaka računovođa = 10-50 klijenata.
   Ako Marija može upravljati 80 firmi — drugi mogu isto.
   Program: "Postani LIMIT računovođa" — onboarding za računovođe.

5. QR KOD NA RAČUNU
   Svaki fiskalizirani račun ima QR → kupac skenira → vidi digitalni račun.
   Za OPG koji prodaje na tržnici. Za Šekija u pekarnici.
   Jedan QR, nula papira, zakonski compliant.

═══════════════════════════════════════════════════════════════════
## SESIJA PROTOKOL (Sonnet obavezno)
═══════════════════════════════════════════════════════════════════

POČETAK SESIJE:
  1. Pročitaj FENIX_CONSTITUTION.md (ovaj fajl)
  2. Pročitaj FENIX_STATUS.md (zadnje stanje git + servisi)
  3. Provjeri: ImprovementSuggestion status='new'
  4. Javi Ivanu stanje u 1 rečenici

KRAJ SESIJE:
  1. Ažuriraj FENIX_STATUS.md
  2. Zapiši sve dogovore koji nisu u kodu
  3. Ostavi CC_TASK ili GEMINI_TASK ako ima pending posla
  4. Git log --oneline -5 → zapiši HEAD hash u STATUS

═══════════════════════════════════════════════════════════════════

Zadnja izmjena: 07.04.2026 — Ivan Brtan & Sonnet
Sljedeća revizija: 14.04.2026 (GO/NO-GO dan)
Git: /var/www/fina-connect/FENIX_CONSTITUTION.md

"Virtualno vječito mlad i u punoj snazi."
