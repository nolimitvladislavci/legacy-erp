"""
Knowledge Graph Summary — pregled stanja za Mariju.
"""
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db.models import Count, Sum, Q
from django.utils import timezone


class Command(BaseCommand):
    help = 'Knowledge Graph summary — firme, NKD, opportunities, matches, rizici'

    def handle(self, *args, **options):
        from companies.models import Company
        from limit_connect_ai.models_knowledge_graph import (
            LegalOpportunity, ClientOpportunityMatch, SupplierRiskAlert,
        )

        now = timezone.now().date()

        total_companies = Company.objects.count()
        draft_companies = Company.objects.filter(oib__startswith='DRAFT').count()
        active_companies = total_companies - draft_companies
        with_nkd = Company.objects.filter(nkd_code__isnull=False).exclude(oib__startswith='DRAFT').count()
        without_nkd = active_companies - with_nkd

        active_opps = LegalOpportunity.objects.filter(
            is_active=True,
        ).filter(Q(deadline__isnull=True) | Q(deadline__gte=now)).count()
        total_opps = LegalOpportunity.objects.count()

        total_matches = ClientOpportunityMatch.objects.count()
        match_stats = ClientOpportunityMatch.objects.aggregate(
            total_savings=Sum('calculated_savings'),
        )
        total_savings = match_stats['total_savings'] or Decimal('0')

        # Matches po statusu
        status_counts = dict(
            ClientOpportunityMatch.objects.values_list('status')
            .annotate(cnt=Count('id'))
            .values_list('status', 'cnt')
        )

        # Firme bez ijednog matcha
        matched_company_ids = set(
            ClientOpportunityMatch.objects.values_list('company_id', flat=True).distinct()
        )
        unmatched = active_companies - len(matched_company_ids)

        # Supplier Risk Alerts
        risk_total = SupplierRiskAlert.objects.count()
        risk_by_level = dict(
            SupplierRiskAlert.objects.values_list('risk_level')
            .annotate(cnt=Count('id'))
            .values_list('risk_level', 'cnt')
        )
        unack = SupplierRiskAlert.objects.filter(is_acknowledged=False).count()

        # Top 5 opportunities po ukupnoj uštedi
        top_opps = (
            LegalOpportunity.objects.filter(is_active=True)
            .annotate(
                match_count=Count('client_matches'),
                total_match_savings=Sum('client_matches__calculated_savings'),
            )
            .order_by('-total_match_savings')[:5]
        )

        # Output
        self.stdout.write(self.style.MIGRATE_HEADING(
            f'\n{"═" * 60}\n'
            f'  KNOWLEDGE GRAPH SUMMARY\n'
            f'  {timezone.now():%Y-%m-%d %H:%M}\n'
            f'{"═" * 60}'
        ))

        self.stdout.write(f'\n  FIRME:')
        self.stdout.write(f'    Ukupno:          {total_companies}')
        self.stdout.write(f'    Aktivne:         {active_companies}')
        self.stdout.write(f'    S NKD kodom:     {with_nkd} ({with_nkd*100//max(active_companies,1)}%)')
        self.stdout.write(f'    Bez NKD:         {without_nkd} ({without_nkd*100//max(active_companies,1)}%)')

        self.stdout.write(f'\n  OPPORTUNITIES:')
        self.stdout.write(f'    Aktivne:         {active_opps}')
        self.stdout.write(f'    Ukupno:          {total_opps}')

        self.stdout.write(f'\n  MATCHES:')
        self.stdout.write(f'    Ukupno:          {total_matches}')
        self.stdout.write(f'    Ukupna ušteda:   {total_savings:,.2f} EUR')
        for status, cnt in sorted(status_counts.items(), key=lambda x: -x[1]):
            self.stdout.write(f'      {status:20s} {cnt}')
        self.stdout.write(f'    Firme bez matcha: {unmatched}')

        self.stdout.write(f'\n  SUPPLIER RISK ALERTS:')
        self.stdout.write(f'    Ukupno:          {risk_total}')
        for level, cnt in sorted(risk_by_level.items(), key=lambda x: -x[1]):
            self.stdout.write(f'      {level:15s} {cnt}')
        self.stdout.write(f'    Nepotvrđeni:     {unack}')

        if top_opps:
            self.stdout.write(f'\n  TOP 5 OPPORTUNITIES:')
            for i, opp in enumerate(top_opps, 1):
                savings = opp.total_match_savings or 0
                self.stdout.write(
                    f'    {i}. {opp.name[:45]:45s} — {savings:>10,.2f} EUR — {opp.match_count} firmi'
                )

        self.stdout.write(f'\n{"═" * 60}\n')
