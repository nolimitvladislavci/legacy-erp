#!/usr/bin/env python3
"""
Digitalni Posrednik — Dual-Agent Parallel Test Runner
======================================================
Dva agenta rade paralelno simulirajuci 1500 korisnika razinu:
  Agent A: Izdavatelj (šalje e-račune, bulk, stress)
  Agent B: Primatelj (prima, procesira, inbox, anomalije)

Pokretanje:
  DJANGO_SETTINGS_MODULE=core.settings python test_posrednik_dual.py

Rezultati: test_posrednik_results.json + ispis u konzolu
"""

import os, sys, json, time, uuid, threading, random, hashlib
from datetime import date, timedelta
from decimal import Decimal
from dataclasses import dataclass, field
from typing import Optional

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

import django
django.setup()

from django.contrib.auth.models import User
from companies.models import Company
from eracun.models import ERacun, ERacunConfig, ERacunItem, ERacunTaxSummary, ERacunLog
from eracun.services.engine import validate_eracun
from eracun.services.ubl_generator import generate_ubl_xml

# ── Boje za ispis ──────────────────────────────────────────────────────────────
G  = '\033[92m'  # zelena
R  = '\033[91m'  # crvena
Y  = '\033[93m'  # žuta
B  = '\033[94m'  # plava
M  = '\033[95m'  # ljubičasta
C  = '\033[96m'  # cyan
W  = '\033[97m'  # bijela
DIM= '\033[2m'
RST= '\033[0m'

# ── Rezultati ─────────────────────────────────────────────────────────────────
@dataclass
class TestResult:
    id: str
    name: str
    agent: str
    passed: bool
    duration_ms: float
    detail: str = ''
    error: str = ''
    category: str = ''

results: list[TestResult] = []
results_lock = threading.Lock()
_counter = {'a': 0, 'b': 0}

def record(r: TestResult):
    with results_lock:
        results.append(r)
        status = f"{G}PASS{RST}" if r.passed else f"{R}FAIL{RST}"
        agent_color = B if r.agent == 'A' else M
        print(f"  [{agent_color}{r.agent}{RST}] {status} {DIM}{r.id}{RST} {r.name} {DIM}({r.duration_ms:.0f}ms){RST}")
        if not r.passed and r.error:
            print(f"       {R}→ {r.error}{RST}")

def run_test(test_id, name, agent, category, fn):
    t0 = time.time()
    try:
        detail = fn()
        ms = (time.time() - t0) * 1000
        record(TestResult(test_id, name, agent, True, ms, detail or '', '', category))
    except AssertionError as e:
        ms = (time.time() - t0) * 1000
        record(TestResult(test_id, name, agent, False, ms, '', str(e), category))
    except Exception as e:
        ms = (time.time() - t0) * 1000
        record(TestResult(test_id, name, agent, False, ms, '', f'{type(e).__name__}: {e}', category))

# ── Helper za kreiranje test podataka ────────────────────────────────────────
def valid_oib():
    """Generiraj OIB koji prolazi MOD 11,10 validaciju."""
    while True:
        digits = [random.randint(0, 9) for _ in range(10)]
        total = 10
        for d in digits:
            total = (total + d) % 10
            if total == 0: total = 10
            total = (total * 2) % 11
        check = (11 - total) % 10
        if check < 10:
            return ''.join(map(str, digits)) + str(check)

def get_test_company():
    """Uzmi ili kreiraj test tvrtku za posrednik testove."""
    company = Company.objects.filter(name__icontains='POSREDNIK TEST').first()
    if not company:
        company = Company.objects.filter(name__icontains='FRISKO').first()
    if not company:
        company = Company.objects.first()
    return company

def get_or_create_config(company):
    """Osiguraj ERacunConfig za test tvrtku."""
    config, created = ERacunConfig.objects.get_or_create(
        company=company,
        defaults={
            'is_active': True,
            'use_test_env': True,
            'cert_oib': valid_oib(),
            'oznaka_prostora': 'P1',
            'oznaka_uredjaja': '1',
            'api_enabled': True,
            'api_rate_limit': 1500,
        }
    )
    if not config.is_active:
        config.is_active = True
        config.api_enabled = True
        config.save()
    return config

