# CC TASK: no-limit.world — Transformacija u EU Umbrella portal

**Prioritet:** HIGH  
**Agent:** Claude Code (CC) — Opus  
**Datum:** 2026-04-16  
**Status:** ✅ DONE  
**Odobrio:** Sonnet  
**Vlasnik:** Ivan Brtan / No-limit udruga

---

## DEFINICIJA DONE — SVE KVAČICE

- [x] 3 nova modela + migracije (AmbassadorApplication upgrade, CountryChapter, PartnershipLead)
- [x] 10+ URL-ova (13 URL-ova aktivno)
- [x] PDF download radi (statut + ambasadorski ugovor A1 + L1/G1/T1)
- [x] Forma za ambasadore radi + WA notifikacija + thank you stranica
- [x] Admin s mark_approved/declined/active akcijama + fieldsets
- [x] 4+ testovi prolaze (10 testova: 3 modela + 7 views)
- [x] CC_REPORT_NOLIMIT.md napisan (ispod)

## BONUS
- [x] 8 jezika (HR, EN, DE, SI, FR, IT, HU, PL) — JS instant switch
- [x] Dark/Light tema — Fenix design tokens, toggle
- [x] L1 Licencni ugovor + G1 GDPR-Kids + T1 ToS evalidator — javni dokumenti s pečatom
- [x] evalidator digitalni pečat (reusable komponenta)
- [x] Statut s evalidator pečatom (SHA-256)

---

## MODELI (3 nova + 1 upgrade)

| Model | Polja | Migracija |
|-------|-------|-----------|
| **AmbassadorApplication** (upgrade) | +desired_role, experience, organization_type, reviewed_by, review_notes, approved_at | 0003 |
| **CountryChapter** | country, country_name, coordinator, is_active, launch_date, ambassador_count, user_count | 0003 |
| **PartnershipLead** | name, organization, country, email, partnership_type, status, potential_value, source | 0003 |

## ADMIN AKCIJE

| Model | Akcije |
|-------|--------|
| AmbassadorApplication | ✓ Odobri, ✗ Odbij, ★ Aktiviraj |
| PartnershipLead | Kontaktirano, ✗ Odbij |
| CountryChapter | Standard CRUD |
| AzilPrijava | Kontaktirano (staro, sačuvano) |

## PDF DOKUMENTI

| Dokument | URL | Pečat |
|----------|-----|-------|
| Statut | /statut/pdf/ | evalidator SHA-256 |
| A1 Ambasadorski ugovor | /dokumenti/ambasadorski-ugovor.pdf | evalidator SHA-256 |
| L1 Licencni ugovor | /notariat/docs/L1/pdf/ | evalidator SHA-256 |
| G1 GDPR-Kids | /notariat/docs/G1/pdf/ | evalidator SHA-256 |
| T1 ToS evalidator | /notariat/docs/T1/pdf/ | evalidator SHA-256 |

## ŠTO OSTAJE (faza 2+)

- [ ] Email potvrda podnositelju prijave (SMTP config)
- [ ] Karta Europe s aktivnim lokacijama (Leaflet.js)
- [ ] Stripe za donacije
- [ ] Django i18n URL prefiks (/en/, /de/) za SEO
- [ ] Dodatni jezici: CS, SK, PT, ES, RO, BG, EL
- [ ] send_welcome_email admin akcija (SMTP)
