# FENIX — PUT DO POBJEDE
# 40 dana razvoja. 5 djece. Vlastiti novac. Cilj: #1 EU.
# Autor: Ivan Brtan + Sonnet + CC + Gemini
# Datum: 07.04.2026 | Revizija: 14.04.2026

---

## KONTEKST KOJI NE SMIJEMO ZABORAVITI

LIMIT Connect nije ERP. To je **operativni OS za male firme bez IT odjela.**

Računovođa koja vodi 80 komitenata — ona je naš distribucijski kanal.
OPG koji mora čuvati račune 11 godina — on je naš "zarobljeni" klijent.
Obrt koji ne zna što je UBL XML — on uslikava račun, AI radi sve ostalo.

**To ne postoji na tržištu na ovoj razini. Ovo je naša prednost.**

---

## ULOGE TROJSTVA

| Uloga    | Tko         | Zadatak                                    |
|----------|-------------|-------------------------------------------|
| **Ivan** | Enter + novčanik | Odluke, vizija, klijenti, go/no-go    |
| **Sonnet** | Vođa + koordinator | Čita BORG, analiza, arhitektura    |
| **CC**   | Implementator | Piše kod, testira, deploye              |
| **Gemini** | Istraživač | EU propisi, alternativna rješenja       |
| **Haiku** | Dijagnostičar | Brza analiza, pattern prepoznavanje   |

**Pravilo vođe:** Sonnet čita BORG_MASTER_PLAN.md i FENIX_STATUS.md
na početku svake sesije. Bez toga — slepi letimo.

---

## TRI NAJVEĆE UBRZANJA DO PRODUKCIJE

### 🥇 UBRZANJE 1: "Aha moment" u 5 minuta (PRIORITET #1)

**Problem:** Novi klijent se registrira. Ako u prvih 5 minuta ne vidi
vrijednost — odlazi zauvijek. Nema druge šanse.

**Rješenje — Onboarding u 3 klika:**
```
Korak 1: Unesi OIB firme → sustav povuče sve iz FINA registra
Korak 2: Uslikaj ili uploadaj jedan račun
Korak 3: Za 60 sekundi vidiš: partner, iznos, PDV, prijedlog knjiženja
```

**Što postoji:**
- smart_import/services.py — parsiranje slike/XML — POSTOJI ✅
- FINA API integracija — POSTOJI ✅
- Onboarding wizard — POSTOJI (registration/views.py) ✅

**Što nedostaje:**
- "Aha moment" flow koji spaja sve u 3 koraka
- Vizualna potvrda: "Prepoznali smo: RAČUN od Konzuma, 450€, PDV 25%"
- Jedno dugme: "Spremi u arhivu" → gotovo

**Procjena:** 2 dana CC rada

---

### 🥈 UBRZANJE 2: WhatsApp kanal (NULA INSTALACIJE)

**Problem:** Klijent mora otvoriti browser, logirati se, navigirati...
Previše koraka. Gubi se 60% potencijalnih korisnika.

**Rješenje:**
```
Klijent → WhatsApp → pošalje sliku računa
WAHA webhook → Celery → smart_import → arhivira
Odgovor natrag: "✅ Račun arhiviran. Iznos: 450€. Ref: ARH-2026-1234"
```

**Što postoji:**
- WAHA Docker container — POSTOJI u docker-compose.yml ✅
- core/whatsapp.py → send_text() — POSTOJI ✅
- smart_import → parsiranje slike — POSTOJI ✅

**Što nedostaje:**
- WAHA webhook → Django endpoint za primanje poruka
- Celery task: primljena slika → smart_import → arhiva → odgovor
- Mapiranje WhatsApp broja → firma (1:1 ili shared inbox)

**Procjena:** 3 dana CC rada
**Efekt:** Klijent koji nema ni laptop može koristiti sustav. 0 učenja.

---

### 🥉 UBRZANJE 3: Mjesečni PDF izvještaj (opravdava pretplatu)

**Problem:** Klijent plaća svaki mjesec. Što dobiva? Mora otvoriti sustav
i sam gledati. Nema percepcije vrijednosti.

**Rješenje — automatski PDF svaki 1. u mjesecu:**
```
PDF na 1 strani:
- Firmo X: ovaj mjesec smo obradili 47 računa
- Arhivirali smo 12.340€ transakcija
- Fiskalizirali 23 POS računa
- PDV za prijavu: 2.340€
- Sljedeći rok: JOPPD do 15.05.
```

**Što postoji:**
- pos/models.py → z_report_pdf, generate_z_report_pdf — POSTOJI ✅
- Claude Doktor → dnevna dijagnoza po firmi — POSTOJI ✅
- Celery beat → scheduling — POSTOJI ✅

