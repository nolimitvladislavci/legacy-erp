"""
delivery/tests/test_b2b_portal.py
════════════════════════════════════════════════════════════════════════════════
B2B Klijentski Portal — Matrica Loma (Scenariji 8.1, 8.2, 8.3)

Testira tri sigurnosna zahtjeva prije izrade HTML/JS sučelja:

  8.1 Tenant Data Leak     — HTTP 404 (ne 403!) na tuđem resursu
  8.2 Legal Vault Premature — blokada forenzike dok je narudžba u tranzitu
  8.3 Bulk Export DDoS      — HTTP 413 za raspon > 31 dan

Pokretanje:
    manage.py test delivery.tests.test_b2b_portal --verbosity=2
"""

import datetime
import uuid
from decimal import Decimal

from django.test import SimpleTestCase, TestCase, override_settings

# ══════════════════════════════════════════════════════════════════════════════
# SCENARIJ 8.1 — Tenant Data Leak (Curenje podataka stanara)
#
# Kupac "Roma" (portal_token_A) pokuša pristupiti računu kupca "Napoli".
# Očekivanje: HTTP 404 (ne 403 — ne smijemo potvrditi da resurs postoji).
# ══════════════════════════════════════════════════════════════════════════════


@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=["*"])
class Test81_TenantDataLeak(TestCase):
    """8.1: Apsolutna izolacija stanara — 404 umjesto 403 na tuđem računu."""

    @classmethod
    def setUpTestData(cls):
        from companies.models import Company
        from invoicing.models import Invoice
        from partners.models import Partner

        # Hub firma (seller)
        cls.hub = Company.objects.create(name="Hub Grosmarkt", oib="11100000001")

        # Kupac Roma — ima vlastiti portal token
        cls.roma = Partner.objects.create(
            company=cls.hub,
            name="Restoran Roma",
            oib="11100000011",
            portal_token=uuid.uuid4(),
        )

        # Kupac Napoli — potpuno odvojen tenant
        cls.napoli = Partner.objects.create(
            company=cls.hub,
            name="Restoran Napoli",
            oib="11100000022",
            portal_token=uuid.uuid4(),
        )

        # Račun koji pripada NAPOLI-ju (ne Romi)
        cls.napoli_invoice = Invoice.objects.create(
            company=cls.hub,
            partner=cls.napoli,
            number="INV-NAPOLI-001",
            date_issued=datetime.date.today(),
            date_due=datetime.date.today() + datetime.timedelta(days=30),
            subtotal=Decimal("500.00"),
            tax_amount=Decimal("125.00"),
            total=Decimal("625.00"),
            status="SENT",
        )

    # ── Test 8.1a: Direktni URL napad ─────────────────────────────────────────

    def test_FAIL_roma_ne_smije_vidjeti_napoli_racun_direktnim_URL(self):
        """
        Roma pristupa /portal/{roma_token}/invoices/{napoli_pk}/ → mora biti 404.
        HTTP 403 bi napadaču otkrio da račun pod tim ID-jem postoji.
        """
        url = "/portal/%s/invoices/%d/" % (str(self.roma.portal_token), self.napoli_invoice.pk)
        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            404,
            "TENANT LEAK: Portal vratio %d umjesto 404 za tuđi račun! "
            "HTTP 403 otkriva postojanje resursa." % response.status_code,
        )
        print("  [PASS] 8.1a: Roma dobiva 404 za Napoli račun (ne 403)")

    # ── Test 8.1b: Manipulacija ID-em u querystringu ──────────────────────────

    def test_FAIL_qs_injection_na_tuđi_racun(self):
        """
        Roma pristupa /portal/{roma_token}/invoices/?pk={napoli_pk} → mora biti 404.
        """
        url = "/portal/%s/invoices/%d/" % (str(self.roma.portal_token), self.napoli_invoice.pk)
        response = self.client.get(url, {"partner_override": self.napoli.pk})

        self.assertEqual(response.status_code, 404, "TENANT LEAK via QS: Dobiven %d umjesto 404" % response.status_code)
        print("  [PASS] 8.1b: QS injection ne propušta tuđe podatke")

    # ── Test 8.1c: Vlastiti račun mora biti dostupan ──────────────────────────

    def test_PASS_roma_vidi_vlastiti_racun(self):
        """
        Sanity check: Roma mora moći vidjeti vlastite račune.
        """
        from invoicing.models import Invoice

        roma_invoice = Invoice.objects.create(
            company=self.hub,
            partner=self.roma,
            number="INV-ROMA-001",
            date_issued=datetime.date.today(),
            date_due=datetime.date.today() + datetime.timedelta(days=30),
            subtotal=Decimal("300.00"),
            tax_amount=Decimal("75.00"),
            total=Decimal("375.00"),
            status="SENT",
        )

        url = "/portal/%s/invoices/%d/" % (str(self.roma.portal_token), roma_invoice.pk)
        response = self.client.get(url)

        self.assertIn(
            response.status_code,
            [200, 301, 302],
            "Roma ne može pristupiti vlastitom računu: HTTP %d" % response.status_code,
        )
        print("  [PASS] 8.1c: Roma normalno vidi vlastite račune (HTTP %d)" % response.status_code)

    # ── Test 8.1d: ORM razina — query ne smije vraćati tuđe zapise ───────────

    def test_FAIL_orm_queryset_izolacija(self):
        """
        Na razini ORM-a: Invoice.objects.filter(partner=roma) ne smije
        uključiti Napoli račune čak i ako se PK ručno ubaci u filter.
        """
        from invoicing.models import Invoice

        # Ovo je ono što portal view mora raditi — filter po partneru
        roma_invoices = Invoice.objects.filter(
            partner=self.roma,
            pk=self.napoli_invoice.pk,  # Pokušaj ubaciti Napoli PK
        )

        self.assertFalse(roma_invoices.exists(), "ORM LEAK: Napoli račun vidljiv kroz Roma queryset!")
        print("  [PASS] 8.1d: ORM queryset strogo izolira po partneru")


