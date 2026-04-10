# GEMINI_TASK: Partitioned Audit Trail + BookingSignature
# Kreirao: Sonnet — 2026-04-10
# Status: SPREMAN ZA IZVRŠENJE
# Prioritet: Visok — izvršiti nakon 15.04. launch

---

## KONTEKST

Analiziran je `core_systemauditlog`:
- Trenutno: 717 MB, 1.44M zapisa, SAMO 2 mjeseca podataka
- Nema particija (0 rows u pg_inherits)
- Rast: ~7 GB/godina → 77 GB za 11 godina zakonskog roka
- PG verzija: 16.13 — native declarative partitioning DOSTUPNO

Odluka (Sonnet):
- NE migriramo postojeći `core_systemauditlog` (FK constraint, rizik, 717MB)
- GRADIMO NOVI model `BookingSignature` — particioniran od nule
- `core_systemauditlog` ostaje za sistemske evente (middleware)
- `BookingSignature` je zakonski validan trag za računovodstvene akcije

---

## ZADATAK 1: Django model BookingSignature

Kreiraj novi app `audit_chain` (ili dodaj u `core/`) s modelom:

```python
# core/audit_chain.py ili audit_chain/models.py

class BookingSignature(models.Model):
    ACTION_CHOICES = [
        ('invoice_create', 'Kreiranje fakture'),
        ('invoice_update', 'Izmjena fakture'),
        ('storno', 'Storno dokumenta'),
        ('ledger_post', 'Knjiženje u konto'),
        ('ledger_delete', 'Brisanje knjiženja'),
        ('pdv_submit', 'Predaja PDV-S'),
        ('joppd_submit', 'Predaja JOPPD'),
        ('export_csv', 'Export podataka'),
        ('export_pdf', 'Export PDF'),
        ('user_change', 'Promjena korisničkih podataka'),
        ('iban_change', 'Promjena IBAN-a'),
        ('company_settings', 'Promjena postavki tvrtke'),
        ('pin_verify', 'PIN verifikacija'),
        ('bulk_delete', 'Masovno brisanje'),
        ('workspace_switch', 'Promjena workspace-a'),
    ]

    RISK_CHOICES = [
        (0, 'Nema rizika'),
        (1, 'Nizak'),
        (2, 'Srednji'),
        (3, 'Visok — zahtijeva PIN'),
        (4, 'Kritično — zahtijeva PIN + review'),
    ]

    # Identitet akcije
    action_type = models.CharField(max_length=50, choices=ACTION_CHOICES)
    performed_by_id = models.IntegerField(db_index=True)       # User.id (no FK — particija!)
    performed_by_name = models.CharField(max_length=150)        # denormalizirano — ostaje i kad user obriše acc
    on_behalf_of_id = models.UUIDField(db_index=True, null=True, blank=True)  # Company.id
    on_behalf_of_name = models.CharField(max_length=200, blank=True)

    # Timestamp (particija ključ)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    # Forenzika
    client_ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    request_method = models.CharField(max_length=10, blank=True)
    request_path = models.CharField(max_length=500, blank=True)

    # Podaci akcije
    object_type = models.CharField(max_length=100, blank=True)  # 'Invoice', 'JournalEntry'...
    object_id = models.CharField(max_length=100, blank=True)
    data_payload = models.JSONField(default=dict)  # snapshot podataka u momentu akcije

    # AI validacija
    ai_validated = models.BooleanField(default=False)
    ai_risk_score = models.SmallIntegerField(choices=RISK_CHOICES, default=0)
    ai_notes = models.TextField(blank=True)
    pin_verified = models.BooleanField(default=False)

    # Kriptografski lanac (blockchain-lite)
    data_hash = models.CharField(max_length=64, blank=True)      # SHA-256 ovog zapisa
    previous_hash = models.CharField(max_length=64, blank=True)  # hash prethodnog zapisa iste firme
    chain_valid = models.BooleanField(default=True)               # False = netko je dirao bazu!

    class Meta:
        db_table = 'audit_booking_signature'
        # NAPOMENA: particioniranje se dodaje u SQL migraciji ispod
        # Django ne zna za PARTITION BY — mora ručno
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['performed_by_id', 'timestamp']),
            models.Index(fields=['on_behalf_of_id', 'timestamp']),
            models.Index(fields=['action_type', 'timestamp']),
            models.Index(fields=['data_hash']),
        ]

    def __str__(self):
        return f"{self.action_type} | {self.performed_by_name} | {self.timestamp}"
```

