# ⚡ CC WAKE — HITNO — 06.04.2026. 00:20
# Blokirani smo. Ivan čeka. Kreni na F1 odmah.

## PRIORITET 1 — ODMAH: TriKey PIN setup za postojeće korisnike
Problem: 0 TriKeyProfile zapisa. Nitko ne može koristiti novi login.
Fiksni stari login radi, ali TriKey je mrtav.

Napravi management komandu koja kreira TriKeyProfile za sve postojeće usere:
```bash
# Provjeri model prvo
grep -n "^class TriKeyProfile\|user = \|pin_hash\|OneToOne" /var/www/fina-connect/accounts/trikey.py | head -10

# Onda napiši:
# accounts/management/commands/init_trikey_profiles.py
# Za svaki User koji nema TriKeyProfile → stvori prazan profil
# Ispiši: "Kreirano X profila"
```

## PRIORITET 2 — TriKey login template
Template `/accounts/trikey/login/` ne postoji (→ redirect ali nema stranice).
Napravi: `templates/accounts/trikey_login.html`
- Email input
- PIN input (6 znamenki, numeric keyboard)
- Link: "Prijava starim načinom" → /hr/login/
- Link: "Postavi PIN" → /accounts/trikey/pin/setup/
- Isti dizajn kao registration/login.html (tamna tema, gold akcent)

## PRIORITET 3 — Nastavi F1 (UI audit)
Nakon TriKey → nastavi CC_TASK_F1_UI_AUDIT.md

## PRAVILO
Čitaj model PRIJE pisanja koda. Uvijek.
