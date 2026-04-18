# PLAN_045 — Gov Export (Porezna Prijava — HR PDV + DE MwSt)

## Cilj
Generiranje i slanje poreznih prijava. HR: PDV-S obrazac za ePorezna XML. DE: UStVA Voranmeldung XML za ELSTER. Arhiviranje svakog submita (ZOR/GoBD).

## URL struktura
```
/hr/pdv/                         → PDVListView (HR)
/hr/pdv/novo/                    → PDVCreateView
/hr/pdv/izracun/<year>/<month>/  → PDVCalculateView (HTMX)
/hr/pdv/<uuid>/xml/              → PDVXMLView (download)
/hr/pdv/<uuid>/submit/           → PDVSubmitView (simulacija)
/de/mwst/                        → MwStListView (DE)
/de/mwst/novo/                   → MwStCreateView
/de/mwst/<uuid>/elster/          → ELSTERExportView
```

## Model
```python
class VATReturn(TenantModel):
    class ReturnType(models.TextChoices):
        HR_PDV_S = "hr_pdv_s", "HR PDV-S"
        DE_USTVAR = "de_ustvar", "DE UStVA"

    class Status(models.TextChoices):
        DRAFT = "draft", "Nacrt"
        SUBMITTED = "submitted", "Predano"
        ACCEPTED = "accepted", "Prihvaćeno"
        REJECTED = "rejected", "Odbijeno"

    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="vat_returns")
    return_type = models.CharField(max_length=20, choices=ReturnType.choices)
    period_year = models.IntegerField()
    period_month = models.IntegerField()  # 1-12
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)

    # HR PDV-S polja (eurski iznosi)
    hr_i1_taxable = models.DecimalField(max_digits=14, decimal_places=2, default=0)   # Oporeziove isporuke 25%
    hr_i2_taxable = models.DecimalField(max_digits=14, decimal_places=2, default=0)   # Oporeziove isporuke 13%
    hr_i3_taxable = models.DecimalField(max_digits=14, decimal_places=2, default=0)   # Oporeziove isporuke 5%
    hr_ii_exempt = models.DecimalField(max_digits=14, decimal_places=2, default=0)    # Oslobodene isporuke
    hr_iii_export = models.DecimalField(max_digits=14, decimal_places=2, default=0)   # Izvoz
    hr_pdv_due = models.DecimalField(max_digits=14, decimal_places=2, default=0)      # PDV za uplatu
    hr_pdv_input = models.DecimalField(max_digits=14, decimal_places=2, default=0)    # Pretporez
    hr_pdv_net = models.DecimalField(max_digits=14, decimal_places=2, default=0)      # Neto za uplatu

    # DE UStVA polja
    de_81_taxable = models.DecimalField(max_digits=14, decimal_places=2, default=0)   # 19% Umsatz
    de_86_taxable = models.DecimalField(max_digits=14, decimal_places=2, default=0)   # 7% Umsatz
    de_mwst_due = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    de_vorsteuer = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    submitted_at = models.DateTimeField(null=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    xml_content = models.TextField(blank=True)  # archive of submitted XML
    reference_number = models.CharField(max_length=50, blank=True)

    class Meta:
        unique_together = [("company", "return_type", "period_year", "period_month")]

    @property
    def period_display(self):
        import calendar
        return f"{calendar.month_name[self.period_month]} {self.period_year}"
```

