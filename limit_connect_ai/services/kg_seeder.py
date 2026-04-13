"""
BORG FENIX - Knowledge Graph Seeder (F2.1)
Seeds regulatory sources, legal opportunities, scans all companies.

Usage:
    from limit_connect_ai.services.kg_seeder import seed_knowledge_graph
    result = seed_knowledge_graph()
"""
import logging
from django.utils import timezone

logger = logging.getLogger('borg.kg_seeder')

HR_SOURCES = [
    {'name': 'Narodne novine', 'source_type': 'nn', 'url_endpoint': 'https://narodne-novine.nn.hr/search.aspx', 'scrape_interval_hours': 6},
    {'name': 'Porezna uprava', 'source_type': 'porezna', 'url_endpoint': 'https://www.porezna-uprava.hr/HR_obavijesti/Stranice/default.aspx', 'scrape_interval_hours': 12},
    {'name': 'FINA javne objave', 'source_type': 'fina', 'url_endpoint': 'https://www.fina.hr/objave', 'scrape_interval_hours': 24},
    {'name': 'EUR-Lex HR', 'source_type': 'eurlex', 'url_endpoint': 'https://eur-lex.europa.eu/search.html?lang=hr', 'scrape_interval_hours': 24},
    {'name': 'HZZ mjere', 'source_type': 'hzz', 'url_endpoint': 'https://mjere.hzz.hr', 'scrape_interval_hours': 24},
    {'name': 'Ministarstvo gospodarstva', 'source_type': 'mingor', 'url_endpoint': 'https://mingor.gov.hr/javne-rasprave/24', 'scrape_interval_hours': 24},
]

NEW_OPPORTUNITIES = [
    {'name': 'Oslobodenje poreza na dobit - nove firme 3 god', 'opportunity_type': 'tax_relief',
     'description': 'Novoosnovani poduzetnici: 0% porez na dobit prve 3 godine (prihod do 995K EUR).', 'typical_savings_eur': 8000},
    {'name': 'Potpomognuta podrucja - 50% nizi porez', 'opportunity_type': 'regional_aid',
     'description': 'Firme u potpomognutim podrucjima placaju 50% nizi porez na dobit.', 'typical_savings_eur': 4000},
    {'name': 'R&D olaksica - 200% odbitak', 'opportunity_type': 'tax_relief',
     'description': 'Udvostuceni odbitak troskova istrazivanja i razvoja od porezne osnovice.', 'typical_savings_eur': 10000},
    {'name': 'Stambeni kredit zaposlenik - neoporezivo 1.328 EUR/mj', 'opportunity_type': 'tax_relief',
     'description': 'Poslodavac moze neoporezivo pomoci otplatu stambenog kredita zaposleniku.', 'typical_savings_eur': 15936},
]


def seed_regulatory_sources():
    """Seed/update standardne HR regulatorne izvore."""
    from limit_connect_ai.models_knowledge_graph import RegulatorySource
    created = 0
    for src in HR_SOURCES:
        _, is_new = RegulatorySource.objects.get_or_create(
            source_type=src['source_type'],
            defaults={'name': src['name'], 'url_endpoint': src['url_endpoint'],
                      'scrape_interval_hours': src['scrape_interval_hours'], 'is_active': True},
        )
        if is_new:
            created += 1
    logger.info('Seeded %d new regulatory sources (total: %d)', created, RegulatorySource.objects.count())
    return created


def seed_legal_opportunities():
    """Seed/update HR legal opportunities."""
    from limit_connect_ai.models_knowledge_graph import LegalOpportunity
    created = 0
    for opp in NEW_OPPORTUNITIES:
        _, is_new = LegalOpportunity.objects.get_or_create(
            name=opp['name'],
            defaults={
                'opportunity_type': opp['opportunity_type'],
                'description': opp['description'],
                'typical_savings_eur': opp['typical_savings_eur'],
                'is_active': True,
            },
        )
        if is_new:
            created += 1
    logger.info('Seeded %d new opportunities (total: %d)', created, LegalOpportunity.objects.count())
    return created


def scan_all_companies():
    """Run opportunity scanner for ALL active companies."""
    from companies.models import Company
    from limit_connect_ai.services.opportunity_scanner import match_opportunities_for_company

    companies = Company.objects.exclude(is_deactivated=True)
    total_matches = 0
    total_savings = 0

    for company in companies:
        try:
            result = match_opportunities_for_company(company)
            total_matches += result.get('count', 0)
            total_savings += float(result.get('total_savings', 0))
        except (ValueError, TypeError) as e:
            logger.warning('Scan failed for %s: %s', company.name, e)

    logger.info('Scanned %d companies: %d matches, %.0f EUR savings',
                companies.count(), total_matches, total_savings)
    return {'companies': companies.count(), 'matches': total_matches, 'savings': total_savings}


def seed_knowledge_graph():
    """Full KG seed: sources + opportunities + company scan."""
    logger.info('=== KG SEED START ===')
    sources = seed_regulatory_sources()
    opportunities = seed_legal_opportunities()
    scan = scan_all_companies()
    result = {'new_sources': sources, 'new_opportunities': opportunities, 'scan': scan}
    logger.info('=== KG SEED DONE: %s ===', result)
    return result
