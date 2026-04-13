"""
Forenzika Zaliha — InventoryLedger.xml generator.
Mjesečni snapshot cijelog inventara — potpisan dokaz za Poreznu.
"""
import xml.etree.ElementTree as ET
from xml.dom import minidom
from decimal import Decimal
from django.utils import timezone


class InventoryLedgerGenerator:
    """Generira InventoryLedger.xml za GovExport pipeline."""

    NS = 'urn:limit-connect:inventory-ledger:v1.0'

    def generate(self, export):
        from inventory.models import InventoryItem, StockMovement, StockBatch

        company = export.company
        root = ET.Element('InventoryLedger', xmlns=self.NS)
        root.set('version', '1.0')
        root.set('generated', timezone.now().isoformat())

        issuer = ET.SubElement(root, 'Issuer')
        ET.SubElement(issuer, 'Name').text = company.name
        ET.SubElement(issuer, 'OIB').text = company.oib or ''

        period = ET.SubElement(root, 'Period')
        ET.SubElement(period, 'From').text = export.period_start.isoformat()
        ET.SubElement(period, 'To').text = export.period_end.isoformat()

        # Snapshot svih artikala
        items = InventoryItem.objects.filter(company=company, is_active=True)
        items_el = ET.SubElement(root, 'Items', count=str(items.count()))

        total_value = Decimal('0')
        for item in items:
            i_el = ET.SubElement(items_el, 'Item', id=str(item.pk))
            ET.SubElement(i_el, 'SKU').text = item.sku
            ET.SubElement(i_el, 'Name').text = item.name
            ET.SubElement(i_el, 'Unit').text = item.unit
            ET.SubElement(i_el, 'Quantity').text = str(item.quantity)
            ET.SubElement(i_el, 'UnitPrice').text = str(item.unit_price or 0)
            ET.SubElement(i_el, 'PurchasePrice').text = str(item.purchase_price or 0)
            value = (item.quantity or 0) * (item.purchase_price or item.unit_price or 0)
            ET.SubElement(i_el, 'TotalValue').text = str(round(value, 2))
            total_value += value

            # SplitAllocation
            if item.reserved_inhouse or item.reserved_marketplace:
                alloc = ET.SubElement(i_el, 'Allocation')
                ET.SubElement(alloc, 'ReservedInhouse').text = str(item.reserved_inhouse)
                ET.SubElement(alloc, 'ReservedMarketplace').text = str(item.reserved_marketplace)
                ET.SubElement(alloc, 'BufferPct').text = str(item.allocation_buffer_pct)

            # Flock link (karenca)
            if item.source_flock_id:
                flock_el = ET.SubElement(i_el, 'SourceFlock', id=str(item.source_flock_id))
                ET.SubElement(flock_el, 'Name').text = item.source_flock.naziv if item.source_flock else ''
                ET.SubElement(flock_el, 'ActiveWithdrawal').text = str(
                    item.source_flock.has_active_karenca if item.source_flock else False
                ).lower()

            # LOT batches
            batches = StockBatch.objects.filter(item=item, quarantine_status='active')
            if batches.exists():
                b_el = ET.SubElement(i_el, 'Batches', count=str(batches.count()))
                for batch in batches:
                    bt = ET.SubElement(b_el, 'Batch')
                    ET.SubElement(bt, 'LOT').text = batch.batch_number
                    ET.SubElement(bt, 'Quantity').text = str(batch.quantity)
                    if batch.expiry_date:
                        ET.SubElement(bt, 'ExpiryDate').text = batch.expiry_date.isoformat()

        # Kretanja u periodu
        movements = StockMovement.objects.filter(
            item__company=company,
            created_at__date__gte=export.period_start,
            created_at__date__lte=export.period_end,
        ).order_by('created_at')

        mov_el = ET.SubElement(root, 'Movements', count=str(movements.count()))
        for mv in movements[:500]:  # Max 500 za XML veličinu
            m = ET.SubElement(mov_el, 'Movement', id=str(mv.pk))
            ET.SubElement(m, 'Item').text = mv.item.name
            ET.SubElement(m, 'Type').text = mv.movement_type
            ET.SubElement(m, 'Quantity').text = str(mv.quantity)
            ET.SubElement(m, 'UnitPrice').text = str(mv.unit_price)
            ET.SubElement(m, 'Reason').text = mv.reason or ''
            ET.SubElement(m, 'Timestamp').text = mv.created_at.isoformat()

        # Summary
        summary = ET.SubElement(root, 'Summary')
        ET.SubElement(summary, 'TotalItems').text = str(items.count())
        ET.SubElement(summary, 'TotalValue').text = str(round(total_value, 2))
        ET.SubElement(summary, 'TotalMovements').text = str(movements.count())
        ET.SubElement(summary, 'Currency').text = 'EUR'

        xml_str = minidom.parseString(ET.tostring(root, encoding='unicode')).toprettyxml(indent='  ')
        return xml_str
