# VAL 3 — DIO 1: ORM RUČNI DEEP PASS (OPUS)
> Najzahtjevniji — svaki view ručno, kontekst template-a, N+1 eliminacija

## CILJ
select_related/prefetch: 1,364 → 1,800+
Ručni prolaz top 6 view fajlova — razumijevanje svakog queryseta.

## SCOPE (po query gap-u):
1. synesis/views.py — 1,637 linija, 179 querya, 4 optimized (2%)
2. worktime/timesheet_views.py — 24 broad catches, gust queryset
3. pos/views.py — 5,890 linija, 950 querya
4. core/views.py — 3,024 linija, 925 querya
5. invoicing/views.py — 2,333 linija, 291 querya
6. appointments/views.py — 1,865 linija, 139 querya

## PRAVILA
- Čitaj svaki view, razumi koji FK se dereferenciraju
- Dodaj select_related za ForeignKey/OneToOne
- Dodaj prefetch_related za reverse FK/M2M
- .only() za list viewse
- .exists() umjesto count()>0
- annotate() umjesto Python petlji za aggregacije
- AST validate nakon svakog fajla

## NE DIRATI:
- Modele, migracije
- csrf_exempt (gotovo)
- Ruff/lint (DIO 2)
- i18n (DIO 3)
