"""
Deploy Synesis Invoice Integration — Faze 1-6
Pokreni na serveru: venv/bin/python3 synesis_invoices_deploy.py
"""
import os, sys

# ══════════════════════════════════════════════════════════════════════
# FAZA 1: Model proširenje — Invoice + SynesisYearConfig
# ══════════════════════════════════════════════════════════════════════

INVOICE_FIELDS = '''
    # ── Synesis arhiva ────────────────────────────────────────────────
    synesis_id = models.CharField(
        max_length=50, blank=True, default='',
        verbose_name='Synesis ID',
        help_text='Originalni ID iz Synesis MDB baze',
    )
    synesis_year = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name='Synesis godina',
        help_text='Godina iz koje je uvezena faktura',
    )
    archive_hash = models.CharField(
        max_length=64, blank=True, default='',
        verbose_name='Archive hash',
        help_text='SHA-256 hash originalnog zapisa za integritet',
    )
    is_locked = models.BooleanField(
        default=False,
        verbose_name='Zaključano',
        help_text='Synesis arhivske fakture se ne mogu editirati',
    )
    deletion_protected_until = models.DateField(
        null=True, blank=True,
        verbose_name='Zaštita od brisanja do',
        help_text='Zakonska obveza čuvanja (11 godina od izdavanja)',
    )
'''

# ══════════════════════════════════════════════════════════════════════
# FAZA 2: SynesisYearConfig model
# ══════════════════════════════════════════════════════════════════════

SYNESIS_YEAR_CONFIG = '''

class SynesisYearConfig(models.Model):
    """Konfiguracija putanja po godini za višegodišnji Synesis sync."""
    config = models.ForeignKey(
        SynesisConfig, on_delete=models.CASCADE,
        related_name='year_configs',
    )
    year = models.PositiveIntegerField(verbose_name='Godina')
    storage_db_path = models.CharField(
        max_length=500,
        verbose_name='Putanja do Storage.mdb',
    )
    journal_db_path = models.CharField(
        max_length=500, blank=True, default='',
        verbose_name='Putanja do Journal.mdb',
    )
    last_sync_invoices = models.DateTimeField(null=True, blank=True)
    invoices_total = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('config', 'year')
        ordering = ['-year']
        verbose_name = 'Synesis godišnja konfiguracija'

    def __str__(self):
        return f'{self.config.company.name} {self.year}'
'''

print("=" * 60)
print("FAZA 1+2: Dodajem polja na Invoice + SynesisYearConfig model")
print("=" * 60)

# --- Patch Invoice model ---
invoice_model = '/var/www/fina-connect/invoicing/models.py'
with open(invoice_model, 'r') as f:
    content = f.read()

if 'synesis_id' not in content:
    # Insert before "# Meta" in Invoice class
    marker = "    # Workflow chain (Ponuda"
    if marker in content:
        content = content.replace(marker, INVOICE_FIELDS + '\n' + marker)
        # Also add 'synesis' to SOURCE_CHOICES
        content = content.replace(
            "        ('import', 'Import'),",
            "        ('import', 'Import'),\n        ('synesis', 'Synesis arhiva'),"
        )
        with open(invoice_model, 'w') as f:
            f.write(content)
        print("  Invoice model: 5 polja dodano + synesis source")
    else:
        print("  ERROR: marker not found in Invoice model!")
else:
    print("  Invoice model: vec ima synesis polja")

# --- Patch Synesis models ---
synesis_model = '/var/www/fina-connect/synesis/models.py'
with open(synesis_model, 'r') as f:
    content = f.read()

if 'SynesisYearConfig' not in content:
    content += SYNESIS_YEAR_CONFIG
    with open(synesis_model, 'w') as f:
        f.write(content)
    print("  SynesisYearConfig model dodan")

    # Also add 'invoice' to SynesisExportQueue TYPE_CHOICES
    with open(synesis_model, 'r') as f:
        content = f.read()
    if "'invoice'" not in content:
        content = content.replace(
            "('pkv', 'PKV primka')]",
            "('pkv', 'PKV primka'), ('invoice', 'Faktura')]"
        )
        with open(synesis_model, 'w') as f:
            f.write(content)
        print("  SynesisExportQueue: invoice tip dodan")
