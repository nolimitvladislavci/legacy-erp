# CC_TASK — DNEVNI PLAN 01.04.2026
# Dodijelio: Sonnet | Izvršava: CC Code (autonomno)
# PRAVILO: Čitaj models.py prije SVAKOG koda. Ne pretpostavljaj field names.

---

## TASK 1 — /pricing/?profile= param fix 🔴 ODMAH

**Problem:** Pricing stranica ignorira `?profile=` URL parametar — korisnik koji dođe
s linka /pricing/?profile=opg ne vidi OPG plan preselektiran.

**Lokacija:** `website/views.py` (pricing view) + `templates/website/pricing.html`

**Što napraviti:**
1. U pricing viewu pročitaj `request.GET.get('profile', '')` i proslijedi u context
2. U template-u: ako `profile` u contextu matchira plan slug → dodaj `active`/`selected` CSS klasu na taj plan
3. Testiraj: `/pricing/?profile=opg`, `/pricing/?profile=udruga`, `/pricing/?profile=farma`
4. Provjeri da svih 7 profil selektora rade (retail, gastro, opg, udruga, farma, obrt, servis)

**Commit:** `fix: pricing page respects ?profile= URL param`

---

## TASK 2 — 3-klik registracija: OIB auto-fill 🔴 ODMAH

**Problem:** Nova firma se registrira bez auto-popunjavanja podataka iz OIB-a.
Korisnik mora ručno upisati sve — conversion rate pada.

**Lokacija:** `registration/views.py`, `registration/templates/`, `registration/urls.py`

**Što napraviti:**
1. API endpoint `/api/oib-lookup/?oib=12345678901` koji:
   - Poziva `https://api.e-racun.hr/api/company?oib={oib}` ili lokalni cache
   - Fallback: sudski registar scrape (ako postoji u codebase, provjeri)
   - Vraća: `{name, address, city, zip, country, pdv_obveznik}`
2. U registracija formi: JS koji na `blur` OIB fielda poziva endpoint i auto-popunjava
3. Loading spinner dok čeka
4. Ako OIB nije nađen → ne blokira, korisnik popunjava ručno

**Provjeri postoji li već:** `grep -rn "oib.lookup\|oib_lookup\|e-racun" /var/www/fina-connect/`

**Commit:** `feat: OIB auto-fill na registraciji — e-racun API lookup`

---

## TASK 3 — T&C Consent: 0/78 firmi 🟠 PRAVNI RIZIK

**Problem:** GDPR + ZZP zahtijevaju da sve aktivne firme imaju potpisane T&C.
Trenutno 0/78 aktivnih firmi nema consent zapis.

**Lokacija:** `core/models.py` (ili gdje je ConsentRecord), `core/views.py`

**Što napraviti:**
1. Provjeri koliko firmi ima consent: 
   ```python
   from core.models import ConsentRecord  # ili pravi model name
   ConsentRecord.objects.filter(consent_type='terms').count()
   ```
2. Ako nema ConsentRecord modela — kreiraj ga (company FK, consent_type, signed_at, ip_address, version)
3. Middleware ili login hook koji redirecta na `/consent/` ako firma nema potpisan consent
4. `/consent/` stranica: prikaži T&C tekst, "Prihvaćam" gumb → kreira zapis
5. Superadmin može bulk-prihvatiti za Synesis firme bez usera
6. Test: login kao Marija → trebala bi vidjeti consent prompt

**Commit:** `feat: T&C consent enforcement — GDPR čl.6(1)(b) + ZZP compliance`

---

## TASK 4 — POS sim skripta: receipt_number fix 🟠

**Problem:** `scripts/pos_sim_all.py` ima 2 buga:
1. `receipt_number` — PositiveIntegerField, treba `next_receipt_num()` 
2. S4 field sesija — `opening_cash` duplikat argument

**Što napraviti:**
1. Pročitaj skriptu: `cat /var/www/fina-connect/scripts/pos_sim_all.py`
2. Pročitaj model: grep za POSReceipt/POSSession modele u `pos/models.py`
3. Popravi oba buga
4. Pokreni: `cd /var/www/fina-connect && venv/bin/python scripts/pos_sim_all.py`
5. Svi scenariji moraju proći: S1-S6 zeleni

**Commit:** `fix: pos_sim_all.py — receipt_number next_receipt_num(), S4 opening_cash`

---

## TASK 5 — FINA eRačun namespace fix 🟠

**Problem:** SOAP poziv na FINA sandbox vraća "Sistemska pogreška" — pogrešan XML namespace.

**Lokacija:** `invoicing/services/eracun_service.py` (ili sličan naziv)

**Što napraviti:**
1. `grep -rn "eracun\|eRacun\|namespace\|xmlns" /var/www/fina-connect/invoicing/`
2. Usporedi namespace s FINA UBL 2.1 specifikacijom:
   - `urn:oasis:names:specification:ubl:schema:xsd:Invoice-2`
   - `urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2`
   - `urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2`
3. Pokreni test SOAP poziv na sandbox
4. Log puni response XML da vidimo grešku

**Commit:** `fix: eRacun UBL namespace — FINA sandbox XML compliance`

---

## REDOSLJED IZVRŠAVANJA

```
TASK 1 → TASK 2 → TASK 4 → TASK 3 → TASK 5
(od najbrže do najkompleksnije)
```

---

## PO ZAVRŠETKU SVEGA

```bash
cd /var/www/fina-connect
git log --oneline -10
```

Ažuriraj FENIX_STATUS.md:
- Sve DONE taskove premjesti u DEPLOYAN sekciju s datumom 01.04.2026 i commitom
- "Zadnje azuriranje: 2026-04-01 — CC Code" + git HEAD hash
- Otvorene probleme koji su riješeni — makni iz liste

