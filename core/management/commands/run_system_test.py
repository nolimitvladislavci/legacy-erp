"""
Management command: run_system_test
Pokreće kompletni simulacijski test sustava i šalje WhatsApp report.
Može se pozivati: manage.py run_system_test --notify=+4915771998747
Ili automatski iz Celery beat.
"""
import subprocess
from datetime import datetime

from django.core.management.base import BaseCommand
from django.db import DatabaseError


IVAN_DE_PHONE = '+4915771998747'

MODULI = [
    ('invoicing', 'Invoicing / Fakture'),
    ('pos', 'POS / Blagajne'),
    ('worktime', 'Worktime / Sati'),
    ('konto', 'Konto / Računovodstvo'),
    ('udruge', 'Udruge (9 segmenata)'),
    ('tax_wizard', 'Tax Wizard'),
    ('delivery', 'Delivery / Transport'),
    ('documents', 'Arhiva / Dokumenti'),
    ('fiscal', 'Fiskalizacija'),
    ('partners', 'Partneri / Klijenti'),
    ('notifications', 'Notifikacije'),
]


class Command(BaseCommand):
    help = 'Potpuni simulacijski test sustava — FENIX test runner'

    def add_arguments(self, parser):
        parser.add_argument('--notify', type=str, default=IVAN_DE_PHONE,
                            help='WhatsApp broj za report')
        parser.add_argument('--quick', action='store_true',
                            help='Samo django check + import test, bez run_tests')

    def handle(self, *args, **options):
        phone = options['notify']
        quick = options['quick']
        start = datetime.now()

        self.stdout.write(self.style.SUCCESS(f'\n🤖 FENIX TEST RUNNER — {start.strftime("%d.%m.%Y %H:%M")}\n'))

        results = {
            'ok': [],
            'warning': [],
            'critical': [],
            'fixes': [],
        }

        # 1. Django system check
        self._run_django_check(results)

        # 2. Import test — svi moduli
        self._run_import_test(results)

        # 3. Migracije
        self._run_migration_check(results)

        # 4. Servis status
        self._run_service_check(results)

        # 5. Poslovne logike (quick smoke)
        self._run_business_smoke(results)

        # 6. Postojeći Django testovi
        if not quick:
            self._run_existing_tests(results)

        # 7. Fiskalizacija status
        self._run_fiscal_check(results)

        # 8. Report
        elapsed = (datetime.now() - start).seconds
        self._send_report(phone, results, elapsed, start)

    def _run_django_check(self, results):
        self.stdout.write('→ Django system check...')
        try:
            from django.core.management import call_command
            from io import StringIO
            out = StringIO()
            call_command('check', stdout=out, stderr=out)
            output = out.getvalue()
            if 'System check identified no issues' in output or 'no issues' in output.lower():
                results['ok'].append('Django system check: čist')
            else:
                results['warning'].append(f'Django check: {output[:200]}')
        except ImportError as e:
            results['critical'].append(f'Django check CRASH: {e}')

    def _run_import_test(self, results):
        self.stdout.write('→ Import test modula...')
        import importlib
        for app_name, label in MODULI:
            try:
                mod = importlib.import_module(f'{app_name}.models')
                results['ok'].append(f'{label}: import OK')
            except ImportError as e:
                results['critical'].append(f'{label}: ImportError — {e}')
            except ImportError as e:
                results['warning'].append(f'{label}: {type(e).__name__} — {e}')

    def _run_migration_check(self, results):
        self.stdout.write('→ Provjera migracija...')
        try:
            result = subprocess.run(
                ['/var/www/fina-connect/venv/bin/python', 'manage.py',
                 'showmigrations', '--plan'],
                cwd='/var/www/fina-connect',
                capture_output=True, text=True, timeout=30
            )
            pending = [l for l in result.stdout.split('\n') if '[ ]' in l]
            if pending:
                results['warning'].append(f'Neprimijenjene migracije: {len(pending)}')
                for p in pending[:5]:
                    results['warning'].append(f'  {p.strip()}')
            else:
                results['ok'].append('Migracije: sve primijenjene')
        except (ValueError, AttributeError) as e:
            results['warning'].append(f'Migration check error: {e}')

    def _run_service_check(self, results):
        self.stdout.write('→ Servis status...')
        servisi = ['gunicorn-fina', 'celery-worker', 'celery-beat', 'redis', 'postgresql']
        for svc in servisi:
            try:
                r = subprocess.run(['systemctl', 'is-active', svc],
                                   capture_output=True, text=True, timeout=5)
                status = r.stdout.strip()
                if status == 'active':
                    results['ok'].append(f'{svc}: aktivan')
                else:
                    results['critical'].append(f'{svc}: {status} — NIJE AKTIVAN')
            except (ValueError, AttributeError):
                results['warning'].append(f'{svc}: provjera nije moguća')

    def _run_business_smoke(self, results):
        self.stdout.write('→ Business logic smoke test...')
        try:
            from invoicing.models import Invoice
            cnt = Invoice.objects.count()
            results['ok'].append(f'Invoicing: {cnt} faktura dostupno')
        except DatabaseError as e:
            results['critical'].append(f'Invoicing model crash: {e}')

        try:
            from pos.models import POSTerminal
            cnt = POSTerminal.objects.count()
            results['ok'].append(f'POS: {cnt} terminala')
        except DatabaseError as e:
            results['critical'].append(f'POS model crash: {e}')

        try:
            from worktime.models import TimeEntry
            cnt = TimeEntry.objects.count()
            results['ok'].append(f'Worktime: {cnt} unosa')
        except DatabaseError as e:
            results['critical'].append(f'Worktime model crash: {e}')

        try:
            from udruge.models import UdrugaMember
            results['ok'].append('Udruge: modeli OK')
        except ImportError:
            try:
                from udruge.models import Loviste
                results['ok'].append('Udruge: modeli OK (Loviste)')
            except ImportError as e:
                results['warning'].append(f'Udruge: {e}')

        try:
            from tax_wizard.models import TaxFormTemplate, TaxDeadline
            forms = TaxFormTemplate.objects.count()
            deadlines = TaxDeadline.objects.count()
            results['ok'].append(f'Tax Wizard: {forms} obrazaca, {deadlines} deadlineova')
        except DatabaseError as e:
            results['warning'].append(f'Tax Wizard: {e}')

    def _run_fiscal_check(self, results):
        self.stdout.write('→ Fiskalizacija provjera...')
        try:
            from fiscal.models import FiscalLog
            pending = FiscalLog.objects.filter(jir='').exclude(zki='').count()
            failed = FiscalLog.objects.filter(status='error').count()
            if pending > 0:
                results['critical'].append(
                    f'Fiskalizacija: {pending} računa bez JIR! (rok 48h)')
            if failed > 0:
                results['warning'].append(
                    f'Fiskalizacija: {failed} neuspjelih pokušaja')
            if pending == 0 and failed == 0:
                results['ok'].append('Fiskalizacija: sve čisto')
        except DatabaseError as e:
            results['warning'].append(f'Fiscal check: {e}')

    def _run_existing_tests(self, results):
        self.stdout.write('→ Django test suite (ovo traje 2-5 min)...')
        try:
            r = subprocess.run(
                ['/var/www/fina-connect/venv/bin/python', 'manage.py', 'test',
                 '--verbosity=1', '--keepdb',
                 'invoicing', 'pos', 'worktime', 'konto', 'archiva'],
                cwd='/var/www/fina-connect',
                capture_output=True, text=True, timeout=300
            )
            output = r.stdout + r.stderr
            if 'OK' in output and 'FAILED' not in output:
                # Izvuci broj testova
                import re
                m = re.search(r'Ran (\d+) test', output)
                n = m.group(1) if m else '?'
                results['ok'].append(f'Django testovi: {n} testova — SVI PROŠLI ✅')
            else:
                # Izvuci greške
                lines = [l for l in output.split('\n') if 'FAIL' in l or 'ERROR' in l]
                results['critical'].append(f'Django testovi FAILED: {len(lines)} grešaka')
                for l in lines[:5]:
                    results['critical'].append(f'  {l}')
        except subprocess.TimeoutExpired:
            results['warning'].append('Django testovi: timeout (>5 min)')
        except (ValueError, AttributeError) as e:
            results['warning'].append(f'Django testovi: {e}')

    def _send_report(self, phone, results, elapsed, start):
        ok_n = len(results['ok'])
        warn_n = len(results['warning'])
        crit_n = len(results['critical'])
        total = ok_n + warn_n + crit_n

        emoji = '✅' if crit_n == 0 else ('🔴' if crit_n > 2 else '🟠')

        lines = [
            f'{emoji} FENIX TEST REPORT',
            f'📅 {start.strftime("%d.%m.%Y %H:%M")} ({elapsed}s)',
            '',
            f'✅ OK: {ok_n}/{total}',
            f'🔴 Kritično: {crit_n}',
            f'🟠 Upozorenja: {warn_n}',
        ]

        if results['critical']:
            lines.append('\n🔴 KRITIČNO:')
            for c in results['critical'][:5]:
                lines.append(f'  • {c}')

        if results['warning']:
            lines.append('\n🟠 UPOZORENJA:')
            for w in results['warning'][:5]:
                lines.append(f'  • {w}')

        lines.append('\nhttps://limit-connect.com/superadmin/ai/')

        message = '\n'.join(lines)

        self.stdout.write('\n' + message)

        # Pošalji WhatsApp
        try:
            from core.whatsapp import send_text as send_whatsapp_text
            send_whatsapp_text(phone=phone, message=message)
            self.stdout.write(self.style.SUCCESS(f'\n📱 WhatsApp poslan na {phone}'))
        except ImportError as e:
            self.stdout.write(self.style.ERROR(f'\n⚠️ WhatsApp NIJE poslan: {e}'))
