# CLAUDE.md — CC automatski čita ovaj fajl pri svakom startu

## KORAK 1 — Pročitaj status (OBAVEZNO, svaki put)

Koristi Fenix LIMIT Connect MCP → read_file alat:

```
read_file: /var/www/fina-connect/FENIX_STATUS.md
```

## KORAK 2 — Provjeri git

```bash
cd /var/www/fina-connect && git log --oneline -5
```

## KORAK 3 — Uzmi najnoviji task

```bash
ls -lt /var/www/fina-connect/CC_TASK_*.md | head -5
```

Pročitaj prvi (najnoviji):
```
read_file: /var/www/fina-connect/CC_TASK_<IME>.md
```

## KORAK 4 — Izvršavaj

Sve fajlove čitaj i piši kroz MCP (read_file, write_file, exec_command).
Nikad ne tražiš fajlove lokalno — sve je na serveru 37.27.248.86.

---

## PRAVILA (ne smiju se kršiti)

1. Čitaj stvarne field nazive iz models.py PRIJE svakog pisanja koda
2. Svaki problem prijavi odmah — ne sakrij
3. Na kraju sesije: git log + ažuriraj FENIX_STATUS.md
4. Commit format: `tip(modul): opis` — npr. `fix(pos): gumb za storno`
5. venv/bin/python manage.py check mora biti 0 errors nakon svakog commita

## KONTEKST

- Projekt: LIMIT Connect (Django 5.1, PostgreSQL, Redis, Celery)
- Server: 37.27.248.86 — limit-connect.com
- Venv: /var/www/fina-connect/venv/bin/python
- Koordinator: Sonnet (claude.ai) — executor: CC (ti)
- Ivan = vlasnik, na enteru, ne smeta se s tehničkim odlukama
