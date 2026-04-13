"""
BORG FENIX — Opportunity Scanner v2
Skenira aktivne olakšice i matchira ih s firmama.

Glavna funkcija: match_opportunities_for_company(company)
Rezultat: {"total_savings": Decimal, "matches": [...], "count": int}

Koristi se:
1. Na onboardingu nove firme (instant ROI)
2. Kad se pojavi nova olakšica (bulk scan svih firmi)
3. Tjedni compliance check
4. WhatsApp notifikacija: "Pronašli smo N prilika za uštedu od X EUR"
"""

import logging
from decimal import Decimal

from django.db.models import Q
from django.utils import timezone

logger = logging.getLogger(__name__)


# ── MAIN ENTRY POINT ─────────────────────────────────────────────────────────


def match_opportunities_for_company(company):
    """
    Pronađi sve aktivne olakšice koje odgovaraju firmi.

    Logika matchiranja:
    1. Filtriraj samo aktivne, neistekle olakšice
    2. Za svaku olakšicu provjeri:
       a) ImpactDomain (direktni FK na olakšici)
       b) ImpactDomain-e kroz RegulatoryUpdate (širi kontekst)
       c) Eligibility criteria (JSON pravila)
    3. Ako nkd_code = None → firma PROLAZI NKD filter (ne isključuj nepoznato)
    4. Izračunaj uštedu (formula → typical → 0)
    5. Kreiraj ClientOpportunityMatch (get_or_create, idempotentno)

    Returns:
        dict: {company_id, company_name, total_savings, count, matches[], scanned_at}
    """
    from limit_connect_ai.models_knowledge_graph import (
        ClientOpportunityMatch,
        LegalOpportunity,
    )

    now = timezone.now().date()

    # Dohvati sve aktivne olakšice (neistekle)
    opportunities = (
        LegalOpportunity.objects.filter(
            is_active=True,
        )
        .filter(
            Q(deadline__isnull=True) | Q(deadline__gte=now),
        )
        .select_related("impact_domain", "regulatory_update")
    )

    matches = []
    total_savings = Decimal("0")

    for opp in opportunities:
        # ── Provjera domain match ────────────────────────────────────
        if not _company_matches_opportunity(company, opp):
            continue

        # ── Provjera eligibility criteria ────────────────────────────
        if not _check_eligibility(company, opp.eligibility_criteria):
            continue

        # ── Izračun uštede ───────────────────────────────────────────
        savings = _calculate_savings(company, opp)

        # ── Kreiraj/ažuriraj match ───────────────────────────────────
        match, created = ClientOpportunityMatch.objects.get_or_create(
            company=company,
            opportunity=opp,
            defaults={
                "calculated_savings": savings,
                "status": "identified",
            },
        )

        if not created:
            # Reaktiviraj expired match ili ažuriraj savings
            if match.status == "expired":
                match.status = "identified"
            if match.calculated_savings != savings:
                match.calculated_savings = savings
            match.save(update_fields=["calculated_savings", "status"])

        if savings > 0:
            total_savings += savings
            matches.append(
                {
                    "opportunity_id": str(opp.pk),
                    "name": opp.name,
                    "type": opp.get_opportunity_type_display(),
                    "type_key": opp.opportunity_type,
                    "savings_eur": float(savings),
                    "deadline": str(opp.deadline) if opp.deadline else None,
                    "days_left": (opp.deadline - now).days if opp.deadline else None,
                    "match_id": str(match.pk),
                    "is_new": created,
                    "description": opp.description[:200],
                    "url": opp.url,
                }
            )

    result = {
        "company_id": str(company.pk),
        "company_name": company.name,
        "total_savings": total_savings,
        "count": len(matches),
        "matches": sorted(matches, key=lambda m: m["savings_eur"], reverse=True),
        "scanned_at": timezone.now().isoformat(),
    }

    if matches:
        logger.info(
            "[BORG] %s: %d prilika, %.2f EUR ustede",
            company.name,
            len(matches),
            total_savings,
        )

    return result


# ── Backward-compatible aliases ──────────────────────────────────────────────


def scan_company(company):
    """Alias za match_opportunities_for_company()."""
    return match_opportunities_for_company(company)


def scan_all_companies():
    """Bulk scan svih aktivnih firmi."""
    from companies.models import Company

    results = []
    companies = Company.objects.all()
    total_companies = companies.count()

    logger.info("[BORG] Pocinjem scan %d firmi...", total_companies)

    for i, company in enumerate(companies, 1):
        try:
            result = match_opportunities_for_company(company)
            if result["count"] > 0:
                results.append(result)
        except Exception as e:
            logger.warning("[BORG] Scan failed za %s: %s", company.name, e)

        if i % 20 == 0:
            logger.info("[BORG] Progress: %d/%d firmi", i, total_companies)

    total_savings = sum(r["total_savings"] for r in results)
    total_matches = sum(r["count"] for r in results)

    logger.info(
        "[BORG] Scan zavrsen: %d/%d firmi s prilikama, %d matcheva, %.2f EUR ukupno",
        len(results),
        total_companies,
        total_matches,
        total_savings,
    )
    return results