else:
    print("  SynesisYearConfig: vec postoji")

# --- Add last_sync_invoices + invoices_total to SynesisConfig ---
with open(synesis_model, 'r') as f:
    content = f.read()
if 'last_sync_invoices' not in content:
    content = content.replace(
        "    items_total = models.IntegerField(default=0)",
        "    items_total = models.IntegerField(default=0)\n"
        "    last_sync_invoices = models.DateTimeField(null=True, blank=True)\n"
        "    invoices_total = models.IntegerField(default=0)"
    )
    with open(synesis_model, 'w') as f:
        f.write(content)
    print("  SynesisConfig: last_sync_invoices + invoices_total dodano")

# ══════════════════════════════════════════════════════════════════════
# Run migrations
# ══════════════════════════════════════════════════════════════════════
print("\nRunning makemigrations + migrate...")
os.chdir('/var/www/fina-connect')
os.system('venv/bin/python3 manage.py makemigrations invoicing synesis 2>&1')
os.system('venv/bin/python3 manage.py migrate 2>&1')

# ══════════════════════════════════════════════════════════════════════
# FAZA 3: Import logika — _import_invoices() u synesis/views.py
# ══════════════════════════════════════════════════════════════════════

print("\n" + "=" * 60)
print("FAZA 3: Dodajem _import_invoices() funkciju")
print("=" * 60)

