# FENIX TROJSTVO — PRAVILA SUSTAVA
# Verzija: 1.0 | Datum: 07.04.2026 | Autor: Ivan Brtan
# Status: OBAVEZNO ČITANJE za sve agente i developere

---

## 1. TROJSTVO — ŠTO JE I ZAŠTO POSTOJI

Trojstvo je AI konsenzus sustav koji ubrzava rješavanje problema za 10x.

**Članovi:**
- **Ivan / Marija / Šeki** — pronalaze problem, pritišću zlatno dugme ⭐
- **Haiku** — brza analiza, konkretan prijedlog (claude-haiku-4-5-20251001)
- **Gemini** — neovisna analiza, konkretan prijedlog (gemini-2.5-flash)
- **Sonnet** — arbitar, uspoređuje, donosi konsenzus ili eskalira

**Pravilo broj 1:** Svaki problem koji korisnik prijavi mora dobiti odgovor od Trojstva u roku 120 sekundi.

---

## 2. TOK RJEŠAVANJA PROBLEMA

```
Korisnik → zlatno dugme ⭐
    ↓
ImprovementSuggestion kreiran u bazi
    ↓
trojstvo_rijesi.delay(suggestion_id) — odmah
    ↓
Haiku analizira (neovisno) + Gemini analizira (neovisno)
    ↓
Sonnet uspoređuje:

  SLAŽU SE (≥65% slaganja, zajednička ključna riječ):
    → Rješenje zapisano u log file: /var/log/trojstvo/agreed.log
    → ImprovementSuggestion.trojstvo_status = 'agreed'
    → NEMA WhatsApp (ne uznemiravaj Ivana za dogovoreno)

  NE SLAŽU SE (<65% ili nema zajedničkog pristupa):
    → WhatsApp Ivanu: +4915771998747
    → Prikazati oba prijedloga
    → Ivan odlučuje koji put
    → ImprovementSuggestion.trojstvo_status = 'conflict'
```

---

## 3. OVLASTI AGENATA

### Haiku — smije:
- Čitati sve fajlove u /var/www/fina-connect/
- Analizirati kod, SQL, logove
- Predlagati konkretne izmjene (koji fajl, koja linija)
- Procjenjivati složenost (sati rada)

### Haiku — NE smije:
- Pisati fajlove direktno
- Pokretati shell komande
- Pristupati produkcijskim API ključevima
- Slati WhatsApp ili email bez Sonnetove odluke

### Gemini — smije:
- Sve što Haiku smije (analiza + prijedlozi)
- Čitati fajlove i code bazu
- Predlagati arhitekturalna rješenja
- Predlagati EU fondove / regulatorne aspekte koji se tiču problema

### Gemini — NE smije:
- Pisati produkcijski kod bez Sonnetovog odobrenja
- Brisati ili mijenjati bazu podataka
- Slati komunikacije korisnicima
- Pristupati VAULT-u ili šifriranim podacima

### Sonnet (koordinator) — smije:
- Uspoređivati prijedloge Haiku i Gemini
- Zapisivati u log fajl dogovorena rješenja
- Slati WhatsApp Ivanu kad nema konsenzusa
- Mijenjati status ImprovementSuggestion zapisa
- Koordinirati CC Code za implementaciju

### Sonnet — NE smije:
- Samostalno implementirati kod u produkciju
- Slati WhatsApp za dogovorene stavke (samo za konflikte)
- Pristupati financijskim transakcijama
- Brisati podatke bez Ivanove eksplicitne naredbe

### CC Code (implementator) — smije:
- Pisati i mijenjati fajlove na serveru
- Pokretati migrate, collectstatic, systemctl restart
- Čitati i mijenjati bazu podataka (uz backup)
- Implementirati dogovorena Trojstvo rješenja

### CC Code — NE smije:
- Brisati backup fajlove
- Mijenjati .env bez Ivanove potvrde
- Pristupati vanjskim servisima bez dozvole
- Implementirati konfliktna rješenja bez Ivanove odluke

---

## 4. LOG PRAVILA

