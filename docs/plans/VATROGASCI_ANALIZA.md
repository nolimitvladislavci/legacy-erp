# VATROGASCI — Tržišna analiza i LIMIT Connect strategija
# Datum: 2026-03-25
# Autor: Sonnet

---

## Tržišna veličina — HR

| Segment | Broj | Napomena |
|---------|------|---------|
| DVD (Dobrovoljno vatrogasno društvo) | ~1.800 | Svako selo ima DVD |
| JVP (Javna vatrogasna postrojba) | ~30 | Gradovi, županije |
| Vatrogasne zajednice (općine/gradovi) | ~420 | Koordinacijska tijela |
| Profesionalni vatrogasci (zaposleni) | ~3.500 | JVP, tvornice |
| Volonteri (DVD) | ~60.000 | Neoporezive naknade |

**Ukupna adresabilna tržišta: ~2.250 organizacija u HR**

---

## Zašto DVD = savršen LIMIT Connect klijent

### 1. Isti pravni okvir kao KUD-ovi (već riješeno)
- DVD = udruga → Zakon o udrugama (NN 74/14)
- Zakon o vatrogastvu (NN 125/19) + Zakon o volontiranju (NN 58/07)
- Nefiskaliziran promet (članarine, donacije) — **POS bypass već postoji**
- Financijsko izvještavanje = Zakon o financijskom poslovanju neprofitnih organizacija

### 2. Specifične financijske potrebe DVD-a
| Potreba | LIMIT Connect status |
|---------|---------------------|
| Evidencija članova + članarine | ✅ POS udruga ready |
| Putni nalozi (intervencije, smotre) | ✅ TravelOrder model + CC task |
| Volonterska evidencija + porezni limit | ✅ worktime/models.py is_volunteer |
| EU fondovi (HVATD, MUP natječaji) | ✅ EU fondovi modul |
| Knjiga prigovora | ✅ KnjigaPrigovora |
| Neoporezive naknade volonterima | ✅ volunteer_annual_limit |

### 3. Što DVD-u specifično nedostaje (NOVO)

#### A) Evidencija opreme i vozila
DVD ima: vatrogasna vozila, aparate za gašenje, osobnu zaštitnu opremu (OZO), crijeva, pumpe.
**Sve je to inventar** — LIMIT Connect `inventory` modul pokriva 80%.
Nedostaje: `servis/pregled` datum, `rok valjanosti atesta`, `vlasnik vs. zaprimljeno od MUP-a`.

#### B) Dnevnik intervencija
Svaka intervencija = zakonska obveza dokumentiranja (Zakon o vatrogastvu čl. 37).
Evidencija: datum/sat, adresa, vrsta intervencija, angažirani vatrogasci, vozila.
**Ovo je nova tablica** — ali je jednostavna.

#### C) Raspoređivanje dežurnih
DVD mora imati plan dežurstava. Worktime modul za smjene postoji — ali nema "interventna dežurnost" tip.

---

## Procjena prihoda

| Paket | Cijena/mj | Target |
|-------|-----------|--------|
| DVD Starter (članarine+putni+volonteri) | 9,99 EUR | 500 DVD-ova |
| DVD Pro (+dnevnik intervencija+oprema) | 19,99 EUR | 200 DVD-ova |
| JVP Enterprise (sve+rashodi+plaće) | 49,99 EUR | 30 JVP-a |

**Realni scenario (6 mj): 50 DVD-ova × 9,99 = ~500 EUR/mj recurring**
**Optimistični (12 mj): 300 DVD-ova = ~3.000 EUR/mj**

---

## GTM strategija — vatrogasci

### Ulazna točka: Vatrogasna zajednica Osječko-baranjske županije
- Osijek je base — Ivan tamo ima kontakte
- 1 zajednica = pristup svim DVD-ovima u županiji
- Predsjednik zajednice = decision maker za sve DVD-ove

### Prodajni argument (3 rečenice):
"DVD može prijaviti intervenciju na mobitelu dok se vozi prema vatri.
Volonterske naknade automatski ostaju ispod poreznog praga — nitko ne ide u prekršaj.
Putni nalog za smotru kreiraš za 30 sekundi, PDF šalješ Mariji — i gotovo."

### Viralni mehanizam:
Predsjednik jednog DVD-a pokazuje drugom predsjedniku na smotri.
DVD smotre = networking event — **Gemini treba mapirati kalendar smotri 2026**.

---

## Što odmah radi, što treba dograditi

### ✅ ODMAH RADI (bez razvoja):
- Upis članova + naplata članarine (POS udruga)
- Putni nalozi za smotre i natjecanja (TravelOrder)
- Volonterska evidencija + porezni limit alarm
- EU fondovi scanner (MUP natječaji, HVATD)
- Arhiva dokumenata (police osiguranja, atesti)
- Financijsko izvještavanje za skupštinu

### 🔨 TREBA DOGRADITI (CC Code, 2-3 dana):
1. **Dnevnik intervencija** — nova tablica `FireIntervention`
2. **Evidencija opreme** — extend `InventoryItem` s `atest_expiry`, `serial_number`, `mup_property`
3. **NKD 84.25** — ✅ upravo dodano u bazu

---

## Zakonski okvir (za COMPLIANCE_SHIELD)

| Zakon | Relevantnost |
|-------|-------------|
| Zakon o vatrogastvu (NN 125/19) | Dnevnik intervencija obvezan |
| Zakon o udrugama (NN 74/14) | DVD pravna forma, financije |
| Zakon o volontiranju (NN 58/07) | Volonterske naknade, limit |
| ZFP neprofitnih org. | Godišnji izvještaj |
| GDPR | Evidencija članova |

---

## Taskovi za agente

### CC Code: CC_TASK_VATROGASCI_MODUL.md
- `FireIntervention` model (10 polja, jednostavan)
- `InventoryItem` extend: atest_expiry + serial_number + is_mup_property
- Template: dnevnik intervencija (lista + forma + PDF)
- NKD 84.25 — ✅ DONE

### Gemini: GEMINI_TASK_VATROGASCI_GTM.md  
- Mapa DVD-ova u Osječko-baranjskoj županiji (broj, kontakti)
- Kalendar vatrogasnih smotri 2026 u HR
- MUP i HVATD natječaji 2026 za koje DVD može aplicirati
- Prodajni script za predsjednika DVD-a
