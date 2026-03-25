# LIMIT Connect — Upute za AI agente
*Ažurirano: 2026-03-25 — Sonnet (komunikacijski protokol + arhitektura)*

---

## Server
```
root@37.27.248.86 | /var/www/fina-connect
. venv/bin/activate
systemctl restart gunicorn-fina celery-worker celery-beat
```

---

## ★ KOMUNIKACIJSKI PROTOKOL — OBAVEZNO ČITATI

### Što Ivan traži od Sonneta (i svih agenata):
1. **Skeniraj, pa preporuči** — ne čekaj da te pita. Vidiš problem u modulu → kažeš odmah.
   Primjer: "Skenirao sam invoicing/models.py i uočio X — predlažem Y."
2. **Znaj što je u bazi** — 86 firmi iz Synesis importa POSTOJE. Marija ih zna.
   Nikad ne pitaj "imaš li kontakt listu" — provjeri bazu prvo.
3. **Bez pritiska** — Ivan zna tempo. 26 dana od nastanka. Plan je 01.04.
   Sonnet ne urgira, ne podsjeća na rokove, ne pita "jesi li spreman".
4. **Ideje, ne upozorenja** — umjesto "trebaš riješiti X", kaži "imam ideju za X — evo kako".
5. **Marija je kanal** — 86 firmi ide kroz nju. Ona ih vodi. Naš posao je da njoj sve radi.
6. **Kampanja = Marija + QR + AI letak** — kada Ivan kaže "kampanja za 86 firmi",
   to znači: pripremi materijale za Mariju, ne outreach strategiju.

### Što NE raditi:
- Ne pitati za stvari koje su već u bazi ili FENIX_STATUS.md
- Ne stvarati pritisak oko rokova
- Ne ponavljati iste preporuke iz prethodnih sesija
- Ne pisati dugačke uvode — idi direktno na stvar

---

## Pravila — UVIJEK

1. **Tema:** crna-zlatna (`--black:#0a0a0a`, `--gold:#c9a84c`), fontovi Cormorant Garamond + Barlow
2. **Branding:** "LIMIT Connect" — NE "Fina Connect", NE "ERP"
3. **Slogan:** "Fiskalizacija u džepu"
4. **HTML forme:** native `<label><input type="radio">` — NIKAD JavaScript onclick za selekciju. Mora raditi na mobitelu.
5. **Tenant isolation:** SVAKI query mora imati `company=` filter.
6. **Prije pisanja koda:** pročitaj stvarna polja iz models.py. Ne pretpostavljaj nazive.
7. **Istina uvijek:** nikad prešutjeti problem, bug, rizik ili bolju opciju.
8. **Revolucionarne stvari** proaktivno reći — ne čekati da Ivan pita.

---

## Task fajlovi

- **Naming:** `CC_TASK_OPIS.md` (bez datuma — datum je u sadržaju)
- **Jednokratni:** napiši → agent odradi → obriši
- **Nikad > 10 aktivnih** — prioritiziraj i obriši stare
- **Trajni kontekst** ide u CLAUDE.md ili FENIX_STATUS.md, ne u task fajlove
- **Koordinacijski fajl:** `FENIX_STATUS.md` — čitaj SVAKI TASK. Ako je DONE tamo — NE RADIŠ PONOVO.

---

## Kampanja za 86 firmi (Synesis import) — KONTEKST

**Strategija:** Marija Brtan (Konjik d.o.o.) je centralni kanal.
- 86 firmi iz Synesis importa je njenih klijenata
- Kada Marija počne koristiti arhivu → sve firme slijede
- Materijali koje treba pripremiti (AI zadatak, uskoro):
  - QR kod plakat za ulaz (brzi pristup)
  - Email s QR kodom i promo letkom za firme koje imaju email
  - Personalizirani link po firmi
- **Status:** Čeka da Marija bude sigurna u arhivu i fiskal

**Sinesis firme u bazi:** 86 firmi, 33.270 partnera, 10.206 faktura — UVEZENO 23.03.2026

---

## Arhitektura — ključni moduli

### Cockpit (refaktorizirano 22.03. — commit 8d44bad)
- `core/cockpit_views.py` — sve cockpit funkcije izolirane
- `@cockpit_required()` dekorator u `permissions/decorators.py`

### POS — Centar svijeta (commit 2430991)
- `POSTerminal.quick_actions` (JSONField) + 14 akcija (QUICK_ACTION_REGISTRY)
- QuickActions panel u `quick.html`, 3 post-receipt hooka
- Multi-konobar PIN preuzimanje: `POSCashier` model, `set_pin()`, `check_pin()`

### Arhiva / Smart Import
- `templates/documents/arhiva_list.html` + `scan_batch.html` (5 faza, drag&drop)
- `smart_import/` → Predkomora OCR pipeline
  - `StagingBatch` → `StagingFile` → `StagingFileHeader`

### Invoicing
- `InvoiceItem.section` + `sort_order` — NOVO (CC_TASK_INVOICE_SECTIONS.md u toku)
- VIS-AN-2026-003: Teil 1 Arbeiten 17.782,88 € + Teil 2 Material 6.111,86 €

### Auth
- TOTP (totp_secret/totp_enabled) — postoji, opcija
- DeviceToken (UUID barcode, POS auto-login) — postoji
- UserAPIKey (lc_live_ format) — NOVO (CC_TASK_API_KEY_AUTH.md u toku)

### Hash Chain (commit 73a0701)
- `pos/hashchain.py` → ChainLink, append_receipt(), verify_chain()

### eRačun posrednik
- `CC_TASK_ERACUN_POSREDNIK_F1.md` čeka FINA API key za live test
- Certifikat Konjik: `/etc/limit-connect/certs/` vrijedi do 2030-07-31

---

## Aktivni klijenti

| Klijent | Firma | Moduli | Status |
|---------|-------|--------|--------|
| Seki Temaj | Uvijek Friško | POS (3 lok, 5 term), Pickup QR, Booking | LIVE |
| Marija Brtan | Konjik d.o.o. | Arhiva, eRačun, Invoicing, Konto | LIVE — fiskal 2 + arhiva |
| Nikša Visković | Viskovic Bau | DE market, GoBD, TSE, DSFinV-K | ONBOARDING |
| Dragan Jakovljevic | Viskovic Bau | Partner (Strategie), superadmin | ONBOARDING |
| Slađana Kruljac | O.P.G. Kruljac + Korpaš d.o.o. | Livestock, Vet, Arhiva | LIVE |

### Synesis / Korpa klijenti
- 86 firmi Marijinih klijenata — u bazi od 23.03.2026
- Korpa direktni: Korpaš, KUD Dukat, OPG Kruljac, Furdi obrt, Cizo čišćenje

### Superadmini
| superadmin / antonio.brtan | Platform owner (Ivan Brtan) |
| marija.brtan | Konjik d.o.o. |
| niksa.viskovic | Viskovic Bau |
| dragan.jakovljevic | Viskovic Bau |

---

## Git HEAD (zadnji poznati)
`c76f55a` — POS Simulacija 25/25
