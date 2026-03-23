"""Agent provizija — mjesečni obračun."""
import logging
from decimal import Decimal
from celery import shared_task
from django.utils import timezone as tz

logger = logging.getLogger('agents')


@shared_task
def calculate_agent_commissions():
    """
    Mjesečno: izračunaj proviziju za sve aktivne agente.
    Pokreće se 1. u mjesecu za prethodni mjesec.
    """
    from partners.models import AgentReferral, AgentPayout
    from registration.models import CompanySubscription

    now = tz.now()
    # Prethodni mjesec
    if now.month == 1:
        month, year = 12, now.year - 1
    else:
        month, year = now.month - 1, now.year

    active_referrals = AgentReferral.objects.filter(status='active').select_related('agent', 'referred_company')

    agents_processed = {}

    for ref in active_referrals:
        # Provjeri da li je istekao (12 mjeseci)
        if ref.expires_at and now > ref.expires_at:
            ref.status = 'expired'
            ref.save(update_fields=['status'])
            continue

        # Nađi aktivnu pretplatu
        sub = CompanySubscription.objects.filter(
            company=ref.referred_company, is_active=True
        ).first()

        if not sub or not sub.monthly_fee:
            continue

        # Izračunaj proviziju
        commission = sub.monthly_fee * ref.commission_percent / 100

        # Akumuliraj po agentu
        agent_pk = str(ref.agent.pk)
        if agent_pk not in agents_processed:
            agents_processed[agent_pk] = {
                'agent': ref.agent,
                'total': Decimal('0'),
                'referrals': [],
                'iban': ref.agent_iban,
            }

        agents_processed[agent_pk]['total'] += commission
        agents_processed[agent_pk]['referrals'].append({
            'company': ref.referred_company.name,
            'plan': sub.plan,
            'monthly_fee': str(sub.monthly_fee),
            'commission_pct': str(ref.commission_percent),
            'commission': str(commission),
        })

        # Update referral total
        ref.total_earned += commission
        ref.save(update_fields=['total_earned'])

    # Kreiraj payout zapise
    created = 0
    for agent_pk, data in agents_processed.items():
        if data['total'] <= 0:
            continue

        payout, was_created = AgentPayout.objects.get_or_create(
            agent=data['agent'],
            period_month=month,
            period_year=year,
            defaults={
                'amount': data['total'],
                'referrals_count': len(data['referrals']),
                'breakdown': data['referrals'],
                'iban': data['iban'],
            }
        )
        if was_created:
            created += 1
            logger.info(
                '[AGENT] Payout created: %s — %s EUR (%d referrals) for %02d/%d',
                data['agent'].name, data['total'], len(data['referrals']), month, year
            )

    return {'month': '%02d/%d' % (month, year), 'agents': len(agents_processed), 'payouts_created': created}


# ─── Wizard Draft Cleanup ────────────────────────────────────────────────────

@shared_task(name='partners.cleanup_stale_wizard_drafts')
def cleanup_stale_wizard_drafts():
    """
    Briše WizardDraft zapise koji su:
    - Stariji od 30 dana I nisu completed
    - Stariji od 90 dana I jesu completed (arhivirani)
    Pokretati: svaki dan u 03:00
    """
    from partners.models import WizardDraft
    from django.utils import timezone as tz
    from datetime import timedelta

    now = tz.now()
    stale = WizardDraft.objects.filter(
        completed=False,
        updated_at__lt=now - timedelta(days=30),
    )
    stale_count = stale.count()
    stale.delete()

    old_completed = WizardDraft.objects.filter(
        completed=True,
        completed_at__lt=now - timedelta(days=90),
    )
    old_count = old_completed.count()
    old_completed.delete()

    logger.info(f'Wizard cleanup: {stale_count} stale + {old_count} old-completed obrisano')
    return {'stale_deleted': stale_count, 'old_deleted': old_count}


@shared_task(name='partners.retroactive_nkd_lookup')
def retroactive_nkd_lookup(company_ids=None, dry_run=False):
    """
    Retroaktivni NKD lookup za firme bez nkd_code.
    Strategija (bez FINA tokena):
      1. Provjeri Synesis uvezene podatke (fakture/partneri) — NKD u importu
      2. FINA infobiz public scrape (bez tokena, rate-limited)
      3. Knowledge Graph — industry inference iz ClientOpportunityMatch patterns
    Vraća broj ažuriranih firmi.
    """
    from companies.models import Company, NKDCode
    from django.db.models import Q

    qs = Company.objects.filter(nkd_code__isnull=True)
    if company_ids:
        qs = qs.filter(id__in=company_ids)
    # Preskoči draft firme
    qs = qs.exclude(oib__startswith='DRAFT')

    updated = 0
    for company in qs[:50]:  # Batch od 50 odjednom
        nkd = _infer_nkd_from_context(company)
        if nkd and not dry_run:
            company.nkd_code = nkd
            company.save(update_fields=['nkd_code'])
            updated += 1
            logger.info(f'NKD retroactive: {company.name} → {nkd.code}')
        elif nkd and dry_run:
            logger.info(f'[DRY RUN] {company.name} → {nkd.code}')
            updated += 1

    logger.info(f'Retroactive NKD: {updated}/{qs.count()} ažurirano')
    return {'updated': updated, 'total_without_nkd': qs.count()}


