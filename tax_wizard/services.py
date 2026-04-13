"""
tax_wizard/services.py — PO-SD kalkulacija, AI Advisor, XML generator

Tri komponente:
  1. POSDCalculator — izračun poreza po tieru
  2. AIAdvisor — "The Cliff" detektor + olakšice
  3. POSDXmlGenerator — XML za ePorezna upload

PRAVNI ŠTIT: AI nikada ne "preporučuje" — samo "simulacija pokazuje".
"""

import logging
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from xml.etree.ElementTree import Element, SubElement, tostring

from django.utils import timezone

from tax_wizard.models import PausalTier, TaxAuditLog, TaxWizardSession

logger = logging.getLogger(__name__)

_Q = Decimal("0.01")
ZERO = Decimal("0.00")
PAUSAL_LIMIT = Decimal("60000")


# ═══════════════════════════════════════════════════════════════
#  1. PO-SD KALKULATOR
# ═══════════════════════════════════════════════════════════════


class POSDCalculator:
    """
    Izračunaj porez za paušalnog obrtnika na temelju ukupnih primitaka.

    Input: q1, q2, q3, q4 (EUR)
    Output: tier, annual_tax, monthly_tax, already_paid, difference
    """

    def __init__(self, year: int = None):
        self.year = year or timezone.now().year

    def calculate(self, q1: Decimal, q2: Decimal, q3: Decimal, q4: Decimal, already_paid: Decimal = ZERO) -> dict:
        """
        Puni izračun PO-SD obrasca.

        Returns dict s svim poljima potrebnim za XML/PDF.
        """
        total = (q1 + q2 + q3 + q4).quantize(_Q, rounding=ROUND_HALF_UP)

        # Tier lookup
        tier = PausalTier.get_tier_for_income(total, self.year)

        if not tier:
            # Iznad 60K — nije paušalac
            return {
                "ukupni_primitak": total,
                "porezni_razred": 0,
                "godisnji_porez": ZERO,
                "mjesecni_porez": ZERO,
                "vec_placeni_porez": already_paid,
                "razlika": ZERO,
                "monthly_contributions": ZERO,
                "annual_contributions": ZERO,
                "total_annual_cost": ZERO,
                "exceeds_limit": True,
                "error": "Primitci prelaze 60.000 EUR — paušalni obrt nije moguć.",
            }

        annual_tax = tier.annual_tax
        difference = (annual_tax - already_paid).quantize(_Q, rounding=ROUND_HALF_UP)
        annual_contributions = (tier.monthly_contributions * 12).quantize(_Q)

        return {
            "ukupni_primitak": total,
            "q1_primitak": q1,
            "q2_primitak": q2,
            "q3_primitak": q3,
            "q4_primitak": q4,
            "porezni_razred": tier.tier_number,
            "tier_min": tier.min_income,
            "tier_max": tier.max_income,
            "godisnji_porez": annual_tax,
            "mjesecni_porez": tier.monthly_tax,
            "vec_placeni_porez": already_paid,
            "razlika": difference,
            "monthly_contributions": tier.monthly_contributions,
            "annual_contributions": annual_contributions,
            "total_annual_cost": (annual_tax + annual_contributions).quantize(_Q),
            "exceeds_limit": False,
            "error": None,
        }


# ═══════════════════════════════════════════════════════════════
#  2. AI ADVISOR — "The Cliff" detektor
# ═══════════════════════════════════════════════════════════════


