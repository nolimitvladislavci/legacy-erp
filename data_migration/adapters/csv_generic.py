"""
data_migration/adapters/csv_generic.py

Genericki CSV/Excel adapter za uvoz partnera i artikala.

Podrzava:
- CSV (UTF-8, Windows-1250, ISO-8859-2 — auto-detekcija via chardet)
- Excel (.xlsx, .xls via openpyxl)
- Automatska detekcija delimitera (csv.Sniffer)
- Bulk insert/update (batch_size=1000)
- Dedup po OIB-u (partneri) i SKU (artikli)
- Inkrementalni progress update svakih 100 redova
"""
import csv
import io
import logging
import os
from decimal import Decimal, InvalidOperation
from typing import Any

import chardet

from .base import AdapterResult, BaseAdapter, MappingField, register_adapter
from django.db import DatabaseError

logger = logging.getLogger(__name__)

# Interval za inkrementalni progress update (svaki N redova)
_PROGRESS_INTERVAL = 100

# ── Mapping sheme ─────────────────────────────────────────────────

PARTNER_SCHEMA = [
    MappingField("name",       "Naziv",           required=True),
    MappingField("oib",        "OIB",             required=False, hint="11 znamenki", field_type="oib"),
    MappingField("address",    "Adresa",          required=False),
    MappingField("city",       "Grad",            required=False),
    MappingField("zip_code",   "Postanski broj",  required=False),
    MappingField("country",    "Drzava",          required=False, hint="HR, DE, AT, SI..."),
    MappingField("email",      "Email",           required=False, field_type="email"),
    MappingField("phone",      "Telefon",         required=False),
    MappingField("contact_person", "Kontakt osoba", required=False),
    MappingField("iban",       "IBAN",            required=False),
    MappingField("vat_id",     "EU VAT ID",       required=False, hint="Npr. HR12345678901"),
    MappingField("partner_type", "Tip",           required=False, hint="client, supplier, both"),
    MappingField("payment_term", "Rok placanja (dani)", required=False, field_type="number"),
    MappingField("notes",      "Napomena",        required=False),
]

ITEM_SCHEMA = [
    MappingField("name",           "Naziv",           required=True),
    MappingField("sku",            "Sifra",           required=True, hint="Jedinstvena sifra artikla"),
    MappingField("barcode",        "Barkod",          required=False),
    MappingField("unit_price",     "Prodajna cijena", required=False, field_type="number"),
    MappingField("purchase_price", "Nabavna cijena",  required=False, field_type="number"),
    MappingField("unit",           "Jed. mjere",      required=False, hint="kom, kg, l, m..."),
    MappingField("tax_rate_value", "PDV stopa (%)",   required=False, field_type="number", hint="25, 13, 5 ili 0"),
    MappingField("category",       "Kategorija",      required=False, hint="product, material, service..."),
    MappingField("description",    "Opis",            required=False),
    MappingField("min_quantity",   "Min. kolicina",   required=False, field_type="number"),
    MappingField("location",       "Lokacija",        required=False),
]


# ── Pomocne funkcije ─────────────────────────────────────────────

def _detect_encoding(raw_bytes: bytes) -> str:
    """Detektira enkodiranje koristeci chardet. Fallback: utf-8."""
    result = chardet.detect(raw_bytes[:100_000])
    encoding = result.get("encoding") or "utf-8"
    confidence = result.get("confidence", 0)

    if confidence < 0.7 and encoding.lower() in ("ascii", "windows-1252"):
        encoding = "windows-1250"

    encoding_map = {
        "iso-8859-2": "iso-8859-2",
        "latin2": "iso-8859-2",
        "windows-1250": "cp1250",
        "cp1250": "cp1250",
    }
    return encoding_map.get(encoding.lower(), encoding)


def _detect_delimiter(text_sample: str) -> str:
    """Detektira delimiter koristeci csv.Sniffer. Fallback: ';'."""
    try:
        lines = text_sample.split("\n")[:10]
        sample = "\n".join(lines)
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        return dialect.delimiter
    except csv.Error:
        if ";" in text_sample[:2000]:
            return ";"
        return ","


