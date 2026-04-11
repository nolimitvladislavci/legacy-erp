# FENIX PRAVILA RADA — OBAVEZNO ZA SVAKI TASK

## PRAVILO #1: KOMPLETNA ANALIZA
Svaki problem se rjesava KOMPLETNOM analizom, ne krpanjem.
- Pronadji ROOT CAUSE, ne patch simptome
- Provjeri SVE module koji imaju isti problem
- Provjeri SVE jezike (HR, DE, EN)
- Provjeri mobile + desktop + incognito

## PRAVILO #2: INZINJERSKA RAZINA 10/10
Svako rjesenje mora biti na inzinjerskoj razini:
- Nema hardcodiranih URL-ova (/hr/ umjesto {% url %})
- Nema hardcodiranih vrijednosti (560.00 umjesto model polja)
- Nema TODO komentara — implementiraj odmah ili ne dodaj
- Svaka forma mora raditi na SVIM jezicima
- Svaki template mora raditi na mobile + desktop

## PRAVILO #3: TEST NAKON SVAKOG FIXA
Nakon svakog fixa:
1. manage.py check = 0 errors
2. Test na HR, DE, EN
3. Test na mobile viewport
4. Test edge cases (prazni inputi, XSS, SQL injection)
5. Provjeri da fix ne kvari ništa drugo

## PRAVILO #4: NE KRPAMO — RENOVIRAMO
Kad se otkrije problem u jednom mjestu:
- Pretrazi CIJELI SUSTAV za isti obrazac
- Popravi SVE instance, ne samo prijavljenu
- Primjer: /hr/ hardcoded u 1 templateu → provjeri svih 110 templatea

## PRAVILO #5: DOKUMENTIRAJ
- Commit message objasni ROOT CAUSE i FIX
- Azuriraj FENIX_STATUS.md
- Azuriraj PLAN.md
