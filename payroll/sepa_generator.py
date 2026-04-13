"""
SEPA pain.001.001.03 Credit Transfer XML Generator
for Croatian payroll (salary) payments.

ISO 20022 namespace: urn:iso:std:iso:20022:tech:xsd:pain.001.001.03
"""

import uuid
import xml.etree.ElementTree as ET
from datetime import date, datetime
from decimal import Decimal

NAMESPACE = "urn:iso:std:iso:20022:tech:xsd:pain.001.001.03"


def generate_sepa_payroll(
    company_name,
    company_oib,
    company_iban,
    company_bic,
    payments,
    execution_date=None,
    msg_id=None,
):
    """
    Generate a SEPA pain.001.001.03 Credit Transfer XML for salary payments.

    Args:
        company_name: Debtor company name (e.g. "Konjik d.o.o.")
        company_oib: Croatian OIB of the company
        company_iban: Company IBAN (e.g. "HR1234567890123456789")
        company_bic: Company BIC/SWIFT code
        payments: List of dicts, each with keys:
            - employee_name (str)
            - iban (str)
            - bic (str)
            - amount (Decimal)
            - reference (str) e.g. "Placa 03/2026"
        execution_date: Requested execution date (date object). Defaults to today.
        msg_id: Message ID string. Auto-generated UUID if not provided.

    Returns:
        XML string with <?xml ...?> declaration.
    """
    if execution_date is None:
        execution_date = date.today()
    if msg_id is None:
        msg_id = uuid.uuid4().hex[:35]

    nb_of_txs = str(len(payments))
    ctrl_sum = sum(p["amount"] for p in payments)

    # Root element with namespace
    root = ET.Element("Document", xmlns=NAMESPACE)
    cstmr_cdt_trf_initn = ET.SubElement(root, "CstmrCdtTrfInitn")

    # --- Group Header (GrpHdr) ---
    grp_hdr = ET.SubElement(cstmr_cdt_trf_initn, "GrpHdr")
    ET.SubElement(grp_hdr, "MsgId").text = msg_id
    ET.SubElement(grp_hdr, "CreDtTm").text = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    ET.SubElement(grp_hdr, "NbOfTxs").text = nb_of_txs
    ET.SubElement(grp_hdr, "CtrlSum").text = f"{ctrl_sum:.2f}"

    initg_pty = ET.SubElement(grp_hdr, "InitgPty")
    ET.SubElement(initg_pty, "Nm").text = company_name
    initg_pty_id = ET.SubElement(initg_pty, "Id")
    initg_pty_org_id = ET.SubElement(initg_pty_id, "OrgId")
    initg_pty_othr = ET.SubElement(initg_pty_org_id, "Othr")
    ET.SubElement(initg_pty_othr, "Id").text = company_oib

    # --- Payment Information (PmtInf) ---
    pmt_inf = ET.SubElement(cstmr_cdt_trf_initn, "PmtInf")
    ET.SubElement(pmt_inf, "PmtInfId").text = f"PMT-{msg_id[:20]}"
    ET.SubElement(pmt_inf, "PmtMtd").text = "TT"
    ET.SubElement(pmt_inf, "NbOfTxs").text = nb_of_txs
    ET.SubElement(pmt_inf, "CtrlSum").text = f"{ctrl_sum:.2f}"

    pmt_tp_inf = ET.SubElement(pmt_inf, "PmtTpInf")
    svc_lvl = ET.SubElement(pmt_tp_inf, "SvcLvl")
    ET.SubElement(svc_lvl, "Cd").text = "SEPA"
    ctgy_purp = ET.SubElement(pmt_tp_inf, "CtgyPurp")
    ET.SubElement(ctgy_purp, "Cd").text = "SALA"

    ET.SubElement(pmt_inf, "ReqdExctnDt").text = execution_date.strftime("%Y-%m-%d")

    # Debtor (company)
    dbtr = ET.SubElement(pmt_inf, "Dbtr")
    ET.SubElement(dbtr, "Nm").text = company_name
    dbtr_id = ET.SubElement(dbtr, "Id")
    dbtr_org_id = ET.SubElement(dbtr_id, "OrgId")
    dbtr_othr = ET.SubElement(dbtr_org_id, "Othr")
    ET.SubElement(dbtr_othr, "Id").text = company_oib

    # Debtor Account
    dbtr_acct = ET.SubElement(pmt_inf, "DbtrAcct")
    dbtr_acct_id = ET.SubElement(dbtr_acct, "Id")
    ET.SubElement(dbtr_acct_id, "IBAN").text = company_iban
    ET.SubElement(dbtr_acct, "Ccy").text = "EUR"

    # Debtor Agent (BIC)
    dbtr_agt = ET.SubElement(pmt_inf, "DbtrAgt")
    dbtr_agt_fin_inst = ET.SubElement(dbtr_agt, "FinInstnId")
    ET.SubElement(dbtr_agt_fin_inst, "BIC").text = company_bic

    ET.SubElement(pmt_inf, "ChrgBr").text = "SLEV"

    # --- Credit Transfer Transaction Information (per employee) ---
    for i, pmt in enumerate(payments, start=1):
        cdt_trf = ET.SubElement(pmt_inf, "CdtTrfTxInf")

        pmt_id = ET.SubElement(cdt_trf, "PmtId")
        ET.SubElement(pmt_id, "EndToEndId").text = pmt.get("end_to_end_id", f"{msg_id[:25]}-{i}")

        amt = ET.SubElement(cdt_trf, "Amt")
        instd_amt = ET.SubElement(amt, "InstdAmt", Ccy="EUR")
        instd_amt.text = f"{pmt['amount']:.2f}"

        cdtr_agt = ET.SubElement(cdt_trf, "CdtrAgt")
        cdtr_agt_fin_inst = ET.SubElement(cdtr_agt, "FinInstnId")
        ET.SubElement(cdtr_agt_fin_inst, "BIC").text = pmt["bic"]

        cdtr = ET.SubElement(cdt_trf, "Cdtr")
        ET.SubElement(cdtr, "Nm").text = pmt["employee_name"]

        cdtr_acct = ET.SubElement(cdt_trf, "CdtrAcct")
        cdtr_acct_id = ET.SubElement(cdtr_acct, "Id")
        ET.SubElement(cdtr_acct_id, "IBAN").text = pmt["iban"]

        rmt_inf = ET.SubElement(cdt_trf, "RmtInf")
        ET.SubElement(rmt_inf, "Ustrd").text = pmt["reference"]

    # Serialize to string with XML declaration
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")

    xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml_body = ET.tostring(root, encoding="unicode")
    return xml_declaration + xml_body


