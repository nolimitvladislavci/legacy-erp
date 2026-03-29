# CC_TASK_VRTIC_I_DOMOVI — Dvije nove vertikale
# Dodijeljen: CC Code
# Prioritet: P1 — revenue driver, Q2 2026
# Procjena: Vrtići 2 tjedna, Domovi Light 1 tjedan

---

## FAZA 1: PRIVATNI VRTIĆI (Q2 2026 — Quick Win)

### Modul 1 — Evidencija djece (kindergarten app)
- Dijete: ime, prezime, datum rođenja, OIB, grupa, alergije, posebne potrebe
- Roditelj/skrbnik: ime, telefon, email, OIB, relacija (majka/otac/skrbnik)
- Grupa: naziv, odgajateljica, kapacitet, dobna skupina
- Upis: datum upisa, datum ispisa, status (aktivan/pasivan/čekanje)
- GDPR čl.8: djeca < 16 — pristanak roditelja OBAVEZAN

### Modul 2 — Automatizirana naplata s izostancima
- Mjesečna cijena po djetetu (konfigurabilan)
- Evidencija dolazaka (prisutno/odsutno/bolovanje)
- Odbitak za izostanke: cijena obroka × broj dana odsutnosti
- Generator mjesečne uplatnice (poziv na broj = OIB djeteta)
- Integracija s invoicing modulom (automatski račun roditelju)

### Modul 3 — Roditeljski portal (web, ne app)
- Javni URL: /vrtic/<slug>/portal/ (login roditelja)
- Dnevni izvještaj odgajateljice (tekst + slike)
- Obavijesti (roditeljski sastanak, izlet, promjena jelovnika)
- Pregled dolazaka i računa svog djeteta
- Kontakt forma za odgajateljicu

### Modul 4 — Kuhinja/normativi (HACCP)
- Jelovnik tjedni (ponedeljak-petak, doručak/ručak/užina)
- BOM normativi po obroku (već postoji u inventory)
- Auto-izračun namirnica za N djece × normativ
- Lista nabave (print/PDF)

### Modul 5 — Pedagoška dokumentacija
- Dnevnik rada odgajateljice
- Razvojne bilješke po djetetu (opcijalno)
- Godišnji plan i program

---

## FAZA 2: DOMOVI ZA STARIJE — LIGHT (Q4 2026)

### CRVENE LINIJE (NE DIRATI):
- ❌ CEZIH integracija (6-12 mj certifikacija)
- ❌ Evidencija lijekova (čl.9 GDPR, posebna kategorija)
- ❌ Medicinski karton (zdravstveni podaci)
- ❌ HZZO fakturiranje (zahtijeva certifikaciju)

### Light moduli (SIGURNI):
1. Korisnici doma: ime, datum rođenja, soba, datum prijema, status
2. Srodnici/kontakti: tko je odgovorna osoba, telefon, email
3. Naplata boravka: mjesečna cijena, faktura srodniku/obitelji
4. Smjene osoblja: tko radi kad, raspored
5. Aktivnosti: dnevne aktivnosti korisnika (ne medicinske)

---

## IMPLEMENTACIJA — Modul 1+2+3 (danas)

### App: kindergarten/
### Modeli:
- KindergartenGroup (grupa)
- Child (dijete)
- Guardian (roditelj/skrbnik)
- ChildGuardian (M2M s relacijom)
- Attendance (evidencija dolazaka)
- MonthlyInvoice (mjesečna uplatnica)
- DailyReport (dnevni izvještaj)
- Announcement (obavijest)

### URL struktura:
- /vrtic/ — dashboard
- /vrtic/djeca/ — lista djece
- /vrtic/djeca/<pk>/ — detalj djeteta
- /vrtic/grupe/ — grupe
- /vrtic/dolasci/ — evidencija dolazaka
- /vrtic/naplata/ — mjesečne uplatnice
- /vrtic/<slug>/portal/ — roditeljski portal (public, auth)
