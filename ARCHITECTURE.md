# LIMIT Connect — System Architecture

## Overview
| Metric | Value |
|--------|-------|
| Python files | 1,209 |
| Python LOC | 180,221 |
| Django apps | 47 |
| DB tables | 296 |
| Migrations | 334 |
| Templates | 455 |
| Static JS | 20 files, 596KB |

## Stack
- **Backend:** Django 5.1.6, Python 3.12
- **Database:** PostgreSQL 16
- **Cache/Queue:** Redis 7, Celery 5.4
- **Server:** Gunicorn + nginx, WhiteNoise static
- **API:** Django REST Framework 3.16, drf-spectacular (OpenAPI)
- **PDF:** xhtml2pdf
- **AI:** Anthropic SDK (claude)
- **Monitoring:** Sentry
- **i18n:** django-modeltranslation, rosetta (HR, DE)
- **Deploy:** systemd (production), Docker Compose (staging)

## Middleware Pipeline
```
SecurityMiddleware → WhiteNoise → Session → Common → CSRF
→ Auth → AuditMiddleware → UserLanguage → Locale
→ RolePermission → Company → Impersonation → CompanyBranch
→ ForcePasswordChange → Subscription → Messages → XFrame
→ IPFilter → ApiErrorFormat → SecurityHeaders
```

## Module Architecture (47 apps)

### CORE
- **core** — settings, middleware, audit, company utils, tenant
- **accounts** — User profiles, device tokens, company switching
- **companies** — Company, TaxRate, BusinessProfile, Branch, NKDCode, OnboardingProgress
- **permissions** — role-based access, IP filtering
- **registration** — SaaS signup, subscription plans

### SALES & POS (pos/, fiscal/, gastro_menu/)
**20 models:**
- `POSTerminal` → has many `POSSession`
- `POSSession` → has many `POSReceipt`, M2M `POSCashier`
  - Properties: total_sales, total_cash_sales, expected_closing_cash, cash_difference
- `POSReceipt` → has many `POSReceiptItem`, `POSPaymentLine`
  - FK: session, cashier, invoice (O2O)
  - Status: OPEN → PAID / CANCELLED / REFUNDED
- `POSPaymentLine` — methods: CASH, CARD, MOBILE, VOUCHER, ACCOUNT, CRYPTO, REVOLUT, AIRCASH
- `POSReceiptItem` — FK: receipt, inventory_item; flags: is_tip, is_pfand_return
- `POSSettings` — per-company: printer, fiscal cert, AI check toggle
- `POSCashier` — PBKDF2 PIN hash, rate-limited
- `Table`, `GastroOrder`, `GastroOrderItem` — restaurant table service
- `WaiterShift`, `CashDeposit`, `POSDailyReport`
- `Voucher`, `LoyaltyProgram`, `GuestLoyalty`
- `KnjigaPrigovora` — legal complaint book (ZZP čl.10)
- `ImprovementSuggestion` — Gemini AI generated

**Services:**
- `pos/services/__init__.py` — open/close session, create receipt, process payment, Z-report
- `pos/services/checkout.py` — CheckoutService (atomic, non-blocking fiscal)
- `pos/services/reporting.py` — ReportingService (DB aggregates, AI warnings)
- `fiscal/service.py` — fiscalize_pos_receipt (FINA CIS integration)

### INVENTORY (inventory/)
**13 models:**
- `InventoryItem` — FK: company, category, tax_rate, warehouse; fields: name, sku, barcode, unit_price, purchase_price, stock_quantity, reorder_point
- `StockMovement` — type: in/out/adjustment, FK: item, performed_by
- `StockBatch` — lot tracking: batch_number, expiry_date, quantity, quarantine flags
- `GoodsReceipt` / `GoodsReceiptItem` — inbound goods with margin calculation
- `PriceChange` — audit trail
- `Warehouse` / `WarehouseTransfer` / `WarehouseTransferItem` — multi-warehouse
- `Inventura` / `InventuraItem` / `InventuraCommission` — physical count with barcode, legal compliance
- `InventoryCountLog` — blind count with weight, theft detection

