"""
evalidator/invoice_service.py — Standalone e-Invoice generator
Radi s plain dict-ima, bez Django modela.
Kopiran i prilagođen iz Fenix V3 UBLInvoiceGenerator.

Podržava:
  - UBL 2.1 / EN 16931 / PEPPOL BIS 3.0 XML
  - Jezici: hr / de / en
  - Tipovi: INV (račun), OFF (ponuda), CRD (odobrenje/storno)
  - PDV stope: 25% / 13% / 5% / 0%
"""
import hashlib
import logging
import uuid
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO
from xml.etree import ElementTree as ET

logger = logging.getLogger("fenix.evalidator.invoice")

# ── UBL 2.1 Namespaces ────────────────────────────────────────────────────
_NS = {
    "":    "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
}
for _pfx, _uri in _NS.items():
    ET.register_namespace(_pfx or "ubl", _uri)

_UBL = _NS[""]
_CAC = _NS["cac"]
_CBC = _NS["cbc"]


def _q(ns, tag):
    return f"{{{ns}}}{tag}"


def _cbc(tag, text, **attrs):
    el = ET.Element(_q(_CBC, tag), attrib=attrs)
    el.text = str(text) if text is not None else ""
    return el


def _cac(tag):
    return ET.Element(_q(_CAC, tag))


