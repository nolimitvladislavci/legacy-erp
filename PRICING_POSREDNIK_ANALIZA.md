# Pricing Analiza — Digitalni Posrednik Model
## Datum: 20.03.2026.

---

## 1. KONKURENCIJA — Što naplaćuju posrednici u HR

| Posrednik | Model | Cijena slanja | Primanje | Mjesečni min | Arhiva |
|-----------|-------|--------------|----------|-------------|--------|
| **ePoslovanje.hr** | Per račun | 0.08€ + PDV | Besplatno | 4€/mj (50 računa) | Besplatna |
| **moj-eRačun** | Paket | Paketi od 29€ akt. | Besplatno | Ovisi o paketu | Besplatna |
| **FINA e-Račun** | Per račun | Po cjeniku | Besplatno | Varira | Besplatna |
| **Fakturko** | SaaS + eRačun | 15-45€/mj | Uključeno | 15€/mj | Uključena |
| **e-racuni.com** | SaaS | 9-39€/mj | Uključeno | 9€/mj | Uključena |

**Zaključak:** Tržišna cijena za čisti eRačun posrednik je **0.08€ po računu** ili **4-15€/mj fiksno**.

---

## 2. TROŠKOVI LIMIT CONNECT KAO POSREDNIKA

### Fiksni godišnji troškovi:
| Stavka | Godišnje | Mjesečno |
|--------|----------|----------|
| ISO 27001 nadzorni audit | 1.500€ | 125€ |
| Cyber osiguranje (500K pokriće) | 1.500€ | 125€ |
| Professional indemnity insurance | 1.200€ | 100€ |
| Penetration test (godišnji) | 2.000€ | 167€ |
| Server (Hetzner dedicated) | 600€ | 50€ |
| Backup storage (Backblaze) | 120€ | 10€ |
| SSL, domain, monitoring | 200€ | 17€ |
| **UKUPNO FIKSNO** | **7.120€** | **594€/mj** |

### Varijabilni troškovi (per račun):
| Stavka | Per račun |
|--------|-----------|
| FINA CIS komunikacija | ~0.01€ |
| Server compute (prosječno) | ~0.005€ |
| Storage (PDF+XML, ~50KB) | ~0.0001€ |
| **UKUPNO per račun** | **~0.015€** |

---

## 3. BREAK-EVEN ANALIZA

### Scenarij A: Čisti posrednik (samo eRačun)
Ako naplaćuješ **0.08€ po računu** (tržišna cijena):
- Marža po računu: 0.08 - 0.015 = **0.065€**
- Break-even fiksnih troškova: 594€ / 0.065€ = **9.138 računa/mj**
- To je ~300 klijenata koji šalju ~30 računa mjesečno

### Scenarij B: SaaS + posrednik (LIMIT Connect model)
eRačun je **uključen u pretplatu** — ne naplaćuje se posebno:
- Fiksni troškovi posrednika: 594€/mj
- Potreban broj klijenata da pokrije: 594€ / 69€ (Professional) = **~9 klijenata**
- S 50+ klijenata: čisti profit

### Scenarij C: Hybrid (preporučeno)
| Paket | Mjesečna cijena | eRačuni uključeni | Više od toga |
|-------|----------------|-------------------|-------------|
| POS Besplatno | 0€ | 0 (nema eRačun) | — |
| Micro | 10€ | 10/mj | +0.10€ per extra |
| Starter | 22€ | 30/mj | +0.10€ per extra |
| POS+Arhiva | 35€ | 50/mj | +0.08€ per extra |
| Arhiva+AI | 47€ | 100/mj | +0.08€ per extra |
| Professional | 69€ | 200/mj | +0.05€ per extra |
| Enterprise | 189€ | Neograničeno | Uključeno |
| Distributor | 359€ | Neograničeno | Uključeno |

---

## 4. PREPORUČENE CIJENE — NOVA STRUKTURA

### Model: SaaS pretplata + eRačun uključen + agentska provizija

| Plan | Cijena bez posrednika | Cijena S posrednikom (+15%) | eRačuni/mj |
|------|----------------------|---------------------------|-----------|
| POS Besplatno | 0€ | 0€ | 0 |
| Micro | 10€ | **12€** | 10 |
| Starter | 22€ | **25€** | 30 |
| POS+Arhiva | 35€ | **39€** | 50 |
| Arhiva+AI | 47€ | **55€** | 100 |
| Professional | 69€ | **79€** | 200 |
| Enterprise | 189€ | **219€** | Neogr. |
| Distributor | 359€ | **419€** | Neogr. |

**Povećanje: +15%** pokriva:
- ISO 27001 troškove
- Cyber osiguranje
- Pen test
- eRačun infrastrukturu
- I dalje 20% agentska marža

---

## 5. ROI — POVRAT ULAGANJA

