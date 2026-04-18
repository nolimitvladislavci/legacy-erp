# PLAN_059 — Honorari (Autorska Prava i Ugovori o Djelu)

## Cilj
HR: Isplata autorskih honorara i ugovora o djelu. Obračun poreza (paušalni odbitak 30%, porez 20%, prirez), JOPPD prijava (elektronska za Poreznu upravu), isplatna lista. Bookkeeper koristi za obračun za klijente.

## HR Zakonski okvir
- Zakon o porezu na dohodak — čl. 57-64 (drugi dohodak)
- Autorski honorar: normirani troškovi 30% → porezna osnovica 70%
- Porez: 20% na iznos do 26.000 EUR/god, 30% iznad
- Prirez: prema stopi općine primatelja (Zagreb: 1.8%, Rijeka: 1.5%)
- JOPPD: elektronska prijava, rok sljedeći dan od isplate
- Samooporezianje se ne primjenjuje za paušalni honorar

## Model
```python
class HonorariContract(TenantModel):
    """
    Ugovor o autorskom djelu ili ugovor o djelu.
    """
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="honorari_contracts")

    class ContractType(models.TextChoices):
        AUTORSKI = "autorski", "Autorski honorar"
        DJELO = "djelo", "Ugovor o djelu"
        STUDENT = "student", "Studentski ugovor"

    contract_type = models.CharField(max_length=20, choices=ContractType.choices)
    recipient_name = models.CharField(max_length=200)
    recipient_oib = models.CharField(max_length=11)
    recipient_address = models.TextField()
    recipient_iban = models.CharField(max_length=34)
    recipient_prirez_opcina = models.CharField(max_length=100, default="Zagreb")
    prirez_stopa = models.DecimalField(max_digits=5, decimal_places=4, default=Decimal("0.018"))

    description = models.TextField()  # Opis djela/usluge
    gross_amount = models.DecimalField(max_digits=10, decimal_places=2)

    # Obračun (auto-populate)
    normative_costs = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # 30%
    tax_base = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # 70%
    income_tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # 20%
    prirez_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # za isplatu

    payment_date = models.DateField(null=True)
    status = models.CharField(
        max_length=20,
        choices=[("draft","Nacrt"),("calculated","Obračunato"),("paid","Isplaćeno"),("joppd_sent","JOPPD predano")],
        default="draft"
    )
    joppd_reference = models.CharField(max_length=50, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    def calculate(self):
        """Obračunaj sve stavke."""
        gross = self.gross_amount
        self.normative_costs = (gross * Decimal("0.30")).quantize(Decimal("0.01"))
        self.tax_base = (gross * Decimal("0.70")).quantize(Decimal("0.01"))
        self.income_tax = (self.tax_base * Decimal("0.20")).quantize(Decimal("0.01"))
        self.prirez_amount = (self.income_tax * self.prirez_stopa).quantize(Decimal("0.01"))
        self.net_amount = (gross - self.income_tax - self.prirez_amount).quantize(Decimal("0.01"))
        self.status = "calculated"
        self.save()
```

## Prirez stope (najpopularnije)
```python
PRIREZ_STOPE = {
    "Zagreb": Decimal("0.018"),      # 1.8%
    "Rijeka": Decimal("0.015"),       # 1.5%
    "Split": Decimal("0.010"),        # 1.0%
    "Osijek": Decimal("0.013"),       # 1.3%
    "Varaždin": Decimal("0.014"),     # 1.4%
    "Pula": Decimal("0.010"),         # 1.0%
    "Zadar": Decimal("0.010"),        # 1.0%
    "Šibenik": Decimal("0.010"),      # 1.0%
    "Dubrovnik": Decimal("0.010"),    # 1.0%
    "Karlovac": Decimal("0.012"),     # 1.2%
    # Bez prireza:
    "Kutina": Decimal("0"),
    "Đakovo": Decimal("0"),
}
```