class AIAdvisor:
    """
    Generira AI poruke (ne savjete!) za wizard.

    Pravni štit:
      ✗ "Preporučujem da smanjite primitke"
      ✓ "Simulacija pokazuje da bi 500€ manje primitaka rezultiralo nižim razredom"

    Checks:
      1. The Cliff — blizu granice razreda (±500€)
      2. The Wall — blizu 60K limita (>50K)
      3. Trend — usporedba s prošlom godinom
      4. Potpomognuto područje — viši osobni odbitak
    """

    # Poruka threshold
    CLIFF_THRESHOLD = Decimal("500")  # EUR od granice razreda
    WALL_WARNING = Decimal("50000")  # EUR — upozorenje na 60K limit

    def __init__(self, year: int = None):
        self.year = year or timezone.now().year
        self.tiers = list(PausalTier.get_all_tiers(self.year))

    def analyze(self, calculation: dict, company=None) -> list:
        """
        Analiziraj izračun i generiraj poruke.

        Returns list of dicts: [{"type": "warning|info|success|simulation", "message": "...", "code": "..."}]
        """
        messages = []
        total = Decimal(str(calculation.get("ukupni_primitak", 0)))
        tier_num = calculation.get("porezni_razred", 0)

        # ── Check 1: EXCEEDS LIMIT ──────────────────────────────────
        if calculation.get("exceeds_limit"):
            messages.append(
                {
                    "type": "error",
                    "code": "exceeds_60k",
                    "message": (
                        f"Ukupni primitci ({total:,.2f} EUR) prelaze zakonski limit "
                        f"od 60.000 EUR za paušalni obrt. Prema čl. 82. Zakona o porezu "
                        f"na dohodak, obvezni ste prijeći na vođenje poslovnih knjiga. "
                        f"Kontaktirajte svog računovođu za prijelaz na redovno oporezivanje."
                    ),
                }
            )
            return messages

        # ── Check 2: THE WALL — blizu 60K ───────────────────────────
        if total >= self.WALL_WARNING:
            remaining = PAUSAL_LIMIT - total
            messages.append(
                {
                    "type": "warning",
                    "code": "near_60k",
                    "message": (
                        f"Primitci ({total:,.2f} EUR) su {remaining:,.2f} EUR ispod "
                        f"zakonskog limita od 60.000 EUR. Ako primitci prijeđu ovaj "
                        f"iznos, obvezni ste voditi poslovne knjige i prijeći na "
                        f"redovno oporezivanje. Ovo je informativni izračun, ne pravni savjet."
                    ),
                }
            )

        # ── Check 3: THE CLIFF — blizu granice razreda ──────────────
        current_tier = None
        lower_tier = None
        for t in self.tiers:
            if t.tier_number == tier_num:
                current_tier = t
            if t.tier_number == tier_num - 1:
                lower_tier = t

        if current_tier and lower_tier:
            distance_to_lower = total - current_tier.min_income
            if distance_to_lower <= self.CLIFF_THRESHOLD:
                savings = current_tier.annual_tax - lower_tier.annual_tax
                messages.append(
                    {
                        "type": "simulation",
                        "code": "cliff_lower_tier",
                        "message": (
                            f"Primitci ({total:,.2f} EUR) su {distance_to_lower:,.2f} EUR "
                            f"iznad granice razreda {lower_tier.tier_number} "
                            f"({lower_tier.max_income:,.2f} EUR). "
                            f"Simulacija pokazuje da bi razred {lower_tier.tier_number} "
                            f"rezultirao s {savings:,.2f} EUR manjim godišnjim porezom "
                            f"({lower_tier.annual_tax:,.2f} EUR umjesto "
                            f"{current_tier.annual_tax:,.2f} EUR). "
                            f"Ovo je informativni izračun, ne pravni savjet."
                        ),
                    }
                )

        # ── Check 4: THE CLIFF — blizu granice VIŠEG razreda ────────
        upper_tier = None
        for t in self.tiers:
            if t.tier_number == tier_num + 1:
                upper_tier = t

        if current_tier and upper_tier:
            distance_to_upper = current_tier.max_income - total
            if distance_to_upper <= self.CLIFF_THRESHOLD:
                extra_tax = upper_tier.annual_tax - current_tier.annual_tax
                messages.append(
                    {
                        "type": "info",
                        "code": "cliff_upper_tier",
                        "message": (
                            f"Primitci ({total:,.2f} EUR) su {distance_to_upper:,.2f} EUR "
                            f"ispod granice razreda {upper_tier.tier_number} "
                            f"({upper_tier.min_income:,.2f} EUR). "
                            f"Prelazak u razred {upper_tier.tier_number} značio bi "
                            f"{extra_tax:,.2f} EUR veći godišnji porez. "
                            f"Ovo je informativni izračun, ne pravni savjet."
                        ),
                    }
                )

        # ── Check 5: POTPOMOGNUTO PODRUČJE ──────────────────────────
        if company:
            from tax_wizard.models import PotpomognutoPodručje

            zip_code = getattr(company, "zip_code", "")
            if zip_code:
                pp = PotpomognutoPodručje.find_by_zip(zip_code)
                if pp:
                    messages.append(
                        {
                            "type": "success",
                            "code": "potpomognuto",
                            "message": (
                                f"Sjedište obrta ({pp.name}, {pp.county}) je na "
                                f"potpomognutom području ({pp.get_group_display()}). "
                                f"Prema važećim propisima, osobni odbitak iznosi "
                                f"{pp.osobni_odbitak:,.2f} EUR mjesečno umjesto "
                                f"standardnih 600 EUR. Ako podnosite DOH obrazac, "
                                f"ova olakšica se automatski primjenjuje."
                            ),
                        }
                    )

        # ── Check 6: RAZLIKA ZA UPLATU/POVRAT ──────────────────────
        razlika = Decimal(str(calculation.get("razlika", 0)))
        if razlika > 0:
            messages.append(
                {
                    "type": "info",
                    "code": "payment_due",
                    "message": (
                        f"Prema izračunu, razlika za uplatu iznosi {razlika:,.2f} EUR. "
                        f"Ovo je razlika između godišnje obveze ({calculation.get('godisnji_porez', 0):,.2f} EUR) "
                        f"i već plaćenih predujmova ({calculation.get('vec_placeni_porez', 0):,.2f} EUR)."
                    ),
                }
            )
        elif razlika < 0:
            messages.append(
                {
                    "type": "success",
                    "code": "refund_due",
                    "message": (
                        f"Prema izračunu, imate pravo na povrat od {abs(razlika):,.2f} EUR. "
                        f"Platili ste više predujmova ({calculation.get('vec_placeni_porez', 0):,.2f} EUR) "
                        f"nego što iznosi godišnja obveza ({calculation.get('godisnji_porez', 0):,.2f} EUR)."
                    ),
                }
            )

        # ── Check 7: NEMA PRIMITAKA ─────────────────────────────────
        if total == 0:
            messages.append(
                {
                    "type": "info",
                    "code": "zero_income",
                    "message": (
                        "Primitci su 0 EUR. Ako ste imali poslovnu aktivnost u "
                        f"{self.year}. godini, provjerite jesu li svi računi uneseni "
                        "i označeni kao plaćeni u sustavu. PO-SD se mora podnijeti "
                        "i ako su primitci 0."
                    ),
                }
            )

        # ── Uvijek: SUCCESS poruka na kraju ─────────────────────────
        if not any(m["type"] == "error" for m in messages):
            messages.append(
                {
                    "type": "success",
                    "code": "calculation_ok",
                    "message": (
                        f"Izračun je završen. Razred {tier_num}, "
                        f"godišnji porez {calculation.get('godisnji_porez', 0):,.2f} EUR, "
                        f"ukupni godišnji troškovi (porez + doprinosi) "
                        f"{calculation.get('total_annual_cost', 0):,.2f} EUR."
                    ),
                }
            )

        return messages


