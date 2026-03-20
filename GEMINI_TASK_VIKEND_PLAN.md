# Gemini Task — Pregled vikend plana: što može poći po krivu?

## Kontekst
Ponedjeljak 23.03. — dolaze pravi korisnici:
- Marija Brtan (Konjik d.o.o.) sa 60+ komitenata
- Korpaš d.o.o. — 5 korisnika
- Šeki (Uvijek Friško) — 3 POS prodajna mjesta

## Što CC agenti rade ovaj vikend

### Zadatak 1 (CC#1): ERacun unique_together
Dodaje `unique_together = [('company', 'invoice_number')]` na ERacun model.
Rizik: migracija na bazi koja ima 0 ERacun unosa — trivijalna.
Pitanje za tebe: je li ovo dovoljno ili trebamo i AppValidator koji blokira
duplikat PRIJE nego dođe do DB?

### Zadatak 2 (CC#2): Feedback gumb u base.html
Floating ⚠️ gumb koji šalje tekst na /superadmin/ai/api/submit-request/.
Rizik: CSRF, JSON parsing, base.html je shared template za sve stranice.
Pitanje za tebe: što može poći po krivu s CSRF tokenom u static JS contextu?

## Tvoja 3 pitanja

### PITANJE 1: Onboarding u ponedjeljak
8 korisnika čeka invite, 7 nema email (ručna predaja lozinki).
Ovo su Šekijevi radnici: dusica.dornjak, elona.temaj, sladjana.sekulic, stefa.bek.
Najrealniji scenario: Šeki dođe s mobitelom, 4 radnika čekaju da mogu ući u POS.
Kako preporučaš da Ivan to odradi? QR na papiru s lozinkom? WhatsApp?

### PITANJE 2: POS testiranje s 3 blagajne
Šeki ima 3 prodajna mjesta. Sve na istom sustavu, različite smjene.
Koji su najčešći problemi pri prvom pokretanju multi-terminal POS-a?
(stock sync, concurrent sessions, Z-report zatvaranje)

### PITANJE 3: Što mi NEDOSTAJE u planu?
Gledam na: unique constraint, feedback loop, bulk invite.
Što bi TI dodao/promijenio da ponedjeljak prođe bez vatrogasnih intervencija?

## Format odgovora
Kratko, direktno. Ovo nije akademski rad — ovo je vikend sprint.
