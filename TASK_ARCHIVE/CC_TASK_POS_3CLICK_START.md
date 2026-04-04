# CC_TASK: POS Redesign — 3 klika do prodaje
## Agent: Claude Code | Prioritet: VISOK | Datum: 2026-03-23

## Kontekst
Zadatak postoji kao CC_TASK_POS_REDESIGN_3KLIKA.md ali nije počet.
Šeki (Uvijek Friško) koristi POS svaki dan — brzina je sve.
Trenutni POS je funkcionalan ali nije optimiziran za "3 klika do prodaje".

## Čitaj PRVO
```bash
cat /var/www/fina-connect/CC_TASK_POS_REDESIGN_3KLIKA.md
```
Pa provjeri trenutni POS template:
```bash
ls /var/www/fina-connect/templates/pos/
grep -n "class\|btn\|click\|cart" /var/www/fina-connect/templates/pos/terminal.html | head -40
```

## Zadatak
Implementiraj što je u originalnom task fajlu.
Fokus: 3 klika max od otvorene kase do fiskaliziranog računa.

Pravila:
- Čitaj stvarne POS modele prije pisanja koda
- Ne briši postojeću funkcionalnost — samo dodaj/poboljšaj
- Testiraj u Šekijevom okruženju (Uvijek Friško — pekara)

## Commit poruka
`POS: 3-click redesign — brzina prodaje za Šekija`