# ═══════════════════════════════════════════════════════════════
#  3. PO-SD XML GENERATOR
# ═══════════════════════════════════════════════════════════════


class POSDXmlGenerator:
    """
    Generira PO-SD XML za upload na ePorezna.

    Format prema Pravilniku o paušalnom oporezivanju (NN 1/20, 156/22, 143/23).
    """

    def generate(self, session: TaxWizardSession) -> str:
        """Generiraj XML string iz wizard sesije."""
        data = session.form_data
        calc = session.calculated_results

        root = Element("PO-SD")
        root.set("xmlns", "http://e-porezna.porezna-uprava.hr/sheme/PO-SD/v1")
        root.set("verzija", "1.0")

        # Zaglavlje
        header = SubElement(root, "Zaglavlje")
        SubElement(header, "Oznaka").text = "PO-SD"
        SubElement(header, "PoreznaGodina").text = str(session.tax_year)
        SubElement(header, "DatumIzrade").text = date.today().strftime("%d.%m.%Y")

        # Obveznik
        obveznik = SubElement(root, "PodaciOObvezniku")
        SubElement(obveznik, "OIB").text = str(data.get("oib", ""))
        SubElement(obveznik, "ImePrezime").text = str(data.get("ime_prezime", ""))
        SubElement(obveznik, "Adresa").text = str(data.get("adresa", ""))
        SubElement(obveznik, "NazivObrta").text = str(data.get("naziv_obrta", ""))
        SubElement(obveznik, "DjelatnostNKD").text = str(data.get("djelatnost_nkd", ""))

        # Primitci po kvartalima
        primitci = SubElement(root, "Primitci")
        for q_num in range(1, 5):
            key = f"q{q_num}_primitak"
            val = Decimal(str(data.get(key, 0))).quantize(_Q)
            SubElement(primitci, f"Kvartal{q_num}").text = str(val)

        total = Decimal(str(calc.get("ukupni_primitak", 0))).quantize(_Q)
        SubElement(primitci, "UkupniPrimitak").text = str(total)

        # Porezni izračun
        porez = SubElement(root, "PorezniIzracun")
        SubElement(porez, "PorezniRazred").text = str(calc.get("porezni_razred", 0))
        SubElement(porez, "GodisnjiPorez").text = str(Decimal(str(calc.get("godisnji_porez", 0))).quantize(_Q))
        SubElement(porez, "VecPlaceniPredujam").text = str(Decimal(str(calc.get("vec_placeni_porez", 0))).quantize(_Q))
        razlika = Decimal(str(calc.get("razlika", 0))).quantize(_Q)
        SubElement(porez, "RazlikaZaUplatu").text = str(max(ZERO, razlika))
        SubElement(porez, "RazlikaZaPovrat").text = str(abs(min(ZERO, razlika)))

        xml_str = tostring(root, encoding="unicode", xml_declaration=False)
        xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str

        return xml_str


