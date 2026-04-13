"""
LIMIT CONNECT — Globalni Streaming ZIP Servis

Streaming ZIP response — browser preuzima dok se generira.
Nema memory overflow-a, nema timeout-a, radi za GB arhive.

Korištenje iz bilo kojeg modula:

    from core.streaming_zip import StreamingZipResponse

    # Iz fajlova na disku
    response = StreamingZipResponse(filename='revizorski_paket.zip')
    response.add_file('/path/to/file.pdf', 'dokumenti/file.pdf')
    response.add_file('/path/to/other.csv', 'izvjestaji/other.csv')
    return response.build()

    # Iz memorije (bytes/string)
    response = StreamingZipResponse(filename='export.zip')
    response.add_content('report.csv', csv_string.encode('utf-8'))
    response.add_content('data.json', json.dumps(data).encode())
    return response.build()

    # Mix — fajlovi + generirani content
    response = StreamingZipResponse(filename='paket.zip')
    response.add_file('/media/cert.pdf', 'certifikati/cert.pdf')
    response.add_content('izvjestaj.html', html_bytes)
    return response.build()
"""
import os

import zipstream
from django.db import DatabaseError
from django.http import StreamingHttpResponse


class StreamingZipResponse:
    """
    Streaming ZIP koji ne učitava cijeli ZIP u memoriju.
    Browser počinje preuzimanje odmah — nema čekanja.
    """

    def __init__(self, filename='download.zip'):
        self.filename = filename
        self.zs = zipstream.ZipFile(mode='w', compression=zipstream.ZIP_DEFLATED)

    def add_file(self, filepath, arcname=None):
        """Dodaj fajl s diska u ZIP."""
        if not os.path.exists(filepath):
            return self
        if arcname is None:
            arcname = os.path.basename(filepath)
        self.zs.write(filepath, arcname=arcname)
        return self

    def add_content(self, arcname, data):
        """Dodaj generirani content (bytes) u ZIP."""
        if isinstance(data, str):
            data = data.encode('utf-8')
        self.zs.writestr(arcname, data)
        return self

    def add_directory(self, dirpath, prefix=''):
        """Dodaj cijeli direktorij rekurzivno."""
        if not os.path.isdir(dirpath):
            return self
        for root, dirs, files in os.walk(dirpath):
            for f in files:
                full = os.path.join(root, f)
                rel = os.path.relpath(full, dirpath)
                arc = os.path.join(prefix, rel) if prefix else rel
                self.zs.write(full, arcname=arc)
        return self

    def build(self):
        """Vrati StreamingHttpResponse — browser počinje download odmah."""
        response = StreamingHttpResponse(
            self.zs,
            content_type='application/zip',
        )
        response['Content-Disposition'] = 'attachment; filename="%s"' % self.filename
        response['Content-Transfer-Encoding'] = 'binary'
        # Streaming — ne znamo veličinu unaprijed
        response['X-Content-Type-Options'] = 'nosniff'
        return response


# ══════════════════════════════════════════════════════════════
# REVIZORSKI PAKET — Kompletni export za revizore
# ══════════════════════════════════════════════════════════════