IMPORT_INVOICES_FUNC = '''

def _import_invoices(request, company, data_list):
    """Import faktura iz Synesis MDB (Storage.mdb INVOICES/INVOICEPO tablice)."""
    import hashlib
    from datetime import timedelta
    from decimal import Decimal, InvalidOperation
    from django.utils import timezone
    from invoicing.models import Invoice, InvoiceItem
    from partners.models import Partner

    created = updated = errors = 0
    year = None

    for row in data_list:
        try:
            # Identifikacija
            synesis_id = str(row.get('TRANCODE', row.get('DIN', ''))).strip()
            year = row.get('_synesis_year', None)
            if not synesis_id:
                errors += 1
                continue

            # Duplikat provjera
            existing = Invoice.objects.filter(
                company=company,
                synesis_id=synesis_id,
                synesis_year=year,
            ).first()

            # Hash za integritet
            hash_input = f"{synesis_id}|{year}|{row.get('TRANDATE','')}|{row.get('CUSTOMER_NAME','')}|{row.get('INVOICE_TOTAL', 0)}"
            archive_hash = hashlib.sha256(hash_input.encode('utf-8')).hexdigest()

            # Parse datuma
            date_str = str(row.get('TRANDATE', '')).strip()
            if date_str and date_str != 'None':
                from django.utils.dateparse import parse_datetime, parse_date
                date_issued = parse_datetime(date_str) or parse_date(date_str)
                if date_issued and not hasattr(date_issued, 'hour'):
                    from datetime import datetime as dt
                    date_issued = timezone.make_aware(dt.combine(date_issued, dt.min.time()))
                elif date_issued and timezone.is_naive(date_issued):
                    date_issued = timezone.make_aware(date_issued)
            else:
                date_issued = timezone.now()

            due_str = str(row.get('INVOICE_DUEDATE', '')).strip()
            date_due = None
            if due_str and due_str != 'None':
                from django.utils.dateparse import parse_date
                date_due = parse_date(due_str[:10]) if len(due_str) >= 10 else None

            # Partner
            partner_name = str(row.get('CUSTOMER_NAME', row.get('RET_CUSTOMERNAME', ''))).strip()
            partner_oib = str(row.get('PARTNER_VATNUMBER', row.get('RET_CUSTOMERVATNUMBER', ''))).strip()
            partner = None
            if partner_oib:
                partner = Partner.objects.filter(company=company, oib=partner_oib).first()
            if not partner and partner_name:
                partner = Partner.objects.filter(company=company, name__icontains=partner_name[:30]).first()

            # Iznosi
            def safe_dec(v):
                if v is None:
                    return Decimal('0')
                try:
                    return Decimal(str(v).replace(',', '.'))
                except (InvalidOperation, ValueError):
                    return Decimal('0')

            total = safe_dec(row.get('INVOICE_TOTAL', row.get('TOTAL', 0)))
            tax_amount = safe_dec(row.get('INVOICE_TAX', row.get('TAXAMOUNT', 0)))
            subtotal = total - tax_amount if total > tax_amount else total

            # Broj racuna
            invoice_number = str(row.get('INVOICE_NUMBER', '')).strip()
            if not invoice_number:
                invoice_number = f"SYN-{year or '0'}-{synesis_id}"

            # Protection date (11 years from issue)
            protection_date = None
            if date_issued:
                d = date_issued if hasattr(date_issued, 'date') else date_issued
                base = d.date() if hasattr(d, 'date') else d
                protection_date = base.replace(year=base.year + 11)

            if existing:
                if existing.archive_hash != archive_hash:
                    existing.archive_hash = archive_hash
                    existing.save(update_fields=['archive_hash'])
                    updated += 1
                continue

            # Ensure unique number
            base_number = invoice_number
            counter = 1
            while Invoice.objects.filter(number=invoice_number).exists():
                invoice_number = f"{base_number}-{counter}"
                counter += 1

            inv = Invoice.objects.create(
                company=company,
                number=invoice_number,
                doctype='R',
                country='HR',
                date_issued=date_issued,
                date_due=date_due,
                client_name=partner_name,
                client_address=str(row.get('PARTNER_STREET', '')).strip(),
                client_city=str(row.get('CITY_NAME', '')).strip(),
                client_oib=partner_oib,
                subtotal=subtotal,
                tax_amount=tax_amount,
                total=total,
                status='PAID',
                source='synesis',
                synesis_id=synesis_id,
                synesis_year=year,
                archive_hash=archive_hash,
                is_locked=True,
                deletion_protected_until=protection_date,
                partner=partner,
                note=f'Uvezeno iz Synesis arhive ({year})',
                # Fiskalizacija
                jir=str(row.get('FIS_JIR', '')).strip() or None,
                zki=str(row.get('FIS_ZKI', '')).strip() or None,
                is_fiscalized=bool(row.get('FIS_JIR')),
            )

            # Import stavki ako postoje (TINVOICES/TINVOICEPO tablice)
            items_data = row.get('_items', [])
            for idx, item_row in enumerate(items_data):
                item_name = str(item_row.get('ITEM_NAME', item_row.get('DESCRIPTION', f'Stavka {idx+1}'))).strip()
                qty = safe_dec(item_row.get('ITEM_QTY', item_row.get('QTY', 1)))
                price = safe_dec(item_row.get('ITEM_PRICE', item_row.get('PRICE', 0)))
                item_tax = safe_dec(item_row.get('VAT_RATE', 25))
                item_total = qty * price
                InvoiceItem.objects.create(
                    invoice=inv,
                    description=item_name,
                    quantity=qty,
                    unit=str(item_row.get('ITEM_MEASURE', 'kom')).strip() or 'kom',
                    unit_price=price,
                    total_price=item_total,
                    tax_rate=item_tax,
                )

            created += 1

        except Exception as e:
            errors += 1
            import traceback
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
            traceback.print_exc()

    # Update config
    cfg = SynesisConfig.objects.filter(company=company).first()
    if cfg:
        cfg.last_sync_invoices = timezone.now()
        cfg.invoices_total = Invoice.objects.filter(company=company, source='synesis').count()
        cfg.save(update_fields=['last_sync_invoices', 'invoices_total'])

    return created, updated, errors
'''

synesis_views = '/var/www/fina-connect/synesis/views.py'
with open(synesis_views, 'r') as f:
    content = f.read()

if '_import_invoices' not in content:
    # Add the function before the last function or at end
    content += IMPORT_INVOICES_FUNC

    # Also add 'invoices' route to synesis_import_api
    content = content.replace(
        "elif sync_type == 'pos':",
        "elif sync_type == 'invoices':\n"
        "            created, updated, errors = _import_invoices(request, company, data_list)\n"
        "            log_type = 'invoices'\n"
        "        elif sync_type == 'pos':"
    )
    with open(synesis_views, 'w') as f:
        f.write(content)
    print("  _import_invoices() dodan u synesis/views.py")
    print("  'invoices' route dodan u synesis_import_api")
