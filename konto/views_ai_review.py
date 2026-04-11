"""
konto/views_ai_review.py
Human review UI for AI bookkeeper proposals.
"""
import json
import logging
from decimal import Decimal, InvalidOperation

from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.translation import gettext as _
from django.db import transaction
from django.utils import timezone

from documents.models import ArhivaEntry

logger = logging.getLogger(__name__)


def _get_company(request):
    """Get active company for current user."""
    company = getattr(request, 'impersonated_company', None)
    if not company:
        try:
            company = request.user.profile.company
        except Exception:
            pass
    return company


@login_required
def ai_review_queue(request):
    """Show ArhivaEntries with AI proposals that are not booked yet."""
    company = _get_company(request)
    if not company:
        messages.warning(request, _('Niste povezani s tvrtkom. Odaberite tvrtku iz izbornika.'))
        return redirect('dashboard')

    entries = (
        ArhivaEntry.objects
        .filter(company=company, is_booked=False)
        .exclude(ai_proposal__isnull=True)
        .order_by('-archived_at')
    )

    # Count by confidence level
    high = 0
    medium = 0
    low = 0
    for e in entries:
        conf = (e.ai_proposal or {}).get('confidence', 0)
        # Normalize: could be 0-1 or 0-100
        if isinstance(conf, (int, float)):
            if conf <= 1:
                conf = conf * 100
        if conf >= 90:
            high += 1
        elif conf >= 70:
            medium += 1
        else:
            low += 1

    # Normalize confidence for template display
    entries_list = list(entries)
    for e in entries_list:
        if e.ai_proposal and 'confidence' in e.ai_proposal:
            c = e.ai_proposal['confidence']
            if isinstance(c, (int, float)) and c <= 1:
                e.ai_proposal['confidence'] = c * 100

    return render(request, 'konto/ai_review_queue.html', {
        'entries': entries_list,
        'high_confidence_count': high,
        'medium_confidence_count': medium,
        'low_confidence_count': low,
    })


@login_required
def ai_confirm_booking(request, pk):
    """POST endpoint to confirm/modify and book an AI proposal."""
    if request.method != 'POST':
        return redirect('konto:ai_review_queue')

    company = _get_company(request)
    entry = get_object_or_404(ArhivaEntry, pk=pk, company=company)

    if entry.is_booked:
        messages.warning(request, f'{entry.doc_number} je vec proknjizeno.')
        return redirect('konto:ai_review_queue')

    action = request.POST.get('action', 'confirm')

    if action == 'reject':
        # Clear AI proposal, mark as reviewed but not booked
        entry.ai_proposal = None
        entry.save(update_fields=['ai_proposal'])
        messages.info(request, f'Prijedlog za {entry.doc_number} odbacen.')
        return redirect('konto:ai_review_queue')

    # Get proposal lines (either original or edited)
    if action == 'edit_confirm':
        debit_lines, credit_lines = _parse_edited_lines(request.POST)
    else:
        proposal = entry.ai_proposal or {}
        debit_lines = proposal.get('debit', [])
        credit_lines = proposal.get('credit', [])

    if not debit_lines and not credit_lines:
        messages.error(request, 'Nema stavki za knjizenje.')
        return redirect('konto:ai_review_queue')

    # Validate balance
    total_debit = sum(Decimal(str(l.get('amount', 0))) for l in debit_lines)
    total_credit = sum(Decimal(str(l.get('amount', 0))) for l in credit_lines)

    if total_debit != total_credit:
        messages.error(
            request,
            f'Temeljnica nije uravnotezena: duguje={total_debit}, potrazuje={total_credit}'
        )
        return redirect('konto:ai_review_queue')

    # Create journal entry
    try:
        je = _create_journal_entry(company, entry, debit_lines, credit_lines, request.user)
        entry.is_booked = True
        entry.save(update_fields=['is_booked'])
        messages.success(
            request,
            f'Proknjizeno: {je.entry_number} za {entry.doc_number} ({total_debit} EUR)'
        )
    except Exception as exc:
        logger.error("AI confirm booking failed for %s: %s", entry.pk, exc, exc_info=True)
        messages.error(request, _('Knjiženje nije uspjelo. Provjerite konto i iznos.'))

    return redirect('konto:ai_review_queue')


def _parse_edited_lines(post_data):
    """Parse edited lines from form POST data."""
    debit_lines = []
    credit_lines = []
    idx = 0
    while True:
        side_key = f'side_{idx}'
        account_key = f'account_{idx}'
        amount_key = f'amount_{idx}'
        desc_key = f'desc_{idx}'

        if side_key not in post_data:
            break

        side = post_data.get(side_key, '')
        account = post_data.get(account_key, '').strip()
        amount_str = post_data.get(amount_key, '0').strip()
        desc = post_data.get(desc_key, '').strip()

        try:
            amount = float(amount_str)
        except (ValueError, TypeError):
            amount = 0

        if account and amount > 0:
            line = {'account': account, 'amount': amount, 'description': desc}
            if side == 'debit':
                debit_lines.append(line)
            else:
                credit_lines.append(line)

        idx += 1

    return debit_lines, credit_lines


@transaction.atomic
def _create_journal_entry(company, archive_entry, debit_lines, credit_lines, user):
    """Create a JournalEntry with LedgerLines from proposal lines."""
    from konto.models import KontoAccount, JournalEntry, LedgerLine
    from konto.services_file import _next_entry_number

    je = JournalEntry.objects.create(
        company=company,
        entry_number=_next_entry_number(company, 'AI'),
        date=archive_entry.doc_date or timezone.now().date(),
        description=f"AI knjizenje: {archive_entry.doc_number} - {archive_entry.partner_name}",
        source_type='manual',
        is_posted=True,
        created_by=user,
    )

    for line in debit_lines:
        account = KontoAccount.objects.get(company=company, code=line['account'])
        LedgerLine.objects.create(
            journal_entry=je,
            account=account,
            side='debit',
            amount=Decimal(str(line['amount'])),
            description=line.get('description', ''),
        )

    for line in credit_lines:
        account = KontoAccount.objects.get(company=company, code=line['account'])
        LedgerLine.objects.create(
            journal_entry=je,
            account=account,
            side='credit',
            amount=Decimal(str(line['amount'])),
            description=line.get('description', ''),
        )

    return je
