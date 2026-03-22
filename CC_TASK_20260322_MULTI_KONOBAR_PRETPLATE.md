# CC TASK: Multi-konobar + Pretplate + Arhiva pristup
# Datum: 2026-03-22
# Prioritet: VISOK

## PRAVILO: Besplatni plan = 1 terminal ZAUVIJEK. Plaćeni = više.
## PRAVILO: Uvijek 1 terminal dostupan, čak i bez pretplate.
## PRAVILO: Poruka "Nadoplati" kad pokuša otvoriti 2. terminal.

## TASK 1: Poruka kod 2. terminala
- Besplatni korisnik otvara 2. terminal → soft banner:
  "Besplatni plan podržava 1 blagajnu. [Nadoplati →]"
- NE blokiraj — prikaži banner, korisnik odlučuje
- Link na /register/upgrade/

## TASK 2: Multi-konobar preuzimanje
- Kad drugi konobar upiše PIN → poruka: "Konobar [Ime] aktivan. Preuzeti?"
- "Preuzmi" → odjavi prethodnog, prijavi novog
- Svaki bon bilježi cashier OIB

## TASK 3: Otkazivanje pretplate
- /companies/subscription/ — plan info + "Otkaži" gumb
- cancel_at_period_end = True, pristup do kraja perioda
- Arhiva UVIJEK dostupna (ZOR 11 godina čuvanja)
- Auto-downgrade na "archive_readonly" plan

## TASK 4: Logo firme u POS headeru
- company.logo ako postoji, inače LIMIT Connect logo
- Klik → /companies/settings/#logo

## TASK 5: Info tko je prijavljen
- POS header: prikaži ime aktivnog blagajnika
- Ako nema cashier → prikaži username
