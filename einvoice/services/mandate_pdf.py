"""
Generiranje PDF punomoći (Mandate) za e-Račun sustav.

Koristi ReportLab za generiranje profesionalnog PDF dokumenta
sukladno Zakonu o elektroničkom izdavanju računa (NN 47/2024).
"""
import io
import logging
from datetime import date

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
)

logger = logging.getLogger("propter.einvoice.mandate_pdf")

# ── Styles ───────────────────────────────────────────────────────────
_BASE_FONT = "Helvetica"
_BOLD_FONT = "Helvetica-Bold"


def _build_styles():
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        "MandateTitle",
        parent=styles["Title"],
        fontName=_BOLD_FONT,
        fontSize=16,
        leading=20,
        alignment=TA_CENTER,
        spaceAfter=4,
        textColor=colors.HexColor("#1a1a2e"),
    ))
    styles.add(ParagraphStyle(
        "MandateSubtitle",
        parent=styles["Normal"],
        fontName=_BASE_FONT,
        fontSize=9,
        leading=12,
        alignment=TA_CENTER,
        spaceAfter=16,
        textColor=colors.HexColor("#666666"),
    ))
    styles.add(ParagraphStyle(
        "SectionHeader",
        parent=styles["Heading2"],
        fontName=_BOLD_FONT,
        fontSize=11,
        leading=14,
        spaceBefore=14,
        spaceAfter=6,
        textColor=colors.HexColor("#1a1a2e"),
        borderWidth=0,
        borderPadding=0,
    ))
    styles.add(ParagraphStyle(
        "FieldLabel",
        parent=styles["Normal"],
        fontName=_BOLD_FONT,
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#444444"),
    ))
    styles.add(ParagraphStyle(
        "FieldValue",
        parent=styles["Normal"],
        fontName=_BASE_FONT,
        fontSize=10,
        leading=13,
        textColor=colors.HexColor("#111111"),
    ))
    styles.add(ParagraphStyle(
        "BodyText2",
        parent=styles["Normal"],
        fontName=_BASE_FONT,
        fontSize=10,
        leading=14,
        alignment=TA_JUSTIFY,
        spaceAfter=8,
        textColor=colors.HexColor("#222222"),
    ))
    styles.add(ParagraphStyle(
        "Footer",
        parent=styles["Normal"],
        fontName=_BASE_FONT,
        fontSize=7.5,
        leading=10,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#999999"),
    ))
    styles.add(ParagraphStyle(
        "SignatureLabel",
        parent=styles["Normal"],
        fontName=_BASE_FONT,
        fontSize=9,
        leading=12,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#555555"),
    ))
    return styles


# ── Mandate type labels ──────────────────────────────────────────────
MANDATE_TYPE_LABELS = {
    "full": "Potpuna punomo\u0107 (slanje i primanje e-Ra\u010duna)",
    "send": "Punomo\u0107 za slanje e-Ra\u010duna",
    "receive": "Punomo\u0107 za primanje e-Ra\u010duna",
}

MANDATE_TYPE_ACTION = {
    "full": "\u0161alje i prima",
    "send": "\u0161alje",
    "receive": "prima",
}


def _entity_table(label, name, oib, address, city, styles):
    """Build a two-column table for principal/agent data."""
    data = [
        [Paragraph("<b>Naziv:</b>", styles["FieldLabel"]),
         Paragraph(name or "—", styles["FieldValue"])],
        [Paragraph("<b>OIB:</b>", styles["FieldLabel"]),
         Paragraph(oib or "—", styles["FieldValue"])],
        [Paragraph("<b>Adresa:</b>", styles["FieldLabel"]),
         Paragraph(address or "—", styles["FieldValue"])],
        [Paragraph("<b>Grad:</b>", styles["FieldLabel"]),
         Paragraph(city or "—", styles["FieldValue"])],
    ]
    t = Table(data, colWidths=[3.2 * cm, 13 * cm])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (0, -1), 0),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8f9fa")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#dee2e6")),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#e9ecef")),
    ]))
    return t


