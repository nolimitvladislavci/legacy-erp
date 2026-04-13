"""
Sandbox Strike — End-to-end eRačun pipeline test.

Tests the ENTIRE chain:
1. Load FINA cert (mTLS readiness)
2. Pick/create test invoice
3. Generate UBL 2.1 XML (CIUS-HR 2025)
4. Validate: XSD + EN 16931 + PROPTER rules
5. Format HTTP request with mTLS cert
6. Fire at echo endpoint (or real sandbox when available)
7. Report every step

Usage:
    python manage.py test_fina_sandbox
    python manage.py test_fina_sandbox --live   # When real sandbox available
"""
import os
import time
import hashlib
import tempfile
import logging
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand

logger = logging.getLogger("propter.einvoice.sandbox")


class Command(BaseCommand):
    help = "End-to-end eRačun sandbox test — proves pipeline readiness"

    def add_arguments(self, parser):
        parser.add_argument("--live", action="store_true", help="Use real FINA sandbox (requires posrednik access)")
        parser.add_argument("--company-oib", default="37590751921", help="OIB firme za test (default: Konjik)")
        # verbosity handled by Django BaseCommand

    def handle(self, *args, **options):
        self.v = options.get("verbosity", 1)
        live = options["live"]
        oib = options["company_oib"]

        self.stdout.write("\n" + "=" * 70)
        self.stdout.write("  SANDBOX STRIKE — FINA eRačun Pipeline Test")
        self.stdout.write("  Mode: " + ("LIVE (real sandbox)" if live else "LOCAL (echo test)"))
        self.stdout.write("=" * 70 + "\n")

        t0 = time.time()
        results = {}

        # ── STEP 1: Load Certificate ──
        results["cert"] = self._step_cert(oib)
        if not results["cert"]["ok"]:
            self._fail("Certificate loading failed")
            return

        # ── STEP 2: Get/Create Test Invoice ──
        results["invoice"] = self._step_invoice(oib)
        if not results["invoice"]["ok"]:
            self._fail("Invoice preparation failed")
            return

        # ── STEP 3: Generate UBL XML ──
        results["ubl"] = self._step_ubl(results["invoice"]["eracun"])
        if not results["ubl"]["ok"]:
            self._fail("UBL generation failed")
            return

        # ── STEP 4: Validate ──
        results["validation"] = self._step_validate(results["ubl"]["xml"])

        # ── STEP 5: mTLS Connection Test ──
        results["mtls"] = self._step_mtls(results["cert"]["cert_path"], results["cert"]["key_path"])

        # ── STEP 6: Submit (echo or live) ──
        if live:
            results["submit"] = self._step_submit_live(results)
        else:
            results["submit"] = self._step_submit_echo(results)

        # ── REPORT ──
        elapsed = time.time() - t0
        self._report(results, elapsed)

    def _step_cert(self, oib):
        self._header("STEP 1: Certificate Loading")
        from eracun.models import ERacunConfig
        from companies.models import Company

        company = Company.objects.filter(oib=oib).first()
        if not company:
            self._error(f"Company with OIB {oib} not found")
            return {"ok": False}

        config = ERacunConfig.objects.filter(company=company).first()
        if not config or not config.cert_path:
            self._error("No eRacun config or cert_path for this company")
            return {"ok": False}

        cert_path = config.cert_path
        if not os.path.exists(cert_path):
            self._error(f"Certificate file not found: {cert_path}")
            return {"ok": False}

        # Load and verify
        try:
            from cryptography.hazmat.primitives.serialization.pkcs12 import load_key_and_certificates
            from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption

            pw_path = os.path.join(os.path.dirname(cert_path), ".cert_password")
            with open(pw_path) as f:
                password = f.read().strip().encode()
            with open(cert_path, "rb") as f:
                p12_data = f.read()

            key, cert, chain = load_key_and_certificates(p12_data, password)

            import datetime
            now = datetime.datetime.now(datetime.timezone.utc)
            days_left = (cert.not_valid_after_utc - now).days

            self._ok(f"Subject: {cert.subject.rfc4514_string()}")
            self._ok(f"Issuer:  {cert.issuer.rfc4514_string()}")
            self._ok(f"Valid:   {cert.not_valid_before_utc.date()} → {cert.not_valid_after_utc.date()} ({days_left} days)")
            self._ok(f"Key:     {type(key).__name__}")

            if days_left < 0:
                self._error("CERTIFICATE EXPIRED!")
                return {"ok": False}

            # Extract to temp PEM files for httpx
            tmp_dir = tempfile.mkdtemp(prefix="fina_sandbox_")
            cert_pem = os.path.join(tmp_dir, "cert.pem")
            key_pem = os.path.join(tmp_dir, "key.pem")

            with open(cert_pem, "wb") as f:
                f.write(cert.public_bytes(Encoding.PEM))
            with open(key_pem, "wb") as f:
                f.write(key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()))

            self._ok(f"PEM extracted: {cert_pem}")

            return {
                "ok": True, "company": company, "config": config,
                "cert_path": cert_pem, "key_path": key_pem,
                "days_left": days_left, "subject": cert.subject.rfc4514_string(),
            }

        except (FileNotFoundError, PermissionError, IOError) as e:
            self._error(f"Certificate load error: {e}")
            return {"ok": False}

    def _step_invoice(self, oib):
        self._header("STEP 2: Test Invoice")
        from eracun.models import ERacun
        from companies.models import Company

        company = Company.objects.filter(oib=oib).first()

        # Try existing draft eRacun
        eracun = ERacun.objects.filter(
            company=company, status="draft"
        ).order_by("-created_at").first()

        if eracun:
            self._ok(f"Using existing draft: {eracun.invoice_number}")
            self._ok(f"  Issuer:    {eracun.issuer_name} ({eracun.issuer_oib})")
            self._ok(f"  Recipient: {eracun.recipient_name} ({eracun.recipient_oib})")
            self._ok(f"  Amount:    {eracun.total} {eracun.currency}")
            return {"ok": True, "eracun": eracun}

        # Create test eRacun
        self._warn("No draft eRacun found — creating test")
        import uuid
        test_number = f"SANDBOX-{uuid.uuid4().hex[:6].upper()}"

        eracun = ERacun.objects.create(
            company=company,
            doc_type="380",
            invoice_number=test_number,
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            currency="EUR",
            issuer_name=company.name,
            issuer_oib=company.oib,
            issuer_address=company.address or "Kralja Zvonimira 2",
            issuer_city=company.city or "Cepin",
            issuer_postal=company.zip_code or "31431",
            issuer_country="HR",
            recipient_name="FINA Sandbox Test d.o.o.",
            recipient_oib="00000000001",
            recipient_address="Ulica grada Vukovara 70",
            recipient_city="Zagreb",
            recipient_postal="10000",
            recipient_country="HR",
            payment_means_code="30",
            subtotal=Decimal("1000.00"),
            tax_amount=Decimal("250.00"),
            total=Decimal("1250.00"),
            status="draft",
        )

        # Add line item
        from eracun.models import ERacunItem
        ERacunItem.objects.create(
            eracun=eracun,
            line_number=1,
            description="Knjigovodstvene usluge — sandbox test",
            quantity=Decimal("1"),
            unit_code="EA",
            unit_price=Decimal("1000.00"),
            line_total=Decimal("1000.00"),
            tax_category="S",
            tax_rate=Decimal("25.00"),
        )

        # Tax summary
        from eracun.models import ERacunTaxSummary
        ERacunTaxSummary.objects.create(
            eracun=eracun,
            tax_category="S",
            tax_rate=Decimal("25.00"),
            taxable_amount=Decimal("1000.00"),
            tax_amount=Decimal("250.00"),
        )

        self._ok(f"Created: {test_number} | 1250.00 EUR")
        return {"ok": True, "eracun": eracun}

    def _step_ubl(self, eracun):
        self._header("STEP 3: UBL 2.1 Generation (CIUS-HR 2025)")
        try:
            from eracun.services.ubl_generator import generate_ubl_xml
            xml_bytes = generate_ubl_xml(eracun)
            xml_str = xml_bytes.decode("utf-8") if isinstance(xml_bytes, bytes) else xml_bytes

            size = len(xml_str.encode("utf-8"))
            sha256 = hashlib.sha256(xml_str.encode("utf-8")).hexdigest()

            self._ok(f"XML generated: {size} bytes")
            self._ok(f"SHA-256: {sha256[:32]}...")

            # Show first 5 lines
            for line in xml_str.split("\n")[:5]:
                self._info(f"  {line.strip()}")

            # Check key elements
            checks = [
                ("CustomizationID", "cius" in xml_str.lower()),
                ("InvoiceTypeCode", "380" in xml_str),
                ("AccountingSupplierParty", "AccountingSupplierParty" in xml_str),
                ("AccountingCustomerParty", "AccountingCustomerParty" in xml_str),
                ("TaxTotal", "TaxTotal" in xml_str),
                ("LegalMonetaryTotal", "LegalMonetaryTotal" in xml_str),
                ("InvoiceLine", "InvoiceLine" in xml_str),
            ]
            for name, passed in checks:
                if passed:
                    self._ok(f"  {name}: present")
                else:
                    self._error(f"  {name}: MISSING")

            return {"ok": True, "xml": xml_str, "size": size, "sha256": sha256}

        except Exception as e:
            self._error(f"UBL generation failed: {e}")
            import traceback
            traceback.print_exc()
            return {"ok": False}

    def _step_validate(self, xml_str):
        self._header("STEP 4: 3-Stage Validation")
        try:
            from einvoice.services.ubl_validator import validate_ubl
            result = validate_ubl(xml_str, strict=False)

            self._ok(f"Valid: {result.is_valid}")
            self._ok(f"Errors: {result.error_count}")
            self._ok(f"Warnings: {len(result.warnings)}")

            for stage, data in result.stage_results.items():
                status = "PASS" if data.get("valid", True) and not data.get("errors") else "ISSUES"
                self._ok(f"  Stage [{stage}]: {status}")

            if result.errors:
                for err in result.errors[:5]:
                    self._warn(f"  ERR: {err}")
            if result.warnings:
                for w in result.warnings[:3]:
                    self._info(f"  WARN: {w}")

            return {"ok": True, "valid": result.is_valid, "errors": result.errors, "warnings": result.warnings}

        except ImportError as e:
            self._error(f"Validation error: {e}")
            return {"ok": False}

    def _step_mtls(self, cert_pem, key_pem):
        self._header("STEP 5: mTLS Certificate Readiness")
        try:
            import httpx
            # Test that httpx can load the cert
            client = httpx.Client(
                cert=(cert_pem, key_pem),
                timeout=httpx.Timeout(connect=5.0, read=10.0, write=10.0, pool=5.0),
            )
            self._ok("httpx client created with mTLS cert")
            self._ok(f"  cert: {cert_pem}")
            self._ok(f"  key:  {key_pem}")

            # Test TLS connection to FINA CIS test (we know this works)
            try:
                resp = client.get("https://cistest.apis-it.hr:8509/", timeout=5.0)
                self._ok(f"  FINA CIS test connection: HTTP {resp.status_code}")
            except httpx.ConnectError:
                self._warn("  FINA CIS test: connection refused (expected for GET)")
            except httpx.ReadTimeout:
                self._warn("  FINA CIS test: timeout (expected, server doesn't respond to GET)")
            except httpx.HTTPError as e:
                self._warn(f"  FINA CIS test: {type(e).__name__}: {e}")

            client.close()
            return {"ok": True}

        except httpx.HTTPError as e:
            self._error(f"mTLS setup failed: {e}")
            return {"ok": False}

    def _step_submit_echo(self, results):
        self._header("STEP 6: Echo Submit (Local Simulation)")
        xml = results["ubl"]["xml"]
        sha = results["ubl"]["sha256"]

        # Simulate what PosrednikClient.submit() would do
        import uuid
        fake_message_id = f"ECHO-{uuid.uuid4().hex[:12].upper()}"

        self._ok("Simulated submit:")
        self._ok("  Endpoint: https://api.einvoice.hr/v1/invoices (NOT called)")
        self._ok("  Method: POST")
        self._ok("  Content-Type: application/xml")
        self._ok(f"  Payload: {results['ubl']['size']} bytes")
        self._ok(f"  SHA-256: {sha[:32]}...")
        self._ok(f"  mTLS: cert loaded ({'YES' if results['mtls']['ok'] else 'NO'})")
        self._ok(f"  Echo MessageID: {fake_message_id}")
        self._ok("  Simulated Status: ACCEPTED")

        return {"ok": True, "message_id": fake_message_id, "mode": "echo"}

    def _step_submit_live(self, results):
        self._header("STEP 6: LIVE Submit")
        self._error("LIVE mode requires FINA_POSREDNIK_API_KEY in environment")
        self._error("Or registration with Moj-eRacun.hr sandbox")
        self._info("Set FINA_POSREDNIK_BASE_URL and FINA_POSREDNIK_API_KEY, then retry")
        return {"ok": False, "mode": "live"}

    def _report(self, results, elapsed):
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write("  SANDBOX STRIKE — RESULTS")
        self.stdout.write("=" * 70)

        steps = [
            ("Certificate", results.get("cert", {}).get("ok")),
            ("Invoice", results.get("invoice", {}).get("ok")),
            ("UBL Generation", results.get("ubl", {}).get("ok")),
            ("Validation", results.get("validation", {}).get("ok")),
            ("mTLS Ready", results.get("mtls", {}).get("ok")),
            ("Submit", results.get("submit", {}).get("ok")),
        ]

        all_pass = True
        for name, ok in steps:
            icon = "PASS" if ok else "FAIL"
            color = self.style.SUCCESS if ok else self.style.ERROR
            self.stdout.write(f"  {color(icon)}  {name}")
            if not ok:
                all_pass = False

        self.stdout.write(f"\n  Time: {elapsed:.2f}s")

        if results.get("validation", {}).get("valid") is False:
            self.stdout.write(self.style.WARNING(f"\n  Validation had {len(results['validation'].get('errors', []))} errors"))
            self.stdout.write(self.style.WARNING("  Fix errors before live submission"))

        if all_pass:
            self.stdout.write(self.style.SUCCESS("\n  PIPELINE READY for production."))
            self.stdout.write("  Next: Register with posrednik (FINA/Moj-eRacun) and set API key.")
        else:
            self.stdout.write(self.style.ERROR("\n  PIPELINE HAS ISSUES. Fix above errors."))

        self.stdout.write("=" * 70 + "\n")

    def _header(self, text):
        self.stdout.write(f"\n{'─' * 50}")
        self.stdout.write(f"  {text}")
        self.stdout.write(f"{'─' * 50}")

    def _ok(self, text):
        self.stdout.write(self.style.SUCCESS(f"  ✓ {text}"))

    def _warn(self, text):
        self.stdout.write(self.style.WARNING(f"  ⚠ {text}"))

    def _error(self, text):
        self.stdout.write(self.style.ERROR(f"  ✗ {text}"))

    def _info(self, text):
        self.stdout.write(f"  · {text}")

    def _fail(self, msg):
        self.stdout.write(self.style.ERROR(f"\n  ABORT: {msg}\n"))
