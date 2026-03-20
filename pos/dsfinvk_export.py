"""
DSFinV-K Export Generator — Kassenarchiv fuer deutsche Finanzamtspruefung.

Generiert ZIP mit CSV-Dateien gemaess DSFinV-K v2.3:
- bonkopf.csv (Belegkoepfe)
- bonpos.csv  (Belegpositionen)
- tse.csv     (TSE-Signaturdaten)
- businesscases.csv (Geschaeftsvorfaelle)
- stamm_kassen.csv (Kassenstammdaten)
- stamm_orte.csv   (Betriebsstaetten)

Usage:
    from pos.dsfinvk_export import generate_dsfinvk_export
    zip_bytes = generate_dsfinvk_export(company, date_from, date_to)

    # Oder als Management Command:
    python manage.py export_dsfinvk <company_uuid> --from 2026-01-01 --to 2026-03-31
"""
import csv
import io
import zipfile
from datetime import date, datetime
from decimal import Decimal

from django.utils import timezone

# DSFinV-K Zahlungsart Mapping
ZAHLUNGSART = {
    'CASH': 'Bar',
    'CARD': 'Unbar',
    'VOUCHER': 'Keine',
    'MOBILE': 'Unbar',
    'REVOLUT': 'Unbar',
    'AIRCASH': 'Unbar',
    'PAYPAL': 'Unbar',
    'CRYPTO': 'Unbar',
}

# DSFinV-K USt-Schluessel
UST_SCHLUESSEL = {
    19: 1,   # Allgemeiner Steuersatz
    7: 2,    # Ermaessigter Steuersatz
    0: 5,    # Nicht steuerbar
    13: 3,   # Durchschnittsatz Landwirtschaft
    5: 4,    # Sondersteuersatz (COVID, historisch)
}

# DSFinV-K GV_TYP
GV_TYP = {
    'sale': 'Umsatz',
    'tip': 'TrinkgeldAN',
    'tip_employer': 'TrinkgeldAG',
    'pfand_return': 'Pfandrueckzahlung',
    'void': 'Storno',
}