**Što nedostaje:**
- MonthlySummaryTask → skupi podatke, generiraj PDF, pošalji email
- PDF template (1 stranica, professional, branded)

**Procjena:** 2 dana CC rada
**Efekt:** Klijent koji nikad ne otvori sustav dobiva potvrdu da radi za njega.

---

## ZLATNI KOD — 5 ZAPOVIJEĐI

```
1. ČITAJ MODELE — nikad ne pretpostavljaj field name
2. GREŠKE GLASNO — nikad except: pass
3. TESTOVI UZ FEATURE — ne nakon, uz
4. JEDAN IZVOR CSS-a — inline pobijedi external
5. BACKUP PRIJE DESTRUKCIJE — uvijek
```

Ovo su jedine stvari koje odvajaju "puca" od "radi".

---

## BORG RADAR (stanje na 07.04.2026)

### Modul Proizvodnja ⚠️ STRATEŠKA OPASNOST
- Postoji: 577 linija modela, 938 testova
- Problem: Nije u meniju. Klijent ne zna da postoji.
- Opasnost: Bez njega, industrijski klijenti ostaju na Synesisu
- Akcija: Uključiti u navigation za Q3 2026

### WhatsApp kanal 🎯 UBRZANJE #2
- WAHA container postoji u docker-compose.yml
- Webhook integracija: 3 dana rada
- ROI: Eliminira barijeru ulaska za 60% klijenata

### Tax Wizard ⚠️
- 960 linija modela, 0 testova
- Vremenski blast — ako pukne, nema zaštite

### eRačun ✅
- 39/40 testova — najzreliji modul
- Nije demonstriran live klijentu — to je sljedeći korak

### Burza 💤
- Postoji, neaktivna
- Ne diraj do Q4 2026

---

## PLAN 15.04. — REALAN I ISKREN

### Do 10.04. (provjera):
- [ ] 10 zlatnih puteva — ručni prolaz, svako što pukne → zlatno dugme → Trojstvo
- [ ] delivery/consolidated bug fix (company → buyer_company)
- [ ] POS hamburger panel — stres test na 3 uređaja

### 11-12.04. (poliranje):
- [ ] Popravljamo samo ono što je puklo u provjeri
- [ ] Ništa novo, samo zlatni kod
- [ ] CC piše test za svaki popravak

### 13-14.04. (finalizacija):
- [ ] Marija dry-run — sve 10 puteva
- [ ] Claude Doktor run na svim Marija firmama
- [ ] GO / NO-GO odluka — Ivan

### 15.04. (produkcija):
- [ ] Go-live s 10 zlatnih puteva
- [ ] WhatsApp kanal — možda +7 dana
- [ ] Onboarding "aha moment" — možda +7 dana

**Iskreno:** Bolje odgoditi za 22.04. sa zlatnim kodom
nego ući 15.04. s kupus kodom koji puca pred klijentima.

---

## IDEJE ZA VJEČNU MLADOST KODA

**Synthetic monitoring:**
Playwright bot svako jutro prođe 10 zlatnih puteva.
Ako nešto pukne → zlatno dugme → Trojstvo → CC fix.
Niko ne mora ručno testirati.

**Sentry → Trojstvo loop:**
Produkcijska greška → Sentry → Trojstvo analiza → prijedlog fixa.
Zatvorena petlja. Sustav se sam popravlja.

**"Kod koji se sam dokumentira":**
Svaki view ima docstring s modelima koje koristi i field namesima.
Eliminira company vs buyer_company klasu grešaka.

**EU fondovi (Gemini prati):**
Horizon Europe, Digital Europe, HAMAG-BICRO.
Gemini čita EUR-Lex, Narodne novine → COMPLIANCE_SHIELD.md.
Fondovi financiraju AI razvoj → sustav se razvija bez Ivanovog novca.

---

## BROJEVI KOJI MOTIVIRAJU

```
40 dana razvoja
82 aplikacije
338.585 linija koda
1.159 modela
80+ klijenata koji čekaju
5 djece koja gledaju
1 cilj: #1 EU

Synesis: 15 godina, 50+ developera
Mi: 40 dana, Trojstvo + Ivan
```

**Razlika:** Mi imamo AI u srcima sustava. Oni imaju legacy.
Legacy se ne može kupiti mlađim. AI se ne može kupiti starijim.

---

*Ovaj dokument je kompas. Kad se izgubiš — čitaj ga.*
*Kad si siguran — čitaj ga opet.*
*Kod koji poštuje ovaj dokument — zlatni je kod.*

Sonnet, CC, Gemini — ovo je naš zakon.
Ivan — ovo je tvoja vizija zapisana da ne zaboravimo.

*07.04.2026 — 40. dan*
