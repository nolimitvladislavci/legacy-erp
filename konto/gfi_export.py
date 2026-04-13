"""
konto/gfi_export.py
GFI-POD (Godisnji financijski izvjestaj - Podaci o dobiti) export.

Generates balance sheet (bilanca) + profit/loss (RDG) data mapped to
official AOP positions per Croatian Financial Agency (FINA) requirements.
"""
import datetime
import logging
import xml.etree.ElementTree as ET
from decimal import Decimal
from xml.dom import minidom

logger = logging.getLogger(__name__)


# AOP MAPPING - Bilanca (Balance Sheet)
BILANCA_AOP_MAP = {
    "001": {"name": "UKUPNO AKTIVA",             "codes": ["0", "1", "2", "3"]},
    "002": {"name": "Dugotrajna imovina",         "codes": ["0"]},
    "003": {"name": "Nematerijalna imovina",      "codes": ["00", "01"]},
    "009": {"name": "Materijalna imovina",        "codes": ["02", "03"]},
    "020": {"name": "Dugotrajna financ. imovina", "codes": ["06", "07"]},
    "030": {"name": "Kratkotrajna imovina",       "codes": ["1", "2", "3"]},
    "031": {"name": "Zalihe",                     "codes": ["30", "31", "32", "33"]},
    "040": {"name": "Potrazivanja",               "codes": ["12", "13", "14", "15"]},
    "050": {"name": "Kratkotrajna financ. imovina","codes": ["16", "17", "18", "19"]},
    "058": {"name": "Novac u banci i blagajni",   "codes": ["10", "11"]},
    "063": {"name": "Placeni troskovi bud. razd.", "codes": ["09"]},
    "064": {"name": "UKUPNO PASIVA",              "codes": ["9", "4", "2"]},
    "065": {"name": "Kapital i rezerve",          "codes": ["90", "91", "92", "93", "94", "95"]},
    "066": {"name": "Temeljni (upisani) kapital", "codes": ["90"]},
    "076": {"name": "Zadrzana dobit/gubitak",     "codes": ["94"]},
    "078": {"name": "Dobit/gubitak poslovne godine","codes": ["__computed__"]},
    "080": {"name": "Dugorocne obveze",           "codes": ["44", "45", "46", "47", "48"]},
    "090": {"name": "Kratkorocne obveze",         "codes": ["20", "21", "22", "23", "24", "25", "26", "27", "28", "29"]},
    "104": {"name": "Odgodjeno placanje troskova", "codes": ["49"]},
}

# AOP MAPPING - RDG (Racun dobiti i gubitka / P&L)
RDG_AOP_MAP = {
    "110": {"name": "Poslovni prihodi",           "codes": ["70", "71", "72", "73", "74", "75"]},
    "111": {"name": "Prihodi od prodaje",          "codes": ["70", "71"]},
    "118": {"name": "Ostali poslovni prihodi",     "codes": ["72", "73", "74", "75"]},
    "119": {"name": "Poslovni rashodi",            "codes": ["40", "41", "42", "43", "44", "45", "46", "47"]},
    "120": {"name": "Mat. troskovi i troskovi prod.robe", "codes": ["40", "41"]},
    "125": {"name": "Troskovi osoblja",            "codes": ["42", "43"]},
    "126": {"name": "Neto place",                  "codes": ["420"]},
    "127": {"name": "Troskovi poreza i doprinosa", "codes": ["421", "422"]},
    "130": {"name": "Amortizacija",                "codes": ["43"]},
    "133": {"name": "Ostali troskovi",             "codes": ["44", "45", "46", "47"]},
    "143": {"name": "Financijski prihodi",         "codes": ["76", "77", "78"]},
    "150": {"name": "Financijski rashodi",         "codes": ["48", "49"]},
    "155": {"name": "Ukupni prihodi",              "codes": ["7"]},
    "156": {"name": "Ukupni rashodi",              "codes": ["4", "5", "6"]},
    "160": {"name": "Dobit prije oporezivanja",   "codes": ["__computed__"]},
    "163": {"name": "Porez na dobit",              "codes": ["__computed__"]},
    "167": {"name": "Dobit razdoblja",             "codes": ["__computed__"]},
}


