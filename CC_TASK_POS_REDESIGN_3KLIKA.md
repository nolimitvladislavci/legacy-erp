# CC TASK: POS Redesign — 3 klika do prvog bona

## KONTEKST
POS aktivacija je prekomplicirana. Korisnik se izgubi u koracima, artikl spremi daje 404, porezne grupe nisu vidljive, blagajnik nema OIB (zakonski obavezan). Treba kompletna reorganizacija.

## SERVER
```
ssh root@37.27.248.86
cd /var/www/fina-connect
. venv/bin/activate
```

## REDOSLIJED IZVRŠENJA (striktno ovim redom)

---

### TASK 1: Auto-seed TaxRate pri registraciji
**Fajl:** `registration/views.py` → `_seed_demo_data()`
**Fajl:** `companies/models.py` → TaxRate model (VEĆ POSTOJI)

Provjeri: `python manage.py shell -c "from companies.models import TaxRate; print([f.name for f in TaxRate._meta.get_fields()])"`

U `_seed_demo_data()` (registration/views.py, oko linije 62), NAKON kreiranja partnera, dodaj:
```python
# Auto-seed porezne stope po zemlji
from companies.models import TaxRate
country = company_data.get('country', 'HR') if isinstance(company_data, dict) else getattr(company, 'country', 'HR')
if not TaxRate.objects.filter(company=company).exists():
    if country in ('DE', 'AT'):
        for name, rate in [('Standard 19%', 19), ('Ermäßigt 7%', 7), ('Steuerfrei', 0)]:
            TaxRate.objects.create(company=company, name=name, rate=rate)
    elif country == 'SI':
        for name, rate in [('DDV 22%', 22), ('DDV 9.5%', 9.5), ('Oproščeno', 0)]:
            TaxRate.objects.create(company=company, name=name, rate=rate)
    else:  # HR default
        for name, rate in [('PDV 25%', 25), ('PDV 13%', 13), ('PDV 5%', 5), ('Oslobođeno 0%', 0)]:
            TaxRate.objects.create(company=company, name=name, rate=rate)
```

**PROVJERA:** Registriraj test korisnika, provjeri da TaxRate postoji.

---

### TASK 2: TaxRate management stranica
**Novi fajl:** `templates/companies/tax_rates.html`
**Fajl:** `companies/views.py` — dodaj `tax_rate_list` view
**Fajl:** `companies/urls.py` — dodaj URL

View:
```python
@login_required
def tax_rate_list(request):
    company = get_user_company(request)
    from companies.models import TaxRate
    
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add':
            name = request.POST.get('name', '').strip()
            rate = request.POST.get('rate', '25')
            if name:
                TaxRate.objects.create(company=company, name=name, rate=rate)
                messages.success(request, f'Stopa "{name}" dodana.')
        elif action == 'delete':
            tid = request.POST.get('tax_id')
            TaxRate.objects.filter(pk=tid, company=company).delete()
            messages.success(request, 'Stopa obrisana.')
        elif action == 'edit':
            tid = request.POST.get('tax_id')
            t = TaxRate.objects.filter(pk=tid, company=company).first()
            if t:
                t.name = request.POST.get('name', t.name)
                t.rate = request.POST.get('rate', t.rate)
                t.save()
                messages.success(request, 'Stopa ažurirana.')
        return redirect('companies:tax_rates')
    
    rates = TaxRate.objects.filter(company=company).order_by('-rate')
    return render(request, 'companies/tax_rates.html', {'rates': rates})
```

Template: fenix dark tema, lista stopa, inline edit, gumb "Dodaj novu".
URL: `path('tax-rates/', views.tax_rate_list, name='tax_rates')`

**PROVJERA:** Otvori /companies/tax-rates/, dodaj/uredi/obriši stopu.

---

### TASK 3: POSCashier.oib migracija
**Fajl:** `pos/models.py` → POSCashier klasa (oko linije 490)
**Nova migracija**

Dodaj polje u POSCashier:
```python
oib = models.CharField(max_length=20, blank=True, default='', 
    verbose_name=_('OIB operatera'),
    help_text=_('Zakonski obavezno za fiskalizaciju (čl. 9. Zakona o fiskalizaciji)'))
```

Kreiraj migraciju: `python manage.py makemigrations pos -n "cashier_oib"`
Apliciraj: `python manage.py migrate pos`

**PROVJERA:** `python manage.py shell -c "from pos.models import POSCashier; print('oib' in [f.name for f in POSCashier._meta.get_fields()])"`

---

### TASK 4: Novi 3-step POS activation wizard
**Zamijeni:** `templates/pos/new_terminal.html` (KOMPLETNO)
**Zamijeni:** `pos/views.py` → `new_terminal()` view

**FLOW:**

