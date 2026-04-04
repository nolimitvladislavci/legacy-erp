# CC_TASK_PUTNI_NALOG_TEMPLATES — Putni nalog 10/10
# Agent: CC Code
# Prioritet: VISOK — otvara KUD, lovce, ribare kao klijente
# Datum: 2026-03-25

---

## Status backend-a (NE DIRAJ — sve radi)

- ✅ Model: `worktime/models.py` — TravelOrder + TravelExpense kompletni
- ✅ Views: `worktime/travel_views.py` — list, create, detail, approve
- ✅ URLs: `worktime/urls.py` — sve rute konfigurirane
- ✅ Admin: bug popravljen (try/except wrap)
- ❌ Templates: NE POSTOJE — ovo jedino treba napraviti
- ❌ PDF export: nedostaje
- ❌ Mobile 3-klik flow: nedostaje

---

## Što treba kreirati

### 1. `worktime/templates/worktime/travel_order_list.html`

Nasljeđuje `base.html`.
Prikazuje listu putnih naloga s filterima po statusu.
Status badge boje: draft=grey, approved=blue, completed=green, cancelled=red.
Gumb "Novi putni nalog" prominentno gore.
Tablica: Broj | Djelatnik | Odredište | Datum polaska | Prijevoz | Ukupno | Status | Akcije

### 2. `worktime/templates/worktime/travel_order_form.html`

**MOBILE-FIRST — 3 klika na mobitelu.**
Koristi se za kreiranje. Polja:

```
Redoslijed u formi (po važnosti):
1. Odredište (text, required)
2. Svrha putovanja (textarea, 2 reda)
3. Polazak → Povratak (datetime-local, side by side)
4. Vrsta prijevoza (radio buttons, vizualni ikonice)
5. Kilometraža (number, samo ako car_personal/car_company)
6. Broj dana dnevnice (number, decimal)
7. Dnevnica po danu (default 26.55 EUR — zakonski maksimum HR)
8. Ostali troškovi (number, opcionalno)
9. Napomene (textarea, opcionalno)
```

Live preview: dok korisnik unosi km i dnevnice, odmah prikazuje izračun ukupnog troška.
JavaScript: `updateTotal()` na svaki input event.

### 3. `worktime/templates/worktime/travel_order_detail.html`

Prikazuje detalje naloga.
Sekcije:
- Header: broj naloga, status badge, ukupni trošak
- Putovanje: odredište, svrha, datumi, prijevoz
- Troškovi: dnevnice, kilometraža, ostalo, UKUPNO
- Troškovi s prilogom: lista TravelExpense (ako postoje)
- Akcije (ovisno o statusu i ulozi):
  - draft + može odobriti → "Odobri" / "Otkaži" gumbi
  - approved → "Završi" gumb
  - completed → "Ispiši PDF" gumb

### 4. PDF export — dodaj view u `travel_views.py`

```python
@login_required
def travel_order_pdf(request, pk):
    """Generira PDF putnog naloga za ispis/arhivu."""
    company = get_user_company(request)
    order = get_object_or_404(TravelOrder, pk=pk, company=company)
    # Koristi ReportLab ili WeasyPrint (već instaliran)
    # Template: worktime/templates/worktime/travel_order_print.html
    # Response: application/pdf, filename: PN-{order.order_number}.pdf
```

Dodaj URL u `worktime/urls.py`:
```python
path('travel-orders/<int:pk>/pdf/', travel_views.travel_order_pdf, name='travel_order_pdf'),
```

### 5. `worktime/templates/worktime/travel_order_print.html`

Čisti A4 print template. Sadržaj:
- Zaglavlje: firma, OIB, adresa
- Naslov: PUTNI NALOG br. {order_number}
- Tablica troškova
- Polja za potpise: Djelatnik, Odobrio, Blagajnik
- Footer: datum ispisa

---

## KUD / Lovci / Ribari — specifičnosti (VAŽNO)

Model već podržava sve kroz TravelExpense.EXPENSE_TYPES:
- KUD smotre → `costume` (Kostim/uniforma), `registration` (Kotizacija)
- Lovci → `licence` (Dozvola), `fuel` (Gorivo do lovišta)
- Ribari → `licence` (Ribolovna dozvola), `ticket` (Karta na plovilo)

**U formi za kreiranje TravelExpense** (dodati kao inline na detail page):
- Dropdown tip troška
- Iznos
- Upload slikovnice/računa (receipt_file)
- Datum računa

---

## Integracija s konto/Marijom

Travel order completed → automatski kreira konto knjiženje:
```python
# U travel_views.py, travel_order_approve view, action='complete':
from konto.models import JournalEntry  # ako postoji
# Kreira: Troškovi putovanja (razred 4) ↔ Obveze prema zaposlenicima
```
Ako konto integracija nije trivijalna — ostavi za Fazu 2, samo dodaj TODO komentar.

---

## Provjera gotovosti (10/10 checkpoints)

- [ ] travel_order_list.html — renderira bez greške
- [ ] travel_order_form.html — kreira novi nalog, live total
- [ ] travel_order_detail.html — prikazuje sve detalje
- [ ] Approve/Complete/Cancel — mijenja status
- [ ] TravelExpense inline na detail — dodaj/briši troškove
- [ ] PDF generira se, download radi
- [ ] Mobile responsive (provjeri na 375px)
- [ ] KUD klijent (KUD Dukat Vladislavci) može kreirati nalog
- [ ] admin.py — TravelOrder vidljiv u /admin/ bez greške
- [ ] Commit: `feat: putni nalog templates + PDF — KUD/lovci/ribari ready`

---

## Napomena za CC Code

Stari server ALLOWED_HOSTS ima 85.9.201.204 — to je BUG-05, ali ne diraj u ovom tasku.
Nakon commit: `git push` i `sudo systemctl restart gunicorn`.