---

## ZADATAK 2: Hash funkcija

```python
# core/audit_chain.py

import hashlib
import json
from django.utils import timezone

def compute_booking_hash(record: dict) -> str:
    """
    SHA-256 hash od svih podataka zapisa.
    Ulaz: dict s poljima bookingsignature-a (bez data_hash, chain_valid).
    Izlaz: 64-char hex string.
    """
    payload = {
        'action_type': record.get('action_type', ''),
        'performed_by_id': record.get('performed_by_id', ''),
        'on_behalf_of_id': str(record.get('on_behalf_of_id', '')),
        'timestamp': str(record.get('timestamp', '')),
        'client_ip': record.get('client_ip', ''),
        'object_type': record.get('object_type', ''),
        'object_id': str(record.get('object_id', '')),
        'data_payload': record.get('data_payload', {}),
        'previous_hash': record.get('previous_hash', ''),
    }
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True, default=str)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def get_previous_hash(company_id) -> str:
    """Dohvati hash zadnjeg zapisa za tu firmu — za lanac."""
    from .models import BookingSignature
    last = BookingSignature.objects.filter(
        on_behalf_of_id=company_id
    ).order_by('-timestamp').values('data_hash').first()
    return last['data_hash'] if last else '0' * 64


def create_booking_signature(
    action_type: str,
    user,
    company=None,
    request=None,
    object_type: str = '',
    object_id: str = '',
    data_payload: dict = None,
    ai_risk_score: int = 0,
    ai_notes: str = '',
    pin_verified: bool = False,
) -> 'BookingSignature':
    """
    Jedina ulazna točka za kreiranje BookingSignature zapisa.
    SYNC — ne async. Ovo je zakonski trag.
    """
    from .models import BookingSignature

    company_id = str(company.id) if company else None
    company_name = company.name if company else ''
    prev_hash = get_previous_hash(company_id) if company_id else '0' * 64

    record_data = {
        'action_type': action_type,
        'performed_by_id': user.id,
        'performed_by_name': user.get_full_name() or user.username,
        'on_behalf_of_id': company_id,
        'on_behalf_of_name': company_name,
        'timestamp': timezone.now(),
        'client_ip': _get_ip(request),
        'user_agent': request.META.get('HTTP_USER_AGENT', '')[:300] if request else '',
        'request_method': request.method if request else '',
        'request_path': request.path if request else '',
        'object_type': object_type,
        'object_id': str(object_id),
        'data_payload': data_payload or {},
        'ai_risk_score': ai_risk_score,
        'ai_notes': ai_notes,
        'pin_verified': pin_verified,
        'previous_hash': prev_hash,
    }

    data_hash = compute_booking_hash(record_data)
    record_data['data_hash'] = data_hash

    return BookingSignature.objects.create(**record_data)


def _get_ip(request) -> str:
    if not request:
        return ''
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    return xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR', '')
```

---

## ZADATAK 3: PostgreSQL PARTITION migracija

PAŽNJA: Ovo nije standardna Django migracija. Piši kao `RunSQL` u migracijskom fajlu.

