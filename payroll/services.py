"""
payroll/services.py — Calculation Engine

Tri funkcije koje pokrivaju cijeli payroll tok:

1. calculate_payslip(run, user)
   Agregira TimeEntry podatke i računa bruto/neto za jednog radnika.
   HR engine: doprinosi 20%, porez 20%/30%, prirez, osobni odbitak.
   DE engine: ne računa poreze, generira Bewegungsdaten za DATEV.

2. run_payroll(run)
   Pokreće calculate_payslip() za sve radnike kompanije.
   Koristi select_for_update() za atomarnost.

3. book_payroll_to_ledger(run)
   Kreira JournalEntry (source_type='payroll') u konto modulu:
     Duguje:    4000 Troškovi rada          (bruto_ukupno)
     Potražuje: 2300 Obveze prema radnicima (neto_ukupno)
     Potražuje: 2390 Obveze za doprinose    (doprinosi)
     Potražuje: 2400 Obveze za porez        (porez)

4. generate_datev_bewegungsdaten(run)
   CSV za njemački DATEV Lohn & Gehalt.
   Format: Personalnummer;Stunden;Überstunden;Nacht;Brutto

5. generate_pain001_salaries(run, bank_account)
   Delegira na Pain001Generator.generate_salary_payments() —
   ali sad koristi Payslip.net_amount umjesto TimeEntry agregata
   jer su iznosi već finalizirani i proknjiženi.
"""

from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from payroll.hr_calculator import OSOBNI_ODBITAK_BASE

# ── HR Porezni Engine ─────────────────────────────────────────────────────────


