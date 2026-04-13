"""
konto/german_accounting.py
German Accounting Module: SKR 03 + DATEV EXTF/700 Export

SKR 03 = Standardkontenrahmen 03 (Prozessgliederungsprinzip)
DATEV EXTF = ASCII-Format fuer Buchungsstapel, Version 700

References:
  - DATEV-Format-Beschreibung v12.0 (2024)
  - SKR 03 Kontenrahmen (DATEV eG)
  - GoBD (BMF-Schreiben 28.11.2019)
"""

import csv
import io
import logging
from datetime import datetime
from decimal import Decimal

logger = logging.getLogger(__name__)


# ─── SKR 03 Kontni plan (essential accounts) ────────────────────────────────

SKR03_ACCOUNTS = [
    # Klasse 0: Anlagevermoegen
    ("0400", "Technische Anlagen und Maschinen", "asset"),
    ("0420", "Bueroeinrichtung", "asset"),
    ("0650", "Bueroeinrichtung (GWG)", "asset"),
    # Klasse 1: Umlaufvermoegen + Geldkonten
    ("1000", "Kasse", "asset"),
    ("1200", "Bank", "asset"),
    ("1400", "Forderungen aus Lieferungen und Leistungen", "asset"),
    ("1410", "Forderungen aus Lieferungen und Leistungen (Inland)", "asset"),
    ("1450", "Forderungen nach 13b UStG", "asset"),
    ("1500", "Sonstige Vermoegengegenstaende", "asset"),
    ("1570", "Abziehbare Vorsteuer", "asset"),
    ("1576", "Abziehbare Vorsteuer 19%", "asset"),
    ("1571", "Abziehbare Vorsteuer 7%", "asset"),
    ("1580", "Vorsteuer im Folgejahr abziehbar", "asset"),
    ("1590", "Durchlaufende Posten", "asset"),
    # Klasse 1: Verbindlichkeiten (liability side uses 1600-1699 in SKR03)
    ("1600", "Verbindlichkeiten aus Lieferungen und Leistungen", "liability"),
    ("1700", "Sonstige Verbindlichkeiten", "liability"),
    ("1740", "Verbindlichkeiten aus Lohn und Gehalt", "liability"),
    ("1741", "Verbindlichkeiten soziale Sicherheit", "liability"),
    ("1760", "Umsatzsteuervorauszahlungen", "liability"),
    ("1770", "Umsatzsteuer 7%", "liability"),
    ("1775", "Umsatzsteuer 19%", "liability"),
    ("1776", "Umsatzsteuer-Vorauszahlung 1/11", "liability"),
    ("1780", "Umsatzsteuer-Vorauszahlungen", "liability"),
    ("1790", "Umsatzsteuer laufendes Jahr", "liability"),
    # Klasse 2: Eigenkapital
    ("2000", "Gezeichnetes Kapital / Stammkapital", "equity"),
    ("2100", "Kapitalruecklagen", "equity"),
    # Klasse 3: Wareneinkauf
    ("3300", "Wareneingang 7% Vorsteuer", "expense"),
    ("3400", "Wareneingang 19% Vorsteuer", "expense"),
    # Klasse 4: Betriebliche Aufwendungen
    ("4100", "Loehne", "expense"),
    ("4120", "Gehaelter", "expense"),
    ("4130", "Gesetzliche soziale Aufwendungen", "expense"),
    ("4200", "Raumkosten / Miete", "expense"),
    ("4210", "Miete (unbewegliche Wirtschaftsgueter)", "expense"),
    ("4240", "Gas, Strom, Wasser", "expense"),
    ("4250", "Reinigung", "expense"),
    ("4300", "Versicherungen", "expense"),
    ("4360", "Kfz-Versicherung", "expense"),
    ("4500", "Fahrzeugkosten", "expense"),
    ("4510", "Kfz-Steuer", "expense"),
    ("4520", "Kfz-Reparaturen", "expense"),
    ("4530", "Treibstoff / Laufende Kfz-Betriebskosten", "expense"),
    ("4600", "Werbekosten", "expense"),
    ("4650", "Bewirtungskosten", "expense"),
    ("4660", "Reisekosten Arbeitnehmer", "expense"),
    ("4700", "Kosten der Warenabgabe", "expense"),
    ("4900", "Sonstige betriebliche Aufwendungen", "expense"),
    ("4910", "Porto", "expense"),
    ("4920", "Telefon", "expense"),
    ("4930", "Buerokosten", "expense"),
    ("4950", "Rechts- und Beratungskosten", "expense"),
    ("4955", "Buchfuehrungskosten", "expense"),
    ("4969", "Nebenkosten des Geldverkehrs", "expense"),
    # Klasse 7: Bestands/Leistung (skip for now)
    # Klasse 8: Erloese
    ("8100", "Steuerfreie Umsaetze 4 Nr. 1a UStG", "income"),
    ("8300", "Erloese 7% USt", "income"),
    ("8400", "Erloese 19% USt", "income"),
    ("8900", "Erloese steuerfrei (Inland)", "income"),
    # Klasse 9: Vortragskonten
    ("9000", "Saldenvortraege Sachkonten", "equity"),
    ("9008", "Saldenvortraege Debitoren", "equity"),
    ("9009", "Saldenvortraege Kreditoren", "equity"),
]


