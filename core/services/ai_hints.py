"""
core/services/ai_hints.py
AI Process Hints — inteligentni savjeti na Control Tower dashboardu.
Analizira stanje sustava i daje konkretne preporuke za akciju.
"""
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


def generate_hints(company, user=None):
    """
    Generate AI process hints based on current system state.
    Returns list of hint dicts: {level, icon, title, message, action_url, action_label, category}
    """
    hints = []
    now = timezone.now()
    today = now.date()

    try:
        _check_unpaid_invoices(company, hints, today)
        _check_eracun_status(company, hints)
        _check_konto_health(company, hints, today)
        _check_inventory_alerts(company, hints)
        _check_employees(company, hints)
        _check_bank_reconciliation(company, hints)
        _check_fiscal_compliance(company, hints, today)
        _check_module_suggestions(company, hints)
        _check_backup_status(hints)
    except Exception as e:
        logger.warning(f'AI hints error: {e}')

    # Sort by priority: critical > warning > info > success
    priority = {'critical': 0, 'warning': 1, 'info': 2, 'success': 3}
    hints.sort(key=lambda h: priority.get(h.get('level', 'info'), 2))

    return hints[:15]  # Max 15 hints


def _check_unpaid_invoices(company, hints, today):
    from invoicing.models import Invoice

    overdue = Invoice.objects.filter(
        company=company,
        status__in=['SENT', 'CONFIRMED', 'FISCALIZED', 'UNPAID'],
        date_due__lt=today,
    ).count()

    if overdue > 0:
        total = Invoice.objects.filter(
            company=company,
            status__in=['SENT', 'CONFIRMED', 'FISCALIZED', 'UNPAID'],
            date_due__lt=today,
        ).aggregate(t=__import__('django.db.models', fromlist=['Sum']).Sum('total'))['t'] or 0

        hints.append({
            'level': 'critical' if overdue > 10 else 'warning',
            'icon': 'bi-exclamation-triangle',
            'title': f'{overdue} neplacenih racuna nakon roka',
            'message': f'Ukupno {total:,.2f} EUR. Najstariji rok je prosao.',
            'action_url': '/hr/invoicing/?status=OVERDUE',
            'action_label': 'Pregledaj dospjele',
            'category': 'financije',
        })

    # Drafts older than 7 days
    old_drafts = Invoice.objects.filter(
        company=company, status='DRAFT',
        date_issued__lt=today - timedelta(days=7),
    ).count()
    if old_drafts > 0:
        hints.append({
            'level': 'info',
            'icon': 'bi-file-earmark-text',
            'title': f'{old_drafts} nacrt-racuna starijih od 7 dana',
            'message': 'Mozda su zaboravljeni? Potvrdite ili obrisite.',
            'action_url': '/hr/invoicing/?status=DRAFT',
            'action_label': 'Pregledaj nacrte',
            'category': 'dokumenti',
        })


def _check_eracun_status(company, hints):
    from eracun.models import ERacunConfig, ERacun

    try:
        config = company.eracun_config
    except Exception:
        hints.append({
            'level': 'warning',
            'icon': 'bi-envelope-paper',
            'title': 'e-Racun nije konfiguriran',
            'message': 'Fiskalizacija 2.0 zahtijeva e-racun od 01.01.2026. Konfigurirajte posrednika.',
            'action_url': '/eracun/posrednik/',
            'action_label': 'Konfiguriraj',
            'category': 'compliance',
        })
        return

    if not config.is_active:
        hints.append({
            'level': 'warning',
            'icon': 'bi-envelope-paper',
            'title': 'e-Racun neaktivan',
            'message': 'Modul postoji ali nije aktiviran.',
            'action_url': '/eracun/settings/',
            'action_label': 'Aktiviraj',
            'category': 'compliance',
        })

    # Unbooked incoming (AS4Message, not ERacun)
    unbooked = 0
    try:
        from einvoice.models.as4_message import AS4Message
        unbooked = AS4Message.objects.filter(
            company=company, direction='IN', status='DELIVERED'
        ).count()
    except Exception:
        pass
    if unbooked > 0:
        hints.append({
            'level': 'warning',
            'icon': 'bi-inbox',
            'title': f'{unbooked} primljenih e-racuna ceka knjizenje',
            'message': 'Proknjizite u URA za tocnu PDV evidenciju.',
            'action_url': '/eracun/inbox/',
            'action_label': 'Otvori inbox',
            'category': 'dokumenti',
        })


