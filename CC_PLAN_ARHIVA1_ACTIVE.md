# ARHIVA-1 MOBILE SCAN — AKTIVNO
**Executor: CC Opus | Start: 2026-04-14 | Status: 🔄 U TIJEKU**

## REDOSLIJED
- [x] A-1.1 ScanToken model + migracija ✅ (postojeće, migration 0024)
- [x] A-1.2 View /scan/{token}/ (GET + POST) ✅ views_scan.py rewrite
- [x] A-1.3 URL routing + RouteRegistry PUBLIC ✅ (fix: path->str, oba route names)
- [x] A-1.4 Mobile UI template ✅ (zlatni gumb, ime firme, direktan feedback)
- [ ] A-1.5 Token generator u umbrella panelu ⏳ SLJEDEĆE
- [x] A-1.6 9 pytest testova ✅ 9/9 passed
- [ ] A-1.7 Commit + FENIX_STATUS update ⏳

## NAPREDAK
| Vrijeme | Korak | Status |
|---------|-------|--------|
| START   | Čitam models/views/urls | ✅ |
| +10min  | ScanToken model već postoji, views_scan.py rewrite | ✅ |
| +20min  | RouteRegistry fix, template novi UX | ✅ |
| +30min  | core/urls.py fix (path->str), 9/9 testovi | ✅ |
| +35min  | Commit 9a705286, gunicorn reload | ✅ |
| +40min  | LIVE test token za Konjik — 200 OK | ✅ |

## LIVE TEST TOKEN
```
URL: https://limit-connect.com/hr/scan/405dfc43-074f-429a-a0a7-5e965f26e04b/
Firma: Konjik d.o.o.
Label: Test ARHIVA-1 — Gasic Ivan gorivo
Status: LIVE ✅ (HTTP 200)
```

## ŠTO OSTAJE
- A-1.5: Token generator UI u umbrella dashboard panelu
  - Forma: dropdown komitenti, label, expiry
  - QR kod prikaz
  - WhatsApp share gumb
  - Lista aktivnih tokena
