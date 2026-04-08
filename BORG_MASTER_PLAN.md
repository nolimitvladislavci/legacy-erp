# BORG MASTER PLAN — LIMIT Connect Ekosustav
# Datum: 07.04.2026 | Autor: Ivan Brtan + Sonnet
# Status: ŽIVI DOKUMENT — ažurira se svake sesije
# Pravilo: Sonnet uvijek čita ovaj fajl na početku sesije

---

## 1. ŠTO JE BORG

BORG nije samo LIMIT Connect. BORG je ekosustav koji se sastoji od:

| Produkt              | Status     | Klijenti          | Prihod model         |
|----------------------|------------|-------------------|----------------------|
| LIMIT Connect (ERP)  | 8.5/10     | 80+ firmi (Marija)| SaaS pretplata       |
| memio.pet            | 8.5/10     | Piloti: Ljubeta   | Freemium → Premium   |
| memio.world          | 6.5/10     | Razvoj            | B2C sjećanja         |
| NO LIMIT udruga      | 7/10       | Azili             | Donacije + sponzori  |
| Boxgram              | 7/10       | Pero, Ljubeta     | Integracija signala  |
| Burza                | Postoji    | Neaktivna         | Marketplace fee      |

**Ključna spoznaja:** Svi produkti dijele isti Django monorepo, isti server, istu bazu.
Kad jedan pukne — puknu svi. Kad se jedan unaprijedi — može pomoći svima.

---

## 2. KONKURENTSKA MAPA — GDJE GUBIMO, GDJE DOBIVAMO

### Synesis (glavni konkurent HR):
- **Dobivamo:** Multi-tenant, AI, mobilni POS, fiskalizacija u cloudu
- **Gubimo:** Zrelost koda (oni imaju 15 godina, mi 1), ekosustav računovođa
- **Opasno:** Ako ne integriramo **modul Proizvodnja** do Q3 2026 — industrijski klijenti
  ostaju na Synesisu. Imamo model (577 linija), ali nije poliran.
- **Opasno:** **eRačun** (UBL 2.1, XAdES-B) — imamo 39/40 testova — ali nismo
  demonstrirali live klijentu. Synesis to ima godinama.

### Libusoft Cicom (komunalni sektor, ~80% tržišta):
- **Dobivamo:** Nemaju mobilni sloj, nemaju AI, nemaju field ERP
- **Gubimo:** Integracija s Poreznom, FINA, HZMO — oni to imaju, mi nemamo direktno
- **Naš napad:** LIMIT Connect kao "Edge ERP" — ide na teren gdje Libusoft ne može

### Pantheon (SLO/HR/RS):
- **Dobivamo:** Lokalna fiskalizacija, HR jezik, brži razvoj
- **Gubimo:** Brandiranje, distribucijska mreža računovođa

---

## 3. ZLATNI KOD — DEFINICIJA I PRAVILA

### Što je zlatni kod:
Kod koji je **predvidiv** — uvijek radi isto, uvijek vraća ono što obećava,
uvijek pada glasno (ne tiho). Ne mora biti savršen. Mora biti pouzdan.

### 5 pravila zlatnog koda (OBAVEZNA za sve agente):

**Pravilo 1 — ČITAJ PRIJE NEGO PIŠEŠ**
Svaki agent (CC, Gemini, Haiku) mora pročitati stvarni model prije pisanja querija.
Nikad pretpostavljaj field name. `company` ≠ `buyer_company` ≠ `hub_company`.
```python
# ZABRANJENO:
ColdChainZone.objects.filter(company=company)
# ZLATNO (nakon čitanja modela):
ColdChainZone.objects.filter(buyer_company=company)
```

**Pravilo 2 — GREŠKA SE VIDI, NE GUTA**
```python
# ZABRANJENO:
except Exception:
    pass
# ZLATNO:
except Exception as e:
    logger.error("MODULE funkcija failed za %s: %s", company, e)
    # i vrati korisniku smislenu poruku
```

**Pravilo 3 — SVAKI KRITIČNI PUT IMA TEST**
10 korisničkih puteva (vidi sekciju 5) moraju imati automatski test.
Test = zaštita od regresije. Bez testa = ne znaš kad si pokvarit.

**Pravilo 4 — JEDAN IZVOR ISTINE ZA CSS/JS**
Inline `<style>` u templatu pobijedi externe fajlove (kaskada).
Nikad ne popravjaj CSS u vanjskom fajlu ako je u templatu inline.

**Pravilo 5 — BACKUP PRIJE DESTRUKCIJE**
Svaka operacija koja briše ili mijenja podatke → backup → operacija → provjera.

---

## 4. BORG RADAR — STANJE SVAKOG MODULA

### ZELENO (radi, ne diraj bez razloga):
- Fiskalizacija (HR) — ZKI/JIR — 97%+ pouzdanost
- eRačun — 39/40 testova
- Accounts/Auth — 2FA, TC consent, memberships
- Claude Doktor — 97/100 test
- Trojstvo — v2, log + WhatsApp

### ŽUTO (radi, ali treba pažnje):
- POS mobitel — hamburger panel nov, nije stres-testiran
- memio.pet — onboarding radi, payment nije
- delivery/consolidated — bug s company poljem (treba fix)
- Payroll — postoji, nije demonstriran klijentu
- Tax wizard — 960 linija modela, 0 testova ⚠️

