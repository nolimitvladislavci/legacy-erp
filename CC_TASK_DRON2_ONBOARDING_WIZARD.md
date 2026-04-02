# CC_TASK: DRON #2 — Lijevak Smrti (Onboarding Kirurgija)
# Datum: 02.04.2026 | Prioritet: 🔴 BLOKIRA go-live
# Odgovorni: CC Code
# Kontekst: register_step2_combined zahtijeva 12 polja upfront — korisnik gori

---

## PRIJETNJA

Trenutni flow: Plan → [12 polja odjednom: naziv, OIB, adresa, grad, zip, industrija,
ime, prezime, email, telefon, lozinka×2] → Potvrda → Dashboard

9 mjesta gdje korisnik dobije grešku i odustane. Svaki error bez crystal-clear
poruke = krivnja pada na sustav, ne na korisnika → nikad se ne vraća.

---

## NOVA ARHITEKTURA (3 koraka, ne 4)

### KORAK 1 (samo 3 polja) — register_step1
Trenutno: Plan selection (ostaje)
Dodati: Ime, Email, Lozinka
To je TO. Korisnik je u sustavu. Dobiva Dashboard s onboarding statusom.

### KORAK 2 (async, unutar platforme) — Setup Wizard
Korisnik je prijavljan. Vidi Dashboard s narančastim banerom:
"Vaš profil je 30% popunjen — završite postavljanje u 5 minuta →"

Wizard sekcije (svaka zasebna HTMX stranica, svaka može failati bez da ruši drugu):
- Sekcija A: Podaci tvrtke (naziv, OIB, adresa) — AJAX OIB lookup
- Sekcija B: Kontakt (telefon, web, email za fakture)
- Sekcija C: IBAN + Fiskalizacija certifikat (upload .p12)
- Sekcija D: Izgled fakture (logo upload, boja, font)
- Sekcija E: Pozovi tim (email kolega → invite link)

Svaka sekcija ima: zelenu kvačicu kad je done, "Preskoči za sada" link.

### KORAK 3 — Verifikacija emaila
Šalje se link, ali NE blokira pristup. Korisnik radi normalno.
Email verifikacija je soft-reminder (banner), ne hard-block.

---

## IMPLEMENTACIJA

### A) Promijeni register_step1 view — dodaj 3 polja

```python
# registration/views.py — register_step1 (POST dio)
if request.method == "POST":
    plan_slug = request.POST.get("plan", "starter")
    first_name = request.POST.get("first_name", "").strip()
    email = request.POST.get("email", "").strip()
    password = request.POST.get("password1", "")
    password2 = request.POST.get("password2", "")

    errors = {}
    if not first_name: errors["first_name"] = "Unesite ime."
    if not email: errors["email"] = "Email je obavezan."
    elif User.objects.filter(email=email).exists():
        errors["email"] = "Ovaj email već postoji. <a href='/accounts/login/'>Prijavite se →</a>"
    if len(password) < 8: errors["password1"] = "Lozinka mora imati min. 8 znakova."
    if password != password2: errors["password2"] = "Lozinke se ne podudaraju."

    if not errors:
        import uuid
        username = email.split("@")[0].replace(".", "_")[:20] + uuid.uuid4().hex[:4]
        with transaction.atomic():
            user = User.objects.create_user(
                username=username, email=email, password=password,
                first_name=first_name
            )
            # Placeholder company — ime = email prefix, OIB = DRAFT + random
            draft_oib = f"DRAFT{uuid.uuid4().hex[:6].upper()}"[:11]
            company = Company.objects.create(
                name=f"Firma korisnika {first_name}",
                oib=draft_oib,
                country="HR",
                is_draft=True,  # Flag — zna da je nepotpuna
                has_signed_tc_consent=True,
                tc_consent_version='v1.0-2026',
                tc_consent_signed_at=timezone.now(),
            )
            profile = UserProfile.objects.create(
                user=user, company=company, role='company_admin',
                totp_enabled=True,  # Bypass 2FA dok ne postave TOTP
            )
            # Subscription — plan iz sessiona
            _create_subscription(company, plan_slug)

        # Seed async — ne blokira
        try: _seed_demo_data(company, user)
        except: pass

        login(request, user)
        return redirect("companies:setup_wizard")  # → Wizard step A
```

### B) Novi URL i view — Setup Wizard

```python
# companies/urls.py — dodaj:
path('setup/', views.setup_wizard, name='setup_wizard'),
path('setup/company/', views.setup_wizard_company, name='setup_wizard_company'),
path('setup/contact/', views.setup_wizard_contact, name='setup_wizard_contact'),
path('setup/fiscal/', views.setup_wizard_fiscal, name='setup_wizard_fiscal'),
```

```python
# companies/views.py — setup_wizard
@login_required
def setup_wizard(request):
    company = request.user.profile.company
    sections = {
        'company': bool(company.name and not company.is_draft),
        'fiscal': bool(company.oib and len(company.oib) == 11 and not company.oib.startswith('DRAFT')),
        'contact': bool(company.phone or company.email),
        'logo': bool(company.logo),
        'team': company.users.count() > 1,
    }
    completion = int(sum(sections.values()) / len(sections) * 100)
    return render(request, 'companies/setup_wizard.html', {
        'sections': sections, 'completion': completion, 'company': company
    })
```

### C) Dashboard banner (base.html ili dashboard template)

```html
{% if request.user.profile.company.is_draft %}
<div class="f-setup-banner" id="setupBanner">
  <div class="f-setup-progress">
    <div class="f-setup-bar" style="width: {{ completion }}%"></div>
  </div>
  <span class="f-gold">Postavljanje profila {{ completion }}%</span>
  <a href="{% url 'companies:setup_wizard' %}" class="f-btn-gold">Nastavi postavljanje →</a>
  <button onclick="document.getElementById('setupBanner').style.display='none'">×</button>
</div>
{% endif %}
```

### D) OIB AJAX lookup (already exists — provjeri)
```bash
grep -rn "oib.*ajax\|ajax.*oib\|/api/oib\|oib_lookup" registration/ companies/ --include="*.py" --include="*.html" | head -10
```
Ako postoji → reuse. Ako ne → CC_TASK_OIB_AJAX.md.

### E) Svaki error mora biti vidljiv

Svako polje u step1 i wizardu mora imati:
- `aria-describedby="field-error-id"`
- `<span id="field-error-id" class="f-error-msg" role="alert">{{ errors.field }}</span>`
- Gumb disabled dok forma procesira: `<button hx-indicator="#spinner" ...>`
- Nakon greške: scroll do prvog errora automatski (`document.querySelector('.f-error-msg').scrollIntoView()`)

---

## PROVJERA

```bash
# Simuliraj čisti onboarding:
cd /var/www/fina-connect
venv/bin/python manage.py shell -c "
from django.test import Client
c = Client()
# Step 1 — samo 3 polja:
r = c.post('/hr/register/', {'plan': 'starter', 'first_name': 'Test', 'email': 'test99@example.com', 'password1': 'TestPass123!', 'password2': 'TestPass123!'})
print('Step1:', r.status_code, r.get('Location',''))
"
```

Očekivano: 302 redirect na /companies/setup/ ili dashboard.
Svaki 200 na step1 POST = problem (forma se vraća s errorima).

---

## DELIVERABLE

1. register_step1 → 3 polja → Company placeholder → login → redirect wizard
2. Setup Wizard base view + 5 sekcija (A-E)
3. Dashboard banner s completion %
4. Svaki error ima role="alert" i vidljivu poruku

Rok: **10.04.2026** (5 dana prije go-live)

