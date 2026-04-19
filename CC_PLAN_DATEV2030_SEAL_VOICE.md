# CC PLAN — DATEV 2030 + eValidator Pečat + Glasovni Send
> Datum: 2026-04-19 | Agent: CC Sonnet

## ANALIZA STANJA
- Swap: 18GB ukupno (2GB + 16GB), 7GB koristi — DOVOLJNO, ne treba novi
- RAM 79% = load testovi s 5000 korisnika — normalno
- DATEV EXTF/700 postoji ali je basic GET bez UI-a
- eValidator = OIB/IBAN validator, nema seal feature
- Send = WhatsApp + Email, nema viral/voice/seal

## ŠTO GRADIMO (3 bloka)

### BLOK 1: eValidator DocumentSeal
- Model: DocumentSeal (seal_token, sha256_hash, entry FK, meta, expires_at)
- Service: seal_service.py — generate_seal(entry) → QR + token
- Endpoint: /evalidator/verify/<token>/ → HTML verifikacijska stranica
- API: /evalidator/api/verify/<token>/ → JSON
- Dizajn: zeleni pečat s QR kodom, embed u PDF marginu

### BLOK 2: DATEV 2030 — Bolje od DATEV-a
Nadogradnja german_accounting.py:
- BelegLink: URL na evalidator verify page po svakom knjiženju
- Buchungs-GUID: UUID4 po knjiženju
- KOST1/KOST2: iz Invoice/cost_center
- SEPA Mandatsreferenz: iz Company settings
- Novi format: SEPA pain.008 XML za direktnu naplatu
- OSS/IOSS: cross-border EU VAT oznake
- UI stranica: /konto/datev-2030/ s kompletnim opcijama
- Format download: CSV (EXTF), ZIP (EXTF + ZUGFeRD + SEPA), preview tablice

### BLOK 3: Digitalni Send s Glasovnom Porukom + Viral Kod
Nadogradnja arhiva_send_komitent:
- viral_code: 8-char unique code po svakom slanju (ArhivaViralSend model)
- Voice: browser Web Speech API TTS → audio/mp3 → WhatsApp voice note (WAHA)
- Channels: Email + WhatsApp + Portal Link (sve odjednom ili odvojeno)
- Seal: automatski generira pečat pri slanju (ako nema)
- Consent flag: GDPR za WhatsApp (WhatsApp communicaton consent)
- Verificacijska stranica: /documents/verify/<viral_code>/ — autentičnost + CTA

## ZAKONSKI OKVIRI
- eIDAS (EU) 910/2014: server timestamp = advanced timestamp (ne QES, ali zakonski validan)
- GoBD §14b: neopozivo, vremenski označeno, dostupno — arhiva already compliant
- GDPR Art. 6(1)(b): slanje dokumenta = izvršenje ugovora = lawful basis
- Glasovna poruka: browser-side TTS bez server storage = GDPR safe
- WhatsApp: business API (WAHA) = user consent required (save_contact flag = consent flag)
- Croatian ZED (NN 150/05): digitalni dokument = original ako potpisan ili timestamp

## OGRANIČENJA (ne radimo ovo)
- Ne radimo server-side voice storage (GDPR)
- Ne radimo QES (Qualified Electronic Signature) — preskupo bez QTSП
- Viral CTA je diskretan, ne agresivan

## REDOSLIJED
1. evalidator/models.py — DocumentSeal model
2. evalidator/migrations/0002_ — migracija
3. evalidator/seal_service.py — generiranje pečata + QR
4. evalidator/views.py — verify_seal endpoint
5. evalidator/templates — verify stranica
6. konto/german_accounting.py — BelegLink + GUID + SEPA
7. konto/datev_2030.py — SEPA XML + OSS format
8. konto/views.py + urls.py — nova UI stranica
9. templates/konto/datev_export.html — bogati UI
10. documents/views_arhiva.py — enhanced send
11. templates/documents/_send_advanced_modal.html — send modal s glasom
12. documents/models.py — ArhivaViralSend model
13. documents/migrations — migracija
14. python manage.py check + test + commit
15. FENIX_STATUS.md update