```sql
-- Korak 1: Kreiraj particioniranu tablicu od nule
-- (Django će kreirati nepaticioniranu tablicu — mi je odmah dropamo i rekreiramo)

CREATE TABLE IF NOT EXISTS audit_booking_signature (
    id BIGSERIAL,
    action_type VARCHAR(50) NOT NULL,
    performed_by_id INTEGER NOT NULL,
    performed_by_name VARCHAR(150) NOT NULL,
    on_behalf_of_id UUID,
    on_behalf_of_name VARCHAR(200) DEFAULT '',
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    client_ip INET,
    user_agent VARCHAR(300) DEFAULT '',
    request_method VARCHAR(10) DEFAULT '',
    request_path VARCHAR(500) DEFAULT '',
    object_type VARCHAR(100) DEFAULT '',
    object_id VARCHAR(100) DEFAULT '',
    data_payload JSONB DEFAULT '{}',
    ai_validated BOOLEAN DEFAULT FALSE,
    ai_risk_score SMALLINT DEFAULT 0,
    ai_notes TEXT DEFAULT '',
    pin_verified BOOLEAN DEFAULT FALSE,
    data_hash VARCHAR(64) DEFAULT '',
    previous_hash VARCHAR(64) DEFAULT '',
    chain_valid BOOLEAN DEFAULT TRUE,
    PRIMARY KEY (id, timestamp)
) PARTITION BY RANGE (timestamp);

-- Korak 2: Particije po godinama (2026-2036)
CREATE TABLE audit_booking_signature_2026 
    PARTITION OF audit_booking_signature
    FOR VALUES FROM ('2026-01-01') TO ('2027-01-01');

CREATE TABLE audit_booking_signature_2027
    PARTITION OF audit_booking_signature
    FOR VALUES FROM ('2027-01-01') TO ('2028-01-01');

CREATE TABLE audit_booking_signature_2028
    PARTITION OF audit_booking_signature
    FOR VALUES FROM ('2028-01-01') TO ('2029-01-01');

CREATE TABLE audit_booking_signature_2029
    PARTITION OF audit_booking_signature
    FOR VALUES FROM ('2029-01-01') TO ('2030-01-01');

CREATE TABLE audit_booking_signature_2030
    PARTITION OF audit_booking_signature
    FOR VALUES FROM ('2030-01-01') TO ('2031-01-01');

CREATE TABLE audit_booking_signature_2031_2036
    PARTITION OF audit_booking_signature
    FOR VALUES FROM ('2031-01-01') TO ('2037-01-01');

-- Korak 3: Indeksi na svakoj particiji (PG16 podržava)
CREATE INDEX ON audit_booking_signature_2026 (performed_by_id, timestamp);
CREATE INDEX ON audit_booking_signature_2026 (on_behalf_of_id, timestamp);
CREATE INDEX ON audit_booking_signature_2026 (action_type, timestamp);
CREATE INDEX ON audit_booking_signature_2026 (data_hash);

-- ponovi za svaku particiju
```

---

## ZADATAK 4: Chain integrity check (Celery task)

```python
# core/tasks/audit_integrity.py

@shared_task(name='core.tasks.audit_integrity.verify_chain')
def verify_chain_for_company(company_id: str, date: str = None):
    """
    Provjeri integritet hash lanca za jednu firmu za jedan dan.
    Pokreće se noćno (Gemini ga triggera).
    """
    from core.audit_chain import compute_booking_hash
    from core.models import BookingSignature

    qs = BookingSignature.objects.filter(
        on_behalf_of_id=company_id
    ).order_by('timestamp')

    if date:
        qs = qs.filter(timestamp__date=date)

    broken = []
    prev_hash = '0' * 64

    for sig in qs.iterator():
        # Rekonstruiraj hash
        record_data = {
            'action_type': sig.action_type,
            'performed_by_id': sig.performed_by_id,
            'on_behalf_of_id': sig.on_behalf_of_id,
            'timestamp': sig.timestamp,
            'client_ip': str(sig.client_ip or ''),
            'object_type': sig.object_type,
            'object_id': sig.object_id,
            'data_payload': sig.data_payload,
            'previous_hash': prev_hash,
        }
        expected = compute_booking_hash(record_data)

        if sig.data_hash != expected:
            broken.append({
                'id': sig.id,
                'timestamp': str(sig.timestamp),
                'action_type': sig.action_type,
                'stored_hash': sig.data_hash,
                'expected_hash': expected,
            })
            sig.chain_valid = False
            sig.save(update_fields=['chain_valid'])

        prev_hash = sig.data_hash

    return {
        'company_id': company_id,
        'checked': qs.count(),
        'broken': len(broken),
        'broken_records': broken,
        'status': 'CHAIN_BROKEN' if broken else 'CHAIN_OK',
    }
```