## URL struktura
```
/hr/honorari/                        → HonorariListView
/hr/honorari/novi/                   → HonorariCreateView
/hr/honorari/<uuid>/                 → HonorariDetailView
/hr/honorari/<uuid>/pdf/             → HonorariPDFView
/hr/honorari/<uuid>/joppd/           → JOPPDView
/hr/honorari/api/prirez/<opcina>/    → PrirezAPIView (HTMX lookup)
```

## HonorariCreateView
```python
class HonorariCreateView(TenantView):
    permission_required = Permission.MANAGE_PAYROLL
    template_name = "honorari/form.html"

    def get(self, request):
        return render(request, self.template_name, {
            "prirez_stope": PRIREZ_STOPE,
        })

    def post(self, request):
        data = request.POST
        contract = HonorariContract(
            company=request.company,
            contract_type=data["contract_type"],
            recipient_name=data["recipient_name"],
            recipient_oib=data["recipient_oib"],
            recipient_address=data["recipient_address"],
            recipient_iban=data["recipient_iban"],
            recipient_prirez_opcina=data["prirez_opcina"],
            prirez_stopa=PRIREZ_STOPE.get(data["prirez_opcina"], Decimal("0")),
            description=data["description"],
            gross_amount=Decimal(data["gross_amount"]),
            payment_date=data.get("payment_date") or None,
            created_by=request.user,
        )
        contract.calculate()
        messages.success(request, f"Honorar obračunat. Neto za isplatu: {contract.net_amount} EUR")
        return redirect("honorari:detail", pk=contract.id)
```

## Template: honorari/form.html
Alpine.js `honorarCalculator()`:
```javascript
function honorarCalculator() {
  return {
    gross: 0,
    prirezStopa: 0.018,
    
    get normativniTroskovi() { return this.gross * 0.30; },
    get poreznaOsnovica() { return this.gross * 0.70; },
    get porezNaDohodak() { return this.poreznaOsnovica * 0.20; },
    get prirez() { return this.porezNaDohodak * this.prirezStopa; },
    get neto() { return this.gross - this.porezNaDohodak - this.prirez; },
    
    fmt(val) {
      return new Intl.NumberFormat('hr-HR', { minimumFractionDigits: 2 }).format(val) + ' EUR';
    },
  };
}
```

Live kalkulator:
```html
<div x-data="honorarCalculator()">
  <div class="grid grid-cols-2 gap-4">
    <div>
      <label class="label">Bruto iznos (EUR)</label>
      <input type="number" step="0.01" x-model.number="gross" class="input text-right font-mono">
    </div>
    <div>
      <label class="label">Prirez općina</label>
      <select @change="prirezStopa = parseFloat($event.target.value)" class="input">
        {% for opcina, stopa in prirez_stope.items %}
        <option value="{{ stopa }}">{{ opcina }} ({{ stopa|percentage }}%)</option>
        {% endfor %}
      </select>
    </div>
  </div>

  <!-- Live obračun -->
  <div class="card mt-4 bg-gray-50">
    <h3 class="font-semibold mb-3">Obračun</h3>
    <table class="w-full text-sm">
      <tr><td>Bruto honorar</td><td class="text-right font-mono" x-text="fmt(gross)"></td></tr>
      <tr class="text-gray-500"><td>- Normativni troškovi (30%)</td><td class="text-right font-mono" x-text="'- ' + fmt(normativniTroskovi)"></td></tr>
      <tr><td>= Porezna osnovica (70%)</td><td class="text-right font-mono" x-text="fmt(poreznaOsnovica)"></td></tr>
      <tr class="text-gray-500"><td>- Porez na dohodak (20%)</td><td class="text-right font-mono" x-text="'- ' + fmt(porezNaDohodak)"></td></tr>
      <tr class="text-gray-500" x-show="prirezStopa > 0"><td>- Prirez</td><td class="text-right font-mono" x-text="'- ' + fmt(prirez)"></td></tr>
      <tr class="border-t-2 font-bold text-fenix-700">
        <td>= NETO za isplatu</td>
        <td class="text-right font-mono text-lg" x-text="fmt(neto)"></td>
      </tr>
    </table>
  </div>
</div>
```

