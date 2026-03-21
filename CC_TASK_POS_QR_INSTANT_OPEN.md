# CC_TASK_POS_QR_INSTANT_OPEN
# Izvršava: CC Code
# Koordinira: Sonnet
# Prioritet: VISOK — ovo rješava Šekijev problem
# Datum: 2026-03-21
#
# KONTEKST (obavezno pročitati):
# Šeki (Uvijek Friško) ima 5 POS terminala. Koristi samo Čepin (3 sesije).
# Vladislavci, Ivanovac, Čepin 2, Terensko vozilo — nula sesija.
# Razlog: otvaranje blagajne zahtijeva login + navigaciju + manual open_session.
# Šekijevi sinovi ne znaju login, ne stignu, ne žele učiti.
# Rješenje: QR kod na zidu → skeniraj mobitelom → blagajna otvorena, sprema za naplatu.
# Zero login. Zero konfiguracija. Zero trening.

---

## ŠTO GRADIŠ

### 1. POSTerminal.access_token polje

Dodaj u pos/models.py → klasa POSTerminal:
```python
access_token = models.CharField(
    max_length=32, unique=True, blank=True,
    verbose_name='QR pristupni token',
    help_text='Auto-generiran. QR kod na zidu pekare — sin skenira, blagajna se otvori.'
)
```

U save() metodi — auto-generiraj ako prazno:
```python
if not self.access_token:
    import secrets
    self.access_token = secrets.token_urlsafe(20)
```

OBAVEZNO: pročitaj pos/models.py klasu POSTerminal PRIJE nego dodaš polje.
Provjeri postoji li već nešto slično (ima `terminal_code`, `qr_code` na Table modelu).

### 2. Nova view — pos_qr_open (BEZ LOGIN REQUIREDA)

```python
# pos/views.py
def pos_qr_open(request, token):
    """
    QR pristup blagajni — bez logina.
    Koristi se za Šekijeve sinove: skeniraju QR, blagajna se otvori.
    
    Sigurnost:
    - Token je 20-char urlsafe random — nije guessable
    - Terminal mora biti is_active=True
    - Otvara sesiju kao 'qr_operator' (poseban User ili system)
    - Sve akcije logira u AIActionLog s IP adresom
    """
    terminal = get_object_or_404(POSTerminal, access_token=token, is_active=True)
    company = terminal.company
    
    # Pronađi otvorenu sesiju ili kreiraj novu
    session = POSSession.objects.filter(terminal=terminal, status='open').first()
    if not session:
        # Nađi ili kreiraj QR operator usera za ovu kompaniju
        from django.contrib.auth.models import User
        qr_user, _ = User.objects.get_or_create(
            username=f'qr_operator_{company.pk}',
            defaults={
                'first_name': 'QR', 'last_name': 'Operator',
                'is_active': True, 'is_staff': False,
            }
        )
        last = terminal.sessions.order_by('-session_number').first()
        next_num = (last.session_number + 1) if last else 1
        session = POSSession.objects.create(
            terminal=terminal,
            operator=qr_user,
            session_number=next_num,
            opening_cash=Decimal('0'),
            status='open',
        )
    
    # Logirati pristup
    ip = request.META.get('HTTP_X_REAL_IP', request.META.get('REMOTE_ADDR', ''))
    from superadmin_ai.models import AIActionLog
    AIActionLog.objects.create(
        company=company, module='pos', action_type='qr_open',
        access_level=1, outcome='executed',
        ip_address=ip,
        details={'terminal': terminal.name, 'token': token[:8] + '...', 'session_id': str(session.pk)}
    )
    
    # Redirect na quick_pos view (već postoji, već radi)
    # Ali moramo logirati usera za session — koristimo session auth trick
    request.session['qr_terminal_id'] = terminal.pk
    request.session['qr_session_id'] = session.pk
    request.session['qr_company_id'] = str(company.pk)
    
    return redirect('pos:qr_session', session_id=session.pk)
```

### 3. Nova view — qr_session (POS sučelje bez @login_required)

Provjeri kako quick_pos radi (pos/views.py, linija ~711).
Napravi qr_session view koji:
- Čita session iz URL parametra
- Validira da session.terminal.access_token odgovara nečemu u request.session
- Prikazuje isti template kao quick_pos ali bez @login_required
- Ima sve iste funkcionalnosti: dodaj artikl, naplati, fiskaliziraj

