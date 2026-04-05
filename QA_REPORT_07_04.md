# QA REPORT — 07.04.2026.
# Izvršio: Claude Code (CC)
# Datum: 06.04.2026. (noćna sesija, prije Marija dry-run 08.04.)
# Git HEAD: 3fc28e0f
# Django check: 0 errors

---

## REZULTATI PO BLOKU

### BLOK A — memio.pet REGISTRACIJA
| Test | Rezultat | Napomena |
|------|----------|---------|
| A1 GET /registracija/ | **PASS** | 200, forma se prikazuje |
| A2 POST kreira profil | **PASS** | 302 redirect na /uzgajivac/ |
| A3 Dupli email | **PASS** | 302, ne 500 |
| A4 Bez emaila | **PASS** | Ne crashira |
| A2.1 Nema LIMIT register linka | **PASS** | 0 linkova na limit-connect.com/hr/register |
| A2.2 Ima /registracija/ link | **PASS** | 3 linka na landing stranici |

**BLOK A: 6/6 PASS**

---

### BLOK B — BOXGRAM / Profil Edge Cases
| Test | Rezultat | Napomena |
|------|----------|---------|
| B1 ear_tag lookup | **PASS** | /pas/QA-TEST-2026/ → 200 |
| B2 Nepostojeći chip | **PASS** | /pas/NIKAD.../ → 404, ne 500 |

Napomena: Signal bridge test (B1 auto PetProfile) preskočen — zahtijeva
puni Django test runner s cross-db transakcijama. Ručna provjera u shellu
potvrđuje da signal radi za nove AnimalProfile objekte.

**BLOK B: 2/2 PASS** (signal test: manual verify OK)

---

### BLOK C — TRIKEY (sigurnosna logika)
| Test | Rezultat | Napomena |
|------|----------|---------|
| C1 PIN 3 znamenke | **PASS** | ValueError |
| C1 PIN slova | **PASS** | ValueError |
| C2 Ispravan PIN | **PASS** | verify_pin=True |
| C2 Pogrešan PIN | **PASS** | verify_pin=False |
| C3 Lockout 5 pokušaja | **PASS** | PermissionError nakon 5× krivo |
| C4 350+ profila | **PASS** | 350 TriKeyProfile u bazi |

**BLOK C: 6/6 PASS**

---

### BLOK D — POS FISKALIZACIJA
| Test | Rezultat | Napomena |
|------|----------|---------|
| D1 JIR bez ZKI | **WARN** | 4 bona — ali svi su DEMO-OFFLINE/TEST-CLEANED (testni podaci, ne pravi fiskalni) |
| D2 POS token auth (krivi token) | **PASS** | 302, ne 200 |

**BLOK D: 1/2 PASS, 1/2 WARN**

Preporuka D1: Dodati `is_demo=True` flag ili obrisati DEMO bonove
prije produkcije. Ne utječe na prave fiskalne operacije.

---

### BLOK E — memio.world (model + API)
| Test | Rezultat | Napomena |
|------|----------|---------|
| E1 Waitlist POST | **PASS** | 201 Created |
| E2 Dupli email | **PASS** | 200, ne 500 |

**BLOK E: 2/2 PASS**

---

### BLOK F — NO LIMIT AZIL
| Test | Rezultat | Napomena |
|------|----------|---------|
| F1 Azil landing | **PASS** | 200, sadrži "azil" i "besplatno" |
| F2 pos-azil.css | **PASS** | 200 |

**BLOK F: 2/2 PASS**

---

### BLOK G — PERFORMANCE
| URL | Vrijeme | Rezultat |
|-----|---------|---------|
| memio.pet/ | 0.042s | **PASS** |
| memio.pet/registracija/ | 0.038s | **PASS** |
| limit-connect.com/hr/ | 0.029s | **PASS** |
| limit-connect.com/no-limit/ | 0.430s | **PASS** |
| memio.world/ | 0.084s | **PASS** |

Sve stranice < 0.5s (limit: 2s). Server na AMD EPYC Genoa odlično
performira.

**BLOK G: 5/5 PASS**

---

### BLOK H — SIGURNOST
| Test | Rezultat | Napomena |
|------|----------|---------|
| H1 /admin/ hidden | **PASS*** | 302→404 (i18n redirect pa 404, admin je na randomiziranom URL-u j3wk...) |
| H2 Debug=False | **PASS** | Nema stack trace leak-a |
| H3 Server header | **PASS** | Ne otkriva Python/Django/Gunicorn |

*H1: Idealno bi /admin/ odmah davao 404, ali chain 302→404 je
prihvatljiv jer attacker nikad ne vidi admin panel.

**BLOK H: 3/3 PASS**

---

## UKUPNO

| Blok | Testova | PASS | WARN | FAIL |
|------|---------|------|------|------|
| A - Registracija | 6 | 6 | 0 | 0 |
| B - Boxgram/Profil | 2 | 2 | 0 | 0 |
| C - TriKey | 6 | 6 | 0 | 0 |
| D - Fiskalizacija | 2 | 1 | 1 | 0 |
| E - memio.world | 2 | 2 | 0 | 0 |
| F - Azil | 2 | 2 | 0 | 0 |
| G - Performance | 5 | 5 | 0 | 0 |
| H - Sigurnost | 3 | 3 | 0 | 0 |
| **UKUPNO** | **28** | **27** | **1** | **0** |

## OCJENA: 9/10

Jedini WARN: 4 DEMO bona s JIR bez ZKI — testni podaci, ne utječe
na produkciju. Preporuka: očistiti prije GO-LIVE 15.04.

## KRITIČNI BUGOVI: 0
## PREPORUKE PRIJE MARIJA DRY-RUN:
1. Obriši DEMO-OFFLINE bonove iz POS baze
2. Razmotri nginx-level 404 za /admin/ (nice-to-have)
3. Dodaj @cache_page(300) na memio.pet/pas/ za skalabilnost

---
Izvještaj generiran automatski. CC sesija 06.04.2026.
