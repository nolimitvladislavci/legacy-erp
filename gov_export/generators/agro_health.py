"""
Agro-Fiskalizacija — AgroHealth.xml generator.
Svaki FlockHealthRecord + karenca → potpisan XML za veterinarsku inspekciju.
"""

import xml.etree.ElementTree as ET
from xml.dom import minidom

from django.utils import timezone


class AgroHealthGenerator:
    """Generira AgroHealth.xml za GovExport pipeline."""

    NS = "urn:limit-connect:agro-health:v1.0"

    def generate(self, export):
        from udruge.models import EggRecord, Flock, FlockHealthRecord, FlockMortality

        company = export.company
        root = ET.Element("AgroHealthReport", xmlns=self.NS)
        root.set("version", "1.0")
        root.set("generated", timezone.now().isoformat())

        # Izdavatelj
        issuer = ET.SubElement(root, "Issuer")
        ET.SubElement(issuer, "Name").text = company.name
        ET.SubElement(issuer, "OIB").text = company.oib or ""
        ET.SubElement(issuer, "Address").text = company.address or ""

        # Period
        period = ET.SubElement(root, "Period")
        ET.SubElement(period, "From").text = export.period_start.isoformat()
        ET.SubElement(period, "To").text = export.period_end.isoformat()

        # Jata
        flocks = Flock.objects.filter(company=company, aktivan=True)
        flocks_el = ET.SubElement(root, "Flocks", count=str(flocks.count()))

        for flock in flocks:
            f_el = ET.SubElement(flocks_el, "Flock", id=str(flock.pk))
            ET.SubElement(f_el, "Name").text = flock.naziv
            ET.SubElement(f_el, "Species").text = flock.get_vrsta_display()
            ET.SubElement(f_el, "Breed").text = flock.pasmina or ""
            ET.SubElement(f_el, "HeadCount").text = str(flock.broj_komada)
            ET.SubElement(f_el, "ActiveCount").text = str(flock.aktivnih_komada)
            ET.SubElement(f_el, "AcquiredDate").text = flock.datum_nabave.isoformat() if flock.datum_nabave else ""
            ET.SubElement(f_el, "FarmingType").text = flock.tip_uzgoja or ""
            ET.SubElement(f_el, "Location").text = flock.objekt or ""
            ET.SubElement(f_el, "HasActiveWithdrawal").text = str(flock.has_active_karenca).lower()
            if flock.karenca_end_date:
                ET.SubElement(f_el, "WithdrawalEndDate").text = flock.karenca_end_date.isoformat()

            # Zdravstveni zapisi u periodu
            health = FlockHealthRecord.objects.filter(
                flock=flock,
                datum__gte=export.period_start,
                datum__lte=export.period_end,
            )
            if health.exists():
                h_el = ET.SubElement(f_el, "HealthRecords", count=str(health.count()))
                for hr in health:
                    rec = ET.SubElement(h_el, "Record", id=str(hr.pk))
                    ET.SubElement(rec, "Type").text = hr.get_vrsta_tretmana_display()
                    ET.SubElement(rec, "Date").text = hr.datum.isoformat()
                    ET.SubElement(rec, "Medicine").text = hr.lijek or ""
                    ET.SubElement(rec, "Dosage").text = hr.doza or ""
                    ET.SubElement(rec, "Veterinarian").text = hr.veterinar or ""
                    if hr.karenca_dana:
                        ET.SubElement(rec, "WithdrawalDays").text = str(hr.karenca_dana)
                        ET.SubElement(rec, "WithdrawalActive").text = str(hr.karenca_aktivna).lower()

            # Mortalitet
            mort = FlockMortality.objects.filter(
                flock=flock,
                datum__gte=export.period_start,
                datum__lte=export.period_end,
            )
            if mort.exists():
                m_el = ET.SubElement(f_el, "MortalityRecords", count=str(mort.count()))
                for m in mort:
                    mr = ET.SubElement(m_el, "Record")
                    ET.SubElement(mr, "Date").text = m.datum.isoformat()
                    ET.SubElement(mr, "Count").text = str(m.broj_uginulih)
                    ET.SubElement(mr, "Reason").text = m.razlog or ""

            # Jaja u periodu
            eggs = EggRecord.objects.filter(
                flock=flock,
                datum__gte=export.period_start,
                datum__lte=export.period_end,
            )
            if eggs.exists():
                e_el = ET.SubElement(f_el, "EggProduction", count=str(eggs.count()))
                total_eggs = sum(e.broj_jaja for e in eggs)
                total_broken = sum(e.broken for e in eggs)
                ET.SubElement(e_el, "TotalEggs").text = str(total_eggs)
                ET.SubElement(e_el, "TotalBroken").text = str(total_broken)

        xml_str = minidom.parseString(ET.tostring(root, encoding="unicode")).toprettyxml(indent="  ")
        return xml_str