**Step 1: Porezne kategorije**
- Prikaži TaxRate.objects.filter(company=company)
- Ako prazno → auto-seed (pozovi istu logiku kao task 1)
- Lista s checkboxom "koristi u POS-u"
- Gumb "Dodaj novu stopu" (inline form)
- "Dalje →" kad postoji barem 1 stopa

**Step 2: Blagajnik**
- Polja: Ime, Prezime, OIB operatera (11 znamenki za HR)
- PIN (4 znamenke) — opcionalno ali preporučeno
- Početna gotovina u blagajni (€) — opcionalno, default 0
- "Dalje →" kad je ime popunjeno

**Step 3: Vrsta blagajne**
- Radio lista (6 tipova, native HTML <label><input type="radio">)
- Klik na tip → submit form → kreira:
  1. POSCashier (ime, prezime, oib, pin)
  2. POSTerminal (tip, company)
  3. POSSession (cashier, opening_cash)
  4. Redirect na POS sučelje (/pos/quick/{terminal_id}/ ili /pos/restaurant/{terminal_id}/)

**POST handler pseudocode:**
```python
if request.method == 'POST':
    # Step data
    cashier_name = request.POST.get('cashier_first') + ' ' + request.POST.get('cashier_last')
    cashier_oib = request.POST.get('cashier_oib', '')
    cashier_pin = request.POST.get('cashier_pin', '')
    opening_cash = Decimal(request.POST.get('opening_cash', '0') or '0')
    pos_type = request.POST.get('pos_type', 'quick')
    
    # Create cashier
    cashier = POSCashier.objects.create(
        company=company, name=cashier_name, oib=cashier_oib,
    )
    if cashier_pin:
        cashier.set_pin(cashier_pin)
        cashier.save()
    
    # Create terminal
    terminal = POSTerminal.objects.create(
        company=company, 
        name=f'{cashier_name} — {pos_type}',
        terminal_code=f'{pos_type[:3].upper()}{secrets.token_hex(2).upper()}',
        pos_type=pos_type,
    )
    
    # Open session
    session = POSSession.objects.create(
        terminal=terminal, operator=request.user,
        session_number=1, opening_cash=opening_cash,
        status='open',
    )
    session.active_cashiers.add(cashier)
    
    # Redirect to POS
    if pos_type == 'restaurant':
        return redirect('pos:restaurant_pos', terminal_id=terminal.pk)
    else:
        return redirect('pos:quick_pos', terminal_id=terminal.pk)
```

**VAŽNO:** Template mora koristiti native HTML radio buttons i form POST — NE JavaScript onclick. Mora raditi na svakom mobitelu.

---

### TASK 5: Fix artikl unos 404
**Dijagnoza:** Pronađi koji URL/view daje 404 pri spremanju artikla.

```bash
grep -n "article_quick_create\|inventory_item_save\|api/quick-create" pos/urls.py pos/views.py
```

Najvjerojatniji problem: URL mismatch ili missing view. Fix routing.

**PROVJERA:** U POS-u dodaj artikl → klikni Spremi → zelena poruka "Artikl spremljen".

---

### TASK 6: Integriraj OIB operatera u fiskalizaciju
**Fajl:** `fiskalizacija/fisk.py` → `_build_racun()` funkcija (oko linije 220)

Trenutno: `sub(racun, 'OibOper', oib)` — koristi company OIB.
Treba: ako receipt ima cashier s OIB-om, koristi taj OIB.

```python
# U _build_racun(), zamijeni:
sub(racun, 'OibOper', oib)

# Sa:
oper_oib = oib  # default: company OIB
if hasattr(receipt, 'cashier') and receipt.cashier and receipt.cashier.oib:
    oper_oib = receipt.cashier.oib
sub(racun, 'OibOper', oper_oib)
```

**PROVJERA:** Kreiraj bon s blagajnikom koji ima OIB → fiskaliziraj → provjeri XML sadrži cashier OIB.

---

## NAKON SVIH TASKOVA
```bash
python manage.py check
systemctl restart gunicorn-fina celery-worker celery-beat
# Test: registriraj novog korisnika, prođi cijeli POS flow
```

## COMMIT PORUKA
```
POS Redesign: 3 klika do prvog bona

1. Auto-seed TaxRate po zemlji pri registraciji (HR/DE/AT/SI)
2. TaxRate management stranica (/companies/tax-rates/)
3. POSCashier.oib polje (zakonski obavezno, čl. 9 Zakona o fiskalizaciji)
4. Novi 3-step wizard: Porezne stope → Blagajnik+OIB → Odaberi tip = OTVORI POS
5. Fix artikl unos 404
6. Fiskalizacija: OIB operatera iz cashier profila, ne company OIB
```

## NAPOMENA
- SVE koristi fenix dark temu (--black:#0a0a0a, --gold:#c9a84c)
- SVE koristi native HTML forme, NE JavaScript onclick
- Template fontovi: Cormorant Garamond (headings) + Barlow (body)
- Testirati na mobitelu OBAVEZNO
