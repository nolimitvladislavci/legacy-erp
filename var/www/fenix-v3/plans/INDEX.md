# FENIX V3 — MASTER PLAN INDEX
**Datum kreiranja**: 2026-04-17  
**Status**: 67 planova — KOMPLETAN  
**Cilj**: Agenti izvršavaju bez ponovnog skeniranja repozitorija

---

## PRAVILO #1 za sve agente
> Čitaj plan POTPUNO prije pisanja ijednog reda koda.  
> Svaki plan ima model + view + template + testovi.  
> CSS: SAMO klase iz PLAN_007B. Nema inline Tailwind za standardne elemente.

---

## TIER 0 — CORE INFRASTRUKTURA (čitaj prvo, uvijek)

| Plan | Naziv | Status |
|------|-------|--------|
| [PLAN_001](PLAN_001_CORE_BASEMODEL.md) | BaseModel, TenantModel, ActiveManager, soft delete | READY |
| [PLAN_002](PLAN_002_CORE_BASEVIEW.md) | FenixView, TenantView, PublicView, HTMX detection | READY |
| [PLAN_003](PLAN_003_CORE_SETTINGS.md) | Settings split (base/dev/test/prod), env(), 3 DB | READY |
| [PLAN_004](PLAN_004_CORE_MIDDLEWARE.md) | CompanyMiddleware, SecurityHeaders, Audit, Performance | READY |
| [PLAN_005](PLAN_005_CORE_URLS.md) | URL routing, RouteRegistry, /hr/ /pub/ /api/v1/ | READY |
| [PLAN_006](PLAN_006_CORE_TEMPLATES.md) | base.html, sidebar, topbar, toasts, empty state | READY |
| [PLAN_007](PLAN_007_CORE_STATIC.md) | fenix.js, PWA manifest, Service Worker, Tailwind config | READY |
| [PLAN_007B](PLAN_007B_GLOBAL_CSS_COMPONENTS.md) | **KRITIČNO**: Globalni CSS — .btn, .card, .table, .badge | READY |
| [PLAN_007C](PLAN_007C_ACCESSIBILITY.md) | WCAG 2.1 AA — skip link, focus trap, aria, voice | READY |
| [PLAN_007D](PLAN_007D_FENIX_ACADEMY.md) | FenixCertificate, 10 modula, WeasyPrint PDF, QR | READY |
| [PLAN_008](PLAN_008_CORE_TESTS.md) | conftest.py, pytest.ini, ruff, mypy, requirements | READY |
| [PLAN_009](PLAN_009_CORE_CELERY.md) | 3 queue (default/heavy/scheduled), Beat, FenixTask | READY |
| [PLAN_010](PLAN_010_CORE_AI_GATEWAY.md) | AIGateway singleton, Haiku-first, cost tracking | READY |

---

## TIER 1 — ACCOUNTS & AUTH

| Plan | Naziv | Status |
|------|-------|--------|
| [PLAN_011](PLAN_011_ACCOUNTS_USERPROFILE.md) | UserProfile, CompanyMembership, 6 rola, LoginAudit | READY |
| [PLAN_012](PLAN_012_ACCOUNTS_LOGIN.md) | LoginView, rate limit 5/5min, ForcePasswordChange | READY |
| [PLAN_013](PLAN_013_ACCOUNTS_PIN.md) | PinVerifyView, pin_required decorator, 15min session | READY |
| [PLAN_014](PLAN_014_COMPANY_SWITCH.md) | CompanySwitchView, HTMX search, sidebar_modules | READY |
| [PLAN_015](PLAN_015_ACCOUNTS_PERMISSIONS.md) | 14 permisija, ROLE_PERMISSIONS, {% can %} tag | READY |
| [PLAN_016](PLAN_016_ACCOUNTS_ONBOARDING.md) | 4-koračni wizard, OIB lookup, module odabir | READY |
| [PLAN_017](PLAN_017_ACCOUNTS_PASSWORD_RESET.md) | Django built-in + custom templates | READY |
| [PLAN_018](PLAN_018_ACCOUNTS_PROFILE_SETTINGS.md) | 4 sekcije, HTMX save, avatar resize 200px | READY |

---

## TIER 2 — COMPANY

