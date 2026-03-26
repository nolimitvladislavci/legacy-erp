# GEMINI TASK: Commercial Document Compliance Watchdog
## Agent: Gemini 2.5 Flash | Prioritet: VISOK | Datum: 2026-03-27
## Autonomija: Sonnet ovlastio — radi bez odobrenja, spremi report

---

## MISIJA

Provjeri sve firme u sustavu na invoice compliance probleme i napiši report.
Posebno: HR PDV stope, DE e-Rechnung obveza, avansni bez završnih, udruge exempt.

## Koraci

### Korak 1: Čitaj relevantne modele
```
read_file invoicing/models.py
read_file propter/models.py
read_file invoicing/fiscal_rules.py (ako postoji)
```

### Korak 2: Provjeri stanje baze
```sql
-- PDV stope po NKD sektoru
SELECT c.name, c.nkd_code_id, i.tax_rate, COUNT(*) as cnt
FROM inventory_inventoryitem i
JOIN companies_company c ON i.company_id = c.id
WHERE i.tax_rate = 25
GROUP BY c.id, c.name, c.nkd_code_id, i.tax_rate
ORDER BY cnt DESC
LIMIT 20;

-- Avansni bez završnih > 90 dana
SELECT number, date_issued, total, company_id
FROM invoicing_invoice
WHERE doctype = 'A'
AND date_issued < NOW() - INTERVAL '90 days'
AND status IN ('CONFIRMED','SENT','PAID');

-- BillingPeriod status
SELECT company_id, year, month, status, otpremnica_count
FROM propter_billingperiod
ORDER BY year DESC, month DESC;

-- Invoice doctypes koji postoje
SELECT doctype, COUNT(*) as n
FROM invoicing_invoice
GROUP BY doctype ORDER BY n DESC;
```

### Korak 3: Compliance analiza (Gemini mozak)
Analiziraj podatke iz baze i identificiraj:
1. Firme s pogrešnim PDV stopama na artiklima (prehrambeni sektor → 5%)
2. Avansni računi bez završnih (Porezna uprava rizik)
3. DE firme bez e-Rechnung od 2025
4. Udruge s nepravilnom fiskalizacijom
5. BillingPeriod-i s otpremnicama koji nisu fakturirani

### Korak 4: Spremi report
Spremi u: `/var/www/fina-connect/COMPLIANCE_INVOICE_REPORT_20260327.md`

Format:
```markdown
# Invoice Compliance Report — 2026-03-27

## Kritični problemi (BLOCK)
...

## Upozorenja (WARN)
...

## Preporuke za admin
...

## Automatski planirane akcije
...
```

### Korak 5: Kreiraj ComplianceWatchItem za svaki nalaz
```python
from limit_connect_ai.models import ComplianceWatchItem
from companies.models import Company

ComplianceWatchItem.objects.get_or_create(
    company=company,
    category='INVOICE_PDV',
    defaults={
        'title': 'X artikala s pogrešnom PDV stopom',
        'severity': 'high',
        'is_active': True,
        'ai_notes': 'Auto-detected by Gemini compliance scan',
    }
)
```

## Output fajlovi
1. `/var/www/fina-connect/COMPLIANCE_INVOICE_REPORT_20260327.md`
2. ComplianceWatchItem zapisi u bazi za svaki nalaz

---

## ⚠️ KRITIČNI PARAMETAR — DODANO 2026-03-27

**OBAVEZNO PROČITAJ: `AGENT_PARAMS_TESTNI_PODACI.md`**

### SQL upiti — OBAVEZNI FILTER

Svaki SQL upit mora imati WHERE uvjet za produkcijske podatke:

```sql
-- UVIJEK koristiti ovaj filter:
WHERE synesis_id IS NULL
AND EXTRACT(year FROM date_issued) >= 2026

-- NIKAD:
-- bez WHERE filtera
-- WHERE EXTRACT(year FROM date_issued) = 2025  (to je Synesis uvoz)
```

### Zakonski parametri za analizu

- PDV provjere: vrijede od 2026, HR standard 25%, snižena 5%, ugostiteljstvo 13%
- DE e-Rechnung: obveza od 01.01.2025 — provjeri samo DE dokumente >= 2025-01-01
- HRK valuta na starim dokumentima = normalno, ne greška
- COVID PDV 16% DE u 2020 = normalno, ne greška

### Pravi podaci za analizu
- **236** produkcijskih Invoice-a (2026, manual)
- **251** POS računa (2026)
- **0** otpremnica (tijek još nije wire-an — Sprint 1 to rješava)


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
