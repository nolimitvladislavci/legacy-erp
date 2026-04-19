# FENIX V3 STATUS — AI-Native ERP · EU #1
Zadnje ažuriranje: 2026-04-19 (test sprint kompletiran)

## SPRINT NAPREDAK

| Sprint | Blokovi | Status |
|--------|---------|--------|
| Sprint 0 | Blok 0 (Temelj) + Blok 1 (Auth) | ✅ DONE |
| Sprint 1 | Blok 3 (Fakture) + Blok 4 (Arhiva) | ✅ DONE |
| Sprint 2 | Blok 2 (Računovodstvo) + Blok 5 (POS) | ✅ DONE |
| Sprint 3 | Blok 9 (AI) + Blok 11 (WhatsApp) | ✅ DONE |
| Sprint 4 | Blok 6 (Zaposlenici) + Blok 7 (Legal) | ✅ DONE |
| Sprint 5 | Blok 8.1-8.8 (Sve vertikale) | ✅ DONE |
| Sprint 6 | Blok 10 (DE + PEPPOL) | ✅ DONE |
| Sprint 7 | Blok 12 (SaaS Platform) | ✅ DONE |
| Sprint 8 | Testiranje + Templates + Production | 🔄 IN PROGRESS |

## TEST SUITE — 68/68 ZELENO ✅

**test_master_5000users.py** — 5000-user simulation, 4 dimenzije:

| Dimenzija | Testovi | Rezultat |
|-----------|---------|---------|
| D1 — Logički (modeli, validacije, business logika) | 33 | ✅ 33/33 |
| D2 — Tehnički (DB integritet, ImageField, Celery, URL routing) | 13 | ✅ 13/13 |
| D3 — Sigurnost (tenant izolacija, API ključevi, GDPR, HTTP) | 12 | ✅ 12/12 |
| D4 — Skalabilnost (5000 bulk, 50 concurrent, N+1, benchmark) | 10 | ✅ 10/10 |
| **UKUPNO** | **68** | **✅ 68/68** |

**Bandit security scan**: 0 issues (saas, notifications, country_plugins, shelter, booking, construction, hospitality, retail, agriculture)

**Bugovi otkriveni i popravljeni testiranjem:**
- `TenantView` import: `core.base_view` (ne `core.views`)
- `APIKey.key_prefix` max_length: 10 → 16 (migration 0002)
- `CompanySubscription` kwargs: plan_name/days_left ne postoje
- `bulk_create` preskače `save()` → booking_code treba eksplicitno
- GDPR unsubscribe URL: `/pub/odjava/{token}/` (ne `/odjava/`)

## IMPLEMENTIRANI MODULI

### Core Platform (Blok 0-5)
- ✅ AuditChain (SHA-256), Domain Gate, DeepSeek Patrol
- ✅ 4-Layer Auth, Umbrella Komitenti, BillingMiddleware
- ✅ Trial banner (HTMX dismiss), Upgrade flow
- ✅ AI Računovodstvo (Haiku konto prijedlog), RRIF+SKR03/SKR04
- ✅ Fakture HR+DE+EU, PDF IBAN/BIC/payment_terms
- ✅ FenixScan OCR, Arhiva, eValidacija Pečat
- ✅ POS offline PWA, HR Fiskalizacija

### Zaposlenici + Legal (Blok 6-7)
- ✅ DataVault šifriranje HR podataka, TimeLogRevision, Compliance
- ✅ Legal: ContractTemplate, Contract (SHA-256), PowerOfAttorney
- ✅ Dispute: AI risk_score 0-100, DisputeEvent audit trail

### 8 Vertikala (Blok 8)
- ✅ Blok 8.1: Stolarija (WindowProfile, MeasurementSession, WindowOffer, BOMItem, InstallationOrder)
- ✅ Blok 8.2: Udruge (AssociationType, Association, Member, MembershipFee, feature flags)
- ✅ Blok 8.3: Azil (Animal, VeterinaryVisit, AdoptionRequest, FosterFamily)
- ✅ Blok 8.4: Termini (Service, Staff, WorkingHours, Appointment, BlockedSlot)
- ✅ Blok 8.5: Baustela (ConstructionSite, WorkLog, MaterialEntry, ProgressReport)
- ✅ Blok 8.6: Hotel (RoomType, Room, Guest, Reservation, HousekeepingLog)
- ✅ Blok 8.7: Maloprodaja (ProductCategory, Product, StockMovement, RetailSale, SaleItem)
- ✅ Blok 8.8: OPG (Field, Crop, FieldActivity, LivestockHerd)

### Country Plugins (Blok 10)
- ✅ CountryConfig per-company/country (HR/DE/AT/SI)
- ✅ HRPlugin: OIB Luhn validacija, HR faktura format
- ✅ DEPlugin: Steuernummer validacija, DATEV EXTF header
- ✅ ATPlugin: UID validacija, Umsatzsteuer
- ✅ SIPlugin: Davčna številka check digit
- ✅ PEPPOLDocument (BIS 3.0 tracking, outbound/inbound)
- ✅ DSFinVKExport (DE TSE, transaction audit)

### Notifications (Blok 11)
- ✅ NotificationTemplate (WhatsApp/Email/Push/SMS, {{variables}})
- ✅ ContactList + ContactSubscriber (GDPR: opt-in, opt-out, unsubscribe_token)
- ✅ NotificationCampaign (broadcast fan-out, statistika)
- ✅ NotificationMessage (per-message log, status tracking)
- ✅ Celery: send_whatsapp_message (WAHA API), send_campaign (async)
- ✅ Public GDPR unsubscribe URL (/pub/odjava/<token>/)

### SaaS Platform (Blok 12)
- ✅ 12.1: UsageEvent + UsageSummary (Celery nightly aggregation)
- ✅ 12.2: TenantInvite (secure token, 7-day expiry)
- ✅ 12.4: CompanyBranding (White-Label: logo/colors/domain/email)
- ✅ 12.5: PartnerProfile + PartnerClientLink (commission 10%, client_limit 50)
- ✅ 12.6: StripeCustomer, StripeSubscription, StripeWebhookEvent (idempotent)
- ✅ 12.7: APIKey (SHA-256 hash, rate limit), APIUsageLog, MarketplaceListing
- ✅ Sidebar: sve vertikale + platforma linkovi

## BAZA PODATAKA
- 50+ tablica u fenix_v3_clean
- Apps: core, accounts, companies, invoicing, arhiva, pos, stolarija,
        accounting, ai_cockpit, employees, sentinel, legal, associations,
        shelter, booking, construction, hospitality, retail, agriculture,
        country_plugins, notifications, saas

## PRIORITETI ZA SLJEDEĆU SESIJU (Sprint 8 nastavak)

1. **Templates** — HTML template za svaku vertikalu (azil, termini, gradilista, hotel, maloprodaja, opg)
   Trenutno: URL routing + views postoje, templates/ NE postoje
2. **PEPPOL XML generator** — HR B2G implementacija (ROK: 2026-01-01 — KRITIČNO)
3. **Stripe checkout flow** — aktivni checkout session za upgrade
4. **DE TSE integracija** — DSFinV-K compatible POS export
5. **AI integracije** — booking assistant, construction cost AI
6. **Prodaja** — onboarding flow za Zdenko pilot, Marija testing

## ARHITEKTURA
- Server: 37.27.248.86 | ssh -p 2222 root@37.27.248.86
- Dir: /var/www/fenix-v3/
- Servis: gunicorn-fenix-v3.service (port 8001)
- Baza: fenix_v3_clean (direktno :5432)
- Test: venv/bin/python -m pytest tests/ -v
