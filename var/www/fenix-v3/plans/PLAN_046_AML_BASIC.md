# PLAN_046 — AML Basic (Anti-Money Laundering — Osnovna Usklađenost)

## Cilj
Osnovna AML/KYC usklađenost za HR računovodstvene firme koje su obveznici prema Zakonu o sprečavanju pranja novca i financiranja terorizma (ZSPNFT). Nije full AML sustav — to je registracija obveznika, unos stranaka, screening lista, te flagging transakcija koje prelaze zakonski prag (10.000 EUR gotovina).

## Zakonski okvir (HR)
- ZSPNFT (NN 108/17, 39/19, 151/22)
- Obveznici: računovođe, porezni savjetnici
- Prag: gotovinska transakcija ≥ 10.000 EUR → obvezna prijava
- Evidencija stranke: ime, OIB/PassportNr, adresa, PEP status, dokument
- Čuvanje evidencije: min 5 godina

## Model
```python
class AMLProfile(TenantModel):
    """
    AML profil kompanije — obveze i konfiguracija.
    Jedan po company.
    """
    company = models.OneToOneField(Company, on_delete=models.CASCADE, related_name="aml_profile")
    is_obligor = models.BooleanField(default=False)  # je li obveznik ZSPNFT
    compliance_officer = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL
    )
    risk_appetite = models.CharField(
        max_length=10,
        choices=[("low", "Nizak"), ("medium", "Srednji"), ("high", "Visok")],
        default="low"
    )
    last_training_date = models.DateField(null=True)

class AMLParty(TenantModel):
    """
    KYC stranka — klijent ili dobavljač kojeg treba pratiti.
    """
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="aml_parties")

    class PartyType(models.TextChoices):
        INDIVIDUAL = "individual", "Fizička osoba"
        LEGAL = "legal", "Pravna osoba"

    class RiskLevel(models.TextChoices):
        LOW = "low", "Nizak"
        MEDIUM = "medium", "Srednji"
        HIGH = "high", "Visok"
        PEP = "pep", "PEP (politički izložena osoba)"

    party_type = models.CharField(max_length=20, choices=PartyType.choices)
    name = models.CharField(max_length=200)
    oib = models.CharField(max_length=11, blank=True)  # HR OIB ili strani ID
    passport_number = models.CharField(max_length=50, blank=True)
    country = models.CharField(max_length=3, default="HR")  # ISO 3166-1
    address = models.TextField(blank=True)
    risk_level = models.CharField(max_length=10, choices=RiskLevel.choices, default=RiskLevel.LOW)
    is_pep = models.BooleanField(default=False)
    is_sanctioned = models.BooleanField(default=False)
    kyc_verified_at = models.DateField(null=True)
    kyc_document_type = models.CharField(max_length=50, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = [("company", "oib")]

class AMLTransaction(TenantModel):
    """
    Transakcija koja podliježe AML praćenju.
    Auto-kreira se za gotovinske transakcije ≥ 10.000 EUR.
    """
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="aml_transactions")
    party = models.ForeignKey(AMLParty, null=True, on_delete=models.SET_NULL)
    transaction_date = models.DateField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, default="EUR")

    class TransactionType(models.TextChoices):
        CASH_IN = "cash_in", "Gotovinski primitak"
        CASH_OUT = "cash_out", "Gotovinska isplata"
        WIRE = "wire", "Bankovni transfer"

    transaction_type = models.CharField(max_length=20, choices=TransactionType.choices)
    description = models.TextField()
    reference = models.CharField(max_length=100, blank=True)

    class Status(models.TextChoices):
        FLAGGED = "flagged", "Označeno za pregled"
        REVIEWED = "reviewed", "Pregledano"
        REPORTED = "reported", "Prijavljeno HANFA-i"
        CLEARED = "cleared", "Riješeno — bez nalaza"

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.FLAGGED)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    reviewed_at = models.DateTimeField(null=True)
    hanfa_reference = models.CharField(max_length=50, blank=True)

    CASH_THRESHOLD = Decimal("10000.00")

    @classmethod
    def should_flag(cls, amount: Decimal, transaction_type: str) -> bool:
        return (transaction_type in ["cash_in", "cash_out"] and
                amount >= cls.CASH_THRESHOLD)
```

## Signal: auto-flag POS gotovinske transakcije
```python
# pos/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=POSTransaction)
def aml_flag_cash_transaction(sender, instance, created, **kwargs):
    if not created:
        return
    if instance.payment_method != "cash":
        return
    if not AMLTransaction.should_flag(instance.total, "cash_in"):
        return

    AMLTransaction.objects.get_or_create(
        company=instance.session.register.company,
        reference=str(instance.id),
        defaults={
            "transaction_date": instance.created_at.date(),
            "amount": instance.total,
            "transaction_type": AMLTransaction.TransactionType.CASH_IN,
            "description": f"POS gotovinska naplata > 10.000 EUR — transakcija {instance.reference_number}",
            "status": AMLTransaction.Status.FLAGGED,
        }
    )
```

