# HAIKU_TASK — REAL-TIME KLASIFIKATOR (uvijek živ)
# Agent: Claude Haiku 3.5
# Uloga: Reflexni sloj BORG FENIX sustava
# Datum: 2026-03-23

## PRINCIP
Haiku je nervni sustav. Reagira brzo, jeftino, uvijek.
Nikad ne odlučuje — klasificira, sortira, filtrira.
Sve teže proslijedi Sonnetu ili Geminiju.

## STALNI ZADACI (webhook/Celery trigger)

### 1. Klasifikacija uploadane slike
Input: base64 slika
Output JSON:
{
  "is_invoice": true/false,
  "confidence": 0.95,
  "vendor_hint": "Lidl",
  "date_hint": "2026-03-15",
  "amount_hint": "142.80",
  "currency": "EUR",
  "page_type": "first" | "continuation" | "summary" | "unknown",
  "needs_grouping_with_previous": true/false
}

### 2. Multi-page grouping (ovo je naš ključni feature)
Input: niz slika iz batch sesije
Logika:
- Gledaj: isti zaglavlje/logo = isti dokument
- Gledaj: "Seite 1/3", "Stranica 2 od 3" = višestranični
- Gledaj: kontinuitet stavki (artikli se nastavljaju)
- Gledaj: "Fortsetzung", "Nastavak", "continued"
Output: grupiranje [0,0,1,1,1,2,3,3] = 4 dokumenta, 3.+4.+5. slika = isti

### 3. OCR post-processing
Input: raw OCR text
Output: strukturirani podaci
{
  "vendor_name": "...",
  "vendor_vat": "...",
  "invoice_number": "...",
  "invoice_date": "...",
  "due_date": "...",
  "net_amount": 0.0,
  "vat_amount": 0.0,
  "gross_amount": 0.0,
  "vat_rate": 19,
  "line_items": [],
  "payment_method": "...",
  "iban": "..."
}

### 4. Compliance quick-check
Input: extracted_data JSON
Vraća: ["⚠ Nedostaje VAT broj dobavljača", "⚠ Datum >2 godine, archivierungspflicht"]

## INTEGRACIJA
- Celery task: haiku_classify_image(image_path, batch_id, image_order)
- Poziva se za svaku sliku odmah nakon uploada
- Rezultat ide u ScanBatchImage.extracted_data

## TROŠKOVNI LIMIT
Haiku je jeftin ali nije besplatan.
Max 500 tokena input + 200 output po slici.
Ako batch ima 100 slika = max 70.000 tokena ≈ $0.05
Prihvatljivo.

## DONE KRITERIJ
- [ ] haiku_classify_image Celery task funkcionira
- [ ] multi-page grouping accuracy >85% na testnim računima
- [ ] OCR post-processing popunjava sve ključne polje
- [ ] Integriran u ScanBatch workflow
