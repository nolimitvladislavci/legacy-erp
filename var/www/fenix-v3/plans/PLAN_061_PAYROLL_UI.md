# PLAN_061 — Payroll UI (Obračun Plaća — Kompletan Interface)

## Cilj
Kompletno sučelje za obračun plaća. Model postoji (PLAN_058). Ovdje je UI: unos parametara, live kalkulator, bulk obračun za sve radnike, PDF isplatne liste, JOPPD priprema, export u bankovni format (HUB-3/SEPA XML).

## HR Doprinosi (2026 stope)
```python
HR_CONTRIBUTION_RATES = {
    # Doprinosi iz plaće (teret radnika)
    "mio_1": Decimal("0.15"),      # MIO I. stup
    "mio_2": Decimal("0.05"),      # MIO II. stup (za mlađe od 40)
    
    # Doprinosi na plaću (teret poslodavca)
    "zdravstveno": Decimal("0.165"),  # Zdravstveno osiguranje
    
    # Porez na dohodak (po razredima)
    "porez_nizak": Decimal("0.20"),   # do 26.000 EUR/god (4.666,67/mj)
    "porez_visok": Decimal("0.30"),   # iznad 26.000 EUR/god
    
    # Osobni odbitak (2026)
    "osnovni_odbitak": Decimal("560.00"),  # EUR/mj — bazni
    # Djeca povećavaju odbitak (1. dijete +0.7, 2. +1.0, 3. +1.4, ...)
}
```

## Obračun plaće (business logic)
```python
from dataclasses import dataclass

@dataclass
class PayslipCalculation:
    """Rezultat obračuna plaće za jednog radnika."""
    employee_id: str
    gross_salary: Decimal
    
    # Iz plaće (radnik plaća)
    mio_1: Decimal
    mio_2: Decimal
    total_deductions: Decimal  # mio_1 + mio_2
    
    # Porezna osnova i porez
    tax_base: Decimal          # gross - mio_1 - mio_2 - osobni_odbitak
    personal_allowance: Decimal
    income_tax: Decimal
    prirez: Decimal
    total_tax: Decimal         # income_tax + prirez
    
    # Neto
    net_salary: Decimal        # gross - total_deductions - total_tax
    
    # Na plaću (poslodavac plaća)
    employer_health: Decimal   # 16.5% na bruto
    total_employer_cost: Decimal  # gross + employer_health


def calculate_payslip(
    gross: Decimal,
    personal_allowance: Decimal = Decimal("560.00"),
    prirez_rate: Decimal = Decimal("0.018"),
    has_mio_2: bool = True,  # False za starije od 40
) -> PayslipCalculation:
    
    # Doprinosi iz plaće
    mio_1 = (gross * HR_CONTRIBUTION_RATES["mio_1"]).quantize(Decimal("0.01"))
    mio_2 = (gross * HR_CONTRIBUTION_RATES["mio_2"]).quantize(Decimal("0.01")) if has_mio_2 else Decimal("0")
    total_deductions = mio_1 + mio_2
    
    # Porezna osnova
    tax_base = max(Decimal("0"), gross - total_deductions - personal_allowance)
    
    # Porez (pojednostavljeni — bez progresivnih razreda za sad)
    income_tax = (tax_base * HR_CONTRIBUTION_RATES["porez_nizak"]).quantize(Decimal("0.01"))
    prirez = (income_tax * prirez_rate).quantize(Decimal("0.01"))
    total_tax = income_tax + prirez
    
    # Neto
    net_salary = (gross - total_deductions - total_tax).quantize(Decimal("0.01"))
    
    # Trošak poslodavca
    employer_health = (gross * HR_CONTRIBUTION_RATES["zdravstveno"]).quantize(Decimal("0.01"))
    total_employer_cost = gross + employer_health
    
    return PayslipCalculation(
        employee_id="",
        gross_salary=gross,
        mio_1=mio_1,
        mio_2=mio_2,
        total_deductions=total_deductions,
        tax_base=tax_base,
        personal_allowance=personal_allowance,
        income_tax=income_tax,
        prirez=prirez,
        total_tax=total_tax,
        net_salary=net_salary,
        employer_health=employer_health,
        total_employer_cost=total_employer_cost,
    )
```

