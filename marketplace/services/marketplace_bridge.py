"""
marketplace/services/marketplace_bridge.py — "Ponudi na burzi" servis

Univerzalni bridge koji povezuje udruge modele s MarketplaceProduct:
- MedProizvodnja → med listing
- BerbaLog → voće listing
- RakijaProizvodnja → rakija listing
- EggRecord → jaja listing
- Golub → aukcija listing

Auto-expiry: 24h jaja, 48h voće, 7d med/rakija, 30d golub aukcija
Geofencing: kvarljivo → delivery_zone 30km
"""
import logging
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from django.utils.text import slugify

logger = logging.getLogger('marketplace')

# Expiry pravila po tipu izvora
EXPIRY_RULES = {
    'EggRecord':          timedelta(hours=24),
    'BerbaLog':           timedelta(hours=48),
    'MedProizvodnja':     timedelta(days=7),
    'RakijaProizvodnja':  timedelta(days=7),
    'Golub':              timedelta(days=30),
}

# Kvarljivi proizvodi — geofencing 30km
PERISHABLE_MODELS = {'EggRecord', 'BerbaLog'}

# Kategorija slug mapping
CATEGORY_SLUGS = {
    'EggRecord':         'jaja',
    'BerbaLog':          'voce',
    'MedProizvodnja':    'med',
    'RakijaProizvodnja': 'rakija',
    'Golub':             'golubi-aukcija',
}


def publish_to_marketplace(source_model, source_id, price, qty, expiry_hours=None, opg_number=''):
    """
    Objavi proizvod na tržnicu iz bilo kojeg source modela.

    Args:
        source_model: str — naziv modela (npr. 'EggRecord')
        source_id: int — PK izvora
        price: Decimal — cijena po jedinici
        qty: Decimal — količina
        expiry_hours: int|None — override za auto-expiry (sati)
        opg_number: str — OPG broj (obavezan za hranu)

    Returns:
        MarketplaceProduct instance
    """
    from marketplace.models import MarketplaceCategory, MarketplaceProduct

    source_obj, company, name, unit, description = _resolve_source(source_model, source_id)

    # Expiry
    if expiry_hours:
        expires_at = timezone.now() + timedelta(hours=expiry_hours)
    else:
        delta = EXPIRY_RULES.get(source_model, timedelta(days=7))
        expires_at = timezone.now() + delta

    # Geofencing
    delivery_zone_km = 30 if source_model in PERISHABLE_MODELS else None

    # Kategorija
    cat_slug = CATEGORY_SLUGS.get(source_model, '')
    category = None
    if cat_slug:
        category, _ = MarketplaceCategory.objects.get_or_create(
            slug=cat_slug,
            defaults={'name': cat_slug.replace('-', ' ').title(), 'icon': _get_icon(source_model)}
        )

    # Slug — unique
    base_slug = slugify(f'{name}-{source_model.lower()}-{source_id}')
    slug = base_slug[:220]

    # Upsert — ako već postoji listing za isti source, ažuriraj
    product, created = MarketplaceProduct.objects.update_or_create(
        source_model=source_model,
        source_id=source_id,
        seller_company=company,
        defaults={
            'name':             name[:200],
            'slug':             slug,
            'description':      description,
            'category':         category,
            'unit_price':       Decimal(str(price)),
            'unit':             unit,
            'available_qty':    Decimal(str(qty)),
            'is_available':     True,
            'auto_listed':      True,
            'expires_at':       expires_at,
            'delivery_zone_km': delivery_zone_km,
            'opg_number':       opg_number,
            'disclaimer_text':  _get_disclaimer(source_model),
        }
    )

    # Set auction mode for collectibles (Golub)
    if source_model == 'Golub':
        product.is_auction = True
        product.starting_bid = product.unit_price
        product.current_bid = None
        product.bid_count = 0
        product.auction_status = 'active'
        product.save(update_fields=[
            'is_auction', 'starting_bid', 'current_bid', 'bid_count', 'auction_status',
        ])

    action = 'created' if created else 'updated'
    logger.info('MarketplaceBridge: %s listing %s for %s #%s (%s)',
                action, product.pk, source_model, source_id, company.name)

    return product


