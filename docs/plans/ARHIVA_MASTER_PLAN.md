# ARHIVA + GLOBAL ERROR — MASTER PLAN
## "Marija testira danas" — Sprint plan

**Datum:** 2026-03-24  
**Deadline:** Danas do kraja dana  
**Kontekst:** CC Code je postavio skeleton — backend postoji, frontend ne postoji.

---

## ŠTO POSTOJI (backend gotov)

```
✅ ScanBatch model + migracije
✅ ScanBatchImage model
✅ 6 URL endpointa (new/upload/process/status/archive/detail)
✅ Celery task process_scan_batch (OCR skeleton)
✅ conversion_service.py — Gemini 2.5-Flash ekstrakcija
✅ ArhivaEntry model — 8.287 dokumenata Konjik
✅ arhiva_list view — kompletan s filterima, stats, bookmarks
✅ generate_ai_proposal Celery task
```

## ŠTO NEDOSTAJE (frontend + AI pipeline)

```
❌ scan_batch.html template — UI ne postoji (samo index.html stub)
❌ arhiva_list.html template — ne postoji
❌ Gemini rate limiter (10 slika/min)  
❌ Haiku multi-page grouper
❌ Global Error Middleware — CC Code napravio /tmp/, nije deployano
❌ 500.html / 404.html template
```

---

## 4 MISIJE — PARALELNO

| Agent | Misija | Fajl |
|-------|--------|------|
| CC Code | Global Error Handler deploy + arhiva_list.html | CC_TASK_ARHIVA_F1.md |
| Gemini | Rate-limited AI pipeline (10/min) + multi-page grouper | GEMINI_TASK_ARHIVA_F2.md |
| Sonnet | scan_batch.html UI (2 tipke filozofija) | SONNET_TASK_ARHIVA_F3.md |
| Ivan | Marija onboarding + feedback loop | IVAN_TASK_ARHIVA_F4.md |

---

## GEMINI RATE LIMITS — STVARNOST

Gemini 2.5-Flash rate limits (Free/Paid tier):
- **Free:** 10 req/min, 500 req/day
- **Pay-as-you-go:** 1.000 req/min
- **Naša pretpostavka:** 10 slika/min je konzervativno za free tier

Za 100 slika → 10 minuta procesiranja.  
Rješenje: Celery chord — grupe od 10, pauza 60s između grupe.  
Korisnik vidi live progress bar. Nije čekanje — to je "AI radi za tebe".

---

## ARHITEKTURA PIPELINE-A

```
Korisnik slika/uploadira
         │
    [Client-side]
    Canvas.toBlob WebP compression
    max 800px, quality 0.75
    (~150KB po slici umjesto 3MB)
         │
    [scan_batch_upload view]
    Prima slike, sprema u ScanBatchImage
         │
    [Celery: haiku_classify_image]  ← odmah, svaka slika
    Brzo: je li to račun? koliko stranica?
    Output: is_invoice, page_type, needs_grouping
         │
    [Celery chord: gemini_extract_batch]  ← 10 slika/min
    Gemini 2.5-Flash Vision
    Output: full JSON (dobavljač, iznos, stavke, OIB...)
         │
    [Celery: haiku_group_multipage]  ← nakon svih slika
    Haiku grupira višestranične dokumente
    Output: [0,0,1,2,2,2,3] = 4 dokumenta
         │
    [scan_batch_archive view]
    Kreira ArhivaEntry za svaki prepoznati dokument
    IntegrityHash, partner auto-creation
         │
    Marija vidi u arhivi odmah
```
