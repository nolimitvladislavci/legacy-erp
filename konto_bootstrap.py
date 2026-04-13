#!/usr/bin/env python3
"""
Konto bootstrap — popunjava kontni plan + retroaktivno knjizi fakture.
Run: cd /var/www/fina-connect && source venv/bin/activate && python3 konto_bootstrap.py
"""
import os

os.environ['DJANGO_SETTINGS_MODULE'] = 'core.settings'
import django; django.setup()

from decimal import Decimal

from django.db import transaction

from companies.models import Company
from invoicing.models import Invoice
from konto.models import JournalEntry, KontoAccount, LedgerLine


def print_status(msg):
    print(f'[+] {msg}')

# ══════════════════════════════════════════════════════════════
# 1. KONTNI PLAN — RRiF standard za HR (najcesce koristen)
# ══════════════════════════════════════════════════════════════

KONTNI_PLAN = [
    # Klasa 0 — Dugotrajna imovina
    ('0', 'Dugotrajna imovina', 'asset'),
    ('0200', 'Gradevinski objekti', 'asset'),
    ('0300', 'Postrojenja i oprema', 'asset'),
    ('0400', 'Alati i inventar', 'asset'),
    ('0700', 'Goodwill i nematerijalna imovina', 'asset'),
    ('0900', 'Ispravak vrijednosti (amortizacija)', 'asset'),

    # Klasa 1 — Kratkotrajna imovina
    ('1', 'Kratkotrajna imovina', 'asset'),
    ('1000', 'Ziro racun u banci', 'asset'),
    ('1010', 'Devizni racun', 'asset'),
    ('1100', 'Blagajna (gotovina)', 'asset'),
    ('1200', 'Potrazivanja od kupaca', 'asset'),
    ('1300', 'Potrazivanja od zaposlenih', 'asset'),
    ('1400', 'Dani predujmovi', 'asset'),
    ('1500', 'Zalihe materijala', 'asset'),
    ('1600', 'Zalihe gotovih proizvoda', 'asset'),
    ('1700', 'Zalihe robe', 'asset'),

    # Klasa 2 — Kratkorocne obveze
    ('2', 'Kratkorocne obveze', 'liability'),
    ('2200', 'Obveze prema dobavljacima', 'liability'),
    ('2300', 'Obveze za poreze i doprinose', 'liability'),
    ('2400', 'Obveza za PDV', 'liability'),
    ('2401', 'Pretporez (ulazni PDV)', 'asset'),
    ('2500', 'Obveze za place', 'liability'),
    ('2600', 'Primljeni predujmovi', 'liability'),
    ('2700', 'Ostale kratkorocne obveze', 'liability'),

    # Klasa 3 — Dugorocne obveze
    ('3', 'Dugorocne obveze', 'liability'),
    ('3100', 'Krediti banaka', 'liability'),
    ('3200', 'Obveze po leasingu', 'liability'),

    # Klasa 4 — Troskovi
    ('4', 'Troskovi', 'expense'),
    ('4000', 'Nabavna vrijednost prodane robe', 'expense'),
    ('4100', 'Troskovi sirovina i materijala', 'expense'),
    ('4200', 'Troskovi usluga', 'expense'),
    ('4300', 'Amortizacija', 'expense'),
    ('4400', 'Ostali troskovi poslovanja', 'expense'),

    # Klasa 5 — Troskovi osoblja
    ('5', 'Troskovi osoblja', 'expense'),
    ('5000', 'Bruto place', 'expense'),
    ('5100', 'Doprinosi na place', 'expense'),
    ('5200', 'Dnevnice i putni troskovi', 'expense'),
    ('5300', 'Ostali troskovi osoblja', 'expense'),

    # Klasa 6 — Ostali troskovi
    ('6', 'Ostali troskovi i financijski rashodi', 'expense'),
    ('6000', 'Troskovi reprezentacije', 'expense'),
    ('6100', 'Osiguranja', 'expense'),
    ('6200', 'Bankarski troskovi', 'expense'),
    ('6300', 'Kamate na kredite', 'expense'),
    ('6400', 'Tecajne razlike', 'expense'),

    # Klasa 7 — Prihodi
    ('7', 'Prihodi', 'income'),
    ('7000', 'Prihodi od prodaje robe', 'income'),
    ('7100', 'Prihodi od usluga', 'income'),
    ('7200', 'Prihodi od prodaje u inozemstvo', 'income'),
    ('7300', 'Ostali poslovni prihodi', 'income'),
    ('7500', 'Financijski prihodi', 'income'),
    ('7900', 'Izvanredni prihodi', 'income'),

    # Klasa 8 — Rezultat
    ('8', 'Rezultat poslovanja', 'equity'),
    ('8000', 'Dobit prije oporezivanja', 'equity'),
    ('8100', 'Porez na dobit', 'expense'),
    ('8200', 'Dobit nakon oporezivanja', 'equity'),

    # Klasa 9 — Kapital
    ('9', 'Kapital', 'equity'),
    ('9000', 'Temeljni kapital', 'equity'),
    ('9100', 'Zadrzana dobit', 'equity'),
    ('9200', 'Dobit tekuce godine', 'equity'),
]