def generate_onboarding_report(company):
    """
    WhatsApp-friendly izvještaj za novu firmu.
    "Pronašli smo 4 prilike za uštedu od 12.340 EUR"
    """
    result = match_opportunities_for_company(company)

    if result["count"] == 0:
        return (
            f"Dobrodosli u LIMIT Connect, {company.name}!\n\n"
            f"Trenutno nema aktivnih olaksica za vas profil, "
            f"ali sustav automatski prati sve promjene zakona i obavijestit ce vas cim se pojavi prilika."
        )

    lines = [
        "*LIMIT Connect — Analiza prilika*",
        f"_{company.name}_",
        "",
        f"Pronasli smo *{result['count']} prilika* za ustedu od *{result['total_savings']:,.2f} EUR*!",
        "",
    ]

    for i, m in enumerate(result["matches"][:5], 1):
        deadline_str = f" (rok: {m['deadline']})" if m["deadline"] else ""
        lines.append(f"{i}. *{m['name']}*")
        lines.append(f"   {m['type']} | Usteda: {m['savings_eur']:,.2f} EUR{deadline_str}")
        lines.append("")

    if result["count"] > 5:
        lines.append(f"... i jos {result['count'] - 5} prilika.")
        lines.append("")

    lines.append("Kontaktirajte nas za aktivaciju!")
    lines.append("limit-connect.com")

    return "\n".join(lines)


# ── INTERNAL: Domain matching ────────────────────────────────────────────────


def _company_matches_opportunity(company, opportunity):
    """
    Provjeri odgovara li firma olakšici.

    Strategija:
    1. Ako olakšica ima direktni impact_domain → koristi ga
    2. Ako nema → provjeri impact_domain-e na RegulatoryUpdate-u
    3. Ako ni RegulatoryUpdate nema domene → olakšica je za sve (match)
    """
    # Direktni impact_domain na olakšici
    if opportunity.impact_domain:
        return _domain_matches(company, opportunity.impact_domain)

    # Provjeri domene na RegulatoryUpdate-u
    if opportunity.regulatory_update:
        domains = opportunity.regulatory_update.impact_domains.all()
        if domains.exists():
            # Firma mora matchirati barem jednu domenu
            return any(_domain_matches(company, d) for d in domains)

    # Nema nijedne domene → olakšica je za sve
    return True


def _domain_matches(company, domain):
    """
    Provjeri matchira li firma ImpactDomain.
    Ključno: nkd_code=None → NE isključuj (ne možemo potvrditi da ne pripada).
    """
    # Country check
    if domain.country != "*" and getattr(company, "country", "HR") != domain.country:
        return False

    # NKD check — FK na NKDCode objekt
    if domain.nkd_codes:
        nkd_fk = getattr(company, "nkd_code", None)
        if nkd_fk is not None:
            company_nkd = nkd_fk.code if hasattr(nkd_fk, "code") else str(nkd_fk)
            if company_nkd not in domain.nkd_codes:
                return False
        # nkd_fk is None → propusti (ne isključuj nepoznato)

    # Business type check
    if domain.business_types:
        if getattr(company, "business_type", "") not in domain.business_types:
            return False

    # VAT check
    if domain.requires_vat and not getattr(company, "is_vat_registered", True):
        return False

    # Employee count check
    num_emp = getattr(company, "num_employees", None)
    if num_emp is not None:
        if domain.min_employees and num_emp < domain.min_employees:
            return False
        if domain.max_employees and num_emp > domain.max_employees:
            return False

    return True


# ── INTERNAL: Eligibility criteria ───────────────────────────────────────────


def _check_eligibility(company, criteria):
    """Provjeri JSON eligibility_criteria s firminim podacima."""
    if not criteria:
        return True

    # Max employees
    max_emp = criteria.get("max_employees")
    if max_emp is not None:
        num_emp = getattr(company, "num_employees", None)
        if num_emp is not None and num_emp > max_emp:
            return False

    # Min annual revenue
    min_revenue = criteria.get("min_annual_revenue")
    if min_revenue:
        revenue = getattr(company, "annual_revenue", None)
        if revenue is not None and revenue < min_revenue:
            return False

    # Requires VAT
    if criteria.get("requires_vat"):
        if not getattr(company, "is_vat_registered", True):
            return False

    # Min employees
    min_emp = criteria.get("min_employees")
    if min_emp:
        num_emp = getattr(company, "num_employees", None)
        if num_emp is not None and num_emp < min_emp:
            return False

    return True


# ── INTERNAL: Savings calculation ────────────────────────────────────────────


def _calculate_savings(company, opportunity):
    """
    Izračunaj uštedu za firmu. Fallback lanac:
    1. savings_formula (Python eval s ograničenim builtins)
    2. typical_savings_eur (defaultna vrijednost)
    3. Decimal('0')
    """
    # Pokušaj formulu prvo
    formula = opportunity.savings_formula
    if formula:
        try:
            context = {
                "num_employees": getattr(company, "num_employees", 5) or 5,
                "annual_revenue": float(getattr(company, "annual_revenue", 100000) or 100000),
                "bruto_placa": 1200,
                "min": min,
                "max": max,
                "abs": abs,
            }
            result = eval(formula, {"__builtins__": {}}, context)  # noqa: S307
            calculated = Decimal(str(result)).quantize(Decimal("0.01"))
            if calculated > 0:
                return calculated
        except (ValueError, TypeError) as e:
            logger.debug("Formula eval failed za %s: %s", opportunity.name, e)

    # Fallback na typical
    if opportunity.typical_savings_eur and opportunity.typical_savings_eur > 0:
        return opportunity.typical_savings_eur

    return Decimal("0")
