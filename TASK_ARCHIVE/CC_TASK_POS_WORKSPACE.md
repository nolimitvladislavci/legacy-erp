# CC_TASK: POS ↔ Workspace integracija — Tjedan 2
# Naručio: Ivan Brtan
# Kreirao: Sonnet — 2026-04-10
# Ovisi o: CC_TASK_BOOKING_SIGNATURE.md (mora biti deployed)
# Procjena: 3-4 sata

---

## STANJE U BAZI (Sonnet verificirao)

```
POSTerminal:   31 terminala — ima company + branch FK, NEMA workspace FK
POSSession:   177 sessiona — nema workspace reference
Workspace:      5 workspaceova — SVE tip 'desk', sve Konjik d.o.o.
                NEMA niti jednog 'premise' tipa workspace-a
CompanyBranch: terminali uglavnom mapiraju na branch (Optika Oko itd.)
```

VAŽNO: Šekijevi terminali (FRIŠKO, 5 kasa) nemaju branch. Konjik terminali imaju branch.
Mapping strategy: terminal.branch → workspace (ako postoji isti grad/naziv), inače NULL.

---

## KORAK 0: Čitaj prije pisanja

```bash
# Provjeri stvarno stanje FK-ova
grep -n "workspace\|branch" /var/www/fina-connect/pos/models.py | head -20

# Provjeri zadnju migraciju
ls -lt /var/www/fina-connect/pos/migrations/ | head -3

# Provjeri BookingSignature je deployed
venv/bin/python manage.py showmigrations booking_audit
```

Ako `booking_audit` nije deployed → STANI. Tjedan 1 mora biti gotov prvi.

---

## KORAK 1: Dodaj workspace FK na POSTerminal

U `pos/models.py`, u klasu `POSTerminal`, dodaj NAKON `branch` FK:

```python
workspace = models.ForeignKey(
    'companies.Workspace',
    on_delete=models.SET_NULL,
    null=True, blank=True,
    related_name='pos_terminals',
    verbose_name='Workspace (poslovni prostor)',
    help_text='PREMISE tip workspace-a. Prazno = terminal nije mapiran na workspace.',
)
```

---

## KORAK 2: Migracija

```bash
cd /var/www/fina-connect
venv/bin/python manage.py makemigrations pos --name="add_workspace_to_terminal"
venv/bin/python manage.py migrate pos
```

---

## KORAK 3: Auto-mapping script (jednokratno)

Pokreni u Django shellu — mapira postojeće terminale na workspace gdje je moguće:

```python
# venv/bin/python manage.py shell
from pos.models import POSTerminal
from companies.models import Workspace

mapped = 0
for terminal in POSTerminal.objects.filter(workspace__isnull=True):
    # Pokušaj mapirati po branchu → workspace iste firme
    if terminal.branch:
        # Traži workspace s istim ili sličnim imenom kao branch
        ws = Workspace.objects.filter(
            company=terminal.company,
            type='premise',
        ).first()
        if not ws:
            # Nema premise workspace — provjeri desk (za računovođe)
            ws = Workspace.objects.filter(
                company=terminal.company,
            ).first()
        if ws:
            terminal.workspace = ws
            terminal.save(update_fields=['workspace'])
            mapped += 1
            print(f"  Mapped: {terminal.name} ({terminal.company}) → {ws.name}")

print(f"\nUkupno mapiranih: {mapped} / {POSTerminal.objects.count()}")
print(f"Bez workspace-a: {POSTerminal.objects.filter(workspace__isnull=True).count()}")
```

---

## KORAK 4: Hook BookingSignature na POS session open/close

Pronađi POS session open i close viewove:

```bash
grep -n "def.*open\|def.*close\|session.*open\|session.*close\|Status.OPEN\|Status.CLOSED" \
  /var/www/fina-connect/pos/views.py | head -20
```

### 4a. Session OPEN — dodaj log_action NAKON session.save():

```python
from booking_audit.utils import log_action

# Nakon što je session kreiran/otvoren:
log_action(
    action='pos_open',
    user=request.user,
    request=request,
    company=session.terminal.company,
    workspace=session.terminal.workspace,  # može biti None
    target_model='pos.POSSession',
    target_id=session.pk,
    after={
        'terminal': session.terminal.name,
        'terminal_code': session.terminal.terminal_code,
        'session_number': session.session_number,
        'opening_cash': str(session.opening_cash),
        'opened_at': session.opened_at.isoformat(),
    },
)
```

### 4b. Session CLOSE (Z-report) — dodaj log_action PRIJE redirect-a:

```python
from booking_audit.utils import log_action

# Nakon što je session zatvoren, PRIJE redirect-a:
log_action(
    action='pos_close',
    user=request.user,
    request=request,
    company=session.terminal.company,
    workspace=session.terminal.workspace,
    target_model='pos.POSSession',
    target_id=session.pk,
    changes={
        'before': {'status': 'open'},
        'after': {
            'status': 'closed',
            'total_sales': str(session.total_sales),
            'closing_cash': str(session.closing_cash),
            'cash_difference': str(session.cash_difference),
            'z_report_number': session.z_report_number,
            'closed_at': session.closed_at.isoformat() if session.closed_at else None,
        },
    },
)
```

### 4c. POS VOID (storno bona) — pronađi storno view i dodaj:

```python
log_action(
    action='pos_void',
    user=request.user,
    request=request,
    company=receipt.session.terminal.company,
    workspace=receipt.session.terminal.workspace,
    target_model='pos.POSReceipt',
    target_id=receipt.pk,
    changes={
        'before': {'status': receipt.status, 'total': str(receipt.total)},
        'after': {'status': 'cancelled'},
    },
    pin_verified=False,  # Tjedan 3: ovdje će ići PIN check
)
```

---

## KORAK 5: Verifikacija

```bash
# Test: otvori i zatvori smjenu u browseru, zatim provjeri
venv/bin/python manage.py shell -c "
from booking_audit.models import BookingSignature
pos_logs = BookingSignature.objects.filter(
    action__in=['pos_open', 'pos_close', 'pos_void']
).order_by('-timestamp')[:5]
for s in pos_logs:
    print(f'{s.timestamp:%H:%M} | {s.action} | {s.get_company()} | hash_ok={s.verify_integrity()}')
"
```

---

## KORAK 6: Git commit

```bash
git add pos/models.py pos/migrations/ pos/views.py
git add booking_audit/
git commit -m "feat: POS ↔ Workspace integracija + BookingSignature hooks

- POSTerminal.workspace FK (nullable, SET_NULL)
- Auto-mapping script: branch → workspace
- BookingSignature: pos_open, pos_close, pos_void akcije
- Z-report snapshot u changes JSON (cash, total, z_number)
- Workspace context na svakom POS zapisu"
```

---

## NIJE U OVOM TASKU (Tjedan 3)

- PIN za POS void/storno (require_pin_for_action dekorator)
- Session inactivity timeout middleware (45min)
- Premise workspace auto-kreacija za svaki terminal bez workspace-a
- Inventura ↔ Workspace mapping

## ZABRANJENA ZONA
- Ne modificirati base.html
- Ne modificirati core/settings.py osim ako je nužno
- Ne diraj core_systemauditlog