# ══════════════════════════════════════════════════════════════════════════════
# SCENARIJ 8.2 — Legal Vault Premature Access
#
# Kupac pokušava preuzeti Legal Vault ZIP za narudžbu koja je u tranzitu.
# Očekivanje: blokada s porukom o zatvorenom terenskom protokolu.
# ══════════════════════════════════════════════════════════════════════════════


class Test82_LegalVaultPrematureAccess(TestCase):
    """8.2: Forenzički materijal nije dostupan dok je narudžba u tranzitu."""

    @classmethod
    def setUpTestData(cls):
        from companies.models import Company
        from marketplace.models import MarketplaceOrder
        from partners.models import Partner

        cls.hub = Company.objects.create(name="Legal Vault Hub", oib="22200000001")
        cls.buyer_co = Company.objects.create(name="Legal Buyer Co", oib="22200000011")
        cls.partner = Partner.objects.create(
            company=cls.hub,
            name="OPG Testni",
            oib="22200000022",
            portal_token=uuid.uuid4(),
        )

        # Narudžba u tranzitu (vozač još nije dostavio)
        cls.order_in_transit = MarketplaceOrder.objects.create(
            buyer_company=cls.buyer_co,
            status="in_transit",  # ← ovo mora biti blokirano
        )

        # Narudžba koja je isporučena — Legal Vault smije biti dostupan
        cls.order_delivered = MarketplaceOrder.objects.create(
            buyer_company=cls.buyer_co,
            status="delivered",
        )

        # Narudžba koja je potvrđena (potpisana) — Legal Vault dostupan
        cls.order_confirmed = MarketplaceOrder.objects.create(
            buyer_company=cls.buyer_co,
            status="completed",
        )

    def _vault_accessible(self, order):
        """
        Centralna logika: Legal Vault je dostupan samo za završene narudžbe.
        Blokira se sve dok je terenski protokol otvoren (in_transit, confirmed,
        picking, packing itd.).
        """
        from partners.b2b_portal import check_legal_vault_access

        return check_legal_vault_access(order)

    # ── Test 8.2a: In_transit → mora biti blokiran ────────────────────────────

    def test_FAIL_vault_blokiran_za_in_transit(self):
        """
        Narudžba u tranzitu — Legal Vault mora biti blokiran.
        Terenski protokol nije zatvoren (potpisnica dostave nije primljena).
        """
        ok, err = self._vault_accessible(self.order_in_transit)
        self.assertFalse(ok, "VAULT LEAK: Legal Vault dostupan za narudzbu u tranzitu!")
        self.assertIn(
            "terenskog protokola",
            err.lower(),
            'Poruka greske mora spominjati "terenskog protokola". Dobiveno: %s' % err,
        )
        print('  [PASS] 8.2a: Vault blokiran za in_transit: "%s"' % err[:70])

    # ── Test 8.2b: Delivered → mora biti dostupan ─────────────────────────────

    def test_PASS_vault_dostupan_za_delivered(self):
        """
        Isporučena narudžba — Legal Vault mora biti dostupan.
        """
        ok, err = self._vault_accessible(self.order_delivered)
        self.assertTrue(ok, "VAULT ERROR: Legal Vault nedostupan za delivered narudzbu! Err: %s" % err)
        print("  [PASS] 8.2b: Vault dostupan za delivered narudzbu")

    # ── Test 8.2c: Completed → dostupan ──────────────────────────────────────

    def test_PASS_vault_dostupan_za_completed(self):
        ok, err = self._vault_accessible(self.order_confirmed)
        self.assertTrue(ok, "Vault nedostupan za completed: %s" % err)
        print("  [PASS] 8.2c: Vault dostupan za completed narudzbu")

    # ── Test 8.2d: Cijeli spektar statusa ─────────────────────────────────────

    def test_FAIL_spektar_blokiranih_statusa(self):
        """
        Svi statusi koji su "aktivni" (roba se fizički kreće) moraju biti blokirani.
        """
        from marketplace.models import MarketplaceOrder
        from partners.b2b_portal import check_legal_vault_access

        blocked_statuses = ["pending", "confirmed", "in_transit", "picking", "packing"]
        allowed_statuses = ["delivered", "completed", "cancelled"]

        for status in blocked_statuses:
            order = MarketplaceOrder(buyer_company=self.buyer_co, status=status)
            # Ne spremamo u DB — samo testiramo logiku
            ok, err = check_legal_vault_access(order)
            self.assertFalse(ok, 'VAULT LEAK za status "%s": trebalo biti blokirano!' % status)

        for status in allowed_statuses:
            order = MarketplaceOrder(buyer_company=self.buyer_co, status=status)
            ok, err = check_legal_vault_access(order)
            self.assertTrue(ok, 'VAULT BLOCKED za status "%s": trebalo biti dozvoljeno!' % status)

        print("  [PASS] 8.2d: Cijeli spektar statusa ispravno klasificiran")
        print("    Blokirano: %s" % blocked_statuses)
        print("    Dozvoljeno: %s" % allowed_statuses)