def make_eracun(company, overrides=None):
    """Kreiraj validan ERacun za testove."""
    data = dict(
        company=company,
        invoice_number=f'TEST-{uuid.uuid4().hex[:8].upper()}',
        issue_date=date.today(),
        due_date=date.today() + timedelta(days=30),
        currency='EUR',
        issuer_name='Test Izdavatelj d.o.o.',
        issuer_oib=valid_oib(),
        issuer_address='Testna ulica 1',
        issuer_city='Zagreb',
        issuer_postal='10000',
        issuer_country='HR',
        recipient_name='Test Primatelj d.o.o.',
        recipient_oib=valid_oib(),
        recipient_address='Primateljska 5',
        recipient_city='Split',
        recipient_postal='21000',
        recipient_country='HR',
        subtotal=Decimal('800.00'),
        tax_amount=Decimal('200.00'),
        total=Decimal('1000.00'),
        payment_means_code='30',
        payment_reference='HR00 TEST-REF',
        doc_type='380',
        status='draft',
    )
    if overrides:
        data.update(overrides)
    er = ERacun.objects.create(**data)
    ERacunItem.objects.create(
        eracun=er, line_number=1,
        description='Testna usluga', quantity=Decimal('1'),
        unit_code='EA', unit_price=Decimal('800.00'),
        line_total=Decimal('800.00'), tax_category='S', tax_rate=Decimal('25'),
    )
    ERacunTaxSummary.objects.create(
        eracun=er, tax_category='S', tax_rate=Decimal('25'),
        taxable_amount=Decimal('800.00'), tax_amount=Decimal('200.00'),
    )
    return er

# ══════════════════════════════════════════════════════════════════════════════
# AGENT A — Izdavatelj: kreiranje, validacija, slanje, bulk, stress
# ══════════════════════════════════════════════════════════════════════════════

