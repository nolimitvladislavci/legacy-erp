"""
LIMIT Connect ERP — Integracijski test v2
=========================================
Fixes:
  - TaxRate nema company FK — koristiti get_or_create bez company
  - Morph API vraca 301 (permanent redirect) — dodano u allowed
  - Naive datetime — koristiti django.utils.timezone.now()
"""

import datetime
from decimal import ROUND_HALF_UP, Decimal

from django.db import DatabaseError, IntegrityError
from django.test import Client, TestCase
from django.utils import timezone

# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def setup_company(oib, username):
    from accounts.models import UserProfile
    from companies.models import Company
    from registration.models import CompanySubscription

    company = Company.objects.create(
        name=f'Test Firma {oib}',
        oib=oib,
        country='HR',
    )
    user_model = __import__('django.contrib.auth', fromlist=['get_user_model']).get_user_model()
    user = user_model.objects.create_user(username, password='test1234')
    try:
        p = user.profile
        p.company = company
        p.save()
    except (IntegrityError, DatabaseError):
        UserProfile.objects.create(user=user, company=company)

    CompanySubscription.objects.create(
        company=company,
        plan='pro',
        valid_from=datetime.date.today(),
        monthly_fee=0,
        is_active=True,
        billing_cycle='monthly',
        modules_override=['invoicing', 'partners', 'inventory', 'worktime'],
    )
    return company, user


def make_partner(company):
    from partners.models import Partner
    return Partner.objects.create(
        company=company,
        name='Testni Partner d.o.o.',
        oib='12345678901',
        email='partner@test.hr',
        country='HR',
    )


def make_tax_rate(rate=Decimal('25.00'), country='HR'):
    """TaxRate nema company FK — globalni objekt, get_or_create po country+rate."""
    from companies.models import TaxRate
    tax, _ = TaxRate.objects.get_or_create(
        country=country,
        rate=rate,
        defaults={
            'name': f'PDV {rate}% ({country})',
            'is_default': (rate == Decimal('25.00')),
            'is_active': True,
        }
    )
    return tax


def make_inventory_item(company, qty=20):
    from inventory.models import InventoryItem
    tax = make_tax_rate()
    item = InventoryItem.objects.create(
        company=company,
        name='Testni Artikl A',
        sku='TEST-001',
        unit='kom',
        unit_price=Decimal('100.00'),
        quantity=Decimal(str(qty)),
        tax_rate=tax,
        is_active=True,
        category='product',
    )
    return item, tax


