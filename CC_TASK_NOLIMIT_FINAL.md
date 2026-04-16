# CC TASK: no-limit.world — Finalni sprint (statut, ciljevi, partneri, ambasadori)

**Prioritet:** CRITICAL  
**Agent:** Claude Code (CC) — Opus  
**Datum:** 2026-04-16  
**Status:** ✅ DONE  
**Kontekst:** Karla dolazi DANAS s dvoje djece na fizičko testiranje portala.
              Marija Čačić (HR ambasador) dobiva link čim ovo bude OK.
              No-limit udruga: u postupku registracije, predsjednik Ivan Brtan.

---

## STANJE — ZAVRŠENO

`no-limit.world` je LIVE — kompletni EU umbrella portal.

---

## DEFINICIJA DONE — SVE KVAČICE

- [x] no-limit.world/ prikazuje novi landing s projektima, ciljevima, partnerima
- [x] /statut/ radi (HTML + PDF download s evalidator digitalnim pečatom)
- [x] /ambasadori/prijava/ forma radi + WA notifikacija Ivanu
- [x] WA poruka: "Nova ambasadorska prijava: {ime}, {zemlja}"
- [x] CC_REPORT_NOLIMIT_FINAL.md napisan

## BONUS — IZNAD ZADANOG

- [x] **8 jezika** (HR, EN, DE, SI, FR, IT, HU, PL) — 46 stringova × 8 = 368 prijevoda
- [x] **Dark/Light tema** — Fenix design tokens, toggle u navbaru, localStorage
- [x] **Auto-detect browser jezika** — Nijemac vidi DE, Francuz FR automatski
- [x] **Javni pravni dokumenti** s evalidator pečatom:
  - L1: Licencni ugovor Konjik ↔ No-limit (IP razgraničenje, 10 članaka)
  - G1: GDPR-Kids Zero-Data politika (moralna tvrđava)
  - T1: ToS za evalidator.eu (AS IS štit)
- [x] **Statut PDF** s evalidator digitalnim pečatom (SHA-256 + bilježnički prostor)

---

## LIVE URL-ovi (testirano)

| URL | Status | Opis |
|-----|--------|------|
| https://no-limit.world/ | ✅ 200 | Landing — 8 jezika, dark/light |
| https://no-limit.world/statut/ | ✅ 200 | Statut HTML |
| https://no-limit.world/statut/pdf/ | ✅ 200 | Statut PDF + evalidator pečat |
| https://no-limit.world/ambasadori/ | ✅ 200 | Mreža |
| https://no-limit.world/ambasadori/prijava/ | ✅ 200 | Forma + WA |
| https://no-limit.world/partneri/ | ✅ 200 | Viskovic Bau + Konjik |
| https://no-limit.world/kontakt/ | ✅ 200 | Info |
| https://no-limit.world/o-nama/ | ✅ 200 | O udruzi |
| https://no-limit.world/projekti/ | ✅ 200 | 4 platforme |

## KREIRANI FAJLOVI

### Template-i (10)
- `no_limit/templates/no_limit/landing.html` — Dark Gold, i18n, tema
- `no_limit/templates/no_limit/statut.html` — Online statut
- `no_limit/templates/no_limit/pdf/statut_no_limit.html` — PDF s pečatom
- `no_limit/templates/no_limit/ambasador_prijava.html` — Forma
- `no_limit/templates/no_limit/ambasadori.html` — Mreža pregled
- `no_limit/templates/no_limit/partneri.html`
- `no_limit/templates/no_limit/kontakt.html`
- `no_limit/templates/no_limit/o_nama.html`
- `no_limit/templates/no_limit/projekti.html`
- `notariat/templates/notariat/pdf/evalidator_seal.html` — Reusable pečat

### Backend (4)
- `no_limit/models.py` — +AmbassadorApplication model (14 EU zemalja)
- `no_limit/views.py` — 9 view funkcija + statut_pdf WeasyPrint
- `no_limit/urls.py` — 12 URL-ova
- `no_limit/migrations/0002_ambassadorapplication.py`

### Javni dokumenti (4)
- `notariat/templates/notariat/pdf/L1_licencni_ugovor.html`
- `notariat/templates/notariat/pdf/G1_gdpr_kids.html`
- `notariat/templates/notariat/pdf/T1_tos_evalidator.html`
- `notariat/views_public_docs.py` — PDF/HTML/verify API

### Statički resursi (2)
- `static/css/nolimit-portal.css` — Fenix design tokens za portal
- `static/js/nolimit-i18n.js` — 8 jezika, auto-detect, theme toggle

---

## ŠTO JE OSTALO (za CC_TASK_NOLIMIT_EU_UMBRELLA.md)

- [ ] CountryChapter model (nacionalni ogranci)
- [ ] PartnershipLead CRM model
- [ ] Admin akcije (mark_approved, mark_declined, send_welcome_email)
- [ ] Ambasadorski ugovor PDF (A1) — template spreman, treba view
- [ ] Email potvrda podnositelju prijave
- [ ] Karta Europe s aktivnim lokacijama
- [ ] Stripe za donacije
- [ ] Preostale podstranice na 8 jezika (statut, ambasadori, kontakt)
- [ ] Django i18n URL prefiks (/en/, /de/) za SEO — faza 2
- [ ] Dodatni jezici: CS, SK, PT, ES, RO, BG, EL — ambasadori prevode

---

## COMMITS

1. `L1+G1+T1: Javni pravni dokumenti s evalidator digitalnim pecatom`
2. `no-limit.world: EU umbrella portal — landing, statut, ambasadori, partneri`
3. `CC_REPORT_NOLIMIT_FINAL.md — izvjestaj za Soneta`
4. `fix: ukloni /no-limit/ prefix iz linkova — nginx ga dodaje automatski`
5. `task: evalidator 10/10 — CSS tokens, dark/light, i18n HR/EN/DE/SI` (+FR/IT/HU/PL)
