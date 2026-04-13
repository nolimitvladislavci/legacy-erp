# Pupilla Synesis — Gap analiza modul po modul

## Datum: 05.04.2026. | Autor: Fenix AI

---

## LEGENDA
- ✅ IMAMO — potpuno pokriveno
- 🟡 DJELOMIČNO — postoji ali nepotpuno
- ❌ NEMAMO — rupa
- 🔵 BOLJE — mi imamo više nego Pupilla

---

## A. FINANCIJSKO / KONTO (150€)
| Pupilla feature | LIMIT Connect | Status |
|---|---|---|
| Glavna knjiga | konto.JournalEntry + LedgerLine | ✅ |
| Kontni plan (HR) | konto.KontoAccount | ✅ |
| Dnevnik knjiženja | JournalEntry list + filter | ✅ |
| Automatsko knjiženje iz dokumenta | invoice_service + GoodsReceipt.book() | ✅ |
| Bruto bilanca | views (debit/credit summa) | ✅ |
| Zaključak godine | AccountingPeriod model | ✅ |
| **Profitni centri** | ❌ Nema CostCenter/ProfitCenter | ❌ |
| **Blagajna (konto)** | POS cash tracking, ali ne kao konto blagajna | 🟡 |
| **Saldakonti (otvorene stavke)** | ❌ Nema OpenItem/aging per partner u konto | ❌ |

### RUPE: Profitni centri, Konto blagajna, Saldakonti

---

## B. PDV (150€)
| Pupilla feature | LIMIT Connect | Status |
|---|---|---|
| PDV obrazac | pdv_s.PDVSReport | ✅ |
| PDV po stopama | Tax rates na InvoiceItem | ✅ |
| IRA/URA knjiga | invoicing (IRA) + documents (URA) | ✅ |
| PDV EU | pdv_s + einvoice | ✅ |
| OSS | tax_wizard | ✅ |
| Storno PDV | Storno invoice PDV recalc | ✅ |

### RUPE: Nema ✅

---

## C. PLAĆE (150€)
| Pupilla feature | LIMIT Connect | Status |
|---|---|---|
| Obračun plaća | payroll.PayrollRun + Payslip | ✅ |
| JOPPD | payroll JOPPD archive | ✅ |
| Minuli rad | EmployeeProfile.years_experience | ✅ |
| Bolovanje/Godišnji | worktime (attendance) | ✅ |
| IP1 obrazac | — | 🟡 |
| **Honorari** | ❌ Nema odvojenog modula za autorske/honorarne | ❌ |

### RUPE: Honorari (ugovori o djelu, autorski honorari)

---

## D. PRODAJA / MALOPRODAJA / VELEPRODAJA
| Pupilla feature | LIMIT Connect | Status |
|---|---|---|
| **Maloprodaja** (135€) | pos modul (POS Joker, Quick, Restaurant) | 🔵 Više |
| **Veleprodaja** (135€) | invoicing (IRA) + inventory + delivery | ✅ |
| Račun (IRA) | invoicing.Invoice | ✅ |
| Ponuda / Predračun | Invoice(type='quote') | ✅ |
| **Otpremnica** | propter.Otpremnica (auto iz fakture) | ✅ |
| **Primka** (robno) | inventory.GoodsReceipt (7 tipova!) | 🔵 |
| Povratna primka | GoodsReceipt(type='return') | ✅ |
| Konsignacijska primka | GoodsReceipt(type='consignment') | ✅ |
| Reklamacijska primka | GoodsReceipt(type='complaint') | ✅ |
| **Posebni cjenik za kupca** | ❌ Nema CustomerPriceList modela | ❌ |
| Kalkulacija maloprodajne cijene | PriceChange model | ✅ |
| Nivelacija cijena | PriceChange model | ✅ |
| Fiskalizacija | fiskalizacija modul (HR + DE) | 🔵 |
| **Narudžbenice (purchase)** | procurement.PurchaseOrder + auto-reorder | 🔵 |
| **Narudžbenice (sales)** | ❌ Nema SalesOrder odvojen od Invoice | ❌ |

### RUPE: Posebni cjenici za kupce, Sales Order (narudžbenica kupca)

---

## E. ROBNO / SKLADIŠTE / INVENTAR
| Pupilla feature | LIMIT Connect | Status |
|---|---|---|
| Artikli / Roba | inventory.InventoryItem | ✅ |
| Kategorije | InventoryItem groups | ✅ |
| Skladišta (multi) | inventory.Warehouse (4 tipa) | ✅ |
| **Međuskladišnica** | inventory.WarehouseTransfer + items | ✅ |
| Inventura | inventory.Inventura + commission | 🔵 |
| Kretanje zaliha | StockMovement (10 tipova!) | 🔵 |
| Serije / šarže | StockBatch + production batch | ✅ |
| Rok trajanja | ExpiryBatch (POS) | ✅ |
| Upravljanje zalihama | reorder.py auto-PurchaseOrder | 🔵 |
| **Materijalno knjiženje** | GoodsReceipt.book() → konto | ✅ |
| **Sljedivost** | traceability app | ✅ |
| Min/Max zaliha | reorder thresholds | ✅ |

### RUPE: Nema ✅ (bolje od Pupille)

---

## F. PLATNI PROMET (100€)
| Pupilla feature | LIMIT Connect | Status |
|---|---|---|
| Virman | konto.BankTransaction | ✅ |
| Uvoz izvoda (FINA) | — | ❌ |
| Kompenzacije | — | ❌ |
| Cesije | — | ❌ |