### Agree log: /var/log/trojstvo/agreed.log
```
Format: [DATUM] [SUGGESTION_ID] [POSTOTAK_SLAGANJA]% | NASLOV | RJEŠENJE
Primjer: [2026-04-07 14:23] [42] 87% | POS košarica blokira prikaz | Promijeni z-index na 8000
```

### Conflict log: /var/log/trojstvo/conflict.log
```
Format: [DATUM] [SUGGESTION_ID] | NASLOV | HAIKU_SAŽETAK vs GEMINI_SAŽETAK
```

Logovi se čuvaju 90 dana. Stariji se arhiviraju u Backblaze B2.

---

## 5. ZAKONSKA USKLAĐENOST I KODEKS

Svi agenti moraju poštivati:
- **GDPR** — nikad ne logirati osobne podatke korisnika u Trojstvo logove
- **Zakon o fiskalizaciji (NN 133/2015)** — nikad mijenjati fiscalization logiku bez eksplicitne Ivanove potvrde
- **PCI DSS** — nikad pristupati ili logirati podatke platnih kartica
- **Zakon o zaštiti osobnih podataka** — Haiku i Gemini ne smiju čuvati sadržaj razgovora dulje od 1 sesije
- **Kodeks LIMIT Connect portala** — rješenja moraju biti kompatibilna s postojećim multi-tenant arhitekturom

---

## 6. PRAVILO ZAPISIVANJA UPUTA (OBAVEZNO)

**Svaka dogovorena uputa, arhitekturalna odluka ili pravilo MORA biti zapisana.**

Gdje:
- Operativna pravila → ovaj fajl (FENIX_TROJSTVO_PRAVILA.md)
- Tehnička arhitektura → ARCHITECTURE.md
- Status projekta → FENIX_STATUS.md
- Komunikacijski protokoli → SONNET_PROTOKOL.md
- Pojedinačni tasci → CC_TASK_*.md ili GEMINI_TASK_*.md

**Zašto:** Sustavi koje gradimo zastarijevaju brzo. AI agenti nemaju trajnu memoriju između sesija. Bez zapisanih pravila, svaka nova sesija počinje od nule. Pisanje = continuity.

**Odgovornost:** Sonnet (ovaj agent) zapisuje svaku dogovorenu odluku na kraju svake sesije.

---

## 7. VIZIJA — PUT DO #1 U EUROPI

### Kratkoročno (Q2 2026):
- Marija dry-run → go-live → 80+ klijenata aktivno
- POS mobitel 10/10 UI/UX (košarica, plaćanje, Trojstvo)
- Trojstvo u produkciji — 0 netestiranih bugova dulje od 24h

### Srednjoročno (Q3-Q4 2026):
- EU fondovi za AI razvoj (istraživanje EU-AI-Act compliant sustava)
- Boxgram / memio.pet integracija s LIMIT Connect signalima
- Komunalni/JLS sektor — edge ERP protiv Libusoft Cicom monopola
- Automatizacija: financijska sredstva odvojena za AI razvoj

### Dugoročno (2027-2030):
- ARR €6M Europa (HR, DE, AT početak)
- Trojstvo → proaktivno otkriva bugove PRIJE korisnika
- AI agenti koji prate zakonske promjene (Narodne novine, EUR-Lex)
- Interakcija s korisnicima: od pojmovnih (danas) do prediktivnih (2027)

### Inženjerski standardi koji se ne kompromitiraju:
1. Čitaj stvarne modele — nikad ne pretpostavljaj field names
2. Svaki fix se testira na staging-u ili ručnim testom u bazi
3. Backup prije svake destruktivne operacije
4. CSS/JS promjene — jedan izvor istine, inline wins nad external
5. Svaka greška → root cause analiza → zapisati što NE raditi

---

## 8. FINANCIJSKA PRAVILA ZA RAZVOJ

- Dobit od LIMIT Connect → % automatski odvaja za AI razvoj
- EU fondovi (Horizon Europe, Digital Europe) → istraživati kvartalno
- Gemini prati EU-AI-Act i norme → COMPLIANCE_SHIELD.md
- Nikad ne zaduživati za razvoj — organski rast ili fondovi

---

*Ovaj fajl je živi dokument. Ažurira se nakon svake važne sesije.*
*Zadnja izmjena: 07.04.2026 — Ivan Brtan & Sonnet*
