from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
"""
invoicing/dunning_templates.py -- Templates za opomene u 3 tona (gentle, firm, legal)
"""


def _format_date(d):
    if d is None:
        return "N/A"
    if hasattr(d, "strftime"):
        return d.strftime("%d.%m.%Y")
    return str(d)


def _get_iban(invoice, company):
    return invoice.issuer_iban or invoice.iban or getattr(company, "iban", "") or ""


def get_gentle_template(invoice, company):
    iban = _get_iban(invoice, company)
    due = _format_date(invoice.date_due)
    subject = f"Podsjetnik za placanje racuna {invoice.number}"
    body = (
        f"Postovani/a {invoice.client_name},\n\n"
        f"ovim putem Vas prijateljski podsjecamo da racun broj {invoice.number} "
        f"u iznosu {invoice.total} {invoice.currency} jos uvijek nije placen.\n\n"
        f"Rok placanja: {due}\n"
    )
    if iban:
        body += f"IBAN za uplatu: {iban}\n"
    body += (
        f"Poziv na broj: {invoice.reference_number or invoice.number}\n\n"
        f"Molimo Vas da izvrsite uplatu u najkracem mogucem roku. "
        f"Ukoliko ste vec izvrsili uplatu, molimo Vas da zanemarite ovu poruku.\n\n"
        f"S postovanjem,\n"
        f"{company.name}"
    )
    return subject, body


def get_firm_template(invoice, company):
    iban = _get_iban(invoice, company)
    due = _format_date(invoice.date_due)
    subject = f"Druga opomena -- racun {invoice.number} dospijece isteklo"
    body = (
        f"Postovani/a {invoice.client_name},\n\n"
        f"usprkos nasem prethodnom podsjetniku, racun broj {invoice.number} "
        f"u iznosu {invoice.total} {invoice.currency} jos uvijek nije placen.\n\n"
        f"Datum dospijeca: {due}\n"
    )
    if iban:
        body += f"IBAN za uplatu: {iban}\n"
    body += (
        f"Poziv na broj: {invoice.reference_number or invoice.number}\n\n"
        f"Molimo Vas da hitno izvrsite uplatu. U slucaju daljnjeg kasnjenja, "
        f"bit cemo prisiljeni poduzeti dodatne mjere naplate.\n\n"
        f"S postovanjem,\n"
        f"{company.name}"
    )
    return subject, body


def get_legal_template(invoice, company):
    iban = _get_iban(invoice, company)
    due = _format_date(invoice.date_due)
    subject = f"Posljednja opomena prije pravnog postupka -- racun {invoice.number}"
    body = (
        f"Postovani/a {invoice.client_name},\n\n"
        f"ovo je posljednja opomena za neplaceni racun broj {invoice.number} "
        f"u iznosu {invoice.total} {invoice.currency}.\n\n"
        f"Datum dospijeca: {due}\n"
    )
    if iban:
        body += f"IBAN za uplatu: {iban}\n"
    body += (
        f"Poziv na broj: {invoice.reference_number or invoice.number}\n\n"
        f"Ukoliko uplata ne bude izvrsena u roku od 7 dana od primitka ove opomene, "
        f"bit cemo prisiljeni pokrenuti pravni postupak naplate potrazivanja "
        f"sukladno vazecim propisima. U tom slucaju, snosit cete i troskove "
        f"postupka i zakonske zatezne kamate.\n\n"
        f"S postovanjem,\n"
        f"{company.name}\n"
        f"OIB: {company.oib}"
    )
    return subject, body


TONE_TEMPLATE_MAP = {
    "gentle": get_gentle_template,
    "firm": get_firm_template,
    "legal": get_legal_template,
}


def get_template(tone, invoice, company):
    """Return (subject, body) for given tone."""
    func = TONE_TEMPLATE_MAP.get(tone, get_gentle_template)
    return func(invoice, company)
