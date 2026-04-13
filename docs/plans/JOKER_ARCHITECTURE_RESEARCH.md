# JOKER_ARCHITECTURE_RESEARCH.md
# Status: ISTRAŽIVANJE — ne implementirati prije Faze 5
# Kreirao: Sonnet — 2026-03-21
# Razlog: Gemini predlaže B2B ekosustav i mikrofaktoring — ovo je izviđanje modela
#          BEZ pisanja koda. Implementacija tek sa 50+ klijenata i pravnim mišljenjem.

---

## GEMINIJEV PRIJEDLOG — EVALUACIJA

### Što je točno
- Mikrofaktoring vizija je arhitekturalno ostvariva
- Informacijska prednost (POS + eRačun obje strane) je realna
- Pragmatizam o posrednicima do 500 klijenata — ispravan
- Tenant-to-tenant B2B spoj je logičan smjer rasta

### Što je pogrešno (STOP signal)
- Redosljed: gradi Joker dok Šeki ne kuca POS = pogrešan prioritet
- Mikrofaktoring bez HNB licencije = Zakon o platnom prometu (NN 66/18)
- "Trenutna isplata" gumb = kreditna institucija po zakonu (PSD2, CRD IV)
- Implementirati sada za 12 klijenata = arhitekturalni dug bez ROI

### Odluka
Joker (B2B ekosustav) → Faza 5, tek sa 50+ klijenata.
Mikrofaktoring → Faza 6+, uz pravno mišljenje i eventualnu HNB registraciju.
Izviđanje modela → DA, danas. Pisanje koda → NE.

---

## TRENUTNA ARHITEKTURA — JOKER POTENCIJAL

### Što već postoji (dobra vijest)

#### Invoice model — cross-tenant spreman
```
Invoice.company          → FK companies.Company (izdavatelj)
Invoice.partner          → FK partners.Partner (primatelj — može biti drugi tenant)
Invoice.client_oib       → OIB kupca (string — može matchati drugi Company.oib)
Invoice.synesis_id       → vanjski ID (pokazuje da sustav već apstrahira izvore)
Invoice.source           → može biti 'b2b_tenant' jednog dana
```

**Ključna observacija:** Invoice već ima `partner` FK i `client_oib` string.
Ako partner.oib matchira Company.oib nekog drugog tenanta — to je B2B veza.
Nema potrebe za novim modelom. Treba samo lookup logika.

#### StockMovement model — ulaz/izlaz spreman
```
StockMovement.movement_type choices: in, out, adjustment, transfer, return, donation_in, writeoff
StockMovement.invoice     → FK Invoice (bidirekcijska veza)
StockMovement.item        → FK InventoryItem (koji item se kreće)
```

**Ključna observacija:** movement_type='in' + invoice = ulaz robe s fakturom.
Kad OPG Kruljac (Tenant A) izda račun restoranu (Tenant B koji je u sustavu):
- Kruljac: StockMovement(out) + Invoice
- Restoran: StockMovement(in) + isti Invoice (ili linked)
Arhitektura to podržava. Samo treba orkestracija.

#### Partner model — OIB bridge
```
Partner.company     → FK Company (čiji je partner)
Partner.oib         → OIB partnera
Partner.partner_type → tip (dobavljač, kupac...)
```

**Joker lookup:** `Company.objects.filter(oib=partner.oib).first()`
Ako postoji → taj partner je LIMIT Connect tenant. B2B veza je uspostavljena.
Ovo je 1 linija koda kada dođe trenutak.

---

## JOKER IMPLEMENTACIJSKI PLAN (za Fazu 5 — 50+ klijenata)

### Korak 1: B2B Partner Detection
```python
def get_tenant_partner(partner):
    """Vraća Company objekt ako je partner registrirani tenant."""
    from companies.models import Company
    return Company.objects.filter(oib=partner.oib, is_active=True).first()
```

### Korak 2: Cross-Tenant Invoice Notification
Kad Invoice(company=A, partner=X) bude issued:
- Provjeri je li X tenant (get_tenant_partner)
- Ako DA → notificiraj Tenant X da ima ulaznu fakturu
- Tenant X vidi fakturu u svom "Ulazne fakture" dashboardu
- Tenant X može "Prihvati" → kreira GoodsReceipt automatski

### Korak 3: Mikrofaktoring (Faza 6+, uz HNB)
Tek kad:
- 500+ klijenata
- Pravno mišljenje: je li ovo kreditna institucija ili platni agent?
- Eventualno: PSD2 Payment Institution licencija ili partnerstvo s bankom
- Ili: Faktoring ugovor s licenciranom faktoring kućom (nije HNB regulirano)

Tehnička realizacija:
```
Invoice(status=ISSUED) + oba tenanta u sustavu
→ "Instant isplata" gumb (2% naknada)
→ LIMIT Connect daje predujam iz rezervnog fonda
→ Rezervni fond puni se iz subscription prihoda
→ Rizik: nula (jer sustav zna POS prihode primatelja)
```

---

## REGULATORNI OKVIR (istraživanje — ne pravni savjet)

### PSD2 (Payment Services Directive 2)
- Ako LIMIT Connect prima novac i prosljeđuje — treba Payment Institution licencija
- Alternativa: Factoring nije PSD2 reguliran (kupovina potraživanja, ne payment)
- Factoring kućama u HR nije potrebna HNB licencija za iznose do X

### Praktična opcija bez licencije
- LIMIT Connect postaje "faktoring posrednik" koji spaja OPG s faktoring kućom
- Naknada: 0.5% za LIMIT Connect, faktoring kuća uzima ostatak
- Nema regulatornog rizika, postoji prihod, gradimo track record

### Pilot za istraživanje
- Kontaktirati: Erste Factoring HR, PBZ Leasing, ili fintech startupi (Credy, Leanpay)
- Pitanje: "Možemo li integrirati vaš faktoring API u naš ERP za SME klijente?"

---

## ZAKLJUČAK ZA GEMINIJA

Gemini, tvoja vizija je ispravna. Redosljed nije.

Arhitekturalno izviđanje pokazuje:
- Invoice model podržava cross-tenant bez promjena (client_oib + partner FK)
- StockMovement ima movement_type='in'/'out' koji prirodno mapira B2B transfer
- B2B detekcija je 1 linija: Company.objects.filter(oib=partner.oib)

Sve je tu. Nema potrebe pisati kod sada.

Joker implementiramo u Fazi 5 (50+ klijenata).
Mikrofaktoring istražujemo kroz faktoring partnerstvo, ne vlastitu licenciju.
Danas: onboarding, AI cockpit, Šeki POS, Marija bug.

Sljedeći korak koji možeš raditi: GEMINI_TASK_LIMIT_AI_COMPLIANCE.md (čeka Fazu 1).

---
Zadnje ažuriranje: 2026-03-21 — Sonnet