def _safe_decimal(value: Any, default: Decimal = Decimal("0")) -> Decimal:
    """Sigurna konverzija u Decimal. Podrzava zareze kao decimalni separator."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return default
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    s = str(value).strip()
    if "," in s and "." in s:
        if s.rindex(",") > s.rindex("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        parts = s.split(",")
        if len(parts) == 2 and len(parts[1]) <= 2:
            s = s.replace(",", ".")
        else:
            s = s.replace(",", "")
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return default


def _clean_oib(value: Any) -> str:
    """Cisti OIB: uklanja razmake, crtice, vodi do 11 znamenki."""
    if not value:
        return ""
    s = str(value).strip().replace(" ", "").replace("-", "").replace(".", "")
    if s.upper().startswith("HR") and len(s) > 2:
        s = s[2:]
    if len(s) == 11 and s.isdigit():
        return s
    return str(value).strip()


def _read_excel(file_path: str) -> list[dict[str, Any]]:
    """Cita Excel (.xlsx) datoteku koristeci openpyxl."""
    import openpyxl

    wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    if len(rows) < 2:
        raise ValueError("Excel datoteka je prazna ili nema podataka ispod zaglavlja.")

    headers = [str(h).strip() if h is not None else f"Kolona_{i}"
               for i, h in enumerate(rows[0])]

    data = []
    for row in rows[1:]:
        if all(cell is None or (isinstance(cell, str) and not cell.strip()) for cell in row):
            continue
        record = {}
        for i, cell in enumerate(row):
            if i < len(headers):
                val = cell
                if isinstance(val, str):
                    val = val.strip()
                record[headers[i]] = val if val is not None else ""
        data.append(record)

    return data


def _update_progress(project, processed, created, updated, failed):
    """Inkrementalni progress update u bazu — frontend polling cita ovo."""
    if project is None:
        return
    project.processed_rows = processed
    project.records_created = created
    project.records_updated = updated
    project.records_failed = failed
    project.save(update_fields=[
        "processed_rows", "records_created", "records_updated", "records_failed",
    ])


# ── Adapter ───────────────────────────────────────────────────────

@register_adapter
class CsvGenericAdapter(BaseAdapter):
    name = "csv_generic"
    label = "Genericki CSV / Excel"
    supported_formats = ["csv", "xlsx", "xls"]
    description = "Uvoz partnera i artikala iz CSV ili Excel datoteka"

    def detect_format(self, file_path: str, file_format: str = "") -> bool:
        if file_format and file_format.lower() in self.supported_formats:
            return True
        ext = os.path.splitext(file_path)[1].lower().lstrip(".")
        return ext in self.supported_formats

    def extract_raw_data(self, file_path: str) -> list[dict[str, Any]]:
        ext = os.path.splitext(file_path)[1].lower()

        if ext in (".xlsx", ".xls"):
            data = _read_excel(file_path)
            if not data:
                raise ValueError("Excel datoteka ne sadrzi podatke.")
            return data

        # ── CSV ──────────────────────────────────────────────────
        with open(file_path, "rb") as f:
            raw_bytes = f.read()

        if not raw_bytes.strip():
            raise ValueError("CSV datoteka je prazna.")

        encoding = _detect_encoding(raw_bytes)
        try:
            text = raw_bytes.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            for fallback in ("cp1250", "iso-8859-2"):
                try:
                    text = raw_bytes.decode(fallback)
                    encoding = fallback
                    break
                except (UnicodeDecodeError, LookupError):
                    continue
            else:
                text = raw_bytes.decode("utf-8", errors="replace")
                encoding = "utf-8 (with replacements)"

        logger.info("CSV encoding detektiran: %s", encoding)

        if text.startswith("\ufeff"):
            text = text[1:]

        delimiter = _detect_delimiter(text)
        logger.info("CSV delimiter detektiran: %r", delimiter)

        reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
        data = []
        for row in reader:
            if all(not v or not v.strip() for v in row.values()):
                continue
            clean_row = {}
            for k, v in row.items():
                key = (k or "").strip()
                if not key:
                    continue
                clean_row[key] = (v or "").strip()
            data.append(clean_row)

        if not data:
            raise ValueError("CSV datoteka ne sadrzi podatke nakon zaglavlja.")

        return data

    def get_mapping_schema(self, entity_type: str = "partners") -> list[dict]:
        if entity_type == "items":
            return [f.to_dict() for f in ITEM_SCHEMA]
        return [f.to_dict() for f in PARTNER_SCHEMA]

    def execute_import(
        self,
        company,
        data: list[dict[str, Any]],
        field_mapping: dict[str, str],
        entity_type: str = "partners",
        user=None,
    ) -> AdapterResult:
        mapped_data = self.apply_mapping(data, field_mapping)

        if entity_type == "items":
            return self._import_items(company, mapped_data, user)
        return self._import_partners(company, mapped_data, user)

    # ── Partner import ────────────────────────────────────────────

    def _import_partners(self, company, data: list[dict], user) -> AdapterResult:
        from partners.models import Partner

        result = AdapterResult()
        logs = []
        project = getattr(self, "_current_project", None)

        # Dohvati postojece partnere za dedup
        existing_by_oib = {}
        existing_by_name = {}
        for p in Partner.objects.unscoped().filter(company=company).only("pk", "oib", "name"):
            if p.oib:
                existing_by_oib[p.oib] = p.pk
            existing_by_name[p.name.lower().strip()] = p.pk

        to_create = []
        to_update_pks = {}

        valid_countries = {"HR", "DE", "AT", "SI", "BA", "RS", "IT", "HU", "OTHER"}
        valid_types = {"client", "supplier", "both", "employee", "agent"}

        for row_idx, row in enumerate(data, start=2):
            name = row.get("name", "").strip()
            if not name:
                result.add_error("Prazan naziv partnera.", row=row_idx, field="name")
                logs.append(("error", row_idx, "name", "Prazan naziv partnera — red preskocen.", "", ""))
                # Inkrementalni progress
                if (row_idx - 1) % _PROGRESS_INTERVAL == 0:
                    _update_progress(project, row_idx - 1, result.created, result.updated, result.failed)
                continue

            oib = _clean_oib(row.get("oib", ""))

            if oib and (len(oib) != 11 or not oib.isdigit()):
                logs.append(("warning", row_idx, "oib",
                             f"Neispravan OIB '{oib}' — uvezen bez OIB-a.",
                             oib, ""))
                oib = ""

            existing_pk = None
            if oib and oib in existing_by_oib:
                existing_pk = existing_by_oib[oib]
            elif name.lower().strip() in existing_by_name:
                existing_pk = existing_by_name[name.lower().strip()]

            country = (row.get("country") or "HR").upper().strip()
            if country not in valid_countries:
                logs.append(("warning", row_idx, "country",
                             f"Nepoznata drzava '{country}' — postavljeno 'HR'.",
                             country, "HR"))
                country = "HR"

            partner_type = (row.get("partner_type") or "client").lower().strip()
            if partner_type not in valid_types:
                logs.append(("warning", row_idx, "partner_type",
                             f"Nepoznat tip '{partner_type}' — postavljeno 'client'.",
                             partner_type, "client"))
                partner_type = "client"

            payment_term = 0
            pt_raw = row.get("payment_term", "")
            if pt_raw:
                try:
                    payment_term = int(pt_raw)
                except (ValueError, TypeError):
                    logs.append(("warning", row_idx, "payment_term",
                                 f"Neispravan rok placanja '{pt_raw}' — postavljeno 0.",
                                 str(pt_raw), "0"))

            fields = {
                "name": name[:200],
                "oib": oib,
                "address": (row.get("address") or "")[:255],
                "city": (row.get("city") or "")[:100],
                "zip_code": (row.get("zip_code") or "")[:20],
                "country": country,
                "email": (row.get("email") or "")[:254],
                "phone": (row.get("phone") or "")[:50],
                "contact_person": (row.get("contact_person") or "")[:200],
                "iban": (row.get("iban") or "")[:34],
                "vat_id": (row.get("vat_id") or "")[:20],
                "partner_type": partner_type,
                "payment_term": payment_term,
                "notes": row.get("notes") or "",
            }

            if existing_pk:
                to_update_pks[existing_pk] = fields
            else:
                to_create.append(fields)
                if oib:
                    existing_by_oib[oib] = -1
                existing_by_name[name.lower().strip()] = -1

            # Inkrementalni progress svakih N redova
            if (row_idx - 1) % _PROGRESS_INTERVAL == 0:
                _update_progress(project, row_idx - 1, result.created, result.updated, result.failed)

        # ── Bulk create u batchevima od 1000 ─────────────────────
        if to_create:
            partners_batch = []
            for i, fields in enumerate(to_create):
                partners_batch.append(Partner(company=company, **fields))
                if len(partners_batch) >= 1000:
                    Partner.objects.unscoped().bulk_create(
                        partners_batch, batch_size=1000, ignore_conflicts=True,
                    )
                    result.created += len(partners_batch)
                    _update_progress(project, len(data), result.created, result.updated, result.failed)
                    partners_batch = []
            if partners_batch:
                Partner.objects.unscoped().bulk_create(
                    partners_batch, batch_size=1000, ignore_conflicts=True,
                )
                result.created += len(partners_batch)

        # ── Bulk update u batchevima od 1000 ─────────────────────
        if to_update_pks:
            update_fields = [
                "name", "address", "city", "zip_code", "country",
                "email", "phone", "contact_person", "iban", "vat_id",
                "partner_type", "payment_term", "notes",
            ]
            partners_batch = []
            for pk, fields in to_update_pks.items():
                p = Partner(pk=pk, company=company)
                for k, v in fields.items():
                    if k != "oib":
                        setattr(p, k, v)
                partners_batch.append(p)
                if len(partners_batch) >= 1000:
                    Partner.objects.unscoped().bulk_update(
                        partners_batch, fields=update_fields, batch_size=1000,
                    )
                    result.updated += len(partners_batch)
                    _update_progress(project, len(data), result.created, result.updated, result.failed)
                    partners_batch = []
            if partners_batch:
                Partner.objects.unscoped().bulk_update(
                    partners_batch, fields=update_fields, batch_size=1000,
                )
                result.updated += len(partners_batch)

        self._save_logs(logs)
        _update_progress(project, len(data), result.created, result.updated, result.failed)
        return result

    # ── Item import ───────────────────────────────────────────────

    def _import_items(self, company, data: list[dict], user) -> AdapterResult:
        from inventory.models import InventoryItem

        result = AdapterResult()
        logs = []
        project = getattr(self, "_current_project", None)

        tax_rate_map = self._build_tax_rate_map(company)

        existing_by_sku = {}
        for item in InventoryItem.objects.unscoped().filter(company=company).only("pk", "sku"):
            if item.sku:
                existing_by_sku[item.sku.lower().strip()] = item.pk

        to_create = []
        to_update_pks = {}

        valid_categories = {
            "material", "tool", "equipment", "consumable", "product",
            "service", "food", "drink", "dessert", "special", "other",
        }
        valid_units = {"kom", "kg", "l", "m", "m2", "m3", "par", "sat", "dan", "kpl", "pak"}

        for row_idx, row in enumerate(data, start=2):
            name = (row.get("name") or "").strip()
            if not name:
                result.add_error("Prazan naziv artikla.", row=row_idx, field="name")
                logs.append(("error", row_idx, "name", "Prazan naziv artikla — red preskocen.", "", ""))
                if (row_idx - 1) % _PROGRESS_INTERVAL == 0:
                    _update_progress(project, row_idx - 1, result.created, result.updated, result.failed)
                continue

            sku = (row.get("sku") or "").strip()
            if not sku:
                result.add_error("Prazna sifra artikla.", row=row_idx, field="sku")
                logs.append(("error", row_idx, "sku", "Prazna sifra artikla — red preskocen.", "", ""))
                if (row_idx - 1) % _PROGRESS_INTERVAL == 0:
                    _update_progress(project, row_idx - 1, result.created, result.updated, result.failed)
                continue

            existing_pk = existing_by_sku.get(sku.lower().strip())

            unit_price = _safe_decimal(row.get("unit_price"))
            purchase_price = _safe_decimal(row.get("purchase_price"))

            unit = (row.get("unit") or "kom").strip().lower()
            if unit not in valid_units:
                logs.append(("warning", row_idx, "unit",
                             f"Nepoznata jed. mjere '{unit}' — postavljeno 'kom'.",
                             unit, "kom"))
                unit = "kom"

            category = (row.get("category") or "other").strip().lower()
            if category not in valid_categories:
                logs.append(("warning", row_idx, "category",
                             f"Nepoznata kategorija '{category}' — postavljeno 'other'.",
                             category, "other"))
                category = "other"

            tax_rate_obj = None
            tax_raw = row.get("tax_rate_value", "")
            if tax_raw:
                tax_rate_obj = self._resolve_tax_rate(tax_raw, tax_rate_map, row_idx, logs)

            min_qty = _safe_decimal(row.get("min_quantity"))

            fields = {
                "name": name[:200],
                "sku": sku[:50],
                "barcode": (row.get("barcode") or "")[:100],
                "unit_price": unit_price,
                "purchase_price": purchase_price,
                "unit": unit[:20],
                "category": category,
                "description": row.get("description") or "",
                "min_quantity": min_qty,
                "location": (row.get("location") or "")[:100],
                "_tax_rate_obj": tax_rate_obj,
            }

            if existing_pk:
                to_update_pks[existing_pk] = fields
            else:
                to_create.append(fields)
                existing_by_sku[sku.lower().strip()] = -1

            if (row_idx - 1) % _PROGRESS_INTERVAL == 0:
                _update_progress(project, row_idx - 1, result.created, result.updated, result.failed)

        # ── Bulk create u batchevima od 1000 ─────────────────────
        if to_create:
            items_batch = []
            for fields in to_create:
                tax_obj = fields.pop("_tax_rate_obj", None)
                item = InventoryItem(company=company, **fields)
                if tax_obj:
                    item.tax_rate = tax_obj
                items_batch.append(item)
                if len(items_batch) >= 1000:
                    InventoryItem.objects.unscoped().bulk_create(
                        items_batch, batch_size=1000, ignore_conflicts=True,
                    )
                    result.created += len(items_batch)
                    _update_progress(project, len(data), result.created, result.updated, result.failed)
                    items_batch = []
            if items_batch:
                InventoryItem.objects.unscoped().bulk_create(
                    items_batch, batch_size=1000, ignore_conflicts=True,
                )
                result.created += len(items_batch)

        # ── Bulk update u batchevima od 1000 ─────────────────────
        if to_update_pks:
            update_fields = [
                "name", "barcode", "unit_price", "purchase_price",
                "unit", "category", "description", "min_quantity", "location",
                "tax_rate",
            ]
            items_batch = []
            for pk, fields in to_update_pks.items():
                tax_obj = fields.pop("_tax_rate_obj", None)
                item = InventoryItem(pk=pk, company=company)
                for k, v in fields.items():
                    if k != "sku":
                        setattr(item, k, v)
                if tax_obj:
                    item.tax_rate = tax_obj
                items_batch.append(item)
                if len(items_batch) >= 1000:
                    InventoryItem.objects.unscoped().bulk_update(
                        items_batch, fields=update_fields, batch_size=1000,
                    )
                    result.updated += len(items_batch)
                    _update_progress(project, len(data), result.created, result.updated, result.failed)
                    items_batch = []
            if items_batch:
                InventoryItem.objects.unscoped().bulk_update(
                    items_batch, fields=update_fields, batch_size=1000,
                )
                result.updated += len(items_batch)

        self._save_logs(logs)
        _update_progress(project, len(data), result.created, result.updated, result.failed)
        return result

    # ── Pomocne metode ────────────────────────────────────────────

    def _build_tax_rate_map(self, company) -> dict:
        """Gradi mapu PDV stopa: Decimal(rate) → TaxRate objekt."""
        try:
            from companies.models import TaxRate
            # Dohvati drzavu tvrtke za filtriranje
            country = getattr(company, "country", "HR") or "HR"
            rates = {}
            for tr in TaxRate.objects.filter(country=country, is_active=True):
                rates[tr.rate] = tr
            # Fallback: dohvati sve HR stope ako nema rezultata
            if not rates:
                for tr in TaxRate.objects.filter(country="HR", is_active=True):
                    rates[tr.rate] = tr
            return rates
        except DatabaseError:
            return {}

    def _resolve_tax_rate(self, raw_value, tax_rate_map, row_idx, logs):
        """Razrjesava PDV stopu iz stringa u TaxRate objekt."""
        rate = _safe_decimal(raw_value)
        if rate in tax_rate_map:
            return tax_rate_map[rate]
        if tax_rate_map:
            closest = min(tax_rate_map.keys(), key=lambda r: abs(r - rate))
            if abs(closest - rate) <= 1:
                logs.append(("warning", row_idx, "tax_rate_value",
                             f"PDV stopa {rate}% nije pronadena — koristena {closest}%.",
                             str(rate), str(closest)))
                return tax_rate_map[closest]
        logs.append(("warning", row_idx, "tax_rate_value",
                     f"PDV stopa {rate}% nije pronadena u sustavu — polje ostavljeno prazno.",
                     str(rate), ""))
        return None

    def _save_logs(self, logs: list):
        """Sprema akumulirane logove u MigrationLog via bulk_create."""
        if not logs:
            return
        from data_migration.models import MigrationLog
        project = getattr(self, "_current_project", None)
        if not project:
            return

        log_objects = [
            MigrationLog(
                project=project,
                level=level,
                row_number=row,
                field_name=field,
                message=msg,
                original_value=orig[:500] if orig else "",
                resolved_value=resolved[:500] if resolved else "",
                entity_type=getattr(self, "_current_entity_type", ""),
            )
            for level, row, field, msg, orig, resolved in logs
        ]
        MigrationLog.objects.bulk_create(log_objects, batch_size=500)
