## PRVO PROCITAJ STATUS
```bash
cat /var/www/fina-connect/FENIX_STATUS.md
```

# GEMINI TASK — Analiza: bulk_invite sigurnost i edge cases

## Kontekst projekta
LIMIT Connect — Django multi-tenant ERP, HR tržište.
Server: limit-connect.com, 78 kompanija, 318 korisnika.

## Što Claude Code implementira (paralelno s tvojom analizom)
Management command `bulk_invite` koji:
1. Pronađe sve korisnike koji se nikad nisu prijavili (last_login__isnull=True)
2. Generira temp lozinku (secrets.choice, 12 znakova)
3. Postavi must_change_password=True
4. Pošalje welcome email async (Celery)

## Stvarni podaci (provjereni)
- 12 korisnika nikad nije ušlo
- 4 imaju email → mogu primiti invite
- 8 NEMA email → problem
- profile.company može biti NULL (SET_NULL u modelu)

## Tvoj zadatak — analiziraj 5 nagaznih mina

### MINA 1: Korisnici bez emaila (8 od 12)
- Što se dogodi s njima? Samo skip?
- Treba li generirati temp lozinku i za njih (za ručnu predaju)?
- Kako ih prikazati u outputu da Ivan zna koga treba kontaktirati?

### MINA 2: Celery nije aktivan
- send_html_email_task.delay() tiho padne ako Celery worker ne radi
- Komanda će reći "email poslan" ali email nikad ne stigne
- Rješenje: sync fallback ili provjera Celery statusa prije slanja?

### MINA 3: profile.company = NULL
- UserProfile.company je ForeignKey s SET_NULL
- Postoje korisnici bez kompanije u bazi
- Filter `profile__company=company` ih ispravno isključuje
- Ali: trebaju li biti u zasebnom reportu za Ivana?

### MINA 4: Idempotentnost
- Što ako se komanda pokrene dvaput?
- Korisnik dobije 2 emaila, 2 temp lozinke
- Prva lozinka postaje nevažeća čim se postavi druga
- Rješenje: flag `invite_sent_at` na profilu? Ili check must_change_password?

### MINA 5: Sigurnost temp lozinke u emailu
- Lozinka putuje emailom u plain textu
- Korisnik MORA promijeniti pri prvom loginu (middleware enforcea)
- Je li 12 znakova dovoljno? Je li secrets.choice siguran?
- Treba li lozinka isteći nakon 72h ako se ne iskoristi?

## Format odgovora
Za svaku minu: RIZIK (visok/srednji/nizak) + preporučeno rješenje u 2 rečenice.
Na kraju: Go/No-Go za implementaciju + lista promjena ako No-Go.