| Plan | Naziv | Status |
|------|-------|--------|
| [PLAN_019](PLAN_019_COMPANY_MODEL.md) | Company model — HR+DE polja, OIB validate, IBAN | READY |
| [PLAN_020](PLAN_020_COMPANY_DASHBOARD.md) | 5 widgeta, HTMX refresh 60s, quick actions | READY |
| [PLAN_021](PLAN_021_COMPANY_UMBRELLA.md) | Umbrella dashboard, context processors | READY |
| [PLAN_022](PLAN_022_COMPANY_SETTINGS.md) | 7 tabova (basic/tax/addr/inv/fiscal/AI/danger) | READY |
| [PLAN_023](PLAN_023_COMPANY_MEMBERS.md) | MemberInvite, RoleChange, Remove, InvitationToken | READY |
| [PLAN_024](PLAN_024_COMPANY_OIB_LOOKUP.md) | OIBLookupView, RGFI API, Redis cache 24h | READY |

---

## TIER 3 — DIGITALNA ARHIVA ★ (najvažniji za bookkeeper)

| Plan | Naziv | Status |
|------|-------|--------|
| [PLAN_025](PLAN_025_ARHIVA_MODEL.md) | ArhivaEntry — 24 doc type, OCR, AI, ZOR 11 god | READY |
| [PLAN_026](PLAN_026_ARHIVA_UPLOAD.md) | Alpine.js upload zone, drag-drop, progress, OCR trigger | READY |
| [PLAN_027](PLAN_027_ARHIVA_OCR.md) | FenixScan, Bedrock/Anthropic, UBL XML parse | READY |
| [PLAN_028](PLAN_028_ARHIVA_LIST_DRAWER.md) | List + HTMX drawer, fixed right panel, animate | READY |
| [PLAN_029](PLAN_029_ARHIVA_SCAN_TOKEN.md) | Mobile scan page, black BG, QR generator | READY |
| [PLAN_030](PLAN_030_ARHIVA_MAGIC_LINK.md) | ArhivaPortalView, MagicLink bulk, PortalDownload | READY |
| [PLAN_031](PLAN_031_ARHIVA_DE_STEUERBERATER.md) | DE polja, GoBD, SHA-256, Bewirtungsbeleg, SKR03 | READY |
| [PLAN_032](PLAN_032_ARHIVA_WHATSAPP.md) | WAHA webhook, WhatsApp share, auto-archive | READY |
| [PLAN_033](PLAN_033_ARHIVA_DATEV.md) | DATEV EXTF, cp1252, decimal comma, SKR03 dict | READY |

---

## TIER 4 — RAČUNOVODSTVO

| Plan | Naziv | Status |
|------|-------|--------|
| [PLAN_034](PLAN_034_INVOICING_MODEL.md) | Invoice + InvoiceItem + InvoicePayment, atomic broj | READY |
| [PLAN_035](PLAN_035_INVOICING_UI.md) | Alpine.js invoiceBuilder, OIB fill, VAT calc | READY |
| [PLAN_036](PLAN_036_INVOICING_ERACUN.md) | UBL 2.1 XML, namespace, line items, tax totals | READY |
| [PLAN_041](PLAN_041_KONTO_MODEL.md) | Account hierarchy, JournalEntry, JournalLine | READY |
| [PLAN_042](PLAN_042_JOURNAL_ENTRY_UI.md) | Konto UI — Alpine.js, account autocomplete, storno | READY |
| [PLAN_043](PLAN_043_PDV.md) | VATReturn, HR PDV-S XML, DE UStVA ELSTER | READY |
| [PLAN_044](PLAN_044_REPORTS.md) | P&L, saldo, overdue, POS, arhiva — Excel+PDF | READY |
| [PLAN_045](PLAN_045_GOV_EXPORT.md) | PDV-S XML ePorezna + DE UStVA ELSTER export | READY |
| [PLAN_046](PLAN_046_AML_BASIC.md) | AML/KYC osnovna — stranke, flagging 10k EUR | READY |

---

## TIER 5 — POS ★★ (4. verzija — KONAČNA)

> **UPOZORENJE**: grep "class POS" mora vratiti TOČNO 5 klasa.  
> Nikad više duplikat POS modela. PLAN_047 je kanon.

| Plan | Naziv | Status |
|------|-------|--------|
| [PLAN_047](PLAN_047_POS_MODEL.md) | **KANONSKI MODEL**: POSRegister, Session, Transaction, Item, Product | READY |
| [PLAN_048](PLAN_048_POS_TERMINAL.md) | POS UI — katalog + košarica + plaćanje + keyboard | READY |
| [PLAN_048B](PLAN_048B_POS_2030_ADVANCED.md) | Smart Pricing, Tap-to-Pay NFC, Ghost Receipt WAHA | READY |
| [PLAN_049](PLAN_049_POS_FISKALIZACIJA.md) | ZKI HMAC-SHA1, FINA SOAP, JIR parse, Celery | READY |
| [PLAN_050](PLAN_050_POS_RECEIPT.md) | Termal 80mm, WeasyPrint, JIR/ZKI, QR kod | READY |
| [PLAN_051](PLAN_051_POS_FREE_TIER.md) | 50 tx/mj limit, reset, upgrade CTA | READY |