## URL struktura
```
/hr/place/                           → PayrollListView (pregled obračuna)
/hr/place/novi/                      → PayrollCreateView (single)
/hr/place/bulk/                      → PayrollBulkView (bulk za sve radnike)
/hr/place/<uuid>/                    → PayslipDetailView
/hr/place/<uuid>/pdf/                → PayslipPDFView
/hr/place/bulk/<month>/pdf/          → PayrollBulkPDFView (sve isplatne liste)
/hr/place/api/kalkulacija/           → PayrollCalcAPIView (live kalkulator, HTMX)
/hr/place/api/joppd/                 → JOPPDPrepView
/hr/place/api/sepa/                  → SEPAExportView
```

## PayrollCalcAPIView (live HTMX kalkulator)
```python
class PayrollCalcAPIView(TenantView):
    def get(self, request):
        try:
            gross = Decimal(request.GET.get("gross", "0"))
        except Exception:
            return HttpResponse("Unesite ispravni iznos")
        
        prirez = Decimal(request.GET.get("prirez", "0.018"))
        has_mio_2 = request.GET.get("mio_2", "1") == "1"
        
        result = calculate_payslip(gross, prirez_rate=prirez, has_mio_2=has_mio_2)
        return render(request, "payroll/partials/calculation_result.html", {"calc": result})
```

## Template: payroll/form.html
Alpine.js `payrollCalc()`:

