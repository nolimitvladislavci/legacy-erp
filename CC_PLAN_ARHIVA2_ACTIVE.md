# ARHIVA-2 MAGIC LINK — AKTIVNO
**Executor: CC Opus | Start: 2026-04-14 | Status: 🔄 U TIJEKU**

## CILJ
Komitent (umbrella child company) dobije link → vidi svoju digitalnu arhivu.
Bez logina. Bez registracije. Welcome page + ZOR 11 godina info.

## PRISTUP
- ArhivaAccessToken model (company FK, UUID token, expiry, created_by)
- /arhiva-portal/{token}/ — read-only pristup arhivi za tu firmu
- Welcome page: ime firme, broj dokumenata, ZOR info
- Bulk generator u umbrella panelu (uz scan tokene)
- WhatsApp share gumb

## REDOSLIJED
- [ ] A-2.1 ArhivaAccessToken model + migracija
- [ ] A-2.2 /arhiva-portal/{token}/ view + template
- [ ] A-2.3 URL routing + RouteRegistry PUBLIC
- [ ] A-2.4 Bulk generator u umbrella panelu
- [ ] A-2.5 Testovi
- [ ] A-2.6 Commit + FENIX_STATUS update

## NAPREDAK
| Vrijeme | Korak | Status |
|---------|-------|--------|
| START   | Čitam postojeći kod | 🔄 |