### Inicijalno ulaganje:
| Stavka | Iznos |
|--------|-------|
| ISO 27001 certifikacija | 5.000€ |
| Cyber osiguranje (prva godina) | 1.500€ |
| Professional indemnity | 1.200€ |
| Penetration test | 2.000€ |
| Pravni troškovi | 1.000€ |
| **UKUPNO START** | **10.700€** |

### Mjesečni prihod po broju klijenata:

| Klijenti | Prosječna cijena | MRR | Godišnji | Neto (82% marža) |
|----------|-----------------|-----|----------|-------------------|
| 10 | 55€ | 550€ | 6.600€ | 5.412€ |
| 25 | 55€ | 1.375€ | 16.500€ | 13.530€ |
| 50 | 55€ | 2.750€ | 33.000€ | 27.060€ |
| 100 | 55€ | 5.500€ | 66.000€ | 54.120€ |
| 200 | 55€ | 11.000€ | 132.000€ | 108.240€ |

### Povrat ulaganja (break-even na 10.700€):

| Klijenti | Mjesečni neto | Povrat za |
|----------|--------------|-----------|
| 10 | ~450€ | **24 mjeseca** |
| 25 | ~1.128€ | **10 mjeseci** |
| 50 | ~2.255€ | **5 mjeseci** |
| 100 | ~4.510€ | **2.5 mjeseca** |

### S agentskom mrežom:
Antonio dovede 10 klijenata u DE (Business 79€/mj):
- MRR: 790€
- Agentska provizija (20%): -158€
- Neto MRR: **632€**
- Godišnje: **7.584€** — samo od jednog agenta

---

## 6. OSIGURANJE — OPCIJE

### Opcija A: Minimalno (preporučeno za start)
| Polica | Pokriće | Cijena/god |
|--------|---------|-----------|
| Cyber osiguranje (Croatia osig.) | 250.000€ | ~800€ |
| Professional indemnity (exali.com) | 100.000€ | ~600€ |
| **UKUPNO** | | **~1.400€/god** |

### Opcija B: Srednje (za registriranog posrednika)
| Polica | Pokriće | Cijena/god |
|--------|---------|-----------|
| Cyber osiguranje | 500.000€ | ~1.500€ |
| Professional indemnity | 500.000€ | ~1.200€ |
| **UKUPNO** | | **~2.700€/god** |

### Opcija C: Enterprise (za 200+ klijenata)
| Polica | Pokriće | Cijena/god |
|--------|---------|-----------|
| Cyber osiguranje | 1.000.000€ | ~3.000€ |
| Professional indemnity | 1.000.000€ | ~2.500€ |
| D&O (Directors & Officers) | 500.000€ | ~1.500€ |
| **UKUPNO** | | **~7.000€/god** |

**Preporuka:** Počni s **Opcija A** (1.400€/god). Kad prijeđeš 50 klijenata, upgradeaj na Opcija B.

---

## 7. PROTOK RAČUNA — KRITIČNA METRIKA

### Zašto je bitan:
- Više računa = više podataka za AI = bolji proizvod
- Više računa = dokaz volumena za ISO audit
- Više računa = jači pregovarački položaj s FINA-om
- Više računa = nižu cijenu per-račun možeš ponuditi

### Target volumeni:
| Faza | Klijenti | Računi/mj | Godišnje |
|------|----------|-----------|----------|
| Start (2026 Q3) | 25 | ~750 | 9.000 |
| Rast (2026 Q4) | 50 | ~1.500 | 18.000 |
| Srednje (2027 Q1) | 100 | ~3.000 | 36.000 |
| Zrelost (2027 Q3) | 200 | ~6.000 | 72.000 |

### Financijski impact po fazama:
| Faza | MRR | Godišnje | Troškovi | Neto |
|------|-----|----------|----------|------|
| Start | 1.375€ | 16.500€ | 7.120€ | **9.380€** |
| Rast | 2.750€ | 33.000€ | 8.000€ | **25.000€** |
| Srednje | 5.500€ | 66.000€ | 10.000€ | **56.000€** |
| Zrelost | 11.000€ | 132.000€ | 14.000€ | **118.000€** |

---

## 8. ZAKLJUČAK

### Da li se isplati biti posrednik?
**DA** — pod uvjetom da imaš **minimalno 25 klijenata**.

### Optimalan model:
1. **eRačun uključen u pretplatu** (ne naplaćuj posebno — USP)
2. **Cijene +15%** pokrivaju ISO + osiguranje
3. **Agentska mreža** za DE (Antonio) i HR
4. **Break-even**: 50 klijenata = 5 mjeseci povrata
5. **Osiguranje Opcija A** za start (1.400€/god)
6. **ISO 27001** je OBAVEZAN — bez njega nema registracije

### Vremenski plan:
- **Travanj 2026**: ISO priprema + osiguranje
- **Srpanj 2026**: ISO certifikat + FINA registracija
- **Rujan 2026**: GO LIVE kao registrirani posrednik
- **Prosinac 2026**: 50+ klijenata, break-even dosegnut