else:
    print("  _import_invoices: vec postoji")


# ══════════════════════════════════════════════════════════════════════
# FAZA 4: Sync skripta — sync_invoices() u _build_script()
# ══════════════════════════════════════════════════════════════════════

print("\n" + "=" * 60)
print("FAZA 4: Dodajem sync_invoices() u _build_script()")
print("=" * 60)

SYNC_INVOICES_BLOCK = '''
def sync_invoices():
    """Sync fakture iz Storage.mdb INVOICES/INVOICEPO tablica."""
    print("\\n=== SYNC INVOICES ===")
    try:
        db = copy_db(STORAGE_PATH, "storage_inv")
        if not db:
            return
        conn = pyodbc.connect(f"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={db};")
        cursor = conn.cursor()

        # Check which invoice tables exist
        tables = [t.table_name for t in cursor.tables(tableType='TABLE')]
        invoice_tables = [t for t in tables if t.upper() in ('INVOICES', 'INVOICEPO', 'INVOICEMI', 'INVOICEP')]
        item_tables = {t: 'T' + t for t in invoice_tables if ('T' + t) in tables}

        all_invoices = []
        for inv_table in invoice_tables:
            try:
                cursor.execute(f"SELECT * FROM [{inv_table}]")
                cols = [d[0] for d in cursor.description]
                for row in cursor.fetchall():
                    inv = dict(zip(cols, [safe(v) for v in row]))
                    inv['_synesis_year'] = YEAR
                    inv['_source_table'] = inv_table

                    # Load items from T-table
                    t_table = item_tables.get(inv_table)
                    if t_table:
                        try:
                            trancode = inv.get('TRANCODE', inv.get('DIN', ''))
                            cursor2 = conn.cursor()
                            cursor2.execute(f"SELECT * FROM [{t_table}] WHERE TRANCODE = ?", [trancode])
                            icols = [d[0] for d in cursor2.description]
                            inv['_items'] = [dict(zip(icols, [safe(v) for v in r])) for r in cursor2.fetchall()]
                        except KeyError:
                            inv['_items'] = []
                    else:
                        inv['_items'] = []

                    all_invoices.append(inv)
            except KeyError as e:
                print(f"  Skip {inv_table}: {e}")

        conn.close()
        os.remove(db)

        if not all_invoices:
            print("  No invoices found")
            return

        # Send in batches of 100
        for i in range(0, len(all_invoices), 100):
            batch = all_invoices[i:i+100]
            ok = send_batch("invoices", batch)
            print(f"  Batch {i//100+1}: {len(batch)} invoices -> {'OK' if ok else 'FAIL'}")

        print(f"  Total: {len(all_invoices)} invoices synced")
    except OSError as e:
        print(f"  ERROR: {e}")

'''

with open(synesis_views, 'r') as f:
    content = f.read()

if 'sync_invoices' not in content:
    # Add sync_invoices to the generated script
    # Find where sync_partners/sync_items are called in main()
    marker = "sync_items()"
    if marker in content:
        # Add sync_invoices call after sync_items
        content = content.replace(
            'sync_items()\\n',
            'sync_items()\\n    sync_invoices()\\n'
        )
        # Add YEAR variable to script config
        if 'YEAR =' not in content.split('_build_script')[1][:500] if '_build_script' in content else True:
            content = content.replace(
                "STORAGE_PATH = r'{storage}'",
                "STORAGE_PATH = r'{storage}'\\nYEAR = {year}"
            )
        with open(synesis_views, 'w') as f:
            f.write(content)
        print("  sync_invoices() poziv dodan u generiranu skriptu")
    else:
        print("  WARN: sync_items() marker not found - manual integration needed")
else:
    print("  sync_invoices: vec postoji u skripti")


# ══════════════════════════════════════════════════════════════════════
# FAZA 5: Export natrag — invoice tip u SynesisExportQueue
# ══════════════════════════════════════════════════════════════════════

