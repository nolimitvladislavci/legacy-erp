# LEX NO LIMIT — Kooperativni digitalni pravni ured
# Kreirano: 2026-04-27 | Tri agenta u realizaciji
# Zakon 26: zapisano odmah

## KONCEPT
Klijent placa uslugu
    → AI drafta dokument (VETRA Legal)
    → Invalid validator potvrđuje iz kuce (klik, review, ovjera)  
    → Dokument zapecacen (VETRA .dok seal)
    → Novac → NO LIMIT udruga → placa invalide za rad

## PRAVNI OKVIR (HR/EU)
- 1x licencirani odvjetnik = SUPERVIZOR (potpisuje, odgovara)
- Nx invalid paralegal = VALIDATOR (review, potvrda, ovjera)  
- AI = DRAFTER (prijedlog dokumenta, ne odlucuje)
- VETRA = NOTARY LAYER (pecati, arhivira, dokazuje)
- Ovo NIJE nadriodvjetnistvo — standardni outsourced legal model (legalan u HR/EU)
- ZOD (Zakon o odvjetnistvu) HR: paralegal rad je legalan pod nadzorom licenciranog odvjetnika

## LIMIT-CONNECT CERTIFIKAT (pravna osnova)
- Interni platformski tecaj (webinar + test + praksa)
- Nije formalna diploma — uvjet za rad na platformi
- Analogija: Google/Salesforce/AWS certifikat — nitko ih ne osporava
- Izdaje se kao .dok dokument (VETRA seal = nepobitno datiran)
- 3 razine: Asistent / Paralegal / Senior Paralegal

## PRIHODI I RASPODJELA
Klijent placa uslugu (npr. 50-200 EUR po dokumentu)
    → 60% → NO LIMIT udruga (administracija, sustav, odvjetnik supervizor)
    → 30% → Invalid validator koji je radio (direktno na racun/ziro)
    → 10% → Razvoj platforme

## TROKUT VRIJEDNOSTI
Invalid: zaposlen, placen, radi od kuce, socijalno ukljucen
Klijent: jeftinija i brza pravna usluga (AI+human review = brze od klasicnog ureda)
Drustvo: EU ESF+ kompatibilno, socijalno poduzece, smanjuje socijalnu iskljucenost

## INFRASTRUKTURA VEC POSTOJI
VETRA Legal modul (LIVE):
  - LegalProfile (attorney/notary uloge) [LIVE]
  - LegalMatter (predmeti) [LIVE]
  - ClientPortalAccess (magic link, bez logina) [LIVE]
  - DocumentTemplate + WeasyPrint PDF [LIVE]
  - ConsultationSlot + Jitsi booking [LIVE]
No Limit (LIVE):
  - AmbassadorApplication (14 zemalja) [LIVE]
  - Baza potencijalnih validatora postoji
fina-connect (LIVE):
  - worktime.VolunteerActivity + EU grant polja [LIVE]
  - konto (obracun placa) [LIVE]
memio_world (LIVE):
  - LearningModule model [LIVE] — baza za webinare/tecajeve

## STO NEDOSTAJE (graditi)

### SPRINT 1 — ValidatorProfile + ReviewQueue
- ValidatorProfile model (VETRA legal app ili No Limit app)
  Polja: user, disability_type, certification_level, is_active,
         hourly_rate, bank_account, validated_docs_count, rating
- ReviewQueue model
  Polja: matter, assigned_validator, status(pending/in_review/approved/rejected),
         assigned_at, completed_at, fee_earned, supervisor_approved
- API: POST /legal/review/<matter_id>/assign/ → dodijeli validatoru
- API: POST /legal/review/<matter_id>/approve/ → invalid potvrdi
- API: POST /legal/review/<matter_id>/reject/ → invalid odbaci s komentarom

### SPRINT 2 — Limit-Connect Certifikat
- CertificateTemplate model (naziv, razina, preduvjeti, rok vazenja)
- CertificateIssuance model (validator, razina, datum, .dok_hash)
- Automatsko izdavanje .dok certifikata pri prolazu testa
- /legal/certifikati/ — moj pregled certifikata
- /legal/certifikat/<uuid>/ — javna verifikacija certifikata (bez logina)

### SPRINT 3 — Webinar/Tecaj platforma
- Prosiriti memio_world.LearningModule za LEX tecajeve
- ILI: novi Django app lex_academy/ u fina-connect
- Modul: video embed (YouTube unlisted / Jitsi live) + kviz + certifikat
- 3 tecaja za pocetak:
  T1: Uvod u paralegal rad (4h) — free
  T2: VETRA dokumenti i .dok format (6h) — 49 EUR
  T3: Pravni procesi za paralegale (8h) — 99 EUR

### SPRINT 4 — Payment flow (Stripe → Udruga → Invalid)
- Klijent placa Stripe checkout
- Webhook: PaymentReceived → kreira ReviewQueue → dodijeli validatoru
- Kraj review-a: automatski obracun fee_earned za invalida
- Mjesecni obracun: export za konto modul (placa invalida)
- Reporting: EU ESF+ format za grant aplikacije

### SPRINT 5 — EU fondovi aplikacija
- Projekt: "Digitalna ukljucenost invalidnih osoba u pravne usluge"
- Fond: ESF+ (Europski socijalni fond plus) — HR ROP 2021-2027
- Iznos: 50k-200k EUR za pilot (12 mj)
- Uvjet: min 20 zaposlenih invalida, mjerljivi outputi
- CERV (Citizens, Equality, Rights and Values) — dodatni fond
- No Limit udruga aplicira (Ivan predsjednik)

## DOMENSKI PLAN
- lex.limit-connect.com — platformski ured (autenticirani korisnici)
- lex.vetra.live — javna verifikacija dokumenata
- nolimit.legal — premium domena za EU prezentacije (kupiti?)

## VEZA S POSTOJECIM PLANOVIMA
- V02 (pravno misljenje eIDAS) → odvjetnik supervizor = ista osoba
- V09 (whitepaper) → LEX NO LIMIT poglavlje
- V10 (Horizon Europe) → LEX kao primjena VETRA protokola
- M4 (No Limit 13/10) → ValidatorProfile baza ambasadora
- fina-connect konto → obracun placa validatora

## REDOSLIJED SPRINTOVA
S1 (ValidatorProfile + Queue) → S2 (Certifikat) → S3 (Webinar) → S4 (Payment) → S5 (EU fondovi)
S1+S2 mogu paralelno. S4 ceka S1. S5 ceka S4 (treba dokazati aktivni model).

## SUDACKA NAPOMENA
Ovo nije samo socijalni projekt. Ovo je OBRAMBENI MOAT za limit-connect:
- Svaki invalid koji se certificira = novi distribucijski kanal
- Svaki certifikat = VETRA .dok = prior art za platformu
- Svaki EU fond = besplatni kapital za razvoj
- Legalni moat: odvjetnik supervizor = regulatory shield