def _check_konto_health(company, hints, today):
    from konto.models import JournalEntry, KontoAccount
    from django.db.models import Sum

    je_count = JournalEntry.objects.filter(company=company).count()
    if je_count == 0:
        hints.append({
            'level': 'critical',
            'icon': 'bi-journal-x',
            'title': 'Knjigovodstvo prazno!',
            'message': 'Nema temeljnica. Pokrenite konto bootstrap za retroaktivno knjizenje.',
            'action_url': '/konto/',
            'action_label': 'Otvori konto',
            'category': 'financije',
        })
        return

    # Balance check
    from konto.models import LedgerLine
    debits = LedgerLine.objects.filter(
        journal_entry__company=company, side='debit'
    ).aggregate(t=Sum('amount'))['t'] or Decimal('0')
    credits = LedgerLine.objects.filter(
        journal_entry__company=company, side='credit'
    ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

    if debits != credits:
        hints.append({
            'level': 'critical',
            'icon': 'bi-exclamation-octagon',
            'title': 'Glavna knjiga NIJE balansirana!',
            'message': f'Duguje: {debits:,.2f}, Potrazuje: {credits:,.2f}, Razlika: {abs(debits-credits):,.2f}',
            'action_url': '/konto/',
            'action_label': 'Provjeri',
            'category': 'financije',
        })
    else:
        hints.append({
            'level': 'success',
            'icon': 'bi-check-circle',
            'title': f'Glavna knjiga balansirana ({je_count} temeljnica)',
            'message': f'D=P={debits:,.2f} EUR',
            'action_url': '/konto/',
            'action_label': 'Detalji',
            'category': 'financije',
        })


def _check_inventory_alerts(company, hints):
    from inventory.models import InventoryItem

    total = InventoryItem.objects.filter(company=company).count()
    if total == 0:
        return

    # Items without price
    no_price = InventoryItem.objects.filter(company=company, unit_price=0).count()
    if no_price > 50:
        hints.append({
            'level': 'info',
            'icon': 'bi-tag',
            'title': f'{no_price} artikala bez cijene',
            'message': 'Azurirajte cijene za tocno fakturiranje.',
            'action_url': '/hr/inventory/',
            'action_label': 'Pregledaj',
            'category': 'poslovanje',
        })


def _check_employees(company, hints):
    from worktime.models import EmployeeProfile
    count = EmployeeProfile.objects.filter(company=company).count()
    if count > 0:
        no_iban = EmployeeProfile.objects.filter(company=company, bank_account='').count()
        if no_iban > 0:
            hints.append({
                'level': 'info',
                'icon': 'bi-person-badge',
                'title': f'{no_iban} zaposlenika bez IBAN-a',
                'message': 'Potrebno za SEPA isplatu placa.',
                'action_url': '/hr/worktime/',
                'action_label': 'Dopuni',
                'category': 'zaposlenici',
            })


def _check_bank_reconciliation(company, hints):
    from konto.models import BankTransaction, BankAccount

    accounts = BankAccount.objects.filter(company=company).count()
    if accounts == 0:
        hints.append({
            'level': 'info',
            'icon': 'bi-bank',
            'title': 'Nema bankovnih racuna',
            'message': 'Dodajte ziro racun i uvezite izvod za automatsko pariranje.',
            'action_url': '/konto/bank/',
            'action_label': 'Dodaj racun',
            'category': 'financije',
        })
        return

    unmatched = BankTransaction.objects.filter(company=company, status='unmatched').count()
    if unmatched > 0:
        hints.append({
            'level': 'warning',
            'icon': 'bi-arrow-left-right',
            'title': f'{unmatched} nepariranih transakcija',
            'message': 'Bankovne transakcije cekaju pariranje s racunima.',
            'action_url': '/konto/bank/',
            'action_label': 'Pariraj',
            'category': 'financije',
        })


def _check_fiscal_compliance(company, hints, today):
    # Check if production certificate exists
    from fiskalizacija.models import FiscalConfig
    configs = FiscalConfig.objects.filter(company=company)
    if configs.exists():
        cfg = configs.first()
        if cfg.is_demo:
            hints.append({
                'level': 'critical',
                'icon': 'bi-shield-exclamation',
                'title': 'Demo FINA certifikat!',
                'message': 'Produkcijski certifikat je obavezan. Narucite od FINA.',
                'action_url': '/hr/invoicing/fiscal/certificates/',
                'action_label': 'Certifikati',
                'category': 'compliance',
            })


def _check_module_suggestions(company, hints):
    try:
        config = company.module_config
        if not config.enabled_modules:
            hints.append({
                'level': 'info',
                'icon': 'bi-grid-3x3-gap',
                'title': 'Odaberite module',
                'message': 'Prilagodite sustav vasim potrebama — odaberite module.',
                'action_url': '/hr/companies/modules/',
                'action_label': 'Odaberi module',
                'category': 'sustav',
            })
    except Exception:
        hints.append({
            'level': 'info',
            'icon': 'bi-grid-3x3-gap',
            'title': 'Konfigurirajte module',
            'message': 'Odaberite koje module zelite koristiti.',
            'action_url': '/hr/companies/modules/',
            'action_label': 'Konfiguriraj',
            'category': 'sustav',
        })


def _check_backup_status(hints):
    import os
    log = '/var/log/cloud_backup.log'
    if os.path.exists(log):
        with open(log) as f:
            lines = f.readlines()
        last_line = lines[-1].strip() if lines else ''
        if 'DONE' in last_line:
            hints.append({
                'level': 'success',
                'icon': 'bi-cloud-check',
                'title': 'Cloud backup aktivan',
                'message': f'Zadnji: {last_line[:50]}',
                'category': 'sustav',
            })
    else:
        hints.append({
            'level': 'warning',
            'icon': 'bi-cloud-slash',
            'title': 'Cloud backup nije konfiguriran',
            'message': 'Podaci nisu sigurni izvan servera.',
            'category': 'sustav',
        })