## PDF Isplatna Lista (WeasyPrint)
Template: `honorari/isplatna_lista_pdf.html`
- Zaglavlje: Naziv firme, OIB, adresa
- Primatelj: Ime, OIB, adresa, IBAN
- Opis: Opis usluge/djela
- Tabela: Bruto → Norm. troškovi → Osnova → Porez → Prirez → NETO
- Footer: Pečat i potpis, Datum isplate
- Napomena: "Primitak podliježe porezu na dohodak sukladno čl. 57. ZPD-a"

```python
class HonorariPDFView(TenantView):
    def get(self, request, pk):
        contract = get_object_or_404(HonorariContract, id=pk, company=request.company)
        html = render_to_string("honorari/isplatna_lista_pdf.html", {
            "contract": contract,
            "company": request.company,
            "date": date.today(),
        })
        pdf = HTML(string=html, base_url=request.build_absolute_uri("/")).write_pdf()
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="honorar-{contract.recipient_oib}.pdf"'
        return response
```

## JOPPD XML (simplified)
```python
def generate_joppd_xml(contract: HonorariContract, company: Company) -> str:
    """
    Generira JOPPD A i B obrazac XML za ePorezna.
    Tip primitka: 1001 (autorski honorar) ili 1200 (ugovor o djelu)
    """
    tip = "1001" if contract.contract_type == "autorski" else "1200"
    datum = contract.payment_date or date.today()
    oznaka = f"{datum.year}{datum.timetuple().tm_yday:03d}1"  # JOPPD oznaka
    
    root = ET.Element("Obrazac")
    root.set("xmlns", "http://e-porezna.porezna-uprava.hr/sheme/zahtjevi/ObrazacJOPPD/v2-2")
    
    zaglavlje = ET.SubElement(root, "Zaglavlje")
    ET.SubElement(zaglavlje, "Vrsta").text = "P"
    ET.SubElement(zaglavlje, "DatumIzvjesca").text = datum.isoformat()
    ET.SubElement(zaglavlje, "Oznaka").text = oznaka
    ET.SubElement(zaglavlje, "OIBPodnositelja").text = company.oib
    ET.SubElement(zaglavlje, "NazivPodnositelja").text = company.name
    
    stranica_b = ET.SubElement(root, "StrB")
    redak = ET.SubElement(stranica_b, "Redak")
    ET.SubElement(redak, "RedniBroj").text = "1"
    ET.SubElement(redak, "OIBPrimatelja").text = contract.recipient_oib
    ET.SubElement(redak, "ImeIPrezimePrimatelja").text = contract.recipient_name
    ET.SubElement(redak, "TipPrimitka").text = tip
    ET.SubElement(redak, "BrutoPrimitak").text = str(contract.gross_amount)
    ET.SubElement(redak, "IznPorezaIPrireza").text = str(contract.income_tax + contract.prirez_amount)
    ET.SubElement(redak, "Neto").text = str(contract.net_amount)
    
    return ET.tostring(root, encoding="unicode", xml_declaration=True)
```

## Testovi
```python
def test_honorar_calculation_correct():
    contract = HonorariContractFactory(
        gross_amount=Decimal("1000.00"),
        prirez_stopa=Decimal("0.018"),
    )
    contract.calculate()
    assert contract.normative_costs == Decimal("300.00")
    assert contract.tax_base == Decimal("700.00")
    assert contract.income_tax == Decimal("140.00")
    assert contract.prirez_amount == Decimal("2.52")
    assert contract.net_amount == Decimal("857.48")

def test_prirez_zero_gemeente():
    contract = HonorariContractFactory(
        gross_amount=Decimal("1000.00"),
        prirez_stopa=Decimal("0"),
    )
    contract.calculate()
    assert contract.prirez_amount == Decimal("0.00")
    assert contract.net_amount == Decimal("860.00")
```
