"""Smart Mailbox — Rule-Based Auto-Classification (Phase 1)."""
import logging
from datetime import date

from lxml import etree

from einvoice.models import InboundInvoice, MessageStatus

logger = logging.getLogger("propter.einvoice.mailbox")

UBL_NS = {
    "inv": "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
}


class SmartMailboxService:
    def process_incoming(self, message):
        ubl_data = self._parse_ubl(message.ubl_xml)

        inbound = InboundInvoice(
            company=message.company, as4_message=message,
            invoice_number=ubl_data["invoice_number"],
            issue_date=ubl_data["issue_date"],
            due_date=ubl_data.get("due_date"),
            currency=ubl_data.get("currency", "EUR"),
            supplier_name=ubl_data["supplier_name"],
            supplier_tax_id=ubl_data.get("supplier_tax_id", ""),
            supplier_address=ubl_data.get("supplier_address", ""),
            net_amount=ubl_data["net_amount"],
            tax_amount=ubl_data["tax_amount"],
            gross_amount=ubl_data["gross_amount"],
            tax_breakdown=ubl_data.get("tax_breakdown", []),
            line_items=ubl_data.get("line_items", []),
        )
        inbound.save()

        is_dup = inbound.check_duplicate()
        if is_dup:
            logger.warning(f"Duplicate: {inbound.invoice_number} from {inbound.supplier_name}")
            message.transition_to(MessageStatus.PROCESSED, detail="Duplikat detektiran")
            return inbound

        classification = self._classify(inbound)
        inbound.suggested_konto = classification["konto"]
        inbound.suggested_konto_name = classification["konto_name"]
        inbound.suggested_cost_center = classification.get("cost_center", "")
        inbound.suggested_vat_treatment = classification["vat_treatment"]
        inbound.classification_confidence = classification["confidence"]
        inbound.classification_reason = classification["reason"]
        inbound.status = InboundInvoice.ProcessingStatus.AUTO_CLASSIFIED
        inbound.save()

        message.transition_to(
            MessageStatus.PROCESSED,
            detail=f"Klasificirano: konto {classification['konto']} ({classification['confidence']:.0%})",
        )
        logger.info(f"Processed: {inbound.invoice_number} from {inbound.supplier_name} -> konto {classification['konto']}")
        return inbound

    def _parse_ubl(self, ubl_xml):
        content = ubl_xml.encode("utf-8") if isinstance(ubl_xml, str) else ubl_xml
        tree = etree.fromstring(content)

        def _text(xpath, default=""):
            el = tree.find(xpath, UBL_NS)
            return el.text.strip() if el is not None and el.text else default

        def _decimal(xpath, default=0.0):
            val = _text(xpath)
            try:
                return float(val) if val else default
            except (ValueError, TypeError):
                return default

        def _date_val(xpath):
            val = _text(xpath)
            if val:
                try:
                    return date.fromisoformat(val)
                except ValueError:
                    return None
            return None

        tax_breakdown = []
        for ts in tree.findall(".//cac:TaxTotal/cac:TaxSubtotal", UBL_NS):
            rate_el = ts.find("cac:TaxCategory/cbc:Percent", UBL_NS)
            base_el = ts.find("cbc:TaxableAmount", UBL_NS)
            amount_el = ts.find("cbc:TaxAmount", UBL_NS)
            if rate_el is not None:
                tax_breakdown.append({
                    "rate": float(rate_el.text or 0),
                    "base": float(base_el.text if base_el is not None else 0),
                    "amount": float(amount_el.text if amount_el is not None else 0),
                })

        line_items = []
        for line in tree.findall(".//cac:InvoiceLine", UBL_NS):
            line_items.append({
                "line_id": line.findtext("cbc:ID", namespaces=UBL_NS) or "",
                "name": line.findtext("cac:Item/cbc:Name", namespaces=UBL_NS) or "",
                "quantity": float(line.findtext("cbc:InvoicedQuantity", namespaces=UBL_NS) or 0),
                "amount": float(line.findtext("cbc:LineExtensionAmount", namespaces=UBL_NS) or 0),
            })

        addr_parts = []
        street = _text(".//cac:AccountingSupplierParty/cac:Party/cac:PostalAddress/cbc:StreetName")
        city = _text(".//cac:AccountingSupplierParty/cac:Party/cac:PostalAddress/cbc:CityName")
        postal = _text(".//cac:AccountingSupplierParty/cac:Party/cac:PostalAddress/cbc:PostalZone")
        if street: addr_parts.append(street)
        if postal and city: addr_parts.append(f"{postal} {city}")
        elif city: addr_parts.append(city)

        return {
            "invoice_number": _text("cbc:ID"),
            "issue_date": _date_val("cbc:IssueDate") or date.today(),
            "due_date": _date_val("cbc:DueDate"),
            "currency": _text("cbc:DocumentCurrencyCode", "EUR"),
            "supplier_name": _text(".//cac:AccountingSupplierParty/cac:Party/cac:PartyName/cbc:Name"),
            "supplier_tax_id": _text(".//cac:AccountingSupplierParty/cac:Party/cac:PartyTaxScheme/cbc:CompanyID"),
            "supplier_address": ", ".join(addr_parts),
            "net_amount": _decimal(".//cac:LegalMonetaryTotal/cbc:TaxExclusiveAmount"),
            "tax_amount": _decimal(".//cac:TaxTotal/cbc:TaxAmount"),
            "gross_amount": _decimal(".//cac:LegalMonetaryTotal/cbc:TaxInclusiveAmount"),
            "tax_breakdown": tax_breakdown,
            "line_items": line_items,
        }

    def _classify(self, inbound):
        confidence = 0.0
        konto = ""
        konto_name = ""
        vat_treatment = "FULL_DEDUCTION"
        reason = ""
        cost_center = ""

        # Rule 1: Supplier History
        previous = InboundInvoice.objects.filter(
            company=inbound.company, supplier_tax_id=inbound.supplier_tax_id,
            status=InboundInvoice.ProcessingStatus.BOOKED,
        ).exclude(final_konto="").order_by("-booked_at").first()

        if previous:
            konto = previous.final_konto
            konto_name = previous.suggested_konto_name
            cost_center = previous.final_cost_center
            confidence = 0.85
            reason = f"Isti dobavljac ({inbound.supplier_name}) prethodno proknjizen na konto {konto}"
            distinct = InboundInvoice.objects.filter(
                company=inbound.company, supplier_tax_id=inbound.supplier_tax_id,
                status=InboundInvoice.ProcessingStatus.BOOKED,
            ).exclude(final_konto="").values_list("final_konto", flat=True).distinct()
            if distinct.count() == 1:
                confidence = 0.95
                reason += " (uvijek isti konto)"

        # Rule 2: VAT Rate
        if not konto and inbound.tax_breakdown:
            rate = inbound.tax_breakdown[0].get("rate", 0)
            if rate == 0:
                vat_treatment = "EXEMPT"
                reason = "PDV stopa 0% - oslobodeno"
            elif rate == 5:
                konto, konto_name, confidence = "4011", "Nabava - snizena stopa 5%", 0.4
                reason = "PDV stopa 5% - hrana/lijekovi"
            elif rate == 13:
                konto, konto_name, confidence = "4012", "Nabava - snizena stopa 13%", 0.4
                reason = "PDV stopa 13% - ugostiteljstvo"
            elif rate == 25:
                konto, konto_name, confidence = "4010", "Nabava - standardna stopa 25%", 0.3
                reason = "PDV stopa 25% - standardna nabava"

        # Rule 3: Line Item Keywords
        if confidence < 0.5 and inbound.line_items:
            all_names = " ".join(item.get("name", "") for item in inbound.line_items).lower()
            keyword_map = {
                "ured": ("4030", "Uredski materijal", 0.6),
                "papir": ("4030", "Uredski materijal", 0.6),
                "toner": ("4030", "Uredski materijal", 0.6),
                "gorivo": ("4050", "Gorivo i prijevoz", 0.7),
                "benzin": ("4050", "Gorivo i prijevoz", 0.7),
                "struj": ("4040", "Energija", 0.7),
                "plin": ("4040", "Energija", 0.6),
                "najam": ("4060", "Najam prostora", 0.7),
                "telefo": ("4070", "Telekomunikacije", 0.7),
                "internet": ("4070", "Telekomunikacije", 0.7),
                "licen": ("4080", "Software i licence", 0.7),
                "softw": ("4080", "Software i licence", 0.7),
                "osiguran": ("4090", "Osiguranje", 0.7),
                "bankov": ("4100", "Bankovne usluge", 0.6),
            }
            best_match, best_conf = None, 0.0
            for kw, (k, kn, c) in keyword_map.items():
                if kw in all_names and c > best_conf:
                    best_match = (k, kn, c, kw)
                    best_conf = c
            if best_match:
                konto, konto_name, confidence = best_match[0], best_match[1], best_match[2]
                reason = f"Kljucna rijec '{best_match[3]}' pronadena u stavkama"

        # Rule 4: Default
        if not konto:
            konto, konto_name, confidence = "4099", "Ostali troskovi (neklasificirano)", 0.1
            reason = "Nije pronadeno pravilo - zadani konto"

        # VAT treatment for partial deduction
        if vat_treatment == "FULL_DEDUCTION" and inbound.tax_breakdown:
            rate = inbound.tax_breakdown[0].get("rate", 25)
            if rate == 0:
                vat_treatment = "EXEMPT"
            elif konto == "4050":
                vat_treatment = "PARTIAL_DEDUCTION"

        return {
            "konto": konto, "konto_name": konto_name,
            "cost_center": cost_center, "vat_treatment": vat_treatment,
            "confidence": confidence, "reason": reason,
        }
