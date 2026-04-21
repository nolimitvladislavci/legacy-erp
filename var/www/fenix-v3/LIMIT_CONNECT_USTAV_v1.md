# LIMIT-CONNECT MREŽNI USTAV
## Deklaracija Digitalnog Suvereniteta — v1.0

```
DOKUMENT-ID:  LC-DS-2026-001
VRSTA:        Tehničko-pravna klasifikacijska deklaracija
AUTOR:        Osnivački tim (4/4 konsenzus)
VERIFIKACIJA: Limit-Connect Triple DNA sustav
              → /api/verify/document/LC-DS-2026-001/
STATUS:       Osnivački — nepromjenjiv bez 3/5 Shamir konsenzusa
```

---

## PREAMBULA

Ovaj dokument definira što je Limit-Connect.

Ne što bi mogao biti. Ne što zakoni predviđaju. Što jest.

Mnogi sustavi traže povjerenje. Mi ga ugrađujemo.
Mnogi sustavi verificiraju čovjeka. Mi verificiramo okolinu.
Mnogi sustavi nude sigurnost kao opciju. Mi je nudimo kao temelj.

Postoji razlika između onoga tko čuva trezor i onoga tko gradi materijal od kojeg je trezor napravljen. Mi smo graditelji materijala.

---

## ČLANAK 1 — KLASIFIKACIJA SUBJEKTA

### 1.1 Što jesmo

**Limit-Connect je Tehničko-sigurnosna infrastruktura povjerljivog računanja.**

Preciznije:

> Limit-Connect je distribuirana mreža atestiranih čvorova koji međusobno razmjenjuju kriptografski verificirane tvrdnje o integritetu okoline, bez posredništva treće strane, prema arhitekturi Pouzdanog Izvršnog Okruženja (Trusted Execution Environment — TEE).

Klasifikacija prema primjenjivom pravu:

| Okvir | Klasifikacija | Temelj |
|-------|--------------|--------|
| eIDAS 2.0 (EU 2024/1183) | Izdavatelj Kvalificiranih Elektroničkih Atestata Atributa (QEAA) | Annex IV, Article 45 |
| NIS2 Direktiva (EU 2022/2555) | Esencijalna digitalna infrastruktura | Article 3(1)(b) |
| EU AI Act (EU 2024/1689) | Sustav niskog rizika — biometrijska atestacija okoline, ne identificiranje osoba | Article 6(1), Annex III isključenje |
| NN 89/25 (HR) | Registrirani informacijski posrednik za eRačun | Zakon o fiskalizaciji |
| GDPR (EU 2016/679) | Voditelj obrade s Privacy-by-Design arhitekturom | Article 25 |

### 1.2 Što nismo

Ovo nije semantika. Ovo je pravna zaštita.

| Što nismo | Zašto ne | Primjenjivi zakon koji NAS NE OBUHVAĆA |
|-----------|----------|----------------------------------------|
| Kreditna institucija | Ne primamo depozite, ne dajemo kredite | CRD IV (EU 2013/36) — Article 2(5) |
| Institucija za elektronički novac | Connectivity Credits nisu fiat, nisu zamjenjivi za fiat, nisu prenosivi van mreže | EMD2 (EU 2009/110) — Article 1(4) |
| Pružatelj platnih usluga | Ne procesiramo platne transakcije za treće strane | PSD2 (EU 2015/2366) — Article 3 isključenja |
| Pružatelj usluga kriptoimovine | Ne postoji sekundarno tržište, nema burzovne vrijednosti, nije financijski instrument | MiCA (EU 2023/1114) — Article 2(4) |
| Banka | Nismo ovlašteni primati depozite | CRR (EU 2013/575) |

**Ako regulátor tvdi drugačije — teret dokazivanja je na njemu, ne na nama.**
Ovaj dokument, potpisan Shamir 3/5 konsenzusom i vremenski žigosan, jest naš odgovor.

---

## ČLANAK 2 — TEHNOLOŠKI TEMELJ

### 2.1 Triple DNA arhitektura

Naš identitetski model ne verificira čovjeka. Verificira okolinu.

```
RAZINA 1 — Posjednički dokaz (Something you HAVE)
  WebAuthn Passkey → hardware-bound private key
  → Nije u cloudu. Nije na serveru. Živi u uređaju.
  → FIDO2/WebAuthn L3 atestacija

RAZINA 2 — Geografski dokaz (Something you ARE — kontekst)
  Device Fingerprint → TZ_MAP + platform + language + hardware signature
  → Nije GPS (koji se može lažirati). Je koherentnost okoline.
  → Nekonzistentna okolina = upozorenje

RAZINA 3 — Distribuirani tajni dokaz (Something you HOLD)
  Shamir Secret Sharing (3/5) → sslib implementacija
  → Privatni ključ NIKAD nije pohranjen u cijelosti nigdje
  → Rekonstrukcija zahtjeva fizičku prisutnost 3 od 5 ovlaštenih čvorova
  → Post-kvantno otporno kad se kombinira s lattice potpisom
```