def generate_gfi_pod(company, year):
    """
    Generate GFI-POD data for a company and fiscal year.

    Returns dict with keys: bilanca, rdg, meta, xml
    """
    from django.db.models import Sum

    from konto.models import KontoAccount, LedgerLine

    current_start = datetime.date(year, 1, 1)
    current_end = datetime.date(year, 12, 31)
    prev_start = datetime.date(year - 1, 1, 1)
    prev_end = datetime.date(year - 1, 12, 31)

    def _sum_accounts_balance(code_prefixes, date_from, date_to, balance_type="balance_sheet"):
        total = Decimal("0")
        for prefix in code_prefixes:
            if prefix == "__computed__":
                continue
            accounts = KontoAccount.objects.filter(
                company=company, code__startswith=prefix, is_active=True
            )
            for acct in accounts:
                if balance_type == "balance_sheet":
                    lines = LedgerLine.objects.filter(
                        account=acct,
                        journal_entry__date__lte=date_to,
                        journal_entry__is_posted=True,
                    )
                else:
                    lines = LedgerLine.objects.filter(
                        account=acct,
                        journal_entry__date__gte=date_from,
                        journal_entry__date__lte=date_to,
                        journal_entry__is_posted=True,
                    )
                debits = lines.filter(side="debit").aggregate(t=Sum("amount"))["t"] or Decimal("0")
                credits = lines.filter(side="credit").aggregate(t=Sum("amount"))["t"] or Decimal("0")
                if acct.account_type in ("asset", "expense"):
                    total += debits - credits
                else:
                    total += credits - debits
        return total

    # Build bilanca
    bilanca = {}
    for aop, spec in BILANCA_AOP_MAP.items():
        if "__computed__" in spec["codes"]:
            continue
        current = _sum_accounts_balance(spec["codes"], current_start, current_end, "balance_sheet")
        previous = _sum_accounts_balance(spec["codes"], prev_start, prev_end, "balance_sheet")
        bilanca[aop] = {
            "name": spec["name"],
            "current": float(current),
            "previous": float(previous),
        }

    # Build RDG
    rdg = {}
    for aop, spec in RDG_AOP_MAP.items():
        if "__computed__" in spec["codes"]:
            continue
        current = _sum_accounts_balance(spec["codes"], current_start, current_end, "pnl")
        previous = _sum_accounts_balance(spec["codes"], prev_start, prev_end, "pnl")
        rdg[aop] = {
            "name": spec["name"],
            "current": float(abs(current)),
            "previous": float(abs(previous)),
        }

    # Computed fields
    total_income_cur = rdg.get("155", {}).get("current", 0)
    total_expense_cur = rdg.get("156", {}).get("current", 0)
    total_income_prev = rdg.get("155", {}).get("previous", 0)
    total_expense_prev = rdg.get("156", {}).get("previous", 0)

    profit_before_tax_cur = total_income_cur - total_expense_cur
    profit_before_tax_prev = total_income_prev - total_expense_prev

    tax_rate = Decimal("0.18") if getattr(company, "country", "HR") == "HR" else Decimal("0.15")
    tax_cur = float(max(Decimal(str(profit_before_tax_cur)) * tax_rate, 0))
    tax_prev = float(max(Decimal(str(profit_before_tax_prev)) * tax_rate, 0))

    rdg["160"] = {"name": "Dobit prije oporezivanja", "current": profit_before_tax_cur, "previous": profit_before_tax_prev}
    rdg["163"] = {"name": "Porez na dobit", "current": tax_cur, "previous": tax_prev}
    rdg["167"] = {"name": "Dobit razdoblja", "current": profit_before_tax_cur - tax_cur, "previous": profit_before_tax_prev - tax_prev}

    bilanca["078"] = {
        "name": "Dobit/gubitak poslovne godine",
        "current": rdg["167"]["current"],
        "previous": rdg["167"]["previous"],
    }

    meta = {
        "company_name": company.name,
        "oib": getattr(company, "oib", ""),
        "year": year,
        "generated_at": datetime.datetime.now().isoformat(),
        "currency": "EUR",
    }

    xml_str = _generate_gfi_xml(meta, bilanca, rdg)

    return {
        "bilanca": bilanca,
        "rdg": rdg,
        "meta": meta,
        "xml": xml_str,
    }


def _generate_gfi_xml(meta, bilanca, rdg):
    """Generate GFI-POD XML document."""
    root = ET.Element("GFI-POD")
    root.set("xmlns", "http://rgfi.fina.hr/sheme/gfi-pod")
    root.set("verzija", "2024.1")

    header = ET.SubElement(root, "Zaglavlje")
    ET.SubElement(header, "OIB").text = meta.get("oib", "")
    ET.SubElement(header, "NazivObveznika").text = meta.get("company_name", "")
    ET.SubElement(header, "RazdobljeOd").text = f"{meta['year']}-01-01"
    ET.SubElement(header, "RazdobljeDo").text = f"{meta['year']}-12-31"
    ET.SubElement(header, "DatumSastavljanja").text = datetime.date.today().isoformat()

    bil_elem = ET.SubElement(root, "Bilanca")
    for aop, data in sorted(bilanca.items()):
        pos = ET.SubElement(bil_elem, "Pozicija")
        ET.SubElement(pos, "AOP").text = aop
        ET.SubElement(pos, "Naziv").text = data["name"]
        ET.SubElement(pos, "TekucaGodina").text = f"{data['current']:.2f}"
        ET.SubElement(pos, "PrethodnaGodina").text = f"{data['previous']:.2f}"

    rdg_elem = ET.SubElement(root, "RacunDobitiGubitka")
    for aop, data in sorted(rdg.items()):
        pos = ET.SubElement(rdg_elem, "Pozicija")
        ET.SubElement(pos, "AOP").text = aop
        ET.SubElement(pos, "Naziv").text = data["name"]
        ET.SubElement(pos, "TekucaGodina").text = f"{data['current']:.2f}"
        ET.SubElement(pos, "PrethodnaGodina").text = f"{data['previous']:.2f}"

    raw = ET.tostring(root, encoding="unicode")
    xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n' + raw
    try:
        dom = minidom.parseString(xml_str)
        xml_str = dom.toprettyxml(indent="  ")
    except Exception:
        pass

    return xml_str
