"""
invoicing/gobd_compliance.py

DE GoBD (Grundsätze ordnungsmäßiger Buchführung und Datenzugriffs) compliance.
Provjera Pflichtangaben (§14 UStG) i kontinuiranog numeriranja računa.
"""
from django.utils import timezone


# ─────────────────────────────────────────────
#  Pflichtangaben provjere (§14 UStG)
# ─────────────────────────────────────────────

def check_pflichtangaben(invoice) -> list:
    """
    Prüfe alle Pflichtangaben auf einer DE Rechnung (§14 Abs. 4 UStG).
    Vrati listu string upozorenja.
    """
    warnings = []

    if not getattr(invoice, 'client_name', None):
        warnings.append('Kundenname (Name des Leistungsempfängers) fehlt')
    if not getattr(invoice, 'client_address', None):
        warnings.append('Kundenadresse (Anschrift des Leistungsempfängers) fehlt')
    if not getattr(invoice, 'number', None):
        warnings.append('Rechnungsnummer fehlt')
    if not getattr(invoice, 'date_issued', None):
        warnings.append('Rechnungsdatum (Ausstellungsdatum) fehlt')

    # Leistungsbeschreibung — stavke moraju postojati
    try:
        if not invoice.items.exists():
            warnings.append('Keine Leistungsbeschreibung / Positionen')
    except Exception:
        pass

    # USt-IdNr ODER Steuernummer izdavatelja
    profile = getattr(invoice, 'invoice_profile', None)
    issuer_oib = getattr(invoice, 'issuer_oib', '')
    has_tax_id = bool(issuer_oib)
    if profile:
        has_tax_id = bool(getattr(profile, 'vat_id', '')) or bool(getattr(profile, 'oib', ''))
    if not has_tax_id:
        warnings.append('Weder USt-IdNr noch Steuernummer des Ausstellers angegeben')

    # Leistungsdatum / Lieferdatum (darf gleich Rechnungsdatum sein, muss aber angegeben werden)
    has_delivery = (
        getattr(invoice, 'date_delivery', None) or
        getattr(invoice, 'date_issued', None)
    )
    if not has_delivery:
        warnings.append('Leistungsdatum / Lieferdatum fehlt')

    return warnings


# ─────────────────────────────────────────────
#  Fortlaufende Nummerierung
# ─────────────────────────────────────────────

def check_fortlaufende_nummer(company, year=None) -> dict:
    """
    Prüfe ob Rechnungsnummern lückenlos fortlaufend sind (GoBD §145 AO).
    Returns: {'ok': bool, 'gaps': list[int], 'message': str}
    """
    from invoicing.models import Invoice

    if not year:
        year = timezone.now().year

    numbers_qs = Invoice.objects.filter(
        company=company,
        doctype='R',
        date_issued__year=year,
        status__in=['SENT', 'PAID', 'UNPAID', 'OVERDUE'],
    ).values_list('number', flat=True)

    numbers = []
    for num in numbers_qs:
        try:
            clean = ''.join(c for c in str(num) if c.isdigit())
            if clean:
                numbers.append(int(clean))
        except (ValueError, TypeError):
            pass

    if not numbers:
        return {'ok': True, 'gaps': [], 'message': 'Keine Rechnungen im Zeitraum'}

    numbers.sort()
    gaps = []
    for i in range(1, len(numbers)):
        if numbers[i] - numbers[i - 1] > 1:
            for missing in range(numbers[i - 1] + 1, numbers[i]):
                gaps.append(missing)

    if gaps:
        return {
            'ok': False,
            'gaps': gaps[:10],
            'message': f'Lücken in der Nummerierung: {len(gaps)} fehlende Nummer(n)',
        }
    return {'ok': True, 'gaps': [], 'message': 'Fortlaufende Nummerierung OK'}


# ─────────────────────────────────────────────
#  Kompletan GoBD report
# ─────────────────────────────────────────────

def get_gobd_report(company, year=None) -> dict:
    """Kompletan GoBD compliance report za tvrtku/godinu."""
    from invoicing.models import Invoice

    if not year:
        year = timezone.now().year

    invoices = Invoice.objects.filter(
        company=company,
        doctype='R',
        date_issued__year=year,
    ).order_by('-date_issued').select_related('invoice_profile')

    issues = []
    for inv in invoices[:100]:
        pflicht = check_pflichtangaben(inv)
        if pflicht:
            issues.append({
                'invoice': inv.number,
                'invoice_pk': inv.pk,
                'warnings': pflicht,
            })

    nummer_check = check_fortlaufende_nummer(company, year)

    return {
        'year': year,
        'total_invoices': invoices.count(),
        'issues_count': len(issues),
        'issues': issues[:20],
        'nummer_check': nummer_check,
        'compliant': len(issues) == 0 and nummer_check['ok'],
    }