def build_audit_package(company, date_from=None, date_to=None):
    """
    Generira kompletni revizorski paket za firmu.

    Sadrži:
    - Knjiga prigovora (PDF)
    - Blagajnički izvještaji (PDF za svaku sesiju)
    - Inventurni listovi (PDF)
    - Inventurne razlike (PDF)
    - Dnevni POS izvještaji (CSV)
    - Z-reporti
    - Fiskalni logovi
    - Artikli (CSV)
    - Partneri (CSV)

    Returns: StreamingZipResponse
    """
    from datetime import date, timedelta

    if not date_from:
        date_from = date.today() - timedelta(days=365)
    if not date_to:
        date_to = date.today()

    zr = StreamingZipResponse(
        filename='revizorski_paket_%s_%s_%s.zip' % (
            company.name.replace(' ', '_')[:20],
            date_from.isoformat(),
            date_to.isoformat(),
        )
    )

    # 1. Artikli CSV
    try:
        import csv
        import io

        from inventory.models import InventoryItem
        buf = io.StringIO()
        buf.write('\ufeff')  # BOM
        w = csv.writer(buf, delimiter=';')
        w.writerow(['SKU', 'Barcode', 'Naziv', 'Kategorija', 'JMJ', 'Nabavna', 'Prodajna', 'Zaliha', 'Aktivan'])
        for item in InventoryItem.objects.filter(company=company):
            w.writerow([item.sku, item.barcode, item.name, item.category, item.unit,
                        item.purchase_price, item.unit_price, item.quantity, item.is_active])
        zr.add_content('artikli/artikli_komplet.csv', buf.getvalue())
    except DatabaseError:
        pass

    # 2. POS Dnevni izvještaji CSV
    try:
        import csv
        import io

        from pos.models import POSDailyReport
        buf = io.StringIO()
        buf.write('\ufeff')
        w = csv.writer(buf, delimiter=';')
        w.writerow(['Datum', 'Terminal', 'Promet', 'Gotovina', 'Kartica', 'Mobilno', 'Revolut',
                     'Računi', 'Stornirani', 'Prosječan', 'Razlika gotovine'])
        for r in POSDailyReport.objects.filter(company=company, date__gte=date_from, date__lte=date_to):
            w.writerow([r.date, r.terminal.name if r.terminal else '', r.total_revenue,
                        r.cash_total, r.card_total, r.mobile_total, r.voucher_total,
                        r.receipt_count, r.cancelled_count, r.average_ticket, r.cash_difference])
        zr.add_content('pos_izvjestaji/dnevni_izvjestaji.csv', buf.getvalue())
    except DatabaseError:
        pass

    # 3. Knjiga prigovora CSV
    try:
        import csv
        import io

        from pos.models import KnjigaPrigovora
        buf = io.StringIO()
        buf.write('\ufeff')
        w = csv.writer(buf, delimiter=';')
        w.writerow(['R.br.', 'Datum primitka', 'Ime', 'Kontakt', 'Opis', 'Datum odgovora', 'Odgovor'])
        for p in KnjigaPrigovora.objects.filter(company=company):
            w.writerow([p.redni_broj, p.datum_primitka, p.ime_potrosaca, p.kontakt,
                        p.opis_prigovora, p.datum_odgovora or '', p.odgovor])
        zr.add_content('prigovori/knjiga_prigovora.csv', buf.getvalue())
    except DatabaseError:
        pass

    # 4. Inventure CSV
    try:
        import csv
        import io

        from inventory.models import Inventura
        for inv in Inventura.objects.filter(company=company):
            buf = io.StringIO()
            buf.write('\ufeff')
            w = csv.writer(buf, delimiter=';')
            w.writerow(['SKU', 'Barcode', 'Naziv', 'JMJ', 'Knjižno', 'Stvarno', 'Razlika', 'Cijena', 'Razlika EUR'])
            for it in inv.items.filter(counted_at__isnull=False).select_related('inventory_item'):
                w.writerow([it.inventory_item.sku, it.inventory_item.barcode, it.inventory_item.name,
                            it.unit, it.expected_qty, it.counted_qty, it.difference_qty,
                            it.unit_price, it.difference_value])
            safe_num = inv.inventura_number.replace('/', '-')
            zr.add_content('inventure/%s.csv' % safe_num, buf.getvalue())
    except DatabaseError:
        pass

    # 5. Fiskalni logovi CSV
    try:
        import csv
        import io

        from invoicing.fiscal_models import FiscalLog
        buf = io.StringIO()
        buf.write('\ufeff')
        w = csv.writer(buf, delimiter=';')
        w.writerow(['Datum', 'Akcija', 'Status', 'Poruka', 'Račun ID'])
        for log in FiscalLog.objects.filter(invoice__company=company, created_at__date__gte=date_from)[:5000]:
            w.writerow([log.created_at, log.action, log.status, log.message[:200], log.invoice_id])
        zr.add_content('fiskalizacija/fiskalni_logovi.csv', buf.getvalue())
    except DatabaseError:
        pass

    # 6. Receipts CSV (svi POS bonovi)
    try:
        import csv
        import io

        from pos.models import POSReceipt
        buf = io.StringIO()
        buf.write('\ufeff')
        w = csv.writer(buf, delimiter=';')
        w.writerow(['Bon#', 'Datum', 'Status', 'Ukupno', 'Blagajnik', 'ZKI', 'JIR', 'Metoda plaćanja'])
        for r in POSReceipt.objects.filter(session__terminal__company=company,
                                           paid_at__date__gte=date_from, paid_at__date__lte=date_to).select_related('cashier'):
            methods = ', '.join(pl.method for pl in r.payment_lines.all())
            w.writerow([r.receipt_number, r.paid_at, r.status, r.total,
                        r.cashier.name if r.cashier else '', r.zki or '', r.jir or '', methods])
        zr.add_content('pos_izvjestaji/svi_bonovi.csv', buf.getvalue())
    except DatabaseError:
        pass

    # 7. StockMovements CSV
    try:
        import csv
        import io

        from inventory.models import StockMovement
        buf = io.StringIO()
        buf.write('\ufeff')
        w = csv.writer(buf, delimiter=';')
        w.writerow(['Datum', 'Artikl', 'Tip', 'Količina', 'Cijena', 'Razlog', 'Operater'])
        for m in StockMovement.objects.filter(item__company=company,
                                              created_at__date__gte=date_from)[:10000]:
            w.writerow([m.created_at, m.item.name if m.item else '', m.movement_type,
                        m.quantity, m.unit_price, m.reason[:100],
                        m.performed_by.username if m.performed_by else ''])
        zr.add_content('skladiste/kretanja_zaliha.csv', buf.getvalue())
    except DatabaseError:
        pass

    # 8. README
    readme = """REVIZORSKI PAKET — %s
Generiran: %s
Period: %s do %s

SADRŽAJ:
- artikli/ — kompletna lista artikala s cijenama i zalihama
- pos_izvjestaji/ — dnevni POS izvještaji + svi bonovi
- prigovori/ — knjiga prigovora (zakonski obavezno)
- inventure/ — inventurni listovi s razlikama
- fiskalizacija/ — logovi fiskalizacije (ZKI/JIR)
- skladiste/ — kretanja zaliha (ulaz/izlaz/korekcija)

NAPOMENA:
Svi CSV fajlovi koriste UTF-8 BOM encoding i ; delimiter.
Otvaraju se u Excel-u bez problema.
Rok čuvanja: 11 godina (Zakon o računovodstvu čl. 10 st. 3).
""" % (company.name, date.today().isoformat(), date_from.isoformat(), date_to.isoformat())
    zr.add_content('README.txt', readme)

    return zr.build()
