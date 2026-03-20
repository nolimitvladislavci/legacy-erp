import csv, io, zipfile, os
from decimal import Decimal
from django.core.management.base import BaseCommand
from pos.models import POSReceipt, POSSession

class Command(BaseCommand):
    help = 'Generira DSFinV-K export koristeći stvarna polja baze.'

    def add_arguments(self, parser):
        parser.add_argument('--company-id', type=str, required=True)
    
    def fmt_dec(self, value):
        if value is None: return "0,00"
        return str(Decimal(str(value)).quantize(Decimal('0.00'))).replace('.', ',')

    def handle(self, *args, **options):
        c_id = options['company_id']
        sessions = POSSession.objects.filter(terminal__company_id=c_id)
        if not sessions.exists():
            self.stdout.write(self.style.WARNING(f"Nema sesija za ID {c_id}"))
            return

        transactions, lines, closing = [], [], []
        for s in sessions:
            # Polje opened_at koje smo jučer potvrdili
            op_at = s.opened_at.isoformat() if s.opened_at else "N/A"
            closing.append([s.terminal.name, op_at, s.id, op_at[:10]])
            
            for r in POSReceipt.objects.filter(session=s):
                transactions.append([
                    s.terminal.name, op_at, str(r.uuid), 
                    r.receipt_number, 'Beleg', 
                    r.fiscal_datetime.isoformat() if r.fiscal_datetime else '', 
                    r.zki[:10] if r.zki else ''
                ])
                # Jedna testna stavka za svaki račun koristeći polje 'total'
                lines.append([
                    s.terminal.name, op_at, str(r.uuid), 
                    1, 'TEST-ART', 'Testna stavka', '1,00', 
                    self.fmt_dec(r.total), '1'
                ])

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for name, head, data in [
                ('transactions.csv', ['Z_KASSE_ID', 'Z_ERSTELLUNG', 'BON_ID', 'BON_NR', 'BON_TYP', 'TSE_SIGNATUR_ERSTELLUNG', 'TSE_ZERTIFIKAT_ID'], transactions),
                ('lines.csv', ['Z_KASSE_ID', 'Z_ERSTELLUNG', 'BON_ID', 'POS_ZEILE', 'ART_NR', 'ART_NAME', 'MENGE', 'PREIS', 'UST_SCHLUESSEL'], lines),
                ('cashpointclosing.csv', ['Z_KASSE_ID', 'Z_ERSTELLUNG', 'Z_NR', 'Z_BUCHUNGSTAG'], closing)
            ]:
                out = io.StringIO()
                w = csv.writer(out, delimiter=';', lineterminator='\r\n')
                w.writerow(head)
                w.writerows(data)
                zipf.writestr(name, out.getvalue().encode('utf-8'))

        filename = f"DSFinV_K_Export_{c_id[:8]}.zip"
        with open(filename, 'wb') as f:
            f.write(zip_buffer.getvalue())
        self.stdout.write(self.style.SUCCESS(f'[✔] ZIP kreiran: {filename}'))
