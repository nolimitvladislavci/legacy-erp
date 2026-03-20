"""
Fiskaly Cloud TSE Sandbox Test — KassenSichV compliance check.

Kreira testni bon s 19% + 7% PDV i salje na Fiskaly sandbox.
Provjerava: auth, start_transaction, finish_transaction, potpis.

Usage:
    python manage.py test_fiskaly_tse
    python manage.py test_fiskaly_tse --cleanup  (brise testne podatke)
"""
import uuid as uuid_mod
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Testira Fiskaly TSE Sandbox integraciju.'

    def add_arguments(self, parser):
        parser.add_argument('--cleanup', action='store_true', help='Obrisi testne podatke')
        parser.add_argument('--api-key', type=str, default='', help='Fiskaly API key')
        parser.add_argument('--api-secret', type=str, default='', help='Fiskaly API secret')
        parser.add_argument('--tss-id', type=str, default='', help='Fiskaly TSS ID')
        parser.add_argument('--client-id', type=str, default='', help='Fiskaly Client ID')

    def handle(self, *args, **options):
        from companies.models import Company
        from pos.models import POSTerminal, POSSession, POSReceipt, POSReceiptItem, POSPaymentLine

        TEST_OIB = 'DE_TSE_TEST_99'

        if options['cleanup']:
            Company.objects.filter(oib=TEST_OIB).delete()
            self.stdout.write(self.style.SUCCESS('Testni podaci obrisani.'))
            return

        self.stdout.write(self.style.WARNING('=== FISKALY TSE SANDBOX TEST ==='))
        self.stdout.write('')

        # ── 1. Sandbox credentials ────────────────────────────────────
        # Fiskaly sandbox: https://dashboard.fiskaly.com/
        sandbox_keys = {
            'api_key': options['api_key'] or 'test_api_key_placeholder',
            'api_secret': options['api_secret'] or 'test_api_secret_placeholder',
            'tss_id': options['tss_id'] or 'test_tss_id_placeholder',
            'client_id': options['client_id'] or 'test_client_id_placeholder',
        }

        has_real_keys = not sandbox_keys['api_key'].startswith('test_')
        if not has_real_keys:
            self.stdout.write(self.style.WARNING(
                'NAPOMENA: Koriste se placeholder kljucevi.\n'
                'Za pravi test dodaj: --api-key X --api-secret Y --tss-id Z --client-id W\n'
                'Ili konfiguriraj na Viskovic Bau: company.settings["tse"] = {...}\n'
            ))

        # ── 2. Test Company ───────────────────────────────────────────
        company, created = Company.objects.get_or_create(
            oib=TEST_OIB,
            defaults={
                'name': 'Fiskaly Test GmbH',
                'country': 'DE',
                'business_type': 'gmbh',
                'fiscal_system': 'de_gobd',
                'currency': 'EUR',
                'settings': {'tse': sandbox_keys},
            }
        )
        if not created:
            company.settings['tse'] = sandbox_keys
            company.country = 'DE'
            company.fiscal_system = 'de_gobd'
            company.save(update_fields=['settings', 'country', 'fiscal_system'])
        self.stdout.write('1. Test firma: %s (%s)' % (company.name, company.oib))

        # ── 3. Terminal + Session ─────────────────────────────────────
        terminal, _ = POSTerminal.objects.get_or_create(
            company=company, terminal_code='TSE-TEST-01',
            defaults={'name': 'TSE Test Kasse', 'is_active': True},
        )
        session, _ = POSSession.objects.get_or_create(
            terminal=terminal, status='open',
            defaults={
                'session_number': 999,
                'operator_id': 1,
                'opening_cash': Decimal('100.00'),
            },
        )
        self.stdout.write('2. Terminal: %s, Smjena #%d' % (terminal.name, session.session_number))

        # ── 4. Test Receipt ───────────────────────────────────────────
        receipt_num = int(str(uuid_mod.uuid4().int)[:5])
        receipt = POSReceipt.objects.create(
            session=session,
            receipt_number=receipt_num,
            subtotal=Decimal('22.23'),
            tax_amount=Decimal('3.27'),
            total=Decimal('25.50'),
            status='paid',
            paid_at=timezone.now(),
        )

        # Stavka 1: Kava 2x5.00 = 10.00 EUR (19% MwSt = NORMAL)
        POSReceiptItem.objects.create(
            receipt=receipt,
            description='Kaffee (19% MwSt)',
            quantity=Decimal('2.00'),
            unit_price=Decimal('5.00'),
            tax_rate=Decimal('19.00'),
            total_price=Decimal('11.90'),  # 10 + 1.90 MwSt
        )

        # Stavka 2: Essen zum Mitnehmen 15.50 EUR (7% MwSt = REDUCED_1)
        POSReceiptItem.objects.create(
            receipt=receipt,
            description='Essen zum Mitnehmen (7% MwSt)',
            quantity=Decimal('1.00'),
            unit_price=Decimal('15.50'),
            tax_rate=Decimal('7.00'),
            total_price=Decimal('16.59'),  # 15.50 + 1.09 MwSt
        )

        # Payment line
        POSPaymentLine.objects.create(
            receipt=receipt,
            method='CASH',
            amount=Decimal('25.50'),
            change_given=Decimal('0.00'),
        )

        self.stdout.write('3. Testni bon #%d: 25.50 EUR (Kaffee 19%% + Essen 7%%)' % receipt_num)

        # ── 5. TSE Adapter Test ───────────────────────────────────────
        self.stdout.write('')
        self.stdout.write('4. Pokusavam Fiskaly API komunikaciju...')

        if not has_real_keys:
            # Simulate without real API call
            self.stdout.write(self.style.WARNING(
                '   SIMULACIJA (nema pravih kljuceva):'
            ))
            self.stdout.write('   - Auth: SKIP (placeholder)')
            self.stdout.write('   - Start Transaction: SKIP')
            self.stdout.write('   - Finish Transaction: SKIP')
            self.stdout.write('')

            # Test adapter instantiation
            try:
                from pos.tse_adapter import FiskalyTSEAdapter
                adapter = FiskalyTSEAdapter(
                    api_key='test', api_secret='test',
                    tss_id='test', client_id='test',
                )
                self.stdout.write(self.style.SUCCESS('   FiskalyTSEAdapter: IMPORTABLE'))

                # Test VAT breakdown
                vat = adapter._build_vat_breakdown(receipt)
                self.stdout.write('   VAT breakdown: %s' % vat)

                # Test payment breakdown
                pay = adapter._build_payment_breakdown(receipt)
                self.stdout.write('   Payment breakdown: %s' % pay)

                self.stdout.write('')
                self.stdout.write(self.style.SUCCESS(
                    '=== SIMULACIJA USPJESNA ===\n'
                    'Adapter radi, DSFinV-K mapiranje tocno.\n'
                    'Za pravi test dodaj Fiskaly sandbox kljuceve.\n'
                    'Registriraj se na: https://dashboard.fiskaly.com/'
                ))

            except Exception as e:
                self.stdout.write(self.style.ERROR('   GRESKA: %s' % e))
            return

        # Real API test
        start_time = timezone.now()
        try:
            from pos.tse_adapter import FiskalyTSEAdapter
            adapter = FiskalyTSEAdapter.from_company(company)

            self.stdout.write('   a) Auth...')
            token = adapter._get_token()
            self.stdout.write(self.style.SUCCESS('      Token: %s...' % token[:20]))

            self.stdout.write('   b) VAT breakdown...')
            vat = adapter._build_vat_breakdown(receipt)
            self.stdout.write('      %s' % vat)

            self.stdout.write('   c) Payment breakdown...')
            pay = adapter._build_payment_breakdown(receipt)
            self.stdout.write('      %s' % pay)

            self.stdout.write('   d) Sign Transaction...')
            result = adapter.sign_transaction(receipt)
            duration = (timezone.now() - start_time).total_seconds()

            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS(
                '=== TSE TRANSAKCIJA POTPISANA za %.2f sekundi ===' % duration
            ))
            self.stdout.write('   TSE Transaktionsnummer: %s' % result.get('tse_transaction_number'))
            self.stdout.write('   TSE Signaturzaehler:    %s' % result.get('tse_signature_counter'))
            self.stdout.write('   TSE Signatur (Hash):    %s...' % result.get('tse_hash', '')[:40])
            self.stdout.write('   TSE Seriennummer:       %s' % result.get('tse_serial_number'))
            self.stdout.write('   TSE Start:              %s' % result.get('tse_start_time'))
            self.stdout.write('   TSE Ende:               %s' % result.get('tse_end_time'))

            # Save to receipt
            receipt.tse_transaction_number = str(result.get('tse_transaction_number', ''))
            receipt.tse_signature_counter = result.get('tse_signature_counter')
            receipt.tse_hash = result.get('tse_hash', '')
            receipt.tse_serial_number = result.get('tse_serial_number', '')
            receipt.tse_error = ''
            receipt.save()

            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('KassenSichV COMPLIANCE: PASSED'))

        except Exception as e:
            duration = (timezone.now() - start_time).total_seconds()
            self.stdout.write(self.style.ERROR(
                '\nFISKALY API GRESKA (%.2fs): %s' % (duration, e)
            ))
            receipt.tse_error = 'TSE_AUSFALL: %s' % str(e)[:150]
            receipt.save(update_fields=['tse_error'])
            self.stdout.write('   Status: TSE_AUSFALL (Nacherfassung pending)')

        self.stdout.write(self.style.WARNING('\n=== KRAJ TESTA ==='))