def _infer_nkd_from_context(company) -> 'NKDCode | None':
    """
    Zaključuje NKD iz konteksta firme.
    Strategija (redoslijed):
    1. Haiku AI — iz naziva firme (85-95% accuracy, ~0.01 USD po firmi)
    2. Knowledge Graph match patterns
    3. Invoice keyword match
    4. POS detect (→ 47.99 maloprodaja)
    """
    from companies.models import NKDCode

    # Strategija 0: Haiku inference iz naziva (primarno)
    nkd = _haiku_infer_nkd(company.name)
    if nkd:
        return nkd

    # Strategija 1: Knowledge Graph match patterns
    try:
        from limit_connect_ai.models_knowledge_graph import ClientOpportunityMatch, LegalOpportunity
        matches = ClientOpportunityMatch.objects.filter(
            company=company
        ).select_related('opportunity__impact_domain')
        for m in matches:
            opp = m.opportunity
            if opp and opp.impact_domain and opp.impact_domain.nkd_section:
                nkd = NKDCode.objects.filter(
                    section=opp.impact_domain.nkd_section, is_active=True
                ).first()
                if nkd:
                    return nkd
    except Exception:
        pass

    # Strategija 2: Invoice descriptions keyword match
    try:
        from invoicing.models import Invoice
        from django.db.models import Q
        desc_words = []
        for inv in Invoice.objects.filter(company=company).values_list('notes', flat=True)[:20]:
            if inv:
                desc_words.extend(inv.lower().split())

        if desc_words:
            # Top 5 najčešćih značajnih riječi
            from collections import Counter
            stopwords = {'za', 'na', 'od', 'do', 'je', 'i', 'u', 'se', 'te', 'po', 'uz'}
            freq = Counter(w for w in desc_words if len(w) > 3 and w not in stopwords)
            for word, _ in freq.most_common(5):
                nkd = NKDCode.objects.filter(
                    Q(name_hr__icontains=word) | Q(name_en__icontains=word),
                    is_active=True
                ).first()
                if nkd:
                    return nkd
    except Exception:
        pass

    # Strategija 3: POS kategorije
    try:
        from pos.models import POSTerminal, Category
        terminals = POSTerminal.objects.filter(company=company)
        if terminals.exists():
            # Firma ima POS — najvjerojatnija djelatnost je maloprodaja
            retail_nkd = NKDCode.objects.filter(code='47.99', is_active=True).first()
            if retail_nkd:
                return retail_nkd
    except Exception:
        pass

    return None


def _haiku_infer_nkd(company_name: str):
    """
    Haiku inference NKD koda iz naziva firme.
    Batch-friendly — poziva se jednom po firmi, ~0.01 USD.
    Returns NKDCode object ili None.
    """
    import os
    import requests as req
    import json as _json

    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        return None

    from companies.models import NKDCode
    nkd_list = '\n'.join(
        f'{c}: {n}'
        for c, n in NKDCode.objects.filter(is_active=True).values_list('code', 'name_hr').order_by('code')
    )

    prompt = (
        f'Tvrtka se zove: "{company_name}"\n\n'
        f'Dostupni NKD kodovi:\n{nkd_list}\n\n'
        f'Koji NKD kod NAJVJEROJATNIJE odgovara ovoj tvrtki?\n'
        f'Vrati SAMO JSON: {{"code": "xx.xx", "confidence": 0.0}}\n'
        f'Bez ikakvog teksta.'
    )

    try:
        resp = req.post(
            'https://api.anthropic.com/v1/messages',
            headers={
                'x-api-key': api_key,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json',
            },
            json={
                'model': 'claude-haiku-4-5-20251001',
                'max_tokens': 60,
                'messages': [{'role': 'user', 'content': prompt}],
            },
            timeout=8,
        )
        resp.raise_for_status()
        text = resp.json()['content'][0]['text'].strip()
        if '```' in text:
            text = text.split('```')[1]
            if text.startswith('json'):
                text = text[4:]
        data = _json.loads(text.strip())
        code = data.get('code', '').strip()
        confidence = float(data.get('confidence', 0))

        if code and confidence >= 0.7:
            return NKDCode.objects.filter(code=code, is_active=True).first()
    except Exception:
        pass
    return None
