"""
intelligence/services.py
Glavna logika Intelligence agenta.
"""
import logging
import json
import re
import datetime

from django.utils import timezone

logger = logging.getLogger('intelligence')


def run_intelligence_job(job):
    """Pokreni jedan job -- provjeri sve izvore i generiraj rezultate."""
    from intelligence.models import IntelligenceResult, IntelligenceSource, FundOpportunity
    from core.gemini_agent import GeminiAgent

    results_count = 0
    sent_count = 0
    sources = job.sources.filter(aktivan=True)

    for source in sources:
        # Provjeri je li proslo dovoljno sati od zadnje provjere
        if source.zadnja_provjera:
            hours_since = (timezone.now() - source.zadnja_provjera).total_seconds() / 3600
            if hours_since < source.provjeri_svakih_sati:
                continue

        try:
            agent = GeminiAgent(max_steps=5)
            task = (
                f"Procitaj URL: {source.url}\n"
                f"Opis izvora: {source.xpath_ili_opis or source.get_tip_display()}\n\n"
                f"Profil firme koja me zanima:\n"
                f"{job.opis_poslovanja or job.company.name}\n"
                f"Kljucne rijeci: {job.kljucne_rijeci}\n\n"
                f"Zadatak:\n"
                f"1. Procitaj sadrzaj URL-a (koristi exec_command s curl)\n"
                f"2. Pronadi relevantne natjecaje/ponude/vijesti koji odgovaraju profilu\n"
                f"3. Za svaki relevantan pronalazak odgovori u formatu JSON:\n"
                '{"pronasci": [{"naslov": "...", "summary": "...", "url": "...", '
                '"relevantnost": 85, "tip": "eu_fond|hr_poticaj|trzisna_cijena|vijest", '
                '"rok_prijave": "2026-06-01", "iznos_max_eur": 50000, '
                '"promo_tekst": "OPG, ovo je idealna prilika...", '
                '"checklist": ["Mora biti OPG", "Potreban ARKOD broj"]}]}\n'
                'Ako nema nista relevantno, vrati: {"pronasci": []}\n'
                'Vrati SAMO JSON, bez komentara.'
            )
            result = agent.run_task(task)

            # Parsiraj JSON iz rezultata
            output = str(result)
            json_match = re.search(r'\{.*"pronasci".*\}', output, re.DOTALL)
            if not json_match:
                source.zadnja_provjera = timezone.now()
                source.save(update_fields=['zadnja_provjera'])
                continue

            data = json.loads(json_match.group())
            pronasci = data.get('pronasci', [])

            for p in pronasci:
                relevantnost = int(p.get('relevantnost', 0))
                if relevantnost < 40:
                    continue

                # Kreira FundOpportunity za fond natjecaje
                fund_opp = None
                if p.get('tip') in ('eu_fond', 'hr_poticaj') and p.get('rok_prijave'):
                    try:
                        rok = datetime.date.fromisoformat(p['rok_prijave'])
                        fund_opp, _ = FundOpportunity.objects.get_or_create(
                            naziv=p['naslov'][:300],
                            defaults={
                                'tip': 'eu_eafrd' if 'EU' in p.get('tip', '') else 'hr_apprrr',
                                'tijelo': 'AI Intelligence',
                                'opis': p['summary'],
                                'url': p.get('url', ''),
                                'rok_prijave': rok,
                                'iznos_max_eur': p.get('iznos_max_eur'),
                                'ai_checklist': p.get('checklist', []),
                                'ai_summary': p['summary'][:500],
                                'otkrio_intelligence': True,
                            }
                        )
                    except Exception:
                        pass

                # Spremi rezultat
                ir = IntelligenceResult.objects.create(
                    job=job,
                    source=source,
                    naslov=p['naslov'][:300],
                    summary=p['summary'],
                    url=p.get('url', ''),
                    ai_relevantnost=relevantnost,
                    promo_tekst=p.get('promo_tekst', ''),
                    fund_opportunity=fund_opp,
                )
                results_count += 1

                # Posalji WhatsApp ako relevantnost > 60
                if relevantnost >= 60 and job.obavijesti_whatsapp:
                    sent = _posalji_obavijest(job, ir)
                    if sent:
                        ir.status = 'obavljeno'
                        ir.obavljeno_at = timezone.now()
                        ir.save(update_fields=['status', 'obavljeno_at'])
                        sent_count += 1

            source.zadnja_provjera = timezone.now()
            source.save(update_fields=['zadnja_provjera'])

        except Exception as e:
            logger.error('Source %s failed: %s', source.naziv, e)

    job.zadnji_run = timezone.now()
    job.save(update_fields=['zadnji_run'])

    return results_count, sent_count


