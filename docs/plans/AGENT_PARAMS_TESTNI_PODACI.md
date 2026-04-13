# VAŽAN PARAMETAR ZA SVE AI AGENTE — Testni podaci i zakonski propisi
## Datum: 2026-03-27 | Naređuje: Sonnet (koordinator)
## OBAVEZNO ČITATI PRIJE SVAKE COMPLIANCE PROVJERE

---

## KRITIČNA NAPOMENA — TESTNI PODACI

### Što je u bazi

| Godina | Broj dok. | Izvor | Status |
|--------|-----------|-------|--------|
| 2011-2024 | ~6.000 | Synesis uvoz (migracija) | **TESTNI/HISTORIJSKI** |
| 2025 | 11.383 | Synesis uvoz (migracija) | **TESTNI/HISTORIJSKI** |
| 2026 | 236 | Manual unos | **PRODUKCIJA — PRAVI** |
| POS 2026 | 251 | Blagajne klijenata | **PRODUKCIJA — PRAVI** |

**Svi `synesis_id IS NOT NULL` dokumenti = uvezeni historijski podaci.**
**NIKAD ne primijeniti compliance pravila 2026 na historijske podatke.**

---

## ZAKONSKI PARAMETRI PO GODINI

### HR — Hrvatska

| Period | Što je vrijedilo |
|--------|-----------------|
| Pre-2023 | Kuna (HRK), stara Fiskalizacija 1.0, PDV 25%/13%/5% |
| 01.01.2023. | **Euro uveden** — HRK fakture su legalne historijske, ne tretirati kao grešku |
| 01.07.2023. | eRačun B2G obveza — SAMO za javnu nabavu |
| 2024 | PDV stope nepromijenjene, fiskalizacija stabilna |
| 2025 | Synesis migracija — ovo NISU pravi propisi, ovo su testni podaci |
| 01.01.2026. | **Naši pravi klijenti počinju.** eRačun B2B planirano. |

**Primjenjuj HR compliance provjere SAMO na dokumente s `date_issued >= 2026-01-01`.**

### DE — Njemačka

| Period | Što je vrijedilo |
|--------|-----------------|
| 07-12.2020. | COVID: PDV 16%/5% — legalno, ne grešku |
| 01.01.2021. | Povratak na 19%/7% |
| 01.01.2023. | Kleinunternehmer: 22.000€/50.000€ granica |
| 01.01.2025. | **e-Rechnung obveza za B2B (primanje i slanje)** |
| 01.01.2025. | Kleinunternehmer nova granica: 25.000€/100.000€ |

**DE e-Rechnung compliance: SAMO za dokumente `date_issued >= 2025-01-01`.**

---

## PRAVILO ZA AI AGENTE (obvezno)

```python
def is_production_document(invoice) -> bool:
    """
    True = pravi produkcijski dokument koji treba compliance provjeru.
    False = historijski/testni, SKIP compliance.
    """
    # Synesis uvoz = historijski
    if invoice.synesis_id:
        return False
    
    # Stari dokumenti (pre-2026 manual unos = edge case, ali ne compliance target)
    if invoice.date_issued:
        year = invoice.date_issued.year if hasattr(invoice.date_issued, 'year') else 2000
        if year < 2026:
            return False
    
    return True


def get_applicable_rules(invoice_date, country='HR') -> dict:
    """
    Vrati koja pravila vrijede za dati datum dokumenta.
    NE primjenjuj 2026 propise na 2024 dokument.
    """
    year = invoice_date.year if hasattr(invoice_date, 'year') else invoice_date
    
    if country == 'HR':
        return {
            'pdv_standard': 25,
            'pdv_snizena': 5,
            'pdv_13': year >= 2025,          # 13% ugostiteljstvo od 2025
            'eracun_b2b': year >= 2026,       # B2B eRačun obveza
            'currency': 'EUR' if year >= 2023 else 'HRK',
            'fiskalizacija_version': '3.0' if year >= 2026 else ('2.0' if year >= 2023 else '1.0'),
            'check_compliance': year >= 2026, # SAMO 2026+ dokumenti
        }
    
    elif country == 'DE':
        return {
            'mwst_standard': 19,
            'mwst_reduced': 7,
            'mwst_covid': 16 if (year == 2020) else 19,  # COVID iznimka
            'erechnung_b2b': year >= 2025,   # E-Rechnung obveza
            'kleinunternehmer_limit': 25000 if year >= 2025 else 22000,
            'check_compliance': year >= 2025, # DE compliance od 2025
        }
    
    return {}
```

---

## PRIMJER ISPRAVNE PROVJERE

```python
# POGREŠNO (ne raditi ovo):
def check_all_invoices():
    for invoice in Invoice.objects.all():
        check_compliance(invoice)  # Primjenjuje 2026 pravila na 2014 dokument!

# ISPRAVNO:
def check_all_invoices():
    # Samo produkcijski dokumenti
    production = Invoice.objects.filter(
        synesis_id__isnull=True,        # Nije Synesis uvoz
        date_issued__year__gte=2026,     # 2026+
    )
    for invoice in production:
        check_compliance(invoice)
```

---

## COMPLIANCE REPORT KONTEKST

Svaki compliance report mora navesti:
```
NAPOMENA: Analiza se odnosi isključivo na dokumente iz 2026+ (produkcija).
Historijski podaci (2011-2025, Synesis uvoz, 15.325 dok.) su ISKLJUČENI
iz compliance provjera jer se na njih primjenjuju propisi koji su tada
bili na snazi, a ne aktualni propisi.
```

---

## ZA HAIKU KLASIFIKATOR

Kad klasificiraš invoice dokumente, uzmi u obzir:
- Valuta HRK na dokumentu pre-2023 = NORMALNO, ne greška
- PDV 23% pre-2012 = historijski (stopa je bila drugačija)
- PDV 16% u 2020. = COVID iznimka DE, NORMALNO
- Nedostajući ZKI/JIR pre-2023 = NORMALNO (stara fiskalizacija)
- Synesis source = historijski uvoz, bez compliance provjere


---
## ⚠️ LEGAL PARAMS — AŽURIRANO 2026-03-27

**OBAVEZNO ČITAJ PRIJE COMPLIANCE KODA:**
```bash
cat LEGAL_PARAMS_MASTER.md
```

**LEGAL_PARAMS_MASTER.md** sadrži:
- HR PDV stope po godinama (2013–2026+) s NN brojevima
- HR Fiskalizacija v1.0→v2.0 (NN 133/12 → NN 89/25) s točnim datumima
- DE MwSt povijest (uključivo COVID 16%/5% 07-12.2020.)
- DE E-Rechnung timeline (2025 primanje, 2026-2028 slanje)
- HRK/EUR tranzicija (01.01.2023., tečaj 7,53450)
- Compliance matrica po periodu
- SQL/Django filter za produkcijske dokumente