### RUPE: FINA izvod uvoz, Kompenzacije, Cesije

---

## G. PUTNI TROŠKOVI / LOCCO (100€ + 70€)
| Pupilla feature | LIMIT Connect | Status |
|---|---|---|
| Putni nalog | worktime.TravelOrder | ✅ |
| Troškovi puta | worktime.TravelExpense | ✅ |
| Dnevnice | TravelOrder.daily_allowance | ✅ |
| Locco vožnja | worktime.MileageLog | ✅ |
| Obračun km | auto kalkulacija | ✅ |

### RUPE: Nema ✅

---

## H. KADROVI (115€)
| Pupilla feature | LIMIT Connect | Status |
|---|---|---|
| Evidencija zaposlenika | worktime.EmployeeProfile | ✅ |
| Ugovori o radu | — | 🟡 |
| Godišnji odmor | attendance tracking | ✅ |
| Bolovanje | attendance tracking | ✅ |

### RUPE: Ugovori o radu model

---

## I. OSTALI MODULI
| Pupilla modul | Cijena | LIMIT Connect ekvivalent | Status |
|---|---|---|---|
| Autoservis | 130€ | work_orders (generički) | 🟡 |
| Autoservis II | 130€ | — | ❌ |
| Članarine | 130€ | udruge modul | ✅ |
| Dividende | 70€ | — | ❌ |
| GDPR | 130€ | ugrađen (Fernet AES, GDPR export) | 🔵 |
| Knjiga gostiju | 130€ | — | ❌ |
| Komercijalisti | 100€ | outreach + registration/agents | ✅ |
| Komisija | 110€ | consignment u GoodsReceipt | ✅ |
| Montaža | 115€ | work_orders | ✅ |
| Neprofit | 130€ | udruge modul | ✅ |
| Paušal | 90€ | tax_wizard | ✅ |
| Projektne usluge | 135€ | projects modul | ✅ |
| Recepcija | 130€ | appointments modul | ✅ |
| Restoran | 130€ | pos gastro + KDS + waiter | 🔵 |
| Rezervacije | 70€ | appointments | ✅ |
| Servis | 130€ | work_orders | ✅ |
| Završni račun | 150€ | konto AccountingPeriod | ✅ |
| **Kamate** | 70€ | ❌ | ❌ |
| **Intrastat** | 130€ | ❌ | ❌ |

---

## SUMARNO — SVE RUPE

| # | Rupa | Pupilla cijena | Ozbiljnost | Tko treba |
|---|---|---|---|---|
| 1 | **Posebni cjenici za kupca** | 135€ (u Prodaja) | 🔴 Kritično | Svaka veleprodaja |
| 2 | **Sales Order (narudžbenica kupca)** | 90€ (Obrada narudžbi) | 🔴 Kritično | Veleprodaja, B2B |
| 3 | **Saldakonti** | 110€ | 🔴 Kritično | Svaka računovođa |
| 4 | **Profitni centri** | 130€ | 🟡 Srednje | Veće firme s odjelima |
| 5 | **Konto blagajna** | 100€ | 🟡 Srednje | Firme s gotovinom van POS-a |
| 6 | **Honorari** | 130€ | 🟡 Srednje | Firme s autorskim ugovorima |
| 7 | **FINA izvod uvoz** | (u Platni promet) | 🟡 Srednje | Svaka firma |
| 8 | **Kompenzacije/Cesije** | (u Platni promet) | 🟡 Srednje | B2B |
| 9 | **Kamate obračun** | 70€ | 🟢 Minor | Financijske firme |
| 10 | **Intrastat** | 130€ | 🟢 Minor | Samo uvoz/izvoz EU |
| 11 | **Knjiga gostiju** | 130€ | 🟢 Minor | Turizam |
| 12 | **Dividende** | 70€ | 🟢 Minor | d.o.o. s više vlasnika |
| 13 | **Autoservis II** | 130€ | 🟢 Nišno | Samo autoservisi |

---

## PREPORUKA — PRIORITET ZATVARANJA

### ODMAH (ova sesija):
1. **Posebni cjenici** — CustomerPriceList model + primjena u POS i invoicing
2. **Sales Order** — SalesOrder model (odvojen od Invoice, convertible)
3. **Saldakonti** — OpenItem view na konto (aging po partneru)

### Ovaj tjedan:
4. Profitni centri — CostCenter FK na LedgerLine
5. FINA izvod uvoz — XML/CSV parser za bankovne izvode
6. Honorari — HonorarContract + obračun

### Kasnije:
7-13. Konto blagajna, kompenzacije, cesije, kamate, Intrastat, knjiga gostiju, dividende

---

## ZA SYNESIS REVERSE ENGINEERING (Marijin PC):

Kad pokreneš Synesis, provjeri:
1. **Posebni cjenici** → kako definira cijene po kupcu? Popust % ili fiksna cijena?
2. **Obrada narudžbi** → flow: narudžba → potvrda → otpremnica → faktura?
3. **Saldakonti** → kako prikazuje otvorene stavke? Aging 30/60/90?
4. **Platni promet** → format FINA izvoda koji uvozi?
5. **Komisija** → flow komisijske prodaje?
6. **Profitni centri** → na kojoj razini? LedgerLine ili JournalEntry?

Javi mi što vidiš — mogu odmah implementirati #1, #2, #3.