### DOCUMENTS & ARCHIVE (documents/)
**14 models:**
- `Document` — generic document
- `ArhivaEntry` — archived document: company, doc_number, doc_date, amount, currency, source_type, partner_name, zki, jir, integrity_hash
  - source_type: invoice_in, invoice_out, receipt, bank, contract, other, synesis, pos, primka, otpremnica, cmr
- `DocumentBlob` — file storage (PDF/XML/image)
- `ConversionRecord` — OCR/AI conversion tracking
- `ArhivaBookmark` — user bookmarks
- `Otpremnica` / `OtpremnicaItem` — delivery notes
- `OtkupniBlok` / `OtkupniBlokItem` — purchase blocks (market)
- `CMR` / `CMRItem` — international transport documents
- `GrossmarktDocument` / `GrossmarktDocItem` — wholesale documents

**Celery Tasks (614 LOC):** OCR pipeline, AI classification, email operator (workdays 08:00)

### INVOICING (invoicing/)
**5 models + 20 service files:**
- `Invoice` — FK: company, partner, business_location; fields: number, type (incoming/outgoing), status, total, tax, fiscal data
- `InvoiceItem` — FK: invoice, inventory_item
- `InvoiceEvent` — audit log
- `DunningRule` / `DunningHistory` — automated payment reminders

**Services:** invoice_service, pdf_service, email_service, fiscalize, storno, confirm, bilingual_labels, fiscal_de, fiscal_f20

### PROCUREMENT (procurement/)
**3 models:**
```python
class PurchaseOrder(models.Model):
    company → companies.Company
    supplier → partners.Partner
    matched_invoice → invoicing.Invoice
    created_by, approved_by → User
    po_number, status (draft→sent→confirmed→partial→received→invoiced→cancelled)
    priority (low/normal/high/urgent)
    order_date, expected_delivery, actual_delivery
    subtotal, tax_amount, total
    match_status (unmatched/matched/mismatch/approved), match_diff_amount

class PurchaseOrderItem(models.Model):
    purchase_order → PurchaseOrder
    inventory_item → inventory.InventoryItem
    description, sku, quantity, unit, unit_price, tax_rate
    line_total, line_tax, quantity_received

class SupplierPriceList(models.Model):
    company → companies.Company
    supplier → partners.Partner
    inventory_item → inventory.InventoryItem
    agreed_price, valid_from, valid_until, min_quantity
```

### MARKETPLACE (marketplace/)
**13 models:**
- `MarketplaceCategory` — self-referential tree (parent FK)
- `MarketplaceProduct` — FK: seller_company, inventory_item, category; fields: name, price, unit, min_order, stock, organic/bio flags
- `MarketplaceOrder` — FK: buyer_company, buyer_user, assigned_driver; status: pending→confirmed→picking→packed→shipped→delivered→cancelled; delivery scheduling
- `MarketplaceOrderItem` — FK: order, product
- `SellerSubOrder` — FK: marketplace_order, seller_company, collected_by, purchase_document; status tracking per seller
- `PartnerDiscount` — buyer-seller specific pricing
- `CategoryDiscount` / `VolumeDiscount` — tiered pricing
- `FuturesListing` — forward contracts: product, price, available_qty, harvest_date, delivery_window
- `FuturesReservation` — FK: listing, buyer; status: pending→confirmed→delivered→cancelled
- `FuturesDeliverySlot` — scheduled delivery windows
- `OrderComplaint` — FK: order, item; with storno_invoice, replacement_order
- `CartSnapshot` — saved cart state per user

### DELIVERY (delivery/)
**18 models:**
- `Vehicle` — type, plate, capacity, GPS, temperature monitoring
- `DeliveryRoute` / `DeliveryStop` — route planning with sequence
- `TemperatureLog`, `ColdChainZone`, `SensorReading` — HACCP cold chain
- `ConsolidatedDelivery` — hub consolidation
- `Rollwagen` / `PackagingExchange` — container tracking
- `SmartBox` — IoT container tracking
- `DeliveryCostRule` — zone-based pricing
- `TransportHandoff` / `DispatchOffer` — driver assignment
- `HACCPIncident` — food safety incidents
- `PickWave` / `PickTask` — warehouse picking
- `DeliveryZone` — geographic zones
- `DeliveryTracking` — real-time GPS

