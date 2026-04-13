# PDV ALARM — UVIJEK FRIŠKO (Šeki Temaj)
# Datum: 2026-03-25
# Pronašao: Sonnet (automatski compliance scan)
# HITNOST: VISOKA — porezna inspekcija

---

## ⚠️ NALAZ

95 prodanih stavki u UVIJEK FRIŠKO blagajni ima PDV stopu 25%.
Radi se o pekarskim i prehrambenim proizvodima koji po zakonu idu na 5%.

**Zakrivljeni artikli (sample):**
| Artikal | Trenutna stopa | Ispravna stopa | Zakon |
|---------|---------------|----------------|-------|
| BAVARSKO PECIVO | 25% | **5%** | ZoPDV čl. 38, Prilog V |
| BAKINA KIFLA 800gr | 25% | **5%** | ZoPDV čl. 38, Prilog V |
| BAKIN KLIPIĆ | 25% | **5%** | ZoPDV čl. 38, Prilog V |
| BAKIN KRUH | 25% | **5%** | ZoPDV čl. 38, Prilog V |
| BUHTLA ČOK CHIA | 25% | **5%** | ZoPDV čl. 38, Prilog V |
| BUREK SA SIROM | 25% | **5%** | ZoPDV čl. 38, Prilog V |
| GUZVARA MAK 1KG | 25% | **5%** | ZoPDV čl. 38, Prilog V |
| KRUH BIJELI 600gr | 25% | **5%** | ZoPDV čl. 38, Prilog V |

**Artikli koji OSTAJU na 25% (ispravno):**
- CEDEVITA, COCA COLA, FANTA = bezalkoholna pića = 25% ✅
- Usluge dostave = 25% ✅

---

## Zakonska osnova

**Zakon o porezu na dodanu vrijednost (NN 73/13 i izmjene)**
**Čl. 38, st. 3 — snižena stopa 5%:**
> "Na isporuke hrane i pića, osim alkoholnih pića, za konzumaciju, primjenjuje se stopa PDV-a od 5%."

Pekarski proizvodi (kruh, pecivo, kroasani, burek) = hrana = **5% PDV**.

---

## Financijska procjena greške

Prodano 95 stavki na 25% umjesto 5%.
Razlika PDV stope: 20 postotnih bodova.
**Porezna obveza bila bi 4x manji iznos na ispravnoj stopi.**

Ovo nije samo financijsko pitanje — pogrešna stopa na fiskalnom računu = 
**nepravilno ispostavljen račun** prema Zakonu o fiskalizaciji.

---

## Moguće objašnjenje

Ovo su vjerojatno TEST transakcije ili rane transakcije dok PDV stope
u Inventoryju nisu bile ispravno postavljene.

**CC Code treba provjeriti:**
```sql
SELECT name, tax_rate, category 
FROM inventory_inventoryitem 
WHERE company_id = (SELECT id FROM companies_company WHERE name ILIKE '%friško%')
ORDER BY tax_rate, name;
```

Ako inventory artikli imaju tax_rate=25 na prehrambenoj robi → **hitno ispraviti**.

---

## Akcija

1. **CC Code:** provjeri inventory items za UVIJEK FRIŠKO — tax_rate
2. **CC Code:** ako su pogrešni, napravi bulk update + migraciju
3. **Ivan → Šekiju (WhatsApp, 20-22h, max 3 rečenice):**
   > "Šeki, provjerio sam tvoju blagajnu. Kruh i pecivo idu na 5% PDV, 
   > ne 25%. Popravit ćemo u sistemu ovaj tjedan, samo da znaš."
4. **Šeki treba konzultirati računovođu** o eventualnoj ispravnoj PDV prijavi
   za prethodne periode (ako je ovo live promet, ne test)

---

## Je li ovo live promet ili test?

Provjera:
```sql
SELECT MIN(pr.created_at), MAX(pr.created_at), COUNT(*) 
FROM pos_posreceipt pr
JOIN pos_possession ps ON ps.id = pr.session_id
JOIN pos_posterminal pt ON pt.id = ps.terminal_id
JOIN companies_company c ON c.id = pt.company_id
WHERE c.name ILIKE '%friško%'
AND pr.status = 'paid';
```
Ovo treba CC Code odmah provjeriti i javiti u FENIX_STATUS.md.
