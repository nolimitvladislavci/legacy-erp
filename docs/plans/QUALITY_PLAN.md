# GROSSMARKT ONLINE — CODE QUALITY PLAN
## Od 6.7 → 8+ u 5 koraka

**Datum**: 4.3.2026.  
**Server**: viskovic-group.de  
**Cilj**: Podići ocjenu koda na 8+ prije turneje (10 dana)

---

## ANALIZA: Zašto je 6.7?

### Što RADI (pozitivno):
- 4 appa deployed, 18 modela, migracije OK
- Company extended polja, fiscal tab, partner flag
- Marketplace views + templates napisani
- Documents modul spreman

### Što NEDOSTAJE (vuče ocjenu dolje):

| Problem | Utjecaj | Prioritet |
|---------|---------|-----------|
| Nema testova (0 tests) | -1.0 | KRITIČNO |
| Nema error handling / logging | -0.5 | VISOKO |
| Nema input validacija (forms) | -0.3 | VISOKO |
| Sidebar ne linkuje na marketplace/documents | -0.3 | VISOKO |
| Nema seed data za demo | -0.2 | SREDNJE |
| Nema middleware za company context | -0.2 | SREDNJE |
| CI/CD testovi failaju | -0.2 | SREDNJE |
| Nema API (DRF) endpointi | -0.2 | NISKO za sad |
| Nema caching | -0.1 | NISKO |
| Security headers nedostaju | -0.1 | NISKO |

---

## PLAN IZVRŠENJA (5 skripti, redom)

### KORAK 1: deploy_marketplace_views.py ✅ SPREMAN
C Code pokreće. Dodaje views, urls, 7 templatea za marketplace.

### KORAK 2: deploy_documents.py ✅ SPREMAN  
C Code pokreće. Dodaje 4 tipa dokumenata, PDF, thermal print.

### KORAK 3: deploy_quality_boost.py 🆕 NOVO
Najveći skok ocjene. Dodaje:
- **Tests** (pytest) za sve modele i views → +1.0
- **Logging** konfiguracija → +0.2
- **Error pages** (404, 500) → +0.1
- **Security middleware** (CSRF, headers) → +0.1
- **Input sanitizacija** na formama → +0.2
- **Company middleware** (auto-inject company u request) → +0.2

### KORAK 4: deploy_sidebar_and_nav.py 🆕 NOVO
- Sidebar linkovi za marketplace + documents
- Breadcrumbs
- Active state highlighting
- Mobile responsive nav fix
- → +0.3

### KORAK 5: deploy_seed_data.py 🆕 NOVO
- Demo kategorije (Voće, Povrće, Mliječni, Meso, Žitarice)
- 3 demo OPG-a s proizvodima
- Demo narudžbe
- Demo dokumente (otpremnica, primka)
- → +0.2 (demo-ready za turneju)

---

## OČEKIVANA OCJENA NAKON SVIH 5:

| Komponenta | Prije | Poslije |
|-----------|-------|---------|
| Modeli + migracije | 8.0 | 8.5 |
| Views + templates | 5.0 | 8.0 |
| Testovi | 0.0 | 7.5 |
| Error handling | 3.0 | 7.5 |
| Security | 5.0 | 8.0 |
| Navigation/UX | 4.0 | 8.0 |
| Demo readiness | 2.0 | 8.5 |
| **UKUPNO** | **6.7** | **~8.2** |

---

## REDOSLIJED ZA C CODE:

```
1. python3 deploy_marketplace_views.py    # ✅ SPREMAN
2. python3 deploy_documents.py            # ✅ SPREMAN
3. python3 deploy_quality_boost.py        # 🔨 gradim sad
4. python3 deploy_sidebar_and_nav.py      # 🔨 gradim sad
5. python3 deploy_seed_data.py            # 🔨 gradim sad
```

Svaki skript je self-contained. Pokreće se redom. Svaki isprintaj DONE na kraju.
