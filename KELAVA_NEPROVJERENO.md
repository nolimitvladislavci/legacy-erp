# KELAVA — NEPROVJERENI REZULTATI (za provjeru)
Sastavljeno 2026-10-15 (sesija `session_01P5KN18DaRqxRrryzpCv9CK`). Ništa ovdje nije potvrđeno kao činjenica.

## 1. Što je na EU u bazi `otpad_kelava` pod izvorom „NEPROVJERENO: internet (eBay oglasi, pretraga 15.10.2026)"
Svi su u zasebnom dijelu „Instrument ploča – srodne varijante (NEPROVJERENO, nisu zamjena)" (dio_id 296). NISU zamjena za 6Q0 920 842 C.
| Broj | Vrsta | Što je tvrdio rezultat pretrage (sažetak pretraživača, ne moj nalaz) |
|---|---|---|
| 6Q0 920 822 | katalog VW | brzinomjer Polo 9N 1.2, napomena o zamjeni dijela |
| 6Q0 920 822 A | katalog VW | analogni, Polo 9N1; usporedni broj 110080125041 |
| 6Q0 920 822 L | katalog VW | s pozadinskim osvjetljenjem, analogni + digitalni zaslon |
| 6Q0 920 802 C | katalog VW | dizel, 1.4 TDI |
| 6Q0 920 800 P | katalog VW | benzin, 1.2 12V, šifra motora AZQ |
| 6Q0 920 801 M | katalog VW | dizel, 1.4 i 1.9 TDI |
| 110 080 125 041 | VDO | usporedni broj uz 6Q0 920 822 A |

## 2. Odakle (izvorni rezultati pretrage, redom kako su vraćeni; preslikavanje broj ↔ oglas NIJE poznato)
Upit: `VW Polo 9N instrument cluster part number 6Q0 920 8 list compatible 6Q0920842C 6Q0920802 6Q0920822`
- https://www.ebay.de/itm/175280275439
- https://www.ebay.de/p/1141942011
- https://www.ebay.de/p/1117091817
- https://www.ebay.de/p/12053146664
- https://www.ebay.de/p/8044493853
- https://www.ebay.de/itm/405977003140
- https://www.ebay.de/itm/405441707046
- https://www.ebay.de/p/1934267533
- https://www.ebay.de/p/21027067028
- https://www.ebay.de/p/9037581029
Pretraga NIJE našla nijedan izvor koji navodi 6Q0 920 842 C ni potvrdu da je 6Q0 920 802 C dio Polo 9N.

## 3. Što je s fotografija (Ivanove slike sata), čitano po dva pogleda
`VW 6Q0 920 842 C B41`, VDO, VD4, `110.080.126/027`, Made in CZ. Upisano u bazu kao OEM, izvor „Unos radnice" (nije neprovjereno iz interneta, ali nije potvrđeno ni katalogom). Veza na Polo Mk4 (9N) i Facelift samo prema prefiksu 6Q0. Drugi redak naljepnice „VWZ…C8440669" nečitljiv, NIJE upisan.

## 4. Kako provjeriti i ispraviti
```
-- svi neprovjereni brojevi
SELECT b.broj, b.vrsta, d.naziv_hr FROM dio_broj b JOIN dio d ON d.id=b.dio_id JOIN izvor s ON s.id=b.izvor_id WHERE s.naziv LIKE 'NEPROVJERENO:%';
-- potvrđen broj: promijeni izvor (npr. na 'Unos radnice' ili katalog), pogrešan: DELETE
-- provjera pravila: trazi_broj('6q0920842c') ne smije vratiti NEPROVJERENO broj
```
Provjeriti na: oznaci dijela (fotografija naljepnice), kataloga proizvođača (ETKA/ElsaWin ili TecDoc uz licencu), ili kupcu koji je ugradio.