```html
<div x-data="payrollCalc()" class="grid grid-cols-2 gap-6">
  <!-- Input forma -->
  <div class="card">
    <h2 class="text-lg font-semibold mb-4">Parametri</h2>
    
    <div class="space-y-4">
      <div>
        <label class="label">Radnik</label>
        <select name="employee_id" class="input" 
                @change="loadEmployee($event.target.value)">
          <option value="">— Odaberi radnika —</option>
          {% for emp in employees %}
          <option value="{{ emp.id }}" 
                  data-gross="{{ emp.base_salary }}"
                  data-prirez="{{ emp.prirez_stopa }}"
                  data-mio2="{{ emp.has_mio_2|yesno:'1,0' }}">
            {{ emp.full_name }} ({{ emp.position }})
          </option>
          {% endfor %}
        </select>
      </div>
      
      <div>
        <label class="label">Bruto plaća (EUR)</label>
        <input type="number" step="0.01"
          x-model.number="gross"
          @input.debounce.500="calculate()"
          class="input text-right font-mono text-lg"
          placeholder="1000.00">
      </div>
      
      <div>
        <label class="label">Osobni odbitak</label>
        <input type="number" step="0.01"
          x-model.number="personalAllowance"
          @input.debounce.500="calculate()"
          class="input text-right font-mono">
        <p class="text-xs text-gray-400 mt-1">Bazni: 560,00 EUR. Djeca povećavaju odbitak.</p>
      </div>
      
      <div>
        <label class="label">Prirez općina</label>
        <select x-model="prirezStopa" @change="calculate()" class="input">
          {% for opcina, stopa in prirez_stope.items %}
          <option value="{{ stopa }}">{{ opcina }} ({{ stopa|to_percent }}%)</option>
          {% endfor %}
        </select>
      </div>
      
      <div class="flex items-center gap-2">
        <input type="checkbox" id="mio2" x-model="hasMio2" @change="calculate()" class="rounded">
        <label for="mio2" class="text-sm">MIO II. stup (radnici mlađi od 40 god.)</label>
      </div>
    </div>
  </div>

  <!-- Live rezultat (HTMX) -->
  <div class="card"
       hx-get="/hr/place/api/kalkulacija/"
       hx-trigger="calcNeeded from:body"
       hx-include="[name='gross'],[name='prirez'],[name='mio_2']"
       hx-swap="innerHTML"
       id="calc-result">
    
    <h2 class="text-lg font-semibold mb-4">Obračun</h2>
    
    <!-- Waterfall prikaz -->
    <div class="space-y-1 text-sm">
      <div class="flex justify-between py-2 border-b">
        <span class="font-medium">BRUTO plaća</span>
        <span class="font-mono font-bold" x-text="fmt(gross)"></span>
      </div>
      
      <div class="flex justify-between text-gray-600 py-1">
        <span>- MIO I. stup (15%)</span>
        <span class="font-mono" x-text="'- ' + fmt(gross * 0.15)"></span>
      </div>
      
      <div class="flex justify-between text-gray-600 py-1" x-show="hasMio2">
        <span>- MIO II. stup (5%)</span>
        <span class="font-mono" x-text="'- ' + fmt(gross * 0.05)"></span>
      </div>
      
      <div class="flex justify-between text-gray-600 py-1">
        <span>- Osobni odbitak</span>
        <span class="font-mono" x-text="'- ' + fmt(personalAllowance)"></span>
      </div>
      
      <div class="flex justify-between py-1 border-t">
        <span>= Porezna osnova</span>
        <span class="font-mono" x-text="fmt(taxBase)"></span>
      </div>
      
      <div class="flex justify-between text-gray-600 py-1">
        <span>- Porez na dohodak (20%)</span>
        <span class="font-mono" x-text="'- ' + fmt(taxBase * 0.20)"></span>
      </div>
      
      <div class="flex justify-between text-gray-600 py-1" x-show="prirezStopa > 0">
        <span>- Prirez</span>
        <span class="font-mono" x-text="'- ' + fmt(taxBase * 0.20 * prirezStopa)"></span>
      </div>
      
      <div class="flex justify-between py-3 border-t-2 border-fenix-500 bg-fenix-50 rounded px-2 mt-2">
        <span class="font-bold text-lg">NETO za isplatu</span>
        <span class="font-mono font-bold text-xl text-fenix-700" x-text="fmt(netSalary)"></span>
      </div>
      
      <div class="mt-4 pt-4 border-t">
        <div class="flex justify-between text-gray-600 py-1">
          <span>+ Zdravstveno na plaću (16.5%)</span>
          <span class="font-mono" x-text="'+ ' + fmt(gross * 0.165)"></span>
        </div>
        <div class="flex justify-between font-medium py-1">
          <span>= Ukupni trošak poslodavca</span>
          <span class="font-mono" x-text="fmt(gross * 1.165)"></span>
        </div>
      </div>
    </div>
  </div>
</div>
```

Alpine.js:
```javascript
function payrollCalc() {
  return {
    gross: 0,
    personalAllowance: 560,
    prirezStopa: 0.018,
    hasMio2: true,

    get totalDeductions() {
      return this.gross * 0.15 + (this.hasMio2 ? this.gross * 0.05 : 0);
    },
    get taxBase() {
      return Math.max(0, this.gross - this.totalDeductions - this.personalAllowance);
    },
    get incomeTax() { return this.taxBase * 0.20; },
    get prirez() { return this.incomeTax * this.prirezStopa; },
    get totalTax() { return this.incomeTax + this.prirez; },
    get netSalary() { return this.gross - this.totalDeductions - this.totalTax; },

    loadEmployee(empId) {
      const opt = document.querySelector(`option[value="${empId}"]`);
      if (!opt) return;
      this.gross = parseFloat(opt.dataset.gross) || 0;
      this.prirezStopa = parseFloat(opt.dataset.prirez) || 0.018;
      this.hasMio2 = opt.dataset.mio2 === '1';
    },

    fmt(val) {
      return new Intl.NumberFormat('hr-HR', { minimumFractionDigits: 2 }).format(val || 0) + ' EUR';
    },
  };
}
```