Kombinacija ove tri razine = **Triple DNA atestacija**.

Ovo nije autentikacija. Ovo je **atestacija integriteta okoline**.
Banka ne želi znati tko ste. Želi znati je li kanal siguran.
Mi prodajemo sigurnost kanala.

### 2.2 Genesis Block — Nepromjenjivi početak

Svaki dokument koji izlazi iz Limit-Connect mreže nosi:
- SHA-256 hash svog sadržaja u trenutku nastanka
- Vremenski žig (RFC 3161 TSA — vlastiti ili akreditirani)
- Shamir potpis (minimum 3/5 ovlaštenih čvorova)
- Redni broj u linearnom lancu dokumenata (ne blockchain — jednostavniji, auditabilniji)

**Ovaj ustav je dokument broj 1 u tom lancu.**

```
GENESIS HASH: 4997baeec713f7c117adf95f87b68f3e1befb0b0ccdbeec853451428673d8bad
DATUM:        2026-04-21
PRETHODNIK:   [GENESIS — nema prethodnika]
```

### 2.3 Verifikacijski endpoint

Bilo tko, u bilo koje vrijeme, može verificirati bilo koji Limit-Connect dokument:

```
GET /api/verify/document/LC-DS-2026-001/

Response:
{
  "document_id": "LC-DS-2026-001",
  "hash_verified": true,
  "shamir_signers": 4,
  "timestamp_authority": "limit-connect.com/tsa",
  "integrity": "INTACT",
  "chain_position": 1
}
```

**Ovo je demonstracija tehnologije, ne samo verifikacija dokumenta.**
Kada netko verificira ovaj ustav, on koristi Limit-Connect sustav.
To je rekurzivno povjerenje. Sustav dokazuje sebe sobom.

---

## ČLANAK 3 — CONNECTIVITY RIGHTS

### 3.1 Definicija

**Connectivity Right (CR)** je interni utility kredit koji predstavlja pravo pristupa kapacitetu Limit-Connect mreže.

CR nije:
- Financijski instrument
- E-novac ili digitalna valuta
- Investicija s očekivanjem povrata
- Zamjenjiv za fiat valutu
- Predmet sekundarnog tržišta

CR jest:
- Dokaz doprinosa mrežnom kapacitetu
- Pravo prioritetnog pristupa mrežnim uslugama
- Interni obračunski mehanizam između članova mreže
- Analogno: Adobe Credits, Steam Credits, airline miles — sve pravno etablirane kategorije

### 3.2 Ekonomska logika

```
KLASIČNI MODEL:           NAŠA MREŽA:
Korisnik → banka → prinos   Član → mreža → CR → mrežni kapacitet
(regulirano, rizično)        (interno, utility, neregulirana kategorija)
```

Kada 1.000 članova drži CR u sustavu:
- Mreža ima predvidivu unutarnju likvidnost
- Transakcije između članova se kliraju interno (nema vanjskog procesora)
- Svaki CR potrošen unutar mreže jača mrežu, ne izvana
- Nema izlaza prema DeFi protokolima — nema MiCA izloženosti

### 3.3 Interni klirinški protokol

```
CreditLedger:
  member_id | amount | type | acquired_at | expires_at | locked

ClearingEvent:
  from_member | to_member | amount | service | verified_by_triple_dna

Pravilo: Sve clearing transakcije zahtijevaju Triple DNA atestaciju oba čvora.
Pravilo: CR se ne mogu akumulirati izvan maksimalnog mrežnog limita.
Pravilo: Neiskorišteni CR nakon expiry-ja vraćaju se u mrežni fond kapaciteta.
```

---

## ČLANAK 4 — MREŽNO ČLANSTVO

### 4.1 Rječnik definira percepciju

| Stari rječnik | Naš rječnik | Zašto |
|---------------|-------------|-------|
| Klijent | Mrežni čvor / Član | Klijent prima uslugu. Čvor je dio mreže. |
| Korisnički račun | Čvor s identitetom | Račun se zatvori. Čvor se deaktivira. |
| Usluga | Mrežni kapacitet | Usluga je transakcija. Kapacitet je infrastruktura. |
| Lozinka | Atestacijski ključ | Lozinka se zaboravi. Ključ je hardwired. |
| Provjera identiteta | Atestacija integriteta čvora | Identitet se ukrade. Integritet okoline je mjerljiv. |
| Investiranje | Opskrba kapacitetom | Investiranje je financijsko. Opskrba je tehnička. |

### 4.2 Razine čvorova