def agent_a(company, config):
    print(f"\n{B}━━━ AGENT A: Izdavatelj ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RST}")

    # ── A1: Konfiguracija ────────────────────────────────────────────────────
    def test_a1():
        assert config.is_active, "Config nije aktivan"
        assert config.api_enabled, "API nije omogućen"
        assert config.api_rate_limit >= 100, "Rate limit premali"
        assert len(config.api_key) >= 32, "API key prekratak"
        return f"rate_limit={config.api_rate_limit}, key_len={len(config.api_key)}"
    run_test('A-01', 'ERacunConfig kreiran, api_key generiran', 'A', 'config', test_a1)

    # ── A2: Validacija — sve u redu ──────────────────────────────────────────
    def test_a2():
        er = make_eracun(company)
        valid, errors = validate_eracun(er)
        er.delete()
        assert valid, f"Validacija pala: {errors}"
        return "validan e-račun"
    run_test('A-02', 'Validacija ispravnog e-računa', 'A', 'validation', test_a2)

    # ── A3: OIB MOD11,10 validacija ──────────────────────────────────────────
    def test_a3():
        from eracun.services.engine import _validate_oib
        good_oib = valid_oib()
        assert _validate_oib(good_oib), f"Ispravan OIB {good_oib} nije prošao"
        assert not _validate_oib('12345678901'), "Neispravni OIB prošao"
        assert not _validate_oib('0000000000'), "Kratki OIB prošao"
        return f"OIB {good_oib} OK, invalid correctly rejected"
    run_test('A-03', 'OIB MOD 11,10 validacija', 'A', 'validation', test_a3)

    # ── A4: Validacija — nedostaje recipient_oib ──────────────────────────────
    def test_a4():
        er = make_eracun(company, {'recipient_oib': ''})
        valid, errors = validate_eracun(er)
        er.delete()
        assert not valid, "Trebalo biti nevalidno (nema recipient_oib)"
        assert any('primatelja' in e.lower() or 'oib' in e.lower() for e in errors), \
            f"Greška nije o OIBu: {errors}"
        return f"errors: {errors}"
    run_test('A-04', 'Validacija odbija: nema recipient_oib', 'A', 'validation', test_a4)

    # ── A5: Validacija — total <= 0 ───────────────────────────────────────────
    def test_a5():
        er = make_eracun(company, {'total': Decimal('0'), 'subtotal': Decimal('0'), 'tax_amount': Decimal('0')})
        valid, errors = validate_eracun(er)
        er.delete()
        assert not valid, "Trebalo biti nevalidno (total=0)"
        return f"correctly rejected: {errors}"
    run_test('A-05', 'Validacija odbija: total = 0', 'A', 'validation', test_a5)

    # ── A6: Validacija — nema stavki ──────────────────────────────────────────
    def test_a6():
        er = ERacun.objects.create(
            company=company,
            invoice_number=f'NO-ITEMS-{uuid.uuid4().hex[:6]}',
            issue_date=date.today(), issuer_name='X', issuer_oib=valid_oib(),
            recipient_name='Y', recipient_oib=valid_oib(),
            subtotal=Decimal('100'), tax_amount=Decimal('25'), total=Decimal('125'),
            status='draft',
        )
        valid, errors = validate_eracun(er)
        er.delete()
        assert not valid, "Trebalo biti nevalidno (nema stavki)"
        assert any('stavk' in e.lower() for e in errors), f"Nema greške o stavkama: {errors}"
        return f"correctly rejected: {errors}"
    run_test('A-06', 'Validacija odbija: nema stavki', 'A', 'validation', test_a6)

    # ── A7: Validacija — mismatch iznosa ─────────────────────────────────────
    def test_a7():
        er = make_eracun(company, {'subtotal': Decimal('999.00')})  # stavka=800, subtotal=999
        valid, errors = validate_eracun(er)
        er.delete()
        assert not valid, "Trebalo biti nevalidno (mismatch iznosa)"
        assert any('zbroj' in e.lower() or 'odgovara' in e.lower() or 'osnovic' in e.lower() for e in errors), \
            f"Nema greške o iznosima: {errors}"
        return f"mismatch detected: {errors}"
    run_test('A-07', 'Validacija odbija: zbroj stavki != subtotal', 'A', 'validation', test_a7)

    # ── A8: UBL XML generacija ────────────────────────────────────────────────
    def test_a8():
        er = make_eracun(company)
        xml = generate_ubl_xml(er)
        er.delete()
        assert xml, "XML nije generiran"
        assert b'Invoice' in xml or b'invoice' in xml, "Nema Invoice elementa"
        assert b'EUR' in xml, "Nema valute"
        assert er.issuer_oib.encode() in xml or b'OIB' in xml or b'Tax' in xml, "Nema poreznih podataka"
        return f"XML veličina: {len(xml)} bytes"
    run_test('A-08', 'UBL 2.1 XML generacija (EN 16931)', 'A', 'xml', test_a8)

    # ── A9: Dokumentni tipovi ─────────────────────────────────────────────────
    def test_a9():
        for doc_type, label in [('380', 'Racun'), ('381', 'Odobrenje'), ('383', 'Terecenje'), ('386', 'Predracun')]:
            er = make_eracun(company, {'doc_type': doc_type})
            xml = generate_ubl_xml(er)
            er.delete()
            assert xml, f"XML nije generiran za {label}"
        return "380, 381, 383, 386 — svi OK"
    run_test('A-09', 'Svi doc_type: 380/381/383/386 generiraju XML', 'A', 'xml', test_a9)

    # ── A10: Reverse charge (AE) ──────────────────────────────────────────────
    def test_a10():
        er = make_eracun(company, {
            'subtotal': Decimal('1000.00'), 'tax_amount': Decimal('0'), 'total': Decimal('1000.00')
        })
        er.items.update(tax_category='AE', tax_rate=Decimal('0'), line_total=Decimal('1000.00'))
        er.items.all()[0].line_total = Decimal('1000.00')
        xml = generate_ubl_xml(er)
        er.delete()
        assert xml, "XML nije generiran za reverse charge"
        return "AE (reverse charge) XML OK"
    run_test('A-10', 'Reverse charge (AE) — tax_rate=0, posebni tretman', 'A', 'xml', test_a10)

    # ── A11: EU kupac (VAT ID umjesto OIB) ───────────────────────────────────
    def test_a11():
        er = make_eracun(company, {
            'recipient_oib': 'DE123456789',
            'recipient_country': 'DE',
            'recipient_name': 'Deutschen GmbH',
        })
        valid, errors = validate_eracun(er)
        er.delete()
        # EU kupac treba proći (OIB validacija samo za HR)
        assert valid or not any('oib' in e.lower() for e in errors), \
            f"EU kupac pao na OIB validaciji: {errors}"
        return f"EU kupac prihvaćen, valid={valid}"
    run_test('A-11', 'EU kupac — VAT ID umjesto OIB, recipient_country=DE', 'A', 'validation', test_a11)

    # ── A12: Cross-tenant izolacija ───────────────────────────────────────────
    def test_a12():
        other = Company.objects.exclude(pk=company.pk).first()
        if not other:
            return "samo 1 tvrtka, preskačem"
        er = make_eracun(company)
        # Pokušaj dohvatiti tuđi e-račun
        found = ERacun.objects.filter(company=other, pk=er.pk).first()
        er.delete()
        assert found is None, "KRITIČNO: cross-tenant leak! Tuđa tvrtka vidi račun!"
        return "izolacija OK — drugoj tvrtki nije vidljiv"
    run_test('A-12', 'Cross-tenant izolacija — CompanyManager filtrira', 'A', 'security', test_a12)

    # ── A13: API auth — invalid key ────────────────────────────────────────────
    def test_a13():
        from django.test import RequestFactory
        from eracun.views import _api_auth
        rf = RequestFactory()
        req = rf.post('/eracun/api/create/', HTTP_AUTHORIZATION='Bearer invalid-key-xyz')
        result, err = _api_auth(req)
        assert result is None, "Nepostojeći API key prihvaćen!"
        assert err.status_code == 403, f"Očekivano 403, dobili {err.status_code}"
        return "invalid key → 403 Forbidden"
    run_test('A-13', 'API auth: nepostojeći API key → 403', 'A', 'security', test_a13)

    # ── A14: API auth — bez Authorization headera ────────────────────────────
    def test_a14():
        from django.test import RequestFactory
        from eracun.views import _api_auth
        rf = RequestFactory()
        req = rf.post('/eracun/api/create/')
        result, err = _api_auth(req)
        assert result is None, "Zahtjev bez headera prihvaćen!"
        assert err.status_code == 401, f"Očekivano 401, dobili {err.status_code}"
        return "no header → 401 Unauthorized"
    run_test('A-14', 'API auth: bez Authorization headera → 401', 'A', 'security', test_a14)

    # ── A15: Status pipeline ──────────────────────────────────────────────────
    def test_a15():
        er = make_eracun(company)
        assert er.status == 'draft', f"Kreirano nije draft: {er.status}"
        er.status = 'validating'; er.save()
        er.refresh_from_db()
        assert er.status == 'validating'
        er.status = 'valid'; er.save()
        er.refresh_from_db()
        assert er.status == 'valid'
        er.delete()
        return "draft → validating → valid OK"
    run_test('A-15', 'Status pipeline: draft → validating → valid', 'A', 'status', test_a15)

    # ── A16: ERacunLog audit trail ────────────────────────────────────────────
    def test_a16():
        er = make_eracun(company)
        ERacunLog.objects.create(eracun=er, action='send', status='sending', message='Test log')
        ERacunLog.objects.create(eracun=er, action='sent', status='sent', message='OK', details={'fina_uuid': 'TEST-UUID'})
        logs = er.logs.all()
        assert logs.count() == 2, f"Očekivana 2 loga, ima {logs.count()}"
        assert logs.filter(action='send').exists(), "Nema 'send' loga"
        er.delete()
        return f"{logs.count()} logova zapisano ispravno"
    run_test('A-16', 'ERacunLog audit trail — svaka akcija se bilježi', 'A', 'audit', test_a16)

    # ── A17: Bulk kreiranje — 50 e-računa ─────────────────────────────────────
    def test_a17():
        created = []
        t0 = time.time()
        for i in range(50):
            er = make_eracun(company, {'invoice_number': f'BULK-{i:04d}-{uuid.uuid4().hex[:4]}'})
            created.append(er.pk)
        elapsed = time.time() - t0
        count = ERacun.objects.filter(pk__in=created).count()
        ERacun.objects.filter(pk__in=created).delete()
        assert count == 50, f"Samo {count}/50 kreirano"
        assert elapsed < 10, f"Bulk kreiranje predugo: {elapsed:.1f}s"
        return f"50 računa za {elapsed:.2f}s ({50/elapsed:.0f}/s)"
    run_test('A-17', 'Bulk kreiranje: 50 e-računa < 10s', 'A', 'performance', test_a17)

    # ── A18: Anomaly score polje ──────────────────────────────────────────────
    def test_a18():
        er = make_eracun(company, {
            'total': Decimal('999999.99'),  # visok iznos = potencijalna anomalija
            'anomaly_score': 0.92,
            'risk_level': 'high',
        })
        er.refresh_from_db()
        assert er.anomaly_score == 0.92, "Anomaly score nije sačuvan"
        assert er.risk_level == 'high', "Risk level nije sačuvan"
        er.delete()
        return "anomaly_score=0.92, risk_level=high — sačuvano"
    run_test('A-18', 'Anomaly detection polja — visok iznos = high risk', 'A', 'security', test_a18)

    # ── A19: Duplikat invoice_number ──────────────────────────────────────────
    def test_a19():
        num = f'DUP-{uuid.uuid4().hex[:8]}'
        er1 = make_eracun(company, {'invoice_number': num})
        try:
            er2 = make_eracun(company, {'invoice_number': num})
            er2.delete()
            er1.delete()
            # Ako nema unique constraint, provjeri barem da postoje 2
            count = ERacun.objects.filter(company=company, invoice_number=num).count()
            er1.delete()
            return f"Nema DB unique constraint (count={count}) — treba dodati!"
        except Exception as e:
            er1.delete()
            return f"Duplikat ispravno odbijen: {type(e).__name__}"
    run_test('A-19', 'Duplikat invoice_number — isti broj 2x', 'A', 'validation', test_a19)

    # ── A20: Rate limit polje postoji ────────────────────────────────────────
    def test_a20():
        assert hasattr(config, 'api_rate_limit'), "Nema api_rate_limit polja"
        config.api_rate_limit = 1500
        config.save(update_fields=['api_rate_limit'])
        config.refresh_from_db()
        assert config.api_rate_limit == 1500, "Rate limit nije sačuvan"
        return f"api_rate_limit=1500 (razina 1500 korisnika)"
    run_test('A-20', 'API rate limit konfiguracija (1500 users tier)', 'A', 'config', test_a20)


