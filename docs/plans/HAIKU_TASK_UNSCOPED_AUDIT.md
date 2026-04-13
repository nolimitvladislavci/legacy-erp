# HAIKU_TASK_UNSCOPED_AUDIT.md
# Agent: Haiku (via Celery / brzi pattern matching) | Prioritet: VISOK
# Datum: 2026-03-25 | Koordinator: Sonnet

---

## MISIJA
Pronaći SVA mjesta u kodu gdje se `.unscoped()` poziva IZVAN sigurnih konteksta
(admin, seed, migration, management commands).

Ukupno identificiranih: ~89 poziva. Trebamo znati koji su opasni.

---

## PRAVILO KLASIFIKACIJE

### ✅ SIGURAN unscoped() — NE PRIJAVLJUJ
- `management/commands/*.py` — CLI alati
- `admin.py` — Django admin
- `*seed*.py`, `*migration*.py`, `*import*.py` — seeding i migracije
- `conftest.py`, `test_*.py`, `tests*.py` — testovi
- `Celery @shared_task` funkcije koje imaju `company=` argument — prihvatljivo
- `superadmin_ai/` — superadmin modul

### 🔴 RIZIČAN unscoped() — PRIJAVI
- `views.py` fajlovi — korisnik može vidjet podatke drugih tvrtki
- `serializers.py` — API leak
- `services.py`, `services/` — ako se poziva iz view konteksta
- `tasks.py` bez `company` argumenta — može procesirati tuđe podatke
- `signals.py` bez company filtera

---

## FAJLOVI ZA PROVJERU (prioritet)

Provjeri redom (od najkritičnijeg):
1. `invoicing/views.py`
2. `invoicing/services/invoice_service.py`
3. `pos/views.py`
4. `pos/views_v2.py`
5. `konto/views.py`
6. `partners/views.py`
7. `companies/views.py`
8. `core/views.py`
9. `core/cockpit_views.py`
10. `core/intelligence_views.py`
11. `worktime/views.py`
12. `inventory/views.py` (ako postoji)
13. `documents/views.py` (ako postoji)
14. `synesis/views.py` (ako postoji)
15. `accounts/views.py`

Sekundarno (samo ako imaš token):
16-30. Ostali `views.py` i `services.py` fajlovi

---

## FORMAT ODGOVORA

```
=== KRITIČNI NALAZI ===

FAJL: invoicing/views.py
LINIJA: 234
KONTEKST: def invoice_list(request): ...
KOD: invoices = Invoice.objects.unscoped().filter(status='PAID')
RAZLOG: Filtrira po statusu ali NE po company — cross-tenant leak
RIZIK: 🔴 HIGH

---

FAJL: pos/views.py
LINIJA: 89
KONTEKST: Celery task bez company arg
KOD: receipts = POSReceipt.objects.unscoped().all()
RAZLOG: Task procesira receipte svih tvrtki
RIZIK: 🟡 MEDIUM (Celery, ne direktni user request)

---

=== STATISTIKE ===
Pregledano fajlova: N
Ukupno unscoped() poziva: N
Kritični (🔴 HIGH): N
Srednji (🟡 MEDIUM): N
Sigurni (✅ OK): N
```

---

## OUTPUT
Napiši nalaze u: `HAIKU_UNSCOPED_AUDIT_REPORT.md`
Sortirati od najkritičnijeg prema manje kritičnom.
Ako nađeš 0 kritičnih — napiši to eksplicitno (dobra vijest).