def generate_mandate_pdf(mandate):
    """
    Generate a PDF punomoć document for the given Mandate instance.

    Returns:
        bytes: The PDF content as bytes.
    """
    buf = io.BytesIO()
    styles = _build_styles()

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        topMargin=2 * cm,
        bottomMargin=2.5 * cm,
        leftMargin=2.2 * cm,
        rightMargin=2.2 * cm,
        title="Punomo\u0107 za e-Ra\u010dun",
        author="LIMIT Connect",
    )

    elements = []

    # ── Header ───────────────────────────────────────────────────────
    elements.append(Paragraph(
        "PUNOMO\u0106 ZA SLANJE E-RA\u010cUNA",
        styles["MandateTitle"],
    ))
    elements.append(Paragraph(
        "Sukladno Zakonu o elektroni\u010dkom izdavanju ra\u010duna (NN 47/2024)",
        styles["MandateSubtitle"],
    ))
    elements.append(HRFlowable(
        width="100%", thickness=1, color=colors.HexColor("#1a1a2e"),
        spaceAfter=12,
    ))

    # ── Section 1: Opunomoćitelj ─────────────────────────────────────
    principal = mandate.principal_company
    elements.append(Paragraph(
        "1. OPUNOMO\u0106ITELJ (Principal — vlasnik OIB-a)",
        styles["SectionHeader"],
    ))
    elements.append(_entity_table(
        "Opunomo\u0107itelj",
        principal.name,
        mandate.principal_oib,
        principal.address,
        f"{principal.zip_code} {principal.city}".strip() if principal.zip_code else principal.city,
        styles,
    ))
    elements.append(Spacer(1, 6))

    # ── Section 2: Opunomoćenik ──────────────────────────────────────
    agent = mandate.agent_company
    elements.append(Paragraph(
        "2. OPUNOMO\u0106ENIK (Agent — posrednik)",
        styles["SectionHeader"],
    ))
    elements.append(_entity_table(
        "Opunomo\u0107enik",
        agent.name,
        mandate.agent_oib,
        agent.address,
        f"{agent.zip_code} {agent.city}".strip() if agent.zip_code else agent.city,
        styles,
    ))
    elements.append(Spacer(1, 6))

    # ── Section 3: Opseg punomoći ────────────────────────────────────
    mt = mandate.mandate_type
    elements.append(Paragraph(
        "3. OPSEG PUNOMO\u0106I",
        styles["SectionHeader"],
    ))
    elements.append(Paragraph(
        f"Tip punomo\u0107i: <b>{MANDATE_TYPE_LABELS.get(mt, mt)}</b>",
        styles["BodyText2"],
    ))
    elements.append(Spacer(1, 4))

    # ── Section 4: Valjanost ─────────────────────────────────────────
    elements.append(Paragraph(
        "4. VALJANOST",
        styles["SectionHeader"],
    ))
    valid_from_str = mandate.valid_from.strftime("%d.%m.%Y") if mandate.valid_from else "—"
    valid_until_str = (
        mandate.valid_until.strftime("%d.%m.%Y")
        if mandate.valid_until
        else "neograni\u010deno"
    )
    elements.append(Paragraph(
        f"Vrijedi od: <b>{valid_from_str}</b> &nbsp;&nbsp;&nbsp; "
        f"Vrijedi do: <b>{valid_until_str}</b>",
        styles["BodyText2"],
    ))
    elements.append(Spacer(1, 4))

    # ── Section 5: Izjava ────────────────────────────────────────────
    action = MANDATE_TYPE_ACTION.get(mt, "\u0161alje/prima")
    elements.append(Paragraph(
        "5. IZJAVA",
        styles["SectionHeader"],
    ))
    elements.append(Paragraph(
        f"Ovim putem opunomo\u0107ujem gore navedenog opunomo\u0107enika da u moje ime "
        f"i za moj ra\u010dun {action} e-Ra\u010dune putem sustava FINA e-Ra\u010dun.",
        styles["BodyText2"],
    ))
    elements.append(Paragraph(
        "Ova punomo\u0107 vrijedi za sve e-Ra\u010dune u navedenom razdoblju valjanosti, "
        "osim ako nije ranije opozvana pisanim putem.",
        styles["BodyText2"],
    ))
    elements.append(Spacer(1, 20))

    # ── Section 6: Potpis ────────────────────────────────────────────
    elements.append(Paragraph(
        "6. POTPIS",
        styles["SectionHeader"],
    ))
    elements.append(Spacer(1, 8))

    sig_data = [
        [
            Paragraph("Mjesto i datum:", styles["FieldLabel"]),
            Paragraph("_" * 40, styles["FieldValue"]),
        ],
        [
            Paragraph("", styles["FieldLabel"]),
            Paragraph("", styles["FieldValue"]),
        ],
        [
            Paragraph("", styles["FieldLabel"]),
            Paragraph("", styles["FieldValue"]),
        ],
        [
            Paragraph("Potpis opunomo\u0107itelja:", styles["SignatureLabel"]),
            Paragraph("Pe\u010dat:", styles["SignatureLabel"]),
        ],
        [
            Paragraph("_" * 35, styles["SignatureLabel"]),
            Paragraph("_" * 35, styles["SignatureLabel"]),
        ],
    ]
    sig_table = Table(sig_data, colWidths=[8.5 * cm, 8.5 * cm])
    sig_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ALIGN", (0, 3), (-1, -1), "CENTER"),
    ]))
    elements.append(sig_table)
    elements.append(Spacer(1, 30))

    # ── Footer ───────────────────────────────────────────────────────
    elements.append(HRFlowable(
        width="100%", thickness=0.5, color=colors.HexColor("#cccccc"),
        spaceAfter=6,
    ))
    elements.append(Paragraph(
        f"Generirano putem LIMIT Connect (limit-connect.com) — Ref: {mandate.id}",
        styles["Footer"],
    ))

    doc.build(elements)
    pdf_bytes = buf.getvalue()
    buf.close()

    logger.info("mandate_pdf generated for mandate=%s (%d bytes)", mandate.id, len(pdf_bytes))
    return pdf_bytes
