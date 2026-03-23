"""
BORG FENIX — Opportunity Scanner
Skenira sve aktivne olakšice i matchira ih s firmama.
Rezultat: "Pronašli smo N prilika za uštedu od X EUR"

Koristi se:
1. Na onboardingu nove firme (instant ROI)
2. Kad se pojavi nova olakšica (bulk scan svih firmi)
3. Tjedni compliance check
"""
import logging
from decimal import Decimal

from django.utils import timezone

logger = logging.getLogger(__name__)


def scan_company(company):
    """
    Skeniraj jednu firmu — pronađi sve prilike koje joj odgovaraju.
    Vraća: {'total_savings': Decimal, 'matches': [...], 'count': int}
    """
    from limit_connect_ai.models_knowledge_graph import (
        LegalOpportunity, ImpactDomain, ClientOpportunityMatch,
    )

    opportunities = LegalOpportunity.objects.filter(
        is_active=True,
    ).select_related('impact_domain').prefetch_related('client_matches')

    now = timezone.now().date()
    matches = []
    total_savings = Decimal('0')

    for opp in opportunities:
        # Provjeri rok
        if opp.deadline and opp.deadline < now:
            continue

        # Provjeri impact domain
        if opp.impact_domain and not opp.impact_domain.matches_company(company):
            continue

        # Provjeri eligibility criteria
        if not _check_eligibility(company, opp.eligibility_criteria):
            continue

        # Izračunaj uštedu
        savings = _calculate_savings(company, opp)

        # Kreiraj ili dohvati match
        match, created = ClientOpportunityMatch.objects.get_or_create(
            company=company,
            opportunity=opp,
            defaults={
                'calculated_savings': savings,
                'status': 'identified',
            },
        )
        if not created and match.status == 'expired':
            # Reaktiviraj ako se ponovio
            match.calculated_savings = savings
            match.status = 'identified'
            match.save(update_fields=['calculated_savings', 'status'])

        if savings > 0:
            total_savings += savings
            matches.append({
                'opportunity_id': str(opp.pk),
                'name': opp.name,
                'type': opp.get_opportunity_type_display(),
                'savings_eur': float(savings),
                'deadline': str(opp.deadline) if opp.deadline else None,
                'match_id': str(match.pk),
                'is_new': created,
            })

    return {
        'company_id': company.pk,
        'company_name': company.name,
        'total_savings': total_savings,
        'count': len(matches),
        'matches': matches,
        'scanned_at': timezone.now().isoformat(),
    }


def scan_all_companies():
    """Bulk scan svih aktivnih firmi."""
    from companies.models import Company

    results = []
    companies = Company.objects.all()

    for company in companies:
        try:
            result = scan_company(company)
            if result['count'] > 0:
                results.append(result)
        except Exception as e:
            logger.warning('Opportunity scan failed for %s: %s', company.name, e)

    total = sum(r['total_savings'] for r in results)
    logger.info(
        '[BORG] Opportunity scan complete: %d firmi, %d prilika, %.2f EUR ukupno',
        len(results), sum(r['count'] for r in results), total,
    )
    return results


def generate_onboarding_report(company):
    """
    Generiraj WhatsApp-friendly izvještaj za novu firmu.
    "Pronašli smo 4 prilike za uštedu od 12.340 EUR"
    """
    result = scan_company(company)

    if result['count'] == 0:
        return (
            f"Dobrodošli u LIMIT Connect, {company.name}!\n\n"
            f"Trenutno nema aktivnih olakšica za vaš profil, "
            f"ali sustav automatski prati sve promjene zakona i obavijestit će vas čim se pojavi prilika."
        )

    lines = [
        f"LIMIT Connect — Analiza prilika za {company.name}",
        f"{'=' * 40}",
        f"Pronašli smo {result['count']} prilika za uštedu od {result['total_savings']:,.2f} EUR!",
        "",
    ]

    for i, m in enumerate(result['matches'][:5], 1):
        deadline_str = f" (rok: {m['deadline']})" if m['deadline'] else ""
        lines.append(f"{i}. {m['name']}")
        lines.append(f"   Tip: {m['type']}")
        lines.append(f"   Ušteda: {m['savings_eur']:,.2f} EUR{deadline_str}")
        lines.append("")

    if result['count'] > 5:
        lines.append(f"... i još {result['count'] - 5} prilika.")
        lines.append("")

    lines.append("Kontaktirajte nas za aktivaciju! limit-connect.com")

    return "\n".join(lines)


def _check_eligibility(company, criteria):
    """Provjeri ispunjava li firma kriterije olakšice."""
    if not criteria:
        return True

    # Max employee age check (za poticaje za mlade)
    max_age = criteria.get('max_employee_age')
    if max_age:
        # Ovo zahtijeva podatke o zaposlenicima — za sad skip
        pass

    # Min revenue
    min_revenue = criteria.get('min_annual_revenue')
    if min_revenue:
        revenue = getattr(company, 'annual_revenue', None)
        if revenue and revenue < min_revenue:
            return False

    # Required modules
    required_modules = criteria.get('required_modules', [])
    if required_modules:
        company_modules = getattr(company, 'module_config', {}) or {}
        for mod in required_modules:
            if not company_modules.get(mod):
                return False

    return True


def _calculate_savings(company, opportunity):
    """Izračunaj uštedu za firmu na temelju formule."""
    if opportunity.typical_savings_eur > 0:
        return opportunity.typical_savings_eur

    formula = opportunity.savings_formula
    if not formula:
        return Decimal('0')

    # Sigurno evaluiraj formulu s kontekst varijablama
    try:
        context = {
            'num_employees': getattr(company, 'num_employees', 5),
            'annual_revenue': float(getattr(company, 'annual_revenue', 100000) or 100000),
            'bruto_placa': 1200,  # Prosječna bruto plaća
            'min': min,
            'max': max,
            'abs': abs,
        }
        result = eval(formula, {"__builtins__": {}}, context)  # noqa: S307
        return Decimal(str(result)).quantize(Decimal('0.01'))
    except Exception:
        return opportunity.typical_savings_eur or Decimal('0')
