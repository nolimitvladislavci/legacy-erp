# POS Simulacija Report — 26.03.2026
# Server: 37.27.248.86 (Hetzner Helsinki)
# Git HEAD: 49011505

## Rezultat


============================================================
  POS SIMULACIJA — BORG CENTAR
============================================================

S1: quick × UVIJEK FRIŠKO (pekara)
  ✅ [S1] Terminal pk=4 | qa: ['scan_barcode', 'add_amount']
  ✅ [S1] Inventura: 521 artikala (s cijenom)
  ✅ [S1] Receipt 1 | total=4.50 EUR | is_training=True
  ✅ [S1] pos_type=quick → signal hookovi NE aktiviraju rental/udrugu (ocekivano)

S2: retail × Konjik (Marija, R1)
  ✅ [S2] Terminal pk=1 | qa: ['scan_barcode', 'add_amount', 'open_modal']
  ✅ [S2] Inventura: 4813 artikala
  ✅ [S2] R1 receipt 1 | is_r1=True | oib=37590751921
  ✅ [S2] Total: 120.62 EUR

S3: retail × KUD Dukat (udruga, membership)
  ✅ [S3] Terminal pk=18 | business_type=udruga
  ✅ [S3] Membership qa: ['membership_scan', 'membership_renew', 'donation']
  ✅ [S3] Receipt 1 | total=20.00 | member=Test Clan
  ✅ [S3] post-receipt hook: evaluate_subscriptions.delay() (udruga pattern)

S4: field × UVIJEK FRIŠKO (teren, GPS, WhatsApp)
  ✅ [S4] Terminal pk=5 | UVIJEK FRIŠKO | qa: ['add_amount', 'add_item', 'gps_location', 'whatsapp_receipt']
  ✅ [S4] Field sesija 4806 | ruta=Ruta Osijek-Cepin
  ✅ [S4] Receipt 1 | total=38.75 EUR
  ✅ [S4] WhatsApp hook: INFO log aktivan (Twilio/Meta API treba za produkciju)

S5: quick × Brunoslav Valiant (0 artikala, brzi iznos)
  ✅ [S5] Inventura: 0 artikala
  ✅ [S5] add_amount dostupan: True
  ✅ [S5] Receipt 1 | total=187.50 EUR
  ✅ [S5] add_amount radi bez inventure (by design)

S6: reception × rental (check-in, eVisitor hook)
  ✅ [S6] Reception terminal pk=49
  ✅ [S6] qa: ['rental_checkin', 'add_item', 'add_item', 'add_item', 'rental_ocr', 'rental_evisitor']
  ✅ [S6] Receipt 1 | total=105.09 EUR
  ✅ [S6] post-receipt hook: check_evisitor_pending DOSTUPAN
  ✅ [S6] pos_type=reception → eVisitor XML trigger aktivan

============================================================
  Rezultat: 25 OK  |  0 WARN  |  0 ERROR
  Kreiranih računa (is_training=True): 66
  Ukupni simulacijski iznos: 6305.59 EUR

  Simulacija zavrsena.

## Scenariji

| # | Tip | Firma | Opis | Status |
|---|-----|-------|------|--------|
| S1 | quick | UVIJEK FRIŠKO | Pekara, brzi iznos | OK |
| S2 | retail | Konjik d.o.o. | R1, OIB kupca | OK |
| S3 | retail | KUD Dukat | Udruga, članarina | OK |
| S4 | field | UVIJEK FRIŠKO | Teren, GPS, WhatsApp | OK |
| S5 | quick | Brunoslav Valiant | 0 artikala, brzi iznos | OK |
| S6 | reception | Konjik (rental) | Check-in, eVisitor | OK |

## Fix primijenjen
- receipt_number: random → sequential per session (PositiveIntegerField safe)
- Svaka sesija počinje od 1

## System check
```
  warnings.warn(
System check identified no issues (0 silenced).
```
