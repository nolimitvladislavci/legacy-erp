# CC_TASK_SAFT_STRATEŠKI — SAF-T plan (HR mandatornost 2026-2027)
# Agent: CC Code + Gemini (istraživanje)
# Prioritet: NIZAK-SREDNJI — HR još ne mandatira, ali DATEV i DE klijenti trebaju
# Datum: 2026-03-25

---

## Verificirano stanje: 0%
Nema ni jednog SAF-T fajla u projektu. Jedini "SAF" koji postoji = SAFETY_FACTOR u reorder.py.

---

## Što je SAF-T

Standard Audit File for Tax (OECD standard, ISO 21378).
XML format koji porezna uprava može zatražiti za audit umjesto fizičkih knjiga.

### HR status (2026):
- **Porezna uprava HR NIJE uvela obvezu** — ali je u planu za 2026-2027
- GFI (godišnji financijski izvještaj) ostaje standardan
- Priprema je strateška, ne urgentna

### DE status (za Viskovic Bau):
- DATEV format ≠ SAF-T — ali konceptualno slično
- GoBD zahtijeva revizijsku slijedivost — DONE za DE
- SAF-T za DE u planu (GoBD kompatibilan)

---

## Strateški plan (NE implementiraj odmah)

### Faza 1 — Model (1 dan, kad dođe pravo vrijeme)
```python
# nova app: saft/ ili u konto/
class SAFTExport(models.Model):
    company = FK
    period_from = DateField
    period_to = DateField
    export_type = CharField  # 'full', 'gl', 'ap', 'ar', 'inventory'
    xml_file = FileField
    status = CharField  # 'generating', 'ready', 'submitted'
    submitted_at = DateTimeField(null=True)
    created_at = auto
```

### Faza 2 — XML Generator (3-5 dana)
SAF-T HR verzija prati OECD SAF-T schema + HR PU specifikaciju.
Sekcije:
- Header (kompanija, period, valuta)
- GeneralLedger (knjiženja)
- Customers (kupci s OIB)
- Suppliers (dobavljači s OIB)
- TaxTable (PDV stope)
- SalesInvoices (izlazni računi)
- PurchaseInvoices (ulazni računi)

### Faza 3 — Automatski export (1 dan)
Celery task: generiraj SAF-T kvartalno, pohrani u MinIO.

---

## Trigger za implementaciju

Implementiraj SAF-T kad se dogodi JEDNO od:
1. HR Porezna uprava objavi obvezu (Gemini Compliance Watchdog prati)
2. Viskovic Bau zatraži za DE audit
3. Više od 50 firmi na platformi pita za SAF-T

Do tada: ovaj task ostaje ovdje kao **strateški backlog**.

---

## Gemini zadatak (odmah)

Gemini treba istražiti:
- Je li HR PU objavila rok za SAF-T mandatornost?
- Koji format — OECD SAF-T 2.0 ili HR specifičan?
- Postoji li EU direktiva koja ubrzava implementaciju?

Output u: SAFT_RESEARCH_REPORT.md