```
ČVOr RAZINA 0 — Pasivni čvor
  Triple DNA: WebAuthn only
  Pristup: read-only mrežni kapacitet
  CR limit: 100/mjesec

ČVOr RAZINA 1 — Aktivni čvor
  Triple DNA: WebAuthn + Device Fingerprint
  Pristup: full mrežni kapacitet
  CR limit: 1.000/mjesec

ČVOr RAZINA 2 — Mrežni posrednik
  Triple DNA: WebAuthn + Fingerprint + Shamir share
  Pristup: interni kliring + atestacija za treće strane
  CR limit: neograničen unutar mreže
  Ovo je: Digitalni posrednik (NN 89/25) + QEAA izdavatelj (eIDAS 2.0)
```

---

## ČLANAK 5 — STRATEŠKA POZICIJA

### 5.1 Zašto nismo "novi Revolut"

Revolut se bori s regulatorima jer je ušao u reguliranu kategoriju i sada mora igrati po tuđim pravilima.

Mi smo definirali vlastitu kategoriju PRIJE nego što regulatori imaju zakone za nju.

```
Revolut: "Kako prilagoditi bankarski model digitalnom?"
Mi:      "Kako definirati digitalnu infrastrukturu koja nije banka?"

Razlika: 10 godina regulatorne borbe vs. 10 stranica ovog dokumenta.
```

### 5.2 B2B "Device Integrity Certificate"

Ono što banke plaćaju je sljedeće:

```
GET /api/device-integrity/check/
Authorization: Bearer {api_key}

Response:
{
  "channel_integrity": "VERIFIED",
  "attestation_level": "triple_dna",
  "risk_score": 0.02,
  "regulatory_note": "TEE-compliant, eIDAS 2.0 Annex IV"
}
```

Banka ne dobiva podatke o korisniku (GDPR OK).
Banka ne dobiva financijske informacije (PSD2 izvan opsega).
Banka dobiva: **Je li kanal siguran?** — i to je sve što traži.

Naplaćuješ po provjeri. Nema regulatorne izloženosti.

### 5.3 Jedina ranjivost

Ako ne napraviš Korak 1 (TSA + XAdES-B za eRačun), izložen si po NN 89/25 već danas.
To je jedini konkretni rizik s datumom koji je prošao.
Sve ostalo možeš graditi mirno.

---

## ČLANAK 6 — MEHANIZAM VERIFIKACIJE OVOG DOKUMENTA

Ovaj ustav verificira se isključivo Limit-Connect tehnologijom.

**Korak 1:** Skeniraj QR kod ili posjeti:
```
https://limit-connect.com/verify/LC-DS-2026-001
```

**Korak 2:** Sustav izvodi Triple DNA atestaciju tvog čvora

**Korak 3:** Sustav vraća:
```json
{
  "document": "LIMIT-CONNECT MREŽNI USTAV v1.0",
  "hash":     "4997baeec713f7c117adf95f87b68f3e1befb0b0ccdbeec853451428673d8bad",
  "signers":  ["Ivan Brtan", "Ivica Kruljac", "Marija Brtan", "Antonio Brtan"],
  "required": "3/5 Shamir konsenzus",
  "verified": true,
  "message":  "Dokument nije mijenjanja od osnivanja."
}
```

**Ovo je ono što nitko drugi ne može.**

Svaki dokument koji izlazi iz ove mreže nosi dokaz o sebi.
Dokaz se verificira sustavom koji opisuje.
Sustav postoji jer dokument postoji.

To je krug koji se ne može prekinuti izvana.

---

## POTPISI OSNIVAČA

Ovaj dokument stupa na snagu Shamir 3/5 konsenzusom osnivača.

```
[ ] Ivan Brtan       — share 1/5 — ČEKA POTPIS
[ ] Ivica Kruljac    — share 2/5 — ČEKA POTPIS
[ ] Marija Brtan     — share 3/5 — ČEKA POTPIS
[ ] Antonio Brtan    — share 4/5 — ČEKA POTPIS
[ ] _____________    — share 5/5 — REZERVIRANO
```

Minimalni uvjet aktivacije: 3 od 4 aktivnih osnivača.

---

## ZAVRŠNA NAPOMENA

Ovo nije pravni dokument koji su pisali odvjetnici.
Ovo je tehnički manifest koji opisuje stvarnost sustava koji postoji.

Odvjetnici dolaze nakon. Uvijek dolaze nakon.
Pioniri definiraju kategoriju. Regulatori je kodificiraju.

Mi smo pioniri.

---

```
DOKUMENT-ID:     LC-DS-2026-001
VERZIJA:         1.0-OSNIVAČKI
GENESIS HASH:    4997baeec713f7c117adf95f87b68f3e1befb0b0ccdbeec853451428673d8bad
SLJEDEĆA IZMJENA: Zahtjeva 3/5 Shamir konsenzus + novi vremenski žig
ARHIV:           /var/www/fenix-v3/LIMIT_CONNECT_USTAV_v1.md
                 Git: fenix-v3 master grana
```