### CRVENO (postoji, ali ne radi ili nije integrirano):
- Modul Proizvodnja (production/) — 577 linija modela, 938 testova ali nije u meniju
- Burza — postoji, neaktivna
- memio.world — 6.5/10, nema plaćanja
- AML — postoji, nije demonstriran
- Worktime — 802 linije modela, 0 testova

### NEVIDLJIVO TRŽIŠTU (postoji ali ne znaju):
- Knjižnica (knjiznica/) — gotovo, nije markentirano
- Eldercare — postoji za domove
- Kindergarten — postoji, nije aktivno
- Lovački — postoji
- Zeleni otok — postoji

---

## 5. 10 ZLATNIH PUTEVA (kritično za 15.04.)

Ovi putevi moraju raditi 100% bez greške:

1. **Login → odabir firme → dashboard** (trenutno: puca na nekim firmama)
2. **POS → dodaj artikl → gotovinska naplata → fiskalizacija** (Šeki use case)
3. **POS → dodaj artikl → kartična naplata** (Šeki use case)
4. **Faktura → unos → PDF → fiskalizacija → slanje emailom**
5. **Nova firma → onboarding wizard → prva blagajna**
6. **Zaposlenik → plaća → JOPPD obrazac**
7. **Skladište → primka → inventura**
8. **Zlatno dugme → Trojstvo → rezultat vidljiv**
9. **Marija → ulaz u klijentsku firmu → pregled faktura**
10. **Superadmin → Claude Doktor → dnevna dijagnoza svih firmi**

---

## 6. TEHNIČKE AKCELERACIJE (ideje za implementaciju)

### Već implementirano:
- Zlatno dugme + Trojstvo (Haiku + Gemini konsenzus)
- Claude Doktor (dnevna dijagnoza)
- MCP server (10 alata za real-time server pristup)
- Gemini autonomni agent (read/write/exec na serveru)

### Sljedeće akceleracije (istraži):

**A) GitHub Copilot Workspace pattern**
Umjesto CC koji čeka naredbu — agent koji svako jutro skenira
otvorene ImprovementSuggestion i autonomno predlaže pull requeste.
Trojstvo to odlučuje, CC implementira.

**B) Sentry + Alerting loop**
Svaka produkcijska greška → Sentry → Trojstvo → prijedlog fixa → CC.
Zatvorena petlja bez Ivana za standardne greške.

**C) Synthetic monitoring**
Playwright skript koji svako jutro prođe svih 10 zlatnih puteva
i javi ako išta pukne. Jeftiniji od ručnog testiranja.

**D) EU AI Act Compliance layer**
Gemini prati EUR-Lex, Narodne novine → automatski kreira
ComplianceWatchItem → Claude Doktor ih prikazuje.
(Ovaj modul već djelomično postoji u limit_connect_ai/)

**E) "Kod koji se sam dokumentira"**
Svaki view, model, task — obavezni docstring s:
- što radi
- koji modeli se koriste
- koji field names (da se izbjegne company vs buyer_company bug)

---

## 7. FINANCIJSKI MOTOR ZA VJEČNU MLADOST

### Model koji ne stari:
```
Klijenti plaćaju SaaS pretplatu
    → % ide u "AI razvoj fond"
    → Fond plaća Anthropic API, Gemini API, server
    → Trojstvo poboljšava sustav
    → Sustav privlači više klijenata
    → Fond raste
```

### EU Fondovi (istraži do Q3 2026):
- Horizon Europe — AI za MSP (Small Business)
- Digital Europe Programme — digitalizacija
- ESIF fondovi kroz HZZ/HAMAG za HR klijente
- Gemini prati ove fondove — GEMINI_EU_AUDIT_MINES.md postoji

### ARR projekcija:
- Q2 2026: €30k ARR (80 klijenata × €30/mj)
- Q4 2026: €120k ARR (400 klijenata × €30/mj)
- 2027: €600k ARR (DE ekspanzija)
- 2030: €6M ARR (HR+DE+AT, enterprise)

---

## 8. PRAVILO VJEČNE MLADOSTI KODA

**Kod ne stari ako:**
1. Svaka sesija počinje čitanjem ovog fajla
2. Svaka dogovorena promjena se zapisuje
3. Svaki bug se analizira do root cause — ne samo patcha
4. Svaki modul ima odgovornog "vlasnika" (Ivan, Marija, CC, Gemini)
5. Testovi se pišu uz svaki novi feature, ne nakon

**Kod stari ako:**
1. Dodajemo feature bez provjere temelja
2. Ignoriramo TODO/FIXME (trenutno 51)
3. Gutamo greške s `except: pass`
4. Pišemo CSS bez znanja kaskade
5. Pretpostavljamo field names umjesto da čitamo modele

---

## 9. SESIJA PROTOKOL (za Sonnet)

**Na početku svake sesije:**
1. Pročitaj BORG_MASTER_PLAN.md (ovaj fajl)
2. Pročitaj FENIX_STATUS.md (zadnje stanje)
3. Pročitaj FENIX_TROJSTVO_PRAVILA.md (ovlasti)
4. Provjeri ImprovementSuggestion.objects.filter(status='new')
5. Javi Ivanu stanje u jednoj rečenici

**Na kraju svake sesije:**
1. Ažuriraj FENIX_STATUS.md sa svim promjenama
2. Zapiši svaki dogovor koji nije u kodu
3. Ostavi CC_TASK ili GEMINI_TASK ako ima pending posla

---

*Zadnja izmjena: 07.04.2026 — Ivan Brtan & Sonnet*
*Sljedeća obvezna revizija: 14.04.2026 (dan prije produkcije)*
