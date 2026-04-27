
---

## ZAKON 9 — KODEKS INŽENJERSKE ČASTI
### "Bez generičkog koda"

Svaki red koda koji izlazi iz ovog sustava mora biti dostojan potpisa.

**Minimum:** Senior inženjer ispred svog vremena, s pogledom dalje nego što vidi.

**Zabranjeno:**
- Generički kod koji ne zna gdje je krenuo ni kamo ide
- View funkcija bez jasnog state contracta
- `except: pass` — svaka greška se logira ili propagira
- Frontend bez state machine — korisnik uvijek zna u kojoj je fazi
- Kamera kao fallback — `getUserMedia` je prvi izbor, ne `<input capture>`
- Privremena rješenja koja postaju vječna

**Obavezno:**
- Svaka view: jasno što prima, što vraća, koje iznimke baca
- Svaki API endpoint: konzistentna JSON shema `{ok, data, error}`
- State machine u frontendu: IDLE → ACTION → PROCESSING → RESULT → ERROR

**Filozofija:**
Ne pišeš kod koji radi danas.
Pišeš arhitekturu koja mora opstati kad tebe nema.

*Zapečaćeno: FENIXINEF™ v1.0 — Ivan Brtan, 2026.*

## ZAKON 26 - PLANOVI SE PISU NA SERVER, NIKAD SAMO U RAZGOVOR
Razgovor nije trajni medij - server jest.
Pravilo: CC zapisuje sve planove na server prije kraja sesije.
1. Provjeri postoje li novi planovi koji nisu u CC_PLAN_*.md fajlovima
2. Ako postoje -> zapiši odmah via SSH ili copy/paste komande
3. git add + git commit -m docs(memory): planovi DD-MM-YYYY
Krsenje: planovi se gube. Ivan gubi zivce (10. put).


## ZAKON 27 — PLAN BEZ VERIFIKACIJE KODA JE LAZAN PLAN (2026-04-27)

Svaki plan koji CC napiše MORA biti provjeren o stvarnom stanju koda PRIJE objave.

**Why:** CC je pisao planove koji izgledaju kompletni ("Akcija: CC danas", "Tko: CC")
ali nije provjerio postoji li fajl, model, endpoint, polje u bazi.
Rezultat: plan je lista zelja maskirana kao gotov zadatak.
Ivan je morao sam otkrivati propuste. To je neprihvatljivo.

**How to apply:**
Za SVAKI plan item koji TVRDI da nesto postoji ili da ce CC implementirati:
  1. grep/find - provjeri postoji li fajl/funkcija/model/polje
  2. Ako ne postoji - odmah implementiraj ILI jasno oznaci: [TODO - ne postoji]
  3. NIKAD ne pisati "Akcija: CC (danas)" bez da odmah napravis tu akciju
  4. NIKAD ne pisati naziv fajla koji nisi provjerio da postoji (npr. dok_builder.py)

Redosljed: PROVJERI -> IMPLEMENTIRAJ -> POTVRDI -> tek onda pisi plan kao gotovo.

Krsenje: Plan koji tvrdi da je nesto gotovo a nije = laz prema Ivanu = nultoleranacija.


## ZAKON 28 — FUNKCIONALNI KOD JE POTPUN BEZ NAPLATE (2026-04-27)

**Temeljno pravilo arhitekture svih sustava (VETRA, fina-connect, fenix-v3):**

Svaki modul se gradi POTPUNO FUNKCIONALAN bez modula naplate.
Naplata je tanka vanjska ljuska koja se dodaje ZADNJA, neposredno prije produkcije.

**Why:**
Naplata NIKAD ne smije biti uvjet za razvoj funkcionalnosti.
Mijesanje billing logike s poslovnom logikom = najcesca greska arhitekture.
Funkcionalni kod dokazuje vrijednost. Billing samo biljezi tu vrijednost.

**Kako to izgleda u praksi:**
  - Svaki modul: radi 100% bez provjere pretplate / kredita / fakture
  - Svi moduli su globalnog karaktera - dostupni svim tenantima u testnoj fazi
  - Billing modul: jedan, centralan, dodaje se kad je funkcionalnost gotova
  - Produkcija = Funkcionalni kod (gotov) + Billing (brzo, na kraju) = LIVE

**Redosljed razvoja (obavezan):**
  1. Implementiraj modul potpuno (UI + logika + API)
  2. Testiraj funkcionalni dio bez ikakvih billing provjera
  3. Potvrdi da sve radi
  4. Dodaj billing check kao jedan middleware/decorator (ne dirkas poslovnu logiku)
  5. Test naplate (brzo - 1-2 dana)
  6. Produkcija

**Sto se NE radi:**
  - Ne blokiras feature iza billing gate-a tijekom razvoja
  - Ne pises if tenant.plan == pro: u poslovnoj logici
  - Ne odgadas testiranje jer billing nije gotov

**Analogija:**
Gradis kucu (funkcionalni kod). Struja/voda/plin (billing) se prikljucuju zadnji.
Kuca je gotova i korisna i bez prikljucaka - prikljucci su brzi i standardizirani.

Krsenje: Blokiranje razvoja modula zbog billing logike = arhitekturalna greska = zabranjena.
