# PRODAJNI SCENARIJI — fina-connect (bez Memio grupe)
# Kreirano: 2026-04-27 | Sudačka odluka Claude

## MEMIO GRUPA SE NE PRODAJE
Ostaje u vlasništvu Udruge — garantira sigurnost podataka + EU fondovi u oba smjera.

## PREPORUČENI SCENARIJ: S-3

| Sc. | Naziv | Što se prodaje | Ciljani kupac | Okvir € | Kompleksnost |
|-----|-------|---------------|--------------|---------|--------------|
| S-1 | Cijeli core ERP | fina-connect bez Memio | Veći ERP vendor (HR/DE) | €80k–€200k | Visoka — 3–6 mj. |
| S-2 | evalidator.eu | PEPPOL+UBL+XRechnung standalone | EU fintech startup | €20k–€60k | Niska — odmah |
| **S-3** | **evalidator + stolarija** | **S-2 + carpentry vertical** | **Industrijski softver HR/DE/AT** | **€35k–€80k** | **Srednja** |
| S-4 | Udruge vertikali | Lovci, vatrogasci, pčelari (ne NGO core) | Govtech, sportski savezi | €12k–€30k | Srednja |
| S-5 | smart_import bundle | AI OCR pipeline + worktime/sati.ink | HR software vendor, fintech | €15k–€35k | Srednja |

## Zašto S-3?
evalidator.eu je odmah odvojiv (vlastita domena, minimalne veze s core ERP-om).
stolarija je rijedak industry vertical (HR/DE/AT tržište za prozore/fasade).
Zajedno daju €35k–€80k brzo, bez diranja core ERP-a koji čeka strpljivijeg kupca.

## PLAN-07: evalidator.eu prodajna priprema
Status: ČEKA POTVRDU SCENARIJA
Trajanje: 2 dana
Zadaci:
- README s arch dijagramom
- OpenAPI spec za evalidator API
- Standalone Docker Compose za demo
- Cijena: listing na Acquire.com / Flippa + direktni kontakt EU fintech-ima

## PLAN-05: Udruge vertikali extract (za S-4)
Status: ČEKA ODLUKU
Trajanje: 3–5 dana
Zadaci:
- Izdvojiti LovackaIskaznica, VatrogasnaOprema/Vozilo/Intervencija, NatjecanjeRezultat
- Standalone Django app, odvojena migracija
- README za kupca

## PLAN-06: smart_import hardening (za S-5)
Status: ČEKA ODLUKU
Trajanje: 2–3 dana
Zadaci:
- OpenAPI dokumentacija OCR pipeline-a
- Unit testovi za OCR+AI staging
- Odvojiti od companies tenanta gdje moguće
