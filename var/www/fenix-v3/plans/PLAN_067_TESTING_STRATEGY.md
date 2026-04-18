# PLAN_067 — Testing Strategy & Smoke Tests

## Cilj
2030 kvaliteta testiranja. Piramida: unit (60%) + integration (30%) + E2E (10%). Svaki kritični workflow ima smoke test. CI zeleno = može ići na prod. Nema "kompajlira = radi" — svaka feature ima test.

## Testna piramida za Fenix V3
```
           /\
          /  \
         / E2E \    ← 10%: Playwright smoke tests
        /--------\
       /            \
      / Integration  \  ← 30%: API + DB + Celery
     /-----------------\
    /                   \
   /     Unit Tests       \  ← 60%: Business logic, models, utils
  /-------------------------\
```

## Struktura test direktorija
```
tests/
    conftest.py              ← globalni fixtures
    factories.py             ← Factory Boy factories ZA SVE modele
    
    unit/
        test_models.py       ← model metode, properties, calculations
        test_utils.py        ← utility funkcije (OIB validation, etc.)
        test_calculations.py ← honorari, payroll, PDV kalkulacije
        test_ocr_parsing.py  ← FenixScan._parse_response()
        test_permissions.py  ← has_permission(), ROLE_PERMISSIONS
    
    integration/
        test_auth.py         ← login, logout, PIN, rate limiting
        test_arhiva.py       ← upload, OCR, drawer, magic link
        test_invoicing.py    ← create, UBL XML, fiskalizacija
        test_pos.py          ← terminal, cart, payment, receipt
        test_payroll.py      ← bulk obračun, PDF, JOPPD
        test_smart_import.py ← batch upload, approve, reject
        test_trojstvo.py     ← consensus engine (mocked providers)
        test_ai_gateway.py   ← cost tracking, budget enforcement
    
    e2e/
        test_smoke.py        ← Playwright kritični pathovi
        test_pos_flow.py     ← POS full workflow
        test_arhiva_flow.py  ← upload → OCR → approve
```

## conftest.py (prošireni, iz PLAN_008)
```python
import pytest
from decimal import Decimal
from django.test import Client
from rest_framework.test import APIClient

from tests.factories import (
    UserFactory, CompanyFactory, MembershipFactory,
    ArhivaEntryFactory, InvoiceFactory, EmployeeFactory,
    POSRegisterFactory, POSTransactionFactory,
)

# --- Core fixtures ---

@pytest.fixture
def user(db):
    return UserFactory()

@pytest.fixture
def owner_user(db):
    return UserFactory(is_active=True)

@pytest.fixture
def company(db):
    return CompanyFactory()

@pytest.fixture
def membership(db, owner_user, company):
    return MembershipFactory(user=owner_user, company=company, role="owner")

@pytest.fixture
def auth_client(db, owner_user, company, membership):
    client = Client()
    client.force_login(owner_user)
    session = client.session
    session["active_company_id"] = str(company.id)
    session.save()
    return client

@pytest.fixture
def api_client(db, owner_user, company, membership):
    client = APIClient()
    client.force_authenticate(user=owner_user)
    return client

# --- Domain fixtures ---

@pytest.fixture
def employee(db, company):
    return EmployeeFactory(company=company, base_salary=Decimal("1200.00"))

@pytest.fixture
def arhiva_entry(db, company):
    return ArhivaEntryFactory(company=company, ai_status="done")

@pytest.fixture
def invoice(db, company):
    return InvoiceFactory(company=company, status="draft")

@pytest.fixture
def pos_register(db, company):
    return POSRegisterFactory(company=company)

# --- AI mock fixtures ---

@pytest.fixture
def mock_ai_gateway(mocker):
    """Mock AI gateway da testovi ne troše API kredit."""
    return mocker.patch("core.ai_gateway.ai_gateway.complete", return_value={
        "content": '{"vendor_name": "Test d.o.o.", "invoice_number": "R-001", "total_amount": "121.00", "vat_amount": "21.00", "date": "2026-04-01"}',
        "tokens": 100,
        "cost_usd": 0.00001,
    })

@pytest.fixture
def mock_fiskalizacija(mocker):
    """Mock FINA SOAP da testovi ne idu na produkciju."""
    return mocker.patch("invoicing.fiscal.send_to_fina", return_value={
        "jir": "aa112233-4455-6677-8899-aabbccddeeff",
        "success": True,
    })
```

