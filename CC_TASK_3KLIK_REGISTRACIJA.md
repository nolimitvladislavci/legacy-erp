# CC_TASK_3KLIK_REGISTRACIJA — Onboarding bez trenja
# Datum: 02.04.2026 — postmortem Viktor Grgurić
# Prioritet: 🔴 BLOKIRA produkciju i svaki novi korisnik
# Odgovorni: CC Code

---

## POSTMORTEM — što je Viktor doživio (8 commitova fixa u 3 sata)

| # | Problem | Uzrok | Fiksano |
|---|---------|-------|---------|
| 1 | User bez Company/UserProfile | Session istekao između register_step3 i step4 | ✅ transaction.atomic() |
| 2 | Force2FA redirect loop | totp_enabled=False, nema bypass | ✅ ručno bypass |
| 3 | ForceTCMiddleware blokada | has_signed_tc_consent=False | ✅ ručno bypass |
| 4 | OIB 12 znakova (limit 11) | DRAFT bio predugačak | ✅ skraćen |
| 5 | Rate limit 429 | 20 pokušaja/min, previše | ✅ 50/min |
| 6 | 502 — NameError Partner | Partner nije importan u umbrella view | ✅ lazy import |
| 7 | Nema blagajnika | _seed_demo_data nije kreirao cashier | ✅ auto-cashier |
| 8 | Kamera ne radi | capture="environment" ne radi desktop | ✅ getUserMedia |
| 9 | Nema puta do POS-a | Umbrella dashboard nema POS link | ✅ zeleni gumb |

**Zaključak:** 9 problema, 0 trebalo biti. Sve je tehničko, sve je predvidivo.

---

## ZADATAK R1 — register_step4 mora biti atomičan i kompletan

Trenutno stanje nakon fixa: `transaction.atomic()` postoji, ali neke stvari
se rade VAN transakcije (seed, subscription, RBAC).

### Ispravan redoslijed unutar jednog `transaction.atomic()`:

```python
with transaction.atomic():
    # 1. User
    user = User.objects.create_user(...)
    
    # 2. Company (OIB max 11 znakova)
    oib = company_data["oib"][:11] if len(company_data.get("oib","")) > 11 else company_data.get("oib","")
    company = Company.objects.create(
        name=company_data["name"],
        oib=oib or f"DRAFT{uuid.uuid4().hex[:6].upper()}",  # uvijek 11 znakova
        ...
        has_signed_tc_consent=True,        # auto-consent pri registraciji
        tc_consent_version='v1.0-2026',
        tc_consent_signed_at=now(),
    )
    
    # 3. UserProfile
    profile = UserProfile.objects.create(
        user=user, company=company,
        role='company_admin',
        totp_enabled=True,   # bypass 2FA dok ne postave pravi TOTP
    )
    
    # 4. Subscription
    CompanySubscription.objects.create(company=company, ...)
    
    # 5. RBAC
    UserRole.objects.get_or_create(user=user, role=admin_role, company=company)

# 6. VAN transakcije (smije failati):
_seed_demo_data(company, user)   # demo data + cashier + konto
```

### Provjeri u registration/views.py — register_step4:
- `transaction.atomic()` wrapper već postoji (commit c710934b)
- Provjeri da je OIB truncation unutar atomic bloka
- Provjeri da `has_signed_tc_consent=True` i `totp_enabled=True` su u atomic bloku

---

## ZADATAK R2 — _seed_demo_data mora kreirati SVE za day-1

Dodati u `registration/views.py` funkciju `_seed_demo_data`:

```python
def _seed_demo_data(company, user):
    # 1. Demo partneri (POSTOJI)
    # 2. Demo artikli (POSTOJI)  
    # 3. TaxRate (POSTOJI)
    
    # 4. POSCashier (FIKSANO commit 588e7c51 — PROVJERI JE LI UŠLO)
    from pos.models import POSCashier
    cashier, _ = POSCashier.objects.get_or_create(
        company=company, user=user,
        defaults={'name': user.get_full_name() or user.username,
                  'can_void': True, 'can_discount': True,
                  'max_discount_percent': 100, 'is_active': True}
    )
    cashier.set_pin('1234')
    cashier.save(update_fields=['pin_hash'])
    
    # 5. POSTerminal — ako nema, kreiraj default
    from pos.models import POSTerminal, POSSettings
    terminal, _ = POSTerminal.objects.get_or_create(
        company=company,
        defaults={
            'name': 'Blagajna 1',
            'terminal_code': 'T001',
            'pos_type': 'quick',
            'is_active': True,
        }
    )
    
    # 6. POSSettings
    POSSettings.objects.get_or_create(company=company)
    
    # 7. KontoChart (seed konto plan)
    try:
        from django.core.management import call_command
        call_command('seed_konto_chart', company_id=str(company.pk), verbosity=0)
    except Exception:
        pass
    
    # 8. OnboardingProgress
    from companies.models import OnboardingProgress
    onb, _ = OnboardingProgress.objects.get_or_create(company=company)
    onb.first_partner_added = True
    onb.first_item_added = True
    onb.save(update_fields=['first_partner_added', 'first_item_added', 'updated_at'])
```