---

## ZADATAK 5: Decorator za akcije koje zahtijevaju PIN

```python
# accounts/decorators.py

from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages

PIN_REQUIRED_ACTIONS = {
    'storno', 'bulk_delete', 'ledger_delete',
    'export_csv', 'iban_change', 'user_change',
    'company_settings', 'pdv_submit', 'joppd_submit',
}

def require_pin_for_action(action_type: str):
    """
    Dekorator za viewove koji zahtijevaju PIN potvrdu.
    Koristi session flag koji postavlja trikey_views.verify_pin_for_action.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if action_type not in PIN_REQUIRED_ACTIONS:
                return view_func(request, *args, **kwargs)

            session_key = f'pin_verified_{action_type}'
            if not request.session.get(session_key):
                request.session['pin_required_action'] = action_type
                request.session['pin_return_url'] = request.get_full_path()
                return redirect('accounts:pin_verify_action')

            # Jednom iskorišten — obrišemo flag
            del request.session[session_key]
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
```

---

## ZADATAK 6: Session timeout middleware

```python
# core/middleware.py (dodati u postojeći fajl)

class InactivityTimeoutMiddleware:
    """
    8h ukupni session + 45min inaktivnosti.
    Ako nema aktivnosti 45min → logout.
    """
    INACTIVITY_SECONDS = 45 * 60   # 45 minuta
    MAX_SESSION_SECONDS = 8 * 3600  # 8 sati

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            now = time.time()
            last_activity = request.session.get('_last_activity', now)
            session_start = request.session.get('_session_start', now)

            # Provjera inaktivnosti
            if now - last_activity > self.INACTIVITY_SECONDS:
                from django.contrib.auth import logout
                logout(request)
                messages.info(request, 'Sesija je istekla zbog neaktivnosti.')
                return redirect('/login/?reason=inactivity')

            # Provjera max trajanja
            if now - session_start > self.MAX_SESSION_SECONDS:
                from django.contrib.auth import logout
                logout(request)
                messages.info(request, 'Radni dan je završen. Prijavite se ponovo.')
                return redirect('/login/?reason=session_expired')

            request.session['_last_activity'] = now
            if '_session_start' not in request.session:
                request.session['_session_start'] = now

        return self.get_response(request)
```

---

## REDOSLJED IZVRŠENJA

1. Kreiraj Django model `BookingSignature` (Zadatak 1)
2. Kreiraj `audit_chain.py` s hash funkcijama (Zadatak 2)
3. Napiši migraciju s `RunSQL` za particioniranje (Zadatak 3)
4. Testiraj: INSERT → provjeri u kojoj particiji je zapis
5. Kreiraj Celery task za integrity check (Zadatak 4)
6. Registriraj u CELERY_BEAT: verify_chain → svake noći 03:00
7. Implementiraj `require_pin_for_action` decorator (Zadatak 5)
8. Primijeni na: storno view, export view, bulk_delete view
9. Dodaj `InactivityTimeoutMiddleware` u settings.py MIDDLEWARE (Zadatak 6)
10. Testiraj 45min timeout

## ZABRANJENA ZONA (ne diraj!)
- core_systemauditlog — ne migrirati, ne dropati
- base.html — ne modificirati
- core/settings.py — samo dodati middleware, ne brisati ništa
- Backup: napravi dump prije SQL particija!

## VERIFIKACIJA (Sonnet review)
Nakon izvršenja, provjeri:
- `SELECT tableoid::regclass, count(*) FROM audit_booking_signature GROUP BY 1;`
- Mora pokazati zapise u `audit_booking_signature_2026`
- Verify chain task: mora vrati `CHAIN_OK` za testni zapis
