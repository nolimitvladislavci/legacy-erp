# CLAUDE.md — CC automatski čita ovaj fajl pri svakom startu

## KORAK 1 — Pročitaj status (OBAVEZNO, svaki put)

Koristi Fenix LIMIT Connect MCP → read_file alat:

```
read_file: FENIX_STATUS.md
```

## KORAK 2 — Provjeri git

```
exec_command: cd /var/www/fina-connect && git log --oneline -5
```

## KORAK 3 — Uzmi najnoviji task

```
exec_command: ls -lt /var/www/fina-connect/CC_TASK_*.md | head -5
```

Pročitaj prvi (najnoviji) → izvršavaj.

## KORAK 4 — Samostalno djeluj

Čitaj FENIX_STATUS.md prioritete. Ako nema CC_TASK, sam odaberi
najvažniji prioritet i počni. Ne pitaj — radi.

---

## PRAVILA (ne smiju se kršiti)

1. Čitaj stvarne field nazive iz models.py PRIJE svakog pisanja koda
2. Svaki problem prijavi odmah — ne sakrij
3. Na kraju sesije: git log + ažuriraj FENIX_STATUS.md
4. Commit format: `tip(modul): opis` — npr. `fix(pos): gumb za storno`
5. `venv/bin/python manage.py check` mora biti 0 errors nakon svakog commita
6. MCP parametar za komande: `cmd` (ne `command`)
7. Testni PIN za sve profile: 123123

## KLJUČNI URL-ovi

| Ruta | Opis |
|------|------|
| /hr/login/ | Login stranica |
| /hr/companies/stolovi/ | Stolovi — raspored komitenata po radnicama |
| /hr/accounts/odaberi-komitente/ | Odabir komitenata za radnicu |
| /hr/documents/arhiva/ | Digitalna arhiva — svi dokumenti |
| /hr/documents/arhiva/upload/ | Upload dokumenta u arhivu |
| /hr/smart-import/ | AI import računa (slika/PDF/XML) |
| /hr/pos/onboarding/ | POS onboarding wizard |
| /hr/ai-cockpit/doktor/ | Claude Doktor — dijagnoza po firmi |
| /no-limit/ | NO LIMIT azil landing |
| /client/<uuid:token>/ | Klijentski portal (bez logina, token) |

## ARHITEKTURA SERVERA (PROČITAJ UVIJEK PRVI)

```
SERVER: 37.27.248.86 | ssh -p 2222 root@37.27.248.86

SUSTAV 1 — Fenix V3:    v3.limit-connect.com → /var/www/fenix-v3/   → gunicorn-fenix-v3 :8001
SUSTAV 2 — Stari ERP:   fina-connect.online  → /var/www/fina-connect/ → gunicorn-fina (unix)

BAZE (Stari ERP):
  fina_erp     → PgBouncer :6432  ← CONN_MAX_AGE=0 obavezno!
  memio_pets   → direktno  :5432
  memio_farm   → direktno  :5432
  memio_world  → direktno  :5432

REDIS: 127.0.0.1:6379/1 (dijele oba sustava)
Reload: systemctl reload gunicorn-fina.service
Detalji: /var/www/fenix-v3/FENIX_ZAKON.md — Zakon 13
```

---

## KONTEKST

- Projekt: LIMIT Connect (Django 5.1, PostgreSQL, Redis, Celery)
- Server: 37.27.248.86 — limit-connect.com
- Venv: /var/www/fina-connect/venv/bin/python
- Baze: default (fina_erp), memio_pets, memio_world
- CC je AUTONOMAN — sam odlučuje, sam izvršava, sam commitira
- Ivan = vlasnik, Marija = prvi korisnik/tester
- Trojstvo: Haiku (analiza) + Gemini (istraživanje) + Sonnet (koordinacija) + CC (implementacija)

## ARHIVA TOK (najvažniji flow)

```
Računovođa logira se → odabere komitenta (switch company)
→ otvori /hr/documents/arhiva/upload/
→ uploada sliku/PDF računa
→ FenixScan OCR parsira (dobavljač, broj, iznos, datum)
→ AI proposal (Haiku) — prijedlog knjiženja (async 3s)
→ ArhivaEntry kreiran, ai_status: pending → processing → done
→ Drawer: pregled + gumbi (WhatsApp / Email / Spremi / Učitaj)
→ Slanje komitentu sprema kontakt u Company.phone/email
```