def generate_sepa_from_payroll_run(company, payroll_run, payslips):
    """
    Build a SEPA pain.001.001.03 XML from Django model instances.

    Args:
        company: Django model with .name, .oib, .iban, .bic attributes.
        payroll_run: Django model with .month (int), .year (int) attributes.
        payslips: Iterable of payslip Django models, each with:
            - .user (Django User with get_full_name())
            - .employee_iban (str)
            - .net_amount (Decimal)

    Returns:
        XML string with <?xml ...?> declaration.
    """
    reference = f"Placa {payroll_run.month:02d}/{payroll_run.year}"

    payments = []
    for ps in payslips:
        payments.append(
            {
                "employee_name": ps.user.get_full_name(),
                "iban": ps.employee_iban,
                "bic": getattr(ps, "employee_bic", company.bic),
                "amount": ps.net_amount,
                "reference": reference,
            }
        )

    return generate_sepa_payroll(
        company_name=company.name,
        company_oib=company.oib,
        company_iban=company.iban,
        company_bic=company.bic,
        payments=payments,
    )


if __name__ == "__main__":
    # Example usage
    payments = [
        {
            "employee_name": "Ivan Horvat",
            "iban": "HR1210010051863000160",
            "bic": "ZABAHR2X",
            "amount": Decimal("1250.00"),
            "reference": "Placa 03/2026",
        },
        {
            "employee_name": "Ana Kovacevic",
            "iban": "HR3623400091110654321",
            "bic": "PBZGHR2X",
            "amount": Decimal("1480.50"),
            "reference": "Placa 03/2026",
        },
    ]

    xml = generate_sepa_payroll(
        company_name="Konjik d.o.o.",
        company_oib="37590751921",
        company_iban="HR1210010051863000160",
        company_bic="ZABAHR2X",
        payments=payments,
        execution_date=date(2026, 3, 15),
    )

    print(xml)