def _resolve_source(source_model, source_id):
    """Dohvati source objekt i izvuci podatke za listing."""
    if source_model == 'EggRecord':
        from udruge.models import EggRecord
        obj = EggRecord.objects.select_related('flock', 'flock__company').get(pk=source_id)
        return (
            obj,
            obj.flock.company,
            f'Svježa jaja — {obj.flock.get_vrsta_display()} ({obj.flock.tip_uzgoja})',
            'kom',
            f'Svježa jaja od {obj.flock.naziv}, {obj.flock.get_tip_uzgoja_display()}. '
            f'Datum nesenja: {obj.datum}.',
        )
    elif source_model == 'MedProizvodnja':
        from udruge.models import MedProizvodnja
        obj = MedProizvodnja.objects.select_related('pcelinjak', 'pcelinjak__company').get(pk=source_id)
        return (
            obj,
            obj.pcelinjak.company,
            f'Med {obj.get_vrsta_display()} — {obj.kolicina_kg} kg',
            'kg',
            f'Med {obj.get_vrsta_display()}, vrcanje {obj.datum_vrcanja}. '
            f'Vlaga: {obj.vlaga_posto}%. Serija: {obj.serija}.',
        )
    elif source_model == 'BerbaLog':
        from udruge.models import BerbaLog
        obj = BerbaLog.objects.select_related('vocnjak', 'vocnjak__company').get(pk=source_id)
        return (
            obj,
            obj.vocnjak.company,
            f'Voće — {obj.vocnjak.naziv} ({obj.get_kvaliteta_display()})',
            'kg',
            f'Berba {obj.datum}, kvaliteta {obj.get_kvaliteta_display()}. '
            f'Količina: {obj.kolicina_kg} kg.',
        )
    elif source_model == 'RakijaProizvodnja':
        from udruge.models import RakijaProizvodnja
        obj = RakijaProizvodnja.objects.select_related('company').get(pk=source_id)
        return (
            obj,
            obj.company,
            f'{obj.naziv} — {obj.get_tip_rakije_display()} {obj.godina}',
            'l',
            f'{obj.naziv}, {obj.get_tip_rakije_display()}, {obj.alkohol_posto}% alk. '
            f'Godina: {obj.godina}. Serija: {obj.serija}.',
        )
    elif source_model == 'Golub':
        from udruge.models import Golub
        obj = Golub.objects.select_related('company', 'golubinjak').get(pk=source_id)
        return (
            obj,
            obj.company,
            f'Golub {obj.prsten_broj} — {obj.naziv or "bez naziva"}',
            'kom',
            f'Golub {obj.prsten_broj}, {obj.get_spol_display()}, boja: {obj.boja}. '
            f'Utrke: {obj.broj_utrka}, pobjede: {obj.broj_pobjeda}. '
            f'Golubinjak: {obj.golubinjak.naziv}.',
        )
    else:
        raise ValueError(f'Nepoznat source_model: {source_model}')


def _get_icon(source_model):
    return {
        'EggRecord':         '🥚',
        'BerbaLog':          '🍎',
        'MedProizvodnja':    '🍯',
        'RakijaProizvodnja': '🥃',
        'Golub':             '🕊️',
    }.get(source_model, '📦')


def _get_disclaimer(source_model):
    base = 'Proizvod dolazi izravno s OPG-a. Prije konzumacije provjerite alergene i rok trajanja.'
    extras = {
        'EggRecord':         ' Jaja čuvati na hladnom (do 5°C). Potrošiti u roku od 28 dana od datuma nesenja.',
        'MedProizvodnja':    ' Med je prirodni proizvod. Ne davati djeci mlađoj od 1 godine.',
        'RakijaProizvodnja': ' Alkoholno piće — zabranjena prodaja maloljetnicima. Pij odgovorno.',
        'BerbaLog':          ' Voće oprati prije konzumacije.',
        'Golub':             ' Aukcija sportskog goluba. Kupac preuzima brigu o životinj.',
    }
    return base + extras.get(source_model, '')


def deactivate_expired_listings():
    """
    Ghost Inventory fix — deaktivira expired listings.
    Poziva se iz Celery taska svakih 6h.
    Returns: dict s brojem deaktiviranih.
    """
    from marketplace.models import MarketplaceProduct

    now = timezone.now()
    expired = MarketplaceProduct.objects.filter(
        auto_listed=True,
        is_available=True,
        expires_at__isnull=False,
        expires_at__lt=now,
    )

    count = expired.count()
    if count:
        expired.update(is_available=False)
        logger.info('Ghost Inventory: deaktivirano %d expired listinga', count)

    return {'deactivated': count}


def get_expiring_soon(hours=6):
    """Listinzi koji ističu u sljedećih N sati — za push notif."""
    from marketplace.models import MarketplaceProduct

    now = timezone.now()
    threshold = now + timedelta(hours=hours)

    return MarketplaceProduct.objects.filter(
        auto_listed=True,
        is_available=True,
        expires_at__isnull=False,
        expires_at__gt=now,
        expires_at__lte=threshold,
    ).select_related('seller_company')
