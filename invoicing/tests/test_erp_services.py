"""
LIMIT Connect ERP — Service Layer Test Suite (faza 2)
======================================================
Pokriva poslovnu logiku u invoicing/services/invoice_service.py:

  1. Invoice.recalculate()       — matematika iz baze stavki
  2. ensure_partner()            — auto-kreacija partnera iz računa
  3. save_items()                — parsiranje POST podataka (zarezi, prazne stavke)
  4. deduct_inventory()          — StockMovement pri PAID statusu
  5. copy_invoice()              — deep copy + integritet stavki
  6. copy_invoice_items()        — kopiranje stavki između dokumenata
  7. mark_worktime_billed()      — TimeEntry.is_billed flag
  8. effective_iban/swift        — property fallback logika
  9. generate_invoice_number()   — format i jedinstvenost
 10. Recalculate nakon izmjene   — live rekalkulacija stavki
"""

import datetime
from decimal import Decimal, ROUND_HALF_UP

from django.test import TestCase, RequestFactory
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import IntegrityError, DatabaseError

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
#  SHARED HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def make_company(oib, name=None):
    from companies.models import Company
    return Company.objects.create(name=name or f'Firma {oib}', oib=oib, country='HR')


def make_user(username, company):
    from accounts.models import UserProfile
    from registration.models import CompanySubscription
    user = User.objects.create_user(username, password='test1234')
    try:
        p = user.profile
        p.company = company
        p.save()
    except (IntegrityError, DatabaseError):
        UserProfile.objects.create(user=user, company=company)
    CompanySubscription.objects.create(
        company=company, plan='pro',
        valid_from=datetime.date.today(), monthly_fee=0,
        is_active=True, billing_cycle='monthly',
        modules_override=['invoicing', 'partners', 'inventory', 'worktime'],
    )
    return user


def make_invoice(company, user, doctype='R', status='DRAFT', **kwargs):
    from invoicing.models import Invoice
    defaults = dict(
        company=company, created_by=user,
        doctype=doctype, status=status,
        client_name='Test Klijent d.o.o.',
        client_oib='22222222222',
        client_address='Testna 1', client_city='10000 Zagreb',
        client_country='Hrvatska',
        date_issued=timezone.now(),
        date_due=datetime.date.today() + datetime.timedelta(days=30),
        payment_method='TRANSAKCIJSKI', currency='EUR',
        number=f'{doctype}-SVC-{Invoice.objects.count()+1:04d}',
        subtotal=Decimal('0'), tax_amount=Decimal('0'), total=Decimal('0'),
        issuer_name='Test Firma', issuer_oib='33333333333',
        country='HR',
    )
    defaults.update(kwargs)
    return Invoice.objects.create(**defaults)


