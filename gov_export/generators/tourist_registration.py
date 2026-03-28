"""
Turistički ZKI — TuristPrijava.xml generator.
Svaki booking check-in → potpisan XML s lokalnim ZKI kodom.
Za obranu kad eVisitor padne.
"""
import xml.etree.ElementTree as ET
from xml.dom import minidom
import hashlib
from django.utils import timezone


class TouristRegistrationGenerator:
    """Generira TuristPrijava.xml za GovExport pipeline."""

    NS = 'urn:limit-connect:tourist-registration:v1.0'

    def generate(self, export):
        company = export.company
        root = ET.Element('TouristRegistration', xmlns=self.NS)
        root.set('version', '1.0')
        root.set('generated', timezone.now().isoformat())

        # Izdavatelj (objekt za smještaj)
        issuer = ET.SubElement(root, 'Issuer')
        ET.SubElement(issuer, 'Name').text = company.name
        ET.SubElement(issuer, 'OIB').text = company.oib or ''

        period = ET.SubElement(root, 'Period')
        ET.SubElement(period, 'From').text = export.period_start.isoformat()
        ET.SubElement(period, 'To').text = export.period_end.isoformat()

        # Rental bookings u periodu
        try:
            from rental.models import Booking, TrafficRecord
            bookings = Booking.objects.filter(
                company=company,
                check_in__gte=export.period_start,
                check_in__lte=export.period_end,
            ).order_by('check_in')

            guests_el = ET.SubElement(root, 'Guests', count=str(bookings.count()))
            for b in bookings:
                g = ET.SubElement(guests_el, 'Guest', id=str(b.pk))
                ET.SubElement(g, 'BookingNumber').text = b.booking_number or ''
                ET.SubElement(g, 'GuestName').text = b.guest_name
                ET.SubElement(g, 'GuestCount').text = str(b.guest_count)
                ET.SubElement(g, 'CheckIn').text = b.check_in.isoformat()
                ET.SubElement(g, 'CheckOut').text = b.check_out.isoformat()
                ET.SubElement(g, 'Status').text = b.status
                if b.actual_check_in:
                    ET.SubElement(g, 'ActualCheckIn').text = b.actual_check_in.isoformat()
                
                # Lokalni ZKI — hash kao dokaz prijave
                zki_data = f'{company.oib}|{b.guest_name}|{b.check_in}|{b.pk}'
                zki = hashlib.sha256(zki_data.encode()).hexdigest()[:32]
                ET.SubElement(g, 'LocalZKI').text = zki

                # Traffic records (eVisitor podaci)
                traffic = TrafficRecord.objects.filter(booking=b)
                for tr in traffic:
                    t_el = ET.SubElement(g, 'TrafficRecord', id=str(tr.pk))
                    ET.SubElement(t_el, 'GuestName').text = tr.guest_name or ''
                    ET.SubElement(t_el, 'Nationality').text = tr.nationality or ''
                    ET.SubElement(t_el, 'DocumentNumber').text = tr.document_number or ''
                    ET.SubElement(t_el, 'EVisitorSynced').text = str(tr.evisitor_synced).lower()
                    if tr.evisitor_synced_at:
                        ET.SubElement(t_el, 'EVisitorSyncedAt').text = tr.evisitor_synced_at.isoformat()
        except Exception:
            ET.SubElement(root, 'Guests', count='0')

        # Experiences bookings
        try:
            from experiences.models import ExperienceBooking
            exp_bookings = ExperienceBooking.objects.filter(
                schedule__experience__company=company,
                schedule__date__gte=export.period_start,
                schedule__date__lte=export.period_end,
                status__in=['checked_in', 'completed'],
            )
            exp_el = ET.SubElement(root, 'ExperienceGuests', count=str(exp_bookings.count()))
            for eb in exp_bookings:
                eg = ET.SubElement(exp_el, 'Guest', id=str(eb.pk))
                ET.SubElement(eg, 'Name').text = eb.guest_name
                ET.SubElement(eg, 'Country').text = eb.guest_country or ''
                ET.SubElement(eg, 'PaxCount').text = str(eb.pax_count)
                ET.SubElement(eg, 'Experience').text = eb.schedule.experience.name
                ET.SubElement(eg, 'Date').text = eb.schedule.date.isoformat()
        except Exception:
            ET.SubElement(root, 'ExperienceGuests', count='0')

        xml_str = minidom.parseString(ET.tostring(root, encoding='unicode')).toprettyxml(indent='  ')
        return xml_str