PAZI: Fiskalizacija mora raditi. Provjeri kako quick_pos poziva CheckoutService
i repliciraj istu logiku. Ne pišemo novu fiskalizaciju — koristimo postojeću.

OBAVEZNO: Pročitaj pos/views.py :: quick_pos (linija ~711) CIJELU funkciju
i pos/views.py :: process_payment CIJELU funkciju prije pisanja.

### 4. URL

```python
# pos/urls.py — dodaj:
path('qr/<str:token>/', views.pos_qr_open, name='pos_qr_open'),
path('qr/session/<int:session_id>/', views.qr_session, name='qr_session'),
```

### 5. QR generiranje — management command

```bash
# python manage.py generate_pos_qr --company "UVIJEK FRIŠKO"
```

Output:
```
Terminal: Blagajna PM Čepin
URL: https://limit-connect.com/pos/qr/abc123xyz456/
QR kod: [ASCII art ili link za print]

Terminal: Blagajna PM Vladislavci  
URL: https://limit-connect.com/pos/qr/def456uvw789/
QR kod: [link za print]
```

Spremi QR slike u media/pos_qr/{company_id}/{terminal_id}.png
Koristi qrcode library (pip install qrcode[pil] --break-system-packages ako nije)

### 6. Print-ready PDF za svaki terminal

Jedna A6 stranica:
- Naziv pekare + naziv terminala
- Veliki QR kod (8x8 cm)
- Tekst: "Skeniraj za otvaranje blagajne"
- Podnožje: limit-connect.com

Spremi kao media/pos_qr/{company_id}/{terminal_id}_print.pdf
Koristiti reportlab ili weasyprint (provjeri što je dostupno).

### 7. Migracija

```bash
python manage.py makemigrations pos --name "add_access_token"
python manage.py migrate
```

### 8. Auto-generiraj tokene za sve postojeće terminale

```python
# U migraciji ili management komandi:
for terminal in POSTerminal.objects.filter(access_token=''):
    terminal.save()  # save() će auto-generirati token
```

---

## SIGURNOST — OBAVEZNO

- access_token je 20-char urlsafe random = ~133 bita entropije = nije bruteforceable
- Terminal mora biti is_active=True — inaktivni terminali ne rade
- Svaki pristup logira se u AIActionLog s IP adresom i timestamp-om
- QR sesija nema pristup admin panelu, settings-u, niti drugim modulima
- Samo pos/ URL-ovi rade kroz QR token
- Rate limit: max 10 QR open pokušaja / IP / sat (koristiti Django cache)

---

## TESTIRANJE

```bash
# 1. Generiraj token za Šekijev terminal
python manage.py generate_pos_qr --company "UVIJEK FRIŠKO"

# 2. Provjeri URL radi
curl -I https://limit-connect.com/pos/qr/{token}/

# 3. Provjeri da sesija nastaje
python manage.py shell -c "
from pos.models import POSSession, POSTerminal
t = POSTerminal.objects.get(pk=4)  # Blagajna PM Čepin
print('Sesija:', POSSession.objects.filter(terminal=t).order_by('-opened_at').first())
"
```

---

## GOTOVO KAD

- [ ] POSTerminal.access_token polje postoji i auto-generira se
- [ ] /pos/qr/{token}/ otvara blagajnu bez logina
- [ ] Fiskalizacija radi kroz QR sesiju (test s terminalom u test modu)
- [ ] QR PDF generiran za sve Šekijeve terminale (5 komada)
- [ ] AIActionLog bilježi svaki QR pristup
- [ ] Migracija aplicirana
- [ ] git commit: "POS QR instant open — zero-login terminal activation"
- [ ] Upiši DONE u FENIX_STATUS.md

---

## FINALNI OUTPUT ZA IVANA

Nakon taska, Ivan treba dobiti 5 PDF fajlova:
- media/pos_qr/FRIŠKO/cepin_print.pdf
- media/pos_qr/FRIŠKO/ivanovac_print.pdf  
- media/pos_qr/FRIŠKO/vladislavci_print.pdf
- media/pos_qr/FRIŠKO/cepin2_print.pdf
- media/pos_qr/FRIŠKO/terensko_print.pdf

Ivan ih printovati, zalijepiti na zid, gotovo.
Šekijev sin skenira jutros — blagajna otvorena za 3 sekunde.
