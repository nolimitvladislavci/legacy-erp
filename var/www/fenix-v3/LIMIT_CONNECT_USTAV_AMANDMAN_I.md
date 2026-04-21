# AMANDMAN I — Digitalni Patentni Ured (DPU)
## Dodatak uz LIMIT-CONNECT MREŽNI USTAV v1.0 (LC-DS-2026-001)

```
DOKUMENT-ID:  LC-DS-2026-002
VRSTA:        Amandman uz Ustav
OVISI O:      LC-DS-2026-001 (Mrežni Ustav v1.0)
STATUS:       DRAFT — čeka implementaciju Genesis Endpointa
              (ne aktivira se prije nego /api/verify/ odgovori na
               prvi vanjski zahtjev)
```

---

## ČLANAK 7 — DIGITALNI PATENTNI URED (DPU)

### 7.1 Definicija

DPU nije institucija. DPU je protokol.

> Digitalni Patentni Ured je skup kriptografskih pravila koja
> omogućuju bilo kojoj osobi da dokaže vremenski prioritet
> izvedbe ideje — bez posrednika, bez pristojbi, bez granica.

DPU ne proglašava prava. DPU bilježi činjenice.
Sudac nije DPU. Sudac je matematika. Sudac je vrijeme.

### 7.2 Što DPU jest i nije

| DPU JEST | DPU NIJE |
|----------|----------|
| Protokol za prior art dokumentaciju | Zamjena za DZIV/EPO/USPTO |
| Kriptografski kronogram izvedbe | Pravna institucija |
| Otvoreni standard za verifikaciju | Vlasnik prava |
| Infrastruktura za zajednicu | Monopolist |
| Dokaz — ako je tehnički besprijekoran | Deklaracija — sama po sebi bezvrijedna |

### 7.3 DPU Genesis Protokol

Svaka inovacija registrirana u DPU-u dobiva "Digitalni DNK zapis":

```
DPU_RECORD {
  invention_hash:    SHA-256(source_code + documentation)
  git_commit:        verified commit hash
  tsa_timestamp:     RFC 3161 vremenski žig (ne naš — akreditirani)
  attestation_nodes: minimalno 3 čvora koji su verificirali zapis
  merkle_proof:      dokaz pozicije u DPU lancu
  otp_license:       OPT_LICENSE_v1.0 (vidi Članak 8)
}
```

**Ključna razlika od manifesta:**
Prior art je valjan samo ako je tehnički neoboriv.

```
SLABO:  "Imali smo ideju, napisali dokument"
        → Odvjetnik ga ruši za 20 minuta

JAKO:   "Ovaj algoritam je bio u produkciji, na ovom serveru,
         u ovom git commitu, sa ovim TSA žigom RFC 3161,
         atestiran od strane N nezavisnih čvorova"
        → Matematički neoborivo u 47 jurisdikcija
```

### 7.4 Federalni konsenzus (umjesto suca)

Kada dođe do spora "tko je prvi":

```
1. Oba aktera predaju svoje DPU zapise
2. Sustav uspoređuje tsa_timestamp oba zapisa
3. Stariji timestamp = prior art
4. Nema suca. Nema mita. Nema žalbe na matematiku.

Tko nema TSA žig — nema dokaz.
Tko ima raniji TSA žig — ima prioritet.
```

### 7.5 Otvoreni Patentni Trust (OPT) — licenca

OPT_LICENSE_v1.0 počiva na jednom pravilu:

> Slobodno koristi. Slobodno gradi. Ne zatvori.
> Ako uzmeš — moraš dodati. Ako zatvoriš — izgubiš pravo korištenja.

Nije GPL (previše restriktivan za komercijalno).
Nije MIT (premalo zaštite za ekosustav).
Jest: **Recipročna infrastrukturna licenca** — analogna Creative Commons BY-SA, ali za kod i algoritme.

---

## ČLANAK 8 — TRI ISTINE (Operativni kompas)

Ovo nisu inspirativne izreke. Ovo su operativna pravila koja određuju redosljed svakog idućeg koraka.

### Istina 1: Manifest dolazi NAKON implementacije