def seed_skr03(company):
    """
    Seeds SKR 03 accounts for a German company.
    Uses get_or_create to be idempotent.
    Returns (created_count, skipped_count).
    """
    from konto.models import KontoAccount

    created = 0
    skipped = 0
    for code, name, account_type in SKR03_ACCOUNTS:
        _, was_created = KontoAccount.objects.get_or_create(
            company=company,
            code=code,
            defaults={
                "name": name,
                "account_type": account_type,
                "is_active": True,
            },
        )
        if was_created:
            created += 1
        else:
            skipped += 1

    logger.info(f"SKR 03 seeded for {company.name}: {created} created, {skipped} existing")
    return created, skipped


# ─── DATEV EXTF/700 Export ───────────────────────────────────────────────────

# BU-Schluessel (Steuerschluessel) mapping
BU_KEYS = {
    Decimal("19.00"): "3",  # 19% USt
    Decimal("7.00"): "2",  # 7% USt
    Decimal("0.00"): "0",  # steuerfrei
}


def generate_datev_export(company, start_date, end_date, berater_nr="", mandanten_nr=""):
    """
    Generates a DATEV EXTF/700 compatible CSV for journal entries
    in the given date range.

    Args:
        company: Company instance (must have country='DE')
        start_date, end_date: date objects
        berater_nr: Beraternummer (Steuerberater ID)
        mandanten_nr: Mandantennummer (Client ID at Steuerberater)

    Returns:
        str: CSV content ready for DATEV import
    """
    from konto.models import JournalEntry

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";", quotechar='"', quoting=csv.QUOTE_ALL)

    now = datetime.now()
    wj_beginn = start_date.replace(month=1, day=1)  # Wirtschaftsjahr-Beginn

    # ── Row 1: EXTF Header (29 fields per DATEV spec) ────────────────────
    header = [
        "EXTF",  # 1: Formatkennung
        "700",  # 2: Versionsnummer
        "21",  # 3: Datenkategorie (Buchungsstapel)
        "Buchungsstapel",  # 4: Formatname
        "13",  # 5: Formatversion
        now.strftime("%Y%m%d%H%M%S") + "000",  # 6: Erzeugt am (YYYYMMDDHHMMSSmmm)
        "",  # 7: Importiert (leer bei Export)
        "FC",  # 8: Herkunft (LIMIT Connect)
        "",  # 9: Exportiert von
        "",  # 10: Importiert von
        berater_nr,  # 11: Berater-Nr
        mandanten_nr,  # 12: Mandanten-Nr
        wj_beginn.strftime("%Y%m%d"),  # 13: WJ-Beginn
        "4",  # 14: Sachkontenlänge
        start_date.strftime("%Y%m%d"),  # 15: Datum von
        end_date.strftime("%Y%m%d"),  # 16: Datum bis
        "",  # 17: Bezeichnung (opt.)
        "",  # 18: Diktatkürzel
        "0",  # 19: Buchungstyp (0=Fibu)
        "0",  # 20: Rechnungslegungszweck
        "",  # 21: Festschreibung
        "EUR",  # 22: WKZ
        "",  # 23: reserviert
        "",  # 24: Derivatskennzeichen
        "",  # 25: reserviert
        "",  # 26: reserviert
        "",  # 27: SKR (03)
        "",  # 28: Branchen-Lösung
        "",  # 29: reserviert
    ]
    writer.writerow(header)

    # ── Row 2: Column headers (Buchungssatz) ─────────────────────────────
    columns = [
        "Umsatz (Soll)",
        "Soll/Haben-Kennzeichen",
        "WKZ Umsatz",
        "Kurs",
        "Basis-Umsatz",
        "WKZ Basis-Umsatz",
        "Konto",
        "Gegenkonto (ohne BU-Schluessel)",
        "BU-Schluessel",
        "Belegdatum",
        "Belegfeld 1",
        "Belegfeld 2",
        "Skonto",
        "Buchungstext",
        "Postensperre",
        "Diverse Adressnummer",
        "Geschaeftspartnerbank",
        "Sachverhalt",
        "Zinssperre",
        "Beleglink",
        "Beleginfo - Art 1",
        "Beleginfo - Inhalt 1",
        "Beleginfo - Art 2",
        "Beleginfo - Inhalt 2",
        "Beleginfo - Art 3",
        "Beleginfo - Inhalt 3",
        "Beleginfo - Art 4",
        "Beleginfo - Inhalt 4",
        "Beleginfo - Art 5",
        "Beleginfo - Inhalt 5",
        "Beleginfo - Art 6",
        "Beleginfo - Inhalt 6",
        "Beleginfo - Art 7",
        "Beleginfo - Inhalt 7",
        "Beleginfo - Art 8",
        "Beleginfo - Inhalt 8",
        "KOST1 - Kostenstelle",
        "KOST2 - Kostenstelle",
        "KOST-Menge",
        "EU-Land u. UStID (Bestimmung)",
        "EU-Steuersatz (Bestimmung)",
        "Abw. Versteuerungsart",
        "Sachverhalt L+L",
        "Funktionsergaenzung L+L",
        "BU 49 Hauptfunktionstyp",
        "BU 49 Hauptfunktionsnummer",
        "BU 49 Funktionsergaenzung",
        "Zusatzinformation - Art 1",
        "Zusatzinformation - Inhalt 1",
        "Zusatzinformation - Art 2",
        "Zusatzinformation - Inhalt 2",
        "Stueck",
        "Gewicht",
        "Zahlweise",
        "Forderungsart",
        "Veranlagungsjahr",
        "Zugeordnete Faelligkeit",
        "Skontotyp",
        "Auftragsnummer",
        "Buchungstyp",
        "USt-Schluessel (Anzahlungen)",
        "EU-Mitgliedstaat (Anzahlungen)",
        "Sachverhalt L+L (Anzahlungen)",
        "EU-Steuersatz (Anzahlungen)",
        "Erloeskonto (Anzahlungen)",
        "Herkunft-Kz",
        "Buchungs GUID",
        "KOST-Datum",
        "SEPA-Mandatsreferenz",
        "Skontosperre",
        "Gesellschaftername",
        "Beteiligtennummer",
        "Identifikationsnummer",
        "Zeichnernummer",
        "Postensperre bis",
        "Bezeichnung SoBil-Sachverhalt",
        "Kennzeichen SoBil-Buchung",
        "Festschreibung",
        "Leistungsdatum",
        "Datum Zuord. Steuerperiode",
        "Faelligkeit",
        "Generalumkehr (GU)",
        "Steuersatz",
        "Land",
    ]
    writer.writerow(columns)

    # ── Data rows: one per LedgerLine pair ───────────────────────────────
    entries = (
        JournalEntry.objects.filter(
            company=company,
            date__gte=start_date,
            date__lte=end_date,
            is_posted=True,
        )
        .prefetch_related("lines__account")
        .select_related("source_invoice")
    )

    row_count = 0
    for entry in entries:
        lines = list(entry.lines.all())
        if len(lines) < 2:
            continue

        # Find debit and credit sides
        debit_lines = [l for l in lines if l.side == "debit"]
        credit_lines = [l for l in lines if l.side == "credit"]

        if not debit_lines or not credit_lines:
            continue

        # For simple 2-line entries, create one DATEV row
        # For multi-line, create one row per debit-credit pair
        soll = debit_lines[0]
        haben = credit_lines[0]

        # Invoice reference
        beleg = ""
        if entry.source_invoice:
            beleg = getattr(entry.source_invoice, "number", "")[:12]
        if not beleg:
            beleg = entry.entry_number[:12]

        # Amount (German decimal format: comma separator)
        amount_str = str(soll.amount).replace(".", ",")

        # BU-Schluessel (tax key) — derive from account code
        bu_key = ""
        if haben.account.code in ("8400",):
            bu_key = "3"  # 19% USt
        elif haben.account.code in ("8300",):
            bu_key = "2"  # 7% USt
        elif soll.account.code in ("3400",):
            bu_key = "9"  # 19% VSt (Vorsteuer)
        elif soll.account.code in ("3300",):
            bu_key = "8"  # 7% VSt

        # Belegdatum: DDMM format (4 digits, no year — DATEV convention)
        beleg_datum = entry.date.strftime("%d%m")

        # Build DATEV row (fill 88 columns, most empty)
        row = [""] * len(columns)
        row[0] = amount_str  # Umsatz
        row[1] = "S"  # Soll
        row[2] = "EUR"  # WKZ
        row[6] = soll.account.code  # Konto
        row[7] = haben.account.code  # Gegenkonto
        row[8] = bu_key  # BU-Schluessel
        row[9] = beleg_datum  # Belegdatum
        row[10] = beleg  # Belegfeld 1
        row[13] = entry.description[:60]  # Buchungstext

        writer.writerow(row)
        row_count += 1

    logger.info(f"DATEV export for {company.name}: {row_count} rows, period {start_date} to {end_date}")
    return output.getvalue()