def bootstrap_kontni_plan(company):
    """Create standard HR kontni plan for company."""
    created = 0
    for code, name, acc_type in KONTNI_PLAN:
        _, was_created = KontoAccount.objects.get_or_create(
            company=company, code=code,
            defaults={'name': name, 'account_type': acc_type}
        )
        if was_created:
            created += 1
    return created


# ══════════════════════════════════════════════════════════════
# 2. RETROAKTIVNO KNJIZENJE FAKTURA
# ══════════════════════════════════════════════════════════════

def book_invoice(invoice, company):
    """
    Proknijzi jednu fakturu u dvostavno knjigovodstvo.

    Izlazni racun (R, FA, POS):
      Duguje: 1200 Potrazivanja od kupaca (bruto iznos)
      Potrazuje: 7100 Prihodi od usluga (neto iznos)
      Potrazuje: 2400 Obveza za PDV (PDV iznos)

    Ulazni racun (URA):
      Duguje: 4200 Troskovi usluga (neto iznos)
      Duguje: 2401 Pretporez (PDV iznos)
      Potrazuje: 2200 Obveze prema dobavljacima (bruto iznos)

    Storno (S):
      Obrnuto od originalnog knjizenja.
    """
    # Skip if already booked
    if JournalEntry.objects.filter(source_invoice=invoice, company=company).exists():
        return None

    # Skip drafts
    if invoice.status == 'DRAFT':
        return None

    total = invoice.total or Decimal('0')
    tax = invoice.tax_amount or Decimal('0')
    net = total - tax

    if total <= 0 and invoice.doctype != 'S':
        return None

    date = invoice.date_issued
    if hasattr(date, 'date'):
        date = date.date()
    if not date:
        return None

    # Determine accounts based on doctype
    if invoice.doctype in ('R', 'FA', 'RN', 'POS', 'PO', 'P', 'A'):
        # Izlazni racun
        debit_account = '1200'  # Potrazivanja od kupaca
        credit_income = '7100'  # Prihodi od usluga
        credit_vat = '2400'     # Obveza za PDV
        desc_prefix = 'IRA'
    elif invoice.doctype == 'URA':
        # Ulazni racun
        debit_account = '4200'  # Troskovi usluga
        credit_income = None
        credit_vat = '2401'     # Pretporez
        credit_liability = '2200'  # Obveze prema dobavljacima
        desc_prefix = 'URA'
    elif invoice.doctype == 'S':
        # Storno - obrnuto knjizenje
        debit_account = '7100'
        credit_income = '1200'
        credit_vat = '2400'
        desc_prefix = 'STORNO'
        total = abs(total)
        tax = abs(tax)
        net = total - tax
    else:
        return None

    # Get or create accounts
    def get_account(code):
        acc, _ = KontoAccount.objects.get_or_create(
            company=company, code=code,
            defaults={'name': code, 'account_type': 'asset'}
        )
        return acc

    with transaction.atomic():
        # Create journal entry
        entry_num = f'{desc_prefix}-{invoice.number}'
        # Ensure unique
        base_num = entry_num
        counter = 1
        while JournalEntry.objects.filter(company=company, entry_number=entry_num).exists():
            entry_num = f'{base_num}-{counter}'
            counter += 1

        je = JournalEntry.objects.create(
            company=company,
            entry_number=entry_num,
            date=date,
            description=f'{desc_prefix}: {invoice.number} — {invoice.client_name or ""}',
            source_type='invoice',
            source_invoice=invoice,
            is_posted=True,
        )

        if invoice.doctype in ('R', 'FA', 'RN', 'POS', 'PO', 'P', 'A'):
            # Debit: Potrazivanja
            LedgerLine.objects.create(
                journal_entry=je, account=get_account(debit_account),
                side='debit', amount=total,
                description=f'Kupac: {invoice.client_name or ""}'
            )
            # Credit: Prihod
            if net > 0:
                LedgerLine.objects.create(
                    journal_entry=je, account=get_account(credit_income),
                    side='credit', amount=net,
                    description=f'Prihod: {invoice.number}'
                )
            # Credit: PDV
            if tax > 0:
                LedgerLine.objects.create(
                    journal_entry=je, account=get_account(credit_vat),
                    side='credit', amount=tax,
                    description=f'PDV: {invoice.number}'
                )

        elif invoice.doctype == 'URA':
            # Debit: Trosak
            if net > 0:
                LedgerLine.objects.create(
                    journal_entry=je, account=get_account(debit_account),
                    side='debit', amount=net,
                    description=f'Trosak: {invoice.number}'
                )
            # Debit: Pretporez
            if tax > 0:
                LedgerLine.objects.create(
                    journal_entry=je, account=get_account(credit_vat),
                    side='debit', amount=tax,
                    description=f'Pretporez: {invoice.number}'
                )
            # Credit: Obveza prema dobavljacu
            LedgerLine.objects.create(
                journal_entry=je, account=get_account(credit_liability),
                side='credit', amount=total,
                description=f'Dobavljac: {invoice.client_name or ""}'
            )

        elif invoice.doctype == 'S':
            # Storno - obrnuto
            LedgerLine.objects.create(
                journal_entry=je, account=get_account(debit_account),
                side='debit', amount=net,
            )
            if tax > 0:
                LedgerLine.objects.create(
                    journal_entry=je, account=get_account(credit_vat),
                    side='debit', amount=tax,
                )
            LedgerLine.objects.create(
                journal_entry=je, account=get_account(credit_income),
                side='credit', amount=total,
            )

    return je


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    print_status('Konto Bootstrap')
    print()

    for company in Company.objects.all():
        print_status(f'Firma: {company.name} ({company.oib})')

        # 1. Kontni plan
        created = bootstrap_kontni_plan(company)
        print(f'  Kontni plan: {created} novih konta')

        # 2. Retroaktivno knjizenje
        invoices = Invoice.objects.filter(company=company).exclude(status='DRAFT').order_by('date_issued')
        booked = skipped = errors = 0

        for inv in invoices:
            try:
                je = book_invoice(inv, company)
                if je:
                    booked += 1
                else:
                    skipped += 1
            except Exception as e:
                errors += 1
                if errors <= 3:
                    print(f'  ERROR: {inv.number}: {e}')

        print(f'  Knjizenje: {booked} proknjizeno, {skipped} preskoceno, {errors} gresaka')

    # Summary
    print()
    print_status('REZULTAT:')
    total_je = JournalEntry.objects.count()
    total_ll = LedgerLine.objects.count()
    total_ka = KontoAccount.objects.count()
    print(f'  Temeljnice: {total_je}')
    print(f'  Stavke knjizenja: {total_ll}')
    print(f'  Konta: {total_ka}')

    # Balance check
    for company in Company.objects.all():
        from django.db.models import Sum
        debits = LedgerLine.objects.filter(
            journal_entry__company=company, side='debit'
        ).aggregate(t=Sum('amount'))['t'] or Decimal('0')
        credits = LedgerLine.objects.filter(
            journal_entry__company=company, side='credit'
        ).aggregate(t=Sum('amount'))['t'] or Decimal('0')
        balanced = 'BALANCED' if debits == credits else f'IMBALANCE: {abs(debits-credits)}'
        if debits > 0:
            print(f'  {company.name}: D={debits:,.2f} P={credits:,.2f} [{balanced}]')