Satoshi nije proglasio Bitcoin. Objavio je kod koji radi i rekao: "Provjerite sami."

**Primjena:** DPU postaje stvaran u trenutku kada `/api/dpu/register/` endpoint odgovori na prvi vanjski zahtjev s valjanim TSA žigom. Ne dan ranije. Svaka objava prije toga je marketing, ne infrastruktura.

**Operativno pravilo:** Svaka inovacija iz ove mreže objavljuje se NAKON što je:
1. Commitirana u git s verifikabilnim hashom
2. Žigosana TSA-om
3. Verificirana od minimalno 3 neovisna čvora

### Istina 2: Prior Art snaga = tehnička preciznost zapisa

Ideja bez koda nije prior art. Whitepaper bez implementacije nije prior art.

**Primjena:** Svaki DPU zapis mora imati `git_commit` koji se može checkout-ati i pokrenuti. Sustav koji se ne može pokrenuti nije izum — to je prijedlog.

**Operativno pravilo:** CC ne commitira "concept" fajlove. CC commitira radni kod. Planovi postoje za interno planiranje, ne za DPU registraciju.

### Istina 3: Standard se osvaja upotrebom, ne proglašenjem

TCP/IP, Git, PDF — nisu proglašeni standardima. Postali su jer su riješili stvarni problem bolje od alternative i bili otvoreni za provjeru.

**Primjena:** Limit-Connect postaje de-facto standard za device integrity verifikaciju u trenutku kad 10+ neovisnih entiteta (banke, regulatori, developeri) poziva naš `/api/verify/` endpoint u produkciji.

**Operativno pravilo:** Svaki novi API endpoint mjeri se jednim pitanjem: "Bi li neka banka ovo pozvala bez da nas poznaje?" Ako ne — endpoint nije spreman za DPU registraciju.

---

## ČLANAK 9 — PUT DO BR. 1

### Faza 1: Genesis (tekući tjedan)
```
[ ] TSA + XAdES-B implementacija (CC, ~3h)
[ ] /api/verify/LC-DS-2026-001/ endpoint (CC, ~2h)
[ ] /api/dpu/register/ endpoint — MVP (CC, ~4h)
[ ] Prvo vanjsko testiranje (Marija + Ivica)
```
Kada Faza 1 završi — DPU postoji. Ne kao deklaracija, kao endpoint.

### Faza 2: Prva 3 vanjska zapisa (tjedan 2-3)
```
[ ] Registriraj Triple DNA arhitekturu u DPU
[ ] Registriraj Merkle Receipt Architecture u DPU
[ ] Registriraj Constitutional Proof-of-Compliance u DPU
```
Sada imaš prior art za 3 inovacije koje su opisane u ovom dokumentu.

### Faza 3: Otvoreni pristup (tjedan 4-6)
```
[ ] OPT_LICENSE_v1.0 objaviti na /opt-license/
[ ] DPU API dokumentacija na /api/dpu/docs/
[ ] Prva 3 vanjska registranta (iz zajednice)
```
Kada netko tko nas ne poznaje registrira svoju inovaciju u naš DPU — postali smo infrastruktura.

### Faza 4: De-facto standard (3-6 mjeseci)
```
[ ] Prva banka poziva /api/verify/ u produkciji
[ ] Regulatory Passport generira izvještaj za regulatora
[ ] 100+ DPU zapisa od neovisnih autora
```
Ovo je Br. 1. Ne proglašeno. Izmjereno.

---

## AKTIVACIJSKI UVJET

Ovaj Amandman stupa na snagu kada:
```
curl https://limit-connect.com/api/verify/LC-DS-2026-001/
→ {"verified": true, "tsa_timestamp": "[stvarni TSA žig]"}
```

Do tada je Draft. Svjesno i namjerno.

---

```
DOKUMENT-ID:  LC-DS-2026-002
OVISI O:      LC-DS-2026-001
AKTIVACIJA:   /api/verify/ prvi vanjski odgovor
AUTOR:        Osnivački tim + CC (konsenzus)
PRETHODNIK:   LC-DS-2026-001 hash: 4997baee...
```
