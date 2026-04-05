# CC TASK F1 — LIMIT Connect UI/UX Audit + Popravci
# Prioritet: 🔥 ODMAH | Rok: 07.04.2026.
# Assignee: Claude Code
# Cilj: Interni moduli 6/10 → 9/10 UI

## KONTEKST
Marija dry-run je 08.04. Šeki i Kruljac testiraju POS. Sve mora izgledati profesionalno.
Ratni raspored kaže: 07.04. = QA dan.

## ZADACI (redom po prioritetu)

### 1. POS sučelje — mobilni audit
Provjeri kako POS izgleda na mobile (375px width):
- `/hr/pos/terminal/` — gumbi dovoljno veliki za prste (min 44px)?
- Numerička tipkovnica — vidljiva bez scrolla?
- Artikli — čitljivi font min 16px?
- Recept/račun — uredan ispis?
Popravi sve što nije mobile-friendly.

### 2. Interni moduli — navigacija
Provjeri sidebar/navbar:
- Sve kategorije prisutne (Prodaja, Nabava, Konto, Honorari, Radnici, Sezonski...)?
- Breadcrumbs rade?
- Mobilni hamburger menu funkcionira?

### 3. Faktura prikaz
- `/hr/prodaja/faktura/nova/` — forma uredna?
- Preview fakture prije ispisa/slanja?
- PDF download radi?

### 4. Dashboard (Home)
- `/hr/` — ima li dashboard smisla vizualno?
- Koji KPI-ji se vide? Jesu li relevantni?
- Dark/light mode radi ispravno svuda?

### 5. Forme — validacija
- Pogreška poruke vidljive i jasne?
- Required polja označena?
- Success/error notifikacije?

## KAKO RADITI
```bash
# Provjeri sve rute koje postoje
python manage.py show_urls 2>/dev/null | grep "^/hr/" | head -50

# Provjeri CSS za mobile
grep -r "min-width\|max-width\|@media" /var/www/fina-connect/static/css/ | head -20
```

## OUTPUT
Za svaki problem: OPIS → FIX → COMMIT
Commiti u format: `fix(ui): [opis]`
Minimalno 5, maksimalno 20 commitova.
Sve DONE stavke u FENIX_STATUS.md.