# ═══════════════════════════════════════════════════════════════
#  4. SESSION HELPER — Kreira/ažurira sesiju
# ═══════════════════════════════════════════════════════════════


def create_posd_session(user, company, year, referred_by=None, referral_company=None, locale="hr") -> TaxWizardSession:
    """Kreiraj novu PO-SD wizard sesiju."""
    import secrets

    from tax_wizard.models import TaxFormTemplate

    template = (
        TaxFormTemplate.objects.filter(
            form_type="PO-SD",
            is_active=True,
            valid_from__year__lte=year + 1,
        )
        .order_by("-valid_from")
        .first()
    )

    if not template:
        raise ValueError(f"Nema aktivnog PO-SD predloška za godinu {year}")

    session = TaxWizardSession.objects.create(
        session_key=secrets.token_urlsafe(32),
        user=user,
        company=company,
        template=template,
        tax_year=year,
        referred_by=referred_by,
        referral_company=referral_company,
        locale=locale,
    )

    # Audit log
    TaxAuditLog.objects.create(
        session=session,
        user=user,
        action="create",
        details={"form_type": "PO-SD", "year": year},
    )

    return session


def process_posd_step(session: TaxWizardSession, step: int, data: dict, user=None, ip_address=None) -> dict:
    """
    Procesira korak PO-SD wizarda.

    Returns dict: {ok: bool, session: dict, ai_messages: list, errors: list}
    """
    errors = []

    if not session.is_editable:
        return {"ok": False, "errors": ["Sesija je zaključana i ne može se mijenjati."]}

    # Merge podataka u form_data
    old_hash = session.data_hash
    session.form_data.update(data)

    # Step-specifična logika
    if step == 0:
        # Step 0: Osnovni podaci — validacija OIB-a
        oib = data.get("oib", "")
        if oib and len(oib) != 11:
            errors.append("OIB mora imati točno 11 znamenki.")
        if not data.get("ime_prezime", "").strip():
            errors.append("Ime i prezime je obavezno.")
        if not data.get("naziv_obrta", "").strip():
            errors.append("Naziv obrta je obavezan.")

    elif step == 1:
        # Step 1: Primitci — validacija iznosa
        total = ZERO
        for q in ["q1_primitak", "q2_primitak", "q3_primitak", "q4_primitak"]:
            val = Decimal(str(data.get(q, 0)))
            if val < 0:
                errors.append("Primitak za kvartal ne može biti negativan.")
                break
            total += val

        if total > PAUSAL_LIMIT:
            errors.append(
                f"Ukupni primitci ({total:,.2f} EUR) prelaze 60.000 EUR. "
                f"Paušalni obrt nije moguć — morate prijeći na redovne knjige."
            )

    elif step == 2:
        # Step 2: Izračun — automatski, nema user inputa osim vec_placeni_porez
        q1 = Decimal(str(session.form_data.get("q1_primitak", 0)))
        q2 = Decimal(str(session.form_data.get("q2_primitak", 0)))
        q3 = Decimal(str(session.form_data.get("q3_primitak", 0)))
        q4 = Decimal(str(session.form_data.get("q4_primitak", 0)))
        already_paid = Decimal(str(data.get("vec_placeni_porez", 0)))

        calculator = POSDCalculator(session.tax_year)
        calc_result = calculator.calculate(q1, q2, q3, q4, already_paid)

        # Spremi izračun
        # Convert Decimal to float for JSON serialization
        session.calculated_results = {k: float(v) if isinstance(v, Decimal) else v for k, v in calc_result.items()}

        # AI Advisor
        advisor = AIAdvisor(session.tax_year)
        ai_msgs = advisor.analyze(calc_result, session.company)

        # Spremi AI poruke
        for msg in ai_msgs:
            session.add_ai_message(step, msg["type"], msg["message"])

    elif step == 3:
        # Step 3: AI provjera — read-only, nema validacije
        pass

    elif step == 4:
        # Step 4: Preview — finalni pregled
        pass

    if errors:
        return {"ok": False, "errors": errors}

    # Update step
    if step >= session.current_step:
        session.current_step = step + 1

    session.save()

    # Audit log
    TaxAuditLog.objects.create(
        session=session,
        user=user,
        action="update",
        details={"step": step, "fields_updated": list(data.keys())},
        data_hash_before=old_hash,
        data_hash_after=session.data_hash,
        ip_address=ip_address,
    )

    return {
        "ok": True,
        "session": {
            "id": str(session.id),
            "current_step": session.current_step,
            "progress": session.progress_percent,
            "status": session.status,
            "form_data": session.form_data,
            "calculated_results": session.calculated_results,
        },
        "ai_messages": session.ai_messages[-5:] if session.ai_messages else [],
        "errors": [],
    }


def finalize_posd_session(session: TaxWizardSession, user=None) -> dict:
    """Finaliziraj PO-SD sesiju — generira XML, zaključava."""
    if session.status not in ("draft", "correction"):
        return {"ok": False, "error": "Sesija nije u statusu koji se može finalizirati."}

    # Generira XML
    generator = POSDXmlGenerator()
    xml_content = generator.generate(session)

    # Spremi XML u fajl
    from django.core.files.base import ContentFile

    filename = f"PO-SD_{session.company.oib}_{session.tax_year}.xml"
    session.xml_file.save(filename, ContentFile(xml_content.encode("utf-8")), save=False)

    # Promijeni status
    if session.referred_by:
        # B2B2C flow — ide na pregled računovođi
        session.status = "review"
    else:
        session.status = "final"

    session.finalized_at = timezone.now()
    session.save()

    # Audit log
    TaxAuditLog.objects.create(
        session=session,
        user=user,
        action="finalize",
        details={
            "status": session.status,
            "xml_filename": filename,
            "total": float(session.calculated_results.get("ukupni_primitak", 0)),
        },
        data_hash_after=session.data_hash,
    )

    return {"ok": True, "xml_filename": filename, "status": session.status}