## factories.py
```python
import factory
from factory.django import DjangoModelFactory
from django.contrib.auth.models import User

class UserFactory(DjangoModelFactory):
    class Meta:
        model = User
    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@fenix.test")
    password = factory.PostGenerationMethodCall("set_password", "testpass123")
    first_name = factory.Faker("first_name", locale="hr_HR")
    last_name = factory.Faker("last_name", locale="hr_HR")

class CompanyFactory(DjangoModelFactory):
    class Meta:
        model = "company.Company"
    name = factory.Sequence(lambda n: f"Test d.o.o. {n}")
    oib = factory.Sequence(lambda n: f"{10000000000 + n}")  # fake OIB
    is_active = True

class MembershipFactory(DjangoModelFactory):
    class Meta:
        model = "accounts.CompanyMembership"
    user = factory.SubFactory(UserFactory)
    company = factory.SubFactory(CompanyFactory)
    role = "owner"

class ArhivaEntryFactory(DjangoModelFactory):
    class Meta:
        model = "arhiva.ArhivaEntry"
    company = factory.SubFactory(CompanyFactory)
    doc_type = "ulazni_racun"
    vendor_name = factory.Faker("company", locale="hr_HR")
    document_number = factory.Sequence(lambda n: f"R-{n:04d}")
    total_amount = factory.Faker("pydecimal", min_value=10, max_value=10000, right_digits=2)
    ai_status = "pending"
    created_by = factory.SubFactory(UserFactory)

class InvoiceFactory(DjangoModelFactory):
    class Meta:
        model = "invoicing.Invoice"
    company = factory.SubFactory(CompanyFactory)
    invoice_number = factory.Sequence(lambda n: f"R1-2026-{n:04d}")
    invoice_type = "R1"
    status = "draft"
    net_amount = factory.Faker("pydecimal", min_value=100, max_value=5000, right_digits=2)
    vat_rate = factory.Faker("random_element", elements=["0.25", "0.13", "0.05"])
    created_by = factory.SubFactory(UserFactory)

class EmployeeFactory(DjangoModelFactory):
    class Meta:
        model = "employee.Employee"
    company = factory.SubFactory(CompanyFactory)
    first_name = factory.Faker("first_name", locale="hr_HR")
    last_name = factory.Faker("last_name", locale="hr_HR")
    oib = factory.Sequence(lambda n: f"{20000000000 + n}")
    base_salary = Decimal("1200.00")
    employment_start = factory.Faker("date_object")
    is_active = True

class POSRegisterFactory(DjangoModelFactory):
    class Meta:
        model = "pos.POSRegister"
    company = factory.SubFactory(CompanyFactory)
    name = "Blagajna 1"
    is_active = True

class POSTransactionFactory(DjangoModelFactory):
    class Meta:
        model = "pos.POSTransaction"
    session = factory.SubFactory("tests.factories.POSSessionFactory")
    transaction_type = "sale"
    payment_method = "cash"
    total = Decimal("25.00")
    status = "completed"
```

## Kritični unit testovi

