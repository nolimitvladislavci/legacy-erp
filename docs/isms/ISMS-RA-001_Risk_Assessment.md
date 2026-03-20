# Risk Assessment — Procjena rizika
## LIMIT Connect ERP Platform

**Dokument:** ISMS-RA-001
**Verzija:** 1.0
**Datum:** 20.03.2026.
**Metodologija:** ISO 27005 (kvalitativna procjena)

---

## 1. Skala procjene

**Vjerojatnost:** 1=Rijetko, 2=Moguće, 3=Vjerojatno, 4=Gotovo sigurno
**Utjecaj:** 1=Zanemariv, 2=Nizak, 3=Srednji, 4=Visok, 5=Kritičan
**Rizik = Vjerojatnost × Utjecaj** (1-20)
**Prihvatljiv:** ≤6 | **Toleriran:** 7-12 | **Neprihvatljiv:** ≥13

---

## 2. Registar rizika

### A. Infrastrukturni rizici

| ID | Rizik | V | U | R | Kontrola | Status |
|---|---|:---:|:---:|:---:|---|---|
| R-01 | Server pad (hardware failure) | 2 | 4 | **8** | Hetzner Cloud SLA, daily backup, DR skripta | TOLERIRAN |
| R-02 | DDoS napad | 2 | 3 | **6** | Hetzner DDoS zaštita, Nginx rate limit | PRIHVATLJIV |
| R-03 | Gubitak podataka (DB corruption) | 1 | 5 | **5** | Dnevni backup, 14-dana retencija, Git | PRIHVATLJIV |
| R-04 | Istek SSL certifikata | 1 | 4 | **4** | Let's Encrypt auto-renew (certbot) | PRIHVATLJIV |
| R-05 | Disk pun | 2 | 3 | **6** | Health monitor (>90% alert), auto-cleanup (>95%) | PRIHVATLJIV |

### B. Aplikacijski rizici

| ID | Rizik | V | U | R | Kontrola | Status |
|---|---|:---:|:---:|:---:|---|---|
| R-06 | SQL injection | 1 | 5 | **5** | Django ORM (parametrizirani upiti), CSP | PRIHVATLJIV |
| R-07 | XSS napad | 1 | 4 | **4** | Django auto-escaping, CSP, X-XSS-Protection | PRIHVATLJIV |
| R-08 | CSRF napad | 1 | 4 | **4** | Django CSRF middleware, SameSite cookies | PRIHVATLJIV |
| R-09 | Cross-tenant data leak | 2 | 5 | **10** | CompanyManager queryset filter, get_user_company() | TOLERIRAN |
| R-10 | Neovlašteni pristup admin panelu | 2 | 5 | **10** | is_superuser check, IP filter, ForcePasswordChange | TOLERIRAN |
| R-11 | Brute force login | 2 | 3 | **6** | Django session, CSRF token (nema rate limit — POBOLJŠATI) | PRIHVATLJIV |

### C. Poslovni rizici

| ID | Rizik | V | U | R | Kontrola | Status |
|---|---|:---:|:---:|:---:|---|---|
| R-12 | FINA CIS nedostupna | 3 | 3 | **9** | Retry task (svakih 2min), 48h zakonski rok | TOLERIRAN |
| R-13 | Fiskaly TSE nedostupna | 2 | 3 | **6** | TSE Ausfall klauzel, Nacherfassung retry | PRIHVATLJIV |
| R-14 | Pogrešna fiskalizacija (dupli JIR) | 1 | 5 | **5** | Atomic transaction, unique receipt number | PRIHVATLJIV |
| R-15 | AML — pranje novca kroz donacije | 2 | 5 | **10** | AML Guard (10k prag), KYC status, email alert | TOLERIRAN |
| R-16 | Neovlašteno brisanje fiskalnih podataka | 1 | 5 | **5** | JIR guard (ne dozvoljava brisanje), hash chain | PRIHVATLJIV |
| R-17 | GDPR breach — curenje osobnih podataka | 1 | 5 | **5** | Tenant izolacija, TLS, RBAC, audit log | PRIHVATLJIV |

### D. Operativni rizici

| ID | Rizik | V | U | R | Kontrola | Status |
|---|---|:---:|:---:|:---:|---|---|
| R-18 | Gubitak ključnog osoblja | 2 | 4 | **8** | Dokumentacija (ISMS), Git, automated systems | TOLERIRAN |
| R-19 | Nekompatibilni update (breaking change) | 2 | 3 | **6** | Git versioning, test suite, backup before deploy | PRIHVATLJIV |
| R-20 | Treća strana kompromitirana (supply chain) | 1 | 4 | **4** | Certificirani dobavljači (Fiskaly BSI, Hetzner ISO) | PRIHVATLJIV |

---

## 3. Plan tretiranja rizika

### Neprihvatljivi rizici (≥13): NEMA

### Tolerirani rizici (7-12) — plan poboljšanja:

| ID | Rizik | R | Planirana kontrola | Rok |
|---|---|:---:|---|---|
| R-09 | Cross-tenant leak | 10 | Automated cross-tenant test suite (21 test, PASS) | DONE |
| R-10 | Admin pristup | 10 | 2FA za superadmine (TOTP) | Q2 2026 |
| R-12 | FINA nedostupna | 9 | Retry + monitoring dashboard | DONE |
| R-15 | AML donacije | 10 | AML Guard + KYC workflow | DONE |
| R-01 | Server pad | 8 | Multi-region backup (Backblaze B2) | Q2 2026 |
| R-18 | Gubitak osoblja | 8 | ISMS dokumentacija + runbook | IN PROGRESS |

---

## 4. Prihvaćanje preostalog rizika

Svi rizici s ocjenom ≤6 su prihvaćeni. Tolerirani rizici (7-12) imaju plan tretiranja. Neprihvatljivih rizika nema.

**Odobrio:** Ivan Brtan, Direktor
**Datum:** 20.03.2026.