def hr_calculate_net(gross, personal_allowance=OSOBNI_ODBITAK_BASE, city_surtax_rate=Decimal("0.12")):
    """
    Hrvatska bruto→neto kalkulacija (NN 114/23 stope za 2024+).

    Doprinosi iz osnovice: 20% (MIO I + MIO II)
    Porezna osnovica = gross - doprinosi - osobni odbitak
    Porez na dohodak:
      do 50.400€/god (4.200€/mj): 20%
      iznad: 30%
    Prirez: na iznos poreza (Grad Zagreb=18%, Rijeka=15%, ostali 12%)

    Parametri:
      personal_allowance: osnovni odbitak (560€ = 1.0 × basic)
      city_surtax_rate: prirez (default 12% — konzervativna procjena)

    Vraća dict s potpunom razradom.
    """
    gross = gross.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # Doprinosi iz osnovice: 20%
    contributions = (gross * Decimal("0.20")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # Porezna osnovica
    tax_base = max(Decimal("0"), gross - contributions - personal_allowance)
    tax_base = tax_base.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # Stopa poreza: 20% do 4200€/mj, 30% iznad
    threshold = Decimal("4200.00")
    if tax_base <= threshold:
        income_tax = (tax_base * Decimal("0.20")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    else:
        income_tax = (threshold * Decimal("0.20") + (tax_base - threshold) * Decimal("0.30")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    # Prirez (na iznos poreza)
    surtax = (income_tax * city_surtax_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    total_tax = income_tax + surtax
    net = gross - contributions - total_tax

    return {
        "gross": gross,
        "contributions": contributions,
        "tax_base": tax_base,
        "income_tax": income_tax,
        "surtax": surtax,
        "total_tax": total_tax,
        "net": net.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
    }


# ── Calculation Engine ────────────────────────────────────────────────────────


@transaction.atomic
def calculate_payslip(payroll_run, user):
    """
    Kreira ili ažurira Payslip za jednog radnika za dani PayrollRun.

    Agregira TimeEntry(status='APPROVED') za period.
    Računa bruto iz sati × satnica (snapshot iz EmployeeProfile).
    Za HR kompanije: primjenjuje hr_calculate_net().
    Za DE kompanije: neto = bruto (DATEV odrađuje poreze).
    """
    import calendar
    import datetime

    from worktime.models import EmployeeProfile, TimeEntry

    from .models import Payslip

    # PAYROLL GILJOTINA: Volonteri se NE obracunavaju!
    if hasattr(user, "employeeprofile") and user.employeeprofile.is_volunteer:
        import logging

        logging.getLogger("payroll").info("PAYROLL BYPASS: %s je volonter — preskocen obracun place.", user)
        return None

    year, month = payroll_run.year, payroll_run.month
    last_day = calendar.monthrange(year, month)[1]
    period_start = datetime.date(year, month, 1)
    period_end = datetime.date(year, month, last_day)

    # Agregiraj odobrene sate za period
    agg = TimeEntry.objects.filter(
        company=payroll_run.company,
        user=user,
        status="APPROVED",
        date__range=(period_start, period_end),
    ).aggregate(
        total_regular=Sum("regular_hours"),
        total_overtime=Sum("overtime_hours"),
        total_night=Sum("night_hours"),
    )

    regular_h = agg["total_regular"] or Decimal("0")
    overtime_h = agg["total_overtime"] or Decimal("0")
    night_h = agg["total_night"] or Decimal("0")
    total_h = regular_h + overtime_h

    # Satnice — snapshot iz EmployeeProfile
    try:
        emp = EmployeeProfile.objects.get(user=user, company=payroll_run.company)
        base_rate = emp.hourly_rate or Decimal("20")
        ot_rate = emp.overtime_rate or Decimal("30")
        emp_iban = emp.bank_account or ""
        personal_allowance = emp.personal_allowance
    except EmployeeProfile.DoesNotExist:
        base_rate = Decimal("20")
        ot_rate = Decimal("30")
        emp_iban = ""
        personal_allowance = OSOBNI_ODBITAK_BASE

    # Noćni bonus: +25% na baznu satnicu
    night_bonus_rate = base_rate * Decimal("0.25")

    gross = (regular_h * base_rate + overtime_h * ot_rate + night_h * night_bonus_rate).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    # ArbZG/ZOR compliance — skupi upozorenja iz perioda
    compliance_entries = (
        TimeEntry.objects.filter(
            company=payroll_run.company,
            user=user,
            date__range=(period_start, period_end),
        )
        .exclude(compliance_note="")
        .values_list("date", "compliance_note")
    )
    compliance_notes = "; ".join(f"{d}: {n}" for d, n in compliance_entries[:10])

    # Porezni engine
    country = getattr(payroll_run.company, "country", "HR")
    if country == "HR":
        tax_calc = hr_calculate_net(gross, personal_allowance)
        contributions = tax_calc["contributions"]
        tax_base_amt = tax_calc["tax_base"]
        tax_amt = tax_calc["total_tax"]
        net = tax_calc["net"]
    else:
        # DE: DATEV odrađuje poreze — mi samo bilježimo bruto
        contributions = Decimal("0")
        tax_base_amt = gross
        tax_amt = Decimal("0")
        net = gross  # placeholder dok DATEV ne vrati stvarne iznose

    # Kreiraj ili ažuriraj Payslip
    payslip, _ = Payslip.objects.update_or_create(
        payroll_run=payroll_run,
        user=user,
        defaults=dict(
            regular_hours=regular_h,
            overtime_hours=overtime_h,
            night_hours=night_h,
            total_hours=total_h,
            hourly_rate_snapshot=base_rate,
            overtime_rate_snapshot=ot_rate,
            gross_amount=gross,
            contributions_amount=contributions,
            tax_base=tax_base_amt,
            tax_amount=tax_amt,
            net_amount=net,
            employee_iban=emp_iban,
            compliance_notes=compliance_notes,
        ),
    )
    return payslip


@transaction.atomic
def run_payroll(payroll_run):
    """
    Pokreće obračun za sve radnike kompanije.
    Zaključava run za izmjene (select_for_update).
    """
    from worktime.models import EmployeeProfile

    # Lock run
    run = (
        __import__("payroll.models", fromlist=["PayrollRun"])
        .PayrollRun.objects.select_for_update()
        .get(pk=payroll_run.pk)
    )

    if run.status not in ("DRAFT", "LOCKED"):
        raise ValueError(f"Ne može se pokrenuti obračun: status={run.status}")

    run.status = "LOCKED"
    run.save(update_fields=["status"])

    # Svi aktivni radnici kompanije s EmployeeProfile
    employees = EmployeeProfile.objects.filter(company=payroll_run.company).select_related("user")

    payslips = []
    for emp in employees:
        ps = calculate_payslip(payroll_run, emp.user)
        payslips.append(ps)

    # Ažuriraj agregirane iznose na run-u
    from .models import Payslip

    agg = Payslip.objects.filter(payroll_run=payroll_run).aggregate(
        tg=Sum("gross_amount"),
        tn=Sum("net_amount"),
        tt=Sum("tax_amount"),
    )
    run.total_gross = agg["tg"] or Decimal("0")
    run.total_net = agg["tn"] or Decimal("0")
    run.total_tax = agg["tt"] or Decimal("0")
    run.status = "FINALIZED"
    run.finalized_at = timezone.now()
    run.save(update_fields=["total_gross", "total_net", "total_tax", "status", "finalized_at"])

    return payslips


@transaction.atomic
def book_payroll_to_ledger(payroll_run, user=None):
    """
    Kreira JournalEntry (source_type='payroll') za finalizirani run.

    Duguje:    4000 Troškovi rada            (total_gross)
    Potražuje: 2300 Obveze prema radnicima   (total_net)
    Potražuje: 2390 Obveze za doprinose      (total_contributions)
    Potražuje: 2400 Obveze za porez/prirez   (total_tax)

    Idempotentno: ako entry već postoji za ovaj run, preskače.
    """
    from konto.models import AccountType, JournalEntry, KontoAccount, LedgerLine
    from konto.services import _next_entry_number

    company = payroll_run.company
    if payroll_run.status not in ("FINALIZED", "PAID"):
        raise ValueError("Samo finalizirani run može se knjižiti.")

    # Idempotentnost
    existing = JournalEntry.objects.filter(
        company=company,
        source_type="payroll",
        description__contains=str(payroll_run.pk),
    ).first()
    if existing:
        return existing

    # Agregiraj doprinose iz payslipova
    from django.db.models import Sum

    from .models import Payslip

    agg = Payslip.objects.filter(payroll_run=payroll_run).aggregate(tc=Sum("contributions_amount"))
    total_contributions = agg["tc"] or Decimal("0")
    total_gross = payroll_run.total_gross
    total_net = payroll_run.total_net
    total_tax = payroll_run.total_tax

    def get_or_create_account(code, name, atype):
        obj, _ = KontoAccount.objects.get_or_create(
            company=company, code=code, defaults={"name": name, "account_type": atype, "is_active": True}
        )
        return obj

    acct_troskovi = get_or_create_account("4000", "Troškovi rada", AccountType.EXPENSE)
    acct_obveze = get_or_create_account("2300", "Obveze prema radnicima", AccountType.LIABILITY)
    acct_doprinosi = get_or_create_account("2390", "Obveze za doprinose", AccountType.LIABILITY)
    acct_porez = get_or_create_account("2400", "Obveze za porez/prirez", AccountType.LIABILITY)

    import datetime

    entry = JournalEntry.objects.create(
        company=company,
        entry_number=_next_entry_number(company, "PLACA"),
        date=datetime.date(
            payroll_run.year,
            payroll_run.month,
            __import__("calendar").monthrange(payroll_run.year, payroll_run.month)[1],
        ),
        source_type="payroll",
        description=f"Obračun plaća {payroll_run.month:02d}/{payroll_run.year} (run #{payroll_run.pk})",
        created_by=user,
        is_posted=True,
    )

    # Duguje: 4000 — cijeli bruto trošak
    LedgerLine.objects.create(journal_entry=entry, account=acct_troskovi, side="debit", amount=total_gross)

    # Potražuje: 2300 — neto isplata radnicima
    LedgerLine.objects.create(journal_entry=entry, account=acct_obveze, side="credit", amount=total_net)

    # Potražuje: 2390 — doprinosi (ako > 0)
    if total_contributions > 0:
        LedgerLine.objects.create(
            journal_entry=entry, account=acct_doprinosi, side="credit", amount=total_contributions
        )

    # Potražuje: 2400 — porez
    if total_tax > 0:
        LedgerLine.objects.create(journal_entry=entry, account=acct_porez, side="credit", amount=total_tax)

    return entry


def generate_datev_bewegungsdaten(payroll_run):
    """
    Generira Bewegungsdaten CSV za DATEV Lohn & Gehalt.
    Format koji prihvaća svaki DATEV od 4.0+:
      Personalnummer;Vorname;Nachname;Stunden;Ueberstunden;Nachtstunden;Brutto

    Vraća: CSV string (UTF-8-sig za Windows kompatibilnost).
    """
    import csv
    import io

    from .models import Payslip

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";", quoting=csv.QUOTE_MINIMAL)

    # Header
    writer.writerow(
        [
            "Personalnummer",
            "Vorname",
            "Nachname",
            "Stunden",
            "Ueberstunden",
            "Nachtstunden",
            "Brutto",
            "Abrechnungsmonat",
        ]
    )

    payslips = (
        Payslip.objects.filter(payroll_run=payroll_run)
        .select_related("user", "user__employeeprofile")
        .order_by("user__last_name")
    )

    for ps in payslips:
        try:
            emp_id = ps.user.employeeprofile.employee_id or str(ps.user.pk)
        except (ValueError, TypeError):
            emp_id = str(ps.user.pk)

        writer.writerow(
            [
                emp_id,
                ps.user.first_name,
                ps.user.last_name,
                str(ps.regular_hours),
                str(ps.overtime_hours),
                str(ps.night_hours),
                str(ps.gross_amount),
                f"{payroll_run.month:02d}/{payroll_run.year}",
            ]
        )

    # UTF-8-sig: BOM za Excel/DATEV na Windowsu
    return "\ufeff" + output.getvalue()


def generate_pain001_from_run(payroll_run, bank_account):
    """
    Generira pain.001 SEPA XML za isplatu neto plaća.
    Koristi Payslip.net_amount (finalizirani iznos),
    ne TimeEntry agregat (koji je samo bruto).
    """
    import datetime

    from finance.bank_parsers import Pain001Generator

    from .models import Payslip

    if payroll_run.status not in ("FINALIZED", "PAID"):
        raise ValueError("Obračun mora biti finaliziran.")

    payslips = (
        Payslip.objects.filter(
            payroll_run=payroll_run,
            is_paid=False,
        )
        .exclude(employee_iban="")
        .select_related("user")
    )

    if not payslips.exists():
        raise ValueError("Nema neisplaćenih listića s IBAN-om.")

    # Pretvori Payslip → payment dict za _build_xml
    import calendar

    last_day = calendar.monthrange(payroll_run.year, payroll_run.month)[1]
    datetime.date(payroll_run.year, payroll_run.month, 1)
    datetime.date(payroll_run.year, payroll_run.month, last_day)

    gen = Pain001Generator(
        company=payroll_run.company,
        bank_account=bank_account,
    )

    # Interna metoda — koristimo direktno _build_xml s payslip podacima
    payments = []
    for ps in payslips:
        payments.append(
            {
                "end_to_end_id": f"SALA-{ps.user.pk}-{payroll_run.month:02d}{payroll_run.year}",
                "amount": ps.net_amount,
                "currency": "EUR",
                "cdtr_name": (ps.user.get_full_name() or ps.user.username)[:70],
                "cdtr_iban": ps.employee_iban.replace(" ", "").upper(),
                "cdtr_bic": "",
                "remittance_info": f"Placa {payroll_run.month:02d}/{payroll_run.year}",
                "purpose_code": "SALA",
            }
        )

    xml_bytes = gen._build_xml(payments, purpose_batch="SALA")

    # Označi run kao PAID i zabilježi batch
    import uuid

    batch_id = str(uuid.uuid4())[:8]
    payroll_run.status = "PAID"
    payroll_run.pain001_generated_at = __import__("django.utils.timezone", fromlist=["now"]).now()
    payroll_run.pain001_batch_id = batch_id
    payroll_run.save(update_fields=["status", "pain001_generated_at", "pain001_batch_id"])

    # Označi listiće kao plaćene
    payslips.update(is_paid=True, payment_reference=f"SALA-{batch_id}")

    return xml_bytes, batch_id