### Kalkulacije (moraju biti 100% točne)
```python
# tests/unit/test_calculations.py

class TestPayrollCalculation:
    def test_standard_1200_eur_zagreb(self):
        """Verifikacija obračuna za tipičnog radnika."""
        calc = calculate_payslip(
            gross=Decimal("1200.00"),
            personal_allowance=Decimal("560.00"),
            prirez_rate=Decimal("0.018"),
            has_mio_2=True,
        )
        # MIO: 15% + 5% = 240
        assert calc.total_deductions == Decimal("240.00")
        # Osnova: 1200 - 240 - 560 = 400
        assert calc.tax_base == Decimal("400.00")
        # Porez: 400 * 20% = 80
        assert calc.income_tax == Decimal("80.00")
        # Prirez: 80 * 1.8% = 1.44
        assert calc.prirez == Decimal("1.44")
        # Neto: 1200 - 240 - 80 - 1.44 = 878.56
        assert calc.net_salary == Decimal("878.56")

    def test_no_mio2_over_40(self):
        calc = calculate_payslip(Decimal("1000.00"), has_mio_2=False)
        assert calc.mio_2 == Decimal("0.00")
        assert calc.total_deductions == Decimal("150.00")

    def test_zero_tax_if_below_allowance(self):
        """Minimalna plaća ispod osobnog odbitka → nema poreza."""
        calc = calculate_payslip(Decimal("600.00"))
        # 600 - 150 (MIO) - 560 (odbitak) = -110 → osnova = 0
        assert calc.tax_base == Decimal("0.00")
        assert calc.income_tax == Decimal("0.00")


class TestHonorariCalculation:
    def test_1000_eur_zagreb(self):
        from honorari.calculations import calculate_honorar
        result = calculate_honorar(Decimal("1000.00"), prirez_rate=Decimal("0.018"))
        assert result["normativni"] == Decimal("300.00")
        assert result["osnova"] == Decimal("700.00")
        assert result["porez"] == Decimal("140.00")
        assert result["prirez"] == Decimal("2.52")
        assert result["neto"] == Decimal("857.48")


class TestOIBValidation:
    def test_valid_oib(self):
        from core.validators import validate_oib
        assert validate_oib("12345678903") == True  # primjer valjanog OIB-a

    def test_invalid_oib_length(self):
        from core.validators import validate_oib
        assert validate_oib("123") == False

    def test_invalid_oib_checksum(self):
        from core.validators import validate_oib
        assert validate_oib("12345678900") == False
```

### Permissions
```python
class TestPermissions:
    def test_owner_has_all_permissions(self, company):
        membership = MembershipFactory(company=company, role="owner")
        for perm in Permission:
            assert has_permission(membership, perm)

    def test_viewer_cannot_manage(self, company):
        membership = MembershipFactory(company=company, role="viewer")
        assert not has_permission(membership, Permission.MANAGE_JOURNAL)
        assert not has_permission(membership, Permission.MANAGE_PAYROLL)
        assert has_permission(membership, Permission.VIEW_DOCUMENTS)

    def test_accountant_can_invoice(self, company):
        membership = MembershipFactory(company=company, role="accountant")
        assert has_permission(membership, Permission.CREATE_INVOICE)
        assert not has_permission(membership, Permission.MANAGE_MEMBERS)
```

## Kritični integration testovi

### Auth flow
```python
class TestLogin:
    def test_successful_login(self, client, user):
        resp = client.post("/hr/login/", {"username": user.username, "password": "testpass123"})
        assert resp.status_code == 302
    
    def test_rate_limit_after_5_failures(self, client, user):
        for _ in range(5):
            client.post("/hr/login/", {"username": user.username, "password": "wrong"})
        resp = client.post("/hr/login/", {"username": user.username, "password": "wrong"})
        assert "previše" in resp.content.decode("utf-8").lower() or resp.status_code == 429

    def test_inactive_user_cannot_login(self, client, db):
        user = UserFactory(is_active=False)
        resp = client.post("/hr/login/", {"username": user.username, "password": "testpass123"})
        assert resp.status_code != 302
```

### Arhiva
```python
class TestArhivaUpload:
    def test_upload_creates_entry(self, auth_client, company):
        pdf = SimpleUploadedFile("test.pdf", b"PDF content", content_type="application/pdf")
        resp = auth_client.post("/hr/documents/arhiva/upload/", {"file": pdf, "doc_type": "ulazni_racun"})
        assert resp.status_code in [200, 201, 302]
        assert ArhivaEntry.objects.filter(company=company).count() == 1

    def test_upload_rejects_oversized_file(self, auth_client):
        big_file = SimpleUploadedFile("big.pdf", b"x" * (21 * 1024 * 1024))
        resp = auth_client.post("/hr/documents/arhiva/upload/", {"file": big_file})
        assert resp.status_code == 400

    def test_magic_link_works_without_auth(self, client, company):
        entry = ArhivaEntryFactory(company=company)
        token = ArhivaAccessToken.objects.create(entry=entry)
        resp = client.get(f"/hr/documents/arhiva/portal/{token.token}/")
        assert resp.status_code == 200
```

