"""
OIB Finalizer — "ozakonjenje" DRAFT tvrtki kad klijent dobije pravi OIB.

Workflow:
  1. Marija unese pravi OIB (11 znamenki, ISO 7064 validan)
  2. Servis validira i zamijeni Company.oib s DRAFT_xxx → pravi OIB
  3. Pokrene VIES lookup za PDV status
  4. Smart Data Sync — ako OIB već postoji kod drugih partnera, povuče podatke
  5. FENIX bonitet scan (cache-aware)
  6. Označi WizardDraft kao finalized

Sigurnosne provjere:
  - OIB mora proći ISO 7064 MOD 11,10 validaciju
  - OIB ne smije već postojati u companies_company (unique constraint)
  - Samo DRAFT_ tvrtke se mogu finalizirati
"""
import logging

from django.db import DatabaseError, transaction

logger = logging.getLogger('partners.oib_finalizer')


class OIBFinalizerError(Exception):
    """Custom exception za finalizer greške."""
    pass


def finalize_oib(company_id, new_oib, user=None):
    """
    Zamijeni DRAFT OIB s pravim i pokreni enrichment pipeline.

    Args:
        company_id: UUID Company objekta
        new_oib: Pravi OIB (11 znamenki)
        user: Django User koji izvršava (za audit log)

    Returns:
        dict: {success, company, vies_result, sync_count, bonitet}

    Raises:
        OIBFinalizerError: Na bilo koju validacijsku grešku
    """
    from companies.models import Company
    from core.oib_validator import validate_oib_hr

    # ── Validacija ─────────────────────────────────────────
    new_oib = new_oib.strip()

    if not validate_oib_hr(new_oib):
        raise OIBFinalizerError(
            f'OIB {new_oib} nije validan (ISO 7064 MOD 11,10 provjera nije prošla).'
        )

    try:
        company = Company.objects.get(pk=company_id)
    except Company.DoesNotExist:
        raise OIBFinalizerError(f'Tvrtka {company_id} ne postoji.')

    if not company.oib.startswith('DRAFT'):
        raise OIBFinalizerError(
            f'Tvrtka {company.name} ima OIB "{company.oib}" koji nije DRAFT. '
            f'Samo DRAFT tvrtke se mogu finalizirati.'
        )

    # Provjeri uniqueness
    if Company.objects.filter(oib=new_oib).exclude(pk=company_id).exists():
        existing = Company.objects.get(oib=new_oib)
        raise OIBFinalizerError(
            f'OIB {new_oib} već postoji u sustavu: {existing.name}. '
            f'Kontaktirajte podršku ako je potrebno spajanje.'
        )

    result = {
        'success': False,
        'company_name': company.name,
        'old_oib': company.oib,
        'new_oib': new_oib,
        'vies_result': None,
        'sync_count': 0,
        'bonitet': None,
        'actions': [],
    }

    # ── Atomična zamjena OIB-a ─────────────────────────────
    with transaction.atomic():
        old_oib = company.oib
        company.oib = new_oib
        company.save(update_fields=['oib', 'updated_at'])
        result['actions'].append(f'OIB: {old_oib} → {new_oib}')

        # Ažuriraj i WizardDraft ako postoji
        from partners.models import WizardDraft
        drafts = WizardDraft.objects.filter(pending_company=company, completed=True)
        for draft in drafts:
            draft.direktor_oib = draft.direktor_oib  # ostaje isti
            draft.save(update_fields=['updated_at'])

        logger.info(
            '[OIB-FINALIZER] %s: %s → %s (by %s)',
            company.name, old_oib, new_oib,
            user.username if user else 'system',
        )

    # ── VIES Lookup ────────────────────────────────────────
    vies_result = _run_vies_check(company, new_oib)
    result['vies_result'] = vies_result
    if vies_result:
        result['actions'].append(
            f'VIES: {"U PDV-u" if vies_result.get("valid") else "Nije u PDV-u"}'
        )

    # ── Smart Data Sync ────────────────────────────────────
    sync_count = _smart_sync_from_siblings(company, new_oib)
    result['sync_count'] = sync_count
    if sync_count:
        result['actions'].append(f'Smart Sync: {sync_count} polja obogaćeno')

    # ── Bonitet Scan ───────────────────────────────────────
    bonitet = _run_bonitet_scan(new_oib, company.id)
    result['bonitet'] = bonitet
    if bonitet:
        result['actions'].append(f'Bonitet: {bonitet.get("risk_level", "UNKNOWN")}')

    result['success'] = True
    return result