## PayrollBulkView (bulk za sve radnike)
```python
class PayrollBulkView(TenantView):
    permission_required = Permission.MANAGE_PAYROLL

    def get(self, request):
        employees = Employee.objects.filter(company=request.company, is_active=True)
        return render(request, "payroll/bulk.html", {"employees": employees})

    def post(self, request):
        year = int(request.POST.get("year", date.today().year))
        month = int(request.POST.get("month", date.today().month))
        employees = Employee.objects.filter(company=request.company, is_active=True)
        
        created_count = 0
        with transaction.atomic():
            for emp in employees:
                calc = calculate_payslip(
                    emp.base_salary,
                    personal_allowance=emp.personal_allowance or Decimal("560"),
                    prirez_rate=emp.prirez_stopa,
                    has_mio_2=emp.has_mio_2,
                )
                payslip, created = Payslip.objects.get_or_create(
                    company=request.company,
                    employee=emp,
                    year=year,
                    month=month,
                    defaults={
                        "gross_salary": calc.gross_salary,
                        "mio_1": calc.mio_1,
                        "mio_2": calc.mio_2,
                        "income_tax": calc.income_tax,
                        "prirez": calc.prirez,
                        "net_salary": calc.net_salary,
                        "employer_health": calc.employer_health,
                        "status": "calculated",
                        "created_by": request.user,
                    }
                )
                if created:
                    created_count += 1
        
        messages.success(request, f"Obračun za {month}/{year} kreiran za {created_count} radnika.")
        return redirect("payroll:bulk_pdf", year=year, month=month)
```

## PDF Isplatna Lista (WeasyPrint)
Template: `payroll/isplatna_lista_pdf.html`
- Zaglavlje: Firma, OIB, adresa
- Radnik: Ime, OIB, IBAN, pozicija
- Period: Mesec/Godina
- Tabela obračuna: Bruto → Doprinosi → Oporezivi dohodak → Porez → Prirez → Neto
- Footer: Potpis ovlaštene osobe

## SEPA XML Export (HRK → EUR bankovni nalog)
```python
def generate_sepa_credit_transfer(payslips: list) -> str:
    """
    Generira SEPA Credit Transfer XML (pain.001.001.03).
    Za masovne isplate plaća putem banke.
    """
    # ... SEPA XML format
    # Total iznos = sum net_salary
    # Jedan CdtTrfTxInf per radnik
    # Debtor = kompanija (IBAN iz company.iban)
    # Creditor = radnik (IBAN iz employee.iban)
    pass  # Implementacija po ISO 20022 shemi
```

## Testovi
```python
def test_payslip_calculation_1000_eur():
    calc = calculate_payslip(Decimal("1000.00"), prirez_rate=Decimal("0.018"))
    assert calc.mio_1 == Decimal("150.00")
    assert calc.mio_2 == Decimal("50.00")
    assert calc.total_deductions == Decimal("200.00")
    assert calc.tax_base == Decimal("240.00")  # 1000 - 200 - 560
    assert calc.income_tax == Decimal("48.00")
    assert calc.prirez == Decimal("0.86")  # 48 * 0.018 = 0.864
    assert calc.net_salary == Decimal("751.14")

def test_bulk_payroll_creates_all_employees(auth_client, company):
    employees = [EmployeeFactory(company=company) for _ in range(5)]
    resp = auth_client.post("/hr/place/bulk/", {"year": 2026, "month": 4})
    assert Payslip.objects.filter(company=company, year=2026, month=4).count() == 5

def test_no_duplicate_payslip(auth_client, company, employee):
    PayslipFactory(company=company, employee=employee, year=2026, month=4)
    # Bulk run ne smije kreirati duplikat
    auth_client.post("/hr/place/bulk/", {"year": 2026, "month": 4})
    assert Payslip.objects.filter(employee=employee, year=2026, month=4).count() == 1
```
