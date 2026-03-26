# CC TASK: KRITIČNO — Joker Pricing + 3Klik Registracija
# Agent: CC Code | Prioritet: 🔴 KRITIČAN — BLOKIRA OTVARANJE 1.4.!
# Datum: 2026-03-26 | Rok: DO 29.3.2026!

## OBAVEZNO PROČITAJ
```bash
cat FENIX_STATUS.md | head -20
git log --oneline -5
cat CC_TASK_JOKER_PRICING.md
cat CC_TASK_3KLIK_REGISTRACIJA.md
```

---

## ZADATAK 1: Joker Pricing (/pricing/?profile=)

### Problem
Trenutna /pricing/ — 11 kartica, previše. DVD predsjednik zatvori za 8 sek.

### Implementacija
Fajl: `registration/pricing_views.py` (dodaj ili proširi)
Template: `registration/templates/registration/pricing_joker.html`

**URL routing:**
```python
# /pricing/                    → profil selektor (6 gumba)
# /pricing/?profile=udruga     → 1 kartica (9.99 EUR/god)
# /pricing/?profile=obrtnik    → 1 kartica (0 EUR paušalac)
# /pricing/?profile=gastro     → 3 kartice (POS / POS+Arhiva / Pro)
# /pricing/?profile=gradjevina → 2 kartice (Osnovno / Pro DE)
# /pricing/?profile=najam      → 1 kartica (Rental 19 EUR/god)
# /pricing/?profile=knjigovodstvo → 1 kartica (Professional)
```

**Svaka kartica sadrži:**
- Naziv + cijena (istaknuto)
- 3-5 bullet poena za taj profil
- CTA gumb → /register/?plan=X&profile=Y

### Test
Provjeri 6 profil URL-ova vraćaju 200 i ne crashaju.

### Commit: `feat: joker pricing — profil-based landing, 6 segmenata`

---

## ZADATAK 2: 3-Klik Registracija (OIB auto-fill)

### Problem
Step3 registracije traži previše podataka — korisnik odustaje.

### Implementacija
Fajl: `registration/views.py` — proširi step3 view
Dodaj AJAX endpoint: `/register/oib-lookup/`

```python
# Haiku endpoint: korisnik unese OIB → Haiku pokuša izvući ime, adresu
# Ako Haiku ne može (nema API key za Fina/Moj-eRacun) → prazan form, user sam unosi
# NIKAD ne blokiraj registraciju! OIB lookup je convenience feature.
```

**Template `registration/step3_auto.html`:**
- OIB polje → onblur: AJAX poziv na /register/oib-lookup/
- Loading spinner dok čeka
- Auto-fill naziv, adresa, grad, PDV status
- Korisnik potvrđuje/mijenja → next step

### Test
- test_oib_lookup_valid() — vraća podatke ili prazan dict (nikad 500)
- test_registration_without_oib() — registracija prolazi i bez OIB-a

### Commit: `feat: 3-klik registracija — OIB auto-fill, Haiku assist`

---

## PRIORITET IZVRŠAVANJA
1. NAJPRE Joker Pricing (90 min) → deploy → test
2. ONDA 3-Klik Registracija (120 min) → deploy → test
3. Ažuriraj FENIX_STATUS.md

## NAPOMENA
Oba zadatka su BLOCKER za 1.4.2026 "vrata otvorena".
Bez ovih nikakvo onboarding nije moguće.
