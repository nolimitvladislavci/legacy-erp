# FINA-Connect × Synesis — Plan testiranja
**Datum:** 05.03.2026
**Tester:** _______________
**Računalo:** Windows PC s instaliranim Synesis ERP i SynesisPOS

---

## PRIPREMA (jednom)

Prijavi se na portal: **https://viskovic-group.de**
Korisnik: Konjik d.o.o. admin

---

## TEST 1 — Synesis postavke na portalu

**URL:** https://viskovic-group.de/synesis/

| # | Što provjeriti | Očekivano | ✓/✗ | Napomena |
|---|---|---|---|---|
| 1.1 | Stranica se otvara | 200 OK, bez greške | | |
| 1.2 | API Token vidljiv | Token prikazan, može se kopirati gumbom | | |
| 1.3 | Storage.mdb putanja | `C:\Synesis\KONJIK2025\Storage.mdb` | | |
| 1.4 | Journal.mdb putanja | `C:\Synesis\KONJIK2025\Journal.mdb` | | |
| 1.5 | SynesisPOS baza | `C:\SynesisPOS\Kasa2025-01.mdb` | | |
| 1.6 | POS lozinka | Lozinka upisana (prikazano kao ****) | | |
| 1.7 | Gumb "Preuzmi Setup (.bat)" | Skida `synesis_setup.bat` | | |
| 1.8 | Gumb "Samo .py skripta" | Skida `synesis_sync.py` | | |
| 1.9 | Sidebar link "Synesis" | Vidljiv pod "Integracije" u meniju | | |

---

## TEST 2 — Jednom: Pokretanje setup instalera

**Na Windows računalu** s Synesis-om:

| # | Korak | Očekivano | ✓/✗ | Napomena |
|---|---|---|---|---|
| 2.1 | Otvori portal, klikni "Preuzmi Setup (.bat)" | Skida `synesis_setup.bat` | | |
| 2.2 | Dvostruki klik na `synesis_setup.bat` | Otvori se crni prozor | | |
| 2.3 | Vidi `[OK] Python pronađen` | Zeleni OK bez greške | | Ako GREŠKA: instalirati Python s python.org, označiti "Add to PATH" |
| 2.4 | Vidi `[OK] Paketi instalirani` | pyodbc i requests instalirani | | Ako GREŠKA: pokrenuti kao Administrator |
| 2.5 | Vidi `[OK] Skripta preuzeta` | synesis_sync.py preuzeta s portala | | |
| 2.6 | Vidi `[OK] Automatska sinkronizacija: svaki dan u 02:00` | Scheduled Task kreiran | | Ako UPOZORENJE: pokrenuti kao Administrator |
| 2.7 | Vidi `=== SYNESIS SYNC ... ===` | Počela prva sinkronizacija | | |
| 2.8 | Vidi `[PARTNERI] Čitam iz Synesis...` | Čitanje Storage.mdb | | |
| 2.9 | Vidi `Pronašao 957 partnera` | Broj partnera u Synesis bazi | | Može biti drugačiji broj |
| 2.10 | Vidi `[ARTIKLI] Čitam iz Synesis...` | Čitanje Storage.mdb ITEMS | | |
| 2.11 | Vidi `Pronašao 2734 artikala` | Broj artikala u bazi | | |
| 2.12 | Vidi `[POS KASA] Čitam iz SynesisPOS...` | Čitanje Kasa2025-01.mdb | | |
| 2.13 | Vidi `=== GOTOVO za Xs ===` | Sync završen bez grešaka | | |
| 2.14 | Prozor se zatvori | Setup završen | | |

---

## TEST 3 — Dashboard widget (odmah po syncu)

**URL:** https://viskovic-group.de/dashboard/company/

