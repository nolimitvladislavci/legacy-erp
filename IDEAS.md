# IDEAS — Append-Only Backlog

> Pravilo: nikad ne brišemo, samo dodajemo.
> Format: `[ID] [STATUS] Opis`
> Status: 💡 nova | 🔄 razmatrana | ✅ implementirana | ❌ odbačena

---

## Ideje

- [I-001] ✅ 3-slojni memory sistem (ADR + IDEAS + KONTEKST) — implementirano CC_TASK_MEMORY_SYSTEM
- [I-002] ✅ Git hook upozorenje za FENIX_STATUS.md — pre-commit hook LIVE
- [I-003] ✅ CLI log-session alat za brzo bilježenje konteksta — /usr/local/bin/log-session LIVE
- [I-004] 🔄 Weekly AI digest (cron + Claude API) — odgođeno, planirati za sprint +2

## [I-005] ✅ Module Launcher — /hr/moduli/ LIVE (2026-04-24)
**Status:** IMPLEMENTIRANO

Bootstrap dark card grid, live search debounce 300ms.
Čita iz `companies.module_registry.MODULES` (95+ modula).
FA_TO_EMOJI konverzija (50+ FA ikona → emoji).
Route u `core/urls.py` direktno (ne u companies/urls.py — inače bi bio /hr/companies/moduli/).
Sidebar: launcher gumb na vrhu `_sidebar_modules.html`.

## [I-006] 💡 form_toolbar v2 port iz fenix-v3 (2026-04-24)
**Status:** TODO — VISOK prioritet

Fenix V3 form_toolbar v2 LIVE. fina-connect nema form toolbar nikakav.
Kopirati `templates/components/form_toolbar.html` iz fenix-v3, prilagoditi.
Uključiti u: documents/arhiva/upload.html, smart_import, svaku formu s text inputom.
UniPortal endpointi već postoje u fina-connect (Sprint 5).

## [I-LEX-001] VETRA Witness Report Protocol (WRP-1.0) (2026-04-27)
**Status:** KONCEPCIJA — visok prioritet

Analogija s knjigovodstvenim servisom. Validator = Tehnicko-forenzicki ispitivac dokumenata.
NIJE odvjetnik/biljeZnik/nadripisar — IT usluga: hash verifikacija → .dok izvjesce.
Odvjetnik/biljeZnik onda donosi pravnu ocjenu na temelju tehnickog izvjesca.

Pravni presedani: sudski vjestak, SSL CA, FINA e-potpis, forensicki lab.
Sprint: LEX NO LIMIT Sprint 2. Prihodi: 30/60/10%.
NIGDJE u HR/EU ne postoji kao standardizirani protokol = trzisna prednost.

## [I-LEX-002] Invalidi IT obrти za pracenje procesa portala (2026-04-27)
**Status:** RJESENJE ZA RADNO-PRAVNI PROBLEM

Svaki validator otvara vlastiti IT obrт → B2B ugovor s No Limit udrugom.
Nije radni odnos. Bonus: HZMO subvencije za invalide-obrtnike.
Definirani odnosi: invalid=poduzetnik, udruga=narucitelj, VETRA=alat, odvjetnik=krajnji kupac.

## [I-LEX-003] VETRA Binary Truth Protocol (BTP-1.0) (2026-04-27)
**Status:** TEMELJ ARHITEKTURE — implementirati odmah

### Koncept: Sve je 1 ili 0. Zeleno ili Crveno.

**Dva sloja provjere:**
| Sloj | Tko | Metoda | Rezultat |
|---|---|---|---|
| L1: Vizualna | Covjek (validator) | Ocima gleda dokument | 1 / 0 |
| L2: Softverska | VETRA sustav | Hash, chain, OTS, potpis | 1 / 0 |
| L3: Kombinacija | AND gate | Oba moraju biti 1 | ZELENO / CRVENO |

**UI flow:**
Validator dolazi → vidi dokument → vidi softverski rezultat (zeleno/crveno)
→ pritisne dugme 'POTVRDI' ili 'ODBIJ' → .dok se pecati → posao procesiran

**Pravni znacaj dugmeta:**
- Nije pravni savjet
- Nije kreiranje isprave
- Jest: 'Vizualno sam potvrdio da ovaj dokument izgleda autenticno'
- Ekvivalent: blagajnik koji prima gotovinu (ne procjenjuje je li transakcija zakonita)

### Invalidi = Volonteri / Studenti

**Volonteri (Zakon o volontiranju NN 58/07, 22/13):**
- No Limit udruga = organizator volontiranja
- Validator = volonter (ne zaposlenik, ne obrtnik)
- Ugovor o volontiranju (ne radni, ne djelo)
- Jamci: pokriveni osiguranjem udruge

**Studenti (Studentski ugovor o djelu):**
- Studentski servis (SSC) posreduje
- Porez = 0 do praga
- Nije radni odnos

**Zasto je ovo CISТО od svih napadnih vektora:**
- Nema radnog odnosa (rjesava vektor #10)
- Nema nadripisarstva (pritisak dugmeta = IT klik, ne pravni akt)
- GDPR Art. 9: volonter daje eksplicitni pristanak pri ukljucivanju
- Volonteri smiju biti invalidi → Zakon o socijalnoj skrbi stiti ih, ne kaznjava