def add_item(invoice, desc='Testna stavka', qty=1, price=100, pdv=25, disc=0):
    from invoicing.models import InvoiceItem
    from decimal import Decimal
    q = Decimal(str(qty))
    p = Decimal(str(price))
    d = Decimal(str(disc))
    base = (q * p * (1 - d / 100)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    tax  = (base * Decimal(str(pdv)) / 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return InvoiceItem.objects.create(
        invoice=invoice, description=desc,
        quantity=q, unit='kom', unit_price=p,
        tax_rate=Decimal(str(pdv)), discount_percent=d,
        total_price=base, gross_total=base + tax,
    )


def make_inventory_item(company, qty=10, price=Decimal('50.00')):
    from inventory.models import InventoryItem
    from companies.models import TaxRate
    tax, _ = TaxRate.objects.get_or_create(
        country='HR', rate=Decimal('25.00'),
        defaults={'name': 'PDV 25%', 'is_default': True, 'is_active': True}
    )
    return InventoryItem.objects.create(
        company=company, name='Artikl za test',
        sku=f'SKU-{InventoryItem.objects.count()+1}',
        unit='kom', unit_price=price, quantity=Decimal(str(qty)),
        tax_rate=tax, is_active=True, category='product',
    )


def cents(d):
    return Decimal(str(d)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


# ─────────────────────────────────────────────────────────────────────────────
#  1. Invoice.recalculate()
# ─────────────────────────────────────────────────────────────────────────────

class TestRecalculate(TestCase):
    """
    recalculate() mora zbrojiti stavke iz baze i ažurirati
    subtotal, tax_amount i total na Invoice instanci.
    """

    def setUp(self):
        self.company = make_company('21000000001')
        self.user    = make_user('recalc_user1', self.company)

    def test_recalculate_prazno(self):
        inv = make_invoice(self.company, self.user)
        inv.recalculate()
        self.assertEqual(cents(inv.subtotal),   Decimal('0.00'))
        self.assertEqual(cents(inv.tax_amount),  Decimal('0.00'))
        self.assertEqual(cents(inv.total),       Decimal('0.00'))

    def test_recalculate_jedna_stavka(self):
        inv = make_invoice(self.company, self.user)
        add_item(inv, qty=2, price=100, pdv=25)   # 200 + 50 PDV = 250
        inv.recalculate()
        self.assertEqual(cents(inv.subtotal),   Decimal('200.00'))
        self.assertEqual(cents(inv.tax_amount),  Decimal('50.00'))
        self.assertEqual(cents(inv.total),       Decimal('250.00'))

    def test_recalculate_mixed_pdv(self):
        inv = make_invoice(self.company, self.user)
        add_item(inv, qty=1, price=100, pdv=25)   # 100 + 25 = 125
        add_item(inv, qty=1, price=100, pdv=13)   # 100 + 13 = 113
        add_item(inv, qty=1, price=100, pdv=5)    # 100 +  5 = 105
        inv.recalculate()
        self.assertEqual(cents(inv.subtotal),   Decimal('300.00'))
        self.assertEqual(cents(inv.tax_amount),  Decimal('43.00'))
        self.assertEqual(cents(inv.total),       Decimal('343.00'))

    def test_recalculate_s_popustom(self):
        inv = make_invoice(self.company, self.user)
        add_item(inv, qty=1, price=200, pdv=25, disc=10)  # 180 + 45 = 225
        inv.recalculate()
        self.assertEqual(cents(inv.subtotal),  Decimal('180.00'))
        self.assertEqual(cents(inv.tax_amount), Decimal('45.00'))
        self.assertEqual(cents(inv.total),      Decimal('225.00'))

    def test_recalculate_vraca_self(self):
        """recalculate() mora vrati self za chain pattern."""
        inv = make_invoice(self.company, self.user)
        result = inv.recalculate()
        self.assertIs(result, inv, "recalculate() mora vrati self")

    def test_recalculate_nakon_brisanja_stavke(self):
        inv = make_invoice(self.company, self.user)
        item = add_item(inv, qty=1, price=100, pdv=25)
        inv.recalculate(); inv.save()
        self.assertEqual(cents(inv.total), Decimal('125.00'))

        item.delete()
        inv.recalculate(); inv.save()
        inv.refresh_from_db()
        self.assertEqual(cents(inv.total), Decimal('0.00'),
            "Nakon brisanja stavke recalculate mora resetirati na 0")

    def test_recalculate_de_pdv_19(self):
        """Njemački PDV 19%."""
        inv = make_invoice(self.company, self.user, country='DE')
        add_item(inv, qty=1, price=100, pdv=19)  # 100 + 19 = 119
        inv.recalculate()
        self.assertEqual(cents(inv.tax_amount), Decimal('19.00'))
        self.assertEqual(cents(inv.total),      Decimal('119.00'))


# ─────────────────────────────────────────────────────────────────────────────
#  2. ensure_partner()
# ─────────────────────────────────────────────────────────────────────────────

class TestEnsurePartner(TestCase):
    """
    ensure_partner() auto-kreira partnera iz client podataka na računu.
    Ako partner s istim OIB-om već postoji, ne smije kreirati duplikat.
    """

    def setUp(self):
        self.company = make_company('21000000002')
        self.user    = make_user('epartner_user1', self.company)

    def test_kreira_partnera_iz_racuna(self):
        from partners.models import Partner
        from invoicing.services.invoice_service import ensure_partner

        inv = make_invoice(self.company, self.user,
            client_name='Novi Partner d.o.o.',
            client_oib='55555555555',
            client_email='novi@test.hr',
        )
        before = Partner.objects.filter(company=self.company, oib='55555555555').count()
        self.assertEqual(before, 0, "Partner ne smije postojati prije poziva")

        ensure_partner(self.company, inv)

        after = Partner.objects.filter(company=self.company, oib='55555555555').count()
        self.assertEqual(after, 1, "ensure_partner mora kreirati 1 partnera")

    def test_nema_duplikata(self):
        from partners.models import Partner
        from invoicing.services.invoice_service import ensure_partner

        inv = make_invoice(self.company, self.user,
            client_name='Postojeći Partner', client_oib='66666666666',
        )
        ensure_partner(self.company, inv)
        ensure_partner(self.company, inv)  # drugi poziv
        ensure_partner(self.company, inv)  # treći poziv

        count = Partner.objects.filter(company=self.company, oib='66666666666').count()
        self.assertEqual(count, 1, f"Mora biti 1 partner, a ima {count}")

    def test_bez_oib_koristi_ime(self):
        from partners.models import Partner
        from invoicing.services.invoice_service import ensure_partner

        inv = make_invoice(self.company, self.user,
            client_name='Firma Bez OIB-a', client_oib='',
        )
        ensure_partner(self.company, inv)
        count = Partner.objects.filter(company=self.company, name='Firma Bez OIB-a').count()
        self.assertGreaterEqual(count, 1, "Mora kreirati partnera i bez OIB-a")

    def test_prazno_ime_nista_ne_kreira(self):
        from partners.models import Partner
        from invoicing.services.invoice_service import ensure_partner

        inv = make_invoice(self.company, self.user, client_name='', client_oib='')
        before = Partner.objects.filter(company=self.company).count()
        ensure_partner(self.company, inv)
        after  = Partner.objects.filter(company=self.company).count()
        self.assertEqual(before, after, "Prazan client_name ne smije kreirati partnera")

    def test_partner_ima_email_s_racuna(self):
        from partners.models import Partner
        from invoicing.services.invoice_service import ensure_partner

        inv = make_invoice(self.company, self.user,
            client_name='Email Partner', client_oib='77777777777',
            client_email='email@firma.hr',
        )
        ensure_partner(self.company, inv)
        partner = Partner.objects.filter(company=self.company, oib='77777777777').first()
        self.assertIsNotNone(partner)
        self.assertEqual(partner.email, 'email@firma.hr')


# ─────────────────────────────────────────────────────────────────────────────
#  3. save_items() — parsiranje POST podataka
# ─────────────────────────────────────────────────────────────────────────────

class TestSaveItems(TestCase):
    """
    save_items() parsira POST array podatke u InvoiceItem objekte.
    Kritični edge caseovi: zarezi kao decimalni separator, prazni opisi.
    """

    def setUp(self):
        self.company = make_company('21000000003')
        self.user    = make_user('saveitems_user1', self.company)

    def _post(self, data):
        """Simulira Django QueryDict s listama."""
        from django.http import QueryDict
        qd = QueryDict(mutable=True)
        for key, values in data.items():
            qd.setlist(key, values if isinstance(values, list) else [values])
        return qd

    def test_osnovna_stavka(self):
        from invoicing.services.invoice_service import save_items
        from invoicing.models import InvoiceItem

        inv = make_invoice(self.company, self.user)
        post = self._post({
            'item_desc[]':  ['Usluga X'],
            'item_qty[]':   ['2'],
            'item_unit[]':  ['h'],
            'item_price[]': ['50.00'],
            'item_pdv[]':   ['25'],
            'item_disc[]':  ['0'],
        })
        save_items(inv, post)
        items = list(inv.items.all())
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].description, 'Usluga X')
        self.assertEqual(cents(items[0].quantity),  Decimal('2.00'))
        self.assertEqual(cents(items[0].unit_price), Decimal('50.00'))
        self.assertEqual(cents(items[0].total_price), Decimal('100.00'))

    def test_decimalni_zarez_kao_separator(self):
        """Europski format: '1,5' mora se parsirati kao 1.5"""
        from invoicing.services.invoice_service import save_items

        inv = make_invoice(self.company, self.user)
        post = self._post({
            'item_desc[]':  ['Artikl s zarezom'],
            'item_qty[]':   ['1,5'],
            'item_unit[]':  ['kom'],
            'item_price[]': ['10,00'],
            'item_pdv[]':   ['25'],
            'item_disc[]':  ['0'],
        })
        save_items(inv, post)
        items = list(inv.items.all())
        self.assertEqual(len(items), 1, "Mora parsirati stavku s decimalnim zarezom")
        self.assertEqual(cents(items[0].quantity),   Decimal('1.50'))
        self.assertEqual(cents(items[0].unit_price),  Decimal('10.00'))
        self.assertEqual(cents(items[0].total_price), Decimal('15.00'))

    def test_prazni_opisi_se_preskace(self):
        """Stavke s praznim opisom se ignoriraju."""
        from invoicing.services.invoice_service import save_items

        inv = make_invoice(self.company, self.user)
        post = self._post({
            'item_desc[]':  ['Prava stavka', '', '   '],
            'item_qty[]':   ['1', '1', '1'],
            'item_unit[]':  ['kom', 'kom', 'kom'],
            'item_price[]': ['100', '200', '300'],
            'item_pdv[]':   ['25', '25', '25'],
            'item_disc[]':  ['0', '0', '0'],
        })
        save_items(inv, post)
        self.assertEqual(inv.items.count(), 1,
            "Samo stavke s opisom se spremi")

    def test_vise_stavki(self):
        from invoicing.services.invoice_service import save_items

        inv = make_invoice(self.company, self.user)
        post = self._post({
            'item_desc[]':  ['Stavka A', 'Stavka B', 'Stavka C'],
            'item_qty[]':   ['1', '2', '3'],
            'item_unit[]':  ['kom', 'h', 'm2'],
            'item_price[]': ['100', '50', '30'],
            'item_pdv[]':   ['25', '13', '5'],
            'item_disc[]':  ['0', '0', '0'],
        })
        save_items(inv, post)
        self.assertEqual(inv.items.count(), 3)

    def test_save_items_brise_stare(self):
        """save_items mora obrisati stare stavke i kreirati nove."""
        from invoicing.services.invoice_service import save_items

        inv = make_invoice(self.company, self.user)
        add_item(inv, 'Stara stavka 1')
        add_item(inv, 'Stara stavka 2')
        self.assertEqual(inv.items.count(), 2)

        post = self._post({
            'item_desc[]':  ['Nova stavka'],
            'item_qty[]':   ['1'],
            'item_unit[]':  ['kom'],
            'item_price[]': ['99'],
            'item_pdv[]':   ['25'],
            'item_disc[]':  ['0'],
        })
        save_items(inv, post)
        items = list(inv.items.all())
        self.assertEqual(len(items), 1, "Stare stavke moraju biti obrisane")
        self.assertEqual(items[0].description, 'Nova stavka')

    def test_popust_u_stavki(self):
        """10% popust mora smanjiti total_price."""
        from invoicing.services.invoice_service import save_items

        inv = make_invoice(self.company, self.user)
        post = self._post({
            'item_desc[]':  ['S popustom'],
            'item_qty[]':   ['1'],
            'item_unit[]':  ['kom'],
            'item_price[]': ['100'],
            'item_pdv[]':   ['25'],
            'item_disc[]':  ['10'],
        })
        save_items(inv, post)
        item = inv.items.first()
        self.assertIsNotNone(item)
        self.assertEqual(cents(item.total_price), Decimal('90.00'),
            f"S 10% popustom na 100€: total mora biti 90.00, a jest {item.total_price}")


# ─────────────────────────────────────────────────────────────────────────────
#  4. deduct_inventory()
# ─────────────────────────────────────────────────────────────────────────────

class TestDeductInventory(TestCase):
    """
    deduct_inventory() mora kreirati StockMovement 'out' pri prvoj promjeni
    statusa na PAID. Ne smije se pozivati dvaput za isti račun.
    """

    def setUp(self):
        self.company = make_company('21000000004')
        self.user    = make_user('deduct_user1', self.company)

    def test_paid_kreira_stock_movement(self):
        from inventory.models import StockMovement
        from invoicing.services.invoice_service import deduct_inventory

        art = make_inventory_item(self.company, qty=10)
        inv = make_invoice(self.company, self.user, status='PAID')
        item = add_item(inv, qty=3, price=50, pdv=25)
        item.inventory_item = art
        item.save()

        before = StockMovement.objects.filter(
            item=art, movement_type='out').count()

        deduct_inventory(inv, old_status='SENT', user=self.user)

        after = StockMovement.objects.filter(
            item=art, movement_type='out').count()
        self.assertEqual(after, before + 1,
            "Mora biti kreiran 1 StockMovement 'out' pri plaćanju")

    def test_stock_movement_veza_na_racun(self):
        """StockMovement mora imati vezu na račun."""
        from inventory.models import StockMovement
        from invoicing.services.invoice_service import deduct_inventory

        art = make_inventory_item(self.company, qty=20)
        inv = make_invoice(self.company, self.user, status='PAID')
        item = add_item(inv, qty=2, price=100, pdv=25)
        item.inventory_item = art
        item.save()

        deduct_inventory(inv, old_status='ACCEPTED', user=self.user)

        movement = StockMovement.objects.filter(item=art, invoice=inv).first()
        self.assertIsNotNone(movement,
            "StockMovement mora biti vezan na račun (invoice FK)")
        self.assertEqual(movement.movement_type, 'out')
        self.assertEqual(cents(movement.quantity), Decimal('2.00'))

    def test_bez_inventory_stavke_nema_movementa(self):
        """Stavka bez inventory_item ne smije kreirati StockMovement."""
        from inventory.models import StockMovement
        from invoicing.services.invoice_service import deduct_inventory

        inv = make_invoice(self.company, self.user, status='PAID')
        add_item(inv, qty=5, price=10, pdv=25)  # bez inventory_item

        before = StockMovement.objects.count()
        deduct_inventory(inv, old_status='SENT', user=self.user)
        after = StockMovement.objects.count()

        self.assertEqual(before, after,
            "Stavka bez inventory_item ne smije kreirati StockMovement")

    def test_ne_deducta_vec_placeeni(self):
        """Ako je old_status već PAID, ne smije deductati opet."""
        from inventory.models import StockMovement
        from invoicing.services.invoice_service import deduct_inventory

        art = make_inventory_item(self.company, qty=50)
        inv = make_invoice(self.company, self.user, status='PAID')
        item = add_item(inv, qty=1, price=100, pdv=25)
        item.inventory_item = art
        item.save()

        before = StockMovement.objects.filter(item=art).count()
        # old_status == PAID — ne smije deductati
        deduct_inventory(inv, old_status='PAID', user=self.user)
        after = StockMovement.objects.filter(item=art).count()

        self.assertEqual(before, after,
            "old_status=PAID ne smije triggerirati novi deduct")

    def test_ne_deducta_ako_nije_paid(self):
        """Status SENT, DRAFT, itd. ne smiju triggerirati deduct."""
        from inventory.models import StockMovement
        from invoicing.services.invoice_service import deduct_inventory

        art = make_inventory_item(self.company, qty=30)
        for status in ['DRAFT', 'SENT', 'ACCEPTED']:
            inv = make_invoice(self.company, self.user, status=status)
            item = add_item(inv, qty=1, price=100, pdv=25)
            item.inventory_item = art
            item.save()
            before = StockMovement.objects.filter(item=art).count()
            deduct_inventory(inv, old_status='DRAFT', user=self.user)
            after = StockMovement.objects.filter(item=art).count()
            self.assertEqual(before, after,
                f"Status {status} ne smije kreirati StockMovement")


# ─────────────────────────────────────────────────────────────────────────────
#  5. copy_invoice()
# ─────────────────────────────────────────────────────────────────────────────

class TestCopyInvoice(TestCase):
    """
    copy_invoice() mora napraviti deep copy s novim brojem i doctypom.
    Stavke se kopiraju, fiskalni podaci se brišu, status je DRAFT.
    """

    def setUp(self):
        self.company = make_company('21000000005')
        self.user    = make_user('copy_user1', self.company)

    def test_kopija_je_draft(self):
        from invoicing.services.invoice_service import copy_invoice
        source = make_invoice(self.company, self.user, status='PAID')
        nova   = copy_invoice(source, 'R', 'R-COPY-001')
        self.assertEqual(nova.status, 'DRAFT',
            f"Kopija mora biti DRAFT, a jest {nova.status}")

    def test_kopija_ima_novi_doctype(self):
        from invoicing.services.invoice_service import copy_invoice
        source = make_invoice(self.company, self.user, doctype='PO')
        nova   = copy_invoice(source, 'R', 'R-FROM-PO-001')
        self.assertEqual(nova.doctype, 'R')

    def test_kopija_ima_novi_broj(self):
        from invoicing.services.invoice_service import copy_invoice
        source = make_invoice(self.company, self.user)
        nova   = copy_invoice(source, 'R', 'R-NOVI-BROJ-999')
        self.assertEqual(nova.number, 'R-NOVI-BROJ-999')
        self.assertNotEqual(nova.number, source.number)

    def test_kopija_razlicit_pk(self):
        from invoicing.services.invoice_service import copy_invoice
        source = make_invoice(self.company, self.user)
        nova   = copy_invoice(source, 'R', 'R-PK-TEST-001')
        self.assertNotEqual(nova.pk, source.pk,
            "Kopija mora imati novi pk")

    def test_fiskalni_podaci_su_ocisceni(self):
        """ZKI, JIR, is_fiscalized moraju biti prazni na kopiji."""
        from invoicing.services.invoice_service import copy_invoice
        source = make_invoice(self.company, self.user)
        source.zki = 'abc123'; source.jir = 'def456'
        source.is_fiscalized = True; source.save()

        nova = copy_invoice(source, 'R', 'R-FISCAL-CLEAR-001')
        self.assertFalse(nova.is_fiscalized,
            "Kopija ne smije biti fiskalizirana")
        self.assertEqual(nova.zki, '',
            f"ZKI mora biti prazan, a jest: '{nova.zki}'")
        self.assertEqual(nova.jir, '',
            f"JIR mora biti prazan, a jest: '{nova.jir}'")

    def test_stavke_se_kopiraju(self):
        from invoicing.services.invoice_service import copy_invoice
        source = make_invoice(self.company, self.user)
        add_item(source, 'Stavka 1', qty=2, price=100, pdv=25)
        add_item(source, 'Stavka 2', qty=1, price=50,  pdv=13)

        nova = copy_invoice(source, 'P', 'P-COPY-ITEMS-001')
        self.assertEqual(nova.items.count(), 2,
            f"Kopija mora imati 2 stavke, a ima {nova.items.count()}")

    def test_stavke_su_neovisne(self):
        """Brisanje stavke na kopiji ne smije utjecati na original."""
        from invoicing.services.invoice_service import copy_invoice
        source = make_invoice(self.company, self.user)
        add_item(source, 'Original stavka', qty=1, price=100, pdv=25)

        nova = copy_invoice(source, 'R', 'R-INDEPENDENT-001')
        nova.items.all().delete()

        self.assertEqual(source.items.count(), 1,
            "Brisanje stavki na kopiji ne smije utjecati na original")

    def test_iznosi_se_kopiraju(self):
        from invoicing.services.invoice_service import copy_invoice
        source = make_invoice(self.company, self.user,
            subtotal=Decimal('280.00'),
            tax_amount=Decimal('58.00'),
            total=Decimal('338.00'))

        nova = copy_invoice(source, 'R', 'R-AMOUNTS-001')
        self.assertEqual(cents(nova.total), Decimal('338.00'),
            "Iznosi moraju biti isti na kopiji")

    def test_extra_fields(self):
        from invoicing.services.invoice_service import copy_invoice
        source = make_invoice(self.company, self.user)
        nova   = copy_invoice(source, 'R', 'R-EXTRA-001',
                              extra_fields={'note': 'Iz ponude PO-001'})
        self.assertEqual(nova.note, 'Iz ponude PO-001')

    def test_source_document_veza(self):
        """Kopija mora imati source_document vezu na original."""
        from invoicing.services.invoice_service import copy_invoice
        source = make_invoice(self.company, self.user)
        nova   = copy_invoice(source, 'R', 'R-SOURCE-001')
        self.assertEqual(nova.source_document_id, source.pk,
            "nova.source_document mora pokazivati na original")


# ─────────────────────────────────────────────────────────────────────────────
#  6. copy_invoice_items()
# ─────────────────────────────────────────────────────────────────────────────

class TestCopyInvoiceItems(TestCase):
    """
    copy_invoice_items() kopira stavke iz jednog računa u drugi.
    Iznosi se čuvaju, vezni pk-ovi se ne prenose.
    """

    def setUp(self):
        self.company = make_company('21000000006')
        self.user    = make_user('copyitems_user1', self.company)

    def test_kopiranje_stavki(self):
        from invoicing.services.invoice_service import copy_invoice_items
        source = make_invoice(self.company, self.user)
        target = make_invoice(self.company, self.user, number='R-TARGET-001')
        add_item(source, 'Stavka X', qty=2, price=50,  pdv=25)
        add_item(source, 'Stavka Y', qty=1, price=100, pdv=13)

        copy_invoice_items(source, target)

        self.assertEqual(target.items.count(), 2,
            "Target mora imati 2 stavke")

    def test_stavke_imaju_iste_iznose(self):
        from invoicing.services.invoice_service import copy_invoice_items
        source = make_invoice(self.company, self.user)
        target = make_invoice(self.company, self.user, number='R-AMOUNTS-002')
        add_item(source, 'Stavka Z', qty=3, price=33, pdv=25)  # 99.00 + 24.75 = 123.75

        copy_invoice_items(source, target)

        t_item = target.items.first()
        self.assertIsNotNone(t_item)
        self.assertEqual(cents(t_item.quantity),   Decimal('3.00'))
        self.assertEqual(cents(t_item.unit_price),  Decimal('33.00'))
        self.assertEqual(cents(t_item.total_price), Decimal('99.00'))


# ─────────────────────────────────────────────────────────────────────────────
#  7. mark_worktime_billed()
# ─────────────────────────────────────────────────────────────────────────────

class TestMarkWorktimeBilled(TestCase):
    """
    mark_worktime_billed() mora postaviti is_billed=True na
    navedenim TimeEntry zapisima i vezati ih na račun.
    """

    def setUp(self):
        self.company = make_company('21000000007')
        self.user    = make_user('worktime_user1', self.company)

    def _make_time_entry(self):
        from worktime.models import TimeEntry, Project
        project, _ = Project.objects.get_or_create(
            code='TEST-PRJ',
            defaults={
                'company': self.company,
                'name': 'Test Projekt',
                'status': 'ACTIVE',
                'hourly_rate': Decimal('50.00'),
            }
        )
        return TimeEntry.objects.create(
            company=self.company,
            user=self.user,
            project=project,
            date=datetime.date.today(),
            duration=Decimal('8.00'),
            description='Test rad',
            is_billed=False,
        )

    def test_oznacava_kao_billed(self):
        from invoicing.services.invoice_service import mark_worktime_billed

        entry = self._make_time_entry()
        inv   = make_invoice(self.company, self.user)

        mark_worktime_billed(inv, str(entry.id))

        entry.refresh_from_db()
        self.assertTrue(entry.is_billed,
            f"TimeEntry {entry.id} mora biti označen kao billed")

    def test_veza_na_racun(self):
        from invoicing.services.invoice_service import mark_worktime_billed

        entry = self._make_time_entry()
        inv   = make_invoice(self.company, self.user)

        mark_worktime_billed(inv, str(entry.id))

        entry.refresh_from_db()
        self.assertEqual(entry.invoice_id, inv.pk,
            "TimeEntry.invoice mora pokazivati na fakturirani račun")

    def test_vise_entry_istovremeno(self):
        from invoicing.services.invoice_service import mark_worktime_billed

        e1 = self._make_time_entry()
        e2 = self._make_time_entry()
        inv = make_invoice(self.company, self.user)

        mark_worktime_billed(inv, f'{e1.id},{e2.id}')

        e1.refresh_from_db(); e2.refresh_from_db()
        self.assertTrue(e1.is_billed, "e1 mora biti billed")
        self.assertTrue(e2.is_billed, "e2 mora biti billed")

    def test_prazni_string_ne_pada(self):
        """Prazan string ne smije podignuti iznimku."""
        from invoicing.services.invoice_service import mark_worktime_billed
        inv = make_invoice(self.company, self.user)
        try:
            mark_worktime_billed(inv, '')
            mark_worktime_billed(inv, None)
        except Exception as e:
            self.fail(f"mark_worktime_billed s praznim stringom podigla iznimku: {e}")

    def test_vec_billed_se_ne_duplicira(self):
        """Već billed entry ne smije promijeniti invoice vezu."""
        from invoicing.services.invoice_service import mark_worktime_billed

        inv1 = make_invoice(self.company, self.user, number='R-WB-001')
        inv2 = make_invoice(self.company, self.user, number='R-WB-002')
        entry = self._make_time_entry()

        mark_worktime_billed(inv1, str(entry.id))
        entry.refresh_from_db()
        self.assertEqual(entry.invoice_id, inv1.pk)

        # Drugi poziv s inv2 — već billed entry ne smije biti prevezan
        mark_worktime_billed(inv2, str(entry.id))
        entry.refresh_from_db()
        self.assertEqual(entry.invoice_id, inv1.pk,
            "Već billed entry ne smije biti prevezan na drugi račun")


# ─────────────────────────────────────────────────────────────────────────────
#  8. effective_iban / effective_swift — property fallback
# ─────────────────────────────────────────────────────────────────────────────

class TestEffectiveIbanSwift(TestCase):
    """
    effective_iban i effective_swift su property-ji koji vraćaju
    ispravni IBAN/SWIFT bez obzira koji je field popunjen (legacy/novi).
    """

    def setUp(self):
        self.company = make_company('21000000008')
        self.user    = make_user('iban_user1', self.company)

    def test_issuer_iban_ima_prednost(self):
        inv = make_invoice(self.company, self.user)
        inv.issuer_iban = 'HR1234'; inv.iban = 'HR9999'; inv.save()
        self.assertEqual(inv.effective_iban, 'HR1234',
            "issuer_iban mora imati prednost")

    def test_legacy_iban_fallback(self):
        inv = make_invoice(self.company, self.user)
        inv.issuer_iban = ''; inv.iban = 'HR_LEGACY'; inv.save()
        self.assertEqual(inv.effective_iban, 'HR_LEGACY',
            "Kad nema issuer_iban, koristiti legacy iban")

    def test_oba_prazna_vraca_prazan(self):
        inv = make_invoice(self.company, self.user)
        inv.issuer_iban = ''; inv.iban = ''; inv.save()
        self.assertEqual(inv.effective_iban, '',
            "Ako su oba prazna, effective_iban mora biti ''")

    def test_issuer_swift_prednost(self):
        inv = make_invoice(self.company, self.user)
        inv.issuer_swift = 'CROAHR22'; inv.swift = 'OLDSWIFT'; inv.save()
        self.assertEqual(inv.effective_swift, 'CROAHR22')

    def test_legacy_swift_fallback(self):
        inv = make_invoice(self.company, self.user)
        inv.issuer_swift = ''; inv.swift = 'LEGACYSWFT'; inv.save()
        self.assertEqual(inv.effective_swift, 'LEGACYSWFT')

    def test_oba_swift_prazna(self):
        inv = make_invoice(self.company, self.user)
        inv.issuer_swift = ''; inv.swift = ''; inv.save()
        self.assertEqual(inv.effective_swift, '')


# ─────────────────────────────────────────────────────────────────────────────
#  9. generate_invoice_number()
# ─────────────────────────────────────────────────────────────────────────────

class TestGenerateInvoiceNumber(TestCase):
    """
    Broj računa mora biti jedinstven, neprazan i u ispravnom formatu.
    """

    def setUp(self):
        self.company = make_company('21000000009')
        self.user    = make_user('gennr_user1', self.company)

    def test_broj_nije_prazan(self):
        from invoicing.services.invoice_service import generate_invoice_number
        from invoicing.models import Invoice
        inv = Invoice(company=self.company, doctype='R')
        generate_invoice_number(inv, None, 'R')
        self.assertTrue(inv.number, "Generirani broj ne smije biti prazan")
        self.assertNotEqual(inv.number.strip(), '')

    def test_razliciti_doctypes_razliciti_prefiksi(self):
        """Ponuda i račun ne bi trebali imati isti broj."""
        from invoicing.services.invoice_service import generate_invoice_number
        from invoicing.models import Invoice

        inv_r  = Invoice(company=self.company, doctype='R')
        inv_po = Invoice(company=self.company, doctype='PO')
        generate_invoice_number(inv_r,  None, 'R')
        generate_invoice_number(inv_po, None, 'PO')

        self.assertNotEqual(inv_r.number, inv_po.number,
            "Račun i ponuda ne smiju imati isti broj")

    def test_broj_sadrzi_godinu(self):
        """Broj računa mora sadržavati tekuću godinu."""
        from invoicing.services.invoice_service import generate_invoice_number
        from invoicing.models import Invoice

        inv = Invoice(company=self.company, doctype='R')
        generate_invoice_number(inv, None, 'R')
        current_year = str(datetime.date.today().year)
        self.assertIn(current_year, inv.number,
            f"Broj računa mora sadržavati godinu {current_year}: '{inv.number}'")

    def test_visestruki_pozivi_razliciti_brojevi(self):
        """Svaki poziv mora generirati drugačiji broj."""
        from invoicing.services.invoice_service import generate_invoice_number
        from invoicing.models import Invoice

        brojevi = set()
        for _ in range(5):
            inv = Invoice(company=self.company, doctype='R')
            generate_invoice_number(inv, None, 'R')
            # Spremi u bazu da counter radi ispravno
            inv.subtotal = Decimal('0'); inv.tax_amount = Decimal('0')
            inv.total = Decimal('0'); inv.date_issued = timezone.now()
            inv.client_name = 'Test'; inv.country = 'HR'
            inv.issuer_name = 'Firma'; inv.issuer_oib = '33333333333'
            inv.save()
            brojevi.add(inv.number)

        self.assertEqual(len(brojevi), 5,
            f"5 računa mora imati 5 različitih brojeva, a imaju: {brojevi}")


# ─────────────────────────────────────────────────────────────────────────────
#  10. Integracijski test — recalculate + save
# ─────────────────────────────────────────────────────────────────────────────

class TestRecalculateIntegracija(TestCase):
    """
    Provjeri da recalculate() + save() ispravno ažurira bazu,
    i da refresh_from_db() vraća ažurirane vrijednosti.
    """

    def setUp(self):
        self.company = make_company('21000000010')
        self.user    = make_user('rcalc_int_user1', self.company)

    def test_recalculate_save_refresh(self):
        inv = make_invoice(self.company, self.user)
        add_item(inv, qty=1, price=100, pdv=25)

        inv.recalculate()
        inv.save()
        inv.refresh_from_db()

        self.assertEqual(cents(inv.subtotal),   Decimal('100.00'))
        self.assertEqual(cents(inv.tax_amount),  Decimal('25.00'))
        self.assertEqual(cents(inv.total),       Decimal('125.00'))

    def test_dodavanje_stavke_azurira_total(self):
        inv = make_invoice(self.company, self.user)
        add_item(inv, qty=1, price=100, pdv=25)
        inv.recalculate(); inv.save()

        # Dodaj drugu stavku
        add_item(inv, qty=1, price=200, pdv=25)
        inv.recalculate(); inv.save()
        inv.refresh_from_db()

        self.assertEqual(cents(inv.subtotal), Decimal('300.00'),
            "Nakon dodavanja stavke subtotal mora biti 300.00")
        self.assertEqual(cents(inv.total),    Decimal('375.00'))

    def test_storno_recalculate(self):
        """Storno račun s negativnim stavkama mora imati negativne iznose."""
        from invoicing.models import InvoiceItem

        original = make_invoice(self.company, self.user,
            subtotal=Decimal('100'), tax_amount=Decimal('25'), total=Decimal('125'))
        add_item(original, qty=1, price=100, pdv=25)

        storno = make_invoice(self.company, self.user, doctype='S', number='S-RECALC-001')
        InvoiceItem.objects.create(
            invoice=storno, description='Storno stavka',
            quantity=Decimal('-1'), unit='kom', unit_price=Decimal('100.00'),
            tax_rate=Decimal('25'), discount_percent=Decimal('0'),
            total_price=Decimal('-100.00'), gross_total=Decimal('-125.00'),
        )
        storno.recalculate()

        self.assertEqual(cents(storno.subtotal),   Decimal('-100.00'))
        self.assertEqual(cents(storno.tax_amount),  Decimal('-25.00'))
        self.assertEqual(cents(storno.total),       Decimal('-125.00'))

    def test_nula_pdv_stavka(self):
        """Stavka s 0% PDV — tax_amount mora biti 0."""
        inv = make_invoice(self.company, self.user)
        add_item(inv, qty=1, price=500, pdv=0)
        inv.recalculate()
        self.assertEqual(cents(inv.tax_amount), Decimal('0.00'),
            "Stavka s PDV 0% ne smije generirati tax")
        self.assertEqual(cents(inv.total), Decimal('500.00'))