### FINANCE & ACCOUNTING
- **finance/** — basic financial tracking
- **konto/** — bookkeeping, bank import, reconciliation (services/bank_import.py)
- **payroll/** — salary calculation (services.py — 16KB)
- **payments/** — payment processing (services.py — 10.6KB)
- **eracun/** — e-invoice integration
- **pdv_s/** — VAT form generation (service.py — 9.2KB)
- **propter/** — Propter Hub integration (services/aggregate.py)

### HR & WORKFORCE
- **worktime/** — TimeEntry, TimeLog, TravelOrder, AnomalyReport (699 LOC models)
- **appointments/** — service booking, dossiers, scheduling (services.py — 9.5KB)
- **tracking/** — GPS employee tracking

### INTEGRATIONS
- **synesis/** — legacy MDB import (services.py — 6.1KB)
- **smart_import/** — AI document import (services.py — 21KB, tasks.py — 472 LOC)
- **fiscal/** — FINA CIS fiscalization
- **push_notifications/** — VAPID Web Push

### OTHER MODULES
- **ai_assistant/** — contextual AI chat widget
- **superadmin_ai/** — AI management, system prompts (services.py — 4.7KB)
- **helpdesk/** — ticketing system
- **maintenance/** — asset management, service calendar
- **rental/** — equipment/room rental
- **webshop/** — B2C online store
- **website/** — CMS, landing pages, gallery
- **assessment/** — field assessments
- **work_orders/** — work order management
- **interventions/** — emergency response tracking
- **aml/** — anti-money laundering
- **virtual_office/** — virtual office management
- **burza/** — project marketplace

## Key Cross-Module Relationships
```
companies.Company ──┬── pos.POSTerminal ── pos.POSSession ── pos.POSReceipt
                    ├── inventory.InventoryItem ── pos.POSReceiptItem
                    ├── invoicing.Invoice ── procurement.PurchaseOrder (matched_invoice)
                    ├── partners.Partner ── procurement.PurchaseOrder (supplier)
                    ├── marketplace.MarketplaceProduct ── marketplace.MarketplaceOrder
                    ├── documents.ArhivaEntry (auto-archived from all modules)
                    ├── worktime.TimeLog ── accounts.DeviceToken (unified login)
                    └── delivery.Vehicle ── delivery.DeliveryRoute

inventory.InventoryItem ──┬── pos.POSReceiptItem (stock deduction on sale)
                          ├── procurement.PurchaseOrderItem (reorder)
                          ├── procurement.SupplierPriceList (pricing)
                          ├── marketplace.MarketplaceProduct (B2B listing)
                          ├── inventory.StockBatch (lot tracking)
                          └── calculator.BOM (bill of materials)

invoicing.Invoice ──┬── eracun (e-invoice XML)
                    ├── fiscal (FINA fiscalization)
                    ├── konto (bookkeeping entries)
                    └── procurement.PurchaseOrder (3-way match)
```

## API Layer
- REST Framework viewsets: partners, appointments, webshop, worktime, pos
- AI Agent Gateway: `/api/ai-agent/` with 4-level permissions
- Dev API: `/_dev/exec/` with command whitelist + Bearer token
- POS API: `/api/pos/items/`, `/api/pos/checkout/` (Gemini standardized)

## Celery Tasks (9 modules)
| Module | LOC | Key Tasks |
|--------|-----|-----------|
| documents | 614 | OCR pipeline, AI classification, email operator |
| smart_import | 472 | AI document parsing, validation |
| superadmin_ai | 279 | System-wide AI operations |
| invoicing | 244 | PDF generation, e-invoice sending |
| appointments | 180 | Reminders, scheduling |
| inventory | 174 | Reorder alerts, expiry checks |
| pos | 127 | Offline fiscal retry (every 2min) |
| worktime | 126 | Anomaly detection |
| ai_assistant | 88 | Chat context processing |

## Security
- PBKDF2 PIN hashing for POS cashiers
- Rate limiting (5 attempts/60s per IP)
- nginx IP whitelist
- Command whitelist on dev API
- AuditMiddleware logging
- SecurityHeaders middleware
- CSRF + session-based auth
- Role-based permissions with IPFilterMiddleware
- integrity_hash on ArhivaEntry (document tamper detection)