---

## TIER 6 — AI EKOSUSTAV

| Plan | Naziv | Status |
|------|-------|--------|
| [PLAN_052](PLAN_052_AI_COCKPIT.md) | AICockpitView, AIInsight model, company context | READY |
| [PLAN_053](PLAN_053_SMART_IMPORT.md) | **MARIJA KILLER FEATURE**: Batch import, OCR, 1-click approve | READY |
| [PLAN_054](PLAN_054_TROJSTVO_ENGINE.md) | 3-agent: Haiku + Gemini + DeepSeek, 2/3 konsenzus | READY |
| [PLAN_055](PLAN_055_VOICE_INPUT.md) | Web Speech API, Alpine plugin, HR/DE/EN, accessibility | READY |
| [PLAN_056](PLAN_056_AI_COST_CONTROL.md) | AIUsageLog, AIBudget, hard limit, CSV export | READY |
| [PLAN_057](PLAN_057_AI_BATCH.md) | Batch job overnight, pause/cancel, throttle | READY |

---

## TIER 7 — HR (Upravljanje Radnicima)

| Plan | Naziv | Status |
|------|-------|--------|
| [PLAN_058](PLAN_058_EMPLOYEE.md) | Employee model, OIB, stope, employment types | READY |
| [PLAN_059](PLAN_059_HONORARI.md) | Autorski honorari, obračun, JOPPD XML, prirez | READY |
| [PLAN_060](PLAN_060_WORKTIME.md) | Evidencija RV, clock-in/out, prekovremeni, ZOR 6g | READY |
| [PLAN_061](PLAN_061_PAYROLL_UI.md) | Plaće UI — kalkulator live, bulk obračun, SEPA | READY |

---

## TIER 8 — MIGRACIJA, DEPLOYMENT, OPS

| Plan | Naziv | Status |
|------|-------|--------|
| [PLAN_062](PLAN_062_DATA_MIGRATION.md) | fina-connect → fenix-v3 idempotentna migracija | READY |
| [PLAN_063](PLAN_063_DEPLOYMENT.md) | Nginx, systemd, Gunicorn, Celery services | READY |
| [PLAN_064](PLAN_064_MONITORING.md) | Sentry, HealthView, logging, DeepSeek Patrol | READY |
| [PLAN_065](PLAN_065_CUTOVER.md) | 9-koračni cutover, rollback u 60s | READY |
| [PLAN_066](PLAN_066_CICD.md) | GitHub Actions CI, deploy.sh zero-downtime, pre-commit | READY |
| [PLAN_067](PLAN_067_TESTING_STRATEGY.md) | Piramida 60/30/10, factories, smoke tests, 80% coverage | READY |

---

## TEHNIČKE KONSTANTE (zapamti za sva kodiranja)

```
Stack: Django 5.1 + HTMX 2 + Alpine.js 3 + Tailwind CSS 3
Baza: PostgreSQL 15 (default: fenix_v3, test: fenix_test)
Cache: Redis 7
Queue: Celery 5 — queues: default, heavy, scheduled
Venv: /var/www/fenix-v3/venv/bin/python
Server: 37.27.248.86, port 8080 (Nginx upstream)
AI: Haiku (OCR/suggest), Gemini Flash (search), DeepSeek (code/patrol)
Fiskalizacija: FINA SOAP (HR), test: Test FINA endpoint
PIN test: 123123
```

## CSS PRAVILO (ne smiješ zaboraviti)
```
✓ <button class="btn-primary">       — ISPRAVNO
✗ <button class="bg-blue-500 ...">   — ZABRANJENO
✓ <div class="card">                 — ISPRAVNO  
✗ <div class="bg-white shadow ...">  — ZABRANJENO
```
Sve klase su definirane u PLAN_007B. Uvijek čitaj PLAN_007B prije template rada.

## ACCESSIBILITY PRAVILO
Svaki interaktivni element mora imati:
- `aria-label` ili `aria-labelledby`
- keyboard navigacija (Tab + Enter/Space)
- fokus vidljiv (`:focus-visible` ring)
- color contrast ratio ≥ 4.5:1

---

*Index generiran: 2026-04-17 | 67 planova | ~750KB dokumentacije*