def generate_dsfinvk_export(company, date_from, date_to):
    """
    Generiert DSFinV-K konformen ZIP-Export.

    Args:
        company: Company Objekt (muss DE sein)
        date_from: date — Beginn des Exportzeitraums
        date_to: date — Ende des Exportzeitraums

    Returns:
        bytes: ZIP-Datei Inhalt
    """
    from pos.models import POSReceipt, POSTerminal, POSSession

    receipts = POSReceipt.objects.filter(
        session__terminal__company=company,
        created_at__date__gte=date_from,
        created_at__date__lte=date_to,
        status__in=['paid', 'cancelled', 'refunded'],
    ).select_related(
        'session', 'session__terminal', 'cashier',
    ).prefetch_related('items', 'payment_lines').order_by('created_at')

    terminals = POSTerminal.objects.filter(company=company, is_active=True)

    # Build ZIP in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:

        # ── bonkopf.csv ──────────────────────────────────────────
        bonkopf = io.StringIO()
        bk_writer = csv.writer(bonkopf, delimiter=';', quoting=csv.QUOTE_ALL)
        bk_writer.writerow([
            'Z_KASSE_ID', 'Z_ERSTELLUNG', 'Z_NR', 'BON_ID', 'BON_NR',
            'BON_TYP', 'BON_NAME', 'TERMINAL_ID', 'BON_STORNO',
            'BON_START', 'BON_ENDE', 'BEDIENER_ID', 'BEDIENER_NAME',
            'UMS_BRUTTO', 'KUNDE_NAME', 'KUNDE_ID', 'BON_NOTIZ',
        ])

        # ── bonpos.csv ───────────────────────────────────────────
        bonpos = io.StringIO()
        bp_writer = csv.writer(bonpos, delimiter=';', quoting=csv.QUOTE_ALL)
        bp_writer.writerow([
            'Z_KASSE_ID', 'Z_ERSTELLUNG', 'Z_NR', 'BON_ID', 'POS_ZEILE',
            'GUTSCHEIN_NR', 'ARTIKELTEXT', 'MENGE', 'FAKTOR',
            'UST_SCHLUESSEL', 'POS_BRUTTO', 'POS_NETTO',
            'GV_TYP', 'GV_NAME', 'INHAUS', 'P_STORNO',
        ])

        # ── tse.csv ──────────────────────────────────────────────
        tse_csv = io.StringIO()
        tse_writer = csv.writer(tse_csv, delimiter=';', quoting=csv.QUOTE_ALL)
        tse_writer.writerow([
            'Z_KASSE_ID', 'Z_ERSTELLUNG', 'Z_NR', 'BON_ID',
            'TSE_TANR', 'TSE_TA_START', 'TSE_TA_ENDE',
            'TSE_TA_VORGANGSART', 'TSE_TA_SIGZ', 'TSE_TA_SIG',
            'TSE_TA_FEHLER', 'TSE_TA_VORGANGSDATEN',
            'TSE_SERIAL', 'TSE_HASHALGO', 'TSE_ZEITFORMAT',
            'TSE_PDENCODING', 'TSE_PUBKEY', 'TSE_ZERTIFIKAT_I',
            'TSE_ZERTIFIKAT_II',
        ])

        # ── Process receipts ─────────────────────────────────────
        z_nr = 0
        for receipt in receipts:
            z_nr += 1
            terminal = receipt.session.terminal
            kasse_id = terminal.terminal_code
            erstellung = receipt.created_at.strftime('%Y-%m-%dT%H:%M:%S')
            bon_id = str(receipt.uuid)
            bon_nr = receipt.receipt_number
            is_storno = 1 if receipt.status == 'cancelled' else 0

            cashier_name = ''
            cashier_id = ''
            if receipt.cashier:
                cashier_name = str(receipt.cashier.name) if hasattr(receipt.cashier, 'name') else ''
                cashier_id = str(receipt.cashier.pk)
            elif receipt.session.operator:
                cashier_name = receipt.session.operator.get_full_name() or receipt.session.operator.username
                cashier_id = str(receipt.session.operator.pk)

            # bonkopf
            bk_writer.writerow([
                kasse_id, erstellung, z_nr, bon_id, bon_nr,
                'Beleg', '', kasse_id, is_storno,
                erstellung, receipt.paid_at.strftime('%Y-%m-%dT%H:%M:%S') if receipt.paid_at else erstellung,
                cashier_id, cashier_name,
                str(receipt.total), '', '', receipt.note or '',
            ])

            # bonpos — eine Zeile pro Artikelposition
            pos_zeile = 0
            for item in receipt.items.all():
                pos_zeile += 1
                tax_rate = int(item.tax_rate) if item.tax_rate else 19
                ust_key = UST_SCHLUESSEL.get(tax_rate, 1)

                brutto = item.total_price or (item.quantity * item.unit_price * (1 + item.tax_rate / 100))
                netto = item.quantity * item.unit_price

                # GV_TYP bestimmen
                if item.is_tip:
                    gv_typ = GV_TYP['tip']
                elif getattr(item, 'is_pfand_return', False):
                    gv_typ = GV_TYP['pfand_return']
                elif is_storno:
                    gv_typ = GV_TYP['void']
                else:
                    gv_typ = GV_TYP['sale']

                bp_writer.writerow([
                    kasse_id, erstellung, z_nr, bon_id, pos_zeile,
                    '', item.description[:60], str(item.quantity), '1.000',
                    ust_key, str(round(brutto, 2)), str(round(netto, 2)),
                    gv_typ, '', '1', 0,
                ])

            # tse — TSE Signatur Daten
            tse_writer.writerow([
                kasse_id, erstellung, z_nr, bon_id,
                receipt.tse_transaction_number or '',
                receipt.tse_start_time.strftime('%Y-%m-%dT%H:%M:%S') if receipt.tse_start_time else '',
                receipt.tse_end_time.strftime('%Y-%m-%dT%H:%M:%S') if receipt.tse_end_time else '',
                'Kassenbeleg-V1',
                receipt.tse_signature_counter or '',
                receipt.tse_hash or '',
                receipt.tse_error or '',
                '',  # Vorgangsdaten
                receipt.tse_serial_number or '',
                'SHA-256', 'unixTime', 'UTF-8', '', '', '',
            ])

        # ── businesscases.csv ────────────────────────────────────
        bc = io.StringIO()
        bc_writer = csv.writer(bc, delimiter=';', quoting=csv.QUOTE_ALL)
        bc_writer.writerow(['GV_TYP', 'GV_NAME', 'AGENTUR_ID', 'UST_SCHLUESSEL', 'UST_SATZ'])
        for gv_key, gv_name in GV_TYP.items():
            bc_writer.writerow([gv_name, gv_name, '', '1', '19.00'])

        # ── stamm_kassen.csv ─────────────────────────────────────
        sk = io.StringIO()
        sk_writer = csv.writer(sk, delimiter=';', quoting=csv.QUOTE_ALL)
        sk_writer.writerow([
            'Z_KASSE_ID', 'KASSE_BRAND', 'KASSE_MODELL', 'KASSE_SERIENNR',
            'KASSE_SW_BRAND', 'KASSE_SW_VERSION', 'KASSE_BASISWAEH_CODE',
        ])
        for t in terminals:
            sk_writer.writerow([
                t.terminal_code, 'LIMIT Connect', 'Cloud POS', t.terminal_code,
                'LIMIT Connect ERP', '2026.03', 'EUR',
            ])

        # ── stamm_orte.csv ───────────────────────────────────────
        so = io.StringIO()
        so_writer = csv.writer(so, delimiter=';', quoting=csv.QUOTE_ALL)
        so_writer.writerow([
            'Z_KASSE_ID', 'NAME', 'STRASSE', 'PLZ', 'ORT', 'LAND',
            'STNR', 'USTID',
        ])
        for t in terminals:
            so_writer.writerow([
                t.terminal_code, company.name,
                company.address, company.zip_code, company.city, company.country,
                company.tax_number or company.oib, company.vat_id,
            ])

        # ── Write all CSVs to ZIP ────────────────────────────────
        zf.writestr('bonkopf.csv', bonkopf.getvalue())
        zf.writestr('bonpos.csv', bonpos.getvalue())
        zf.writestr('tse.csv', tse_csv.getvalue())
        zf.writestr('businesscases.csv', bc.getvalue())
        zf.writestr('stamm_kassen.csv', sk.getvalue())
        zf.writestr('stamm_orte.csv', so.getvalue())

        # ── index.json (Metadata) ────────────────────────────────
        import json
        meta = json.dumps({
            'version': '2.3',
            'erpiD': 'LIMIT Connect ERP',
            'kassenID': [t.terminal_code for t in terminals],
            'zeitraum': {
                'von': date_from.isoformat(),
                'bis': date_to.isoformat(),
            },
            'erstellungsDatum': datetime.now().isoformat(),
            'anzahlBelege': z_nr,
            'firma': {
                'name': company.name,
                'steuernummer': company.tax_number or company.oib,
                'ustId': company.vat_id,
            },
        }, indent=2, ensure_ascii=False)
        zf.writestr('index.json', meta)

    return zip_buffer.getvalue()