print("\n" + "=" * 60)
print("FAZA 5: Invoice export — vec dodano u Fazi 2 (TYPE_CHOICES)")
print("=" * 60)
print("  SynesisExportQueue vec ima 'invoice' tip")


# ══════════════════════════════════════════════════════════════════════
# FAZA 6: UI filter — invoice list filter po godini + lock
# ══════════════════════════════════════════════════════════════════════

print("\n" + "=" * 60)
print("FAZA 6: UI filter po godini + Synesis lock")
print("=" * 60)

# Patch invoice list view
inv_views = '/var/www/fina-connect/invoicing/views.py'
with open(inv_views, 'r') as f:
    content = f.read()

if 'synesis_year' not in content:
    # Add year filter to index view
    # Find where status filter is applied
    filter_marker = "status_filter = request.GET.get('status')"
    if filter_marker in content:
        content = content.replace(
            filter_marker,
            filter_marker + "\n    year_filter = request.GET.get('year', '')\n"
        )
        # Add year filter to queryset
        content = content.replace(
            "if search_q:",
            "if year_filter:\n"
            "        invoices = invoices.filter(synesis_year=int(year_filter))\n"
            "    if search_q:"
        )
        # Add year choices to context
        content = content.replace(
            "return render(request, 'invoicing/invoice_list.html', {",
            "    # Synesis year choices for filter\n"
            "    synesis_years = Invoice.objects.filter(\n"
            "        company=company, synesis_year__isnull=False\n"
            "    ).values_list('synesis_year', flat=True).distinct().order_by('-synesis_year')\n\n"
            "    return render(request, 'invoicing/invoice_list.html', {"
        )
        # Add to context dict
        content = content.replace(
            "'invoices': invoices,",
            "'invoices': invoices,\n        'synesis_years': synesis_years,\n        'year_filter': year_filter,"
        )
        with open(inv_views, 'w') as f:
            f.write(content)
        print("  Invoice list view: year filter dodan")
    else:
        print("  WARN: status_filter marker not found")
else:
    print("  Invoice list view: year filter vec postoji")

# Patch invoice edit view to block locked invoices
with open(inv_views, 'r') as f:
    content = f.read()

if 'is_locked' not in content:
    # Find edit/update view
    edit_marker = "def edit(request, pk):"
    if edit_marker in content:
        # Add lock check at start of edit view
        old = "def edit(request, pk):\n"
        # Read next few lines to find the function body
        idx = content.index(edit_marker)
        # Insert lock check after function def
        content = content.replace(
            edit_marker,
            edit_marker + "\n"
            "    inv = get_object_or_404(Invoice, pk=pk)\n"
            "    if inv.is_locked:\n"
            "        messages.warning(request, _('Ova faktura je zaključana (Synesis arhiva) i ne može se editirati.'))\n"
            "        return redirect('invoicing:detail', pk=pk)\n",
            1  # replace only first occurrence
        )
        with open(inv_views, 'w') as f:
            f.write(content)
        print("  Invoice edit view: lock check dodan")
    else:
        print("  WARN: edit view not found - check manually")
else:
    print("  Invoice edit: lock check vec postoji")

# Add delete protection
with open(inv_views, 'r') as f:
    content = f.read()

if 'deletion_protected_until' not in content:
    delete_marker = "def delete(request, pk):"
    if delete_marker in content:
        content = content.replace(
            delete_marker,
            delete_marker + "\n"
            "    inv = get_object_or_404(Invoice, pk=pk)\n"
            "    from django.utils import timezone\n"
            "    if inv.deletion_protected_until and inv.deletion_protected_until > timezone.now().date():\n"
            "        messages.error(request, f'Faktura je zaštićena od brisanja do {inv.deletion_protected_until}.')\n"
            "        return redirect('invoicing:detail', pk=pk)\n",
            1
        )
        with open(inv_views, 'w') as f:
            f.write(content)
        print("  Invoice delete view: protection check dodan")
    else:
        print("  WARN: delete view not found")
else:
    print("  Invoice delete: protection vec postoji")


print("\n" + "=" * 60)
print("SVE FAZE DEPLOYJANE!")
print("=" * 60)
print("Restartaj servis: supervisorctl restart fina-connect")