def _posalji_obavijest(job, result):
    """Posalji WhatsApp obavijest korisniku."""
    from core.whatsapp import send_text
    try:
        phone = job.whatsapp_broj
        if not phone:
            from accounts.models import UserProfile
            profile = UserProfile.objects.filter(
                company=job.company, role='company_admin'
            ).first()
            if profile:
                phone = getattr(profile.user, 'phone', '') or ''

        if not phone:
            return False

        msg = (
            f'Poslovna inteligencija -- nova prilika\n\n'
            f'*{result.naslov}*\n\n'
            f'{result.summary[:300]}\n\n'
            f'Relevantnost: {result.ai_relevantnost}%\n'
        )
        if result.promo_tekst:
            msg += f'\n{result.promo_tekst[:200]}'
        if result.url:
            msg += f'\n\nLink: {result.url}'

        r = send_text(phone, msg)
        return r.get('success', False)
    except Exception as e:
        logger.error('Obavijest failed: %s', e)
        return False


def create_futures_listing_from_crop(crop_plan):
    """
    Automatski kreira FuturesListing na Burzi kad je visak usjeva spreman.
    """
    import datetime
    from marketplace.models import FuturesListing, MarketplaceCategory

    # Provjeri nije li vec kreiran listing za ovu godinu i kulturu
    existing = FuturesListing.objects.filter(
        seller_company=crop_plan.company,
        name__icontains=crop_plan.get_kultura_display(),
        available_from__year=crop_plan.godina,
    ).exists()

    if existing:
        return False

    cat_map = {
        'kukuruz': 'Zitarice',
        'kukuruz_silaza': 'Zitarice',
        'psenica': 'Zitarice',
        'jecam': 'Zitarice',
        'djetelina': 'Krmno bilje',
        'livada': 'Krmno bilje',
        'soja': 'Uljarice',
        'suncokret': 'Uljarice',
    }
    cat_naziv = cat_map.get(crop_plan.kultura, 'Ostalo')
    category, _ = MarketplaceCategory.objects.get_or_create(name=cat_naziv)

    FuturesListing.objects.create(
        seller_company=crop_plan.company,
        category=category,
        name=f'{crop_plan.get_kultura_display()} -- {crop_plan.sorta or "domace"} {crop_plan.godina}',
        description=(
            f'OPG {crop_plan.company.name} nudi visak usjeva {crop_plan.get_kultura_display()}.\n'
            f'Godina: {crop_plan.godina} | Prinos: {crop_plan.stvarni_prinos_t or "U berbi"} t\n'
            f'{"Ekoloska proizvodnja" if crop_plan.is_organic else "Konvencionalna proizvodnja"}'
        ),
        unit='t',
        unit_price=0,
        total_capacity=crop_plan.procijenjeni_visak_t,
        available_from=datetime.date(crop_plan.godina, 9, 1),
        available_until=datetime.date(crop_plan.godina, 12, 31),
        booking_deadline=datetime.date(crop_plan.godina, 8, 1),
        is_organic=crop_plan.is_organic,
        status='open',
    )
    return True