| # | Što provjeriti | Očekivano | ✓/✗ | Napomena |
|---|---|---|---|---|
| 3.1 | Widget "Synesis integracija" vidljiv | Prikazan na dashboardu | | |
| 3.2 | ERP — broj partnera | ≥ 900 (iz Synesis baze) | | |
| 3.3 | ERP — broj artikala | ≥ 2000 (iz Synesis baze) | | |
| 3.4 | ERP — datum zadnje sync | Danas, npr. "05.03 14:32" | | |
| 3.5 | POS — Kasa 1 sekcija vidljiva | "Kasa 1 — SynesisPOS" | | Samo ako POS ima računa |
| 3.6 | POS — prihod danas | EUR iznos ili 0.00 | | 0 je OK ako nema računa danas |
| 3.7 | Gumb "Preuzmi Setup (.bat)" na widgetu | Radi, skida .bat | | |

---

## TEST 4 — Partneri uvezeni

**URL:** https://viskovic-group.de/partners/

| # | Što provjeriti | Očekivano | ✓/✗ | Napomena |
|---|---|---|---|---|
| 4.1 | Popis partnera prikazuje uvezene | > 900 partnera | | |
| 4.2 | Partner ima naziv, OIB, adresu | Podaci ispravni | | |
| 4.3 | Klikni na jednog partnera | Detalji se otvaraju | | |
| 4.4 | Drugi put pokrenuti sync (2.bat) | Partneri se ažuriraju, ne dupliciraju | | |

---

## TEST 5 — Artikli uvezeni

**URL:** https://viskovic-group.de/inventory/

| # | Što provjeriti | Očekivano | ✓/✗ | Napomena |
|---|---|---|---|---|
| 5.1 | Artikli prikazani | > 2000 artikala | | |
| 5.2 | Artikl ima naziv, šifru "SYN-xxx", cijenu | Podaci ispravni | | |
| 5.3 | PDV stopa ispravna | 25%, 13% ili 5% | | |
| 5.4 | Drugi put sync ne duplicira | Isti broj artikala | | |

---

## TEST 6 — Synesis log

**URL:** https://viskovic-group.de/synesis/

| # | Što provjeriti | Očekivano | ✓/✗ | Napomena |
|---|---|---|---|---|
| 6.1 | Tablica "Povijest sinkronizacija" | Vidljivi redovi synca | | |
| 6.2 | Sync tip: Partneri, Artikli | Badge prikazan | | |
| 6.3 | Kolona "Kreirano" | Broj kreiranih zapisa | | |
| 6.4 | Kolona "Greške" | 0 (idealno) | | |
| 6.5 | Trajanje | Prikazano u sekundama | | |

---

## TEST 7 — Automatski sync (sutradan)

| # | Što provjeriti | Očekivano | ✓/✗ | Napomena |
|---|---|---|---|---|
| 7.1 | Windows Task Scheduler | "FinaConnect-SynesisSync" postoji | | Start → Task Scheduler |
| 7.2 | Sutradan ujutro na dashboardu | Datum sync-a = danas ujutro | | |
| 7.3 | Bez intervencije | Sync se odvio automatski | | |

---

## GREŠKE — što raditi

| Greška | Uzrok | Rješenje |
|---|---|---|
| Python nije pronađen | Python nije instaliran ili nije u PATH | https://www.python.org/downloads/ → "Add to PATH" |
| Scheduled Task nije kreiran | Nedostatak admin prava | Pokrenuti setup.bat kao Administrator |
| Preuzimanje skripte neuspješno | Internet ili token problem | Provjeriti vezu, regenerirati token na portalu |
| Error 401 u syncu | Token nije ispravan | Klik "Regeneriraj token" → ponovo preuzmi setup.bat |
| Greška u bazi | .mdb zaključana od strane Synesis | Zatvoriti Synesis, ponovo pokrenuti sync |
| Broj greška > 0 | Provjeri log detalje | /synesis/ → tablica logova → detalji greške |

---

## BILJEŠKE TESTERA

```
Datum testa: _______________
Tester: _______________
Windows verzija: _______________
Python verzija: _______________
Synesis verzija: _______________

Broj uvezenih partnera: _______________
Broj uvezenih artikala: _______________
Trajanje synca: _______________

Problemi: _______________________________________________
          _______________________________________________
```
