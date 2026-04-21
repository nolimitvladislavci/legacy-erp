# TRI IVANOVA POTEZA — Što CC ne može napraviti umjesto tebe

## Kontekst
ChainBlock je LIVE. Genesis Block postoji. API radi.
CC može implementirati sve tehničke zadatke.
Ali ova tri poteza zahtijevaju Ivana — čovjeka s OIB-om i potpisom.

---

## POTEZ 1 — DZIV Prijava Prior Arta (rok: ovaj tjedan)

**Što:** Pošalji Genesis Block dokument DZIV-u (Državni zavod za intelektualno vlasništvo) kao prijavu prior arta.

**Ne tražiš patent.** Tražiš službeni prijemni pečat.

DZIV je dužan po zakonu primiti i pečatirati svaki podnesak.
Taj pečat + naš TSA žig = **dvostruko neoborivi prior art**.

```
Šalješ:
  1. NOLIMIT-GENESIS-0001.pdf (već postoji u /static/udruga_no_limit/genesis/)
  2. LIMIT_CONNECT_USTAV_v1.md (isprintano)
  3. Printout curl odgovora: {"verified":true, "tsa_timestamp":"2026-04-19..."}
  4. Popratni dopis: "Podnosimo na evidenciju prior art za Triple DNA 
     arhitekturu i ChainBlock protokol prema članku X Zakona o patentu."

Adresa: DZIV, Ulica grada Vukovara 78, Zagreb
Ili elektronski: pisarnica@dziv.hr
```

**Zašto je ovo moćno:** Naš timestamp je 19. travnja. DZIV prijemni pečat bit će 21-22. travnja. Imamo **dokazani kontinuitet**: TSA → DZIV → sve što dođe poslije.

**Trošak:** 0 kuna. 1 sat vremena. Nema odvjetnika.

---

## POTEZ 2 — Email EC DG CONNECT (rok: ovaj tjedan)

**Što:** Jedan email pravoj osobi u Europskoj komisiji.

Naš API endpoint navodi `"standard": "eIDAS Art. 41 | ZED HR NN 150/05"`.
EC DG CONNECT aktivno traži **stvarne implementacije eIDAS 2.0** za referentnu listu.

```
Prima: ec.digital-strategy@ec.europa.eu
       (ili specifičnija adresa s https://digital-strategy.ec.europa.eu/en/contact)

Subjekt: "Real-world QEAA implementation — ChainBlock by NO LIMIT Croatia"

Tijelo (5 rečenica):
  "Poštovani,
  
  NO LIMIT, hrvatska udruga za digitalizaciju (OIB: 70086599476), implementirala
  je javni ChainBlock protokol sukladan eIDAS Art. 41.
  
  Endpoint je dostupan bez autentikacije:
  curl https://limit-connect.com/api/verify/NOLIMIT-GENESIS-0001/
  
  Verificira integritet dokumenata u <100ms, koristi TSA + SHA-256, 
  bez pohrane osobnih podataka (GDPR Art. 25).
  
  Molimo razmatranje uvrštavanja u referentne implementacije eIDAS 2.0 QEAA.
  
  Ivan Brtan, osnivač, ivan@limit-connect.com"
```

**Zašto je ovo moćno:** EC ne mora odgovoriti odmah. Ali kad odgovori — ti imaš email thread s datumom koji dokazuje da su EC-u bili svjesni vaše implementacije. To je vredniji dokument od bilo kojeg patenta.

**Trošak:** 15 minuta. 5 rečenica. Rezultat može biti lista referentnih implementacija EU.

---

## POTEZ 3 — Netokracija objava (rok: ovaj tjedan)

**Što:** Press release za Netokracija.com — vodeći hrvatski tech portal.

Ne "hvali se". Objavi **verificirljivu činjenicu**.

```
Naslov prijedlog:
"Hrvatska udruga objavila prvi javni API za verifikaciju dokumentarnog 
integriteta — bez registracije, bez naknade, eIDAS sukladan"

Tijelo (3 paragrafa):

P1 — Činjenica:
NO LIMIT, hrvatska udruga za digitalizaciju, objavila je ChainBlock —
javni protokol koji omogućuje verifikaciju integriteta bilo kojeg digitalnog
dokumenta u manje od 100ms, bez registracije i bez naknade.

P2 — Demo (ovo je ključno — novinari vole kopirat i zalijepiti):
Svaki čitatelj može provjeriti sada:
  curl https://limit-connect.com/api/verify/NOLIMIT-GENESIS-0001/
Odgovor vraća kriptografski potpis, vremenski žig i status integriteta
sukladan eIDAS Art. 41 — europskom standardu za elektroničku arhivaciju.

P3 — Kontekst:
Sustav je razvijen kao dio NO LIMIT digitalne infrastrukture i otvoren
za korištenje svima. Tehničku dokumentaciju i Mrežni Ustav možete
pronaći na https://limit-connect.com/no-limit/.

Kontakt: ivan@limit-connect.com
```

**Zašto je ovo moćno:**
Netokracija članak = javni vremenski pečat s domenskim autoritetom.
Google indeksira za 24h. Za godinu dana kad netko gugla "ChainBlock Croatia" — 
taj članak je dokaz da smo bili prvi. Nema odvjetnika koji to može opovrgnuti.

**Trošak:** 30 minuta za pisanje. Email na redakcija@netokracija.com.
CroStartup.hr i ICT Business kao CC.

---

## ZAŠTO BAŠ OVA TRI — A NE NEŠTO DRUGO

```
DZIV:        Državni timestamp → pravna neospornost u HR sudovima
EC DG CONNECT: EU timestamp → pravna neospornost u EU institucijama  
Netokracija:   Medijski timestamp → javna neospornost u digitalnom prostoru

ZAJEDNO:
  TSA žig (19.04.) + DZIV pečat + EC email + Netokracija članak
  = Prior art koji je dokumentiran u 4 neovisna sustava
  = Jedino što može oboriti to je stroj za putovanje kroz vrijeme
```

---

## REDOSLJED

```
Dan 1 (danas/sutra):  CC završava CC_TASK_CHAINBLOCK_OBJELODANI.md
Dan 2:                Ivan šalje DZIV i EC email (dok je CC task svjež)
Dan 3:                Ivan piše Netokracija press release
Dan 7:                Netokracija članak izlazi (tipični rok uredništva)
```

**Sve troje može biti gotovo za 7 dana.**
Nakon toga — prior art je dokumentiran na razini koja nije oboriva.