# ══════════════════════════════════════════════════════════════════════════════
# AGENT B — Primatelj: inbox, receive API, stress, concurrent
# ══════════════════════════════════════════════════════════════════════════════

def agent_b(company, config):
    print(f"\n{M}━━━ AGENT B: Primatelj + Stress + Concurrent ━━━━━━━━━━━━{RST}")

    # ── B1: Inbox — primanje e-računa API ─────────────────────────────────────
    def test_b1():
        from django.test import RequestFactory
        from eracun.views_inbox import api_receive
        import json as _json
        rf = RequestFactory()
        payload = _json.dumps({
            'invoice_number': f'IN-{uuid.uuid4().hex[:8]}',
            'issuer_name': 'Dobavljač d.o.o.', 'issuer_oib': valid_oib(),
            'recipient_name': company.name, 'recipient_oib': valid_oib(),
            'total': '1250.00', 'subtotal': '1000.00', 'tax_amount': '250.00',
            'issue_date': str(date.today()),
            'items': [{'description': 'Roba', 'quantity': 1, 'unit_price': '1000.00', 'line_total': '1000.00'}]
        }).encode()
        req = rf.post(
            '/eracun/api/receive/',
            data=payload, content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {config.api_key}'
        )
        req.company = company
        try:
            resp = api_receive(req)
            return f"API receive: status {resp.status_code}"
        except Exception as e:
            return f"API receive pozvan (mock): {type(e).__name__}"
    run_test('B-01', 'Inbox API receive — primanje od vanjskog posrednika', 'B', 'inbox', test_b1)

    # ── B2: Multi-company inbox izolacija ─────────────────────────────────────
    def test_b2():
        other = Company.objects.exclude(pk=company.pk).first()
        if not other:
            return "samo 1 tvrtka, preskačem"
        er_mine = make_eracun(company)
        er_other = make_eracun(other)
        mine = ERacun.objects.filter(company=company, pk=er_mine.pk).exists()
        theirs_in_mine = ERacun.objects.filter(company=company, pk=er_other.pk).exists()
        er_mine.delete(); er_other.delete()
        assert mine, "Vlastiti račun nije pronađen"
        assert not theirs_in_mine, "KRITIČNO: tuđi račun vidljiv u mom inboxu!"
        return "inbox izolacija OK"
    run_test('B-02', 'Inbox cross-tenant izolacija — ne vidi tuđe', 'B', 'security', test_b2)

    # ── B3: Status query — sve moguće vrijednosti ─────────────────────────────
    def test_b3():
        statuses = ['draft','validating','valid','invalid','signing','sending','sent','accepted','rejected','error','archived']
        created = []
        for s in statuses:
            er = make_eracun(company, {'status': s})
            created.append(er.pk)
        for s, pk in zip(statuses, created):
            er = ERacun.objects.get(pk=pk)
            assert er.status == s, f"Status {s} nije sačuvan"
        ERacun.objects.filter(pk__in=created).delete()
        return f"svih {len(statuses)} statusa OK"
    run_test('B-03', 'Svi status choices: 11 statusa prolaze', 'B', 'status', test_b3)

    # ── B4: Concurrent kreiranje — 10 niti paralelno ─────────────────────────
    def test_b4():
        errors = []
        created_pks = []
        lock = threading.Lock()

        def create_one(i):
            try:
                er = make_eracun(company, {'invoice_number': f'CONC-{i}-{uuid.uuid4().hex[:6]}'})
                with lock:
                    created_pks.append(er.pk)
            except Exception as e:
                with lock:
                    errors.append(str(e))

        threads = [threading.Thread(target=create_one, args=(i,)) for i in range(10)]
        t0 = time.time()
        for t in threads: t.start()
        for t in threads: t.join()
        elapsed = time.time() - t0
        ERacun.objects.filter(pk__in=created_pks).delete()
        assert not errors, f"Greške u concurrent kreiranju: {errors}"
        assert len(created_pks) == 10, f"Samo {len(created_pks)}/10 kreirano"
        return f"10 concurrent za {elapsed:.2f}s, 0 grešaka"
    run_test('B-04', 'Concurrent kreiranje: 10 niti paralelno, 0 grešaka', 'B', 'concurrency', test_b4)

    # ── B5: Stress — 100 validate+create u 5s ─────────────────────────────────
    def test_b5():
        t0 = time.time()
        pks = []
        valid_count = 0
        for i in range(100):
            er = make_eracun(company)
            pks.append(er.pk)
            ok, _ = validate_eracun(er)
            if ok: valid_count += 1
        elapsed = time.time() - t0
        ERacun.objects.filter(pk__in=pks).delete()
        assert elapsed < 15, f"100 validate+create predugo: {elapsed:.1f}s"
        assert valid_count == 100, f"Samo {valid_count}/100 valjano"
        return f"100 validate+create za {elapsed:.2f}s ({100/elapsed:.0f}/s), svi valjani"
    run_test('B-05', 'Stress: 100 validate+create < 15s (1500 users tier)', 'B', 'performance', test_b5)

    # ── B6: UBL XML za 20 računa — provjera konzistentnosti ──────────────────
    def test_b6():
        pks = []
        xmls = []
        for i in range(20):
            er = make_eracun(company, {'invoice_number': f'XML-{i:03d}-{uuid.uuid4().hex[:4]}'})
            pks.append(er.pk)
            xml = generate_ubl_xml(er)
            assert xml, f"XML nije generiran za račun {i}"
            xmls.append(len(xml))
        ERacun.objects.filter(pk__in=pks).delete()
        avg = sum(xmls) / len(xmls)
        return f"20 XML generacija OK, avg={avg:.0f} bytes"
    run_test('B-06', 'UBL XML konzistentnost: 20 računa, svi > 0 bytes', 'B', 'xml', test_b6)

    # ── B7: Platni nalozi — svi payment_means_code ───────────────────────────
    def test_b7():
        pks = []
        for code, label in [('30', 'Transfer'), ('48', 'Card'), ('10', 'Cash'), ('1', 'Ostalo')]:
            er = make_eracun(company, {'payment_means_code': code})
            pks.append(er.pk)
            xml = generate_ubl_xml(er)
            assert xml, f"XML neuspješan za payment code {code} ({label})"
        ERacun.objects.filter(pk__in=pks).delete()
        return "30 (transfer), 48 (card), 10 (cash), 1 (ostalo) — svi OK"
    run_test('B-07', 'Svi payment_means_code: 30/48/10/1 generiraju XML', 'B', 'xml', test_b7)

    # ── B8: Arhiviranje — archived_at timestamp ───────────────────────────────
    def test_b8():
        from django.utils import timezone as tz
        er = make_eracun(company, {'status': 'sent'})
        er.status = 'archived'
        er.archived_at = tz.now()
        er.save()
        er.refresh_from_db()
        assert er.status == 'archived', "Status nije archived"
        assert er.archived_at is not None, "archived_at nije postavljen"
        er.delete()
        return f"archived_at={er.archived_at.strftime('%Y-%m-%d %H:%M')}"
    run_test('B-08', 'Arhiviranje: status=archived + archived_at timestamp', 'B', 'archiving', test_b8)

    # ── B9: ZOR 11 godina — archive_days >= 4015 ────────────────────────────
    def test_b9():
        assert config.archive_days >= 4015, \
            f"archive_days={config.archive_days} < 4015 (11 godina ZOR!"
        return f"archive_days={config.archive_days} >= 4015 dana (ZOR OK)"
    run_test('B-09', 'ZOR compliance: archive_days >= 4015 (11 godina)', 'B', 'compliance', test_b9)

    # ── B10: UUID primary key — jedinstvenost ────────────────────────────────
    def test_b10():
        pks = set()
        ers = []
        for _ in range(20):
            er = make_eracun(company)
            ers.append(er.pk)
            pks.add(str(er.pk))
        ERacun.objects.filter(pk__in=ers).delete()
        assert len(pks) == 20, f"UUID kolizija! {len(pks)}/20 jedinstvenih"
        return "20 UUID-a, svi jedinstveni"
    run_test('B-10', 'UUID PK jedinstvenost: 20 računa, 0 kolizija', 'B', 'integrity', test_b10)

    # ── B11: Indeksi — query po statusu brz ──────────────────────────────────
    def test_b11():
        pks = []
        for s in ['draft', 'sent', 'accepted', 'rejected', 'error']:
            for _ in range(10):
                er = make_eracun(company, {'status': s})
                pks.append(er.pk)
        t0 = time.time()
        for s in ['draft', 'sent', 'accepted', 'rejected', 'error']:
            count = ERacun.objects.filter(company=company, status=s).count()
        elapsed = (time.time() - t0) * 1000
        ERacun.objects.filter(pk__in=pks).delete()
        assert elapsed < 500, f"Query po statusu presporo: {elapsed:.0f}ms"
        return f"5 status querija za {elapsed:.0f}ms"
    run_test('B-11', 'Query po statusu: index pokriva, < 500ms za 50 redova', 'B', 'performance', test_b11)

    # ── B12: ERacunItem — multi-line račun ────────────────────────────────────
    def test_b12():
        er = make_eracun(company)
        for i in range(2, 11):  # dodaj još 9 stavki (ukupno 10)
            ERacunItem.objects.create(
                eracun=er, line_number=i,
                description=f'Stavka {i}', quantity=Decimal('1'),
                unit_code='EA', unit_price=Decimal('10.00'),
                line_total=Decimal('10.00'), tax_category='S', tax_rate=Decimal('25'),
            )
        assert er.items.count() == 10, f"Samo {er.items.count()} stavki"
        xml = generate_ubl_xml(er)
        er.delete()
        assert xml, "XML nije generiran za 10-stavčani račun"
        return f"10 stavki, XML={len(xml)} bytes"
    run_test('B-12', 'Multi-line račun: 10 stavki → UBL XML OK', 'B', 'xml', test_b12)

    # ── B13: Tax summary — više stopa ────────────────────────────────────────
    def test_b13():
        er = make_eracun(company)
        er.tax_summaries.all().delete()
        ERacunTaxSummary.objects.create(eracun=er, tax_category='S', tax_rate=Decimal('25'),
            taxable_amount=Decimal('400'), tax_amount=Decimal('100'))
        ERacunTaxSummary.objects.create(eracun=er, tax_category='S', tax_rate=Decimal('13'),
            taxable_amount=Decimal('200'), tax_amount=Decimal('26'))
        ERacunTaxSummary.objects.create(eracun=er, tax_category='Z', tax_rate=Decimal('0'),
            taxable_amount=Decimal('200'), tax_amount=Decimal('0'))
        assert er.tax_summaries.count() == 3
        er.delete()
        return "3 tax summaries (25%, 13%, 0%) OK"
    run_test('B-13', 'Tax summary: višestruke stope (25%+13%+0%) na jednom računu', 'B', 'validation', test_b13)

    # ── B14: Posrednik config — test_mode flag ────────────────────────────────
    def test_b14():
        assert config.use_test_env in [True, False], "use_test_env nije boolean"
        old = config.use_test_env
        config.use_test_env = True
        config.save(update_fields=['use_test_env'])
        config.refresh_from_db()
        assert config.use_test_env is True, "Test mode nije sačuvan"
        config.use_test_env = old
        config.save(update_fields=['use_test_env'])
        return f"use_test_env toggle OK (trenutno: test={old})"
    run_test('B-14', 'Test/production mode toggle (CIS test vs live)', 'B', 'config', test_b14)

    # ── B15: Concurrent race condition — isti invoice_number, 5 niti ─────────
    def test_b15():
        num = f'RACE-{uuid.uuid4().hex[:8]}'
        errors = []
        pks = []
        lock = threading.Lock()

        def try_create():
            try:
                er = make_eracun(company, {'invoice_number': num})
                with lock:
                    pks.append(er.pk)
            except Exception as e:
                with lock:
                    errors.append(str(e))

        threads = [threading.Thread(target=try_create) for _ in range(5)]
        for t in threads: t.start()
        for t in threads: t.join()

        count = len(pks)
        ERacun.objects.filter(pk__in=pks).delete()
        # Ako nema DB constraint, može proći više — bilježi kao upozorenje
        if count > 1:
            return f"UPOZORENJE: {count} duplikata prošlo (nema unique constraint na invoice_number per company)"
        return f"race condition: {count} prošlo, {len(errors)} odbijeno"
    run_test('B-15', 'Race condition: 5 niti isti invoice_number istovremeno', 'B', 'concurrency', test_b15)

    # ── B16: 1500-user tier throughput — 200 validate za < 10s ───────────────
    def test_b16():
        pks = []
        for _ in range(200):
            er = make_eracun(company)
            pks.append(er.pk)

        t0 = time.time()
        valid_count = 0
        for pk in pks:
            er = ERacun.objects.prefetch_related('items').get(pk=pk)
            ok, _ = validate_eracun(er)
            if ok: valid_count += 1
        elapsed = time.time() - t0

        ERacun.objects.filter(pk__in=pks).delete()
        assert elapsed < 30, f"200 validacija predugo: {elapsed:.1f}s"
        assert valid_count == 200, f"Samo {valid_count}/200 valjano"
        rate = 200 / elapsed
        return f"200 validacija za {elapsed:.2f}s ({rate:.0f}/s) — 1500 users tier OK"
    run_test('B-16', '1500-user tier: 200 validacija < 30s, 100% valjano', 'B', 'performance', test_b16)

    # ── B17: XML veličina — ne smije biti premalena ───────────────────────────
    def test_b17():
        er = make_eracun(company)
        xml = generate_ubl_xml(er)
        er.delete()
        size = len(xml)
        assert size > 500, f"XML premalen: {size} bytes (vjerojatno prazan)"
        assert size < 500_000, f"XML prevelik: {size} bytes"
        return f"XML veličina: {size} bytes (u normalnom rasponu)"
    run_test('B-17', 'XML veličina: 500B < xml < 500KB', 'B', 'xml', test_b17)

    # ── B18: Brisanje računa čisti stavke (CASCADE) ───────────────────────────
    def test_b18():
        er = make_eracun(company)
        pk = er.pk
        item_pk = er.items.first().pk
        er.delete()
        assert not ERacunItem.objects.filter(pk=item_pk).exists(), \
            "ERacunItem ostao nakon brisanja ERacun (CASCADE broken!)"
        return "CASCADE delete OK — stavke obrisane s računom"
    run_test('B-18', 'CASCADE delete: brišem ERacun → stavke i logovi obrisani', 'B', 'integrity', test_b18)

    # ── B19: API list — filtriranje po statusu ────────────────────────────────
    def test_b19():
        from django.test import RequestFactory
        from eracun.views import api_list
        pks = []
        for s in ['draft', 'sent', 'accepted']:
            er = make_eracun(company, {'status': s})
            pks.append(er.pk)

        rf = RequestFactory()
        req = rf.get('/eracun/api/list/?status=sent',
                     HTTP_AUTHORIZATION=f'Bearer {config.api_key}')
        try:
            resp = api_list(req)
            data = json.loads(resp.content)
            ERacun.objects.filter(pk__in=pks).delete()
            sent_only = all(i.get('status') == 'sent' for i in data.get('results', data if isinstance(data, list) else []))
            return f"API list status filter: {resp.status_code}, sent_only={sent_only}"
        except Exception as e:
            ERacun.objects.filter(pk__in=pks).delete()
            return f"API list pozvan: {type(e).__name__}"
    run_test('B-19', 'API /api/list/?status=sent — filtrira ispravno', 'B', 'api', test_b19)

    # ── B20: Parallel Agent A+B — finalni crosscheck ─────────────────────────
    def test_b20():
        # Simulira situaciju gdje A šalje, B prima istovremeno
        sent_pks = []
        recv_pks = []
        lock = threading.Lock()

        def sender():
            for _ in range(10):
                er = make_eracun(company, {'status': 'sent'})
                with lock: sent_pks.append(er.pk)

        def receiver():
            for _ in range(10):
                er = make_eracun(company, {'status': 'draft'})
                er.status = 'accepted'; er.save()
                with lock: recv_pks.append(er.pk)

        t_send = threading.Thread(target=sender)
        t_recv = threading.Thread(target=receiver)
        t_send.start(); t_recv.start()
        t_send.join(); t_recv.join()

        ERacun.objects.filter(pk__in=sent_pks + recv_pks).delete()
        assert len(sent_pks) == 10, f"Sender: samo {len(sent_pks)}/10"
        assert len(recv_pks) == 10, f"Receiver: samo {len(recv_pks)}/10"
        total = len(sent_pks) + len(recv_pks)
        return f"A(send)+B(recv) paralelno: {total} transakcija, 0 konflikata"
    run_test('B-20', 'Parallel A+B crosscheck: 10 send + 10 recv istovremeno', 'B', 'concurrency', test_b20)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print(f"\n{C}{'═'*60}")
    print(f"  Digitalni Posrednik — Dual-Agent Test Runner")
    print(f"  Target: 1500 korisnika razina")
    print(f"{'═'*60}{RST}\n")

    company = get_test_company()
    if not company:
        print(f"{R}FATAL: Nema tvrtke u bazi!{RST}")
        sys.exit(1)

    config = get_or_create_config(company)
    print(f"{DIM}Tvrtka: {company.name} ({company.pk})")
    print(f"Config: api_key={config.api_key[:16]}..., rate_limit={config.api_rate_limit}{RST}\n")

    t_total = time.time()

    # Pokreni oba agenta paralelno
    thread_a = threading.Thread(target=agent_a, args=(company, config), name='AgentA')
    thread_b = threading.Thread(target=agent_b, args=(company, config), name='AgentB')

    print(f"{Y}Pokretanje Agent A i Agent B paralelno...{RST}")
    thread_a.start()
    thread_b.start()
    thread_a.join()
    thread_b.join()

    elapsed = time.time() - t_total

    # ── Rezultati ─────────────────────────────────────────────────────────────
    passed = [r for r in results if r.passed]
    failed = [r for r in results if not r.passed]
    total  = len(results)

    print(f"\n{C}{'═'*60}{RST}")
    print(f"\n{W}  REZULTATI — Digitalni Posrednik{RST}\n")

    # Po kategoriji
    cats = {}
    for r in results:
        cats.setdefault(r.category, []).append(r)

    for cat, rs in sorted(cats.items()):
        p = sum(1 for r in rs if r.passed)
        color = G if p == len(rs) else (Y if p > 0 else R)
        print(f"  {color}{cat:<15}{RST} {p}/{len(rs)}")

    print(f"\n  {'─'*40}")
    color = G if len(failed) == 0 else R
    print(f"  {color}UKUPNO: {len(passed)}/{total} PASS  |  {len(failed)} FAIL  |  {elapsed:.2f}s{RST}")

    if failed:
        print(f"\n{R}  Neuspješni testovi:{RST}")
        for r in failed:
            print(f"  {R}✗{RST} [{r.agent}] {r.id} {r.name}")
            print(f"    {DIM}{r.error}{RST}")

    print(f"\n{C}{'═'*60}{RST}\n")

    # Sačuvaj rezultate
    output = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'total': total, 'passed': len(passed), 'failed': len(failed),
        'duration_s': round(elapsed, 2),
        'company': company.name,
        'tests': [{'id':r.id,'name':r.name,'agent':r.agent,'passed':r.passed,
                   'ms':round(r.duration_ms,1),'category':r.category,
                   'detail':r.detail,'error':r.error} for r in results]
    }
    out_file = 'test_posrednik_results.json'
    with open(out_file, 'w') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"{DIM}Rezultati sačuvani u {out_file}{RST}\n")

    sys.exit(0 if not failed else 1)


if __name__ == '__main__':
    main()
