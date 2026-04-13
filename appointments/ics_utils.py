"""
.ics (iCalendar) file generation for appointments.
"""

from datetime import datetime


def generate_ics(appointment):
    """
    Generate an .ics file content string for the given Appointment instance.
    Returns a string that can be written as a .ics file.
    """

    def fmt_dt(dt):
        """Format datetime as iCalendar UTC timestamp."""
        if dt is None:
            return ""
        if hasattr(dt, "utctimetuple"):
            return dt.strftime("%Y%m%dT%H%M%SZ")
        return ""

    uid = f"appointment-{appointment.id}@limit-connect.com"
    now = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    summary = appointment.title or "Termin"
    description = (appointment.description or "").replace("\n", "\\n")
    location = getattr(appointment, "location", "") or ""
    dtstart = fmt_dt(appointment.start_time)
    dtend = fmt_dt(appointment.end_time) if appointment.end_time else dtstart

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//LIMIT Connect//Appointments//HR",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{now}",
        f"DTSTART:{dtstart}",
        f"DTEND:{dtend}",
        f"SUMMARY:{summary}",
        f"DESCRIPTION:{description}",
        f"LOCATION:{location}",
        "STATUS:CONFIRMED",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return "\r\n".join(lines)
