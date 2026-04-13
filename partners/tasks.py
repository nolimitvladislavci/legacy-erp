"""Agent provizija — mjesečni obračun."""
import logging
from decimal import Decimal
from celery import shared_task
from django.utils import timezone as tz
from django.db import IntegrityError, DatabaseError

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
    except DatabaseError:
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
    except DatabaseError:
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
    except DatabaseError:
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
    except (json.JSONDecodeError, ValueError):
        pass
    return None


@shared_task(name='partners.classify_buyer_types_batch')
def classify_buyer_types_batch(company_id=None):
    """
    Batch klasifikacija buyer_type za partnere.
    Poziva istu logiku kao management command classify_buyer_types.
    """
    from partners.management.commands.classify_buyer_types import classify_partner
    from partners.models import Partner
    from django.utils import timezone
    import logging

    logger = logging.getLogger('partners.tasks')

    qs = Partner.objects.all()
    if company_id:
        qs = qs.filter(company_id=company_id)

    changed = 0
    for partner in qs.iterator(chunk_size=2000):
        result = classify_partner(partner)
        if result['confidence'] == 'skip':
            continue

        if (partner.buyer_type != result['buyer_type'] or
            partner.is_budget_user != result['is_budget_user'] or
            partner.is_nonprofit_no_activity != result['is_nonprofit_no_activity']):

            partner.buyer_type = result['buyer_type']
            partner.is_budget_user = result['is_budget_user']
            partner.is_nonprofit_no_activity = result['is_nonprofit_no_activity']
            partner.save(update_fields=[
                'buyer_type', 'is_budget_user',
                'is_nonprofit_no_activity', 'updated_at',
            ])
            changed += 1

    logger.info('classify_buyer_types_batch: %d partnera ažurirano (company=%s)', changed, company_id)
    return {'changed': changed, 'total': qs.count()}


# ═══════════════════════════════════════════════════
#  VIES BATCH VALIDACIJA
# ═══════════════════════════════════════════════════

@shared_task(bind=True, max_retries=2, default_retry_delay=300,
             time_limit=3600, soft_time_limit=3500)
