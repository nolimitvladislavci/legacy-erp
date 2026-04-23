# CC_TASK — NO LIMIT Servis + 3 Inovacije iz Budućnosti
## Status: TODO | Prioritet: P0

---

## KONTEKST
Sesija 56. dana. Ivan je dao nalog: "servisiraj NO LIMIT na razinu dostojnu naše razine."
Djeluj kao senior inženjer koji je preuzeo projekt. Cilj: 13/10 na svim frontama.

## ZADATAK 1 — Pravopis no_limit.html (fina-connect)
File: `/var/www/fina-connect/templates/website/no_limit.html`
Backup postoji: `no_limit_backup_20260420.html`

Napravi Python script koji zamjenjuje sve iznakažene CRO dijakritike:
```python
replacements = {
    'cuva': 'čuva', 'Cuva': 'Čuva', 'cuvamo': 'čuvamo',
    'sto ': 'što ', 'Sto ': 'Što ', 'sto.': 'što.',
    'zivotinje': 'životinje', 'zivotinja': 'životinja',
    'vlasnickih': 'vlasničkih', 'vlasnicke': 'vlasničke',
    'trosica': 'troška', 'trosak': 'trošak',
    'znacenje': 'značenje', 'znaci': 'znači',
    'prezivljava': 'preživljava', 'prezivljava': 'preživljava',
    'isjecke': 'isječke', 'isjecak': 'isječak',
    'osnivacke': 'osnivačke', 'osnivacka': 'osnivačka',
    'zapecateni': 'zapečaćeni', 'zapecatiti': 'zapečatiti',
    'naseg': 'našeg', 'nasim': 'našim', 'nase ': 'naše ',
    'Gradimo': 'Gradimo', 'Branimo': 'Branimo',
    'cijelog': 'cijelog',
    'svjedoci': 'svjedoci',
    'kriptografski': 'kriptografski',
}
```
Prođi CIJELI file word-by-word. Provjeri na no-limit.world nakon deploya.

## ZADATAK 2 — Dodati nove patente / OSS reference u NO LIMIT landing

U sekciju "Dokumenti" (`.dokumenti-section`) dodati 5 novih kartica:
- folija-py | PyPI | MIT | Runtime Integrity Python
- folija-js | npm | MIT | Runtime Integrity Node.js  
- folija-go | Go | MIT | Runtime Integrity Go
- folija-dotnet | NuGet | MIT | Runtime Integrity .NET
- OpenDOK-2026 | CC0 | Javna domena | .dok standard

ChainBlock blokovi: #22-#26 (već zapečaćeni — samo prikazati).

Format doc-card istog stila kao postojeće kartice.

## ZADATAK 3 — Genesis Block badge "aktivan=0" fix

Problem: Genesis block (#0, NOLIMIT-GENESIS-0001) prikazuje badge "aktivan=0".
Uzrok: badge logika vjerojatno provjerava neki aktivacijski flag koji genesis blok nema.

Fix: u views_badge.py ili verify_chain template — genesis blok (block_number=0) 
uvijek je "AKTIVAN" neovisno o flagovima. Dodati poseban check.

Lokacija: `/var/www/fenix-v3/evalidator/views_badge.py`
URL testa: `https://limit-connect.com/verify/NOLIMIT-GENESIS-0001/`

## ZADATAK 4 — Quick Login (1-click za poznate uređaje)

Implementirati "Quick Login" za TrustedDevice korisnike:
- Ako device_fingerprint prepoznat I zadnji login < 8h → prikaži "Dobrodošao natrag, [ime]" + PIN unos direktno
- Preskoči username/password korak za verified devices
- Logirati kao BookingSignature event 'quick_login'

Lokacija: `/var/www/fenix-v3/accounts/` (trikey_views.py + login template)

## ZADATAK 5 — .dok Badge Embed Widget upgrade

Trenutni trust-badge.js prikazuje samo chain verification.
Upgrade: prikaži folija-krunica status + .dok seal QR kod + block broj.

```html
<!-- Embed 3 linije -->
<div data-folija-seal="NOLIMIT-GENESIS-0001"></div>
<script src="https://limit-connect.com/static/js/trust-badge.js"></script>
```

Dodati u trust-badge.js:
- Folija seal status (language + version)
- .dok bundle download link  
- Animirani "krunica širi se" efekt (CSS pulse na chain nodes)

## 3 INOVACIJE IZ BUDUĆNOSTI (ZAKON 24 ih zahtijeva)

### 1. TEHNOLOGIJA — AI Document DNA (Semantic Fingerprint)
Svaki dokument koji prođe FenixScan dobiva AI "DNA" — 512-dim embedding.
Duplikat detekcija ne radi na hashu (koji se mijenja s jednim bitom) nego na SEMANTICI.
"Isti ugovor, drugačiji datum" = match na 94%+ sličnosti.
Implementacija: sentence-transformers model, pohrana u pgvector.
Utjecaj: eliminiraj duplikate u arhivi, detect plagijat, pronađi varijante ugovora.

### 2. SIGURNOST — Dead Man's Switch za kritične dokumente
Dokument označen kao "kritičan" šalje se automatski na 3 e-mail adrese ako 
korisnik nije pristupio sustavu 30 dana. "Digitalna oporuka" feature.
Implementacija: Celery Beat daily job, check last_login, send encrypted ZIP.
Utjecaj: jedinstven sigurnosni feature, emotivna prodajna priča za 50+ tržište.

### 3. MREŽNI EFEKT — Folija Trust Network (cross-platform verification)
Svaki user koji embedda trust-badge.js postaje "Folija node".
Čvor šalje heartbeat na central verify API.
Vizualizacija na no-limit.world: live karta EU čvorova koji verificiraju.
Implementacija: Celery + Redis counter, Leaflet.js karta, anonymized IPs.
Utjecaj: svaki embed = viral marketing + network effect + demo EU coverage.

---

## DEPLOY REDOSLIJED
1. Pravopis fix (fina-connect) → `systemctl reload gunicorn-fina.service`
2. OSS kartice (fina-connect) → reload
3. Genesis badge fix (fenix-v3) → `systemctl reload gunicorn-fenix-v3.service`
4. Quick Login → test na mobitelu
5. Trust Badge upgrade → purge CDN cache

## PROVJERI NAKON DEPLOYA
- [ ] no-limit.world — nema pravopisnih grešaka
- [ ] Genesis block pokazuje AKTIVAN badge
- [ ] 5 novih OSS kartica vidljive
- [ ] Quick Login radi na mobitelu
- [ ] trust-badge.js prikazuje folija status

