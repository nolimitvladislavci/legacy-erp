"""
BORG Compliance Simulator — simulira financijski utjecaj regulatornih promjena.

Phase 1: PDV promjene — izracunaj delta na recurring invoices.
Phase 2: LLM-driven simulacija za slozenije promjene.
"""
import logging
from decimal import Decimal

from django.utils import timezone

logger = logging.getLogger('borg.simulation')


class ComplianceSimulator:
    """Simulira financijski utjecaj regulatorne promjene na tenanta."""

    def simulate_vat_change(self, company, old_rate, new_rate, effective_date):
        """
        Analizira aktivne fakture i racuna delta za PDV promjenu.

        Returns: {
            'monthly_impact_eur': Decimal,
            'quarterly_impact_eur': Decimal,
            'affected_invoices': int,
            'direction': 'increase' | 'decrease',
            'details': str,
        }
        """
        from datetime import timedelta

        from invoicing.models import Invoice

        old_rate = Decimal(str(old_rate))
        new_rate = Decimal(str(new_rate))
        rate_diff = new_rate - old_rate

        # Find recent invoices with the old rate to estimate monthly volume
        three_months_ago = timezone.now() - timedelta(days=90)
        recent_invoices = Invoice.objects.filter(
            company=company,
            date_issued__gte=three_months_ago,
            tax_percent=old_rate,
            status__in=['SENT', 'PAID', 'OVERDUE', 'CONFIRMED', 'FISCALIZED'],
        )

        total_subtotal = recent_invoices.aggregate(
            total=models_Sum('subtotal')
        )['total'] or Decimal('0')

        invoice_count = recent_invoices.count()

        # Calculate monthly average
        monthly_subtotal = total_subtotal / Decimal('3')

        # Impact calculation
        monthly_impact = monthly_subtotal * rate_diff / Decimal('100')
        quarterly_impact = monthly_impact * Decimal('3')

        direction = 'increase' if rate_diff > 0 else 'decrease'

        details = (
            f'Na temelju {invoice_count} faktura iz zadnja 3 mjeseca '
            f'(prosjek {monthly_subtotal:.2f} EUR/mj neto), '
            f'promjena PDV stope s {old_rate}% na {new_rate}% '
            f'znaci {direction} od {abs(monthly_impact):.2f} EUR mjesecno.'
        )

        return {
            'monthly_impact_eur': monthly_impact,
            'quarterly_impact_eur': quarterly_impact,
            'affected_invoices': invoice_count,
            'direction': direction,
            'details': details,
            'old_rate': float(old_rate),
            'new_rate': float(new_rate),
            'effective_date': effective_date.isoformat() if effective_date else None,
        }

    def simulate_regulation_impact(self, company, regulatory_update):
        """
        Visi razina: koristi AI summary i module overlap za procjenu.
        Returns BorgInsight-ready dict.
        """
        from limit_connect_ai.services.nn_classifier import NNTenantClassifier

        classifier = NNTenantClassifier()
        result = classifier.classify(regulatory_update, company)

        if not result['relevant']:
            return None

        # Check if it's a VAT change
        if regulatory_update.category == 'VAT':
            # Try to extract rates from AI summary
            vat_result = self._try_vat_simulation(company, regulatory_update)
            if vat_result:
                return vat_result

        # Generic impact assessment
        return {
            'insight_type': 'regulation_impact',
            'title': f'Utjecaj: {regulatory_update.title[:150]}',
            'summary': result['impact_summary'],
            'data': {
                'severity': result['severity'],
                'affected_modules': result['affected_modules'],
                'nn_number': regulatory_update.nn_number,
                'effective_date': regulatory_update.effective_date.isoformat() if regulatory_update.effective_date else None,
            },
            'confidence_score': 0.6 if result['severity'] == 'action_required' else 0.4,
        }

    def _try_vat_simulation(self, company, regulatory_update):
        """Try to run VAT simulation if applicable."""
        # This would parse AI summary for rate changes
        # For now, return None (Phase 2: LLM extraction)
        return None


# Import for aggregate
from django.db.models import Sum as models_Sum


def create_insight_from_simulation(company, sim_result, regulatory_update=None):
    """Create BorgInsight from simulation result."""
    from borg_ops.models import BorgInsight

    insight = BorgInsight.objects.create(
        company=company,
        insight_type=sim_result.get('insight_type', 'regulation_impact'),
        title=sim_result['title'],
        summary=sim_result['summary'],
        data=sim_result.get('data', {}),
        regulatory_update=regulatory_update,
        confidence_score=sim_result.get('confidence_score', 0.5),
    )

    # Audit trail
    from borg_ops.audit_helpers import log_borg_audit
    log_borg_audit(
        company=company,
        entry_type='REGULATORY',
        summary=f'Insight generiran: {sim_result["title"][:100]}',
        severity='INFO',
        regulatory_update=regulatory_update,
        metadata={'insight_id': insight.pk, 'confidence': sim_result.get('confidence_score', 0.5)},
    )

    return insight
