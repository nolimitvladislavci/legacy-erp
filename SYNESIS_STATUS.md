# Synesis integracija — stanje 05.03.2026

## Što je implementirano

### Django app: synesis/
-  — SynesisConfig (OneToOne per company) + SynesisLog
-  — settings, regenerate_token, download_script, download_setup_bat,
                        download_script_public, synesis_import_api,
                        _import_partners, _import_items, _import_pos
-  — /synesis/ namespace
- Migracije: 0001 (init), 0002 (pos_db_path), 0003 (POS stats fields)

### URL-ovi
| URL | Opis |
|---|---|
| /synesis/ | Settings stranica (login required) |
| /synesis/regenerate-token/ | POST — regeneriraj API token |
| /synesis/download-script/ | GET — preuzmi synesis_sync.py |
| /synesis/download-setup/ | GET — preuzmi synesis_setup.bat (installer) |
| /api/synesis/import/ | POST — Token auth, prima partnere/artikle/POS |
| /api/synesis/script/{token}/ | GET — javni endpoint za BAT download skripte |

### SynesisConfig fields (Konjik d.o.o.)
- api_token: W-fYDg_lwFpnOuq4eyfwxySM-sMPo3O8hiCMfQ_JRYg
- storage_db_path: C:\Synesis\KONJIK2025\Storage.mdb
- journal_db_path: C:\Synesis\KONJIK2025\Journal.mdb
- pos_db_path: C:\SynesisPOS\Kasa2025-01.mdb
- pos_db_password: nedrijesigaca
- pos_name: Kasa 1

### Synesis baze (lokalno na Windows računalu)
- Storage.mdb: PARTNERS (957), ITEMS (2734), INVOICES (825)
- Journal.mdb: Journal (11766), eFaktura
- Kasa2025-01.mdb: Receipts, TReceipts, Total, Items, CashDeposit, Users, Settings
- System/Kasa.mdb: ista struktura, rezervna

### Dashboard
- company_admin.html: synesis_cfg u contextu, widget prikazuje ERP + POS stats
- base.html: sidebar link Integracije → Synesis

## Što nedostaje (za sljedeću sesiju)

1. Uvoz INVOICES iz Storage.mdb → invoicing app (825 faktura)
2. TReceipts analytics — promet po artiklima, grafikon po danima
3. Company isolation security (7 view fajlova — vidi QUALITY_PLAN.md)
4. Empty states + Quick-add modali u invoice wizard

## Tehnički detalji

### Import flow
Windows: synesis_setup.bat (jednom) → kreira Scheduled Task (02:00 daily)
         synesis_sync.py → čita .mdb → POST /api/synesis/import/ (Token auth)
Server: synesis_import_api → _import_partners / _import_items / _import_pos
        → upsert po OIB-u (partneri) ili sku=SYN-{ID} (artikli)
        → SynesisLog zapis + SynesisConfig stats update

### InventoryItem mapping
- sku = SYN-{ITEM_ID} (unique_together company+sku)
- category: ne importira se (choices field) — opis ide u description
- tax_rate: VAT_RATE 25→id=1, 13→id=2, 10→13 (stara HR), 5→id=3, 0→id=6

### Partner mapping  
- upsert: if OIB → filter(company, oib=oib) else filter(company, name=name, oib=None)
- PARTNER_TYPE: 1=supplier, 2=client
- INT_COUNTRYID: HR→Hrvatska, DE→Njemacka, itd.

### POS import
- Receipts zadnjih 90 dana
- Računa revenue_today/week/month filtracijom po Receipt_Date
- Pohranjuje summary u SynesisConfig (ne individual records)