def vies_batch_validate(self, batch_size=500):
    """
    Batch VIES validacija partnera s HR OIB-om ili EU VAT ID-om.
    Koristi EU VIES SOAP servis.
    Pokreće se periodično (celery-beat) ili ručno.

    Provjerava SVE buyer_type kategorije uključujući b2b_novat i udruga_novat.
    Ako je VIES valid → upgradea buyer_type i postavlja is_vat_registered + vat_id.
    """
    import requests
    import time
    from xml.etree import ElementTree as ET
    from partners.models import Partner
    from partners.hr_registry import _parse_address
    from django.utils import timezone as tz
    from django.db.models import Q

    VIES_URL = 'https://ec.europa.eu/taxation_customs/vies/services/checkVatService'
    SOAP_TPL = """<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:urn="urn:ec.europa.eu:taxud:vies:services:checkVat:types">
  <soapenv:Body>
    <urn:checkVat>
      <urn:countryCode>{cc}</urn:countryCode>
      <urn:vatNumber>{vat}</urn:vatNumber>
    </urn:checkVat>
  </soapenv:Body>
</soapenv:Envelope>"""

    UPGRADE_MAP = {
        'b2b_novat': 'b2b_vat',
        'udruga_novat': 'udruga_vat',
    }

    # Dohvati partnere koji trebaju provjeru — SVE tipove osim b2c
    stale = tz.now() - tz.timedelta(days=30)
    partners = Partner.objects.filter(
        Q(vies_valid__isnull=True) | Q(vies_checked_at__lt=stale)
    ).filter(
        Q(oib__regex=r'^\d{11}$') | Q(vat_id__regex=r'^[A-Z]{2}\d')
    ).exclude(
        buyer_type='b2c'
    ).exclude(oib='').order_by('?')[:batch_size]

    checked = 0
    valid = 0
    upgraded = 0
    errors = 0

    for partner in partners:
        # Determine country code + VAT number
        if partner.vat_id and len(partner.vat_id) > 2:
            cc = partner.vat_id[:2].upper()
            vat_num = partner.vat_id[2:].strip()
        elif partner.oib and len(partner.oib) == 11 and partner.oib.isdigit():
            cc = 'HR'
            vat_num = partner.oib
        else:
            continue

        try:
            resp = requests.post(
                VIES_URL,
                data=SOAP_TPL.format(cc=cc, vat=vat_num),
                headers={'Content-Type': 'text/xml; charset=utf-8'},
                timeout=15,
            )
            if resp.status_code != 200:
                errors += 1
                continue

            root = ET.fromstring(resp.content)
            ns = {'v': 'urn:ec.europa.eu:taxud:vies:services:checkVat:types'}
            is_valid_el = root.find('.//v:valid', ns)
            name_el = root.find('.//v:name', ns)
            addr_el = root.find('.//v:address', ns)

            is_vat_valid = is_valid_el is not None and is_valid_el.text == 'true'

            update_fields = ['vies_valid', 'vies_checked_at', 'vies_name', 'vies_address']

            partner.vies_valid = is_vat_valid
            partner.vies_checked_at = tz.now()
            if name_el is not None and name_el.text:
                partner.vies_name = name_el.text[:255]
            if addr_el is not None and addr_el.text:
                partner.vies_address = addr_el.text[:500]
                # Popuni adresu/grad ako prazni
                if not partner.address or not partner.city:
                    try:
                        parsed = _parse_address(addr_el.text)
                        if not partner.address and parsed.get('address'):
                            partner.address = parsed['address']
                            update_fields.append('address')
                        if not partner.city and parsed.get('city'):
                            partner.city = parsed['city']
                            update_fields.append('city')
                        if not partner.zip_code and parsed.get('zip_code'):
                            partner.zip_code = parsed['zip_code']
                            update_fields.append('zip_code')
                    except KeyError:
                        pass

            # Upgrade buyer_type ako je VIES valid
            if is_vat_valid and partner.buyer_type in UPGRADE_MAP:
                partner.buyer_type = UPGRADE_MAP[partner.buyer_type]
                partner.is_vat_registered = True
                if not partner.vat_id:
                    partner.vat_id = f'{cc}{vat_num}'
                update_fields.extend(['buyer_type', 'is_vat_registered', 'vat_id'])
                upgraded += 1

            partner.save(update_fields=list(set(update_fields)))
            _log_vies_audit(partner, is_vat_valid, partner.vies_name or '', partner.vies_address or '')

            checked += 1
            if is_vat_valid:
                valid += 1

        except requests.exceptions.Timeout:
            errors += 1
            continue
        except requests.RequestException as e:
            logger.warning("VIES error for %s: %s", partner.oib, e)
            errors += 1
            continue

        time.sleep(1.1)

    logger.info(
        "VIES batch: checked=%d, valid=%d, upgraded=%d, errors=%d",
        checked, valid, upgraded, errors,
    )
    return {'checked': checked, 'valid': valid, 'upgraded': upgraded, 'errors': errors}



# ── BORG Audit Hook for VIES ──────────────────────────────────────

def _log_vies_audit(partner, vies_valid, vies_name='', vies_address=''):
    """Log VIES validation result to BorgAuditEntry."""
    try:
        from borg_ops.audit_helpers import log_borg_audit
        company = partner.company
        severity = 'INFO' if vies_valid else 'WARNING'
        summary = (
            f'VIES provjera partnera {partner.name} (OIB: {partner.oib}) — '
            f'{"VALIDAN" if vies_valid else "NEVALIDAN"}'
        )
        log_borg_audit(
            company=company,
            entry_type='VIES_CHECK',
            summary=summary,
            severity=severity,
            document=partner,
            verification_type='VIES',
            verification_result={
                'vies_valid': vies_valid,
                'vies_name': vies_name,
                'vies_address': vies_address,
            },
        )
    except ImportError:
        pass
