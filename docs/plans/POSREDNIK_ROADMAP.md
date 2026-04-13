# Informacijski Posrednik — Roadmap do registracije

## Status: U PRIPREMI
## Matična firma: Konjik d.o.o. (OIB: 37590751921)
## Datum: 20.03.2026.

---

## Zakonski okvir
- **Zakon o fiskalizaciji** (NN 133/12, 115/16, 106/18, 121/19, 138/20) — čl. 61
- **Fiskalizacija 2.0** — od 01.01.2026. obvezni e-Računi za PDV obveznike
- **Od 01.01.2027.** — obvezno za SVE subjekte

## Definicija (čl. 2 Zakona)
Informacijski posrednik = pravna ili fizička osoba s OIB-om koja profesionalno
pruža usluge izdavanja i primanja e-Računa, fiskalizacije e-Računa,
te može pružati eReporting i/ili metadata usluge.

---

## Uvjeti za registraciju

### OBAVEZNO:
| # | Uvjet | Status | Akcija |
|---|-------|--------|--------|
| 1 | Registrirana firma s OIB-om | ✅ | Konjik d.o.o. — 37590751921 |
| 2 | **ISO/IEC 27001 certifikat** | ❌ | KRITIČNO — obavezan za posrednika |
| 3 | Prolazak testa sukladnosti na Testing Portalu | ❌ | Porezna uprava izdaje link |
| 4 | Zahtjev čl. 61 s dokumentacijom | ❌ | Podnosi se Poreznoj upravi |
| 5 | Certifikat sukladnosti od PU | ❌ | Dobiva se nakon testa |
| 6 | Upis u Popis informacijskih posrednika | ❌ | PU objavljuje na portalu |

### PREPORUČENO:
| # | Uvjet | Status | Akcija |
|---|-------|--------|--------|
| 7 | Cyber osiguranje (min 500K EUR) | ❌ | Kontaktirati osiguravatelja |
| 8 | Penetration test | ❌ | Naručiti od cert. firme |
| 9 | DPA ugovor s korisnicima | ✅ | Kreiran — /legal/dpa/ |
| 10 | Opći uvjeti poslovanja | ✅ | Kreiran — /legal/opci-uvjeti/ |
| 11 | Politika privatnosti | ⚠️ | Treba ažurirati |

---

## ISO 27001 — Plan

### Cijena: 3.000-8.000 EUR (implementacija) + 1.500 EUR/god (nadzorni audit)
### Trajanje: 3-6 mjeseci

### Koraci:
1. **Gap analiza** (2 tjedna) — što imamo, što fali
2. **Dokumentacija ISMS-a** (4 tjedna) — politike, procedure, risk assessment
3. **Implementacija kontrola** (4-8 tjedana) — tehničke + organizacijske mjere
4. **Interni audit** (1 tjedan) — provjera spremnosti
5. **Certifikacijski audit** (Stage 1 + Stage 2) — 2-3 dana
6. **Izdavanje certifikata** — vrijedi 3 godine, godišnji nadzorni audit

### Što LIMIT Connect VEĆ IMA (pokriva ~60% ISO 27001):
- ✅ Enkripcija u prijenosu (TLS/SSL)
- ✅ Pristupna kontrola (RBAC, 2FA, rate limiting)
- ✅ Audit log (SystemAuditLog, LoginAttempt)
- ✅ Backup (dnevni)
- ✅ Integrity hash (SHA-256 na dokumentima)
- ✅ Incident detection (AI watchdog, anomaly patrol)
- ✅ GDPR compliance (DPA, podatci u EU)

### Što FALI za ISO 27001:
- ❌ Formalni ISMS dokument (Information Security Management System)
- ❌ Risk assessment i risk treatment plan
- ❌ Business Continuity Plan (BCP)
- ❌ Formal incident response procedure
- ❌ Supplier security assessment
- ❌ Security awareness training za zaposlenike
- ❌ Physical security policy (server room)
- ❌ Change management procedure

---

## Plan realizacije

### Faza 1 (Travanj 2026) — Dokumentacija
- [ ] Napisati ISMS politiku
- [ ] Risk assessment (AI može pomoći)
- [ ] BCP plan
- [ ] Incident response procedure

### Faza 2 (Svibanj 2026) — ISO audit priprema
- [ ] Kontaktirati certifikacijska tijela (DNV, Bureau Veritas, TÜV)
- [ ] Gap analiza s konzultantom
- [ ] Penetration test

### Faza 3 (Lipanj-Srpanj 2026) — Certifikacija
- [ ] ISO 27001 Stage 1 audit
- [ ] ISO 27001 Stage 2 audit
- [ ] Certifikat

### Faza 4 (Kolovoz 2026) — FINA registracija
- [ ] Zahtjev Poreznoj upravi (čl. 61)
- [ ] Test sukladnosti na Testing Portalu
- [ ] Certifikat sukladnosti
- [ ] Upis u Popis informacijskih posrednika

### Faza 5 (Rujan 2026) — GO LIVE kao posrednik
- [ ] Marketing: "Registrirani informacijski posrednik"
- [ ] Steuerberater kanal u DE
- [ ] Agentska mreža aktivna

---

## Financijski plan

| Stavka | Jednokratno | Godišnje |
|--------|------------|----------|
| ISO 27001 implementacija | 5.000 EUR | — |
| ISO 27001 nadzorni audit | — | 1.500 EUR |
| Cyber osiguranje | — | 1.500 EUR |
| Penetration test | 2.000 EUR | 2.000 EUR |
| Pravni troškovi (DPA, OUP) | 1.000 EUR | — |
| **UKUPNO** | **8.000 EUR** | **5.000 EUR/god** |

### ROI:
- 100 klijenata × 69 EUR/mj (Professional) = 6.900 EUR MRR
- Godišnji prihod: 82.800 EUR
- Godišnji trošak (server + certifikati + osiguranje): ~15.000 EUR
- **Neto marža: ~82%**

---

## Što imamo u sustavu (tehnički ready):

| Modul | Status |
|-------|--------|
| e-Račun slanje (UBL 2.1) | ✅ |
| FINA CIS fiskalizacija | ✅ |
| TSE/KassenSichV (DE) | ✅ |
| Propter posrednik wizard | ✅ |
| API za vanjske klijente | ✅ |
| doc_integrity hash | ✅ |
| 40/40 posrednik testova | ✅ |
| Arhiva 11 godina | ✅ |
| DPA ugovor | ✅ |
| Opći uvjeti | ✅ |
| Tippgeber ugovori (DE+HR) | ✅ |
| Agent referral sustav | ✅ |
| Concurrent login detection | ✅ |
| AI Council (Razina 4) | ✅ |
