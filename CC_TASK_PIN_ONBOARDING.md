# CC_TASK: PIN Onboarding — korisnici bez emaila
# Datum: 02.04.2026 | Prioritet: 🟡 Srednji
# Odgovorni: CC Code

## PROBLEM
7 korisnika ima @limit-connect.com placeholder email.
Password reset šalje tamo → void → korisnik ne može resetirati pristup.
GDPR čl. 25 — platforma mora korisniku osigurati kontrolu nad računom.

## RJEŠENJE — PIN-based onboarding

### A) Zabrana placeholder emaila
Pri kreiranju korisnika — ako email završava @limit-connect.com ili je prazan:
- NE kreirati korisnika s lažnim emailom
- Generirati 6-znamenkasti jednokratni PIN (secrets.randbelow)
- Prikazati PIN adminu na ekranu (JEDNOM, nije pohranjen plaintext)
- Korisnik se prijavljuje: username + PIN kao privremena lozinka
- Sustav forsira promjenu lozinke pri prvoj prijavi (must_change_password=True)

### B) Reset bez emaila — admin flow
Ako korisnik nema stvarni email, admin firme može:
- Ići na /hr/companies/users/ → klik "Resetiraj PIN"
- Sustav generira novi 6-znamenkasti PIN
- Prikazuje ga adminu (ne šalje nikamo)
- Admin ga preda radniku fizički/usmeno

### C) Postojeći @limit-connect.com korisnici — migracija
Script koji:
1. Pronađe sve email like '%@limit-connect.com'
2. Postavi must_change_password=True
3. Generira privremeni PIN
4. Obavijesti company_admin WhatsApp-om s listom korisnika i PIN-ovima

### D) Password reset flow nadogradnja
Ako user.email završava @limit-connect.com ili je prazan:
- Reset forma → prikazuje: "Obratite se administratoru tvrtke"
- Admin firme dobiva WhatsApp: "Korisnik X traži reset — generirajte PIN na /hr/companies/users/"

## IMPLEMENTACIJA
- accounts/views.py — user create form validacija
- accounts/views.py — admin PIN generate view
- templates/accounts/user_form.html — PIN prikaz modal
- registration/password_reset_form.html — poruka za korisnike bez emaila
- management command: migrate_placeholder_emails.py

## ROK: Sprint nakon 15.04.