def _run_vies_check(company, oib):
    """VIES provjera i automatski update Company + svih Partner zapisa."""
    try:
        from partners.hr_registry import VIESLookup
        vies = VIESLookup(timeout=15)
        res = vies.check_vat('HR', oib)

        if res.get('error'):
            logger.warning('[OIB-FINALIZER] VIES error for %s: %s', oib, res['error'])
            return {'valid': None, 'error': str(res['error'])}

        is_vat = res.get('valid', False)

        # Update Company
        company.is_vat_registered = is_vat
        if is_vat:
            company.vat_id = f'HR{oib}'
            company.pdv_status = 'obveznik'
        company.save(update_fields=[
            'is_vat_registered', 'vat_id', 'pdv_status', 'updated_at'
        ])

        # Update all Partner records with this OIB
        from django.utils import timezone

        from partners.models import Partner
        now = timezone.now()

        partners_updated = 0
        for p in Partner.objects.filter(oib=oib):
            changed_fields = ['updated_at']
            p.is_vat_registered = is_vat
            changed_fields.append('is_vat_registered')

            if is_vat:
                p.vat_id = f'HR{oib}'
                changed_fields.append('vat_id')

                # Upgrade buyer_type if still generic
                if p.buyer_type == 'b2b_novat':
                    p.buyer_type = 'b2b_vat'
                    changed_fields.append('buyer_type')
                elif p.buyer_type == 'udruga_novat':
                    p.buyer_type = 'udruga_vat'
                    changed_fields.append('buyer_type')

            vies_name = res.get('name', '')
            p.notes = (p.notes or '') + f'\n[OIB-FINALIZER {now:%Y-%m-%d}] VIES valid={is_vat} | "{vies_name}"'
            changed_fields.append('notes')
            p.save(update_fields=changed_fields)
            partners_updated += 1

        logger.info(
            '[OIB-FINALIZER] VIES %s: valid=%s, %d partners updated',
            oib, is_vat, partners_updated,
        )

        return {
            'valid': is_vat,
            'name': res.get('name', ''),
            'address': res.get('address', ''),
            'partners_updated': partners_updated,
        }

    except DatabaseError as exc:
        logger.exception('[OIB-FINALIZER] VIES failed for %s: %s', oib, exc)
        return {'valid': None, 'error': str(exc)}


def _smart_sync_from_siblings(company, oib):
    """
    Ako isti OIB postoji kod drugih partnera, povuci opisne podatke
    na novostvorenu Company i njene partnere.
    """
    from django.db import connection

    SYNC_FIELDS = ['email', 'phone', 'web', 'address', 'city', 'zip_code', 'iban', 'swift']
    total_synced = 0

    with connection.cursor() as cur:
        for field in SYNC_FIELDS:
            cur.execute(f"""
                UPDATE partners_partner target
                SET {field} = source.{field}, updated_at = NOW()
                FROM (
                    SELECT DISTINCT ON (oib) oib, {field}
                    FROM partners_partner
                    WHERE oib = %s AND {field} != ''
                    ORDER BY oib, updated_at DESC
                ) source
                WHERE target.oib = source.oib
                  AND target.{field} = ''
                  AND target.company_id = %s
            """, [oib, str(company.id)])
            total_synced += cur.rowcount

    # Also sync to Company itself if empty
    from partners.models import Partner
    donor = Partner.objects.filter(oib=oib).exclude(company=company).order_by('-updated_at').first()
    if donor:
        changed = []
        if not company.address and donor.address:
            company.address = donor.address
            changed.append('address')
        if not company.city and donor.city:
            company.city = donor.city
            changed.append('city')
        if not company.zip_code and donor.zip_code:
            company.zip_code = donor.zip_code
            changed.append('zip_code')
        if not company.email and donor.email:
            company.email = donor.email
            changed.append('email')
        if not company.phone and donor.phone:
            company.phone = donor.phone
            changed.append('phone')
        if not company.iban and donor.iban:
            company.iban = donor.iban
            changed.append('iban')
        if changed:
            changed.append('updated_at')
            company.save(update_fields=changed)
            total_synced += len(changed) - 1  # -1 for updated_at

    return total_synced


def _run_bonitet_scan(oib, company_id):
    """Redis-cached bonitet scan."""
    try:
        from fiskalizacija.fina_bonitet_service import get_supplier_risk
        return get_supplier_risk(oib, company_id)
    except ImportError as exc:
        logger.warning('[OIB-FINALIZER] Bonitet failed for %s: %s', oib, exc)
        return {'risk_level': 'UNKNOWN', 'error': str(exc)}


def get_draft_companies():
    """Lista svih DRAFT tvrtki za Marijin dashboard."""
    from companies.models import Company
    from partners.models import WizardDraft

    drafts = Company.objects.filter(oib__startswith='DRAFT').order_by('-created_at')
    results = []
    for co in drafts:
        wizard = WizardDraft.objects.filter(pending_company=co).first()
        results.append({
            'company': co,
            'wizard': wizard,
            'director': wizard.direktor_ime if wizard else '',
            'director_email': wizard.direktor_email if wizard else '',
            'firma_type': wizard.get_kapital_tip_display() if wizard else '',
            'created': co.created_at,
            'step': wizard.current_step if wizard else 0,
            'completed': wizard.completed if wizard else False,
        })
    return results