def _d2(v) -> str:
    return str(Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


# ── Računanje stavki ──────────────────────────────────────────────────────

def compute_item(item: dict) -> dict:
    """
    Izračunaj sve iznose za jednu stavku.
    Ulaz: {description, quantity, unit, unit_price, discount_percent, tax_rate}
    """
    qty       = Decimal(str(item.get("quantity", 1)))
    price     = Decimal(str(item.get("unit_price", 0)))
    disc      = Decimal(str(item.get("discount_percent", 0)))
    tax_rate  = Decimal(str(item.get("tax_rate", 25)))

    gross     = qty * price
    discount  = (gross * disc / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    subtotal  = (gross - discount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    tax_amt   = (subtotal * tax_rate / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    total     = subtotal + tax_amt

    return {
        **item,
        "qty":           qty,
        "price":         price,
        "disc":          disc,
        "subtotal":      subtotal,
        "tax_amount":    tax_amt,
        "total":         total,
        "tax_rate":      tax_rate,
    }


def compute_totals(items: list) -> dict:
    """Agregiraj totale po stavkama."""
    from collections import defaultdict
    groups = defaultdict(lambda: {"taxable": Decimal(0), "tax": Decimal(0)})

    subtotal   = Decimal(0)
    tax_total  = Decimal(0)

    for it in items:
        subtotal  += it["subtotal"]
        tax_total += it["tax_amount"]
        rate = str(it["tax_rate"])
        groups[rate]["taxable"] += it["subtotal"]
        groups[rate]["tax"]     += it["tax_amount"]

    total = subtotal + tax_total
    return {
        "subtotal":    subtotal.quantize(Decimal("0.01")),
        "tax_total":   tax_total.quantize(Decimal("0.01")),
        "total":       total.quantize(Decimal("0.01")),
        "tax_groups":  {k: {kk: vv.quantize(Decimal("0.01")) for kk, vv in v.items()} for k, v in groups.items()},
    }


# ── UBL XML Generator ─────────────────────────────────────────────────────

_UNIT_MAP = {
    "kom": "C62", "pcs": "C62", "St":  "C62",
    "sat": "HUR", "h":   "HUR", "Std": "HUR",
    "dan": "DAY", "Tag": "DAY",
    "mj":  "MON", "Mon": "MON",
    "m":   "MTR", "m2":  "MTK", "m3":  "MTQ",
    "kg":  "KGM", "L":   "LTR",
    "paus":"C62", "usl": "C62", "Psch":"C62",
}

_TYPE_CODE = {"INV": "380", "OFF": "380", "PRO": "386", "CRD": "381"}
_PAY_CODE  = {"T": "30", "G": "10", "K": "48", "O": "1"}


def build_ubl_xml(data: dict, items: list, totals: dict) -> bytes:
    """
    Generiraj UBL 2.1 XML bytes iz dict-ova.

    data: {
      doc_type, number, issue_date, due_date, currency,
      note, payment_method,
      seller_name, seller_oib, seller_vat_id, seller_address, seller_city,
      seller_email, seller_iban, seller_bic,
      buyer_name, buyer_oib, buyer_address, buyer_city, buyer_country,
    }
    items: [computed_item(), ...]
    totals: compute_totals(items)
    """
    cur = data.get("currency", "EUR")
    doc_type = data.get("doc_type", "INV")

    root = ET.Element(_q(_UBL, "Invoice"))
    root.append(_cbc("UBLVersionID", "2.1"))
    root.append(_cbc("CustomizationID",
        "urn:cen.eu:en16931:2017#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0"))
    root.append(_cbc("ProfileID",
        "urn:fdc:peppol.eu:2017:poacc:billing:01:1.0"))
    root.append(_cbc("ID", data.get("number", "1")))
    root.append(_cbc("IssueDate", data.get("issue_date", date.today().isoformat())))
    if data.get("due_date"):
        root.append(_cbc("DueDate", data["due_date"]))
    root.append(_cbc("InvoiceTypeCode", _TYPE_CODE.get(doc_type, "380")))
    root.append(_cbc("DocumentCurrencyCode", cur))
    if data.get("note"):
        root.append(_cbc("Note", data["note"]))

    # ── Supplier ──
    sup = _cac("AccountingSupplierParty")
    sp = _cac("Party")
    pn = _cac("PartyName"); pn.append(_cbc("Name", data.get("seller_name", ""))); sp.append(pn)
    addr = _cac("PostalAddress")
    addr.append(_cbc("StreetName", data.get("seller_address", "")))
    if data.get("seller_city"):
        addr.append(_cbc("CityName", data["seller_city"]))
    cnt = _cac("Country"); cnt.append(_cbc("IdentificationCode", data.get("seller_country", "HR"))); addr.append(cnt)
    sp.append(addr)
    vat_id = data.get("seller_vat_id") or ("HR" + data["seller_oib"] if data.get("seller_oib") else "")
    if vat_id:
        ts = _cac("PartyTaxScheme")
        ts.append(_cbc("CompanyID", vat_id))
        sc = _cac("TaxScheme"); sc.append(_cbc("ID", "VAT")); ts.append(sc)
        sp.append(ts)
    le = _cac("PartyLegalEntity")
    le.append(_cbc("RegistrationName", data.get("seller_name", "")))
    if data.get("seller_oib"):
        le.append(_cbc("CompanyID", data["seller_oib"], schemeID="9918"))
    sp.append(le)
    sup.append(sp); root.append(sup)

    # ── Customer ──
    cus = _cac("AccountingCustomerParty")
    cp = _cac("Party")
    cpn = _cac("PartyName"); cpn.append(_cbc("Name", data.get("buyer_name", ""))); cp.append(cpn)
    baddr = _cac("PostalAddress")
    baddr.append(_cbc("StreetName", data.get("buyer_address", "")))
    if data.get("buyer_city"):
        baddr.append(_cbc("CityName", data["buyer_city"]))
    bcnt = _cac("Country"); bcnt.append(_cbc("IdentificationCode", data.get("buyer_country", "HR"))); baddr.append(bcnt)
    cp.append(baddr)
    if data.get("buyer_oib"):
        bts = _cac("PartyTaxScheme")
        bts.append(_cbc("CompanyID", "HR" + data["buyer_oib"]))
        bsc = _cac("TaxScheme"); bsc.append(_cbc("ID", "VAT")); bts.append(bsc)
        cp.append(bts)
        ble = _cac("PartyLegalEntity")
        ble.append(_cbc("RegistrationName", data.get("buyer_name", "")))
        ble.append(_cbc("CompanyID", data["buyer_oib"], schemeID="9918"))
        cp.append(ble)
    cus.append(cp); root.append(cus)

    # ── PaymentMeans ──
    pm = _cac("PaymentMeans")
    pm.append(_cbc("PaymentMeansCode", _PAY_CODE.get(data.get("payment_method", "T"), "30")))
    if data.get("due_date"):
        pm.append(_cbc("PaymentDueDate", data["due_date"]))
    if data.get("seller_iban"):
        acc = _cac("PayeeFinancialAccount")
        acc.append(_cbc("ID", data["seller_iban"].replace(" ", "")))
        if data.get("seller_bic"):
            br = _cac("FinancialInstitutionBranch")
            fi = _cac("FinancialInstitution"); fi.append(_cbc("ID", data["seller_bic"])); br.append(fi)
            acc.append(br)
        pm.append(acc)
    root.append(pm)

    # ── TaxTotal ──
    tt = _cac("TaxTotal")
    tt.append(_cbc("TaxAmount", _d2(totals["tax_total"]), currencyID=cur))
    for rate_str, grp in sorted(totals["tax_groups"].items(), key=lambda x: -Decimal(x[0])):
        tst = _cac("TaxSubtotal")
        tst.append(_cbc("TaxableAmount", _d2(grp["taxable"]), currencyID=cur))
        tst.append(_cbc("TaxAmount",     _d2(grp["tax"]),     currencyID=cur))
        cat = _cac("TaxCategory")
        r = Decimal(rate_str)
        code = "S" if r >= 20 else ("AA" if r > 0 else "Z")
        cat.append(_cbc("ID", code))
        cat.append(_cbc("Percent", rate_str))
        sc2 = _cac("TaxScheme"); sc2.append(_cbc("ID", "VAT")); cat.append(sc2)
        tst.append(cat); tt.append(tst)
    root.append(tt)

    # ── MonetaryTotal ──
    mt = _cac("LegalMonetaryTotal")
    mt.append(_cbc("LineExtensionAmount", _d2(totals["subtotal"]),  currencyID=cur))
    mt.append(_cbc("TaxExclusiveAmount",  _d2(totals["subtotal"]),  currencyID=cur))
    mt.append(_cbc("TaxInclusiveAmount",  _d2(totals["total"]),     currencyID=cur))
    mt.append(_cbc("PayableAmount",       _d2(totals["total"]),     currencyID=cur))
    root.append(mt)

    # ── InvoiceLines ──
    for idx, item in enumerate(items, 1):
        line = _cac("InvoiceLine")
        line.append(_cbc("ID", str(idx)))
        unit_code = _UNIT_MAP.get(item.get("unit", "kom"), "C62")
        line.append(_cbc("InvoicedQuantity", _d2(item["qty"]), unitCode=unit_code))
        line.append(_cbc("LineExtensionAmount", _d2(item["subtotal"]), currencyID=cur))

        itel = _cac("Item")
        itel.append(_cbc("Description", item.get("description", "")))
        itel.append(_cbc("Name", (item.get("description", ""))[:100]))
        cat2 = _cac("ClassifiedTaxCategory")
        r2 = item["tax_rate"]
        code2 = "S" if r2 >= 20 else ("AA" if r2 > 0 else "Z")
        cat2.append(_cbc("ID", code2))
        cat2.append(_cbc("Percent", str(r2)))
        sc3 = _cac("TaxScheme"); sc3.append(_cbc("ID", "VAT")); cat2.append(sc3)
        itel.append(cat2)
        line.append(itel)

        price_el = _cac("Price")
        price_el.append(_cbc("PriceAmount", _d2(item["price"]), currencyID=cur))
        if item.get("disc") and item["disc"] > 0:
            alw = _cac("AllowanceCharge")
            alw.append(_cbc("ChargeIndicator", "false"))
            alw.append(_cbc("MultiplierFactorNumeric", str(item["disc"] / 100)))
            alw.append(_cbc("Amount", _d2(item["qty"] * item["price"] * item["disc"] / 100), currencyID=cur))
            price_el.append(alw)
        line.append(price_el)
        root.append(line)

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    buf = BytesIO()
    tree.write(buf, xml_declaration=True, encoding="UTF-8")
    return buf.getvalue()


# ── PDF Generator ─────────────────────────────────────────────────────────

_LABELS = {
    "hr": {
        "INV": "RAČUN",    "OFF": "PONUDA",   "CRD": "ODOBRENJE", "PRO": "PREDRAČUN",
        "seller": "Izdavatelj", "buyer": "Primatelj",
        "pos": "Pos.", "desc": "Opis", "qty": "Kol.", "unit": "Jed.",
        "price": "Jed. cijena", "disc": "Pop.%", "amount": "Iznos",
        "subtotal": "Osnovica", "tax": "PDV", "total": "UKUPNO",
        "payment": "Podaci za plaćanje", "iban": "IBAN", "bic": "BIC",
        "ref": "Poziv na broj", "due": "Rok plaćanja",
        "date": "Datum izdavanja", "due_label": "Rok plaćanja",
        "tax_id": "OIB", "currency": "Valuta",
        "note_label": "Napomena",
        "footer": "eValidator.eu · Besplatni EU e-Račun generator · EN 16931 / PEPPOL BIS 3.0",
        "generated_by": "Generirano putem evalidator.eu",
        "verify": "Provjeri pečat",
    },
    "de": {
        "INV": "RECHNUNG", "OFF": "ANGEBOT", "CRD": "GUTSCHRIFT", "PRO": "PROFORMARECHNUNG",
        "seller": "Auftragnehmer", "buyer": "Auftraggeber",
        "pos": "Pos.", "desc": "Beschreibung", "qty": "Menge", "unit": "Einh.",
        "price": "Einzelpreis", "disc": "Rabatt", "amount": "Betrag",
        "subtotal": "Nettobetrag", "tax": "MwSt.", "total": "GESAMT",
        "payment": "Zahlungsinformationen", "iban": "IBAN", "bic": "BIC",
        "ref": "Verwendungszweck", "due": "Fällig bis",
        "date": "Rechnungsdatum", "due_label": "Fälligkeitsdatum",
        "tax_id": "Steuer-Nr.", "currency": "Währung",
        "note_label": "Hinweis",
        "footer": "eValidator.eu · Kostenloser EU E-Rechnung Generator · EN 16931 / PEPPOL BIS 3.0",
        "generated_by": "Erstellt via evalidator.eu",
        "verify": "Siegel prüfen",
    },
    "en": {
        "INV": "INVOICE",  "OFF": "QUOTE",    "CRD": "CREDIT NOTE", "PRO": "PROFORMA",
        "seller": "From", "buyer": "To",
        "pos": "Pos.", "desc": "Description", "qty": "Qty", "unit": "Unit",
        "price": "Unit price", "disc": "Disc%", "amount": "Amount",
        "subtotal": "Subtotal", "tax": "VAT", "total": "TOTAL",
        "payment": "Payment details", "iban": "IBAN", "bic": "BIC",
        "ref": "Reference", "due": "Due date",
        "date": "Issue date", "due_label": "Due date",
        "tax_id": "Tax ID", "currency": "Currency",
        "note_label": "Note",
        "footer": "eValidator.eu · Free EU e-Invoice Generator · EN 16931 / PEPPOL BIS 3.0",
        "generated_by": "Generated via evalidator.eu",
        "verify": "Verify seal",
    },
}


def build_pdf(data: dict, items: list, totals: dict, lang: str = "hr",
              seal_token: str = None, seal_qr_b64: str = None) -> bytes:
    """
    Generiraj PDF račun putem WeasyPrint.
    Vraća bytes.
    """
    from django.template.loader import render_to_string
    import weasyprint

    L = _LABELS.get(lang, _LABELS["hr"])
    doc_type = data.get("doc_type", "INV")

    context = {
        "data":       data,
        "items":      items,
        "totals":     totals,
        "L":          L,
        "doc_type_label": L.get(doc_type, doc_type),
        "lang":       lang,
        "seal_token":   seal_token,
        "seal_qr_b64":  seal_qr_b64,
        "verify_base":  "https://evalidator.eu/verify/",
    }

    html = render_to_string("evalidator/invoice/pdf_modern.html", context)
    return weasyprint.HTML(string=html, base_url="https://evalidator.eu/").write_pdf()


def make_filename(data: dict) -> str:
    num = data.get("number", "1").replace("/", "-").replace(" ", "_")
    doc = data.get("doc_type", "INV")
    return f"eValidaTor_{doc}_{num}"