## URL struktura
```
/hr/aml/                          → AMLDashboardView
/hr/aml/stranke/                  → AMLPartyListView
/hr/aml/stranke/nova/             → AMLPartyCreateView
/hr/aml/stranke/<uuid>/           → AMLPartyDetailView
/hr/aml/transakcije/              → AMLTransactionListView (flagged first)
/hr/aml/transakcije/<uuid>/review/ → AMLTransactionReviewView (POST)
/hr/aml/izvjestaj/                → AMLReportView (PDF za evidenciju)
```

## AMLDashboardView
```python
class AMLDashboardView(TenantView):
    permission_required = Permission.MANAGE_AML
    template_name = "aml/dashboard.html"

    def get(self, request):
        profile, _ = AMLProfile.objects.get_or_create(company=request.company)
        flagged = AMLTransaction.objects.filter(
            company=request.company,
            status=AMLTransaction.Status.FLAGGED
        ).count()
        pep_parties = AMLParty.objects.filter(
            company=request.company,
            is_pep=True
        ).count()
        high_risk = AMLParty.objects.filter(
            company=request.company,
            risk_level=AMLParty.RiskLevel.HIGH
        ).count()
        return render(request, self.template_name, {
            "profile": profile,
            "flagged_count": flagged,
            "pep_count": pep_parties,
            "high_risk_count": high_risk,
            "recent_flagged": AMLTransaction.objects.filter(
                company=request.company,
                status=AMLTransaction.Status.FLAGGED
            ).order_by("-transaction_date")[:10],
        })
```

## AML Risk Screening (basic)
```python
def screen_party(party: AMLParty) -> dict:
    """
    Osnovna provjera. U produkciji integrirati sa:
    - EU Sanctions List (europa.eu/consolidated-sanctions)
    - UN Security Council List
    - OFAC SDN List
    
    Za sada: regex provjera PEP titula u imenu.
    """
    PEP_KEYWORDS = ["ministar", "predsjednik", "gradonačelnik", "župan",
                    "zastupnik", "senator", "ambasador", "veleposlanik",
                    "minister", "president", "senator", "ambassador"]
    
    name_lower = party.name.lower()
    is_pep_by_name = any(kw in name_lower for kw in PEP_KEYWORDS)
    
    return {
        "is_pep": is_pep_by_name,
        "screening_note": "Automatska provjera ključnih riječi u imenu" if is_pep_by_name else "",
        "manual_review_needed": is_pep_by_name or party.country not in EU_COUNTRIES,
    }

EU_COUNTRIES = {"AT","BE","BG","CY","CZ","DE","DK","EE","ES","FI","FR","GR",
                "HR","HU","IE","IT","LT","LU","LV","MT","NL","PL","PT","RO",
                "SE","SI","SK"}
```

## Template: aml/dashboard.html
- Alert banner ako postoje flagged transakcije (btn-danger + broj)
- Widget grid (3 tile): Označene transakcije | PEP stranke | Visok rizik
- Tabela: posljednjih 10 flagged transakcija
- Quick link "Dodaj stranku" | "Pregled svih transakcija"
- Warning: "Nije zamjena za pravi AML sustav" — info badge

## PDF izvještaj (AMLReportView)
```python
class AMLReportView(TenantView):
    permission_required = Permission.MANAGE_AML

    def get(self, request):
        """Download PDF evidencije za regulatorne potrebe."""
        year = int(request.GET.get("year", date.today().year))
        transactions = AMLTransaction.objects.filter(
            company=request.company,
            transaction_date__year=year,
        ).order_by("transaction_date")
        
        html = render_to_string("aml/report_pdf.html", {
            "company": request.company,
            "transactions": transactions,
            "year": year,
            "generated_at": timezone.now(),
        })
        pdf = HTML(string=html).write_pdf()
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="AML-evidencija-{year}.pdf"'
        return response
```

## Permissions
```python
Permission.MANAGE_AML = "manage_aml"
# Roles: owner, admin
# Compliance officer (iz AMLProfile) dobiva poseban pristup
```

## NAPOMENE ZA IMPLEMENTACIJU
1. Ovo je **osnovna compliance** — nije certificiran AML sustav
2. Za stranke s visokim rizikom → uvijek tražiti manuelni review
3. Svi zapisi imaju retention 5 godina (soft delete + archive flag)
4. KYC dokumenti se čuvaju u ArhivaEntry (link AMLParty → ArhivaEntry)
5. Nikad ne implementiraj automatsku prijavu HANFA-i bez pravničkog review-a