---

## ZADATAK R3 — dashboard_router auto-recovery

Trenutno stanje (commit c710934b): auto-recovery postoji ako nema Company.
Provjeri da:

```python
# dashboard_router u core/views.py
profile, _created = UserProfile.objects.get_or_create(
    user=request.user, defaults={'role': 'company_admin'}
)

if not profile.company:
    # ... kreira Company + Subscription
    profile.totp_enabled = True   # bypass
    # has_signed_tc_consent=True na company
    # ... _seed_demo_data(company, user)  ← MORA BITI POZVAN I OVDJE
```

Dodati `_seed_demo_data` i u auto-recovery path, ne samo u register_step4.

---

## ZADATAK R4 — Distributor onboarding skripta

Kad se distributor registrira (umbrella_relation='distributer'), automatski:

```python
def _setup_distributor(company, user):
    """Sve što distributor treba da može odmah raditi."""
    
    # 1. Subscription — distributor plan, monthly_fee=0
    from registration.models import CompanySubscription, PricingPlan
    plan = PricingPlan.objects.filter(slug='distributor').first()
    CompanySubscription.objects.update_or_create(
        company=company,
        defaults={
            'plan': 'distributor',
            'pricing_plan': plan,
            'monthly_fee': 0,  # provizijski model
            'is_active': True,
            'valid_until': now().date() + timedelta(days=365),
        }
    )
    
    # 2. Umbrella setup
    konjik = Company.objects.filter(oib='37590751921').first()
    if konjik:
        company.umbrella_parent = konjik
        company.umbrella_relation = 'distributer'
        company.is_umbrella = True
        company.umbrella_max_children = 50
        company.save(update_fields=[
            'umbrella_parent','umbrella_relation',
            'is_umbrella','umbrella_max_children'
        ])
    
    # 3. _seed_demo_data (blagajnik, terminal, demo data)
    _seed_demo_data(company, user)
```

Trigger: ako `reg_plan == 'distributor'` ili invite code ima `umbrella_relation='distributer'`.

---

## ZADATAK R5 — Umbrella dashboard ima POS gumb

Već fiksano (commit 22533492). Provjeri da:
- Zeleni "Otvori POS" gumb vodi na `{% url 'pos:dashboard' %}`
- "Postavke" gumb vodi na `{% url 'companies:settings' %}`
- Na mobilnom su oba vidljiva (flex-wrap)

---

## PROVJERA (pokreni za svakog novog korisnika):

```bash
cd /var/www/fina-connect
venv/bin/python manage.py shell << 'EOF'
from django.contrib.auth.models import User
u = User.objects.get(username='NEW_USERNAME')
from accounts.models import UserProfile
p = UserProfile.objects.get(user=u)
company = p.company
print(f"UserProfile: {p.role}")
print(f"Company: {company.name}")
print(f"OIB len: {len(company.oib)} ({'OK' if len(company.oib) <= 11 else 'PROBLEM'})")
print(f"TC consent: {company.has_signed_tc_consent}")
print(f"2FA bypass: {p.totp_enabled}")
from registration.models import CompanySubscription
sub = CompanySubscription.objects.filter(company=company, is_active=True).first()
print(f"Subscription: {sub.plan if sub else 'NEMA'}")
from pos.models import POSCashier, POSTerminal
cashier = POSCashier.objects.filter(company=company).first()
terminal = POSTerminal.objects.filter(company=company).first()
print(f"Cashier: {'OK PIN=' + ('1234' if cashier else 'NEMA')}")
print(f"Terminal: {terminal.name if terminal else 'NEMA'}")
EOF
```

Svaki redak mora biti OK. Ako nije — problem je u R1-R4.

---

## GIT:
```bash
git add registration/views.py core/views.py
git commit -m "fix(onboarding): kompletna registracija u jednoj transakciji — R1-R5"
```
