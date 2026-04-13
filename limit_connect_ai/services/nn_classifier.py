"""
NN Tenant Classifier — klasificira RegulatoryUpdate relevantnost PER TENANT.

Koristi ImpactDomain.matches_company() za brzu provjeru,
a za kompleksnije slucajeve LLM analizu.
"""
import logging
from django.db import DatabaseError

logger = logging.getLogger('borg.nn_classifier')


class NNTenantClassifier:
    """Klasificira RegulatoryUpdate relevantnost per tenant."""

    SEVERITY_MAP = {
        range(1, 4): 'info',
        range(4, 7): 'warning',
        range(7, 11): 'action_required',
    }

    def classify(self, regulatory_update, company):
        """
        Klasificiraj relevantnost regulatorne promjene za firmu.

        Returns:
            dict: {
                'relevant': bool,
                'severity': 'info' | 'warning' | 'action_required',
                'impact_summary': str,
                'affected_modules': list[str],
            }
        """
        # Step 1: Check ImpactDomain matches (fast, rule-based)
        domains = regulatory_update.impact_domains.all()
        if domains.exists():
            matched = any(d.matches_company(company) for d in domains)
            if not matched:
                return {
                    'relevant': False,
                    'severity': 'info',
                    'impact_summary': '',
                    'affected_modules': [],
                }

        # Step 2: Check affected_modules overlap with company's active apps
        company_modules = self._get_company_modules(company)
        affected = regulatory_update.affected_modules or []
        module_overlap = set(affected) & set(company_modules)

        if not affected:
            # No modules specified = potentially affects everyone
            relevant = True
        elif module_overlap:
            relevant = True
        else:
            relevant = False

        if not relevant:
            return {
                'relevant': False,
                'severity': 'info',
                'impact_summary': '',
                'affected_modules': [],
            }

        # Step 3: Determine severity from impact_score
        severity = self._score_to_severity(regulatory_update.impact_score)

        # Step 4: Generate impact summary
        impact_summary = self._generate_summary(regulatory_update, company, module_overlap)

        return {
            'relevant': True,
            'severity': severity,
            'impact_summary': impact_summary,
            'affected_modules': list(module_overlap) if module_overlap else affected,
        }

    def _get_company_modules(self, company):
        """Determine which modules a company actively uses."""
        modules = []
        try:
            # Check invoicing
            from invoicing.models import Invoice
            if Invoice.objects.filter(company=company).exists():
                modules.append('invoicing')
        except DatabaseError:
            pass

        try:
            # Check POS
            from pos.models import POSTerminal
            if POSTerminal.objects.filter(company=company).exists():
                modules.append('pos')
        except DatabaseError:
            pass

        try:
            # Check payroll
            from payroll.models import Employee
            if Employee.objects.filter(company=company).exists():
                modules.append('payroll')
        except DatabaseError:
            pass

        try:
            # Check eracun
            from eracun.models import ERacunConfig
            if ERacunConfig.objects.filter(company=company).exists():
                modules.append('eracun')
        except DatabaseError:
            pass

        try:
            # Check inventory
            from inventory.models import InventoryItem
            if InventoryItem.objects.filter(company=company).exists():
                modules.append('inventory')
        except DatabaseError:
            pass

        return modules

    def _score_to_severity(self, score):
        """Convert impact_score (1-10) to severity level."""
        if score >= 7:
            return 'action_required'
        elif score >= 4:
            return 'warning'
        return 'info'

    def _generate_summary(self, update, company, module_overlap):
        """Generate a human-readable impact summary."""
        modules_str = ', '.join(module_overlap) if module_overlap else 'sve module'
        summary = (
            f'{update.get_category_display()}: {update.title[:100]}. '
            f'Utjece na {modules_str} za {company.name}.'
        )
        if update.effective_date:
            summary += f' Stupanje na snagu: {update.effective_date.strftime("%d.%m.%Y")}.'
        if update.ai_summary:
            summary += f' {update.ai_summary[:200]}'
        return summary


def classify_and_store(regulatory_update, company):
    """
    Classify + store result in TenantRegulatoryImpact.
    Creates BorgTask if severity >= warning.
    Returns TenantRegulatoryImpact instance or None.
    """
    from limit_connect_ai.models_knowledge_graph import TenantRegulatoryImpact

    classifier = NNTenantClassifier()
    result = classifier.classify(regulatory_update, company)

    impact, created = TenantRegulatoryImpact.objects.update_or_create(
        company=company,
        regulatory_update=regulatory_update,
        defaults={
            'is_relevant': result['relevant'],
            'severity': result['severity'],
            'impact_summary': result['impact_summary'],
            'affected_modules': result['affected_modules'],
        },
    )

    if result['relevant'] and result['severity'] in ('warning', 'action_required'):
        # Create BorgTask
        from borg_ops.models import BorgTask
        task_exists = BorgTask.objects.filter(
            company=company,
            task_type='adaptation',
            reference_type='RegulatoryUpdate',
            reference_id=str(regulatory_update.pk),
            status__in=['pending', 'in_progress'],
        ).exists()

        if not task_exists:
            priority = 1 if result['severity'] == 'action_required' else 2
            BorgTask.objects.create(
                company=company,
                task_type='adaptation',
                title=f'NN: {regulatory_update.title[:200]}',
                description=result['impact_summary'],
                priority=priority,
                reference_type='RegulatoryUpdate',
                reference_id=str(regulatory_update.pk),
            )

        # BorgAuditEntry
        from borg_ops.audit_helpers import log_borg_audit
        log_borg_audit(
            company=company,
            entry_type='REGULATORY',
            summary=result['impact_summary'][:500],
            severity='WARNING' if result['severity'] == 'warning' else 'ACTION_REQUIRED',
            regulatory_update=regulatory_update,
            legal_reference=regulatory_update.nn_number,
            metadata={'affected_modules': result['affected_modules']},
        )

    return impact