## PDVCalculateView — auto-izračun iz faktura
```python
class PDVCalculateView(TenantView):
    """HTMX endpoint — vraća JSON s izračunatim poljima za odabrani period."""

    def get(self, request, year, month):
        from django.db.models import Sum, Q
        from invoicing.models import Invoice

        # Izlazni PDV (prodaja)
        issued = Invoice.objects.filter(
            company=request.company,
            issue_date__year=year,
            issue_date__month=month,
            status="paid",
            invoice_type__in=["R1", "R2"],
        )

        i1 = issued.filter(vat_rate=Decimal("0.25")).aggregate(
            s=Sum("net_amount"))["s"] or Decimal("0")
        i2 = issued.filter(vat_rate=Decimal("0.13")).aggregate(
            s=Sum("net_amount"))["s"] or Decimal("0")
        i3 = issued.filter(vat_rate=Decimal("0.05")).aggregate(
            s=Sum("net_amount"))["s"] or Decimal("0")

        pdv_due = (i1 * Decimal("0.25") + i2 * Decimal("0.13") + i3 * Decimal("0.05")).quantize(Decimal("0.01"))

        # Ulazni PDV (nabava) — iz ArhivaEntry
        from arhiva.models import ArhivaEntry
        input_vat = ArhivaEntry.objects.filter(
            company=request.company,
            document_date__year=year,
            document_date__month=month,
            doc_type__in=["ulazni_racun", "troskovi"],
        ).aggregate(s=Sum("ai_vat_amount"))["s"] or Decimal("0")

        return JsonResponse({
            "hr_i1_taxable": str(i1),
            "hr_i2_taxable": str(i2),
            "hr_i3_taxable": str(i3),
            "hr_pdv_due": str(pdv_due),
            "hr_pdv_input": str(input_vat),
            "hr_pdv_net": str((pdv_due - input_vat).quantize(Decimal("0.01"))),
        })
```

## HR PDV-S XML generator
```python
def generate_pdv_s_xml(vat_return: VATReturn) -> str:
    """Generira PDV-S XML za ePorezna prema shemi Porezne uprave."""
    company = vat_return.company
    period = f"{vat_return.period_year}{vat_return.period_month:02d}"

    root = ET.Element("PDVObrazac")
    root.set("xmlns", "http://e-porezna.porezna-uprava.hr/sheme/zahtjevi/PDV/v2-0")

    zaglavlje = ET.SubElement(root, "Zaglavlje")
    ET.SubElement(zaglavlje, "Porezni_obveznik_OIB").text = company.oib
    ET.SubElement(zaglavlje, "Naziv").text = company.name
    ET.SubElement(zaglavlje, "Adresa").text = company.address or ""
    ET.SubElement(zaglavlje, "Razdoblje").text = period

    # Sekcija I — Oporeziove isporuke
    i_sekcija = ET.SubElement(root, "I_OporeziveIsporuke")
    ET.SubElement(i_sekcija, "I_1_Osnovica").text = str(vat_return.hr_i1_taxable)
    ET.SubElement(i_sekcija, "I_1_Porez").text = str(
        (vat_return.hr_i1_taxable * Decimal("0.25")).quantize(Decimal("0.01")))
    ET.SubElement(i_sekcija, "I_2_Osnovica").text = str(vat_return.hr_i2_taxable)
    ET.SubElement(i_sekcija, "I_2_Porez").text = str(
        (vat_return.hr_i2_taxable * Decimal("0.13")).quantize(Decimal("0.01")))
    ET.SubElement(i_sekcija, "I_3_Osnovica").text = str(vat_return.hr_i3_taxable)
    ET.SubElement(i_sekcija, "I_3_Porez").text = str(
        (vat_return.hr_i3_taxable * Decimal("0.05")).quantize(Decimal("0.01")))

    # Sekcija PDV za uplatu / pretporez
    pdv_sekcija = ET.SubElement(root, "PDV_ZaUplatuPovrat")
    ET.SubElement(pdv_sekcija, "Obveza_PDV").text = str(vat_return.hr_pdv_due)
    ET.SubElement(pdv_sekcija, "Pretporez").text = str(vat_return.hr_pdv_input)
    ET.SubElement(pdv_sekcija, "Razlika").text = str(vat_return.hr_pdv_net)

    return ET.tostring(root, encoding="unicode", xml_declaration=True)
```