# ══════════════════════════════════════════════════════════════════════════════
# SCENARIJ 8.3 — Bulk Export DDoS kroz ZIP
#
# Zahtjev za ZIP paket koji obuhvaća > 31 dan mora biti odbijen
# s HTTP 413 Payload Too Large.
# ══════════════════════════════════════════════════════════════════════════════


class Test83_BulkExportDDoS(SimpleTestCase):
    """8.3: ZIP bulk export blokiran za raspon > 31 dan (anti-DDoS)."""

    def _validate_export_range(self, date_from, date_to):
        """
        Centralna validacija raspona. Vraća (ok, http_status, error_msg).
        Poziva partners.b2b_portal.validate_export_date_range().
        """
        from partners.b2b_portal import validate_export_date_range

        return validate_export_date_range(date_from, date_to)

    # ── Test 8.3a: 5 godina → HTTP 413 ───────────────────────────────────────

    def test_FAIL_5_godina_vraca_413(self):
        """
        Zahtjev za 5 godina računa mora biti odbijen s HTTP 413.
        """
        date_from = datetime.date(2020, 1, 1)
        date_to = datetime.date(2025, 1, 1)  # 1826 dana

        ok, status_code, err = self._validate_export_range(date_from, date_to)

        self.assertFalse(ok, "DDoS PROPUST: 5-godišnji export nije blokiran!")
        self.assertEqual(
            status_code, 413, "Pogrešan HTTP status: dobiven %d, očekivan 413 Payload Too Large" % status_code
        )
        print('  [PASS] 8.3a: 5-godišnji export vraća HTTP 413: "%s"' % err[:60])

    # ── Test 8.3b: Točno 31 dan → dopušteno ──────────────────────────────────

    def test_PASS_31_dan_dozvoljen(self):
        """
        Raspon od točno 31 dana je na granici — mora biti dopušten.
        """
        date_from = datetime.date(2025, 1, 1)
        date_to = datetime.date(2025, 2, 1)  # 31 dan

        ok, status_code, err = self._validate_export_range(date_from, date_to)

        self.assertTrue(ok, "EXPORT BLOKIRAN za 31 dan (granica): %s" % err)
        print("  [PASS] 8.3b: 31-dnevni export prolazi (granični slučaj)")

    # ── Test 8.3c: 32 dana → HTTP 413 ────────────────────────────────────────

    def test_FAIL_32_dana_vraca_413(self):
        """
        32 dana — jedan dan više od limita → mora biti blokiran.
        """
        date_from = datetime.date(2025, 1, 1)
        date_to = datetime.date(2025, 2, 2)  # 32 dana

        ok, status_code, err = self._validate_export_range(date_from, date_to)

        self.assertFalse(ok, "DDoS PROPUST: 32-dnevni export nije blokiran!")
        self.assertEqual(status_code, 413, "Pogrešan status za 32 dana: %d" % status_code)
        print("  [PASS] 8.3c: 32-dnevni export vraća HTTP 413")

    # ── Test 8.3d: Obrnuti raspon (date_from > date_to) → HTTP 400 ───────────

    def test_FAIL_obrnuti_raspon_vraca_400(self):
        """
        date_from > date_to je nevalidan unos → HTTP 400 Bad Request.
        """
        date_from = datetime.date(2025, 6, 1)
        date_to = datetime.date(2025, 1, 1)  # obrnuto

        ok, status_code, err = self._validate_export_range(date_from, date_to)

        self.assertFalse(ok, "Obrnuti raspon nije blokiran!")
        self.assertEqual(status_code, 400, "Obrnuti raspon mora vratiti 400, ne %d" % status_code)
        print("  [PASS] 8.3d: Obrnuti raspon vraća HTTP 400")

    # ── Test 8.3e: Jedan dan → dozvoljen ─────────────────────────────────────

    def test_PASS_jedan_dan_dozvoljen(self):
        """
        Najmanji mogući raspon (1 dan) mora raditi.
        """
        today = datetime.date.today()
        ok, status_code, err = self._validate_export_range(today, today)
        self.assertTrue(ok, "1-dnevni raspon nije dopušten: %s" % err)
        print("  [PASS] 8.3e: 1-dnevni raspon radi")

    # ── Test 8.3f: None datumi → HTTP 400 ────────────────────────────────────

    def test_FAIL_none_datumi_vraca_400(self):
        """
        Nedostajući datumi (None) → HTTP 400.
        """
        ok, status_code, err = self._validate_export_range(None, None)
        self.assertFalse(ok, "None datumi nisu odbijeni!")
        self.assertEqual(status_code, 400, "None datumi moraju vratiti 400, ne %d" % status_code)
        print("  [PASS] 8.3f: None datumi vraćaju HTTP 400")