### POS
```python
class TestPOSFlow:
    def test_add_item_to_cart(self, auth_client, pos_register):
        product = POSProductFactory(register=pos_register)
        resp = auth_client.post("/hr/pos/api/cart/add/", {
            "product_id": str(product.id),
            "quantity": 1,
        }, content_type="application/json")
        assert resp.json()["ok"] == True

    def test_sale_creates_transaction(self, auth_client, pos_register):
        session = POSSessionFactory(register=pos_register)
        resp = auth_client.post("/hr/pos/api/sale/", {
            "payment_method": "cash",
            "items": [{"product_id": "...", "quantity": 1, "price": "25.00"}],
        }, content_type="application/json")
        assert POSTransaction.objects.filter(session=session).count() == 1
```

## E2E Smoke Tests (Playwright)

```python
# tests/e2e/test_smoke.py
import pytest
from playwright.sync_api import Page, expect

LIVE_URL = "http://localhost:8000"

@pytest.fixture
def logged_in_page(page: Page, live_server):
    page.goto(f"{live_server.url}/hr/login/")
    page.fill('[name="username"]', "testadmin")
    page.fill('[name="password"]', "testpass123")
    page.click('[type="submit"]')
    page.wait_for_url("**/dashboard/**")
    return page

def test_dashboard_loads(logged_in_page):
    expect(logged_in_page.locator("h1")).to_be_visible()

def test_arhiva_upload_page_accessible(logged_in_page):
    logged_in_page.goto(f"{LIVE_URL}/hr/documents/arhiva/upload/")
    expect(logged_in_page.locator('[data-testid="upload-zone"]')).to_be_visible()

def test_pos_terminal_loads(logged_in_page):
    logged_in_page.goto(f"{LIVE_URL}/hr/pos/terminal/")
    expect(logged_in_page.locator('[data-testid="pos-cart"]')).to_be_visible()
    expect(logged_in_page.locator('[data-testid="pos-catalog"]')).to_be_visible()

def test_smart_import_accessible(logged_in_page):
    logged_in_page.goto(f"{LIVE_URL}/hr/smart-import/")
    expect(logged_in_page.locator('[data-testid="drop-zone"]')).to_be_visible()

def test_company_switch_works(logged_in_page):
    logged_in_page.click('[data-testid="company-switcher"]')
    expect(logged_in_page.locator('[data-testid="company-search"]')).to_be_visible()

def test_login_logout_cycle(page: Page, live_server):
    page.goto(f"{live_server.url}/hr/login/")
    page.fill('[name="username"]', "testadmin")
    page.fill('[name="password"]', "testpass123")
    page.click('[type="submit"]')
    page.goto(f"{live_server.url}/hr/accounts/logout/")
    # Logout mora biti POST
    page.locator('[data-testid="logout-btn"]').click()
    expect(page).to_have_url("**/login/**")
```

## Coverage ciljevi
| Modul | Minimum coverage |
|-------|-----------------|
| core/models.py | 90% |
| calculations (payroll, honorari, pdv) | 100% |
| validators (OIB, IBAN) | 100% |
| auth/permissions | 95% |
| views (all) | 80% |
| tasks (Celery) | 70% |
| FenixScan OCR | 75% |
| Ukupno projekt | ≥ 80% |

## pytest.ini settings
```ini
[pytest]
DJANGO_SETTINGS_MODULE = config.settings.test
python_files = tests/*/test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    --reuse-db
    --strict-markers
    -x
    --tb=short
markers =
    slow: marks tests as slow (deselect with '-m "not slow"')
    integration: marks integration tests
    e2e: marks end-to-end tests requiring browser
    ai: marks tests that call real AI APIs
```

## PRAVILA KOJA SE NE SMIJU KRŠITI
1. **Nema AI poziva u testovima** osim ako fixture nije označen `@pytest.mark.ai`
2. **Nema real FINA SOAP poziva** — uvijek mock
3. **Nema test podataka na produkcijskoj bazi** — TEST baza je odvojena
4. **Svaki novi view mora imati min 1 test** — prijedlog: 200 OK + 401 bez autentikacije
5. **Kalkulacijski testovi su sekundarni** — tebe treba netko drugi provjeriti
6. **Factories za sve modele** — ne kreirati modele direktno u testovima
