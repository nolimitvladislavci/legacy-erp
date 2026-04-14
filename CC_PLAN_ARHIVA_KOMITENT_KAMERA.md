# PLAN: Arhiva × Komitent × Kamera — 10/10

**Status**: U TIJEKU
**Datum**: 2026-04-14

---

## DIJAGNOZA

### Problem 1: "Arhiva se izgubi kad se otvori"
- Bottom toolbar link: `{% url 'documents:arhiva_list' %}` — BEZ company parametra
- `arhiva_list` koristi `get_user_company(request)` → ISPRAVNO vraća Agrovladislavci kad je umbrella_as_company aktivan
- ALI: header u arhivi kaže `{{ request.company.name }}` — ne pokazuje jasno koji je komitent
- Problem: arhiva Agrovladislavci je PRAZNA jer nema još dokumenata → korisnik misli da je "izgubljena"
- FIX: jasni breadcrumb "Konjik → Agrovladislavci → Arhiva" + empty state poruka

### Problem 2: "Ne radi dugme Slikaj kamerom"
- "Skeniraj račune" → `scan_batch_new` → kreiraj ScanBatch(company=get_user_company) → redirect scan_batch_detail
- scan_batch.html: `<input type="file" capture="environment" multiple hidden>`
- Camera button je `<label for="cam">` koji trigera hidden file input
- Mogući razlozi zašto ne radi:
  a) Nije HTTPS (getUserMedia zahtijeva HTTPS) — ali limit-connect.com JE HTTPS ✅
  b) iOS Safari ne podržava `multiple` + `capture` zajedno — MOŽDA ❓
  c) JavaScript error prije nego dođe do uploada
  d) scan_batch_upload endpoint failira tiho

### Problem 3: Modul "skuplja prašinu"
- scan_batch postoji, ima AI OCR analizu, ali:
  - Nema jasnu vezu s komitentom iz umbrella konteksta
  - Nema direct-to-archive flow (slika → odmah u arhivu bez batch koraka)
  - UX je previše koraka: klik → batch → upload → analyze → archive
  - Treba: JEDAN KLIK → kamera → slika → gotovo

## RJEŠENJE

### Faza 1: Arhiva × Komitent kontekst
1. Breadcrumb u arhivi: "Konjik → [Workspace] → Agrovladislavci → Arhiva"
2. Empty state: "Agrovladislavci nema još dokumenata. Skenirajte prvi račun!"
3. Prominent client name u header arhive

### Faza 2: Instant Scan (1-Click Camera)
INOVACIJA: Umjesto batch flow-a (5 koraka), napraviti:
- Jedan gumb "📸 Slikaj račun" → otvori kameru → slika se ODMAH uploada u arhivu
- AI OCR automatski u pozadini (partner, iznos, datum)
- Bez batch koraka, bez čekanja

### Faza 3: Camera fix
- Ukloniti `multiple` s `capture` inputa (iOS bug)
- Dodati fallback JavaScript getUserMedia
- Toast notification kad upload uspije/ne uspije
