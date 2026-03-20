"""
Monthly audit hash chain verification for all companies.
Run via cron: 0 3 1 * * /var/www/fina-connect/venv/bin/python manage.py audit_verify_all

Verifies SHA-256 hash chain integrity for every company and sends
email alert to admins if any chain is broken.
"""
from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone


class Command(BaseCommand):
    help = 'Verify audit hash chains for all companies and alert on failure.'

    def handle(self, *args, **options):
        from konto.models import LedgerLine
        from konto.integrity import verify_chain
        from companies.models import Company

        company_ids = (
            LedgerLine.objects
            .filter(integrity_hash__gt='')
            .values_list('journal_entry__company', flat=True)
            .distinct()
        )

        results = []
        failures = []

        for cid in company_ids:
            company = Company.objects.get(pk=cid)
            count = LedgerLine.objects.filter(
                journal_entry__company=company,
                integrity_hash__gt='',
            ).count()

            valid, broken_at = verify_chain(company)
            status = 'VALID' if valid else f'BROKEN at line {broken_at}'
            results.append({
                'company': company.name,
                'count': count,
                'valid': valid,
                'broken_at': broken_at,
            })

            if valid:
                self.stdout.write(f'  [OK]   {company.name}: {count} lines - VALID')
            else:
                self.stdout.write(self.style.ERROR(
                    f'  [FAIL] {company.name}: {count} lines - BROKEN at {broken_at}'
                ))
                failures.append(company.name)

        total = sum(r['count'] for r in results)
        self.stdout.write(f'\nTotal: {total} hashed lines across {len(results)} companies')

        if failures:
            self.stdout.write(self.style.ERROR(
                f'ALERT: {len(failures)} company chains BROKEN!'
            ))
            # Send email alert
            self._send_alert(failures, results)
        else:
            self.stdout.write(self.style.SUCCESS('All chains VALID.'))

    def _send_alert(self, failures, results):
        now = timezone.now()
        subject = f'[LIMIT Connect] AUDIT ALERT - Hash chain broken ({len(failures)} companies)'

        body_lines = [
            f'Audit Hash Chain Verification Report',
            f'Date: {now.strftime("%d.%m.%Y %H:%M")} UTC',
            f'',
            f'FAILURES DETECTED:',
        ]
        for r in results:
            if not r['valid']:
                body_lines.append(
                    f'  - {r["company"]}: BROKEN at line ID {r["broken_at"]} '
                    f'({r["count"]} total lines)'
                )
        body_lines.extend([
            '',
            'All results:',
        ])
        for r in results:
            status = 'VALID' if r['valid'] else f'BROKEN at {r["broken_at"]}'
            body_lines.append(f'  {r["company"]}: {r["count"]} lines - {status}')
        body_lines.extend([
            '',
            'Action required: Check the affected companies immediately.',
            'Run: python manage.py audit_verify_all',
            '',
            '-- LIMIT Connect ERP (automated)',
        ])

        body = '\n'.join(body_lines)

        try:
            admin_emails = [e for _, e in getattr(settings, 'ADMINS', [])]
            if not admin_emails:
                admin_emails = [getattr(settings, 'DEFAULT_FROM_EMAIL', 'admin@viskovic-group.de')]

            send_mail(
                subject,
                body,
                getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@viskovic-group.de'),
                admin_emails,
                fail_silently=True,
            )
            self.stdout.write(f'Alert email sent to: {", ".join(admin_emails)}')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Email alert failed: {e}'))