## DE UStVA ELSTER export
```python
def generate_ustvar_elster(vat_return: VATReturn) -> str:
    """
    Generira ELSTER UStVA XML.
    VAŽNO: Ovo je simplified format — za produkciju potrebna
    ELSTER ERiC biblioteka ili ELSTER API integracija.
    """
    company = vat_return.company
    kz_81 = str(int(vat_return.de_81_taxable * 100))  # ELSTER koristi centi
    kz_61 = str(int(vat_return.de_mwst_due * 100))
    kz_66 = str(int(vat_return.de_vorsteuer * 100))

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Elster xmlns="http://www.elster.de/elsterxml/schema/v12">
  <TransferHeader version="12">
    <Verfahren>ElsterAnmeldung</Verfahren>
    <DatenArt>UStVA</DatenArt>
    <Vorgang>send-Auth</Vorgang>
  </TransferHeader>
  <DatenTeil>
    <Nutzdatenblock>
      <NutzdatenHeader version="11">
        <NutzdatenTicket>1</NutzdatenTicket>
        <Empfaenger id="F">{company.de_finanzamt_nummer or '0000'}</Empfaenger>
      </NutzdatenHeader>
      <Nutzdaten>
        <Anmeldungssteuern art="UStVA" version="202401">
          <DatenLieferant>
            <Name>{company.name}</Name>
            <Steuernummer>{company.de_steuernummer or ''}</Steuernummer>
          </DatenLieferant>
          <Steuerfall>
            <Umsatzsteuervoranmeldung>
              <Jahr>{vat_return.period_year}</Jahr>
              <Zeitraum>{vat_return.period_month:02d}</Zeitraum>
              <Kz81>{kz_81}</Kz81>
              <Kz61>{kz_61}</Kz61>
              <Kz66>{kz_66}</Kz66>
            </Umsatzsteuervoranmeldung>
          </Steuerfall>
        </Anmeldungssteuern>
      </Nutzdaten>
    </Nutzdatenblock>
  </DatenTeil>
</Elster>"""
    return xml
```

## UI: PDVCreateView
- Alpine.js wizard:
  1. Odaberi period (month/year dropdown)
  2. Klik "Izračunaj automatski" → HTMX poziv PDVCalculateView → popuni polja
  3. Korisnik može ručno korigirati
  4. Spremi + XML download
- Polja grupirana po sekcijama PDV obrasca
- Totali se računaju u realnom vremenu
- Gumb "Preuzmi XML" → download za manuelni upload na ePorezna
- Gumb "Arhiviraj" → spremi XML u ArhivaEntry (ZOR retention)

## Arhiviranje submita
```python
class PDVSubmitView(TenantView):
    def post(self, request, pk):
        vat = get_object_or_404(VATReturn, id=pk, company=request.company, status="draft")
        xml = generate_pdv_s_xml(vat)

        # Arhiviraj u ArhivaEntry
        ArhivaEntry.objects.create(
            company=request.company,
            doc_type="pdv_prijava",
            document_number=f"PDV-{vat.period_year}-{vat.period_month:02d}",
            document_date=date.today(),
            description=f"PDV-S prijava za {vat.period_display}",
            created_by=request.user,
            # file se generira i sprema na S3/local
        )

        vat.xml_content = xml
        vat.status = VATReturn.Status.SUBMITTED
        vat.submitted_at = timezone.now()
        vat.submitted_by = request.user
        vat.save()

        return JsonResponse({"ok": True, "message": "PDV prijava arhivirana."})
```

## Testovi
```python
def test_pdv_calculate_sums_invoices(auth_client, company):
    # 3 fakture sa različitim stopama → točan izračun
    ...

def test_pdv_xml_valid_structure(company):
    vat = VATReturnFactory(company=company)
    xml = generate_pdv_s_xml(vat)
    root = ET.fromstring(xml)
    assert root.tag.endswith("PDVObrazac")
    ...

def test_pdv_unique_per_period(company):
    VATReturn.objects.create(company=company, period_year=2026, period_month=1, ...)
    with pytest.raises(IntegrityError):
        VATReturn.objects.create(company=company, period_year=2026, period_month=1, ...)
```