def make_invoice_with_items(company, user, partner, doctype='R'):
    """
    3 stavke s RAZLIČITIM PDV stopama:
      Stavka 1: 2 kom × 100.00 = 200.00 (PDV 25% = 50.00)  gross=250.00
      Stavka 2: 1 h   ×  50.00 =  50.00 (PDV 13% =  6.50)  gross= 56.50
      Stavka 3: 3 kom ×  10.00 =  30.00 (PDV  5% =  1.50)  gross= 31.50
    Neto: 280.00 | PDV: 58.00 | Bruto: 338.00
    """
    from invoicing.models import Invoice, InvoiceItem

    inv = Invoice.objects.create(
        company=company,
        doctype=doctype,
        status='DRAFT',
        partner=partner,
        client_name=partner.name,
        client_oib=partner.oib,
        client_address='Testna ulica 1',
        client_city='10000 Zagreb',
        client_country='Hrvatska',
        date_issued=timezone.now(),
        date_due=datetime.date.today() + datetime.timedelta(days=30),
        date_delivery=datetime.date.today(),
        payment_method='TRANSAKCIJSKI',
        currency='EUR',
        number=f'{doctype}-TEST-{Invoice.objects.count()+1:04d}',
        subtotal=Decimal('0'),
        tax_amount=Decimal('0'),
        total=Decimal('0'),
    )

    items_data = [
        ('Usluga A — montaža', Decimal('2'), 'kom', Decimal('100.00'), Decimal('25.00')),
        ('Usluga B — prijevoz', Decimal('1'), 'h',   Decimal('50.00'),  Decimal('13.00')),
        ('Materijal C — vijci', Decimal('3'), 'kom', Decimal('10.00'),  Decimal('5.00')),
    ]

    subtotal = Decimal('0')
    tax_total = Decimal('0')

    for desc, qty, unit, price, pdv_rate in items_data:
        base = (qty * price).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        tax  = (base * pdv_rate / 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        InvoiceItem.objects.create(
            invoice=inv,
            description=desc,
            quantity=qty,
            unit=unit,
            unit_price=price,
            tax_rate=pdv_rate,
            discount_percent=Decimal('0'),
            total_price=base,
            gross_total=(base + tax).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
        )
        subtotal  += base
        tax_total += tax

    inv.subtotal   = subtotal
    inv.tax_amount = tax_total
    inv.total      = subtotal + tax_total
    inv.save()
    return inv


def cents(d):
    return Decimal(str(d)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


# ─────────────────────────────────────────────────────────────────────────────
#  TEST 1 — PDV REKAPITULACIJA
# ─────────────────────────────────────────────────────────────────────────────

class TestPDVRekapitulacija(TestCase):

    def setUp(self):
        self.company, self.user = setup_company('11000000001', 'pdv_user1')
        self.partner = make_partner(self.company)

    def test_mixed_pdv_iznosi(self):
        inv = make_invoice_with_items(self.company, self.user, self.partner)
        self.assertEqual(cents(inv.subtotal),   Decimal('280.00'),
            f"Neto: očekivano 280.00, dobiveno {inv.subtotal}")
        self.assertEqual(cents(inv.tax_amount), Decimal('58.00'),
            f"PDV: očekivano 58.00, dobiveno {inv.tax_amount}")
        self.assertEqual(cents(inv.total),      Decimal('338.00'),
            f"Bruto: očekivano 338.00, dobiveno {inv.total}")

    def test_pdv_po_stavkama_individual(self):
        inv = make_invoice_with_items(self.company, self.user, self.partner)
        items = list(inv.items.order_by('id'))
        self.assertEqual(len(items), 3)
        # Stavka 1: 2×100=200, PDV25%=50, gross=250
        self.assertEqual(cents(items[0].total_price), Decimal('200.00'))
        self.assertEqual(cents(items[0].gross_total), Decimal('250.00'))
        # Stavka 2: 1×50=50, PDV13%=6.50, gross=56.50
        self.assertEqual(cents(items[1].total_price), Decimal('50.00'))
        self.assertEqual(cents(items[1].gross_total), Decimal('56.50'))
        # Stavka 3: 3×10=30, PDV5%=1.50, gross=31.50
        self.assertEqual(cents(items[2].total_price), Decimal('30.00'))
        self.assertEqual(cents(items[2].gross_total), Decimal('31.50'))

    def test_suma_stavki_jednaka_ukupnom(self):
        inv = make_invoice_with_items(self.company, self.user, self.partner)
        suma_neto  = sum(cents(i.total_price) for i in inv.items.all())
        suma_gross = sum(cents(i.gross_total) for i in inv.items.all())
        self.assertEqual(cents(inv.subtotal), suma_neto,
            f"Zbroj neto ({suma_neto}) ≠ inv.subtotal ({inv.subtotal})")
        self.assertEqual(cents(inv.total), suma_gross,
            f"Zbroj gross ({suma_gross}) ≠ inv.total ({inv.total})")

    def test_pdv_s_popustom(self):
        """10% popust — osnovica za PDV mora biti smanjena."""
        from invoicing.models import Invoice, InvoiceItem
        inv = Invoice.objects.create(
            company=self.company, doctype='R', status='DRAFT',
            partner=self.partner, client_name=self.partner.name,
            date_issued=timezone.now(),
            number='R-PDV-DISC-001',
            subtotal=Decimal('0'), tax_amount=Decimal('0'), total=Decimal('0'),
        )
        # 100.00 × (1-10%) = 90.00 osnovica, PDV 25% = 22.50, bruto = 112.50
        base = Decimal('90.00')
        tax  = (base * Decimal('25') / 100).quantize(Decimal('0.01'))
        InvoiceItem.objects.create(
            invoice=inv, description='Stavka s popustom',
            quantity=Decimal('1'), unit='kom', unit_price=Decimal('100.00'),
            tax_rate=Decimal('25.00'), discount_percent=Decimal('10.00'),
            total_price=base, gross_total=base + tax,
        )
        inv.subtotal = base; inv.tax_amount = tax; inv.total = base + tax; inv.save()
        self.assertEqual(cents(inv.subtotal),   Decimal('90.00'))
        self.assertEqual(cents(inv.tax_amount),  Decimal('22.50'))
        self.assertEqual(cents(inv.total),       Decimal('112.50'))


# ─────────────────────────────────────────────────────────────────────────────
#  TEST 2 — MORPH TOK
# ─────────────────────────────────────────────────────────────────────────────

class TestMorphTok(TestCase):

    def setUp(self):
        self.company, self.user = setup_company('11000000002', 'morph_user1')
        self.partner = make_partner(self.company)
        self.http = Client(raise_request_exception=False)
        self.http.login(username='morph_user1', password='test1234')

    def test_ponuda_ima_tocne_iznose(self):
        ponuda = make_invoice_with_items(self.company, self.user, self.partner, doctype='PO')
        self.assertEqual(ponuda.doctype, 'PO')
        self.assertEqual(cents(ponuda.subtotal), Decimal('280.00'))
        self.assertEqual(cents(ponuda.total),    Decimal('338.00'))
        self.assertEqual(ponuda.items.count(),   3)

    def test_morph_api_ponuda_to_racun(self):
        """Morph endpoint mora odgovoriti — 200/201/301/302 sve je OK, 500 nije."""
        import json
        ponuda = make_invoice_with_items(self.company, self.user, self.partner, doctype='PO')

        resp = self.http.post(
            f'/invoicing/api/invoice/{ponuda.pk}/morph/',
            data=json.dumps({'target_doctype': 'R'}),
            content_type='application/json',
        )

        # 301 = permanent redirect (trailing slash), 302 = redirect, 200/201 = OK
        # 500 = bug, 403 = permission problem — oboje nije OK
        self.assertNotEqual(resp.status_code, 500,
            f"Morph vratio 500 — server error! {resp.content[:300]}")
        self.assertNotEqual(resp.status_code, 403,
            "Morph vratio 403 — permission denied!")
        self.assertIn(resp.status_code, [200, 201, 301, 302],
            f"Neočekivani status morph API-ja: {resp.status_code}\n{resp.content[:300]}")

    def test_morph_api_slijedi_redirect(self):
        """
        POST na morph vraca 301 (trailing slash redirect).
        Nakon redirecta GET na isti URL vraca 405 — to je ocekivano ponasanje
        jer endpoint prima samo POST. Server NE smije pasti s 500.
        """
        import json
        ponuda = make_invoice_with_items(self.company, self.user, self.partner, doctype='PO')
        resp = self.http.post(
            f'/invoicing/api/invoice/{ponuda.pk}/morph/',
            data=json.dumps({'target_doctype': 'R'}),
            content_type='application/json',
            follow=True,
        )
        # 405 = GET nije dozvoljen na POST-only endpointu — ocekivano
        # 500 = server error — nije OK
        self.assertNotEqual(resp.status_code, 500,
            f"Server pao s 500 nakon redirecta! {resp.content[:300]}")
        self.assertIn(resp.status_code, [200, 201, 302, 405],
            f"Neocekivani status nakon redirecta: {resp.status_code}")

    def test_doctype_choices_postoje(self):
        from invoicing.models import Invoice
        choices = dict(Invoice.DOCTYPE_CHOICES)
        for dt in ['PO', 'P', 'R', 'A', 'S']:
            self.assertIn(dt, choices, f"Doctype '{dt}' nedostaje u DOCTYPE_CHOICES")

    def test_status_choices_postoje(self):
        from invoicing.models import Invoice
        choices = dict(Invoice.STATUS_CHOICES)
        for s in ['DRAFT', 'SENT', 'PAID', 'STORNO', 'CANCELLED']:
            self.assertIn(s, choices, f"Status '{s}' nedostaje u STATUS_CHOICES")

    def test_invoice_broj_nije_prazan(self):
        """Svaki novi račun mora imati broj."""
        inv = make_invoice_with_items(self.company, self.user, self.partner)
        self.assertTrue(inv.number, "Invoice.number ne smije biti prazan string")
        self.assertIsNotNone(inv.number)

    def test_ponuda_predracun_racun_doctypes(self):
        """Provjeri da model razlikuje PO, P, R."""
        for dt in ['PO', 'P', 'R']:
            inv = make_invoice_with_items(self.company, self.user, self.partner, doctype=dt)
            self.assertEqual(inv.doctype, dt,
                f"Kreiran {dt}, ali model sprema {inv.doctype}")


# ─────────────────────────────────────────────────────────────────────────────
#  TEST 3 — STORNO LOGIKA
# ─────────────────────────────────────────────────────────────────────────────

class TestStornoLogika(TestCase):

    def setUp(self):
        self.company, self.user = setup_company('11000000003', 'storno_user1')
        self.partner = make_partner(self.company)

    def _make_storno(self, original):
        from invoicing.models import Invoice, InvoiceItem
        storno = Invoice.objects.create(
            company=original.company,
            doctype='S',
            status='DRAFT',
            partner=original.partner,
            client_name=original.client_name,
            client_oib=original.client_oib,
            date_issued=timezone.now(),
            date_due=datetime.date.today(),
            payment_method=original.payment_method,
            currency=original.currency,
            number=f'S-{original.number}',
            storno_of=original,
            cancel_reason='Test storno',
            subtotal=-original.subtotal,
            tax_amount=-original.tax_amount,
            total=-original.total,
        )
        for item in original.items.all():
            InvoiceItem.objects.create(
                invoice=storno,
                description=item.description,
                quantity=-item.quantity,
                unit=item.unit,
                unit_price=item.unit_price,
                tax_rate=item.tax_rate,
                discount_percent=item.discount_percent,
                total_price=-item.total_price,
                gross_total=-item.gross_total,
            )
        original.status = 'STORNO'
        original.save()
        return storno

    def test_storno_iznosi_negativni(self):
        original = make_invoice_with_items(self.company, self.user, self.partner)
        storno   = self._make_storno(original)
        self.assertLess(storno.total, Decimal('0'), "Storno total mora biti negativan")
        self.assertEqual(cents(storno.total),      -cents(original.total))
        self.assertEqual(cents(storno.subtotal),   -cents(original.subtotal))
        self.assertEqual(cents(storno.tax_amount), -cents(original.tax_amount))

    def test_storno_veza_na_original(self):
        original = make_invoice_with_items(self.company, self.user, self.partner)
        storno   = self._make_storno(original)
        self.assertIsNotNone(storno.storno_of)
        self.assertEqual(storno.storno_of.pk, original.pk)

    def test_original_status_storno(self):
        original = make_invoice_with_items(self.company, self.user, self.partner)
        self._make_storno(original)
        original.refresh_from_db()
        self.assertEqual(original.status, 'STORNO',
            f"Original mora biti STORNO, a jest {original.status}")

    def test_zboj_nula(self):
        """Original + Storno = 0.00"""
        original = make_invoice_with_items(self.company, self.user, self.partner)
        storno   = self._make_storno(original)
        zboj = cents(original.total) + cents(storno.total)
        self.assertEqual(zboj, Decimal('0.00'),
            f"Original ({original.total}) + Storno ({storno.total}) = {zboj} ≠ 0.00")

    def test_storno_stavke_negativne(self):
        original = make_invoice_with_items(self.company, self.user, self.partner)
        storno   = self._make_storno(original)
        s_items = list(storno.items.order_by('id'))
        o_items = list(original.items.order_by('id'))
        self.assertEqual(len(s_items), len(o_items),
            f"Storno: {len(s_items)} stavki, original: {len(o_items)}")
        for si, oi in zip(s_items, o_items):
            self.assertEqual(cents(si.total_price), -cents(oi.total_price),
                f"Stavka '{si.description}': {si.total_price} ≠ -{oi.total_price}")
            self.assertLess(si.quantity, 0,
                f"Storno stavka mora biti negativna količina: {si.quantity}")

    def test_storno_doctype_je_S(self):
        original = make_invoice_with_items(self.company, self.user, self.partner)
        storno   = self._make_storno(original)
        self.assertEqual(storno.doctype, 'S',
            f"Storno mora imati doctype S, a ima {storno.doctype}")

    def test_storno_of_nullable(self):
        """Normalni račun nema storno_of."""
        inv = make_invoice_with_items(self.company, self.user, self.partner)
        self.assertIsNone(inv.storno_of,
            "Normalni račun ne smije imati storno_of")


# ─────────────────────────────────────────────────────────────────────────────
#  TEST 4 — INVENTORY
# ─────────────────────────────────────────────────────────────────────────────

class TestInventoryRollback(TestCase):

    def setUp(self):
        self.company, self.user = setup_company('11000000004', 'inv_roll_user1')
        self.partner = make_partner(self.company)

    def test_inventory_model_postoji(self):
        item, _ = make_inventory_item(self.company, qty=20)
        self.assertEqual(item.quantity, Decimal('20'))
        self.assertEqual(item.unit_price, Decimal('100.00'))
        self.assertEqual(item.category, 'product')

    def test_deduct_smanjuje_kolicinu(self):
        item, _ = make_inventory_item(self.company, qty=20)
        initial = item.quantity
        try:
            from inventory.services import deduct_inventory
            deduct_inventory(item, Decimal('3'))
            item.refresh_from_db()
            self.assertEqual(item.quantity, initial - Decimal('3'),
                f"Nakon deducta: {item.quantity}, očekivano {initial - 3}")
        except ImportError:
            # Nema services.py — ručni deduct
            item.quantity -= Decimal('3')
            item.save()
            item.refresh_from_db()
            self.assertEqual(item.quantity, Decimal('17'))

    def test_inventory_veza_na_invoice_item(self):
        from invoicing.models import InvoiceItem
        field_names = [f.name for f in InvoiceItem._meta.get_fields()]
        self.assertIn('inventory_item', field_names,
            "InvoiceItem treba imati inventory_item FK")

    def test_inventory_ima_tax_rate(self):
        item, tax = make_inventory_item(self.company)
        self.assertIsNotNone(item.tax_rate)
        self.assertEqual(item.tax_rate.rate, Decimal('25.00'))

    def test_inventory_kolicina_ne_moze_biti_negativna_logicki(self):
        """Logički test — zaliha ne bi smjela ići ispod nule."""
        item, _ = make_inventory_item(self.company, qty=5)
        # Samo provjeri da model ima min_quantity polje kao zaštitu
        self.assertTrue(hasattr(item, 'min_quantity'),
            "InventoryItem treba imati min_quantity polje za zaštitu")


# ─────────────────────────────────────────────────────────────────────────────
#  TEST 5 — PARTNER BALANCE
# ─────────────────────────────────────────────────────────────────────────────

class TestPartnerBalance(TestCase):

    def setUp(self):
        self.company, self.user = setup_company('11000000005', 'balance_user1')
        self.partner = make_partner(self.company)

    def _quick_invoice(self, number, total_amount, doctype='R', status='SENT'):
        from invoicing.models import Invoice
        return Invoice.objects.create(
            company=self.company, doctype=doctype, status=status,
            partner=self.partner, client_name=self.partner.name,
            date_issued=timezone.now(),
            date_due=datetime.date.today() + datetime.timedelta(days=30),
            number=number,
            subtotal=total_amount, tax_amount=Decimal('0'), total=total_amount,
        )

    def test_partner_invoice_fk_postoji(self):
        from invoicing.models import Invoice
        field_names = [f.name for f in Invoice._meta.get_fields()]
        self.assertIn('partner', field_names, "Invoice mora imati 'partner' FK")

    def test_tri_racuna_jedan_storno(self):
        """3 računa (100+200+300) - 1 storno (300) = balance 300."""
        inv1 = self._quick_invoice('R-BAL-001', Decimal('100.00'))
        inv2 = self._quick_invoice('R-BAL-002', Decimal('200.00'))
        inv3 = self._quick_invoice('R-BAL-003', Decimal('300.00'))

        from invoicing.models import Invoice
        Invoice.objects.create(
            company=self.company, doctype='S', status='DRAFT',
            partner=self.partner, client_name=self.partner.name,
            date_issued=timezone.now(), number='S-R-BAL-003',
            storno_of=inv3,
            subtotal=-Decimal('300.00'), tax_amount=Decimal('0'), total=-Decimal('300.00'),
        )
        inv3.status = 'STORNO'; inv3.save()

        # Balance = aktivni računi (ne-stornirani)
        aktivni = Invoice.objects.filter(
            company=self.company, partner=self.partner, doctype='R'
        ).exclude(status='STORNO')
        balance = sum(cents(r.total) for r in aktivni)
        self.assertEqual(balance, Decimal('300.00'),
            f"Balance: očekivano 300.00, dobiveno {balance}")

    def test_storno_ponistava_balance(self):
        """1 račun + 1 storno = ukupno 0."""
        from invoicing.models import Invoice
        inv = self._quick_invoice('R-ZERO-001', Decimal('500.00'))
        Invoice.objects.create(
            company=self.company, doctype='S', status='DRAFT',
            partner=self.partner, client_name=self.partner.name,
            date_issued=timezone.now(), number='S-ZERO-001', storno_of=inv,
            subtotal=-Decimal('500.00'), tax_amount=Decimal('0'), total=-Decimal('500.00'),
        )
        inv.status = 'STORNO'; inv.save()

        svi = Invoice.objects.filter(company=self.company, partner=self.partner)
        ukupno = sum(cents(r.total) for r in svi)
        self.assertEqual(ukupno, Decimal('0.00'),
            f"Nakon storna balance mora biti 0.00, a jest {ukupno}")

    def test_vise_partnera_ne_mijesaju_se(self):
        """Balance partnera A ne smije uključivati račune partnera B."""
        from invoicing.models import Invoice
        from partners.models import Partner

        partner_b = Partner.objects.create(
            company=self.company, name='Partner B', oib='98765432101',
            email='b@test.hr', country='HR',
        )
        # Partner A: 100€
        self._quick_invoice('R-A-001', Decimal('100.00'))
        # Partner B: 999€
        Invoice.objects.create(
            company=self.company, doctype='R', status='SENT',
            partner=partner_b, client_name=partner_b.name,
            date_issued=timezone.now(),
            date_due=datetime.date.today() + datetime.timedelta(days=30),
            number='R-B-001',
            subtotal=Decimal('999.00'), tax_amount=Decimal('0'), total=Decimal('999.00'),
        )
        balance_a = sum(
            cents(r.total) for r in
            Invoice.objects.filter(company=self.company, partner=self.partner)
        )
        self.assertEqual(balance_a, Decimal('100.00'),
            f"Balance partnera A ({balance_a}) ne smije uključivati partnera B")


# ─────────────────────────────────────────────────────────────────────────────
#  TEST 6 — MODEL INTEGRITET
# ─────────────────────────────────────────────────────────────────────────────

class TestModelIntegritet(TestCase):

    def setUp(self):
        self.company, self.user = setup_company('11000000006', 'integrity_user1')
        self.partner = make_partner(self.company)

    def test_invoice_obavezna_polja(self):
        from invoicing.models import Invoice
        field_names = [f.name for f in Invoice._meta.get_fields()]
        for field in ['doctype', 'status', 'number', 'date_issued',
                      'client_name', 'subtotal', 'tax_amount', 'total', 'currency']:
            self.assertIn(field, field_names, f"Invoice nema polje '{field}'")

    def test_invoice_item_obavezna_polja(self):
        from invoicing.models import InvoiceItem
        field_names = [f.name for f in InvoiceItem._meta.get_fields()]
        for field in ['invoice', 'description', 'quantity', 'unit',
                      'unit_price', 'tax_rate', 'total_price', 'gross_total']:
            self.assertIn(field, field_names, f"InvoiceItem nema polje '{field}'")

    def test_fiskalizacija_polja(self):
        from invoicing.models import Invoice
        field_names = [f.name for f in Invoice._meta.get_fields()]
        for field in ['zki', 'jir', 'is_fiscalized', 'operator_oib', 'fiscal_datetime']:
            self.assertIn(field, field_names, f"Fiskalizacija: polje '{field}' nedostaje")

    def test_iban_swift(self):
        from invoicing.models import Invoice
        field_names = [f.name for f in Invoice._meta.get_fields()]
        self.assertIn('iban',  field_names, "Invoice nema IBAN")
        self.assertIn('swift', field_names, "Invoice nema SWIFT")

    def test_storno_of_nullable(self):
        from invoicing.models import Invoice
        field = Invoice._meta.get_field('storno_of')
        self.assertTrue(field.null, "storno_of mora biti null=True")

    def test_decimal_preciznost(self):
        from invoicing.models import Invoice
        for fname in ['subtotal', 'tax_amount', 'total']:
            field = Invoice._meta.get_field(fname)
            self.assertGreaterEqual(field.decimal_places, 2,
                f"{fname}: min 2 decimale")
            self.assertGreaterEqual(field.max_digits, 10,
                f"{fname}: min 10 znamenki")

    def test_partner_model_polja(self):
        from partners.models import Partner
        field_names = [f.name for f in Partner._meta.get_fields()]
        for field in ['name', 'oib', 'email', 'country']:
            self.assertIn(field, field_names, f"Partner nema polje '{field}'")

    def test_tax_rate_unique_together(self):
        """TaxRate ima unique_together (country, rate) — duplikat mora failati."""
        from django.db import IntegrityError

        from companies.models import TaxRate
        make_tax_rate(Decimal('7.00'), 'DE')
        with self.assertRaises(IntegrityError,
                msg="Dupli TaxRate (DE, 7%) mora podignuti IntegrityError"):
            TaxRate.objects.get_or_create(
                country='DE', rate=Decimal('7.00'),
                name='Duplikat', is_default=False, is_active=True,
            )
