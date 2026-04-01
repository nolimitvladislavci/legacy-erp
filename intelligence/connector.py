"""
BORG FENIX — Intelligence Pipeline Connector (F3.1)
Connects NN feed results + external sources into unified IntelligenceResult/FundOpportunity pipeline.

Runs as Celery task: intelligence_unified_scan
"""
import logging
from celery import shared_task
from django.utils import timezone
from django.db.models import Q

logger = logging.getLogger('borg.intelligence')


@shared_task
def intelligence_unified_scan():
    """
    Unified intelligence scan:
    1. Run NN scraper for latest regulatory updates
    2. Convert high-impact regulatory updates to FundOpportunities
    3. Match FundOpportunities with company IntelligenceJobs
    4. Generate IntelligenceResults
    """
    stats = {'nn_processed': 0, 'funds_created': 0, 'results_created': 0}

    # Step 1: Run NN scraper
    try:
        from limit_connect_ai.services.nn_feed_service import NNFeedScraperService
        nn = NNFeedScraperService()
        nn_result = nn.process_feed()
        stats['nn_processed'] = nn_result.get('processed', 0)
        logger.info('NN scraper: %s', nn_result)
    except Exception as e:
        logger.error('NN scraper failed: %s', e)

    # Step 2: Convert EU_FUND regulatory updates to FundOpportunities
    stats['funds_created'] = _convert_regulatory_to_funds()

    # Step 3: Match funds with company jobs and create results
    stats['results_created'] = _match_funds_to_companies()

    logger.info('Unified scan complete: %s', stats)
    return stats


def _convert_regulatory_to_funds():
    """Convert unprocessed EU_FUND/TAX regulatory updates to FundOpportunity."""
    from limit_connect_ai.models_knowledge_graph import RegulatoryUpdate
    from intelligence.models import FundOpportunity

    updates = RegulatoryUpdate.objects.filter(
        category__in=['EU_FUND', 'TAX', 'LABOUR'],
        is_processed=True,
    ).exclude(
        # Skip if already linked to a fund
        title__in=FundOpportunity.objects.values_list('naziv', flat=True),
    )

    created = 0
    for update in updates[:20]:  # Max 20 per run
        tip_map = {
            'EU_FUND': 'eu_esf',
            'TAX': 'hr_ostalo',
            'LABOUR': 'hr_ostalo',
        }

        fund, is_new = FundOpportunity.objects.get_or_create(
            naziv=update.title[:300],
            defaults={
                'tip': tip_map.get(update.category, 'hr_ostalo'),
                'tijelo': 'Auto-detected',
                'opis': update.ai_summary or update.raw_text[:1000],
                'url': update.url,
                'ai_summary': update.ai_summary[:500] if update.ai_summary else '',
                'kljucne_rijeci': update.affected_modules or [],
                'otkrio_intelligence': True,
                'status': 'aktivan',
                'ciljna_skupina': 'svi',
            },
        )
        if is_new:
            created += 1

    logger.info('Converted %d regulatory updates to FundOpportunities', created)
    return created


def _match_funds_to_companies():
    """Match active FundOpportunities with company IntelligenceJobs."""
    from intelligence.models import IntelligenceJob, IntelligenceResult, FundOpportunity

    active_funds = FundOpportunity.objects.filter(
        status='aktivan',
    ).exclude(
        rok_prijave__lt=timezone.now().date(),
    )

    jobs = IntelligenceJob.objects.filter(aktivan=True).select_related('company')
    created = 0

    for job in jobs:
        keywords = job.kljucne_rijeci or []
        for fund in active_funds:
            # Check if already matched
            if IntelligenceResult.objects.filter(job=job, fund_opportunity=fund).exists():
                continue

            # Simple keyword matching
            fund_text = f"{fund.naziv} {fund.opis} {' '.join(fund.kljucne_rijeci or [])}".lower()
            relevance = 0

            for kw in keywords:
                if kw.lower() in fund_text:
                    relevance += 20

            # Minimum relevance threshold
            if relevance < 20 and keywords:
                continue

            # If no keywords, assign base relevance
            if not keywords:
                relevance = 50

            IntelligenceResult.objects.create(
                job=job,
                naslov=fund.naziv[:300],
                summary=fund.ai_summary or fund.opis[:500],
                url=fund.url,
                ai_relevantnost=min(relevance, 100),
                fund_opportunity=fund,
                status='novo',
            )
            created += 1

    logger.info('Created %d new IntelligenceResults', created)
    return created


@shared_task
def seed_intelligence_jobs():
    """Create IntelligenceJob for companies that don't have one."""
    from companies.models import Company
    from intelligence.models import IntelligenceJob, IntelligenceSource

    companies = Company.objects.exclude(is_deactivated=True)
    sources = IntelligenceSource.objects.filter(aktivan=True)
    created = 0

    for company in companies:
        job, is_new = IntelligenceJob.objects.get_or_create(
            company=company,
            defaults={
                'aktivan': True,
                'opis_poslovanja': f'{company.name} - {company.business_type}',
                'kljucne_rijeci': [],
            },
        )
        if is_new:
            job.sources.set(sources)
            created += 1

    logger.info('Created %d new IntelligenceJobs', created)
    return created
