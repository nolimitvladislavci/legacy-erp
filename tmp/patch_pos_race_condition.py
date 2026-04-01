"""
POS Race Condition Fix — 4 mjesta
1. views.py: new_receipt — select_for_update na session
2. views.py: open_session — select_for_update na terminal
3. models.py: POSReceipt.save() — global_number atomic
4. services/checkout.py: _next_receipt_number — select_for_update

Pokreni: python /tmp/patch_pos_race_condition.py
"""
import os

BASE = '/var/www/fina-connect'

# ══════════════════════════════════════════════════════════════
# PATCH 1: views.py — new_receipt + open_session
# ══════════════════════════════════════════════════════════════
views_path = os.path.join(BASE, 'pos/views.py')
with open(views_path, 'r') as f:
    views_code = f.read()

# --- PATCH 1a: new_receipt ---
old_new_receipt = """@login_required
@require_POST
def new_receipt(request, session_id):
    session = get_object_or_404(POSSession, pk=session_id)
    if session.status != POSSession.Status.OPEN:
        messages.error(request, 'Session is closed.')
        return redirect('pos:session_detail', session_id=session_id)
    last = session.receipts.order_by('-receipt_number').first()
    next_num = (last.receipt_number + 1) if last else 1
    receipt = POSReceipt.objects.create(
        session=session, receipt_number=next_num,
        table_number=request.POST.get('table_number', ''),
        note=request.POST.get('note', ''),
    )
    return redirect('pos:receipt_detail', receipt_id=receipt.pk)"""

new_new_receipt = """@login_required
@require_POST
@transaction.atomic
def new_receipt(request, session_id):
    # select_for_update: serializes receipt creation per session (race condition fix)
    session = get_object_or_404(POSSession.objects.select_for_update(), pk=session_id)
    if session.status != POSSession.Status.OPEN:
        messages.error(request, 'Session is closed.')
        return redirect('pos:session_detail', session_id=session_id)
    from django.db.models import Max
    max_num = session.receipts.aggregate(m=Max('receipt_number'))['m'] or 0
    next_num = max_num + 1
    receipt = POSReceipt.objects.create(
        session=session, receipt_number=next_num,
        table_number=request.POST.get('table_number', ''),
        note=request.POST.get('note', ''),
    )
    return redirect('pos:receipt_detail', receipt_id=receipt.pk)"""

if old_new_receipt in views_code:
    views_code = views_code.replace(old_new_receipt, new_new_receipt)
    print("PATCH 1a: new_receipt — OK")
else:
    print("PATCH 1a: new_receipt — ALREADY PATCHED or code changed")

# --- PATCH 1b: open_session ---
old_open_session = """@login_required
@require_POST
def open_session(request, terminal_id):
    terminal = get_object_or_404(POSTerminal, pk=terminal_id)
    company, err = _check_tenant(request, terminal)
    if err: return err
    if terminal.sessions.filter(status=POSSession.Status.OPEN).exists():
        messages.warning(request, 'Terminal already has an open session.')
        return redirect('pos:terminal_detail', terminal_id=terminal_id)
    last = terminal.sessions.order_by('-session_number').first()
    next_num = (last.session_number + 1) if last else 1
    opening_cash = Decimal(request.POST.get('opening_cash', '0') or '0')
    session = POSSession.objects.create(
        terminal=terminal, operator=request.user,
        session_number=next_num, opening_cash=opening_cash,
        status=POSSession.Status.OPEN,
    )"""

new_open_session = """@login_required
@require_POST
@transaction.atomic
def open_session(request, terminal_id):
    # select_for_update: serializes session creation per terminal (race condition fix)
    terminal = get_object_or_404(POSTerminal.objects.select_for_update(), pk=terminal_id)
    company, err = _check_tenant(request, terminal)
    if err: return err
    if terminal.sessions.filter(status=POSSession.Status.OPEN).exists():
        messages.warning(request, 'Terminal already has an open session.')
        return redirect('pos:terminal_detail', terminal_id=terminal_id)
    from django.db.models import Max
    max_num = terminal.sessions.aggregate(m=Max('session_number'))['m'] or 0
    next_num = max_num + 1
    opening_cash = Decimal(request.POST.get('opening_cash', '0') or '0')
    session = POSSession.objects.create(
        terminal=terminal, operator=request.user,
        session_number=next_num, opening_cash=opening_cash,
        status=POSSession.Status.OPEN,
    )"""

if old_open_session in views_code:
    views_code = views_code.replace(old_open_session, new_open_session)
    print("PATCH 1b: open_session — OK")
else:
    print("PATCH 1b: open_session — ALREADY PATCHED or code changed")

with open(views_path, 'w') as f:
    f.write(views_code)


# ══════════════════════════════════════════════════════════════
# PATCH 2: models.py — POSReceipt.save() global_number atomic
# ══════════════════════════════════════════════════════════════
models_path = os.path.join(BASE, 'pos/models.py')
with open(models_path, 'r') as f:
    models_code = f.read()

old_save = """    def save(self, *args, **kwargs):
        if not self.global_number:
            from django.db.models import Max
            company = self.session.terminal.company
            last = POSReceipt.objects.filter(
                session__terminal__company=company
            ).aggregate(m=Max('global_number'))['m'] or 0
            self.global_number = last + 1
        super().save(*args, **kwargs)"""

new_save = """    def save(self, *args, **kwargs):
        if not self.global_number:
            from django.db.models import Max
            from django.db import transaction as _tx
            company = self.session.terminal.company
            # Atomic global_number: lock company row to serialize (race condition fix)
            with _tx.atomic():
                from companies.models import Company
                Company.objects.select_for_update().filter(pk=company.pk).first()
                last = POSReceipt.objects.filter(
                    session__terminal__company=company
                ).aggregate(m=Max('global_number'))['m'] or 0
                self.global_number = last + 1
        super().save(*args, **kwargs)"""

if old_save in models_code:
    models_code = models_code.replace(old_save, new_save)
    print("PATCH 2: POSReceipt.save() global_number — OK")
else:
    print("PATCH 2: POSReceipt.save() global_number — ALREADY PATCHED or code changed")

with open(models_path, 'w') as f:
    f.write(models_code)


# ══════════════════════════════════════════════════════════════
# PATCH 3: services/checkout.py — _next_receipt_number atomic
# ══════════════════════════════════════════════════════════════
checkout_path = os.path.join(BASE, 'pos/services/checkout.py')
with open(checkout_path, 'r') as f:
    checkout_code = f.read()

old_next = """    @staticmethod
    def _next_receipt_number(session):
        from django.db.models import Max
        max_num = session.receipts.aggregate(m=Max('receipt_number'))['m'] or 0
        return max_num + 1"""

new_next = """    @staticmethod
    def _next_receipt_number(session):
        # select_for_update on session: serializes receipt_number per session (race condition fix)
        from django.db.models import Max
        from pos.models import POSSession
        POSSession.objects.select_for_update().filter(pk=session.pk).first()
        max_num = session.receipts.aggregate(m=Max('receipt_number'))['m'] or 0
        return max_num + 1"""

if old_next in checkout_code:
    checkout_code = checkout_code.replace(old_next, new_next)
    print("PATCH 3: checkout._next_receipt_number — OK")
else:
    print("PATCH 3: checkout._next_receipt_number — ALREADY PATCHED or code changed")

with open(checkout_path, 'w') as f:
    f.write(checkout_code)


print("\n=== SVA 4 RACE CONDITION PATCHA PRIMJENJENA ===")
print("Sljedeci korak: test + restart")
